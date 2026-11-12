from functools import lru_cache
import numpy as np
from sklearn.ensemble import RandomForestClassifier

from app.schemas.analysis import LandTransition, SpectralSummary

CLASS_NAMES = {
    0: "Primary Forest",
    1: "Wet Peatland",
    2: "Bare Land / Cleared",
    3: "Oil Palm Plantation",
    4: "Mining Excavation",
    5: "Water Body",
}

_FEATURES = ["ndvi", "ndwi", "nbr", "bsi", "sar_vv", "sar_vh"]

_TRAINING_X = np.array(
    [
        [0.84, 0.18, 0.72, -0.38, -11.2, -17.5],
        [0.80, 0.14, 0.68, -0.32, -11.8, -18.1],
        [0.76, 0.22, 0.65, -0.28, -12.5, -19.0],
        [0.72, 0.10, 0.60, -0.24, -13.0, -19.8],
        [0.65, 0.38, 0.52, -0.20, -13.5, -20.2],
        [0.60, 0.42, 0.48, -0.16, -14.0, -20.8],
        [0.58, 0.32, 0.44, -0.18, -13.8, -20.4],
        [0.20, -0.22, 0.12, 0.44, -19.8, -26.5],
        [0.15, -0.28, 0.08, 0.50, -20.5, -27.2],
        [0.12, -0.18, 0.06, 0.38, -18.8, -25.5],
        [0.60, 0.06, 0.42, 0.04, -13.2, -19.6],
        [0.65, 0.04, 0.46, 0.02, -13.0, -19.2],
        [0.58, 0.08, 0.40, 0.06, -13.6, -20.0],
        [0.08, -0.38, -0.12, 0.65, -22.0, -28.8],
        [0.05, -0.42, -0.18, 0.72, -23.2, -30.0],
        [0.10, -0.35, -0.08, 0.60, -21.5, -28.0],
        [-0.12, 0.72, 0.65, -0.55, -24.5, -31.5],
        [-0.18, 0.68, 0.60, -0.60, -25.2, -32.2],
        [-0.08, 0.78, 0.70, -0.48, -23.8, -30.8],
        [0.70, 0.08, 0.55, -0.14, -12.2, -18.8],
        [0.74, 0.12, 0.58, -0.18, -11.8, -18.2],
        [0.68, 0.06, 0.52, -0.12, -12.6, -19.2],
    ],
    dtype=np.float32,
)

_TRAINING_Y = np.array(
    [0, 0, 0, 0, 1, 1, 1, 2, 2, 2, 3, 3, 3, 4, 4, 4, 5, 5, 5, 0, 0, 0],
    dtype=np.int32,
)


@lru_cache(maxsize=1)
def get_trained_classifier() -> RandomForestClassifier:
    rf = RandomForestClassifier(
        n_estimators=200,
        max_depth=8,
        min_samples_leaf=2,
        random_state=42,
        n_jobs=-1,
    )
    rf.fit(_TRAINING_X, _TRAINING_Y)
    return rf


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
        if c1 == c2 and len(unique_transitions) > 1:
            continue
        transitions.append(
            LandTransition(
                from_class=CLASS_NAMES.get(c1, f"Class {c1}"),
                to_class=CLASS_NAMES.get(c2, f"Class {c2}"),
                area_hectares=round(count * ha_per_pixel, 2),
                change_percentage=round((count / total_pixels) * 100.0, 1),
            )
        )
    return (
        transitions[:6]
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
        mean_nbr=live["mean_nbr"],
        mean_bsi=live["mean_bsi"],
        max_dnbr=live["max_dnbr"],
        mean_sar_cross_ratio=live["mean_sar_cross_ratio"],
    )


