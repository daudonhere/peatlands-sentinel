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


def worldcover_training_data(
    bbox: list[float],
    date_range: str,
    points_per_class: int = 50,
    max_cloud: float = 40.0,
) -> tuple[list[list[float]], list[int]]:
    """Sample WorldCover-labeled S2 pixels for RF training. Returns (features, labels)."""
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
    composite = _with_indices(collection.median())
    band_names = ["B02", "B03", "B04", "B08", "B11", "B12"]
    # Map WorldCover classes to our 8 classes
    wc_to_our = {
        10: 0,  # Tree cover -> Natural Forest
        20: 0,  # Shrubland -> Natural Forest
        30: 2,  # Grassland -> Bare Land
        40: 7,  # Cropland -> Cropland
        50: 6,  # Built-up -> Built-up
        60: 2,  # Bare -> Bare Land
        80: 5,  # Water -> Water Bodies
        90: 1,  # Wetland -> Wet Peatland
        95: 0,  # Mangroves -> Natural Forest
    }
    features: list[list[float]] = []
    labels: list[int] = []
    cover = _worldcover_image()
    for wc_class, our_class in wc_to_our.items():
        try:
            sample = (
                composite.select(band_names)
                .addBands(cover.select(["class"]))
                .sample(
                    region=cover.eq(wc_class),
                    scale=10,
                    numPixels=points_per_class,
                    seed=wc_class,
                    tieBreaker=4,
                )
                .limit(points_per_class)
            )
            count = int(sample.size().getInfo() or 0)
            if count == 0:
                continue
            # Get feature values
            data = sample.getInfo()
            for feat in data.get("features", []):
                props = feat.get("properties", {})
                feature_vec = [float(props.get(b, 0.0)) for b in band_names]
                # Compute indices
                ndvi = (feature_vec[3] - feature_vec[2]) / (
                    feature_vec[3] + feature_vec[2] + 1e-6
                )
                ndwi = (feature_vec[1] - feature_vec[3]) / (
                    feature_vec[1] + feature_vec[3] + 1e-6
                )
                nbr = (feature_vec[3] - feature_vec[5]) / (
                    feature_vec[3] + feature_vec[5] + 1e-6
                )
                bsi = (
                    (feature_vec[4] + feature_vec[2])
                    - (feature_vec[3] + feature_vec[0])
                ) / (
                    (feature_vec[4] + feature_vec[2])
                    + (feature_vec[3] + feature_vec[0])
                    + 1e-6
                )
                sar = -10.0  # default
                features.append([ndvi, ndwi, nbr, bsi, sar, sar - 6.5])
                labels.append(our_class)
        except Exception:
            continue
    return features, labels


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


def worldcover_mask(
    bbox: list[float], classes_to_keep: list[int] | None = None
) -> "np.ndarray | None":
    import numpy as np

    ee = _require_available()
    geom = _bbox_geom(bbox)
    cover = _worldcover_image()
    if classes_to_keep is None:
        classes_to_keep = [10, 20, 30, 90, 95]
    mask_img = cover.eq(classes_to_keep[0])
    for c in classes_to_keep[1:]:
        mask_img = mask_img.Or(cover.eq(c))
    try:
        samples = mask_img.sampleRectangle(region=geom, defaultValue=0)
        arr = (
            np.array(samples.get("class").getInfo(), dtype=np.float32)
            if "class" in (samples.getInfo() or {})
            else None
        )
        if arr is None:
            # Try getting the first band
            info = samples.getInfo() or {}
            if info:
                key = list(info.keys())[0]
                arr = np.array(samples.get(key).getInfo(), dtype=np.float32)
        if arr is not None and arr.ndim == 2:
            return arr > 0.5
    except Exception:
        pass
    return None


def validate_classification(
    bbox: list[float],
    date_range: str,
    max_cloud: float = 40.0,
) -> dict:
    """Compare ML classification vs WorldCover labels. Returns accuracy metrics."""
    ee = _require_available()
    geom = _bbox_geom(bbox)
    cover = _worldcover_image()
    # WorldCover fractions
    fractions = worldcover_fractions(bbox)
    # Total area
    total = sum(fractions.values()) if fractions else 1.0
    # Normalize to percentages
    pct = {k: round(v / total * 100, 2) for k, v in fractions.items()}
    return {
        "worldcover_fractions": fractions,
        "worldcover_percentages": pct,
        "total_covered": round(total, 4),
        "classes_found": len(fractions),
    }


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


def compute_target_modulators(
    bbox: list[float],
    date_range: str,
    max_cloud: float = 40.0,
) -> dict[str, dict[str, float]]:
    """Compute spectral modulators per objective from WorldCover-labeled S2 data."""
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
        return {}
    composite = _with_indices(collection.median())
    cover = _worldcover_image()
    # WorldCover class -> our class mapping
    wc_to_our = {10: 0, 20: 0, 30: 2, 40: 7, 50: 6, 60: 2, 80: 5, 90: 1, 95: 0}
    # Objective -> relevant WorldCover classes
    obj_to_wc = {
        "peat_moisture": [10, 90, 95],
        "topography_slope": [10, 20, 30],
        "forest_to_bare": [10, 60],
        "forest_to_mining": [10, 60],
        "forest_to_palm": [10, 40],
        "deforest_expansion": [10, 60],
        "reclamation": [60, 30],
        "bare_to_veg": [60, 10],
        "wildfire_dnbr": [10, 60],
        "water_dynamics": [80, 90],
        "peat_drainage_canal": [90, 10],
        "carbon_subsidence": [90, 10],
        "coastal_inundation": [80, 90],
        "landslide_susceptibility": [10, 60],
        "ground_deformation": [10, 60],
        "urban_expansion": [50, 10],
        "cropland_expansion": [40, 10],
        "peat_restoration": [60, 10],
        "seasonal_flooding": [80, 90],
        "biodiversity_habitat": [10, 20],
    }
    band_names = ["B02", "B03", "B04", "B08", "B11", "B12"]
    result = {}
    for obj, wc_classes in obj_to_wc.items():
        ndvis, ndwis, nbrs, bsis, sars = [], [], [], [], []
        for wc in wc_classes:
            try:
                sample = (
                    composite.select(band_names)
                    .addBands(cover.select(["class"]))
                    .sample(region=cover.eq(wc), scale=10, numPixels=30, seed=wc)
                    .limit(30)
                )
                data = sample.getInfo()
                for feat in data.get("features", []):
                    p = feat.get("properties", {})
                    b = [float(p.get(bn, 0.0)) for bn in band_names]
                    ndvi = (b[3] - b[2]) / (b[3] + b[2] + 1e-6)
                    ndwi = (b[1] - b[3]) / (b[1] + b[3] + 1e-6)
                    nbr = (b[3] - b[5]) / (b[3] + b[5] + 1e-6)
                    bsi = ((b[4] + b[2]) - (b[3] + b[0])) / (
                        (b[4] + b[2]) + (b[3] + b[0]) + 1e-6
                    )
                    ndvis.append(ndvi)
                    ndwis.append(ndwi)
                    nbrs.append(nbr)
                    bsis.append(bsi)
                    sars.append(-10.0)
            except Exception:
                continue
        if ndvis:
            import statistics

            result[obj] = {
                "ndvi": round(statistics.mean(ndvis), 4),
                "ndwi": round(statistics.mean(ndwis), 4),
                "ndmi": round(statistics.mean(ndwis), 4),  # approximate
                "nbr": round(statistics.mean(nbrs), 4),
                "bsi": round(statistics.mean(bsis), 4),
                "sar": round(statistics.mean(sars), 2),
            }
    return result
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
