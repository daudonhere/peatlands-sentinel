from functools import lru_cache
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import StratifiedKFold, cross_val_predict

from app.schemas.analysis import ClassScatterPoint, ModelAccuracy
from app.services.classifier import (
    classify_arrays,
    get_trained_classifier,
    simulate_arrays,
    training_dataset,
)
from app.services.reference_data import CLASS_NAMES, CLASS_COLORS
from app.services.validation import accuracy_report, per_class_user_accuracy

_BASELINE_FEATURES = {
    "ndvi": 0.78,
    "ndwi": 0.14,
    "ndmi": 0.38,
    "nbr": 0.66,
    "bsi": -0.28,
    "cross_ratio": -18.1,
}


def _cross_validated_predictions() -> tuple[np.ndarray, np.ndarray]:
    features, labels = training_dataset()
    counts = np.bincount(labels, minlength=len(CLASS_NAMES))
    folds = int(max(2, min(5, counts[counts > 0].min())))
    model = RandomForestClassifier(
        n_estimators=300,
        max_depth=8,
        min_samples_leaf=1,
        random_state=42,
        n_jobs=-1,
    )
    predictions = cross_val_predict(
        model,
        features,
        labels,
        cv=StratifiedKFold(n_splits=folds, shuffle=True, random_state=42),
    )
    return labels, predictions


@lru_cache(maxsize=1)
def evaluate_local_model() -> ModelAccuracy:
    labels, predictions = _cross_validated_predictions()
    return accuracy_report(
        labels, predictions, [CLASS_NAMES[i] for i in sorted(CLASS_NAMES)]
    )


def model_breakdown() -> list[dict]:
    report = evaluate_local_model()
    rows = per_class_user_accuracy(report)
    colors = {name: CLASS_COLORS[code] for code, name in CLASS_NAMES.items()}
    for row in rows:
        row["color"] = colors.get(row["class"], "#7a7a7a")
    return rows


def _grid_from_baseline() -> dict:
    return {
        key: np.full((128, 128), value, dtype=np.float32)
        for key, value in _BASELINE_FEATURES.items()
    }


def class_scatter_from_arrays(
    pre_arrays: dict, post_arrays: dict
) -> list[ClassScatterPoint]:
    pre_labels = classify_arrays(pre_arrays)
    post_labels = classify_arrays(post_arrays)

    def column(arrays: dict, key: str) -> np.ndarray | None:
        values = arrays.get(key)
        return values.ravel() if isinstance(values, np.ndarray) else None

    pre_ndvi, post_ndvi = column(pre_arrays, "ndvi"), column(post_arrays, "ndvi")
    pre_ndmi, post_ndmi = column(pre_arrays, "ndmi"), column(post_arrays, "ndmi")
    if pre_ndvi is None or post_ndvi is None:
        return []

    points: list[ClassScatterPoint] = []
    for code in sorted(CLASS_NAMES):
        pre_mask = pre_labels == code
        post_mask = post_labels == code
        if not pre_mask.any() and not post_mask.any():
            continue
        points.append(
            ClassScatterPoint(
                land_class=CLASS_NAMES[code],
                pre_ndvi=round(float(np.nanmean(pre_ndvi[pre_mask])), 4)
                if pre_mask.any()
                else 0.0,
                post_ndvi=round(float(np.nanmean(post_ndvi[post_mask])), 4)
                if post_mask.any()
                else 0.0,
                pre_ndmi=round(float(np.nanmean(pre_ndmi[pre_mask])), 4)
                if pre_ndmi is not None and pre_mask.any()
                else 0.0,
                post_ndmi=round(float(np.nanmean(post_ndmi[post_mask])), 4)
                if post_ndmi is not None and post_mask.any()
                else 0.0,
            )
        )
    return points


def simulate_class_scatter(target: str, run_id: str) -> list[ClassScatterPoint]:
    return class_scatter_from_arrays(
        _grid_from_baseline(), simulate_arrays(target, run_id)
    )


def landcover_grid(arrays: dict) -> np.ndarray:
    labels = classify_arrays(arrays)
    side = int(round(np.sqrt(labels.size)))
    return labels.reshape(side, side).astype(np.int8)


def change_grid(pre_arrays: dict, post_arrays: dict) -> np.ndarray:
    pre = classify_arrays(pre_arrays)
    post = classify_arrays(post_arrays)
    changed = (pre >= 0) & (post >= 0) & (pre != post)
    grid = np.zeros(post.shape, dtype=np.int8)
    grid[changed] = 1
    return grid


def trained_model_info() -> dict:
    model = get_trained_classifier()
    return {
        "algorithm": "RandomForest",
        "n_estimators": int(model.n_estimators),
        "max_depth": int(model.max_depth or 0),
        "classes": [CLASS_NAMES[i] for i in sorted(CLASS_NAMES)],
    }
