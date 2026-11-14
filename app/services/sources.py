from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any, Protocol

from app.config import get_settings
from app.services import cog, gee, observations


@dataclass
class SourceResult:
    source: str
    metrics: dict[str, Any]
    pre_arrays: dict[str, Any] | None = None
    post_arrays: dict[str, Any] | None = None
    scene_meta: dict[str, Any] = field(default_factory=dict)


class SatelliteDataSource(Protocol):
    name: str

    async def pipeline_metrics(
        self,
        bbox: list[float],
        pre_date_range: str,
        post_date_range: str,
        max_cloud: float,
    ) -> SourceResult: ...

    async def scene_observations(
        self,
        bbox: list[float],
        date_range: str,
        max_cloud: float,
        max_items: int = 8,
    ) -> list[dict]: ...


class PlanetaryComputerSource:
    name = "planetary_computer"

    async def pipeline_metrics(
        self,
        bbox: list[float],
        pre_date_range: str,
        post_date_range: str,
        max_cloud: float,
    ) -> SourceResult:
        live = await cog.fetch_live_pipeline_metrics(
            bbox=bbox,
            pre_date_range=pre_date_range,
            post_date_range=post_date_range,
            max_cloud=max_cloud,
            size=32,
        )
        meta = {
            k: v
            for k, v in live.items()
            if not k.startswith("_")
            and k
            not in (
                "mean_ndvi",
                "mean_ndwi",
                "mean_ndmi",
                "mean_mndwi",
                "mean_nbr",
                "mean_bsi",
                "max_dnbr",
                "mean_sar_cross_ratio",
            )
        }
        metrics = {k: v for k, v in live.items() if not k.startswith("_")}
        return SourceResult(
            source=self.name,
            metrics=metrics,
            pre_arrays=live.get("_pre_arrays"),
            post_arrays=live.get("_arrays"),
            scene_meta=meta,
        )

    async def scene_observations(
        self,
        bbox: list[float],
        date_range: str,
        max_cloud: float,
        max_items: int = 8,
    ) -> list[dict]:
        return await observations.fetch_scene_observations(
            bbox=bbox,
            date_range=date_range,
            max_cloud=max_cloud,
            max_items=max_items,
        )


class EarthEngineSource:
    name = "gee"

    async def pipeline_metrics(
        self,
        bbox: list[float],
        pre_date_range: str,
        post_date_range: str,
        max_cloud: float,
    ) -> SourceResult:
        if not gee.is_available():
            raise LookupError("GEE is not configured or authorized.")
        metrics = await gee.pipeline_metrics(
            bbox, pre_date_range, post_date_range, max_cloud
        )
        meta = {
            k: v
            for k, v in metrics.items()
            if k
            in (
                "pre_scene_id",
                "post_scene_id",
                "pre_datetime",
                "post_datetime",
                "valid_pixel_ratio",
            )
        }
        return SourceResult(
            source=self.name,
            metrics=metrics,
            pre_arrays=metrics.get("_pre_arrays"),
            post_arrays=metrics.get("_arrays"),
            scene_meta=meta,
        )

    async def scene_observations(
        self,
        bbox: list[float],
        date_range: str,
        max_cloud: float,
        max_items: int = 8,
    ) -> list[dict]:
        raise LookupError("GEE scene observations are not supported yet.")


class LandsatSource:
    name = "landsat"

    async def pipeline_metrics(
        self,
        bbox: list[float],
        pre_date_range: str,
        post_date_range: str,
        max_cloud: float,
    ) -> SourceResult:
        if not gee.is_available():
            raise LookupError("GEE is not configured or authorized.")
        metrics = await gee.landsat_pipeline_metrics(
            bbox, pre_date_range, post_date_range, max_cloud
        )
        meta = {
            k: v
            for k, v in metrics.items()
            if k
            in (
                "pre_scene_id",
                "post_scene_id",
                "pre_datetime",
                "post_datetime",
                "valid_pixel_ratio",
                "mean_lst",
            )
        }
        return SourceResult(
            source=self.name,
            metrics=metrics,
            pre_arrays=metrics.get("_pre_arrays"),
            post_arrays=metrics.get("_arrays"),
            scene_meta=meta,
        )

    async def scene_observations(
        self,
        bbox: list[float],
        date_range: str,
        max_cloud: float,
        max_items: int = 8,
    ) -> list[dict]:
        raise LookupError("Landsat scene observations are not supported yet.")


_SOURCES = {
    "planetary_computer": PlanetaryComputerSource,
    "gee": EarthEngineSource,
    "landsat": LandsatSource,
}


def available_sources() -> list[dict[str, Any]]:
    return [
        {"name": name, "available": gee.is_available() if name == "gee" else True}
        for name in _SOURCES
    ]


def get_data_source(name: str | None = None) -> SatelliteDataSource:
    settings = get_settings()
    key = (name or settings.data_source or "planetary_computer").lower()
    if key not in _SOURCES:
        raise ValueError(f"Unknown data source '{name}'.")
    return _SOURCES[key]()


async def resolve_pipeline_metrics(
    name: str | None,
    bbox: list[float],
    pre_date_range: str,
    post_date_range: str,
    max_cloud: float,
) -> SourceResult:
    source = get_data_source(name)
    return await source.pipeline_metrics(
        bbox, pre_date_range, post_date_range, max_cloud
    )
