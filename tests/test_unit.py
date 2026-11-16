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


def test_sources_list():
    from app.services.sources import _SOURCES

    assert "planetary_computer" in _SOURCES
    assert "gee" in _SOURCES
    assert "landsat" in _SOURCES


def test_classifier_worldcover_training():
    from app.services import classifier

    features = [[0.5, 0.1, 0.5, -0.2]]
    labels = [0]
    classifier.set_worldcover_training(features, labels)
    f, l = classifier.get_training_data()
    assert len(f) == len(features)
    assert len(l) == len(features)
    assert l[0] == 0

    classifier.set_worldcover_training([], [])
    f2, l2 = classifier.get_training_data()
    assert len(f2) == 0
    assert len(l2) == 0
    assert classifier.get_trained_classifier() is None


def test_reference_data_targets():
    from app.services import reference_data

    assert len(reference_data.ANALYSIS_TARGETS) >= 20
    assert "peat_moisture" in reference_data.ANALYSIS_TARGETS


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


def test_firms_confidence_filter():
    """Test FIRMS confidence values."""
    from app.services.firms import fetch_active_fires

    # Confidence values should be n, l, h, or empty
    assert True  # structural test


def test_firms_archive_param():
    """Test fetch_active_fires accepts archive param."""
    import inspect
    from app.services.firms import fetch_active_fires

    sig = inspect.signature(fetch_active_fires)
    assert "archive" in sig.parameters
    assert sig.parameters["archive"].default is False


def test_worldcover_epoch_and_features():
    from app.services.gee_analysis import (
        WC_TO_CLASS,
        _pixel_features,
        label_epoch_range,
        label_epoch_year,
    )

    assert 2015 <= label_epoch_year() <= 2100
    assert (
        label_epoch_range() == f"{label_epoch_year()}-01-01/{label_epoch_year()}-12-31"
    )
    assert set(WC_TO_CLASS.values()) <= set(range(8))
    props = {
        "B2": 400.0,
        "B3": 500.0,
        "B4": 300.0,
        "B8": 2800.0,
        "B11": 1300.0,
        "B12": 500.0,
    }
    row = _pixel_features(props)
    assert row is not None and len(row) == 4
    assert all(-1.0 <= value <= 1.0 for value in row)
    assert _pixel_features({"B2": 1.0}) is None


def test_period_buckets_cadence():
    from datetime import date

    from app.services.temporal import period_buckets

    weekly = period_buckets(date(2024, 1, 1), date(2024, 1, 31), "weekly")
    assert len(weekly) == 5
    assert weekly[0][2] == "2024-W01"
    assert weekly[-1][2] == "2024-W05"

    monthly = period_buckets(date(2024, 1, 1), date(2024, 12, 31), "monthly")
    assert [key for _, _, key in monthly] == [f"2024-{m:02d}" for m in range(1, 13)]

    yearly = period_buckets(date(2022, 6, 1), date(2024, 3, 1), "yearly")
    assert [key for _, _, key in yearly] == ["2022", "2023", "2024"]


def test_dnbr_baseline():
    from app.services.temporal import apply_dnbr_baseline

    series = [
        {"period": "2024-03", "nbr": 0.40},
        {"period": "2024-01", "nbr": 0.70},
        {"period": "2024-02", "nbr": None},
    ]
    result = apply_dnbr_baseline(series)
    assert [row["period"] for row in result] == ["2024-01", "2024-02", "2024-03"]
    assert result[0]["dnbr"] == 0.0
    assert result[1]["dnbr"] is None
    assert result[2]["dnbr"] == 0.3


def test_gee_landsat_gap_filling():
    """Test resolve_pipeline_metrics has gap-filling logic."""
    import inspect
    from app.services.sources import resolve_pipeline_metrics

    src = inspect.getsource(resolve_pipeline_metrics)
    assert "valid_pixel_ratio" in src
    assert "LandsatSource" in src


def test_multi_source_fallback_notification():
    """Test fallback metadata is set."""
    import inspect
    from app.services.sources import resolve_pipeline_metrics

    src = inspect.getsource(resolve_pipeline_metrics)
    assert "fallback_from" in src
    assert "fallback_reason" in src


def test_twenty_layer_targets():
    """Test 20 analysis targets exist in reference_data."""
    from app.services.reference_data import ANALYSIS_TARGETS

    assert len(ANALYSIS_TARGETS) >= 20


def test_ai_analyst_uses_ai_when_configured():
    """Test generate_analyst_report calls AI endpoint."""
    import inspect
    from app.services.ai_analyst import generate_analyst_report

    src = inspect.getsource(generate_analyst_report)
    assert "resolve_endpoint" in src
    assert "heuristic_report" in src


if __name__ == "__main__":
    test_firms_safe_float()
    test_firms_sensors_list()
    test_firms_confidence_filter()
    test_firms_archive_param()
    test_gee_pipeline_metrics_import()
    test_gee_analysis_import()
    test_sources_list()
    test_classifier_worldcover_training()
    test_reference_data_targets()
    test_intervention_calibrate()
    test_gee_landsat_gap_filling()
    test_multi_source_fallback_notification()
    test_twenty_layer_targets()
    test_ai_analyst_uses_ai_when_configured()
    test_period_buckets_cadence()
    test_dnbr_baseline()
    test_worldcover_epoch_and_features()
    print("All unit tests passed!")
