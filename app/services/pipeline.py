from __future__ import annotations

import asyncio
from typing import Any

import numpy as np

from app.schemas.analysis import (
    AnalysisPipelineRequest,
    ClassScatterPoint,
    SpectralSummary,
    TimeSeriesPoint,
)
from app.config import get_settings
from app.services.geospatial import polygon_mask

from app.services.classifier import (
    build_spectral_summary_from_live,
    classify_live_arrays,
)
from app.services.hazard import multi_hazard_profile
from app.services.hydrology import evaluate_peat_hydrology_profile
from app.services.model_metrics import (
    class_scatter_from_arrays,
    evaluate_local_model,
)
from app.services.sources import resolve_pipeline_metrics
from app.services.temporal import (
    apply_dnbr_baseline,
    parse_iso_interval,
    series_from_live,
)


def _merge_arrays(pre: dict | None, post: dict | None) -> dict[str, np.ndarray]:
    merged: dict[str, np.ndarray] = {}
    for key, value in (post or {}).items():
        if isinstance(value, np.ndarray):
            merged[key] = value
    for key in ("ndvi", "nbr", "ndmi", "ndwi"):
        value = (pre or {}).get(key)
        if isinstance(value, np.ndarray):
            merged[f"pre_{key}"] = value
    return merged


def _extract_geometry(payload: Any) -> dict[str, Any] | None:
    aoi = getattr(payload, "aoi", None)
    geom = getattr(aoi, "geometry", aoi) if aoi is not None else None
    if hasattr(geom, "model_dump"):
        geom = geom.model_dump()
    if isinstance(geom, dict) and geom.get("type") in ("Polygon", "MultiPolygon"):
        return geom
    if isinstance(geom, dict) and geom.get("type") == "Feature":
        inner = geom.get("geometry")
        if isinstance(inner, dict) and inner.get("type") in ("Polygon", "MultiPolygon"):
            return inner
    return None


def _mask_arrays(geometry: Any, bbox: list[float], arrays: Any) -> Any:
    if not isinstance(arrays, dict) or not geometry:
        return arrays
    out = dict(arrays)
    for key, value in list(arrays.items()):
        if isinstance(value, np.ndarray) and value.ndim == 2:
            mask = polygon_mask(geometry, bbox, value.shape)
            out[key] = np.where(mask, value, np.nan).astype(value.dtype, copy=False)
    return out


def _recompute_metrics(
    metrics: dict[str, Any], pre_arrays: Any, post_arrays: Any
) -> None:
    if not isinstance(post_arrays, dict):
        return
    for key, arr_key in (
        ("mean_ndvi", "ndvi"),
        ("mean_ndwi", "ndwi"),
        ("mean_ndmi", "ndmi"),
        ("mean_mndwi", "mndwi"),
        ("mean_nbr", "nbr"),
        ("mean_bsi", "bsi"),
    ):
        arr = post_arrays.get(arr_key)
        if isinstance(arr, np.ndarray):
            finite = arr[np.isfinite(arr)]
            if finite.size:
                metrics[key] = round(float(np.nanmean(finite)), 4)
    arr = post_arrays.get("cross_ratio")
    if isinstance(arr, np.ndarray):
        finite = arr[np.isfinite(arr)]
        if finite.size:
            metrics["mean_sar_cross_ratio"] = round(float(np.nanmean(finite)), 4)
    ndvi_arr = post_arrays.get("ndvi")
    if isinstance(ndvi_arr, np.ndarray):
        finite = ndvi_arr[np.isfinite(ndvi_arr)]
        if finite.size:
            metrics["vegetation_fraction"] = round(float(np.mean(finite > 0.3)), 4)
    mndwi_arr = post_arrays.get("mndwi")
    if isinstance(mndwi_arr, np.ndarray):
        finite = mndwi_arr[np.isfinite(mndwi_arr)]
        if finite.size:
            metrics["water_fraction"] = round(float(np.mean(finite > 0.0)), 4)
    pre_nbr = (pre_arrays or {}).get("nbr") if isinstance(pre_arrays, dict) else None
    post_nbr = post_arrays.get("nbr")
    if isinstance(pre_nbr, np.ndarray) and isinstance(post_nbr, np.ndarray):
        dnbr = pre_nbr - post_nbr
        finite = dnbr[np.isfinite(dnbr)]
        if finite.size:
            metrics["max_dnbr"] = round(float(np.nanmax(finite)), 4)


