import asyncio
import io
import zipfile
from unittest.mock import AsyncMock, patch

import numpy as np
import openpyxl
from httpx import AsyncClient, ASGITransport

from app.main import app


_MOCK_ARRAYS = {
    "ndvi": np.full((128, 128), 0.42, dtype=np.float32),
    "dnbr": np.full((128, 128), 0.08, dtype=np.float32),
    "nbr": np.full((128, 128), 0.55, dtype=np.float32),
    "bsi": np.full((128, 128), 0.12, dtype=np.float32),
    "cross_ratio": np.full((128, 128), -6.5, dtype=np.float32),
}

_MOCK_PRE_ARRAYS = {
    "ndvi": np.full((128, 128), 0.78, dtype=np.float32),
    "nbr": np.full((128, 128), 0.65, dtype=np.float32),
    "bsi": np.full((128, 128), -0.28, dtype=np.float32),
    "cross_ratio": np.full((128, 128), -7.2, dtype=np.float32),
}

_MOCK_LIVE = {
    "source": "live_cog",
    "pre_scene_id": "S2A_PRE_MOCK",
    "post_scene_id": "S2A_POST_MOCK",
    "pre_datetime": "2023-08-01",
    "post_datetime": "2024-07-18",
    "valid_pixel_ratio": 0.88,
    "mean_ndvi": 0.42,
    "mean_ndwi": 0.08,
    "mean_mndwi": 0.05,
    "mean_nbr": 0.55,
    "mean_bsi": 0.12,
    "max_dnbr": 0.08,
    "mean_sar_cross_ratio": -6.5,
    "_arrays": _MOCK_ARRAYS,
    "_pre_arrays": _MOCK_PRE_ARRAYS,
}


