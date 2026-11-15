from __future__ import annotations

from app.services.gee import (
    _bbox_geom,
    _require_available,
    _s2_collection,
    _split_interval,
    _worldcover_image,
)

WC_TO_CLASS = {
    10: 0,
    20: 0,
    30: 2,
    40: 7,
    50: 6,
    60: 2,
    80: 5,
    90: 1,
    95: 0,
}


def worldcover_training_data(
    bbox: list[float],
    date_range: str,
    points_per_class: int = 50,
    max_cloud: float = 40.0,
) -> tuple[list[list[float]], list[int]]:
    """Sample ESA WorldCover labeled Sentinel-2 pixels for RF training."""
    ee = _require_available()
    geom = _bbox_geom(bbox)
    start, end = _split_interval(date_range)
    collection = (
        _s2_collection()
        .filterBounds(geom)
        .filterDate(start, end)
        .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", max_cloud))
        .sort("CLOUDY_PIXEL_PERCENTAGE")
    )
    if int(collection.size().getInfo() or 0) == 0:
        return [], []
    composite = collection.median()
    bands = ["B2", "B3", "B4", "B8", "B11", "B12"]
    cover = _worldcover_image()
    features: list[list[float]] = []
    labels: list[int] = []
    for wc_class, our_class in WC_TO_CLASS.items():
        try:
            sample = (
                composite.select(bands)
                .addBands(cover.select(["class"]))
                .updateMask(cover.eq(wc_class))
                .sample(
                    region=geom,
                    scale=10,
                    numPixels=points_per_class,
                    seed=wc_class,
                )
                .limit(points_per_class)
            )
            for feat in (sample.getInfo() or {}).get("features", []):
                props = feat.get("properties", {})
                b = [float(props.get(band, 0.0)) for band in bands]
                ndvi = (b[3] - b[2]) / (b[3] + b[2] + 1e-6)
                ndwi = (b[1] - b[3]) / (b[1] + b[3] + 1e-6)
                nbr = (b[3] - b[5]) / (b[3] + b[5] + 1e-6)
                bsi = ((b[4] + b[2]) - (b[3] + b[0])) / (
                    (b[4] + b[2]) + (b[3] + b[0]) + 1e-6
                )
                features.append([ndvi, ndwi, nbr, bsi])
                labels.append(our_class)
        except Exception:
            continue
    return features, labels
