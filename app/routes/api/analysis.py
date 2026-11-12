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
    get_analysis_arrays,
    get_analysis_run,
    list_analysis_runs,
    save_analysis_run,
)

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

    area_ha = calculate_polygon_area_hectares(geom_dict)
    run_id = f"sentinel_{uuid.uuid4().hex[:8]}"
    created_at = datetime.now(timezone.utc).isoformat()

    (
        (spectral_summary, transitions, arrays, source_meta, scatter),
        dem_grid,
    ) = await asyncio.gather(
        resolve_spectral(bbox, payload, run_id, area_ha),
        resolve_dem(bbox),
    )

    topography = compute_dem_topography_summary(bbox, elev_grid=dem_grid)
    metrics_payload = spectral_summary.model_dump()
    metrics_payload.update(topography)
    metrics_payload.update(source_meta)
    enriched = enrich_metrics(metrics_payload)
    metrics_payload = enriched["metrics"]
    accuracy = ModelAccuracy.model_validate(enriched["accuracy"])
    time_series = await resolve_time_series(bbox, payload, run_id, spectral_summary)

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
        extra_data={
            "accuracy": accuracy.model_dump(),
            "time_series": [point.model_dump() for point in time_series],
            "class_scatter": [point.model_dump() for point in scatter],
            "data_source": source_meta.get(
                "source", payload.data_source or "planetary_computer"
            ),
        },
    )

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
    )


@router.get("/{run_id}")
async def get_run_details(run_id: str):
    run = get_analysis_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Analysis run not found.")
    return run


@router.get("/{run_id}/overlay.png")
async def get_run_overlay_image(run_id: str, period: str = "post", index: str = "ndvi"):
    run = get_analysis_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Analysis run not found.")

    arrays = get_analysis_arrays(run_id) or {}
    key = f"pre_{index}" if period == "pre" and f"pre_{index}" in arrays else index
    values = arrays.get(key)
    if values is not None and index != "ndvi":
        png_bytes = render_index_png(values, index)
    else:
        png_bytes = generate_spectral_overlay_png(
            run.get("target", "peat_moisture"),
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


@router.get("/history/list")
async def list_recent_analyses():
    return list_analysis_runs(limit=20)
