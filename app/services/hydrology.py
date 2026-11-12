import numpy as np

_WTD_SAFE_M = -0.40
_WTD_MAX_M = 0.05


def _clip(value: float, low: float, high: float) -> float:
    return float(np.clip(value, low, high))


def estimate_water_table_depth(
    mean_ndwi: float,
    mean_sar_cross_ratio: float,
    dry_spell_days: int = 10,
    mean_ndmi: float | None = None,
) -> float:
    ndwi_factor = _clip(mean_ndwi, -0.6, 0.6) * 0.50
    sar_norm = _clip((mean_sar_cross_ratio + 15.0) / 12.0, -0.6, 0.6)
    sar_factor = sar_norm * 0.28
    dry_decay = float(dry_spell_days) * 0.011

    wtd = -0.30 + ndwi_factor + sar_factor - dry_decay
    if mean_ndmi is not None:
        ndmi_factor = _clip(mean_ndmi, -0.6, 0.6) * 0.22
        wtd = (wtd * 0.78) + (-0.30 + ndmi_factor) * 0.22

    return round(_clip(wtd, -2.0, _WTD_MAX_M), 2)


def estimate_peat_subsidence_rate(wtd_meters: float) -> float:
    drainage_cm = max(0.0, -wtd_meters * 100.0)
    subsidence = 0.5 + drainage_cm * 0.067
    return round(float(min(subsidence, 15.0)), 2)


def estimate_co2_emission(wtd_meters: float) -> float:
    drainage_cm = max(0.0, -wtd_meters * 100.0)
    return round(float(drainage_cm * 0.91), 2)


def estimate_water_retention_capacity(
    mean_ndmi: float, mean_ndwi: float, mean_sar_cross_ratio: float
) -> float:
    moisture_term = _clip((mean_ndmi + 0.2) / 0.9, 0.0, 1.0)
    surface_term = _clip((mean_ndwi + 0.3) / 0.9, 0.0, 1.0)
    dielectric_term = _clip((mean_sar_cross_ratio + 24.0) / 14.0, 0.0, 1.0)
    score = 0.45 * moisture_term + 0.30 * surface_term + 0.25 * dielectric_term
    return round(score * 100.0, 1)


def estimate_drainage_intensity(
    wtd_meters: float, mean_slope_deg: float, dry_spell_days: int = 10
) -> float:
    depth_term = _clip(-wtd_meters / 1.2, 0.0, 1.0)
    slope_term = _clip(mean_slope_deg / 12.0, 0.0, 1.0)
    climate_term = _clip(dry_spell_days / 60.0, 0.0, 1.0)
    return round((0.55 * depth_term + 0.25 * slope_term + 0.20 * climate_term) * 100, 1)


def estimate_canal_density_index(
    wtd_meters: float, mean_ndwi: float, mean_ndmi: float
) -> dict:
    deficit = _clip((-wtd_meters - 0.30) / 0.9, 0.0, 1.0)
    wetland_loss = _clip((0.35 - mean_ndwi) / 0.7, 0.0, 1.0)
    dryness = _clip((0.40 - mean_ndmi) / 0.8, 0.0, 1.0)
    pressure = 0.45 * deficit + 0.30 * wetland_loss + 0.25 * dryness
    km_per_km2 = round(pressure * 4.2, 2)
    spacing_m = int(round(1000.0 / max(km_per_km2, 0.05), -1))
    return {
        "canal_density_km_km2": km_per_km2,
        "implied_canal_spacing_m": spacing_m,
        "drainage_pressure_index": round(pressure, 4),
        "block_priority": "Immediate"
        if pressure >= 0.65
        else "High"
        if pressure >= 0.45
        else "Planned"
        if pressure >= 0.25
        else "Monitor",
    }


def _compliance_band(wtd: float) -> tuple[str, str]:
    if wtd >= _WTD_SAFE_M:
        return "Compliant (>= -40 cm, PP71/2014)", "Low"
    if wtd >= -0.60:
        return "Warning Threshold (-40 to -60 cm)", "Moderate"
    if wtd >= -0.80:
        return "Severe Drainage (-60 to -80 cm)", "High"
    return "Critical Desiccation (< -80 cm)", "Critical"


def evaluate_peat_hydrology_profile(metrics: dict) -> dict:
    ndwi = float(metrics.get("mean_ndwi", 0.15))
    ndmi = float(metrics.get("mean_ndmi", 0.2))
    sar = float(metrics.get("mean_sar_cross_ratio", -10.5))
    slope = float(metrics.get("mean_slope_deg", 0.6))
    dry_days = int(metrics.get("dry_spell_days", 10))

    wtd = estimate_water_table_depth(ndwi, sar, dry_days, ndmi)
    subsidence = estimate_peat_subsidence_rate(wtd)
    co2_loss = estimate_co2_emission(wtd)
    compliance, risk = _compliance_band(wtd)
    canals = estimate_canal_density_index(wtd, ndwi, ndmi)

    return {
        "water_table_depth_m": wtd,
        "water_table_depth_cm": round(wtd * 100.0, 1),
        "subsidence_rate_cm_year": subsidence,
        "co2_emission_tco2e_ha_year": co2_loss,
        "water_retention_capacity_pct": estimate_water_retention_capacity(
            ndmi, ndwi, sar
        ),
        "drainage_intensity_pct": estimate_drainage_intensity(wtd, slope, dry_days),
        "hydrology_compliance": compliance,
        "hydrology_risk": risk,
        **canals,
    }
