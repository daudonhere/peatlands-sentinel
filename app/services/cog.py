import numpy as np
import planetary_computer
import rasterio
from rasterio.warp import transform_bounds
from rasterio.windows import from_bounds

from app.services.ingestion import search_stac_items
from app.services.raster import calculate_ndvi

SCL_INVALID = (0, 1, 3, 8, 9, 10)


def _read_band(href: str, bbox: list[float], size: int) -> np.ndarray:
    with rasterio.open(href) as ds:
        bounds = transform_bounds("EPSG:4326", ds.crs, *bbox)
        window = from_bounds(*bounds, transform=ds.transform)
        return ds.read(1, window=window, out_shape=(size, size), boundless=True, fill_value=0)


def read_live_ndvi(item: dict, bbox: list[float], size: int = 64) -> dict[str, float | str]:
    signed = planetary_computer.sign(item)
    red = _read_band(signed["assets"]["B04"]["href"], bbox, size).astype(np.float32)
    nir = _read_band(signed["assets"]["B08"]["href"], bbox, size).astype(np.float32)
    scl = _read_band(signed["assets"]["SCL"]["href"], bbox, size)

    valid = ~np.isin(scl, SCL_INVALID) & (red + nir > 0)
    if not valid.any():
        raise ValueError("No cloud-free pixels in AOI for this scene.")

    ndvi = calculate_ndvi(nir / 10000.0, red / 10000.0)
    return {
        "scene_id": item["id"],
        "datetime": item["properties"].get("datetime", ""),
        "mean_ndvi": round(float(np.mean(ndvi[valid])), 3),
        "valid_pixel_ratio": round(float(valid.mean()), 3),
    }


async def live_ndvi_for_aoi(bbox: list[float], datetime_range: str, max_cloud: float = 30.0) -> dict:
    items = await search_stac_items(
        bbox=bbox,
        datetime_range=datetime_range,
        collections=["sentinel-2-l2a"],
        max_items=1,
        query={"eo:cloud_cover": {"lt": max_cloud}},
    )
    if not items:
        raise LookupError("No Sentinel-2 scene found for AOI and date range.")
    return read_live_ndvi(items[0], bbox)
