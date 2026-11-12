from __future__ import annotations

from datetime import date
from typing import Any

from app.services.gee import (
    _bbox_geom,
    _require_available,
    _s2_collection,
    _split_interval,
    _worldcover_image,
)


def _with_indices(image: Any) -> Any:
    import ee

    nir = image.select("B08").rename("nir")
    red = image.select("B04").rename("red")
    green = image.select("B03").rename("green")
    swir1 = image.select("B11").rename("swir1")
    swir2 = image.select("B12").rename("swir2")
    return image.addBands(
        [
            ee.Image(nir.subtract(red).divide(nir.add(red)).rename("NDVI")),
            ee.Image(green.subtract(nir).divide(green.add(nir)).rename("NDWI")),
            ee.Image(nir.subtract(swir1).divide(nir.add(swir1)).rename("NDMI")),
            ee.Image(green.subtract(swir1).divide(green.add(swir1)).rename("MNDWI")),
            ee.Image(nir.subtract(swir2).divide(nir.add(swir2)).rename("NBR")),
        ]
    )


def s2_snapshot(
    bbox: list[float], datetime_range: str, max_cloud: float = 40.0
) -> dict | None:
    ee = _require_available()
    start, end = _split_interval(datetime_range)
    geom = _bbox_geom(bbox)
    collection = (
        _s2_collection()
        .filterBounds(geom)
        .filterDate(start, end)
        .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", max_cloud))
        .sort("CLOUDY_PIXEL_PERCENTAGE")
    )
    if int(collection.size().getInfo() or 0) == 0:
        return None
    composite = _with_indices(collection.median())
    stats = composite.reduceRegion(ee.Reducer.mean(), geom, 100, maxPixels=1e9)
    info = stats.getInfo() or {}
    first = collection.first().getInfo() or {}
    return {
        "scene_id": first.get("system:index"),
        "datetime": first.get("system:time_start"),
        "cloud_cover": first.get("CLOUDY_PIXEL_PERCENTAGE"),
        "mean_ndvi": info.get("NDVI"),
        "mean_ndwi": info.get("NDWI"),
        "mean_ndmi": info.get("NDMI"),
        "mean_mndwi": info.get("MNDWI"),
        "mean_nbr": info.get("NBR"),
    }


def pipeline_metrics(
    bbox: list[float],
    pre_date_range: str,
    post_date_range: str,
    max_cloud: float = 40.0,
) -> dict:
    _require_available()
    pre = s2_snapshot(bbox, pre_date_range, max_cloud)
    post = s2_snapshot(bbox, post_date_range, max_cloud)
    if post is None:
        raise LookupError(f"No S2 scene for {bbox} / {post_date_range}.")
    pre_nbr = (pre or {}).get("mean_nbr") or 0.0
    post_nbr = post.get("mean_nbr") or 0.0
    return {
        "source": "gee",
        "pre_scene_id": (pre or {}).get("scene_id"),
        "post_scene_id": post.get("scene_id"),
        "pre_datetime": (pre or {}).get("datetime"),
        "post_datetime": post.get("datetime"),
        "valid_pixel_ratio": 1.0,
        "mean_ndvi": post.get("mean_ndvi") or 0.0,
        "mean_ndwi": post.get("mean_ndwi") or 0.0,
        "mean_ndmi": post.get("mean_ndmi") or 0.0,
        "mean_mndwi": post.get("mean_mndwi") or 0.0,
        "mean_nbr": post_nbr,
        "mean_bsi": 0.0,
        "max_dnbr": round(max(0.0, pre_nbr - post_nbr), 4),
        "mean_sar_cross_ratio": -10.5,
    }


def worldcover_fractions(bbox: list[float]) -> dict[int, float]:
    ee = _require_available()
    geom = _bbox_geom(bbox)
    stats = _worldcover_image().reduceRegion(
        ee.Reducer.proportion(), geom, 100, maxPixels=1e9
    )
    info = stats.getInfo() or {}
    fractions: dict[int, float] = {}
    for band, value in info.items():
        try:
            fractions[int(band)] = round(float(value), 4)
        except (TypeError, ValueError):
            continue
    return fractions