async def test_end_to_end_pipeline():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        geojson_polygon = {
            "type": "Polygon",
            "coordinates": [
                [
                    [102.10, 0.45],
                    [102.40, 0.45],
                    [102.40, 0.65],
                    [102.10, 0.65],
                    [102.10, 0.45],
                ]
            ],
        }

        payload = {
            "aoi": geojson_polygon,
            "target": "forest_to_bare",
            "pre_date_range": "2023-06-01/2023-12-31",
            "post_date_range": "2024-01-01/2024-12-31",
            "max_cloud_cover": 20.0,
        }

        mock_dem = np.linspace(5.0, 35.0, 64 * 64, dtype=np.float32).reshape(64, 64)
        with (
            patch(
                "app.services.cog.fetch_live_pipeline_metrics",
                new=AsyncMock(return_value=_MOCK_LIVE),
            ),
            patch(
                "app.services.cog.fetch_live_dem",
                new=AsyncMock(return_value=mock_dem),
            ),
        ):
            res = await client.post("/api/analysis/run", json=payload)

        assert res.status_code == 200, res.text
        data = res.json()

        run_id = data["run_id"]
        assert run_id.startswith("sentinel_")
        assert data["target"] == "forest_to_bare"
        assert data["area_hectares"] > 0
        metrics = data["spectral_metrics"]
        assert "mean_ndvi" in metrics
        assert metrics["mean_ndvi"] == 0.42
        assert "threat_level" in data["ai_report"]
        assert len(data["land_transitions"]) > 0
        assert data["accuracy"]["overall_accuracy"] > 0.0
        assert len(data["time_series"]) > 0
        assert len(data["class_scatter"]) > 0

        res_get = await client.get(f"/api/analysis/{run_id}")
        assert res_get.status_code == 200
        saved_data = res_get.json()
        assert saved_data["id"] == run_id
        assert saved_data["metrics"]["source"] == "live_cog"
        assert saved_data["metrics"]["valid_pixel_ratio"] == 0.88
        assert saved_data["metrics"]["max_elevation_m"] == 35.0
        assert saved_data["metrics"]["min_elevation_m"] == 5.0

        from app.services.storage import get_analysis_arrays

        persisted_arrays = get_analysis_arrays(run_id)
        assert persisted_arrays is not None
        assert "ndvi" in persisted_arrays
        assert persisted_arrays["ndvi"].shape == (128, 128)

        res_overlay = await client.get(f"/api/analysis/{run_id}/overlay.png")
        assert res_overlay.status_code == 200
        assert res_overlay.headers["content-type"] == "image/png"
        assert res_overlay.content.startswith(b"\x89PNG")

        res_export = await client.get(f"/api/analysis/{run_id}/export")
        assert res_export.status_code == 200
        assert res_export.headers["content-type"] == "application/zip"

        zip_bytes = io.BytesIO(res_export.content)
        with zipfile.ZipFile(zip_bytes, "r") as zf:
            file_list = zf.namelist()
            assert any(f.endswith("_boundary.geojson") for f in file_list)
            assert any(f.endswith("_summary.json") for f in file_list)
            assert any(f.endswith("_report.xlsx") for f in file_list)
            assert any(f.endswith("_preview.svg") for f in file_list)
            assert any(f.endswith("_raster.tif") for f in file_list)
            assert any(f.endswith("_project.qgs") for f in file_list)
            assert any(f.endswith("_boundary.gpkg") for f in file_list)
            assert any(f.endswith("_report.md") for f in file_list)
            assert any(f.endswith("_transitions.csv") for f in file_list)

            gpkg_bytes = zf.read([f for f in file_list if f.endswith(".gpkg")][0])
            assert gpkg_bytes.startswith(b"SQLite format 3\x00")

            xlsx_name = [f for f in file_list if f.endswith(".xlsx")][0]
            wb = openpyxl.load_workbook(io.BytesIO(zf.read(xlsx_name)))
            assert "Executive Summary" in wb.sheetnames
            assert "Telemetry & Indices" in wb.sheetnames
            assert "Land Transitions" in wb.sheetnames
            assert "Model Accuracy" in wb.sheetnames

            tif_bytes = zf.read([f for f in file_list if f.endswith(".tif")][0])
            assert tif_bytes.startswith(b"II*\x00")

            qgs_content = zf.read(
                [f for f in file_list if f.endswith(".qgs")][0]
            ).decode()
            assert "<qgis" in qgs_content
            assert "spectral_raster_layer" in qgs_content

        res_iv = await client.get(
            f"/api/insights/{run_id}/intervention?dams_per_100ha=4"
        )
        assert res_iv.status_code == 200
        iv = res_iv.json()
        assert iv["wtd_after_m"] >= iv["wtd_before_m"]
        assert "emission_reduction_tco2e_year" in iv

        res_fire = await client.post(
            "/api/insights/fires", json={"bbox": [102.0, 0.2, 103.0, 0.8]}
        )
        assert res_fire.status_code in (200, 502, 503)

        res_history = await client.get("/api/analysis/history/list")
        assert res_history.status_code == 200
        history_list = res_history.json()
        assert any(item["id"] == run_id for item in history_list)


async def test_fallback_to_simulation():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        geojson_polygon = {
            "type": "Polygon",
            "coordinates": [
                [
                    [102.10, 0.45],
                    [102.40, 0.45],
                    [102.40, 0.65],
                    [102.10, 0.65],
                    [102.10, 0.45],
                ]
            ],
        }
        payload = {
            "aoi": geojson_polygon,
            "target": "wildfire_dnbr",
            "pre_date_range": "2023-06-01/2023-12-31",
            "post_date_range": "2024-01-01/2024-12-31",
        }

        with (
            patch(
                "app.services.cog.fetch_live_pipeline_metrics",
                new=AsyncMock(side_effect=LookupError("no scene")),
            ),
            patch(
                "app.services.cog.fetch_live_dem",
                new=AsyncMock(return_value=None),
            ),
        ):
            res = await client.post("/api/analysis/run", json=payload)

        assert res.status_code == 200
        data = res.json()
        assert data["spectral_metrics"]["mean_ndvi"] != 0.42
        assert data["run_id"].startswith("sentinel_")


if __name__ == "__main__":
    asyncio.run(test_end_to_end_pipeline())
    asyncio.run(test_fallback_to_simulation())
    print("All pipeline tests passed.")
