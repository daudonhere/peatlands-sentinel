_SUBSIDENCE_RATE_CM_PER_CM_DRAINAGE = 0.067
_CO2_TCO2E_HA_YR_PER_CM_DRAINAGE = 0.91
_MAX_WTD_M = 0.05
_SAFE_WTD_M = -0.40


def simulate_canal_blocking(
    wtd_m: float, area_ha: float, dams_per_100ha: float
) -> dict:
    if dams_per_100ha < 0 or area_ha <= 0:
        raise ValueError("dams_per_100ha must be >= 0 and area_ha > 0.")

    raise_cm = min(dams_per_100ha * 5.0, abs(wtd_m) * 100.0)
    new_wtd_m = min(_MAX_WTD_M, wtd_m + raise_cm / 100.0)

    before_cm = max(0.0, -wtd_m * 100.0)
    after_cm = max(0.0, -new_wtd_m * 100.0)

    delta_cm = before_cm - after_cm
    subsidence_reduction = round(delta_cm * _SUBSIDENCE_RATE_CM_PER_CM_DRAINAGE, 2)
    emission_reduction_ha_yr = round(delta_cm * _CO2_TCO2E_HA_YR_PER_CM_DRAINAGE, 2)

    return {
        "wtd_before_m": round(wtd_m, 2),
        "wtd_after_m": round(new_wtd_m, 2),
        "total_dams": round(dams_per_100ha * area_ha / 100.0),
        "subsidence_reduction_cm_year": subsidence_reduction,
        "emission_reduction_tco2e_ha_year": emission_reduction_ha_yr,
        "emission_reduction_tco2e_year": round(emission_reduction_ha_yr * area_ha, 1),
        "meets_safe_threshold": new_wtd_m >= _SAFE_WTD_M,
    }
