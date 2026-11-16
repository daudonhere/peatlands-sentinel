from __future__ import annotations

from app.services import gee
from app.services.temporal import (
    apply_dnbr_baseline,
    parse_iso_interval,
    period_buckets,
)

_SCALE = 100
_MAX_PIXELS = 1e9
_OPTICAL_KEYS = ("ndvi", "ndwi", "mndwi", "ndmi", "nbr", "bsi")
_LST_GAIN = 0.00341802
_LST_OFFSET = 149.0
_KELVIN = 273.15


def _mean(ee, image, geom) -> dict:
    values = image.reduceRegion(
        reducer=ee.Reducer.mean(),
        geometry=geom,
        scale=_SCALE,
        maxPixels=_MAX_PIXELS,
    ).getInfo()
    return values or {}


def _optical_row(ee, geom, start: str, end: str, max_cloud: float) -> dict | None:
    from datetime import date, timedelta

    def _try(s: str, e: str, cloud: float):
        try:
            coll = (
                gee._s2_collection()
                .filterBounds(geom)
                .filterDate(s, e)
                .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", cloud))
            )
            if int(coll.size().getInfo() or 0) == 0:
                return None
            img = coll.median().clip(geom)
            bands = ee.Image.cat(
                [
                    img.normalizedDifference(["B8", "B4"]).rename("ndvi"),
                    img.normalizedDifference(["B3", "B8"]).rename("ndwi"),
                    img.normalizedDifference(["B3", "B11"]).rename("mndwi"),
                    img.normalizedDifference(["B8", "B11"]).rename("ndmi"),
                    img.normalizedDifference(["B8", "B12"]).rename("nbr"),
                    img.expression(
                        "((B11 + B4) - (B8 + B2)) / ((B11 + B4) + (B8 + B2))",
                        {
                            "B11": img.select("B11"),
                            "B4": img.select("B4"),
                            "B8": img.select("B8"),
                            "B2": img.select("B2"),
                        },
                    ).rename("bsi"),
                ]
            )
            values = _mean(ee, bands, geom)
            if values.get("ndvi") is None:
                return None
            return {
                key: round(float(values[key]), 4)
                for key in _OPTICAL_KEYS
                if values.get(key) is not None
            }
        except Exception:
            return None

    # Try the week as-is with increasing cloud tolerance, then expand the window.
    for cloud in (max_cloud, 60.0, 80.0):
        result = _try(start, end, cloud)
        if result is not None:
            return result
    try:
        s = (date.fromisoformat(start) - timedelta(days=3)).isoformat()
        e = (date.fromisoformat(end) + timedelta(days=3)).isoformat()
        for cloud in (60.0, 80.0):
            result = _try(s, e, cloud)
            if result is not None:
                return result
    except ValueError:
        pass
    return None


def _sar_row(ee, geom, start: str, end: str) -> float | None:
    try:
        coll = (
            gee._s1_collection()
            .filterBounds(geom)
            .filterDate(start, end)
            .filter(ee.Filter.eq("instrumentMode", "IW"))
        )
        img = coll.select(["VV", "VH"]).median()
        ratio = img.select("VH").subtract(img.select("VV")).rename("sar")
        value = _mean(ee, ratio, geom).get("sar")
        return None if value is None else round(float(value), 2)
    except Exception:
        return None


def _lst_row(ee, geom, start: str, end: str, max_cloud: float) -> float | None:
    try:
        coll = (
            gee._landsat_collection()
            .filterBounds(geom)
            .filterDate(start, end)
            .filter(ee.Filter.lt("CLOUD_COVER", max_cloud))
        )
        celsius = (
            coll.select("ST_B10")
            .median()
            .multiply(_LST_GAIN)
            .add(_LST_OFFSET)
            .subtract(_KELVIN)
            .rename("lst")
        )
        value = _mean(ee, celsius, geom).get("lst")
        return None if value is None else round(float(value), 2)
    except Exception:
        return None


async def gee_time_series(
    bbox: list[float],
    date_range: str,
    max_cloud: float = 40.0,
    granularity: str = "monthly",
) -> list[dict]:
    ee = gee._require_available()
    geom = gee._bbox_geom(bbox)
    start_d, end_d = parse_iso_interval(date_range)

    rows: list[dict] = []
    for start, end, key in period_buckets(start_d, end_d, granularity):
        window_start = start.isoformat()
        window_end = end.isoformat()
        optical = _optical_row(ee, geom, window_start, window_end, max_cloud)
        if optical is None:
            continue
        rows.append(
            {
                "period": key,
                **optical,
                "sar": _sar_row(ee, geom, window_start, window_end),
                "lst": _lst_row(ee, geom, window_start, window_end, max_cloud),
            }
        )
    return apply_dnbr_baseline(rows)
