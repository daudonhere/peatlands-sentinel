HOOIJER_TCO2E_HA_YEAR_PER_CM = 0.91
RAISE_PER_DAM_CM = 6.0
MAX_WTD_M = 0.0
SAFE_WTD_M = -0.40


def simulate_canal_blocking(
    wtd_m: float, area_ha: float, dams_per_100ha: float
) -> dict[str, float]:
    if dams_per_100ha < 0 or area_ha <= 0:
        raise ValueError("dams_per_100ha must be >= 0 and area_ha > 0.")

    raise_cm = min(dams_per_100ha * RAISE_PER_DAM_CM, abs(wtd_m) * 100.0)
    new_wtd_m = min(MAX_WTD_M, wtd_m + raise_cm / 100.0)

    before_cm = max(0.0, -wtd_m * 100.0)
    after_cm = max(0.0, -new_wtd_m * 100.0)
    reduction_ha_year = (before_cm - after_cm) * HOOIJER_TCO2E_HA_YEAR_PER_CM

    return {
        "wtd_before_m": round(wtd_m, 2),
        "wtd_after_m": round(new_wtd_m, 2),
        "total_dams": round(dams_per_100ha * area_ha / 100.0),
        "emission_reduction_tco2e_ha_year": round(reduction_ha_year, 2),
        "emission_reduction_tco2e_year": round(reduction_ha_year * area_ha, 1),
        "meets_safe_threshold": new_wtd_m >= SAFE_WTD_M,
    }
