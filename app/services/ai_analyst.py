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
    sar = float(metrics.get("mean_sar_cross_ratio", -10.0))
    subsidence = float(metrics.get("subsidence_rate_cm_year", 1.5))
    co2 = float(metrics.get("co2_emission_tco2e_ha_year", 0.0))
    area = float(metrics.get("area_hectares", 0.0))
    wrc = float(metrics.get("water_retention_capacity", 0.5))
    drain = float(metrics.get("drainage_intensity", 0.3))
    canal = float(metrics.get("canal_density_km_per_km2", 0.5))
    mndwi = float(metrics.get("mean_mndwi", 0.1))
    nbr = float(metrics.get("mean_nbr", 0.5))
    transitions = metrics.get("land_transitions", [])

    # Build transition summary
    trans_text = ""
    if transitions:
        top = transitions[0] if isinstance(transitions, list) else {}
        if isinstance(top, dict):
            trans_text = f" Top transition: {top.get('from_class', '?')} to {top.get('to_class', '?')} ({top.get('area_hectares', 0):.1f} ha)."

    # Determine threat level using multiple indicators
    threat_score = 0
    if dnbr > 0.40:
        threat_score += 3
    if ndwi < -0.15:
        threat_score += 2
    if bsi > 0.3:
        threat_score += 2
    if wtd_cm < -80:
        threat_score += 3
    if wtd_cm < -55:
        threat_score += 1
    if ndmi < 0.05:
        threat_score += 1
    if ndvi < 0.3:
        threat_score += 1
    if co2 > 5.0:
        threat_score += 2
    if subsidence > 3.0:
        threat_score += 1
    if drain > 0.6:
        threat_score += 1
    if hazard and hazard.lower() not in ("", "low", "none"):
        threat_score += 1

    if threat_score >= 6:
        threat = "Critical"
        status = "Critical Dry"
    elif threat_score >= 3:
        threat = "Moderate"
        status = "Draining"
    else:
        threat = "Low"
        status = "Wet"

    # Fire risk summary
    if threat == "Critical":
        fire_summary = (
            f"High fire susceptibility: severe moisture loss (WTD {wtd_cm:.0f} cm), "
            f"elevated BSI {bsi:.2f}, burn severity dNBR {dnbr:.2f}. "
            f"CO2 emission {co2:.1f} tCO2e/ha/yr."
        )
    elif threat == "Moderate":
        fire_summary = (
            f"Moderate moisture deficit: NDWI {ndwi:.2f}, NDMI {ndmi:.2f}, "
            f"drainage intensity {drain:.2f}. Early intervention recommended."
        )
    else:
        fire_summary = (
            f"Hydrological balance stable. NDVI {ndvi:.2f}, moisture retention adequate "
            f"(NDWI {ndwi:.2f}, WRC {wrc:.2f}). Low fire risk."
        )

    # Reasoning
    reasoning = (
        f"Target {target}: NDVI {ndvi:.2f}, NDWI {ndwi:.2f}, NDMI {ndmi:.2f}, "
        f"BSI {bsi:.2f}, NBR {nbr:.2f}, MNDWI {mndwi:.2f}, SAR {sar:.1f} dB. "
        f"WTD {wtd_cm:.0f} cm, subsidence {subsidence:.1f} cm/yr, "
        f"CO2 {co2:.1f} tCO2e/ha/yr, drainage {drain:.2f}, canal density {canal:.2f} km/km2."
        f"{trans_text}" + (f" Dominant hazard: {hazard}." if hazard else "")
    )

    # Actions based on threat and metrics
    actions = []
    if threat == "Critical":
        actions.append("Dispatch local peatland patrol unit immediately")
        actions.append("Verify canal block water levels")
        if wtd_cm < -80:
            actions.append(
                f"Emergency rewetting: WTD at {wtd_cm:.0f} cm exceeds safe threshold"
            )
        if co2 > 5.0:
            actions.append(f"Carbon emission alert: {co2:.1f} tCO2e/ha/yr")
        actions.append("Report hotspot coordinates to forestry command center")
    elif threat == "Moderate":
        actions.append("Monitor satellite passes at 5-day intervals")
        if drain > 0.5:
            actions.append("Inspect drainage canals for blockage or illegal clearing")
        if subsidence > 2.0:
            actions.append(f"Track subsidence: {subsidence:.1f} cm/yr")
        actions.append("Check for illegal canal clearing activities nearby")
    else:
        actions.append("Maintain baseline environmental surveillance")
        if area > 1000:
            actions.append(f"Continue monitoring {area:.0f} ha peatland area")

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
