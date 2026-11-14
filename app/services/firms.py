import csv
import io
import httpx

from app.config import get_settings


def _safe_float(value: object) -> float:
    try:
        return float(value) if value not in (None, "") else 0.0
    except (TypeError, ValueError):
        return 0.0


FIRMS_URL = "https://firms.modaps.eosdis.nasa.gov/api/area/csv"
FIRMS_SENSORS = ["VIIRS_SNPP_NRT", "VIIRS_NOAA20_NRT", "MODIS_NRT"]


async def fetch_active_fires(
    bbox: list[float], days: int = 3
) -> list[dict[str, float | str]]:
    key = get_settings().firms_map_key
    if not key:
        raise PermissionError("FIRMS_MAP_KEY not configured.")

    days = max(1, min(days, 5))
    area = ",".join(str(v) for v in bbox)
    all_fires: list[dict[str, float | str]] = []
    seen: set[tuple[str, str]] = set()

    async with httpx.AsyncClient(timeout=30.0) as client:
        for sensor in FIRMS_SENSORS:
            url = f"{FIRMS_URL}/{key}/{sensor}/{area}/{days}"
            try:
                resp = await client.get(url)
                resp.raise_for_status()
                rows = csv.DictReader(io.StringIO(resp.text))
                for r in rows:
                    if not r.get("latitude"):
                        continue
                    lat = r["latitude"]
                    lon = r["longitude"]
                    dedup_key = (lat, lon)
                    if dedup_key in seen:
                        continue
                    seen.add(dedup_key)
                    all_fires.append(
                        {
                            "latitude": float(lat),
                            "longitude": float(lon),
                            "confidence": r.get("confidence", ""),
                            "frp": _safe_float(r.get("frp")),
                            "acq_date": r.get("acq_date", ""),
                            "sensor": sensor,
                        }
                    )
            except Exception:
                continue

    return all_fires
