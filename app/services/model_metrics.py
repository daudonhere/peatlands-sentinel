import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import StratifiedKFold, cross_val_predict

from app.schemas.analysis import ClassScatterPoint, ModelAccuracy
from app.services.classifier import (
    classify_arrays,
    get_trained_classifier,
    training_dataset,
)
from app.services.reference_data import CLASS_NAMES, CLASS_COLORS
from app.services.validation import accuracy_report, per_class_user_accuracy


def _cross_validated_predictions() -> tuple[np.ndarray, np.ndarray]:
    features, labels = training_dataset()
    if features.size == 0 or len(np.unique(labels)) < 2:
        return np.empty(0, dtype=np.int32), np.empty(0, dtype=np.int32)
    counts = np.bincount(labels, minlength=len(CLASS_NAMES))
    min_count = int(counts[counts > 0].min())
    if min_count < 2:
        return np.empty(0, dtype=np.int32), np.empty(0, dtype=np.int32)
    folds = int(min(5, min_count))
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


def class_scatter_from_arrays(
    pre_arrays: dict, post_arrays: dict
) -> list[ClassScatterPoint]:
    pre_labels = classify_arrays(pre_arrays)
    post_labels = classify_arrays(post_arrays)

    def column(arrays: dict, key: str) -> np.ndarray | None:
        values = arrays.get(key)
        return values.ravel() if isinstance(values, np.ndarray) else None

    pre_ndvi, post_ndvi = column(pre_arrays, "ndvi"), column(post_arrays, "ndvi")
    pre_ndwi, post_ndwi = column(pre_arrays, "ndwi"), column(post_arrays, "ndwi")
    pre_ndmi, post_ndmi = column(pre_arrays, "ndmi"), column(post_arrays, "ndmi")
    pre_bsi, post_bsi = column(pre_arrays, "bsi"), column(post_arrays, "bsi")
    pre_nbr, post_nbr = column(pre_arrays, "nbr"), column(post_arrays, "nbr")
    pre_sar, post_sar = (
        column(pre_arrays, "cross_ratio"),
        column(post_arrays, "cross_ratio"),
    )
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
                class_code=code,
                pre_ndvi=round(float(np.nanmean(pre_ndvi[pre_mask])), 4)
                if pre_mask.any()
                else 0.0,
                post_ndvi=round(float(np.nanmean(post_ndvi[post_mask])), 4)
                if post_mask.any()
                else 0.0,
                pre_ndwi=round(float(np.nanmean(pre_ndwi[pre_mask])), 4)
                if pre_ndwi is not None and pre_mask.any()
                else 0.0,
                post_ndwi=round(float(np.nanmean(post_ndwi[post_mask])), 4)
                if post_ndwi is not None and post_mask.any()
                else 0.0,
                pre_ndmi=round(float(np.nanmean(pre_ndmi[pre_mask])), 4)
                if pre_ndmi is not None and pre_mask.any()
                else 0.0,
                post_ndmi=round(float(np.nanmean(post_ndmi[post_mask])), 4)
                if post_ndmi is not None and post_mask.any()
                else 0.0,
                pre_bsi=round(float(np.nanmean(pre_bsi[pre_mask])), 4)
                if pre_bsi is not None and pre_mask.any()
                else 0.0,
                post_bsi=round(float(np.nanmean(post_bsi[post_mask])), 4)
                if post_bsi is not None and post_mask.any()
                else 0.0,
                pre_nbr=round(float(np.nanmean(pre_nbr[pre_mask])), 4)
                if pre_nbr is not None and pre_mask.any()
                else 0.0,
                post_nbr=round(float(np.nanmean(post_nbr[post_mask])), 4)
                if post_nbr is not None and post_mask.any()
                else 0.0,
                pre_sar=round(float(np.nanmean(pre_sar[pre_mask])), 4)
                if pre_sar is not None and pre_mask.any()
                else 0.0,
                post_sar=round(float(np.nanmean(post_sar[post_mask])), 4)
                if post_sar is not None and post_mask.any()
                else 0.0,
            )
        )
    return points


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
    if model is None:
        return {
            "algorithm": "RandomForest",
            "n_estimators": 0,
            "max_depth": 0,
            "classes": [CLASS_NAMES[i] for i in sorted(CLASS_NAMES)],
        }
    return {
        "algorithm": "RandomForest",
        "n_estimators": int(model.n_estimators),
        "max_depth": int(model.max_depth or 0),
        "classes": [CLASS_NAMES[i] for i in sorted(CLASS_NAMES)],
    }
