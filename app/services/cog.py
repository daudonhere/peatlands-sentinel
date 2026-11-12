from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache

import numpy as np
import planetary_computer
import rasterio
from rasterio.enums import Resampling
from rasterio.transform import from_bounds
from rasterio.vrt import WarpedVRT

from app.services.ingestion import search_stac_items
from app.services.raster import (
    calculate_bsi,
    calculate_dnbr,
    calculate_mndwi,
    calculate_nbr,
    calculate_ndvi,
    calculate_ndwi,
    calculate_sar_cross_ratio,
)

_S2_BANDS = ["B02", "B03", "B04", "B08", "B11", "B12", "SCL"]
_S1_BANDS = ["vv", "vh"]
_SCL_INVALID = {0, 1, 3, 8, 9, 10}
_SCALE = 10_000.0
_GRID = 128

_executor = ThreadPoolExecutor(max_workers=8)


def _read_band_sync(href: str, bbox: list[float], size: int) -> np.ndarray:
    transform = from_bounds(*bbox, size, size)
    with rasterio.open(href) as ds:
        with WarpedVRT(
            ds,
            crs="EPSG:4326",
            transform=transform,
            width=size,
            height=size,
            resampling=Resampling.average,
        ) as vrt:
            return vrt.read(1, masked=False).astype(np.float32)


async def _read_band(href: str, bbox: list[float], size: int) -> np.ndarray:
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(_executor, _read_band_sync, href, bbox, size)


async def _fetch_s2_bands(
    item: dict, bbox: list[float], size: int
) -> dict[str, np.ndarray]:
    signed = planetary_computer.sign(item)
    tasks = {
        b: _read_band(signed["assets"][b]["href"], bbox, size)
        for b in _S2_BANDS
        if b in signed["assets"]
    }
    results = await asyncio.gather(*tasks.values(), return_exceptions=True)
    return {k: r for k, r in zip(tasks.keys(), results) if isinstance(r, np.ndarray)}


async def _fetch_s1_bands(
    item: dict, bbox: list[float], size: int
) -> dict[str, np.ndarray]:
    try:
        signed = planetary_computer.sign(item)
        tasks = {
            b: _read_band(signed["assets"][b]["href"], bbox, size)
            for b in _S1_BANDS
            if b in signed["assets"]
        }
        if not tasks:
            return {}
        results = await asyncio.gather(*tasks.values(), return_exceptions=True)
        return {
            k: r for k, r in zip(tasks.keys(), results) if isinstance(r, np.ndarray)
        }
    except Exception:
        return {}


async def fetch_live_dem(bbox: list[float], size: int = 64) -> np.ndarray | None:
    try:
        from app.services.ingestion import search_dem_scenes

        items = await search_dem_scenes(bbox)
        if not items:
            return None
        return await _fetch_dem_band(items[0], bbox, size)
    except Exception:
        return None


async def _fetch_dem_band(item: dict, bbox: list[float], size: int) -> np.ndarray:
    signed = planetary_computer.sign(item)
    return await _read_band(signed["assets"]["data"]["href"], bbox, size)


def _s2_to_indices(bands: dict[str, np.ndarray]) -> dict[str, np.ndarray]:
    ref_shape = None
    for v in bands.values():
        if isinstance(v, np.ndarray) and v.ndim == 2:
            ref_shape = v.shape
            break
    if ref_shape is None:
        ref_shape = (1, 1)
    scl = bands.get("SCL", np.ones(ref_shape, dtype=np.float32) * 4)
    invalid = (
        np.isin(scl, list(_SCL_INVALID))
        if scl.shape == ref_shape
        else np.zeros(ref_shape, dtype=bool)
    )
    mask = ~invalid

    b02 = bands.get("B02", np.zeros_like(scl)) / _SCALE
    b03 = bands.get("B03", np.zeros_like(scl)) / _SCALE
    b04 = bands.get("B04", np.zeros_like(scl)) / _SCALE
    b08 = bands.get("B08", np.zeros_like(scl)) / _SCALE
    b11 = bands.get("B11", np.zeros_like(scl)) / _SCALE
    b12 = bands.get("B12", np.zeros_like(scl)) / _SCALE

    return {
        "ndvi": np.where(mask, calculate_ndvi(b08, b04), np.nan),
        "ndwi": np.where(mask, calculate_ndwi(b03, b08), np.nan),
        "mndwi": np.where(mask, calculate_mndwi(b03, b11), np.nan),
        "nbr": np.where(mask, calculate_nbr(b08, b12), np.nan),
        "bsi": np.where(mask, calculate_bsi(b02, b04, b08, b11), np.nan),
        "valid_mask": mask,
    }


def _s1_to_indices(bands: dict[str, np.ndarray]) -> dict[str, np.ndarray]:
    vv = bands.get("vv", np.full((1, 1), np.nan, dtype=np.float32))
    vh = bands.get("vh", np.full((1, 1), np.nan, dtype=np.float32))
    return {"cross_ratio": calculate_sar_cross_ratio(vh, vv)}


