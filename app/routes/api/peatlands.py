from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.services.ingestion import search_stac_items
from app.services.ai_analyst import generate_analyst_brief, RiskAssessment

router = APIRouter(prefix="/api/peatlands", tags=["Peatlands"])


class AOIRequest(BaseModel):
    bbox: list[float]  # [min_lon, min_lat, max_lon, max_lat]
    datetime_range: str = "2024-01-01/2024-12-31"


@router.post("/scenes")
async def get_scenes_for_aoi(payload: AOIRequest):
    """Finds Sentinel-1 and Sentinel-2 scenes covering the area of interest."""
    if len(payload.bbox) != 4:
        raise HTTPException(
            status_code=400, detail="BBox must contain exactly 4 coordinates."
        )

    try:
        s2_items = await search_stac_items(
            bbox=payload.bbox,
            datetime_range=payload.datetime_range,
            collections=["sentinel-2-l2a"],
            max_items=4,
        )
        s1_items = await search_stac_items(
            bbox=payload.bbox,
            datetime_range=payload.datetime_range,
            collections=["sentinel-1-grd"],
            max_items=4,
        )
        return {
            "optical_scenes": [
                {
                    "id": item["id"],
                    "datetime": item["properties"].get("datetime"),
                    "cloud_cover": item["properties"].get("eo:cloud_cover"),
                    "assets": list(item["assets"].keys()),
                }
                for item in s2_items
            ],
            "sar_scenes": [
                {
                    "id": item["id"],
                    "datetime": item["properties"].get("datetime"),
                    "polarizations": item["properties"].get("sar:polarizations"),
                }
                for item in s1_items
            ],
        }
    except Exception as exc:
        raise HTTPException(
            status_code=502, detail=f"STAC search failed: {exc}"
        ) from exc


@router.get("/assess-risk", response_model=RiskAssessment)
async def assess_risk(
    ndvi: float = Query(0.65, ge=-1.0, le=1.0),
    ndwi: float = Query(0.12, ge=-1.0, le=1.0),
    dnbr: float = Query(0.04, ge=-1.0, le=2.0),
):
    """Computes AI-assisted risk status from observed spectral indices."""
    metrics = {
        "mean_ndvi": ndvi,
        "mean_ndwi": ndwi,
        "max_dnbr": dnbr,
    }
    return await generate_analyst_brief(metrics)
