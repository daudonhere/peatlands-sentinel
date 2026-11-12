import csv
import io
import httpx

from app.config import get_settings

FIRMS_URL = "https://firms.modaps.eosdis.nasa.gov/api/area/csv"


async def fetch_active_fires(bbox: list[float], days: int = 3) -> list[dict[str, float | str]]:
    key = get_settings().firms_map_key
    if not key:
        raise PermissionError("FIRMS_MAP_KEY not configured.")

    area = ",".join(str(v) for v in bbox)
    url = f"{FIRMS_URL}/{key}/VIIRS_SNPP_NRT/{area}/{max(1, min(days, 10))}"
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(url)
        resp.raise_for_status()

    rows = csv.DictReader(io.StringIO(resp.text))
    return [
        {
            "latitude": float(r["latitude"]),
            "longitude": float(r["longitude"]),
            "confidence": r.get("confidence", ""),
            "frp": float(r.get("frp") or 0.0),
            "acq_date": r.get("acq_date", ""),
        }
        for r in rows
        if r.get("latitude")
    ]
