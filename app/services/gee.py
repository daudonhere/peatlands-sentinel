from __future__ import annotations

from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.config import get_settings


class GeeUnavailable(RuntimeError):
    pass


def _import_ee():
    try:
        import ee
    except ImportError as exc:
        raise GeeUnavailable(
            "earthengine-api is not installed. Add the 'gee' extra to enable it."
        ) from exc
    return ee


@lru_cache(maxsize=1)
def _initialize() -> bool:
    settings = get_settings()
    if not settings.gee_project:
        return False
    ee = _import_ee()
    credentials = None
    if settings.gee_service_account:
        credentials = ee.ServiceAccountCredentials(settings.gee_service_account)
    elif settings.gee_private_key_file and Path(settings.gee_private_key_file).exists():
        credentials = ee.ServiceAccountCredentials.from_json_keyfile(
            str(settings.gee_private_key_file), project_id=settings.gee_project
        )
    try:
        ee.Initialize(credentials, project=settings.gee_project)
        return True
    except Exception:
        return False


def is_available() -> bool:
    settings = get_settings()
    if not settings.gee_ready:
        return False
    try:
        return _initialize()
    except GeeUnavailable:
        return False


def _require_available():
    ee = _import_ee()
    if not is_available():
        raise GeeUnavailable("GEE is not configured or authorized.")
    return ee


def _split_interval(date_range: str) -> tuple[str, str]:
    parts = date_range.split("/")
    if len(parts) != 2:
        raise ValueError("GEE date range must be start/end.")
    return parts[0].strip(), parts[1].strip()


def _bbox_geom(bbox: list[float]) -> Any:
    import ee

    min_lon, min_lat, max_lon, max_lat = bbox
    return ee.Geometry.Rectangle([min_lon, min_lat, max_lon, max_lat], None, True)


def _s2_collection() -> Any:
    import ee

    return ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")


def _s1_collection() -> Any:
    import ee

    return ee.ImageCollection("COPERNICUS/S1_GRD")


def _landsat_collection() -> Any:
    import ee

    return ee.ImageCollection("LANDSAT/LC08/C02/T1_SR")


def _worldcover_image() -> Any:
    import ee

    return (
        ee.ImageCollection(get_settings().gee_worldcover_collection)
        .first()
        .select("landcover", ["class"])
        .int16()
    )



def collection_catalog() -> list[str]:
    return [
        "COPERNICUS/S2_SR_HARMONIZED",
        "COPERNICUS/S1_GRD",
        "LANDSAT/LC08/C02/T1_SR",
        "ESA/WorldCover/v200/2021",
    ]
