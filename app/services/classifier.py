from __future__ import annotations

import numpy as np
from sklearn.ensemble import RandomForestClassifier

from app.config import get_settings
from app.schemas.analysis import LandTransition, SpectralSummary
from app.services.reference_data import CLASS_NAMES, FEATURES

_TRAINING_FEATURES: list[list[float]] = []
_TRAINING_LABELS: list[int] = []
_TRAINING_COORDS: list[list[float]] = []


def new_classifier(n_estimators: int | None = None) -> RandomForestClassifier:
    return RandomForestClassifier(
        n_estimators=int(n_estimators or get_settings().gee_rf_trees),
        max_depth=16,
        min_samples_leaf=1,
        random_state=42,
        n_jobs=-1,
    )


def set_worldcover_training(
    features: list[list[float]],
    labels: list[int],
    coords: list[list[float]] | None = None,
) -> None:
    global _TRAINING_FEATURES, _TRAINING_LABELS, _TRAINING_COORDS
    if features and labels and len(features) == len(labels):
        _TRAINING_FEATURES = list(features)
        _TRAINING_LABELS = list(labels)
        _TRAINING_COORDS = list(coords) if coords and len(coords) == len(labels) else []
    else:
        _TRAINING_FEATURES = []
        _TRAINING_LABELS = []
        _TRAINING_COORDS = []


def get_training_coords() -> np.ndarray:
    if not _TRAINING_COORDS:
        return np.empty((0, 2), dtype=np.float64)
    return np.array(_TRAINING_COORDS, dtype=np.float64)


def get_training_data() -> tuple[np.ndarray, np.ndarray]:
    if not _TRAINING_FEATURES or not _TRAINING_LABELS:
        return np.empty((0, len(FEATURES)), dtype=np.float32), np.empty(
            0, dtype=np.int32
        )
    return (
        np.array(_TRAINING_FEATURES, dtype=np.float32),
        np.array(_TRAINING_LABELS, dtype=np.int32),
    )


def training_dataset() -> tuple[np.ndarray, np.ndarray]:
    return get_training_data()


def get_trained_classifier() -> RandomForestClassifier | None:
    features, labels = get_training_data()
    if features.size == 0 or len(np.unique(labels)) < 2:
        return None
    rf = new_classifier()
    rf.fit(features, labels)
    return rf


def _as_grid(values: np.ndarray, reference: np.ndarray) -> np.ndarray:
    if values.shape == reference.shape:
        return values
    return np.full(reference.shape, float(values.flat[0]), dtype=np.float32)


def _build_pixel_features(
    ndvi: np.ndarray,
    ndwi: np.ndarray,
    nbr: np.ndarray,
    bsi: np.ndarray,
) -> np.ndarray:
    size = ndvi.size
    ndwi_flat = (
        ndwi.ravel() if not np.all(np.isnan(ndwi)) else np.zeros(size, dtype=np.float32)
    )
    return np.column_stack([ndvi.ravel(), ndwi_flat, nbr.ravel(), bsi.ravel()]).astype(
        np.float32
    )


def classify_raster_pixels(features_matrix: np.ndarray) -> np.ndarray:
    valid = ~np.isnan(features_matrix).any(axis=1)
    result = np.full(len(features_matrix), -1, dtype=np.int32)
    model = get_trained_classifier()
    if model is not None and valid.any():
        result[valid] = model.predict(features_matrix[valid])
    return result


def classify_arrays(arrays: dict) -> np.ndarray:
    nan_grid = np.full((128, 128), np.nan, dtype=np.float32)
    ndvi = arrays.get("ndvi", nan_grid)
    shape = ndvi.shape if ndvi.ndim == 2 else (128, 128)
    filler = np.full(shape, np.nan, dtype=np.float32)
    features = _build_pixel_features(
        ndvi,
        _as_grid(arrays.get("ndwi", filler), ndvi),
        _as_grid(arrays.get("nbr", filler), ndvi),
        _as_grid(arrays.get("bsi", filler), ndvi),
    )
    return classify_raster_pixels(features)


def compute_land_transition_matrix(
    pre_classes: np.ndarray, post_classes: np.ndarray, total_area_ha: float
) -> list[LandTransition]:
    valid = (pre_classes >= 0) & (post_classes >= 0)
    pre_v = pre_classes[valid]
    post_v = post_classes[valid]
    total_pixels = int(valid.sum())
    if total_pixels == 0:
        return []

    ha_per_pixel = total_area_ha / float(total_pixels)
    unique_transitions: dict[tuple[int, int], int] = {}
    for pc, oc in zip(pre_v.tolist(), post_v.tolist()):
        pair = (pc, oc)
        unique_transitions[pair] = unique_transitions.get(pair, 0) + 1

    transitions: list[LandTransition] = []
    for (c1, c2), count in sorted(
        unique_transitions.items(), key=lambda x: x[1], reverse=True
    ):
        transitions.append(
            LandTransition(
                from_class=CLASS_NAMES.get(c1, f"Class {c1}"),
                to_class=CLASS_NAMES.get(c2, f"Class {c2}"),
                area_hectares=round(count * ha_per_pixel, 2),
                change_percentage=round((count / total_pixels) * 100.0, 1),
            )
        )
    return (
        transitions[:8]
        if transitions
        else [
            LandTransition(
                from_class=CLASS_NAMES.get(list(unique_transitions)[0][0], "Stable"),
                to_class=CLASS_NAMES.get(list(unique_transitions)[0][1], "Stable"),
                area_hectares=round(total_area_ha, 2),
                change_percentage=100.0,
            )
        ]
    )


def build_spectral_summary_from_live(live: dict) -> SpectralSummary:
    return SpectralSummary(
        mean_ndvi=live["mean_ndvi"],
        mean_ndwi=live["mean_ndwi"],
        mean_ndmi=live.get("mean_ndmi", 0.0),
        mean_nbr=live["mean_nbr"],
        mean_bsi=live["mean_bsi"],
        max_dnbr=live["max_dnbr"],
        mean_sar_cross_ratio=live["mean_sar_cross_ratio"],
    )


def classify_live_arrays(
    pre_live: dict, post_live: dict, area_ha: float
) -> list[LandTransition]:
    return compute_land_transition_matrix(
        classify_arrays(pre_live.get("_arrays", {})),
        classify_arrays(post_live.get("_arrays", {})),
        area_ha,
    )
