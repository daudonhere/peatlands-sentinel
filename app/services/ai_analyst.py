from typing import Any, Literal
import httpx
from pydantic import BaseModel, Field, ValidationError

from app.config import Settings, get_settings
from app.schemas.analysis import AIAnalystReport

_SCHEMAS = (
    "{\n"
    '  "threat_level": "Low" | "Moderate" | "High" | "Critical",\n'
    '  "peat_moisture_status": "Wet" | "Draining" | "Critical Dry",\n'
    '  "fire_risk_summary": "1-2 sentence risk explanation",\n'
    '  "classification_reasoning": "2-3 sentences explaining observed spectral/SAR transitions",\n'
    '  "recommended_actions": ["Action 1", "Action 2", "Action 3"]\n'
    "}"
)

SYSTEM_PROMPT = (
    "You are an environmental satellite analyst evaluating tropical peatlands, "
    "cropland expansion and deforestation.\n"
    "Analyze the provided multi-temporal telemetry, hydrology and land transitions.\n"
    f"Return strictly valid JSON with this exact schema:\n{_SCHEMAS}"
)


class ChatMessage(BaseModel):
    role: Literal["system", "user"]
    content: str


class ChatCompletionRequest(BaseModel):
    model: str
    messages: list[ChatMessage]
    stream: bool = False
    temperature: float = 0.2
    response_format: dict[str, str] | None = None


class ChatCompletionResponse(BaseModel):
    choices: list[dict[str, Any]] = Field(default_factory=list)


class ProviderEndpoint(BaseModel):
    provider: str
    url: str
    model: str
    headers: dict[str, str]
    payload: ChatCompletionRequest


def _strip_fences(raw: str) -> str:
    text = raw.strip()
    if text.startswith("```"):
        parts = text.split("```")
        if len(parts) > 1:
            body = parts[1]
            return body[4:] if body.startswith("json") else body
    return text


def resolve_endpoint(settings: Settings) -> ProviderEndpoint | None:
    provider = (settings.ai_provider or "openai").lower()

    if provider == "ollama":
        if not settings.ollama_api_key:
            return None
        url = settings.ollama_url.rstrip("/")
        return ProviderEndpoint(
            provider="ollama-cloud",
            url=url,
            model=settings.ollama_model,
            headers={
                "Authorization": f"Bearer {settings.ollama_api_key}",
                "Content-Type": "application/json",
            },
            payload=ChatCompletionRequest(
                model=settings.ollama_model,
                messages=[],
            ),
        )

    if provider in ("openrouter", "custom", "openai"):
        if not settings.ai_api_key:
            return None
        base = settings.ai_base_url.rstrip("/")
        if provider == "openrouter":
            base = "https://openrouter.ai/api/v1"
        return ProviderEndpoint(
            provider=provider,
            url=f"{base}/chat/completions",
            model=settings.ai_model,
            headers={
                "Authorization": f"Bearer {settings.ai_api_key}",
                "Content-Type": "application/json",
            },
            payload=ChatCompletionRequest(
                model=settings.ai_model,
                messages=[],
                response_format={"type": "json_object"},
            ),
        )

    return None


def _build_request(endpoint: ProviderEndpoint, user_payload: dict[str, Any]):
    request = endpoint.payload.model_copy(
        update={
            "messages": [
                ChatMessage(role="system", content=SYSTEM_PROMPT),
                ChatMessage(role="user", content=str(user_payload)),
            ]
        }
    )
    body = request.model_dump(exclude_none=True)
    if endpoint.provider == "ollama-cloud":
        body.pop("response_format", None)
    return body


def _extract_content(provider: str, data: dict[str, Any]) -> str:
    if provider == "ollama-cloud":
        return str(
            data.get("response") or data.get("message", {}).get("content") or "{}"
        )
    try:
        return str(
            ChatCompletionResponse.model_validate(data).choices[0]["message"]["content"]
        )
    except (ValidationError, KeyError, IndexError, TypeError):
        return "{}"


