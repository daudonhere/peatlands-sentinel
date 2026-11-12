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
        "deforest_expansion",
        "forest_to_mining",
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
        arr_resized = arr
        if arr.shape != (height, width):
            zoom = np.array([height / arr.shape[0], width / arr.shape[1]])
            from scipy.ndimage import zoom as nd_zoom

            arr_resized = nd_zoom(arr, zoom, order=1)
        nan_mask = np.isnan(arr_resized)
        valid_data = arr_resized[~nan_mask] if (~nan_mask).any() else np.array([0.0])
        vmin, vmax = (
            float(np.percentile(valid_data, 5)),
            float(np.percentile(valid_data, 95)),
        )
        norm = _normalize(np.nan_to_num(arr_resized, nan=vmin), vmin, vmax)
        if target in (
            "wildfire_dnbr",
            "forest_to_bare",
            "deforest_expansion",
            "forest_to_mining",
        ):
            r, g, b = _colormap_fire(norm)
        elif target in ("peat_moisture", "water_dynamics"):
            r, g, b = _colormap_water(norm)
        else:
            r, g, b = _colormap_rdylgn(norm)
        a = np.where(nan_mask, 0, 185).astype(np.uint8)
    else:
        grad = _fallback_gradient(height, width, target, period)
        if target in (
            "wildfire_dnbr",
            "forest_to_bare",
            "deforest_expansion",
            "forest_to_mining",
        ):
            r, g, b = _colormap_fire(grad)
        elif target in ("peat_moisture", "water_dynamics"):
            r, g, b = _colormap_water(grad)
        else:
            r, g, b = _colormap_rdylgn(grad)
        a = np.full((height, width), 185, dtype=np.uint8)

    rgba = np.dstack([r, g, b, a]).tobytes()
    return _encode_png(width, height, rgba)
