import numpy as np
from app.services.raster import (
    calculate_ndvi,
    calculate_ndwi,
    calculate_nbr,
    calculate_dnbr,
    classify_dnbr_severity,
)


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


if __name__ == "__main__":
    test_spectral_indices()
    print("All raster self-checks passed.")
