import numpy as np

_LANDSLIDE_WEIGHTS = {
    "slope": 0.42,
    "relief": 0.20,
    "wetness": 0.21,
    "canopy_loss": 0.17,
}


def _clip01(value: float) -> float:
    return float(np.clip(value, 0.0, 1.0))


def landslide_susceptibility(
    mean_slope_deg: float,
    elevation_relief_m: float,
    mean_ndvi: float,
    mean_ndwi: float,
) -> dict:
    slope_term = _clip01(mean_slope_deg / 25.0)
    relief_term = _clip01(elevation_relief_m / 120.0)
    wetness_term = _clip01((mean_ndwi + 0.2) / 0.9)
    canopy_term = _clip01((0.75 - mean_ndvi) / 0.75)

    score = (
        slope_term * _LANDSLIDE_WEIGHTS["slope"]
        + relief_term * _LANDSLIDE_WEIGHTS["relief"]
        + wetness_term * _LANDSLIDE_WEIGHTS["wetness"]
        + canopy_term * _LANDSLIDE_WEIGHTS["canopy_loss"]
    )
    score = round(score, 4)

    if score >= 0.70:
        level = "Very High"
    elif score >= 0.50:
        level = "High"
    elif score >= 0.30:
        level = "Moderate"
    else:
        level = "Low"

    return {
        "landslide_susceptibility": score,
        "landslide_level": level,
        "slope_term": round(slope_term, 4),
        "relief_term": round(relief_term, 4),
        "wetness_term": round(wetness_term, 4),
        "canopy_loss_term": round(canopy_term, 4),
    }


def ground_deformation_risk(
    subsidence_cm_year: float, slope_deg: float, elevation_mean_m: float
) -> dict:
    subsidence_term = _clip01(subsidence_cm_year / 6.0)
    gradient_term = _clip01(slope_deg / 15.0)
    coastal_term = (
        _clip01((10.0 - elevation_mean_m) / 10.0) if elevation_mean_m < 12 else 0.0
    )
    composite = round(
        0.55 * subsidence_term + 0.20 * gradient_term + 0.25 * coastal_term, 4
    )
    return {
        "ground_deformation_index": composite,
        "seismic_sensitivity": "Low"
        if composite < 0.35
        else "Moderate"
        if composite < 0.6
        else "High",
        "note": "Optical and SAR proxies only, no InSAR phase stacking",
    }


def coastal_inundation_risk(
    mean_elevation_m: float, mndwi: float, subsidence_cm_year: float
) -> dict:
    elevation_term = _clip01((8.0 - mean_elevation_m) / 8.0)
    water_term = _clip01((mndwi + 0.05) / 0.55)
    subsidence_term = _clip01(subsidence_cm_year / 5.0)
    score = round(0.45 * elevation_term + 0.35 * water_term + 0.20 * subsidence_term, 4)
    return {
        "inundation_risk": score,
        "inundation_level": "Low"
        if score < 0.35
        else "Moderate"
        if score < 0.6
        else "High",
        "relative sea level rise proxy_cm_year": round(subsidence_cm_year + 0.4, 2),
    }


def multi_hazard_profile(metrics: dict) -> dict:
    slope = float(metrics.get("mean_slope_deg", 0.0))
    relief = float(metrics.get("elevation_relief_m", 0.0))
    elevation = float(metrics.get("mean_elevation_m", 0.0))
    ndvi = float(metrics.get("mean_ndvi", 0.5))
    ndwi = float(metrics.get("mean_ndwi", 0.1))
    mndwi = float(metrics.get("mean_mndwi", ndwi))
    subsidence = float(metrics.get("subsidence_rate_cm_year", 0.0))

    profile = landslide_susceptibility(slope, relief, ndvi, ndwi)
    profile.update(ground_deformation_risk(subsidence, slope, elevation))
    profile.update(coastal_inundation_risk(elevation, mndwi, subsidence))
    profile["dominant_hazard"] = max(
        (
            (profile["landslide_susceptibility"], "Landslide"),
            (profile["ground_deformation_index"], "Ground deformation"),
            (profile["inundation_risk"], "Coastal inundation"),
        ),
        key=lambda item: item[0],
    )[1]
    return profile
