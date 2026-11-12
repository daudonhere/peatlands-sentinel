import numpy as np


def compute_normalized_ratio(band_a: np.ndarray, band_b: np.ndarray) -> np.ndarray:
    """Computes (band_a - band_b) / (band_a + band_b) safely handling zero division."""
    denom = band_a.astype(np.float32) + band_b.astype(np.float32)
    diff = band_a.astype(np.float32) - band_b.astype(np.float32)
    with np.errstate(divide="ignore", invalid="ignore"):
        ratio = np.where(denom == 0.0, 0.0, diff / denom)
    return np.clip(ratio, -1.0, 1.0)


def calculate_ndvi(nir: np.ndarray, red: np.ndarray) -> np.ndarray:
    """Normalized Difference Vegetation Index for canopy health monitoring."""
    return compute_normalized_ratio(nir, red)


def calculate_ndwi(green: np.ndarray, nir: np.ndarray) -> np.ndarray:
    """Normalized Difference Water Index (McFeeters) for surface water presence."""
    return compute_normalized_ratio(green, nir)


def calculate_nbr(nir: np.ndarray, swir: np.ndarray) -> np.ndarray:
    """Normalized Burn Ratio using NIR (B08) and SWIR-2 (B12)."""
    return compute_normalized_ratio(nir, swir)


def calculate_dnbr(pre_fire_nbr: np.ndarray, post_fire_nbr: np.ndarray) -> np.ndarray:
    """Difference Normalized Burn Ratio (dNBR) measuring burn severity."""
    return pre_fire_nbr - post_fire_nbr


def calculate_sar_cross_ratio(vh_db: np.ndarray, vv_db: np.ndarray) -> np.ndarray:
    """VH/VV cross-ratio from decibel backscatter for soil moisture and structure."""
    return vh_db - vv_db


def classify_dnbr_severity(dnbr_value: float) -> str:
    """USGS burn severity classification thresholds."""
    if dnbr_value < -0.1:
        return "Enhanced Regrowth"
    if dnbr_value <= 0.1:
        return "Unburned"
    if dnbr_value <= 0.27:
        return "Low Severity"
    if dnbr_value <= 0.66:
        return "Moderate Severity"
    return "High Severity"
