import struct
import zlib
import numpy as np


def _encode_png(width: int, height: int, rgba_bytes: bytes) -> bytes:
    def chunk(tag: bytes, data: bytes) -> bytes:
        crc = zlib.crc32(tag + data) & 0xFFFFFFFF
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", crc)

    header = b"\x89PNG\r\n\x1a\n"
    ihdr = chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
    raw = b"".join(
        b"\x00" + rgba_bytes[y * width * 4 : (y + 1) * width * 4] for y in range(height)
    )
    idat = chunk(b"IDAT", zlib.compress(raw, level=6))
    iend = chunk(b"IEND", b"")
    return header + ihdr + idat + iend


def _colormap_rdylgn(val: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    t = np.clip(val, 0.0, 1.0)
    r = np.where(t < 0.5, 1.0, 1.0 - (t - 0.5) * 2.0)
    g = np.where(t < 0.5, t * 2.0, 1.0)
    b = np.zeros_like(t)
    return (r * 240).astype(np.uint8), (g * 190).astype(np.uint8), b.astype(np.uint8)


def _colormap_fire(val: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    t = np.clip(val, 0.0, 1.0)
    r = (t * 230 + 20).astype(np.uint8)
    g = ((1.0 - t) * 140 + 20).astype(np.uint8)
    b = np.where(t > 0.6, 20, 80).astype(np.uint8)
    return r, g, b


def _colormap_water(val: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    t = np.clip(val, 0.0, 1.0)
    r = ((1.0 - t) * 60).astype(np.uint8)
    g = (t * 160 + 40).astype(np.uint8)
    b = (t * 220 + 35).astype(np.uint8)
    return r, g, b


def _normalize(arr: np.ndarray, vmin: float, vmax: float) -> np.ndarray:
    span = vmax - vmin
    if span == 0:
        return np.zeros_like(arr)
    return np.clip((arr - vmin) / span, 0.0, 1.0)


def _fallback_gradient(height: int, width: int, target: str, period: str) -> np.ndarray:
    y, x = np.mgrid[0:height, 0:width]
    cx, cy = width / 2.0, height / 2.0
    dist = np.sqrt((x - cx) ** 2 + (y - cy) ** 2) / np.sqrt(cx**2 + cy**2)
    tex = np.sin(x * 0.15) * np.cos(y * 0.15) * 0.1
    val = np.clip(1.0 - dist + tex, 0.0, 1.0).astype(np.float32)
    if period == "pre":
        return val * 0.9
    if target in (
        "wildfire_dnbr",
        "forest_to_bare",
        "forest_to_mining",
        "deforest_expansion",
        "peat_drainage_canal",
        "landslide_susceptibility",
        "ground_deformation",
        "carbon_subsidence",
        "urban_expansion",
        "biodiversity_habitat",
    ):
        return 1.0 - val * 0.7
    if target in ("peat_moisture", "water_dynamics"):
        return val
    return val * 0.6


def generate_spectral_overlay_png(
    target: str,
    metrics: dict,
    width: int = 128,
    height: int = 128,
    period: str = "post",
    arrays: dict | None = None,
) -> bytes:
    if arrays and ("ndvi" in arrays or "pre_ndvi" in arrays):
        if period == "pre" and "pre_ndvi" in arrays:
            arr = arrays["pre_ndvi"]
        elif period == "post" and target == "wildfire_dnbr" and "dnbr" in arrays:
            arr = arrays["dnbr"]
        else:
            arr = arrays.get("ndvi", arrays.get("pre_ndvi"))
        nan_mask_src = np.isnan(arr)
        if arr.shape != (height, width):
            zoom = np.array([height / arr.shape[0], width / arr.shape[1]])
            from scipy.ndimage import zoom as nd_zoom

            arr_resized = nd_zoom(np.nan_to_num(arr, nan=0.0), zoom, order=1)
            nan_mask = nd_zoom(nan_mask_src.astype(np.float32), zoom, order=0) > 0.5
        else:
            arr_resized = arr
            nan_mask = nan_mask_src
        valid_data = (
            arr[np.isfinite(arr)] if np.isfinite(arr).any() else np.array([0.0])
        )
        vmin, vmax = (
            float(np.percentile(valid_data, 5)),
            float(np.percentile(valid_data, 95)),
        )
        norm = _normalize(np.nan_to_num(arr_resized, nan=vmin), vmin, vmax)
        if target in (
            "wildfire_dnbr",
            "forest_to_bare",
            "forest_to_mining",
            "deforest_expansion",
            "peat_drainage_canal",
            "landslide_susceptibility",
            "ground_deformation",
            "carbon_subsidence",
            "urban_expansion",
            "biodiversity_habitat",
        ):
            r, g, b = _colormap_fire(norm)
        elif target in (
            "peat_moisture",
            "water_dynamics",
            "coastal_inundation",
            "seasonal_flooding",
        ):
            r, g, b = _colormap_water(norm)
        else:
            r, g, b = _colormap_rdylgn(norm)
        a = np.where(nan_mask, 0, 185).astype(np.uint8)
    else:
        # No arrays available - return transparent placeholder
        r = np.zeros((height, width), dtype=np.uint8)
        g = np.zeros((height, width), dtype=np.uint8)
        b = np.zeros((height, width), dtype=np.uint8)
        a = np.zeros((height, width), dtype=np.uint8)

    rgba = np.dstack([r, g, b, a]).tobytes()
    return _encode_png(width, height, rgba)


def render_index_png(values: np.ndarray, index: str, size: int = 256) -> bytes:
    from scipy.ndimage import zoom as nd_zoom

    from app.services.charts import colorize_index

    arr = np.asarray(values, dtype=np.float32)
    if arr.ndim != 2:
        arr = np.zeros((size, size), dtype=np.float32)
    if arr.shape != (size, size):
        zoom = np.array([size / arr.shape[0], size / arr.shape[1]])
        arr = nd_zoom(np.nan_to_num(arr, nan=0.0), zoom, order=1)
    r, g, b = colorize_index(arr, index)
    alpha = np.full((size, size), 255, dtype=np.uint8)
    return _encode_png(size, size, np.dstack([r, g, b, alpha]).tobytes())
