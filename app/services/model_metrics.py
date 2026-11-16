import numpy as np
from sklearn.model_selection import StratifiedKFold, cross_val_predict

from app.schemas.analysis import ClassScatterPoint, ModelAccuracy
from app.services.classifier import (
    classify_arrays,
    get_trained_classifier,
    get_training_coords,
    new_classifier,
    training_dataset,
)
from app.services.reference_data import CLASS_NAMES, CLASS_COLORS
from app.services.validation import accuracy_report, per_class_user_accuracy


def _spatial_holdout_predictions() -> tuple[np.ndarray, np.ndarray] | None:
    features, labels = training_dataset()
    coords = get_training_coords()
    if (
        features.size == 0
        or coords.shape[0] != features.shape[0]
        or coords.shape[0] < 20
    ):
        return None
    counts = np.bincount(labels, minlength=len(CLASS_NAMES))
    if int((counts > 0).sum()) < 2:
        return None
    # Build spatial blocks (0.05 deg grid) so train/test never share a location.
    block_ids = np.array(
        [f"{int(c[0] * 20)}_{int(c[1] * 20)}" for c in coords], dtype=object
    )
    unique_blocks = np.unique(block_ids)
    if unique_blocks.size < 4:
        return None
    rng = np.random.default_rng(42)
    shuffled = rng.permutation(unique_blocks)
    cut = max(1, int(round(unique_blocks.size * 0.7)))
    train_blocks = set(shuffled[:cut].tolist())
    test_blocks = set(shuffled[cut:].tolist())
    train_mask = np.array([b in train_blocks for b in block_ids])
    test_mask = ~train_mask
    if train_mask.sum() < 10 or test_mask.sum() < 10:
        return None
    # Keep only classes present in both splits.
    train_labels = labels[train_mask]
    test_labels = labels[test_mask]
    common = np.intersect1d(np.unique(train_labels), np.unique(test_labels))
    if common.size < 2:
        return None
    train_keep = np.isin(labels, common) & train_mask
    test_keep = np.isin(labels, common) & test_mask
    if train_keep.sum() < 10 or test_keep.sum() < 10:
        return None
    model = new_classifier()
    model.fit(features[train_keep], labels[train_keep])
    preds = model.predict(features[test_keep])
    return labels[test_keep], preds


def _cross_validated_predictions() -> tuple[np.ndarray, np.ndarray]:
    spatial = _spatial_holdout_predictions()
    if spatial is not None:
        return spatial
    features, labels = training_dataset()
    empty = (np.empty(0, dtype=np.int32), np.empty(0, dtype=np.int32))
    if features.size == 0:
        return empty
    counts = np.bincount(labels, minlength=len(CLASS_NAMES))
    usable = counts >= 2
    if int(usable.sum()) < 2:
        return empty
    keep = usable[labels]
    features = features[keep]
    labels = labels[keep]
    folds = int(min(5, counts[usable].min()))
    model = new_classifier()
    predictions = cross_val_predict(
        model,
        features,
        labels,
        cv=StratifiedKFold(n_splits=folds, shuffle=True, random_state=42),
    )
    return labels, predictions
    labels, predictions = _cross_validated_predictions()
    return accuracy_report(
        labels, predictions, [CLASS_NAMES[i] for i in sorted(CLASS_NAMES)]
    )


def evaluate_local_model() -> ModelAccuracy:
    labels, predictions = _cross_validated_predictions()
    return accuracy_report(
        labels, predictions, [CLASS_NAMES[i] for i in sorted(CLASS_NAMES)]
    )
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