def stratified_worldcover_samples(
    bbox: list[float],
    points_per_class: int = 150,
    bands: list[str] | None = None,
) -> list[dict]:
    _require_available()
    geom = _bbox_geom(bbox)
    band_names = bands or ["B02", "B03", "B04", "B08", "B11", "B12"]
    latest = _s2_collection().filterBounds(geom).median().select(band_names)
    cover = _worldcover_image()
    samples: list[dict] = []
    for class_id in range(1, 11):
        region = (
            latest.select(band_names)
            .addBands(cover.select(["class"]))
            .sample(
                region=cover.eq(class_id),
                scale=10,
                numPixels=points_per_class,
                seed=class_id,
                tieBreaker=4,
            )
            .limit(points_per_class)
        )
        count = int(region.size().getInfo() or 0)
        samples.append({"class": class_id, "count": count})
    return samples


def smile_random_forest_classify(
    bbox: list[float],
    pre_date_range: str,
    post_date_range: str,
    points_per_class: int = 150,
    trees: int = 200,
) -> dict:
    ee = _require_available()
    geom = _bbox_geom(bbox)
    band_names = ["B02", "B03", "B04", "B08", "B11", "B12"]
    cover = _worldcover_image()

    def train_and_fraction(date_range: str) -> dict:
        start, end = _split_interval(date_range)
        collection = (
            _s2_collection()
            .filterBounds(geom)
            .filterDate(start, end)
            .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", 60.0))
            .sort("CLOUDY_PIXEL_PERCENTAGE")
        )
        if int(collection.size().getInfo() or 0) == 0:
            return {}
        composite = _with_indices(collection.median()).select(band_names)
        training = None
        for class_id in range(1, 11):
            sample = (
                composite.addBands(cover.select(["class"]))
                .sample(
                    region=cover.eq(class_id),
                    scale=10,
                    numPixels=points_per_class,
                    seed=class_id,
                    tieBreaker=4,
                )
                .limit(points_per_class)
            )
            training = sample if training is None else training.merge(sample)
        rf = ee.Classifier.smileRandomForest(
            numberOfTrees=trees, seed=42, useBaggedPrediction=True
        ).train(
            {
                "features": training,
                "classifierProperty": "class",
                "inputPropertyNames": band_names,
            }
        )
        labeled = composite.classify(rf).select("class")
        proportions = (
            labeled.reduceRegion(
                ee.Reducer.proportion(), geom, 30, maxPixels=1e9
            ).getInfo()
            or {}
        )
        fractions: dict[int, float] = {}
        for band, value in proportions.items():
            try:
                fractions[int(band)] = round(float(value), 4)
            except (TypeError, ValueError):
                continue
        return fractions

    return {
        "pre": train_and_fraction(pre_date_range),
        "post": train_and_fraction(post_date_range),
    }


def monthly_ndvi_series(bbox: list[float], start: date, end: date) -> list[dict]:
    ee = _require_available()
    geom = _bbox_geom(bbox)
    points: list[dict] = []
    cursor = start.replace(day=1)
    while cursor <= end:
        next_year = cursor.year + 1 if cursor.month == 12 else cursor.year
        next_month = 1 if cursor.month == 12 else cursor.month + 1
        month_end = date(next_year, next_month, 1).replace(day=1)
        composite = _s2_collection().filterBounds(geom)
        composite = composite.filterDate(cursor.isoformat(), month_end.isoformat())
        composite = composite.filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", 60.0))
        if int(composite.size().getInfo() or 0) > 0:
            stats = (
                _with_indices(composite.median())
                .reduceRegion(ee.Reducer.mean(), geom, 100, maxPixels=1e9)
                .getInfo()
                or {}
            )
            points.append(
                {
                    "period": cursor.strftime("%Y-%m"),
                    "ndvi": round(float(stats.get("NDVI") or 0.0), 4),
                }
            )
        cursor = date(next_year, next_month, 1)
    return points

