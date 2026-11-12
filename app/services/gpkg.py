import sqlite3
import struct
from typing import Any

_GPKG_USER_VERSION = 10300
_EPOCH = "2024-01-01T00:00:00.000Z"


def _wkb_polygon(ring: list[list[float]]) -> bytes:
    points = ring[:-1] if len(ring) > 1 and ring[0] == ring[-1] else ring
    body = struct.pack("<I", 3) + struct.pack("<i", 1) + struct.pack("<i", len(points))
    for lon, lat in points:
        body += struct.pack("<dd", float(lon), float(lat))
    return b"\x01" + body


def _wkb_multipolygon(polygon_rings: list[list[list[float]]]) -> bytes:
    parts = b"".join(_wkb_polygon(ring) for ring in polygon_rings)
    body = struct.pack("<I", 6) + struct.pack("<i", len(polygon_rings)) + parts
    return b"\x01" + body


def _geometry_wkb(geometry: dict[str, Any]) -> bytes:
    coords = geometry.get("coordinates", [])
    if geometry.get("type") == "MultiPolygon":
        polygon_rings = [polygon[0] for polygon in coords if polygon]
        return _wkb_multipolygon(polygon_rings)
    rings = coords if coords else []
    return _wkb_polygon(rings[0] if rings else [])


def _gpkg_header(blob: bytes, bbox: list[float]) -> bytes:
    min_lon, min_lat, max_lon, max_lat = bbox
    envelope = struct.pack(
        "<dddd",
        float(min_lon),
        float(min_lat),
        float(max_lon),
        float(max_lat),
    )
    return b"GP" + bytes([0, 3]) + struct.pack("<i", 4326) + envelope + blob


def generate_geo_package_bytes(
    run_id: str, geometry: dict[str, Any], bbox: list[float], area_ha: float = 0.0
) -> bytes:
    conn = sqlite3.connect(":memory:")
    conn.execute(
        """
        CREATE TABLE gpkg_spatial_ref_sys (
            srs_name TEXT NOT NULL,
            srs_id INTEGER PRIMARY KEY,
            organization TEXT NOT NULL,
            organization_coordsys_id INTEGER NOT NULL,
            definition TEXT NOT NULL,
            description TEXT
        )
        """
    )
    for row in (
        ("Undefined Cartesian SRS", -1, "NONE", -1, "undefined", None),
        ("Undefined geographic SRS", 0, "NONE", 0, "undefined", None),
        (
            "WGS 84 geodetic",
            4326,
            "EPSG",
            4326,
            'GEOGCRS["WGS 84",DATUM["World Geodetic System 1984"],CS[ll,UNIT[degree]]]',
            "WGS 84 (Longitude, Latitude)",
        ),
    ):
        conn.execute("INSERT INTO gpkg_spatial_ref_sys VALUES (?,?,?,?,?,?)", row)
    conn.execute(
        """
        CREATE TABLE gpkg_contents (
            table_name TEXT NOT NULL PRIMARY KEY,
            data_type TEXT NOT NULL,
            identifier TEXT UNIQUE,
            description TEXT DEFAULT '',
            last_change DATETIME NOT NULL DEFAULT '2024-01-01T00:00:00.000Z',
            min_x DOUBLE, min_y DOUBLE, max_x DOUBLE, max_y DOUBLE,
            srs_id INTEGER REFERENCES gpkg_spatial_ref_sys(srs_id)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE gpkg_geometry_columns (
            table_name TEXT NOT NULL,
            column_name TEXT NOT NULL,
            geometry_type_name TEXT NOT NULL,
            srs_id INTEGER NOT NULL,
            z TINYINT NOT NULL,
            m TINYINT NOT NULL,
            CONSTRAINT pk_geom_cols PRIMARY KEY (table_name, column_name)
        )
        """
    )
    table_name = "aoi_boundary"
    conn.execute(
        f"""
        CREATE TABLE {table_name} (
            fid INTEGER PRIMARY KEY AUTOINCREMENT,
            geom BLOB,
            run_id TEXT,
            area_hectares REAL
        )
        """
    )
    conn.execute(
        "INSERT INTO gpkg_contents VALUES (?,?,?,?,?,?,?,?,?,?)",
        (
            table_name,
            "features",
            run_id,
            f"Peatlands Sentinel AOI {run_id}",
            _EPOCH,
            float(bbox[0]),
            float(bbox[1]),
            float(bbox[2]),
            float(bbox[3]),
            4326,
        ),
    )
    geom_type = "MULTIPOLYGON" if geometry.get("type") == "MultiPolygon" else "POLYGON"
    conn.execute(
        "INSERT INTO gpkg_geometry_columns VALUES (?,?,?,?,?,?)",
        (table_name, "geom", geom_type, 4326, 0, 0),
    )
    blob = _gpkg_header(_geometry_wkb(geometry), bbox)
    conn.execute(
        f"INSERT INTO {table_name} (geom, run_id, area_hectares) VALUES (?,?,?)",
        (sqlite3.Binary(blob), run_id, area_ha),
    )
    conn.execute("PRAGMA application_id = 1196444487")
    conn.execute("PRAGMA user_version = 10300")
    conn.commit()
    out = sqlite3.connect(":memory:")
    conn.backup(out)
    conn.close()
    return out.serialize()
