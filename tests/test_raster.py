import numpy as np
from app.services.raster import (
    calculate_ndvi,
    calculate_ndwi,
    calculate_nbr,
    calculate_dnbr,
    classify_dnbr_severity,
)
from app.services.hydrology import evaluate_peat_hydrology_profile
from app.services.intervention import simulate_canal_blocking
from app.services.geotiff import generate_geotiff_raster


def test_spectral_indices():
    nir = np.array([0.8, 0.4], dtype=np.float32)
    red = np.array([0.2, 0.4], dtype=np.float32)
    green = np.array([0.3, 0.5], dtype=np.float32)
    swir = np.array([0.1, 0.2], dtype=np.float32)

    ndvi = calculate_ndvi(nir, red)
    assert np.isclose(ndvi[0], 0.6)
    assert np.isclose(ndvi[1], 0.0)

    ndwi = calculate_ndwi(green, nir)
    assert np.isclose(ndwi[0], (0.3 - 0.8) / 1.1)

    nbr = calculate_nbr(nir, swir)
    assert nbr[0] > 0.0

    dnbr = calculate_dnbr(0.7, 0.2)
    assert np.isclose(dnbr, 0.5)
    assert classify_dnbr_severity(dnbr) == "Moderate Severity"


def test_hydrology_and_geotiff():
    hydro = evaluate_peat_hydrology_profile(
        {"mean_ndwi": 0.2, "mean_sar_cross_ratio": -10.0}
    )
    assert "water_table_depth_m" in hydro
    assert "subsidence_rate_cm_year" in hydro
    assert hydro["hydrology_risk"] in ("Low", "Moderate", "High", "Critical")

    tif = generate_geotiff_raster([102.0, 0.2, 103.0, 0.8], width=32, height=32)
    assert tif.startswith(b"II*\x00")
    assert len(tif) > 1000


def test_canal_blocking():
    r = simulate_canal_blocking(-0.8, 100.0, 4.0)
    assert r["wtd_after_m"] > r["wtd_before_m"]
    assert r["emission_reduction_tco2e_ha_year"] > 0
    assert simulate_canal_blocking(-0.1, 100.0, 20.0)["wtd_after_m"] == 0.0


if __name__ == "__main__":
    test_spectral_indices()
    test_canal_blocking()
    test_hydrology_and_geotiff()
    print("All raster self-checks passed.")
