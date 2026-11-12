from typing import Any
import numpy as np


def extract_bbox_from_geometry(geometry: dict[str, Any]) -> list[float]:
    """Computes [min_lon, min_lat, max_lon, max_lat] from GeoJSON Polygon or MultiPolygon."""
    coords = geometry.get("coordinates", [])
    geom_type = geometry.get("type", "Polygon")

    points: list[list[float]] = []
    if geom_type == "Polygon":
        for ring in coords:
            points.extend(ring)
    elif geom_type == "MultiPolygon":
        for polygon in coords:
            for ring in polygon:
                points.extend(ring)

    if not points:
        raise ValueError("Cannot extract coordinates from empty geometry.")

    lons = [p[0] for p in points]
    lats = [p[1] for p in points]
    return [
        round(float(min(lons)), 6),
        round(float(min(lats)), 6),
        round(float(max(lons)), 6),
        round(float(max(lats)), 6),
    ]


def calculate_polygon_area_hectares(bbox: list[float]) -> float:
    """Estimates geodesic polygon area in hectares from bounding box."""
    min_lon, min_lat, max_lon, max_lat = bbox
    lat_mid = np.radians((min_lat + max_lat) / 2.0)
    meters_per_deg_lat = 111320.0
    meters_per_deg_lon = 111320.0 * np.cos(lat_mid)

    width_m = abs(max_lon - min_lon) * meters_per_deg_lon
    height_m = abs(max_lat - min_lat) * meters_per_deg_lat
    area_sq_m = width_m * height_m
    return round(float(area_sq_m / 10000.0), 2)


def apply_s2_cloud_mask(
    bands: dict[str, np.ndarray], scl_band: np.ndarray
) -> dict[str, np.ndarray]:
    """Masks clouds and cloud shadows based on Sentinel-2 Scene Classification Layer (SCL).

    SCL classes masked: 3 (cloud shadow), 8 (medium prob), 9 (high prob), 10 (cirrus).
    """
    cloud_mask = np.isin(scl_band, [3, 8, 9, 10])
    masked_bands: dict[str, np.ndarray] = {}
    for name, data in bands.items():
        masked = np.where(cloud_mask, np.nan, data.astype(np.float32))
        masked_bands[name] = masked
    return masked_bands


def compute_normalized_difference(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """Safely calculates (a - b) / (a + b) with nan-handling."""
    denom = a + b
    diff = a - b
    with np.errstate(divide="ignore", invalid="ignore"):
        result = np.where(denom == 0.0, 0.0, diff / denom)
    return np.clip(result, -1.0, 1.0)


def calculate_ndvi(nir: np.ndarray, red: np.ndarray) -> np.ndarray:
    return compute_normalized_difference(nir, red)


def calculate_ndwi(green: np.ndarray, nir: np.ndarray) -> np.ndarray:
    return compute_normalized_difference(green, nir)


def calculate_mndwi(green: np.ndarray, swir1: np.ndarray) -> np.ndarray:
    return compute_normalized_difference(green, swir1)


def calculate_nbr(nir: np.ndarray, swir2: np.ndarray) -> np.ndarray:
    return compute_normalized_difference(nir, swir2)


def calculate_dnbr(pre_nbr: np.ndarray, post_nbr: np.ndarray) -> np.ndarray:
    return pre_nbr - post_nbr


def calculate_bsi(
    blue: np.ndarray, red: np.ndarray, nir: np.ndarray, swir1: np.ndarray
) -> np.ndarray:
    """Bare Soil Index (BSI) identifying mineral extraction and clearings."""
    num = (swir1 + red) - (nir + blue)
    denom = (swir1 + red) + (nir + blue)
    with np.errstate(divide="ignore", invalid="ignore"):
        bsi = np.where(denom == 0.0, 0.0, num / denom)
    return np.clip(bsi, -1.0, 1.0)


def calculate_sar_cross_ratio(vh_db: np.ndarray, vv_db: np.ndarray) -> np.ndarray:
    return vh_db - vv_db