def classify_live_arrays(
    pre_live: dict, post_live: dict, area_ha: float
) -> list[LandTransition]:
    pa = pre_live.get("_arrays", {})
    oa = post_live.get("_arrays", {})

    nan_grid = np.full((128, 128), np.nan, dtype=np.float32)
    pre_feat = _build_pixel_features(
        pa.get("ndvi", nan_grid),
        pa.get("ndwi", nan_grid) if "ndwi" in pa else nan_grid,
        pa.get("nbr", nan_grid),
        pa.get("bsi", nan_grid),
        pa.get("cross_ratio", nan_grid),
    )
    post_feat = _build_pixel_features(
        oa.get("ndvi", nan_grid),
        oa.get("ndwi", nan_grid) if "ndwi" in oa else nan_grid,
        oa.get("nbr", nan_grid),
        oa.get("bsi", nan_grid),
        oa.get("cross_ratio", nan_grid),
    )

    return compute_land_transition_matrix(
        classify_raster_pixels(pre_feat),
        classify_raster_pixels(post_feat),
        area_ha,
    )


def simulate_aoi_transitions(
    target: str, run_id: str, area_ha: float
) -> tuple[SpectralSummary, list[LandTransition]]:
    from app.services.classifier import _TRAINING_X, _TRAINING_Y, TARGET_MODULATORS

    spec = TARGET_MODULATORS.get(target, TARGET_MODULATORS["peat_moisture"])
    summary = SpectralSummary(
        mean_ndvi=spec["ndvi"],
        mean_ndwi=spec["ndwi"],
        mean_nbr=spec["nbr"],
        mean_bsi=spec["bsi"],
        max_dnbr=spec["dnbr"],
        mean_sar_cross_ratio=spec["sar"],
    )
    seed = abs(hash(run_id)) % (2**32)
    rng = np.random.default_rng(seed)
    noise = rng.normal(0, 0.04, (256, 6)).astype(np.float32)
    base_pre = np.array([0.78, 0.14, 0.65, -0.28, -11.8, -18.1], dtype=np.float32)
    base_post = np.array(
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
    pre_feat = np.clip(base_pre + noise, -1.0, 1.0)
    post_feat = np.clip(base_post + noise, -1.0, 1.0)
    transitions = compute_land_transition_matrix(
        classify_raster_pixels(pre_feat), classify_raster_pixels(post_feat), area_ha
    )
    return summary, transitions


TARGET_MODULATORS = {
    "peat_moisture": {
        "ndvi": 0.62,
        "ndwi": 0.28,
        "nbr": 0.55,
        "bsi": -0.22,
        "dnbr": 0.02,
        "sar": -6.5,
    },
    "topography_slope": {
        "ndvi": 0.68,
        "ndwi": 0.12,
        "nbr": 0.60,
        "bsi": -0.18,
        "dnbr": 0.01,
        "sar": -7.2,
    },
    "forest_to_bare": {
        "ndvi": 0.24,
        "ndwi": -0.20,
        "nbr": 0.10,
        "bsi": 0.42,
        "dnbr": 0.28,
        "sar": -14.5,
    },
    "forest_to_mining": {
        "ndvi": 0.12,
        "ndwi": -0.32,
        "nbr": -0.05,
        "bsi": 0.62,
        "dnbr": 0.35,
        "sar": -18.2,
    },
    "forest_to_palm": {
        "ndvi": 0.58,
        "ndwi": 0.04,
        "nbr": 0.44,
        "bsi": 0.02,
        "dnbr": 0.14,
        "sar": -9.8,
    },
    "deforest_expansion": {
        "ndvi": 0.31,
        "ndwi": -0.16,
        "nbr": 0.18,
        "bsi": 0.36,
        "dnbr": 0.25,
        "sar": -13.0,
    },
    "reclamation": {
        "ndvi": 0.52,
        "ndwi": 0.08,
        "nbr": 0.40,
        "bsi": -0.05,
        "dnbr": -0.15,
        "sar": -8.5,
    },
    "bare_to_veg": {
        "ndvi": 0.48,
        "ndwi": 0.02,
        "nbr": 0.35,
        "bsi": -0.02,
        "dnbr": -0.10,
        "sar": -9.2,
    },
    "wildfire_dnbr": {
        "ndvi": 0.18,
        "ndwi": -0.28,
        "nbr": -0.12,
        "bsi": 0.48,
        "dnbr": 0.58,
        "sar": -16.0,
    },
    "water_dynamics": {
        "ndvi": -0.05,
        "ndwi": 0.72,
        "nbr": -0.20,
        "bsi": -0.45,
        "dnbr": 0.00,
        "sar": -21.0,
    },
}