async def fetch_spectral_snapshot(
    bbox: list[float],
    datetime_range: str,
    max_cloud: float = 40.0,
    size: int = _GRID,
) -> dict:
    s2_items, s1_items = await asyncio.gather(
        search_stac_items(
            bbox=bbox,
            datetime_range=datetime_range,
            collections=["sentinel-2-l2a"],
            max_items=1,
            query={"eo:cloud_cover": {"lt": max_cloud}},
        ),
        search_stac_items(
            bbox=bbox,
            datetime_range=datetime_range,
            collections=["sentinel-1-rtc"],
            max_items=1,
        ),
    )
    if not s2_items:
        raise LookupError(
            f"No S2 scene for {bbox} / {datetime_range} < {max_cloud}% cloud."
        )

    s2_bands, s1_result = await asyncio.gather(
        _fetch_s2_bands(s2_items[0], bbox, size),
        _fetch_s1_bands(s1_items[0], bbox, size)
        if s1_items
        else asyncio.sleep(0, result={}),
    )

    s2_idx = _s2_to_indices(s2_bands)
    s1_idx = (
        _s1_to_indices(s1_result)
        if s1_result
        else {"cross_ratio": np.full((size, size), np.nan)}
    )

    valid = s2_idx["valid_mask"]
    pct_valid = float(valid.mean())

    def nanmean(a: np.ndarray) -> float:
        v = a[valid] if valid.any() else a.ravel()
        return round(float(np.nanmean(v)), 4) if not np.all(np.isnan(v)) else 0.0

    return {
        "scene_id": s2_items[0]["id"],
        "s1_scene_id": s1_items[0]["id"] if s1_items else None,
        "datetime": s2_items[0]["properties"].get("datetime", "")[:10],
        "cloud_cover": s2_items[0]["properties"].get("eo:cloud_cover"),
        "valid_pixel_ratio": round(pct_valid, 3),
        "mean_ndvi": nanmean(s2_idx["ndvi"]),
        "mean_ndwi": nanmean(s2_idx["ndwi"]),
        "mean_mndwi": nanmean(s2_idx["mndwi"]),
        "mean_nbr": nanmean(s2_idx["nbr"]),
        "mean_bsi": nanmean(s2_idx["bsi"]),
        "mean_sar_cross_ratio": nanmean(s1_idx["cross_ratio"]),
        "_arrays": {
            "ndvi": s2_idx["ndvi"],
            "bsi": s2_idx["bsi"],
            "nbr": s2_idx["nbr"],
            "cross_ratio": s1_idx["cross_ratio"],
        },
    }


async def fetch_live_pipeline_metrics(
    bbox: list[float],
    pre_date_range: str,
    post_date_range: str,
    max_cloud: float = 40.0,
) -> dict:
    pre, post = await asyncio.gather(
        fetch_spectral_snapshot(bbox, pre_date_range, max_cloud),
        fetch_spectral_snapshot(bbox, post_date_range, max_cloud),
    )

    pre_nbr = pre["_arrays"]["nbr"]
    post_nbr = post["_arrays"]["nbr"]
    dnbr = calculate_dnbr(pre_nbr, post_nbr)
    valid = ~np.isnan(dnbr)

    return {
        "source": "live_cog",
        "pre_scene_id": pre["scene_id"],
        "post_scene_id": post["scene_id"],
        "pre_datetime": pre["datetime"],
        "post_datetime": post["datetime"],
        "valid_pixel_ratio": round(
            float((pre["valid_pixel_ratio"] + post["valid_pixel_ratio"]) / 2), 3
        ),
        "mean_ndvi": post["mean_ndvi"],
        "mean_ndwi": post["mean_ndwi"],
        "mean_mndwi": post["mean_mndwi"],
        "mean_nbr": post["mean_nbr"],
        "mean_bsi": post["mean_bsi"],
        "max_dnbr": round(float(np.nanmax(dnbr[valid])), 4) if valid.any() else 0.0,
        "mean_sar_cross_ratio": post["mean_sar_cross_ratio"],
        "_arrays": {
            "ndvi": post["_arrays"]["ndvi"],
            "dnbr": dnbr,
            "nbr": post["_arrays"]["nbr"],
            "bsi": post["_arrays"]["bsi"],
            "cross_ratio": post["_arrays"]["cross_ratio"],
        },
        "_pre_arrays": {
            "ndvi": pre["_arrays"]["ndvi"],
            "nbr": pre["_arrays"]["nbr"],
            "bsi": pre["_arrays"]["bsi"],
            "cross_ratio": pre["_arrays"]["cross_ratio"],
        },
    }


async def live_ndvi_for_aoi(
    bbox: list[float], datetime_range: str, max_cloud: float = 40.0
) -> dict:
    snap = await fetch_spectral_snapshot(bbox, datetime_range, max_cloud)
    return {k: v for k, v in snap.items() if k != "_arrays"}
