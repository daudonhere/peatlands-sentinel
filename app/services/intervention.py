"""Canal blocking intervention simulation for peatland rewetting.

Coefficients are literature-based (Hooijer et al., 2012; Ritzema et al., 2014)
and can be calibrated with field measurements via `calibrate_coefficients`.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class CanalBlockingParams:
    """Calibratable parameters for canal blocking simulation."""

    raise_cm_per_dam: float = 5.0
    max_raise_fraction: float = 1.0
    subsidence_rate_per_cm: float = 0.067
    co2_tco2e_per_cm_ha_yr: float = 0.91
    max_wtd_m: float = 0.05
    safe_wtd_m: float = -0.40
    dam_efficiency_decay: float = 0.02  # efficiency drops at deeper WTD


# Default parameters (literature-based)
_DEFAULT_PARAMS = CanalBlockingParams()

# Calibrated parameters (updated by calibrate_coefficients)
_CALIBRATED_PARAMS: CanalBlockingParams | None = None


def get_params() -> CanalBlockingParams:
    return _CALIBRATED_PARAMS or _DEFAULT_PARAMS


def calibrate_coefficients(
    observed_before: list[float],
    observed_after: list[float],
    dams_per_100ha: float,
) -> CanalBlockingParams:
    """Calibrate raise_cm_per_dam from field measurements (before/after WTD).

    observed_before: list of WTD (m) before canal blocking
    observed_after: list of WTD (m) after canal blocking
    dams_per_100ha: number of dams installed per 100 ha
    """
    if (
        not observed_before
        or not observed_after
        or len(observed_before) != len(observed_after)
    ):
        return get_params()

    import statistics

    deltas = [a - b for a, b in zip(observed_after, observed_before)]  # positive = rise
    mean_delta_cm = statistics.mean(deltas) * 100.0
    if dams_per_100ha <= 0 or mean_delta_cm <= 0:
        return get_params()

    raise_per_dam = mean_delta_cm / dams_per_100ha
    params = CanalBlockingParams(
        raise_cm_per_dam=round(raise_per_dam, 2),
        subsidence_rate_per_cm=get_params().subsidence_rate_per_cm,
        co2_tco2e_per_cm_ha_yr=get_params().co2_tco2e_per_cm_ha_yr,
        max_wtd_m=get_params().max_wtd_m,
        safe_wtd_m=get_params().safe_wtd_m,
        dam_efficiency_decay=get_params().dam_efficiency_decay,
    )
    global _CALIBRATED_PARAMS
    _CALIBRATED_PARAMS = params
    return params


def simulate_canal_blocking(
    wtd_m: float, area_ha: float, dams_per_100ha: float
) -> dict:
    if dams_per_100ha < 0 or area_ha <= 0:
        raise ValueError("dams_per_100ha must be >= 0 and area_ha > 0.")

    params = get_params()

    # Efficiency decays at deeper WTD (harder to raise water table)
    depth_cm = abs(wtd_m) * 100.0
    efficiency = max(0.3, 1.0 - depth_cm * params.dam_efficiency_decay / 100.0)
    raise_cm = min(
        dams_per_100ha * params.raise_cm_per_dam * efficiency,
        depth_cm,
    )
    new_wtd_m = min(params.max_wtd_m, wtd_m + raise_cm / 100.0)

    before_cm = max(0.0, -wtd_m * 100.0)
    after_cm = max(0.0, -new_wtd_m * 100.0)

    delta_cm = before_cm - after_cm
    subsidence_reduction = round(delta_cm * params.subsidence_rate_per_cm, 2)
    emission_reduction_ha_yr = round(delta_cm * params.co2_tco2e_per_cm_ha_yr, 2)

    return {
        "wtd_before_m": round(wtd_m, 2),
        "wtd_after_m": round(new_wtd_m, 2),
        "total_dams": round(dams_per_100ha * area_ha / 100.0),
        "subsidence_reduction_cm_year": subsidence_reduction,
        "emission_reduction_tco2e_ha_year": emission_reduction_ha_yr,
        "emission_reduction_tco2e_year": round(emission_reduction_ha_yr * area_ha, 1),
        "meets_safe_threshold": new_wtd_m >= params.safe_wtd_m,
        "calibrated": _CALIBRATED_PARAMS is not None,
        "efficiency": round(efficiency, 3),
    }
