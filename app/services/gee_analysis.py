from __future__ import annotations

import re

import numpy as np

from app.config import get_settings
from app.services.gee import (
    _bbox_geom,
    _require_available,
    _s2_collection,
    _split_interval,
    _worldcover_image,
)

WC_TO_CLASS = {
    10: 0,
    95: 0,
    40: 7,
    50: 6,
    60: 2,
    80: 5,
    90: 1,
}

_BANDS = ["B2", "B3", "B4", "B8", "B11", "B12"]
_SEED_OFFSETS = (42, 7, 13, 21, 33, 55, 77, 99, 111, 131, 151, 173)
_FINE_SCALE = 10
_COARSE_SCALE = 30
_FINE_CLASSES = (1, 2, 6)


def label_epoch_year() -> int:
    match = re.search(r"(\d{4})", get_settings().gee_worldcover_collection)
    return int(match.group(1)) if match else 2021


def label_epoch_range() -> str:
    year = label_epoch_year()
    return f"{year}-01-01/{year}-12-31"


def _cloud_free(image):
    scl = image.select("SCL")
    masked = scl.eq(1).Or(scl.eq(3)).Or(scl.eq(8)).Or(scl.eq(9)).Or(scl.eq(10))
    return image.updateMask(masked.Not())


def _pixel_features(props: dict) -> list[float] | None:
    try:
        bands = [float(props[band]) for band in _BANDS]
    except (KeyError, TypeError, ValueError):
        return None
    if not np.all(np.isfinite(bands)):
        return None
    b2, b3, b4, b8, b11, b12 = bands
    ndvi = (b8 - b4) / (b8 + b4 + 1e-6)
    ndwi = (b3 - b8) / (b3 + b8 + 1e-6)
    nbr = (b8 - b12) / (b8 + b12 + 1e-6)
    bsi = ((b11 + b4) - (b8 + b2)) / ((b11 + b4) + (b8 + b2) + 1e-6)
    return [ndvi, ndwi, nbr, bsi]


def worldcover_training_data(
    bbox: list[float],
    points_per_class: int | None = None,
    max_cloud: float = 40.0,
) -> tuple[list[list[float]], list[int], list[list[float]]]:
    settings = get_settings()
    points = int(points_per_class or settings.gee_samples_per_class)
    draws = max(1, int(settings.gee_sample_draws))

    ee = _require_available()
    geom = _bbox_geom(bbox)
    start, end = _split_interval(label_epoch_range())
    collection = (
        _s2_collection()
        .filterBounds(geom)
        .filterDate(start, end)
        .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", max_cloud))
    )
    if int(collection.size().getInfo() or 0) == 0:
        return [], [], []

    stacked = collection.median().select(_BANDS).addBands(_worldcover_image())
    samples: dict[tuple[float, ...], tuple[int, float, float]] = {}
    for draw in range(draws):
        seed = _SEED_OFFSETS[draw % len(_SEED_OFFSETS)]
        payload = (
            stacked.stratifiedSample(
                numPoints=points,
                classBand="class",
                region=geom,
                scale=_COARSE_SCALE,
                seed=seed,
                tileScale=8,
                geometries=True,
            ).getInfo()
            or {}
        )
        for feature in payload.get("features", []):
            props = feature.get("properties", {})
            label = WC_TO_CLASS.get(int(props.get("class", -1)))
            if label is None:
                continue
            values = _pixel_features(props)
            if values is None:
                continue
            geom_coords = (feature.get("geometry") or {}).get("coordinates")
            if not (
                isinstance(geom_coords, (list, tuple)) and len(geom_coords) >= 2
            ):
                continue
            lon, lat = float(geom_coords[0]), float(geom_coords[1])
            samples[tuple(round(value, 6) for value in values)] = (
                label,
                lon,
                lat,
            )

    features = [list(key) for key in samples]
    labels = [value[0] for value in samples.values()]
    coords = [[value[1], value[2]] for value in samples.values()]
    return features, labels, coords
