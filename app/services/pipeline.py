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
from app.services.temporal import parse_iso_interval, series_from_live


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
    run_id: str,
    area_ha: float,
) -> tuple[SpectralSummary, list, dict, dict, list[ClassScatterPoint]]:
    geometry = _extract_geometry(payload)
    # Try to get WorldCover training data and target modulators when GEE is available
    if payload.data_source == "gee":
        try:
            from app.services import gee_analysis as _gee_analysis
            from app.services import reference_data as _ref_data

            features, labels = _gee_analysis.worldcover_training_data(
                bbox, payload.post_date_range, points_per_class=30
            )
            if features and labels:
                from app.services import classifier as _clf

                _clf.set_worldcover_training(features, labels)

            modulators = _gee_analysis.compute_target_modulators(
                bbox, payload.post_date_range
            )
            if modulators:
                _ref_data.update_target_modulators(modulators)
        except Exception:
            pass
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
    return summary, transitions, arrays, extra, scatter


async def resolve_dem(bbox: list[float]):
    from app.services import cog as _cog_module

    try:
        return await asyncio.wait_for(_cog_module.fetch_live_dem(bbox), timeout=8.0)
    except Exception:
        return None


async def resolve_time_series(
    bbox: list[float],
    payload: AnalysisPipelineRequest,
    run_id: str,
    summary: SpectralSummary,
) -> list[TimeSeriesPoint]:
    start, end = parse_iso_interval(payload.post_date_range)
    observations: list[dict[str, Any]] = []
    if payload.data_source != "gee":
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

    pre_anchor = {"ndvi": 0.72, "ndwi": 0.16, "ndmi": 0.34}
    post_anchor = summary.model_dump()
    rows = series_from_live(
        observations,
        start,
        end,
        pre_anchor,
        post_anchor,
        granularity=payload.granularity,
        seed=run_id,
    )
    return [TimeSeriesPoint.model_validate(row) for row in rows]


def enrich_metrics(metrics: dict[str, Any]) -> dict[str, Any]:
    metrics.update(evaluate_peat_hydrology_profile(metrics))
    metrics.update(multi_hazard_profile(metrics))
    accuracy = evaluate_local_model()
    return {"metrics": metrics, "accuracy": accuracy.model_dump()}
