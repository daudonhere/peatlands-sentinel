from typing import Any
import httpx

from app.config import get_settings
from app.schemas.analysis import AIAnalystReport


async def generate_analyst_report(
    target: str,
    metrics: dict[str, Any],
    transitions: list[dict[str, Any]],
) -> AIAnalystReport:
    """Generates an environmental interpretation using configured AI provider with deterministic fallback."""
    settings = get_settings()

    system_prompt = (
        "You are an environmental satellite analyst evaluating tropical peatlands and deforestation.\n"
        "Analyze the provided multi-temporal telemetry and land transitions.\n"
        "Return strictly valid JSON with this exact schema:\n"
        "{\n"
        '  "threat_level": "Low" | "Moderate" | "High" | "Critical",\n'
        '  "peat_moisture_status": "Wet" | "Draining" | "Critical Dry",\n'
        '  "fire_risk_summary": "1-2 sentence risk explanation",\n'
        '  "classification_reasoning": "2-3 sentences explaining observed spectral/SAR transitions",\n'
        '  "recommended_actions": ["Action 1", "Action 2", "Action 3"]\n'
        "}"
    )

    user_payload = {
        "analysis_target": target,
        "spectral_and_sar_metrics": metrics,
        "top_land_transitions": transitions,
    }

    # 1. Try external AI Provider if API key is provided
    if settings.ai_api_key:
        try:
            headers = {
                "Authorization": f"Bearer {settings.ai_api_key}",
                "Content-Type": "application/json",
            }
            body = {
                "model": settings.ai_model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": str(user_payload)},
                ],
                "response_format": {"type": "json_object"},
            }
            async with httpx.AsyncClient(timeout=20.0) as client:
                res = await client.post(
                    f"{settings.ai_base_url.rstrip('/')}/chat/completions",
                    headers=headers,
                    json=body,
                )
                if res.status_code == 200:
                    raw_content = (
                        res.json()
                        .get("choices", [{}])[0]
                        .get("message", {})
                        .get("content", "{}")
                    )
                    return AIAnalystReport.model_validate_json(raw_content)
        except Exception:
            pass

    # 2. Try Local Ollama if configured
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            res = await client.post(
                f"{settings.ollama_base_url}/api/generate",
                json={
                    "model": settings.ollama_model,
                    "prompt": f"{system_prompt}\nInput: {user_payload}",
                    "stream": False,
                    "format": "json",
                },
            )
            if res.status_code == 200:
                raw_content = res.json().get("response", "{}")
                return AIAnalystReport.model_validate_json(raw_content)
    except Exception:
        pass

    # 3. Deterministic Heuristic Engine
    ndvi = float(metrics.get("mean_ndvi", 0.5))
    ndwi = float(metrics.get("mean_ndwi", 0.1))
    bsi = float(metrics.get("mean_bsi", -0.1))
    dnbr = float(metrics.get("max_dnbr", 0.05))

    if dnbr > 0.40 or (ndwi < -0.15 and bsi > 0.3):
        threat = "Critical"
        status = "Critical Dry"
        fire_summary = "High fire susceptibility observed with severe surface moisture loss and elevated bare soil reflectance."
        reasoning = f"Target {target}: Significant canopy loss identified (NDVI: {ndvi:.2f}, BSI: {bsi:.2f}) with critical burn severity signature (dNBR: {dnbr:.2f})."
        actions = [
            "Dispatch local peatland patrol unit",
            "Verify canal block water levels immediately",
            "Report hotspot coordinates to forestry command center",
        ]
    elif ndwi < 0.0 or bsi > 0.1:
        threat = "Moderate"
        status = "Draining"
        fire_summary = "Moisture deficit detected across the peat dome surface with emerging ground exposure."
        reasoning = f"Target {target}: Transitional land dynamics observed with declining water indices and emerging canopy thinning."
        actions = [
            "Monitor satellite passes at 5-day intervals",
            "Check for illegal canal clearing activities nearby",
        ]
    else:
        threat = "Low"
        status = "Wet"
        fire_summary = "Hydrological balance stable. Dense canopy coverage acts as a natural moisture barrier."
        reasoning = f"Target {target}: Canopy health remains optimal (NDVI: {ndvi:.2f}) with positive water retention (NDWI: {ndwi:.2f})."
        actions = ["Maintain baseline environmental surveillance"]

    return AIAnalystReport(
        threat_level=threat,
        peat_moisture_status=status,
        fire_risk_summary=fire_summary,
        classification_reasoning=reasoning,
        recommended_actions=actions,
    )
