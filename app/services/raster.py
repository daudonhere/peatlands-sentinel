import numpy as np


def compute_normalized_ratio(band_a: np.ndarray, band_b: np.ndarray) -> np.ndarray:
    denom = band_a.astype(np.float32) + band_b.astype(np.float32)
    diff = band_a.astype(np.float32) - band_b.astype(np.float32)
    with np.errstate(divide="ignore", invalid="ignore"):
        ratio = np.where(denom == 0.0, 0.0, diff / denom)
    return np.clip(ratio, -1.0, 1.0)


def calculate_ndvi(nir: np.ndarray, red: np.ndarray) -> np.ndarray:
    return compute_normalized_ratio(nir, red)


def calculate_ndwi(green: np.ndarray, nir: np.ndarray) -> np.ndarray:
    return compute_normalized_ratio(green, nir)


def calculate_mndwi(green: np.ndarray, swir1: np.ndarray) -> np.ndarray:
    return compute_normalized_ratio(green, swir1)


def calculate_ndmi(nir: np.ndarray, swir1: np.ndarray) -> np.ndarray:
    return compute_normalized_ratio(nir, swir1)


def calculate_nbr(nir: np.ndarray, swir: np.ndarray) -> np.ndarray:
    return compute_normalized_ratio(nir, swir)


def calculate_dnbr(pre_fire_nbr: np.ndarray, post_fire_nbr: np.ndarray) -> np.ndarray:
    return pre_fire_nbr - post_fire_nbr


def calculate_bsi(
    blue: np.ndarray, red: np.ndarray, nir: np.ndarray, swir1: np.ndarray
) -> np.ndarray:
    num = (swir1 + red) - (nir + blue)
    denom = (swir1 + red) + (nir + blue)
    with np.errstate(divide="ignore", invalid="ignore"):
        bsi = np.where(denom == 0.0, 0.0, num / denom)
    return np.clip(bsi, -1.0, 1.0)


def calculate_sar_cross_ratio(vh_db: np.ndarray, vv_db: np.ndarray) -> np.ndarray:
    return vh_db - vv_db


def classify_dnbr_severity(dnbr_value: float) -> str:
    if dnbr_value < -0.1:
        return "Enhanced Regrowth"
    if dnbr_value <= 0.1:
        return "Unburned"
    if dnbr_value <= 0.27:
        return "Low Severity"
    if dnbr_value <= 0.66:
        return "Moderate Severity"
    return "High Severity"
