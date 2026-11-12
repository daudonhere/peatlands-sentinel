from functools import lru_cache
import numpy as np
from sklearn.ensemble import RandomForestClassifier

from app.schemas.analysis import LandTransition

CLASS_NAMES = {
    0: "Primary Forest",
    1: "Wet Peatland",
    2: "Bare Land / Cleared",
    3: "Oil Palm Plantation",
    4: "Mining Excavation",
    5: "Water Body",
}


@lru_cache(maxsize=1)
def get_trained_classifier() -> RandomForestClassifier:
    """Provides a baseline Random Forest classifier trained on representative endmember signatures."""
    # Features: [NDVI, NDWI, MNDWI, NBR, BSI, SAR_VH_db, SAR_VV_db]
    synthetic_training_x = np.array(
        [
            # Primary Forest
            [0.82, 0.15, -0.45, 0.75, -0.35, -12.0, -6.5],
            [0.78, 0.10, -0.40, 0.70, -0.30, -11.5, -6.0],
            # Wet Peatland
            [0.60, 0.35, 0.20, 0.45, -0.20, -14.0, -8.0],
            [0.55, 0.40, 0.25, 0.40, -0.15, -15.5, -9.0],
            # Bare Land / Cleared
            [0.18, -0.25, -0.30, 0.05, 0.45, -20.0, -14.0],
            [0.22, -0.20, -0.25, 0.10, 0.40, -19.5, -13.5],
            # Oil Palm Plantation
            [0.65, 0.05, -0.25, 0.50, -0.05, -13.5, -8.5],
            [0.62, 0.08, -0.20, 0.48, -0.02, -13.0, -8.0],
            # Mining Excavation
            [0.08, -0.35, -0.20, -0.15, 0.65, -22.0, -16.0],
            [0.05, -0.40, -0.15, -0.20, 0.70, -23.0, -17.0],
            # Water Body
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
    """Predicts land cover classes for each pixel.

    features_matrix shape: (N_pixels, 7)
    """
    rf = get_trained_classifier()
    return rf.predict(features_matrix)


def compute_land_transition_matrix(
    pre_classes: np.ndarray, post_classes: np.ndarray, total_area_ha: float
) -> list[LandTransition]:
    """Calculates transition statistics between pre-period and post-period land cover."""
    total_pixels = len(pre_classes)
    if total_pixels == 0:
        return []

    ha_per_pixel = total_area_ha / float(total_pixels)
    transitions: list[LandTransition] = []

    unique_transitions = {}
    for pre_c, post_c in zip(pre_classes, post_classes):
        pair = (int(pre_c), int(post_c))
        unique_transitions[pair] = unique_transitions.get(pair, 0) + 1

    for (c1, c2), count in sorted(
        unique_transitions.items(), key=lambda x: x[1], reverse=True
    ):
        if c1 == c2 and len(unique_transitions) > 1:
            # Skip unchanged self-transitions if other conversions occur
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
