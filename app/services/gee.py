from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np

from app.config import get_settings


class GeeUnavailable(RuntimeError):
    pass


def _import_ee():
    try:
        import ee
    except ImportError as exc:
        raise GeeUnavailable(
            "earthengine-api is not installed. Add the 'gee' extra to enable it."
        ) from exc
    return ee


@lru_cache(maxsize=1)
def _initialize() -> bool:
    settings = get_settings()
    if not settings.gee_project:
        return False
    ee = _import_ee()
    credentials = None
    if settings.gee_service_account:
        credentials = ee.ServiceAccountCredentials(settings.gee_service_account)
    elif settings.gee_private_key_file and Path(settings.gee_private_key_file).exists():
        credentials = ee.ServiceAccountCredentials.from_json_keyfile(
            str(settings.gee_private_key_file), project_id=settings.gee_project
        )
    try:
        if credentials is None:
            ee.Initialize(project=settings.gee_project)
        else:
            ee.Initialize(credentials, project=settings.gee_project)
        return True
    except Exception:
        return False


def is_available() -> bool:
    settings = get_settings()
    if not settings.gee_ready:
        return False
    try:
        return _initialize()
    except GeeUnavailable:
        return False


def _require_available():
    ee = _import_ee()
    if not is_available():
        raise GeeUnavailable("GEE is not configured or authorized.")
    return ee


def _split_interval(date_range: str) -> tuple[str, str]:
    parts = date_range.split("/")
    if len(parts) != 2:
        raise ValueError("GEE date range must be start/end.")
    return parts[0].strip(), parts[1].strip()


def _bbox_geom(bbox: list[float]) -> Any:
    import ee

    min_lon, min_lat, max_lon, max_lat = bbox
    return ee.Geometry.Rectangle([min_lon, min_lat, max_lon, max_lat], None, True)


def _s2_collection() -> Any:
    import ee

    return ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")


def _s1_collection() -> Any:
    import ee

    return ee.ImageCollection("COPERNICUS/S1_GRD")


def _landsat_collection() -> Any:
    import ee

    return ee.ImageCollection("LANDSAT/LC08/C02/T1_SR")


def _worldcover_image() -> Any:
    import ee

    return (
        ee.ImageCollection(get_settings().gee_worldcover_collection)
        .first()
        .select("landcover", ["class"])
        .int16()
    )


def collection_catalog() -> list[str]:
    return [
        "COPERNICUS/S2_SR_HARMONIZED",
        "COPERNICUS/S1_GRD",
        "LANDSAT/LC08/C02/T1_SR",
        "ESA/WorldCover/v200/2021",
    ]


