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


def generate_spectral_overlay_png(
    target: str,
    metrics: dict[str, float],
    width: int = 128,
    height: int = 128,
    period: str = "post",
) -> bytes:
    y, x = np.mgrid[0:height, 0:width]
    cx, cy = width / 2.0, height / 2.0
    dist = np.sqrt((x - cx) ** 2 + (y - cy) ** 2) / np.sqrt(cx**2 + cy**2)
    tex = np.sin(x * 0.15) * np.cos(y * 0.15) * 0.1
    val = np.clip(1.0 - dist + tex, 0.0, 1.0)

    a = np.full((height, width), 185, dtype=np.uint8)
    a[dist > 0.95] = 0

    if period == "pre":
        r = ((1.0 - val) * 45).astype(np.uint8)
        g = (val * 185 + 55).astype(np.uint8)
        b = ((1.0 - val) * 60 + 20).astype(np.uint8)
    elif target in ("wildfire_dnbr", "forest_to_bare", "deforest_expansion"):
        r = (val * 230 + 20).astype(np.uint8)
        g = ((1.0 - val) * 160 + 30).astype(np.uint8)
        b = np.where(val > 0.7, 30, 80).astype(np.uint8)
    elif target in ("peat_moisture", "water_dynamics"):
        r = ((1.0 - val) * 80).astype(np.uint8)
        g = (val * 180 + 40).astype(np.uint8)
        b = (val * 220 + 35).astype(np.uint8)
    elif target in ("topography_slope", "reclamation", "bare_to_veg"):
        r = (val * 190 + 40).astype(np.uint8)
        g = (val * 140 + 60).astype(np.uint8)
        b = ((1.0 - val) * 100).astype(np.uint8)
    else:
        r = ((1.0 - val) * 200).astype(np.uint8)
        g = (val * 200).astype(np.uint8)
        b = np.full((height, width), 60, dtype=np.uint8)

    rgba = np.dstack([r, g, b, a]).tobytes()
    return _encode_png(width, height, rgba)
