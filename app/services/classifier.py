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


@lru_cache(maxsize=1)
def get_trained_classifier() -> RandomForestClassifier:
    synthetic_training_x = np.array(
        [
            [0.82, 0.15, -0.45, 0.75, -0.35, -12.0, -6.5],
            [0.78, 0.10, -0.40, 0.70, -0.30, -11.5, -6.0],
            [0.60, 0.35, 0.20, 0.45, -0.20, -14.0, -8.0],
            [0.55, 0.40, 0.25, 0.40, -0.15, -15.5, -9.0],
            [0.18, -0.25, -0.30, 0.05, 0.45, -20.0, -14.0],
            [0.22, -0.20, -0.25, 0.10, 0.40, -19.5, -13.5],
            [0.65, 0.05, -0.25, 0.50, -0.05, -13.5, -8.5],
            [0.62, 0.08, -0.20, 0.48, -0.02, -13.0, -8.0],
            [0.08, -0.35, -0.20, -0.15, 0.65, -22.0, -16.0],
            [0.05, -0.40, -0.15, -0.20, 0.70, -23.0, -17.0],
            [-0.20, 0.75, 0.85, -0.30, -0.60, -25.0, -18.0],
            [-0.15, 0.70, 0.80, -0.25, -0.55, -24.5, -17.5],
        ],
        dtype=np.float32,
    )
    synthetic_training_y = np.array(
        [0, 0, 1, 1, 2, 2, 3, 3, 4, 4, 5, 5], dtype=np.int32
    )
    rf = RandomForestClassifier(n_estimators=50, random_state=42)
    rf.fit(synthetic_training_x, synthetic_training_y)
    return rf


def classify_raster_pixels(features_matrix: np.ndarray) -> np.ndarray:
    return get_trained_classifier().predict(features_matrix)


def compute_land_transition_matrix(
    pre_classes: np.ndarray, post_classes: np.ndarray, total_area_ha: float
) -> list[LandTransition]:
    total_pixels = len(pre_classes)
    if total_pixels == 0:
        return []

    ha_per_pixel = total_area_ha / float(total_pixels)
    transitions: list[LandTransition] = []
    unique_transitions: dict[tuple[int, int], int] = {}

    for pre_c, post_c in zip(pre_classes, post_classes):
        pair = (int(pre_c), int(post_c))
        unique_transitions[pair] = unique_transitions.get(pair, 0) + 1

    for (c1, c2), count in sorted(
        unique_transitions.items(), key=lambda x: x[1], reverse=True
    ):
        if c1 == c2 and len(unique_transitions) > 1:
            continue
        area_ha = round(count * ha_per_pixel, 2)
        pct = round((count / total_pixels) * 100.0, 1)
        transitions.append(
            LandTransition(
                from_class=CLASS_NAMES.get(c1, f"Class {c1}"),
                to_class=CLASS_NAMES.get(c2, f"Class {c2}"),
                area_hectares=area_ha,
                change_percentage=pct,
            )
        )
    return transitions[:5]


def simulate_aoi_transitions(
    target: str, run_id: str, area_ha: float
) -> tuple[SpectralSummary, list[LandTransition]]:
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
    noise = rng.normal(0, 0.05, (100, 7))

    pre_features = (
        np.array([0.78, 0.12, -0.40, 0.70, -0.30, -11.5, -6.0], dtype=np.float32)
        + noise
    )
    post_features = (
        np.array(
            [
                spec["ndvi"],
                spec["ndwi"],
                -0.3,
                spec["nbr"],
                spec["bsi"],
                spec["sar"],
                spec["sar"] - 5.0,
            ],
            dtype=np.float32,
        )
        + noise
    )

    pre_classes = classify_raster_pixels(pre_features)
    post_classes = classify_raster_pixels(post_features)
    transitions = compute_land_transition_matrix(pre_classes, post_classes, area_ha)
    return summary, transitions