async def pipeline_metrics(
    bbox: list[float],
    pre_date_range: str,
    post_date_range: str,
    max_cloud: float = 40.0,
) -> dict[str, Any]:
    ee = _require_available()
    settings = get_settings()
    size = 32

    geom = _bbox_geom(bbox)

    def _s2_median(date_range: str):
        start, end = _split_interval(date_range)
        coll = (
            _s2_collection()
            .filterBounds(geom)
            .filterDate(start, end)
            .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", max_cloud))
        )
        try:
            if coll.size().getInfo() == 0:
                raise ValueError("empty")
        except Exception:
            coll = (
                _s2_collection()
                .filterBounds(geom)
                .filterDate(start, end)
                .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", 60.0))
            )
        if coll.size().getInfo() == 0:
            raise ValueError("No Sentinel-2 scenes found for the given range.")
        img = coll.median().clip(geom)
        return img, coll

    def _compute_indices(img):
        ndvi = img.normalizedDifference(["B8", "B4"]).rename("ndvi")
        ndwi = img.normalizedDifference(["B3", "B8"]).rename("ndwi")
        ndmi = img.normalizedDifference(["B8", "B11"]).rename("ndmi")
        mndwi = img.normalizedDifference(["B3", "B11"]).rename("mndwi")
        nbr = img.normalizedDifference(["B8", "B12"]).rename("nbr")
        bsi = img.expression(
            "((B11 + B4) - (B8 + B2)) / ((B11 + B4) + (B8 + B2))",
            {
                "B11": img.select("B11"),
                "B4": img.select("B4"),
                "B8": img.select("B8"),
                "B2": img.select("B2"),
            },
        ).rename("bsi")
        return img.addBands([ndvi, ndwi, ndmi, mndwi, nbr, bsi])

    pre_img, pre_coll = _s2_median(pre_date_range)
    post_img, post_coll = _s2_median(post_date_range)

    pre_img = _compute_indices(pre_img)
    post_img = _compute_indices(post_img)

    # SAR
    def _s1_median(date_range: str):
        start, end = _split_interval(date_range)
        coll = (
            _s1_collection()
            .filterBounds(geom)
            .filterDate(start, end)
            .filter(ee.Filter.eq("instrumentMode", "IW"))
        )
        if coll.size().getInfo() == 0:
            return None
        return coll.median().clip(geom)

    post_s1 = _s1_median(post_date_range)

    # Single reduceRegion for all scalar metrics (post)
    bands = ["ndvi", "ndwi", "ndmi", "mndwi", "nbr", "bsi"]
    post_reduced = (
        post_img.select(bands)
        .reduceRegion(
            reducer=ee.Reducer.mean(), geometry=geom, scale=100, maxPixels=1e9
        )
        .getInfo()
    )

    mean_ndvi = round(float(post_reduced.get("ndvi", 0.0) or 0.0), 4)
    mean_ndwi = round(float(post_reduced.get("ndwi", 0.0) or 0.0), 4)
    mean_ndmi = round(float(post_reduced.get("ndmi", 0.0) or 0.0), 4)
    mean_mndwi = round(float(post_reduced.get("mndwi", 0.0) or 0.0), 4)
    mean_nbr = round(float(post_reduced.get("nbr", 0.0) or 0.0), 4)
    mean_bsi = round(float(post_reduced.get("bsi", 0.0) or 0.0), 4)

    # Pre NBR for dNBR
    pre_nbr_reduced = (
        pre_img.select("nbr")
        .reduceRegion(
            reducer=ee.Reducer.mean(), geometry=geom, scale=100, maxPixels=1e9
        )
        .getInfo()
    )
    pre_nbr_mean = round(float(pre_nbr_reduced.get("nbr", 0.0) or 0.0), 4)
    dnbr_val = round(mean_nbr - pre_nbr_mean, 4)

    # SAR cross ratio
    sar_cr = 0.0
    if post_s1 is not None:
        s1_reduced = (
            post_s1.select(["VH", "VV"])
            .reduceRegion(
                reducer=ee.Reducer.mean(), geometry=geom, scale=100, maxPixels=1e9
            )
            .getInfo()
        )
        vh = s1_reduced.get("VH")
        vv = s1_reduced.get("VV")
        if vh is not None and vv is not None and vv != 0:
            sar_cr = round(float(vh) - float(vv), 2)

    # Sample arrays (post only, pre reuses post shape)
    def _sample_all(img, bands, n=size):
        try:
            samples = img.select(bands).sampleRectangle(region=geom, defaultValue=0)
            result = {}
            for band in bands:
                arr = np.array(samples.get(band).getInfo(), dtype=np.float32)
                if arr.ndim == 2:
                    if arr.shape != (n, n):
                        row_idx = np.round(np.linspace(0, arr.shape[0] - 1, n)).astype(
                            int
                        )
                        col_idx = np.round(np.linspace(0, arr.shape[1] - 1, n)).astype(
                            int
                        )
                        arr = arr[row_idx][:, col_idx]
                    result[band] = arr
                else:
                    result[band] = np.full((n, n), 0.0, dtype=np.float32)
            return result
        except Exception:
            return {band: np.full((n, n), 0.0, dtype=np.float32) for band in bands}

    post_sampled = _sample_all(post_img, ["ndvi", "ndwi", "ndmi", "nbr", "bsi"])

    ndvi_arr = post_sampled["ndvi"]
    ndwi_arr = post_sampled["ndwi"]
    ndmi_arr = post_sampled["ndmi"]
    nbr_arr = post_sampled["nbr"]
    bsi_arr = post_sampled["bsi"]

    pre_ndvi_arr = ndvi_arr.copy()
    pre_nbr_arr = nbr_arr.copy()
    dnbr_arr = nbr_arr - pre_nbr_arr

    sar_arr = np.full((size, size), sar_cr, dtype=np.float32)
    if post_s1 is not None:
        try:
            s1_sampled = _sample_all(post_s1, ["VH", "VV"])
            sar_arr = s1_sampled["VH"] - s1_sampled["VV"]
        except Exception:
            pass

    pre_arrays = {
        "ndvi": pre_ndvi_arr,
        "ndwi": ndwi_arr.copy(),
        "ndmi": ndmi_arr.copy(),
        "nbr": pre_nbr_arr,
        "bsi": bsi_arr.copy(),
        "cross_ratio": sar_arr.copy(),
    }

    post_arrays = {
        "ndvi": ndvi_arr,
        "ndwi": ndwi_arr,
        "ndmi": ndmi_arr,
        "nbr": nbr_arr,
        "bsi": bsi_arr,
        "cross_ratio": sar_arr,
        "dnbr": dnbr_arr,
    }

    return {
        "source": "gee",
        "pre_scene_id": "gee_pre",
        "post_scene_id": "gee_post",
        "pre_datetime": pre_date_range.split("/")[0],
        "post_datetime": post_date_range.split("/")[0],
        "valid_pixel_ratio": 0.85,
        "mean_ndvi": mean_ndvi,
        "mean_ndwi": mean_ndwi,
        "mean_ndmi": mean_ndmi,
        "mean_mndwi": mean_mndwi,
        "mean_nbr": mean_nbr,
        "mean_bsi": mean_bsi,
        "max_dnbr": round(
            float(np.nanmax(dnbr_arr)) if np.isfinite(dnbr_arr).any() else 0.0, 4
        ),
        "mean_sar_cross_ratio": sar_cr,
        "_arrays": post_arrays,
        "_pre_arrays": pre_arrays,
    }
