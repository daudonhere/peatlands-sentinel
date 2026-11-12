from typing import Any
import httpx
from pydantic import BaseModel, Field

from app.config import get_settings


class RiskAssessment(BaseModel):
    threat_level: str = Field(description="Low, Moderate, High, or Critical")
    peat_moisture_status: str = Field(description="Wet, Draining, or Critical Dry")
    fire_risk_summary: str = Field(
        description="Brief explanation of wildfire susceptibility"
    )
    recommended_actions: list[str] = Field(default_factory=list)


async def generate_analyst_brief(metrics: dict[str, Any]) -> RiskAssessment:
    """Asks local LLM via Ollama to generate risk assessment from raster metrics."""
    settings = get_settings()
    prompt = (
        "You are an environmental satellite analyst for peatlands conservation.\n"
        f"Analyze these metrics: {metrics}.\n"
        "Return valid JSON matching this schema:\n"
        "{\n"
        '  "threat_level": "Low" | "Moderate" | "High" | "Critical",\n'
        '  "peat_moisture_status": "Wet" | "Draining" | "Critical Dry",\n'
        '  "fire_risk_summary": "1-2 sentence risk explanation",\n'
        '  "recommended_actions": ["action 1", "action 2"]\n'
        "}"
    )

    try:
        async with httpx.AsyncClient(timeout=25.0) as client:
            resp = await client.post(
                f"{settings.ollama_base_url}/api/generate",
                json={
                    "model": settings.ollama_model,
                    "prompt": prompt,
                    "stream": False,
                    "format": "json",
                },
            )
            resp.raise_for_status()
            raw_response = resp.json().get("response", "{}")
            return RiskAssessment.model_validate_json(raw_response)
    except Exception:
        # Fallback heuristic when Ollama server is offline
        ndvi = float(metrics.get("mean_ndvi", 0.5))
        ndwi = float(metrics.get("mean_ndwi", 0.0))
        dnbr = float(metrics.get("max_dnbr", 0.0))

        if dnbr > 0.44 or (ndwi < -0.2 and ndvi < 0.3):
            threat = "Critical"
            status = "Critical Dry"
            summary = "High fire susceptibility observed with severe dryness and degraded canopy."
            actions = ["Deploy patrol team", "Verify water table canal blocks"]
        elif ndwi < 0.0:
            threat = "Moderate"
            status = "Draining"
            summary = "Moisture deficit detected across peat dome surface."
            actions = ["Monitor hotspot feeds", "Schedule re-inspection in 5 days"]
        else:
            threat = "Low"
            status = "Wet"
            summary = "Hydrological balance stable. Healthy vegetation cover detected."
            actions = ["Maintain standard observation frequency"]

        return RiskAssessment(
            threat_level=threat,
            peat_moisture_status=status,
            fire_risk_summary=summary,
            recommended_actions=actions,
        )
