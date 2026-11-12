from __future__ import annotations

import asyncio
import numpy as np

from app.services.cog import _fetch_s2_bands, _s2_to_indices
from app.services.ingestion import search_stac_items
from app.services.temporal import seasonal_window

_OBSERVATION_FIELDS = ("mean_ndvi", "mean_ndwi", "mean_ndmi", "mean_nbr", "mean_bsi")


def _summarize_indices(indices: dict) -> dict:
    valid = indices["valid_mask"]
    summary: dict = {}
    for name in _OBSERVATION_FIELDS:
        values = indices[name[5:]]
        values = values[valid] if valid.any() else values.ravel()
        if np.all(np.isnan(values)):
            continue
        summary[name] = round(float(np.nanmean(values)), 4)
    return summary


def _cloud_rank(item: dict) -> float:
    value = item.get("properties", {}).get("eo:cloud_cover")
    try:
        return float(value)
    except (TypeError, ValueError):
        return 100.0


async def _snapshot_observation(
    item: dict, bbox: list[float], size: int = 32
) -> dict | None:
    try:
        bands = await _fetch_s2_bands(item, bbox, size)
        if "B08" not in bands or "B04" not in bands:
            return None
        observation = {
            "scene_id": item.get("id"),
            "datetime": str(item.get("properties", {}).get("datetime", ""))[:10],
            "cloud_cover": _cloud_rank(item),
        }
        observation.update(_summarize_indices(_s2_to_indices(bands)))
        return observation
    except Exception:
        return None


async def fetch_scene_observations(
    bbox: list[float],
    datetime_range: str,
    max_cloud: float = 40.0,
    max_items: int = 8,
) -> list[dict]:
    items = await search_stac_items(
        bbox=bbox,
        datetime_range=datetime_range,
        collections=["sentinel-2-l2a"],
        max_items=max_items,
        query={"eo:cloud_cover": {"lt": max_cloud}},
    )
    if not items:
        return []

    results = await asyncio.gather(
        *[_snapshot_observation(item, bbox) for item in items]
    )
    observations = [obs for obs in results if obs]
    observations.sort(key=lambda obs: obs["datetime"])
    return observations


async def fetch_seasonal_composite(
    bbox: list[float],
    year: int,
    composite_season: str,
    max_cloud: float = 60.0,
) -> dict | None:
    start_iso, end_iso = seasonal_window(year, composite_season)
    items = await search_stac_items(
        bbox=bbox,
        datetime_range=f"{start_iso}/{end_iso}",
        collections=["sentinel-2-l2a"],
        max_items=10,
        query={"eo:cloud_cover": {"lt": max_cloud}},
    )
    if not items:
        return None

    clearest = min(items, key=_cloud_rank)
    return await _snapshot_observation(clearest, bbox)
