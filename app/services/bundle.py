import io
import json
import zipfile
from typing import Any

import numpy as np

from app.services.exporter import (
    generate_excel_report,
    generate_svg_preview,
    generate_qgis_project_xml,
)
from app.services.geotiff import generate_geotiff_raster


def _csv_rows(headers: list[str], rows: list[list[Any]]) -> str:
    lines = [",".join(headers)]
    for row in rows:
        lines.append(",".join("" if value is None else str(value) for value in row))
    return "\n".join(lines) + "\n"


def _markdown_report(run_data: dict[str, Any]) -> str:
    ai_report = run_data.get("ai_report", {})
    metrics = run_data.get("metrics", {})
    accuracy = run_data.get("accuracy") or {}
    lines = [
        f"# Peatlands Sentinel - {run_data.get('id', 'run')}",
        "",
        f"- Target: {run_data.get('target')}",
        f"- Area: {run_data.get('area_hectares')} Ha",
        f"- Threat: {ai_report.get('threat_level')}",
        f"- Moisture: {ai_report.get('peat_moisture_status')}",
        f"- Source: {metrics.get('source', 'simulation')}",
        "",
        "## Spectral metrics",
        "",
    ]
    for key in (
        "mean_ndvi",
        "mean_ndwi",
        "mean_ndmi",
        "mean_nbr",
        "mean_bsi",
        "max_dnbr",
        "mean_sar_cross_ratio",
        "water_table_depth_cm",
        "drainage_intensity_pct",
        "canal_density_km_km2",
    ):
        if key in metrics:
            lines.append(f"- {key}: {metrics[key]}")
    if accuracy:
        lines.extend(
            [
                "",
                "## Model accuracy",
                "",
                f"- Overall accuracy: {accuracy.get('overall_accuracy')}",
                f"- Kappa: {accuracy.get('kappa')}",
                f"- Samples: {accuracy.get('samples')}",
            ]
        )
    lines.extend(
        ["", "## Narrative", "", ai_report.get("classification_reasoning", ""), ""]
    )
    return "\n".join(lines)


def create_export_zip_package(
    run_data: dict[str, Any],
    raster_values: "np.ndarray | None" = None,
    bbox: list[float] | None = None,
    arrays: dict[str, Any] | None = None,
) -> io.BytesIO:
    import numpy as np

    from app.services.charts import (
        render_accuracy_chart_svg,
        render_line_chart_svg,
        render_transition_chart_svg,
    )
    from app.services.gpkg import generate_geo_package_bytes
    from app.services.renderer import render_index_png

    zip_buffer = io.BytesIO()
    run_id = run_data.get("id", "run")
    geometry = run_data.get("geojson", {}).get("geometry", {})
    bbox = bbox or run_data.get("geojson", {}).get("bbox", [0, 0, 1, 1])

    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        zip_file.writestr(
            f"{run_id}_boundary.geojson",
            json.dumps(run_data.get("geojson", {}), indent=2),
        )
        zip_file.writestr(f"{run_id}_summary.json", json.dumps(run_data, indent=2))
        zip_file.writestr(
            f"{run_id}_report.xlsx", generate_excel_report(run_data).getvalue()
        )
        zip_file.writestr(f"{run_id}_report.md", _markdown_report(run_data))

        transitions = run_data.get("transitions", [])
        zip_file.writestr(
            f"{run_id}_transitions.csv",
            _csv_rows(
                ["from_class", "to_class", "area_hectares", "change_percentage"],
                [
                    [
                        row.get("from_class"),
                        row.get("to_class"),
                        row.get("area_hectares"),
                        row.get("change_percentage"),
                    ]
                    for row in transitions
                ],
            ),
        )
        series = run_data.get("time_series", [])
        if series:
            zip_file.writestr(
                f"{run_id}_timeseries.csv",
                _csv_rows(
                    ["period", "ndvi", "ndwi", "ndmi"],
                    [
                        [
                            row.get("period"),
                            row.get("ndvi"),
                            row.get("ndwi"),
                            row.get("ndmi"),
                        ]
                        for row in series
                    ],
                ),
            )
            zip_file.writestr(f"{run_id}_timeseries.svg", render_line_chart_svg(series))
        zip_file.writestr(
            f"{run_id}_transitions.svg", render_transition_chart_svg(transitions)
        )
        accuracy = run_data.get("accuracy")
        if accuracy:
            zip_file.writestr(
                f"{run_id}_accuracy.svg", render_accuracy_chart_svg(accuracy)
            )

        ai_report = run_data.get("ai_report", {})
        zip_file.writestr(
            f"{run_id}_preview.svg",
            generate_svg_preview(
                target=run_data.get("target", "analysis"),
                threat=ai_report.get("threat_level", "Low"),
                bbox=bbox,
                area_ha=run_data.get("area_hectares", 0.0),
            ),
        )

        zip_file.writestr(
            f"{run_id}_raster.tif",
            generate_geotiff_raster(bbox, values=raster_values),
        )
        zip_file.writestr(
            f"{run_id}_boundary.gpkg",
            generate_geo_package_bytes(
                run_id, geometry, bbox, float(run_data.get("area_hectares", 0.0))
            ),
        )

        for index_name in ("ndvi", "ndwi", "ndmi", "bsi", "dnbr"):
            values = (arrays or {}).get(index_name)
            if isinstance(values, np.ndarray):
                zip_file.writestr(
                    f"{run_id}_{index_name}.png",
                    render_index_png(values, index_name),
                )

        zip_file.writestr(
            f"{run_id}_project.qgs",
            generate_qgis_project_xml(
                run_id, f"{run_id}_boundary.geojson", f"{run_id}_raster.tif"
            ),
        )

    zip_buffer.seek(0)
    return zip_buffer
