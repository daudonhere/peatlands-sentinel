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
    ModelAccuracy,
)
from app.services.ai_analyst import generate_analyst_report
from app.services.bundle import create_export_zip_package
from app.services.geospatial import (
    calculate_polygon_area_hectares,
    compute_dem_topography_summary,
    extract_bbox_from_geometry,
)
from app.services.pipeline import (
    enrich_metrics,
    resolve_dem,
    resolve_spectral,
    resolve_time_series,
)
from app.services.renderer import generate_spectral_overlay_png, render_index_png
from app.services.storage import (
    delete_analysis_run,
    get_analysis_arrays,
    get_analysis_run,
    list_analysis_runs,
    save_analysis_run,
)

router = APIRouter(prefix="/api/analysis", tags=["Analysis Pipeline"])


_JOBS: dict[str, dict] = {}


def _job_update(
    run_id: str, progress: int, message: str, status: str = "running"
) -> None:
    if run_id in _JOBS:
        _JOBS[run_id]["progress"] = progress
        _JOBS[run_id]["message"] = message
        _JOBS[run_id]["status"] = status


async def execute_analysis_pipeline(
    payload: AnalysisPipelineRequest,
    run_id: str,
    progress_cb=None,
) -> AnalysisPipelineResponse:
    def update(progress: int, message: str) -> None:
        if progress_cb:
            progress_cb(progress, message)

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
    created_at = datetime.now(timezone.utc).isoformat()

    update(10, "Resolving spectral data")
    (
        (spectral_summary, transitions, arrays, source_meta, scatter),
        dem_grid,
    ) = await asyncio.gather(
        resolve_spectral(bbox, payload, run_id, area_ha),
        resolve_dem(bbox),
    )

    update(45, "Computing topography")
    topography = compute_dem_topography_summary(bbox, elev_grid=dem_grid)
    metrics_payload = spectral_summary.model_dump()
    metrics_payload.update(topography)
    metrics_payload.update(source_meta)
    enriched = enrich_metrics(metrics_payload)
    metrics_payload = enriched["metrics"]
    accuracy = ModelAccuracy.model_validate(enriched["accuracy"])
    update(65, "Building time series")
    time_series = await resolve_time_series(bbox, payload, run_id, spectral_summary)

    update(80, "Running AI analyst")
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

    update(92, "Saving run")
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
        extra_data={
            "accuracy": accuracy.model_dump(),
            "time_series": [point.model_dump() for point in time_series],
            "class_scatter": [point.model_dump() for point in scatter],
            "data_source": source_meta.get(
                "source", payload.data_source or "planetary_computer"
            ),
        },
    )

    update(100, "Complete")
    return AnalysisPipelineResponse(
        run_id=run_id,
        created_at=created_at,
        target=payload.target,
        area_hectares=area_ha,
        spectral_metrics=spectral_summary,
        land_transitions=transitions,
        ai_report=ai_report,
        telemetry=metrics_payload,
        accuracy=accuracy,
        time_series=time_series,
        class_scatter=scatter,
        data_source=source_meta.get(
            "source", payload.data_source or "planetary_computer"
        ),
        export_available=True,
        geojson=geojson_envelope,
    )


@router.post("/run", response_model=AnalysisPipelineResponse)
async def run_analysis_pipeline(payload: AnalysisPipelineRequest):
    run_id = f"sentinel_{uuid.uuid4().hex[:8]}"
    return await execute_analysis_pipeline(payload, run_id)


@router.post("/run-async")
async def run_analysis_async(payload: AnalysisPipelineRequest):
    run_id = f"sentinel_{uuid.uuid4().hex[:8]}"
    _JOBS[run_id] = {
        "progress": 0,
        "message": "Queued",
        "status": "running",
        "result": None,
        "error": None,
    }

    async def _job():
        try:

            def cb(p, m):
                _job_update(run_id, p, m, "running")

            result = await execute_analysis_pipeline(payload, run_id, progress_cb=cb)
            _JOBS[run_id]["result"] = result.model_dump()
            _job_update(run_id, 100, "Complete", "done")
        except Exception as exc:
            _JOBS[run_id]["error"] = str(exc)
            _job_update(run_id, 100, "Failed", "error")

    asyncio.create_task(_job())
    return {"job_id": run_id}


@router.get("/{run_id}/status")
async def get_job_status(run_id: str):
    job = _JOBS.get(run_id)
    if job is None:
        run = get_analysis_run(run_id)
        if run is None:
            raise HTTPException(status_code=404, detail="Job not found.")
        return {"progress": 100, "message": "Complete", "status": "done", "result": run}
    return {
        "progress": job["progress"],
        "message": job["message"],
        "status": job["status"],
        "result": job["result"],
        "error": job["error"],
    }


@router.get("/{run_id}")
async def get_run_details(run_id: str):
    run = get_analysis_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Analysis run not found.")
    return run


@router.get("/{run_id}/overlay.png")
async def get_run_overlay_image(
    run_id: str, period: str = "post", index: str = "ndvi", target: str | None = None
):
    run = get_analysis_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Analysis run not found.")

    arrays = get_analysis_arrays(run_id) or {}
    key = f"pre_{index}" if period == "pre" and f"pre_{index}" in arrays else index
    values = arrays.get(key)
    if values is not None and index != "ndvi":
        png_bytes = render_index_png(values, index)
    else:
        objective = target or run.get("target", "peat_moisture")
        png_bytes = generate_spectral_overlay_png(
            objective,
            run.get("metrics", {}),
            width=256,
            height=256,
            period=period,
            arrays=arrays,
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
    zip_stream = create_export_zip_package(
        run, raster_values=ndvi_arr, bbox=bbox, arrays=arrays
    )
    filename = f"{run_id}_export.zip"

    return StreamingResponse(
        zip_stream,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.delete("/{run_id}")
async def delete_run(run_id: str):
    delete_analysis_run(run_id)
    return {"deleted": run_id}


@router.get("/history/list")
async def list_recent_analyses():
    return list_analysis_runs(limit=20)
