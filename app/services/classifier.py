from functools import lru_cache
import numpy as np
from sklearn.ensemble import RandomForestClassifier

from app.schemas.analysis import LandTransition, SpectralSummary
from app.services.reference_data import (
    CLASS_NAMES,
    FEATURES,
    TARGET_MODULATORS,
    TRAINING_X,
    TRAINING_Y,
)

_TRAINING_MATRIX = np.array(TRAINING_X, dtype=np.float32)
_TRAINING_LABELS = np.array(TRAINING_Y, dtype=np.int32)


@lru_cache(maxsize=1)
def get_trained_classifier() -> RandomForestClassifier:
    rf = RandomForestClassifier(
        n_estimators=200,
        max_depth=8,
        min_samples_leaf=2,
        random_state=42,
        n_jobs=-1,
    )
    rf.fit(_TRAINING_MATRIX, _TRAINING_LABELS)
    return rf


def training_dataset() -> tuple[np.ndarray, np.ndarray]:
    return _TRAINING_MATRIX.copy(), _TRAINING_LABELS.copy()


def feature_names() -> list[str]:
    return list(FEATURES)


def _as_grid(values: np.ndarray, reference: np.ndarray) -> np.ndarray:
    if values.shape == reference.shape:
        return values
    return np.full(reference.shape, float(values.flat[0]), dtype=np.float32)


def _build_pixel_features(
    ndvi: np.ndarray,
    ndwi: np.ndarray,
    nbr: np.ndarray,
    bsi: np.ndarray,
    sar_cross_ratio: np.ndarray,
) -> np.ndarray:
    size = ndvi.size
    sar_flat = (
        sar_cross_ratio.ravel()
        if sar_cross_ratio.shape == ndvi.shape
        else np.full(size, float(sar_cross_ratio.flat[0]))
    )
    sar_vv = sar_flat - 6.5
    ndwi_flat = (
        ndwi.ravel() if not np.all(np.isnan(ndwi)) else np.zeros(size, dtype=np.float32)
    )
    return np.column_stack(
        [ndvi.ravel(), ndwi_flat, nbr.ravel(), bsi.ravel(), sar_vv, sar_flat]
    ).astype(np.float32)


def classify_raster_pixels(features_matrix: np.ndarray) -> np.ndarray:
    valid = ~np.isnan(features_matrix).any(axis=1)
    result = np.full(len(features_matrix), -1, dtype=np.int32)
    if valid.any():
        result[valid] = get_trained_classifier().predict(features_matrix[valid])
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
        _as_grid(arrays.get("cross_ratio", filler), ndvi),
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


def target_profile(target: str) -> dict:
    return TARGET_MODULATORS.get(target, TARGET_MODULATORS["peat_moisture"])


def _profile_features(target: str) -> np.ndarray:
    spec = target_profile(target)
    return np.array(
        [
            spec["ndvi"],
            spec["ndwi"],
            spec["nbr"],
            spec["bsi"],
            spec["sar"] - 6.5,
            spec["sar"],
        ],
        dtype=np.float32,
    )


def simulate_features(
    target: str, run_id: str, rows: int = 256
) -> tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(abs(hash(run_id)) % (2**32))
    noise = rng.normal(0, 0.04, (rows, 6)).astype(np.float32)
    base_pre = np.array([0.78, 0.14, 0.65, -0.28, -11.8, -18.1], dtype=np.float32)
    base_post = _profile_features(target)
    pre = np.column_stack(
        [np.clip(base_pre + noise, -1.0, 1.0)[:, :4], base_pre[4:] + noise[:, 4:]]
    ).astype(np.float32)
    post = np.column_stack(
        [np.clip(base_post + noise, -1.0, 1.0)[:, :4], base_post[4:] + noise[:, 4:]]
    ).astype(np.float32)
    return pre, post


def simulate_aoi_transitions(
    target: str, run_id: str, area_ha: float
) -> tuple[SpectralSummary, list[LandTransition]]:
    spec = target_profile(target)
    summary = SpectralSummary(
        mean_ndvi=spec["ndvi"],
        mean_ndwi=spec["ndwi"],
        mean_ndmi=spec.get("ndmi", 0.0),
        mean_nbr=spec["nbr"],
        mean_bsi=spec["bsi"],
        max_dnbr=spec["dnbr"],
        mean_sar_cross_ratio=spec["sar"],
    )
    pre, post = simulate_features(target, run_id)
    transitions = compute_land_transition_matrix(
        classify_raster_pixels(pre), classify_raster_pixels(post), area_ha
    )
    return summary, transitions


def simulate_arrays(target: str, run_id: str) -> dict:
    spec = target_profile(target)
    rng = np.random.default_rng(abs(hash(run_id + target)) % (2**32))
    grid = 128

    def field(center: float, spread: float) -> np.ndarray:
        base = np.full((grid, grid), center, dtype=np.float32)
        return np.clip(base + rng.normal(0, spread, (grid, grid)), -1.0, 1.0).astype(
            np.float32
        )

    return {
        "ndvi": field(spec["ndvi"], 0.06),
        "ndwi": field(spec["ndwi"], 0.05),
        "ndmi": field(spec.get("ndmi", 0.1), 0.06),
        "nbr": field(spec["nbr"], 0.05),
        "bsi": field(spec["bsi"], 0.05),
        "cross_ratio": field(spec["sar"], 0.9),
    }
