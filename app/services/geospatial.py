from typing import Any
import numpy as np

from app.services.raster import (
    calculate_ndvi,
    calculate_ndwi,
    calculate_mndwi,
    calculate_nbr,
    calculate_dnbr,
    calculate_bsi,
    calculate_sar_cross_ratio,
)

__all__ = [
    "extract_bbox_from_geometry",
    "calculate_polygon_area_hectares",
    "apply_s2_cloud_mask",
    "calculate_ndvi",
    "calculate_ndwi",
    "calculate_mndwi",
    "calculate_nbr",
    "calculate_dnbr",
    "calculate_bsi",
    "calculate_sar_cross_ratio",
]


def extract_bbox_from_geometry(geometry: dict[str, Any]) -> list[float]:
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
    min_lon, min_lat, max_lon, max_lat = bbox
    lat_mid = np.radians((min_lat + max_lat) / 2.0)
    meters_per_deg_lat = 111320.0
    meters_per_deg_lon = 111320.0 * np.cos(lat_mid)

    width_m = abs(max_lon - min_lon) * meters_per_deg_lon
    height_m = abs(max_lat - min_lat) * meters_per_deg_lat
    return round(float((width_m * height_m) / 10000.0), 2)


def apply_s2_cloud_mask(
    bands: dict[str, np.ndarray], scl_band: np.ndarray
) -> dict[str, np.ndarray]:
    cloud_mask = np.isin(scl_band, [3, 8, 9, 10])
    masked_bands: dict[str, np.ndarray] = {}
    for name, data in bands.items():
        masked_bands[name] = np.where(cloud_mask, np.nan, data.astype(np.float32))
    return masked_bands
