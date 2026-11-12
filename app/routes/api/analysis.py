import asyncio
from datetime import datetime, timezone
import io
import uuid
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from app.schemas.analysis import (
    AnalysisPipelineRequest,
    AnalysisPipelineResponse,
    GeoJSONFeature,
    SpectralSummary,
)
from app.services.geospatial import (
    extract_bbox_from_geometry,
    calculate_polygon_area_hectares,
    compute_dem_topography_summary,
)
from app.services.hydrology import evaluate_peat_hydrology_profile
from app.services.classifier import (
    simulate_aoi_transitions,
    build_spectral_summary_from_live,
    classify_live_arrays,
)
from app.services.ai_analyst import generate_analyst_report
from app.services.storage import (
    save_analysis_run,
    get_analysis_run,
    get_analysis_arrays,
    list_analysis_runs,
)
from app.services.exporter import create_export_zip_package
from app.services.renderer import generate_spectral_overlay_png

router = APIRouter(prefix="/api/analysis", tags=["Analysis Pipeline"])


async def _resolve_spectral(
    bbox: list[float],
    payload: AnalysisPipelineRequest,
    run_id: str,
    area_ha: float,
) -> tuple[SpectralSummary, list, dict, dict]:
    try:
        from app.services import cog as _cog_module

        live = await _cog_module.fetch_live_pipeline_metrics(
            bbox=bbox,
            pre_date_range=payload.pre_date_range,
            post_date_range=payload.post_date_range,
            max_cloud=payload.max_cloud_cover,
        )
        summary = build_spectral_summary_from_live(live)
        transitions = classify_live_arrays(
            {"_arrays": live.get("_pre_arrays", live["_arrays"])},
            {"_arrays": live["_arrays"]},
            area_ha,
        )
        arrays = {
            **live["_arrays"],
            "pre_ndvi": live.get("_pre_arrays", {}).get(
                "ndvi", live["_arrays"]["ndvi"]
            ),
            "pre_nbr": live.get("_pre_arrays", {}).get("nbr", live["_arrays"]["nbr"]),
        }
        extra = {
            "source": live.get("source", "live_cog"),
            "pre_scene_id": live.get("pre_scene_id"),
            "post_scene_id": live.get("post_scene_id"),
            "pre_datetime": live.get("pre_datetime"),
            "post_datetime": live.get("post_datetime"),
            "valid_pixel_ratio": live.get("valid_pixel_ratio"),
        }
        return summary, transitions, arrays, extra
    except Exception:
        summary, transitions = simulate_aoi_transitions(payload.target, run_id, area_ha)
        return summary, transitions, {}, {"source": "simulation"}


async def _resolve_dem(bbox: list[float]):
    from app.services import cog as _cog_module

    return await _cog_module.fetch_live_dem(bbox)


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

    area_ha = calculate_polygon_area_hectares(geom_dict)
    run_id = f"sentinel_{uuid.uuid4().hex[:8]}"
    created_at = datetime.now(timezone.utc).isoformat()

    (
        (spectral_summary, transitions, arrays, source_meta),
        dem_grid,
    ) = await asyncio.gather(
        _resolve_spectral(bbox, payload, run_id, area_ha),
        _resolve_dem(bbox),
    )

    topography = compute_dem_topography_summary(bbox, elev_grid=dem_grid)
    metrics_payload = spectral_summary.model_dump()
    metrics_payload.update(topography)
    metrics_payload.update(source_meta)
    hydrology = evaluate_peat_hydrology_profile(metrics_payload)
    metrics_payload.update(hydrology)

    ai_report = await generate_analyst_report(
        target=payload.target,
        metrics=metrics_payload,
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
        metrics_data=metrics_payload,
        transitions_data=[t.model_dump() for t in transitions],
        ai_report_data=ai_report.model_dump(),
        arrays=arrays or None,
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


@router.get("/{run_id}/overlay.png")
async def get_run_overlay_image(run_id: str, period: str = "post"):
    run = get_analysis_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Analysis run not found.")

    target = run.get("target", "peat_moisture")
    metrics = run.get("metrics", {})
    arrays = get_analysis_arrays(run_id)
    png_bytes = generate_spectral_overlay_png(
        target, metrics, width=256, height=256, period=period, arrays=arrays
    )
    return StreamingResponse(io.BytesIO(png_bytes), media_type="image/png")


@router.get("/{run_id}/export")
async def export_analysis_bundle(run_id: str):
    run = get_analysis_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Analysis run not found.")

    arrays = get_analysis_arrays(run_id)
    bbox = run.get("geojson", {}).get("bbox", [0, 0, 1, 1])
    ndvi_arr = arrays.get("ndvi") if arrays else None
    zip_stream = create_export_zip_package(run, raster_values=ndvi_arr, bbox=bbox)
    filename = f"{run_id}_export.zip"

    return StreamingResponse(
        zip_stream,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/history/list")
async def list_recent_analyses():
    return list_analysis_runs(limit=20)