async def _query_cloud(
    endpoint: ProviderEndpoint, user_payload: dict[str, Any]
) -> AIAnalystReport | None:
    settings = get_settings()
    try:
        async with httpx.AsyncClient(timeout=settings.ai_timeout_seconds) as client:
            res = await client.post(
                endpoint.url,
                headers=endpoint.headers,
                json=_build_request(endpoint, user_payload),
            )
            if res.status_code != 200:
                return None
            content = _extract_content(endpoint.provider, res.json())
            return AIAnalystReport.model_validate_json(_strip_fences(content))
    except Exception:
        return None


def heuristic_report(target: str, metrics: dict[str, Any]) -> AIAnalystReport:
    ndvi = float(metrics.get("mean_ndvi", 0.5))
    ndwi = float(metrics.get("mean_ndwi", 0.1))
    ndmi = float(metrics.get("mean_ndmi", 0.2))
    bsi = float(metrics.get("mean_bsi", -0.1))
    dnbr = float(metrics.get("max_dnbr", 0.05))
    wtd_cm = float(metrics.get("water_table_depth_cm", -35.0))
    hazard = str(metrics.get("dominant_hazard", ""))

    if dnbr > 0.40 or (ndwi < -0.15 and bsi > 0.3) or wtd_cm < -80:
        threat = "Critical"
        status = "Critical Dry"
        fire_summary = "High fire susceptibility observed with severe surface moisture loss and elevated bare soil reflectance."
        reasoning = (
            f"Target {target}: significant canopy loss identified (NDVI {ndvi:.2f}, "
            f"NDMI {ndmi:.2f}, BSI {bsi:.2f}) with burn severity signature dNBR {dnbr:.2f} "
            f"and water table at {wtd_cm:.0f} cm."
        )
        actions = [
            "Dispatch local peatland patrol unit",
            "Verify canal block water levels immediately",
            "Report hotspot coordinates to forestry command center",
        ]
    elif ndwi < 0.0 or bsi > 0.1 or ndmi < 0.05 or wtd_cm < -55:
        threat = "Moderate"
        status = "Draining"
        fire_summary = "Moisture deficit detected across the peat dome surface with emerging ground exposure."
        reasoning = (
            f"Target {target}: transitional land dynamics observed (NDMI {ndmi:.2f}, "
            f"NDWI {ndwi:.2f}) with declining water retention"
            + (f" and elevated {hazard.lower()} susceptibility." if hazard else ".")
        )
        actions = [
            "Monitor satellite passes at 5-day intervals",
            "Check for illegal canal clearing activities nearby",
        ]
    else:
        threat = "Low"
        status = "Wet"
        fire_summary = "Hydrological balance stable. Dense canopy coverage acts as a natural moisture barrier."
        reasoning = (
            f"Target {target}: canopy health remains optimal (NDVI {ndvi:.2f}) with "
            f"positive moisture retention (NDWI {ndwi:.2f}, NDMI {ndmi:.2f})."
        )
        actions = ["Maintain baseline environmental surveillance"]

    return AIAnalystReport(
        threat_level=threat,
        peat_moisture_status=status,
        fire_risk_summary=fire_summary,
        classification_reasoning=reasoning,
        recommended_actions=actions,
    )


async def generate_analyst_report(
    target: str,
    metrics: dict[str, Any],
    transitions: list[dict[str, Any]],
) -> AIAnalystReport:
    settings = get_settings()
    endpoint = resolve_endpoint(settings)

    user_payload = {
        "analysis_target": target,
        "spectral_and_sar_metrics": metrics,
        "top_land_transitions": transitions,
    }

    if endpoint is not None:
        report = await _query_cloud(endpoint, user_payload)
        if report is not None:
            return report

    return heuristic_report(target, metrics)


def analyst_engine_status() -> dict[str, Any]:
    settings = get_settings()
    endpoint = resolve_endpoint(settings)
    return {
        "mode": endpoint.provider if endpoint else "deterministic-heuristic",
        "model": endpoint.model if endpoint else None,
        "cloud_configured": endpoint is not None,
    }
