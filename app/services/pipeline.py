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
from app.services.classifier import (
    build_spectral_summary_from_live,
    classify_live_arrays,
    simulate_aoi_transitions,
    simulate_arrays,
)
from app.services.hazard import multi_hazard_profile
from app.services.hydrology import evaluate_peat_hydrology_profile
from app.services.model_metrics import (
    class_scatter_from_arrays,
    evaluate_local_model,
    simulate_class_scatter,
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


async def resolve_spectral(
    bbox: list[float],
    payload: AnalysisPipelineRequest,
    run_id: str,
    area_ha: float,
) -> tuple[SpectralSummary, list, dict, dict, list[ClassScatterPoint]]:
    try:
        result = await asyncio.wait_for(
            resolve_pipeline_metrics(
                payload.data_source,
                bbox,
                payload.pre_date_range,
                payload.post_date_range,
                payload.max_cloud_cover,
            ),
            timeout=12.0,
        )
        summary = build_spectral_summary_from_live(result.metrics)
        transitions = classify_live_arrays(
            {"_arrays": result.pre_arrays or result.post_arrays or {}},
            {"_arrays": result.post_arrays or {}},
            area_ha,
        )
        arrays = _merge_arrays(result.pre_arrays, result.post_arrays)
        scatter = (
            class_scatter_from_arrays(result.pre_arrays or {}, result.post_arrays or {})
            if result.pre_arrays and result.post_arrays
            else simulate_class_scatter(payload.target, run_id)
        )
        extra = {"source": result.source, **result.scene_meta}
        return summary, transitions, arrays, extra, scatter
    except Exception:
        summary, transitions = simulate_aoi_transitions(payload.target, run_id, area_ha)
        arrays = simulate_arrays(payload.target, run_id)
        return (
            summary,
            transitions,
            arrays,
            {"source": "simulation"},
            simulate_class_scatter(payload.target, run_id),
        )


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
