import asyncio
import io
import zipfile
from httpx import AsyncClient, ASGITransport
import openpyxl

from app.main import app


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

        res = await client.post("/api/analysis/run", json=payload)
        assert res.status_code == 200, res.text
        data = res.json()

        run_id = data["run_id"]
        assert run_id.startswith("sentinel_")
        assert data["target"] == "forest_to_bare"
        assert data["area_hectares"] > 0
        assert "mean_ndvi" in data["spectral_metrics"]
        assert "threat_level" in data["ai_report"]
        assert len(data["land_transitions"]) > 0

        res_get = await client.get(f"/api/analysis/{run_id}")
        assert res_get.status_code == 200
        saved_data = res_get.json()
        assert saved_data["id"] == run_id

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
            assert any(f.endswith("_project.qgs") for f in file_list)
            assert any(f.endswith("_raster.tif") for f in file_list)

            xlsx_filename = [f for f in file_list if f.endswith(".xlsx")][0]
            wb = openpyxl.load_workbook(io.BytesIO(zf.read(xlsx_filename)))
            assert "Executive Summary" in wb.sheetnames
            assert "Telemetry & Indices" in wb.sheetnames
            assert "Land Transitions" in wb.sheetnames

            qgs_filename = [f for f in file_list if f.endswith(".qgs")][0]
            qgs_content = zf.read(qgs_filename).decode("utf-8")
            assert "<qgis" in qgs_content
            assert "AOI Boundary" in qgs_content

        res_overlay = await client.get(f"/api/analysis/{run_id}/overlay.png")
        assert res_overlay.status_code == 200
        assert res_overlay.headers["content-type"] == "image/png"
        assert res_overlay.content.startswith(b"\x89PNG")

        res_iv = await client.get(f"/api/insights/{run_id}/intervention?dams_per_100ha=4")
        assert res_iv.status_code == 200
        assert res_iv.json()["wtd_after_m"] >= res_iv.json()["wtd_before_m"]

        res_fire = await client.post("/api/insights/fires", json={"bbox": [102.0, 0.2, 103.0, 0.8]})
        assert res_fire.status_code in (200, 502, 503)

        res_history = await client.get("/api/analysis/history/list")
        assert res_history.status_code == 200
        history_list = res_history.json()
        assert any(item["id"] == run_id for item in history_list)


if __name__ == "__main__":
    asyncio.run(test_end_to_end_pipeline())
