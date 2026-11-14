"""Unit tests for GEE pipeline_metrics and firms multi-sensor."""

import asyncio
from unittest.mock import patch, MagicMock


def test_firms_safe_float():
    from app.services.firms import _safe_float

    assert _safe_float("5.01") == 5.01
    assert _safe_float("") == 0.0
    assert _safe_float(None) == 0.0
    assert _safe_float("abc") == 0.0


def test_firms_sensors_list():
    from app.services.firms import FIRMS_SENSORS_NRT, FIRMS_SENSORS_ARCHIVE

    assert "VIIRS_SNPP_NRT" in FIRMS_SENSORS_NRT
    assert "VIIRS_NOAA20_NRT" in FIRMS_SENSORS_NRT
    assert "MODIS_NRT" in FIRMS_SENSORS_NRT
    assert "VIIRS_SNPP_SP" in FIRMS_SENSORS_ARCHIVE
    assert "MODIS_SP" in FIRMS_SENSORS_ARCHIVE


def test_firms_fetch_active_fires_mock():
    """Test fetch_active_fires with mocked HTTP."""
    import asyncio
    from unittest.mock import AsyncMock, patch

    mock_csv = (
        "latitude,longitude,bright_ti4,scan,track,acq_date,acq_time,satellite,instrument,confidence,version,bright_ti5,frp,daynight\n"
        "-4.12051,114.75179,330.21,0.52,0.41,2026-11-10,612,N20,VIIRS,n,2.0NRT,290.05,5.01,D\n"
    )

    async def run():
        with patch("httpx.AsyncClient.get") as mock_get:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.text = mock_csv
            mock_resp.raise_for_status = MagicMock()
            mock_get.return_value = mock_resp

            from app.services.firms import fetch_active_fires

            fires = await fetch_active_fires([114.0, -4.2, 115.0, -4.0], 3)
            assert len(fires) >= 1
            assert fires[0]["latitude"] == -4.12051
            assert fires[0]["sensor"] in (
                "VIIRS_SNPP_NRT",
                "VIIRS_NOAA20_NRT",
                "MODIS_NRT",
            )

    asyncio.run(run())


def test_gee_pipeline_metrics_import():
    from app.services import gee

    assert hasattr(gee, "pipeline_metrics")
    assert hasattr(gee, "landsat_pipeline_metrics")
    assert hasattr(gee, "is_available")


def test_gee_analysis_import():
    from app.services import gee_analysis

    assert hasattr(gee_analysis, "worldcover_training_data")
    assert hasattr(gee_analysis, "worldcover_mask")
    assert hasattr(gee_analysis, "validate_classification")
    assert hasattr(gee_analysis, "compute_target_modulators")
    assert hasattr(gee_analysis, "cross_sensor_validation")


def test_sources_list():
    from app.services.sources import _SOURCES

    assert "planetary_computer" in _SOURCES
    assert "gee" in _SOURCES
    assert "landsat" in _SOURCES


def test_classifier_worldcover_training():
    from app.services import classifier

    # Test set/get
    features = [[0.5, 0.1, 0.5, -0.2, -10.0, -16.5]]
    labels = [0]
    classifier.set_worldcover_training(features, labels)
    f, l = classifier.get_training_data()
    assert len(f) == 1
    assert len(l) == 1
    assert l[0] == 0

    # Reset
    classifier.set_worldcover_training([], [])
    f2, l2 = classifier.get_training_data()
    assert len(f2) > 0  # falls back to hardcoded


def test_reference_data_update_modulators():
    from app.services import reference_data

    original_count = len(reference_data.TARGET_MODULATORS)
    reference_data.update_target_modulators({"test_obj": {"ndvi": 0.5}})
    assert "test_obj" in reference_data.TARGET_MODULATORS
    # Cleanup
    del reference_data.TARGET_MODULATORS["test_obj"]


def test_intervention_calibrate():
    from app.services.intervention import (
        calibrate_coefficients,
        simulate_canal_blocking,
    )

    # Calibrate with field data
    before = [-0.5, -0.6, -0.4]
    after = [-0.3, -0.35, -0.25]
    params = calibrate_coefficients(before, after, 2.0)
    assert params.raise_cm_per_dam > 0

    # Simulate with calibrated params
    r = simulate_canal_blocking(-0.5, 100.0, 2.0)
    assert r["calibrated"] is True
    assert r["efficiency"] > 0


if __name__ == "__main__":
    test_firms_safe_float()
    test_firms_sensors_list()
    test_gee_pipeline_metrics_import()
    test_gee_analysis_import()
    test_sources_list()
    test_classifier_worldcover_training()
    test_reference_data_update_modulators()
    test_intervention_calibrate()
    print("All unit tests passed!")