async def resolve_spectral(
    bbox: list[float],
    payload: AnalysisPipelineRequest,
    area_ha: float,
) -> tuple[SpectralSummary, list, dict, dict, list[ClassScatterPoint]]:
    geometry = _extract_geometry(payload)
    # Fetch real ESA WorldCover training labels when GEE is available
    training_error = None
    try:
        from app.services import gee_analysis as _gee_analysis

        settings = get_settings()
        features, labels, coords = await asyncio.wait_for(
            asyncio.to_thread(
                _gee_analysis.worldcover_training_data,
                bbox,
                settings.gee_samples_per_class,
            ),
            timeout=420.0,
        )
        if features and labels:
            from app.services import classifier as _clf

            _clf.set_worldcover_training(features, labels, coords)
        else:
            training_error = "No WorldCover training samples returned for this AOI."
    except Exception as exc:
        import sys

        print(
            f"[resolve_spectral] WorldCover training failed: {exc!r}",
            file=sys.stderr,
            flush=True,
        )
        training_error = str(exc)
    result = await asyncio.wait_for(
        resolve_pipeline_metrics(
            payload.data_source,
            bbox,
            payload.pre_date_range,
            payload.post_date_range,
            payload.max_cloud_cover,
        ),
        timeout=120.0,
    )
    post_arrays = _mask_arrays(geometry, bbox, result.post_arrays)
    pre_arrays = _mask_arrays(geometry, bbox, result.pre_arrays)
    metrics = dict(result.metrics)
    _recompute_metrics(metrics, pre_arrays, post_arrays)
    summary = build_spectral_summary_from_live(metrics)
    transitions = classify_live_arrays(
        {"_arrays": pre_arrays or post_arrays or {}},
        {"_arrays": post_arrays or {}},
        area_ha,
    )
    arrays = _merge_arrays(pre_arrays, post_arrays)
    scatter = class_scatter_from_arrays(pre_arrays or {}, post_arrays or {})
    extra = {"source": result.source, **result.scene_meta}
    if training_error:
        extra["training_error"] = training_error
    return summary, transitions, arrays, extra, scatter


async def resolve_dem(bbox: list[float]):
    from app.services import cog as _cog_module

    try:
        result = await asyncio.wait_for(_cog_module.fetch_live_dem(bbox), timeout=8.0)
        if result is not None and (
            not hasattr(result, "size") or (result.size > 0 and not np.all(result == 0))
        ):
            return result
    except Exception:
        pass

    try:
        from app.services import gee as _gee_module

        return await asyncio.wait_for(
            asyncio.to_thread(_gee_module.gee_dem_grid, bbox), timeout=45.0
        )
    except Exception:
        return None


async def resolve_time_series(
    bbox: list[float], payload: AnalysisPipelineRequest
) -> list[TimeSeriesPoint]:
    observations: list[dict[str, Any]] = []
    if payload.data_source == "gee":
        try:
            from app.services import gee_series

            rows = await asyncio.wait_for(
                gee_series.gee_time_series(
                    bbox,
                    payload.post_date_range,
                    payload.max_cloud_cover,
                    payload.granularity,
                ),
                timeout=150.0,
            )
            return [TimeSeriesPoint.model_validate(row) for row in rows]
        except Exception:
            observations = []
    else:
        try:
            from app.services.observations import fetch_scene_observations

            observations = await asyncio.wait_for(
                fetch_scene_observations(
                    bbox, payload.post_date_range, payload.max_cloud_cover, 8
                ),
                timeout=8.0,
            )
        except Exception:
            observations = []

    rows = apply_dnbr_baseline(
        series_from_live(observations, granularity=payload.granularity)
    )
    return [TimeSeriesPoint.model_validate(row) for row in rows]


def enrich_metrics(metrics: dict[str, Any]) -> dict[str, Any]:
    metrics.update(evaluate_peat_hydrology_profile(metrics))
    metrics.update(multi_hazard_profile(metrics))
    accuracy = evaluate_local_model()
    return {"metrics": metrics, "accuracy": accuracy.model_dump()}
