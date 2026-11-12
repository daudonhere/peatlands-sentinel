import numpy as np

_WTD_SAFE_M = -0.40
_WTD_MAX_M = 0.05


def estimate_water_table_depth(
    mean_ndwi: float,
    mean_sar_cross_ratio: float,
    dry_spell_days: int = 10,
) -> float:
    ndwi_factor = np.clip(mean_ndwi, -0.6, 0.6) * 0.50
    sar_norm = np.clip((mean_sar_cross_ratio + 15.0) / 12.0, -0.6, 0.6)
    sar_factor = float(sar_norm) * 0.28
    dry_decay = float(dry_spell_days) * 0.011

    wtd = -0.30 + ndwi_factor + sar_factor - dry_decay
    return round(float(np.clip(wtd, -2.0, _WTD_MAX_M)), 2)


def estimate_peat_subsidence_rate(wtd_meters: float) -> float:
    drainage_cm = max(0.0, -wtd_meters * 100.0)
    subsidence = 0.5 + drainage_cm * 0.067
    return round(float(min(subsidence, 15.0)), 2)


def estimate_co2_emission(wtd_meters: float) -> float:
    drainage_cm = max(0.0, -wtd_meters * 100.0)
    return round(float(drainage_cm * 0.91), 2)


def evaluate_peat_hydrology_profile(metrics: dict) -> dict:
    ndwi = float(metrics.get("mean_ndwi", 0.15))
    sar = float(metrics.get("mean_sar_cross_ratio", -10.5))

    wtd = estimate_water_table_depth(ndwi, sar)
    subsidence = estimate_peat_subsidence_rate(wtd)
    co2_loss = estimate_co2_emission(wtd)

    if wtd >= _WTD_SAFE_M:
        compliance = "Compliant (>= -40 cm, PP71/2014)"
        risk = "Low"
    elif wtd >= -0.60:
        compliance = "Warning Threshold (-40 to -60 cm)"
        risk = "Moderate"
    elif wtd >= -0.80:
        compliance = "Severe Drainage (-60 to -80 cm)"
        risk = "High"
    else:
        compliance = "Critical Desiccation (< -80 cm)"
        risk = "Critical"

    return {
        "water_table_depth_m": wtd,
        "water_table_depth_cm": round(wtd * 100.0, 1),
        "subsidence_rate_cm_year": subsidence,
        "co2_emission_tco2e_ha_year": co2_loss,
        "hydrology_compliance": compliance,
        "hydrology_risk": risk,
    }
