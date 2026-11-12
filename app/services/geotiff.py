import struct
import numpy as np


def generate_geotiff_raster(
    bbox: list[float],
    values: np.ndarray | None = None,
    width: int = 128,
    height: int = 128,
) -> bytes:
    min_lon, min_lat, max_lon, max_lat = bbox
    pixel_scale_x = abs(max_lon - min_lon) / float(width)
    pixel_scale_y = abs(max_lat - min_lat) / float(height)

    if values is not None and values.ndim == 2:
        from scipy.ndimage import zoom as nd_zoom

        if values.shape != (height, width):
            scale = (height / values.shape[0], width / values.shape[1])
            values = nd_zoom(values, scale, order=1)
        finite = values[np.isfinite(values)]
        vmin = float(finite.min()) if finite.size else 0.0
        vmax = float(finite.max()) if finite.size else 1.0
        span = vmax - vmin if vmax != vmin else 1.0
        scaled = np.clip((np.nan_to_num(values, nan=vmin) - vmin) / span * 255, 0, 255)
        raster = scaled.astype(np.uint8).tobytes()
    else:
        y, x = np.mgrid[0:height, 0:width]
        cx, cy = width / 2.0, height / 2.0
        dist = np.sqrt((x - cx) ** 2 + (y - cy) ** 2) / np.sqrt(cx**2 + cy**2)
        raster = (np.clip(1.0 - dist, 0.0, 1.0) * 255).astype(np.uint8).tobytes()

    geokeys = struct.pack(
        "<4H 4H 4H 4H",
        1,
        1,
        0,
        3,
        1024,
        0,
        1,
        2,
        1025,
        0,
        1,
        1,
        2048,
        0,
        1,
        4326,
    )

    pixel_scale = struct.pack("<3d", pixel_scale_x, pixel_scale_y, 0.0)
    tiepoints = struct.pack("<6d", 0.0, 0.0, 0.0, min_lon, max_lat, 0.0)

    header = b"II\x2a\x00"
    raster_offset = 8
    scale_offset = raster_offset + len(raster)
    tiepoint_offset = scale_offset + len(pixel_scale)
    geokey_offset = tiepoint_offset + len(tiepoints)
    ifd_offset = geokey_offset + len(geokeys)

    full_header = header + struct.pack("<I", ifd_offset)

    tags = [
        (256, 4, 1, width),
        (257, 4, 1, height),
        (258, 3, 1, 8),
        (259, 3, 1, 1),
        (262, 3, 1, 1),
        (273, 4, 1, raster_offset),
        (278, 4, 1, height),
        (279, 4, 1, len(raster)),
        (33550, 12, 3, scale_offset),
        (33922, 12, 6, tiepoint_offset),
        (34735, 3, len(geokeys) // 2, geokey_offset),
    ]
    tags.sort(key=lambda t: t[0])

    ifd = struct.pack("<H", len(tags))
    for tag, dtype, count, val in tags:
        if dtype == 3 and count == 1:
            val_bytes = struct.pack("<HH", val, 0)
        elif dtype == 4 and count == 1:
            val_bytes = struct.pack("<I", val)
        else:
            val_bytes = struct.pack("<I", val)
        ifd += struct.pack("<HHI", tag, dtype, count) + val_bytes
    ifd += struct.pack("<I", 0)

    return full_header + raster + pixel_scale + tiepoints + geokeys + ifd
