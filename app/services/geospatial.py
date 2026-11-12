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
    "calculate_ndvi",
    "calculate_ndwi",
    "calculate_mndwi",
    "calculate_nbr",
    "calculate_dnbr",
    "calculate_bsi",
    "calculate_sar_cross_ratio",
    "calculate_slope_degrees",
    "compute_dem_topography_summary",
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


def calculate_polygon_area_hectares(geometry_or_bbox: Any) -> float:
    if isinstance(geometry_or_bbox, (list, tuple)):
        bbox = list(geometry_or_bbox)
        min_lon, min_lat, max_lon, max_lat = bbox
        lat_mid = np.radians((min_lat + max_lat) / 2.0)
        width_m = abs(max_lon - min_lon) * 111320.0 * np.cos(lat_mid)
        height_m = abs(max_lat - min_lat) * 111320.0
        return round(float((width_m * height_m) / 10000.0), 2)

    geom_type = geometry_or_bbox.get("type", "Polygon")
    polygons: list[Any] = []
    if geom_type == "Polygon":
        polygons = [geometry_or_bbox.get("coordinates", [])]
    elif geom_type == "MultiPolygon":
        polygons = geometry_or_bbox.get("coordinates", [])

    total_deg2 = 0.0
    all_lats: list[float] = []
    for poly in polygons:
        if not poly or not poly[0]:
            continue
        ring = poly[0]
        xs = [float(p[0]) for p in ring]
        ys = [float(p[1]) for p in ring]
        all_lats.extend(ys)
        s = 0.0
        n = len(xs)
        for i in range(n):
            j = (i + 1) % n
            s += xs[i] * ys[j] - xs[j] * ys[i]
        total_deg2 += abs(s) / 2.0

    if total_deg2 == 0.0 or not all_lats:
        return 0.0
    lat_mid = np.radians(float(np.mean(all_lats)))
    meters_per_deg = 111320.0 * np.cos(lat_mid)
    area_m2 = total_deg2 * (meters_per_deg**2)
    return round(float(area_m2 / 10000.0), 2)


def calculate_slope_degrees(
    elevation_grid: np.ndarray, cell_size_meters: float = 30.0
) -> np.ndarray:
    dy, dx = np.gradient(elevation_grid, cell_size_meters)
    slope_rad = np.arctan(np.sqrt(dx**2 + dy**2))
    return np.degrees(slope_rad)


def compute_dem_topography_summary(
    bbox: list[float],
    base_elevation_m: float = 12.0,
    elev_grid: np.ndarray | None = None,
) -> dict[str, float]:
    if elev_grid is None or elev_grid.size == 0 or np.all(np.isnan(elev_grid)):
        grid_size = 20
        y, x = np.mgrid[0:grid_size, 0:grid_size]
        cy, cx = grid_size / 2.0, grid_size / 2.0
        dome_factor = np.clip(
            1.0 - ((x - cx) ** 2 + (y - cy) ** 2) / (cx**2 + cy**2), 0, 1
        )
        elev_grid = base_elevation_m + dome_factor * 8.5

    finite = np.where(np.isfinite(elev_grid), elev_grid, float(np.nanmean(elev_grid)))
    min_lon, min_lat, max_lon, max_lat = bbox
    lat_mid = np.radians((min_lat + max_lat) / 2.0)
    rows, cols = finite.shape
    cell_lat_m = abs(max_lat - min_lat) * 111320.0 / max(rows - 1, 1)
    cell_lon_m = abs(max_lon - min_lon) * 111320.0 * np.cos(lat_mid) / max(cols - 1, 1)
    cell_size_m = float((cell_lat_m + cell_lon_m) / 2.0) or 30.0
    slopes = calculate_slope_degrees(finite, cell_size_meters=cell_size_m)

    return {
        "mean_elevation_m": round(float(np.mean(finite)), 1),
        "max_elevation_m": round(float(np.max(finite)), 1),
        "min_elevation_m": round(float(np.min(finite)), 1),
        "elevation_relief_m": round(float(np.max(finite) - np.min(finite)), 1),
        "mean_slope_deg": round(float(np.mean(slopes)), 2),
        "max_slope_deg": round(float(np.max(slopes)), 2),
    }
