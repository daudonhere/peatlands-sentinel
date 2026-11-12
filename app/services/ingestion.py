from typing import Any
import httpx

from app.config import get_settings


async def search_stac_items(
    bbox: list[float],
    datetime_range: str,
    collections: list[str],
    max_items: int = 5,
    query: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    settings = get_settings()
    payload: dict[str, Any] = {
        "bbox": bbox,
        "datetime": datetime_range,
        "collections": collections,
        "limit": max_items,
    }
    if query:
        payload["query"] = query

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(f"{settings.stac_api_url}/search", json=payload)
        resp.raise_for_status()
        data = resp.json()
        return data.get("features", [])


async def search_dem_scenes(bbox: list[float]) -> list[dict[str, Any]]:
    return await search_stac_items(
        bbox=bbox,
        datetime_range="2020-01-01/2024-12-31",
        collections=["cop-dem-glo-30"],
        max_items=2,
    )
