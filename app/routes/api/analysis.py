from datetime import datetime, timezone
import uuid
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from app.schemas.analysis import (
    AnalysisPipelineRequest,
    AnalysisPipelineResponse,
    GeoJSONFeature,
)
from app.services.geospatial import (
    extract_bbox_from_geometry,
    calculate_polygon_area_hectares,
)
from app.services.classifier import simulate_aoi_transitions
from app.services.ai_analyst import generate_analyst_report
from app.services.storage import save_analysis_run, get_analysis_run, list_analysis_runs
from app.services.exporter import create_export_zip_package

router = APIRouter(prefix="/api/analysis", tags=["Analysis Pipeline"])


@router.post("/run", response_model=AnalysisPipelineResponse)
async def run_analysis_pipeline(payload: AnalysisPipelineRequest):
    geom_dict = (
        payload.aoi.geometry.model_dump()
        if isinstance(payload.aoi, GeoJSONFeature)
        else payload.aoi.model_dump()
    )

    try:
        bbox = extract_bbox_from_geometry(geom_dict)
    except Exception as exc:
        raise HTTPException(
            status_code=400, detail=f"Invalid GeoJSON geometry: {exc}"
        ) from exc

    area_ha = calculate_polygon_area_hectares(bbox)
    run_id = f"sentinel_{uuid.uuid4().hex[:8]}"
    created_at = datetime.now(timezone.utc).isoformat()

    spectral_summary, transitions = simulate_aoi_transitions(
        payload.target, run_id, area_ha
    )

    ai_report = await generate_analyst_report(
        target=payload.target,
        metrics=spectral_summary.model_dump(),
        transitions=[t.model_dump() for t in transitions],
    )

    geojson_envelope = {
        "type": "Feature",
        "bbox": bbox,
        "geometry": geom_dict,
        "properties": {"run_id": run_id, "target": payload.target, "area_ha": area_ha},
    }

    save_analysis_run(
        run_id=run_id,
        created_at=created_at,
        target=payload.target,
        area_hectares=area_ha,
        geojson_data=geojson_envelope,
        metrics_data=spectral_summary.model_dump(),
        transitions_data=[t.model_dump() for t in transitions],
        ai_report_data=ai_report.model_dump(),
    )

    return AnalysisPipelineResponse(
        run_id=run_id,
        created_at=created_at,
        target=payload.target,
        area_hectares=area_ha,
        spectral_metrics=spectral_summary,
        land_transitions=transitions,
        ai_report=ai_report,
        export_available=True,
    )


@router.get("/{run_id}")
async def get_run_details(run_id: str):
    run = get_analysis_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Analysis run not found.")
    return run


@router.get("/{run_id}/export")
async def export_analysis_bundle(run_id: str):
    run = get_analysis_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Analysis run not found.")

    zip_stream = create_export_zip_package(run)
    filename = f"{run_id}_export.zip"

    return StreamingResponse(
        zip_stream,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/history/list")
async def list_recent_analyses():
    return list_analysis_runs(limit=20)
