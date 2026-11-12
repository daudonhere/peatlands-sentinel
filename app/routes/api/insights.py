from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.services.cog import live_ndvi_for_aoi
from app.services.firms import fetch_active_fires
from app.services.intervention import simulate_canal_blocking
from app.services.storage import get_analysis_run

router = APIRouter(prefix="/api/insights", tags=["Insights"])


class BBoxRequest(BaseModel):
    bbox: list[float] = Field(min_length=4, max_length=4)
    days: int = Field(default=3, ge=1, le=10)
    datetime_range: str = "2024-01-01/2024-12-31"


@router.post("/fires")
async def active_fires(payload: BBoxRequest):
    try:
        fires = await fetch_active_fires(payload.bbox, payload.days)
    except PermissionError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"FIRMS request failed: {exc}") from exc
    return {"count": len(fires), "fires": fires}


@router.post("/live-ndvi")
async def live_ndvi(payload: BBoxRequest):
    try:
        return await live_ndvi_for_aoi(payload.bbox, payload.datetime_range)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"COG read failed: {exc}") from exc


@router.get("/{run_id}/intervention")
async def canal_blocking(run_id: str, dams_per_100ha: float = Query(2.0, ge=0.0, le=20.0)):
    run = get_analysis_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Analysis run not found.")
    wtd = run["metrics"].get("water_table_depth_m", -0.35)
    return simulate_canal_blocking(wtd, run["area_hectares"], dams_per_100ha)
