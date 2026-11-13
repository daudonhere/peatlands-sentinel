from typing import Any, Literal
from pydantic import BaseModel, Field, field_validator


class GeoJSONGeometry(BaseModel):
    type: Literal["Polygon", "MultiPolygon"]
    coordinates: list[Any]

    @field_validator("coordinates")
    @classmethod
    def validate_coordinates(cls, v: list[Any]) -> list[Any]:
        if not v or not isinstance(v, list):
            raise ValueError("Coordinates must be a non-empty list.")
        return v


class GeoJSONFeature(BaseModel):
    type: Literal["Feature"] = "Feature"
    geometry: GeoJSONGeometry
    properties: dict[str, Any] = Field(default_factory=dict)


def _line_to_polygon(value: dict[str, Any]) -> dict[str, Any]:
    if value.get("type") == "LineString":
        coords = [list(point) for point in value.get("coordinates", [])]
        if len(coords) >= 3:
            if coords[0] != coords[-1]:
                coords.append(list(coords[0]))
            return {"type": "Polygon", "coordinates": [coords]}
    return value


class AnalysisPipelineRequest(BaseModel):
    aoi: GeoJSONFeature | GeoJSONGeometry

    @field_validator("aoi", mode="before")
    @classmethod
    def normalize_aoi(cls, value: Any) -> Any:
        if isinstance(value, dict):
            if value.get("type") == "FeatureCollection":
                for feature in value.get("features", []):
                    if isinstance(feature, dict) and feature.get("geometry"):
                        value = feature
                        break
            if isinstance(value, dict) and value.get("type") == "Feature":
                value = value.get("geometry", value)
            if isinstance(value, dict):
                value = _line_to_polygon(value)
        return value

    target: str = Field(
        default="peat_moisture",
        description="Target analysis type (e.g. peat_moisture, forest_to_bare, wildfire_dnbr)",
    )
    pre_date_range: str = Field(
        default="2023-06-01/2023-12-31",
        description="Baseline acquisition window (ISO 8601 interval)",
    )
    post_date_range: str = Field(
        default="2024-01-01/2024-12-31",
        description="Monitoring acquisition window (ISO 8601 interval)",
    )
    max_cloud_cover: float = Field(default=25.0, ge=0.0, le=100.0)
    data_source: Literal["planetary_computer", "gee"] | None = None
    granularity: Literal["weekly", "monthly", "yearly"] = "monthly"
    composite_season: str | None = Field(
        default=None,
        description="Optional seasonal window in MM-DD/MM-DD form",
    )


class SpectralSummary(BaseModel):
    mean_ndvi: float
    mean_ndwi: float
    mean_ndmi: float = 0.0
    mean_nbr: float
    mean_bsi: float
    max_dnbr: float
    mean_sar_cross_ratio: float


class LandTransition(BaseModel):
    from_class: str
    to_class: str
    area_hectares: float
    change_percentage: float


class ModelAccuracy(BaseModel):
    overall_accuracy: float
    kappa: float
    confusion_matrix: list[list[int]]
    class_names: list[str]
    samples: int


class TimeSeriesPoint(BaseModel):
    period: str
    ndvi: float
    ndwi: float
    ndmi: float


class ClassScatterPoint(BaseModel):
    land_class: str
    class_code: int
    pre_ndvi: float
    post_ndvi: float
    pre_ndmi: float
    post_ndmi: float
    pre_bsi: float
    post_bsi: float


class AIAnalystReport(BaseModel):
    threat_level: str
    peat_moisture_status: str
    fire_risk_summary: str
    classification_reasoning: str
    recommended_actions: list[str]


class AnalysisPipelineResponse(BaseModel):
    run_id: str
    created_at: str
    target: str
    area_hectares: float
    spectral_metrics: SpectralSummary
    land_transitions: list[LandTransition]
    ai_report: AIAnalystReport
    telemetry: dict[str, Any] = Field(default_factory=dict)
    accuracy: ModelAccuracy | None = None
    time_series: list[TimeSeriesPoint] = Field(default_factory=list)
    class_scatter: list[ClassScatterPoint] = Field(default_factory=list)
    data_source: str = "planetary_computer"
    export_available: bool = True
    geojson: dict[str, Any] | None = None
