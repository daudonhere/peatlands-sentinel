import numpy as np


def estimate_water_table_depth(
    mean_ndwi: float,
    mean_sar_cross_ratio: float,
    dry_spell_days: int = 10,
) -> float:
    base_wtd = -0.35
    ndwi_factor = np.clip(mean_ndwi, -0.6, 0.6) * 0.45
    sar_factor = np.clip((mean_sar_cross_ratio + 12.0) / 10.0, -0.5, 0.5) * 0.25
    dry_decay = float(dry_spell_days) * 0.012

    estimated_wtd = base_wtd + ndwi_factor + sar_factor - dry_decay
    return round(float(np.clip(estimated_wtd, -1.8, 0.1)), 2)


def estimate_peat_subsidence_rate(wtd_meters: float) -> float:
    drainage_depth_cm = max(0.0, -wtd_meters * 100.0)
    subsidence_cm_year = 0.5 + (drainage_depth_cm * 0.042)
    return round(float(subsidence_cm_year), 2)


def evaluate_peat_hydrology_profile(
    metrics: dict[str, float],
) -> dict[str, float | str]:
    ndwi = metrics.get("mean_ndwi", 0.15)
    sar = metrics.get("mean_sar_cross_ratio", -10.5)

    wtd = estimate_water_table_depth(ndwi, sar)
    subsidence = estimate_peat_subsidence_rate(wtd)

    if wtd >= -0.40:
        compliance = "Compliant (Safe <= -40cm)"
        risk = "Low"
    elif wtd >= -0.60:
        compliance = "Warning Threshold (-40 to -60cm)"
        risk = "Moderate"
    elif wtd >= -0.80:
        compliance = "Severe Drainage (-60 to -80cm)"
        risk = "High"
    else:
        compliance = "Critical Desiccation (< -80cm)"
        risk = "Critical"

    return {
        "water_table_depth_m": wtd,
        "water_table_depth_cm": round(wtd * 100.0, 1),
        "subsidence_rate_cm_year": subsidence,
        "hydrology_compliance": compliance,
        "hydrology_risk": risk,
    }
