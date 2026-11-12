import io
import json
import sqlite3
from typing import Any
import numpy as np

from app.config import get_settings


def get_db_connection() -> sqlite3.Connection:
    settings = get_settings()
    db_path = settings.data_dir / "peatlands.db"
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with get_db_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS analysis_runs (
                id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                target TEXT NOT NULL,
                area_hectares REAL NOT NULL,
                geojson TEXT NOT NULL,
                metrics TEXT NOT NULL,
                transitions TEXT NOT NULL,
                ai_report TEXT NOT NULL,
                arrays_blob BLOB
            )
            """
        )
        try:
            conn.execute("ALTER TABLE analysis_runs ADD COLUMN arrays_blob BLOB")
        except sqlite3.OperationalError:
            pass
        conn.commit()


def _pack_arrays(arrays: dict[str, np.ndarray] | None) -> bytes | None:
    if not arrays:
        return None
    buf = io.BytesIO()
    np.savez_compressed(
        buf, **{k: v for k, v in arrays.items() if isinstance(v, np.ndarray)}
    )
    return buf.getvalue()


def _unpack_arrays(blob: bytes | None) -> dict[str, np.ndarray] | None:
    if not blob:
        return None
    with np.load(io.BytesIO(blob)) as npz:
        return {k: npz[k] for k in npz.files}


def save_analysis_run(
    run_id: str,
    created_at: str,
    target: str,
    area_hectares: float,
    geojson_data: dict[str, Any],
    metrics_data: dict[str, Any],
    transitions_data: list[dict[str, Any]],
    ai_report_data: dict[str, Any],
    arrays: dict[str, np.ndarray] | None = None,
) -> None:
    init_db()
    with get_db_connection() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO analysis_runs
            (id, created_at, target, area_hectares, geojson, metrics, transitions, ai_report, arrays_blob)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                created_at,
                target,
                area_hectares,
                json.dumps(geojson_data),
                json.dumps(metrics_data),
                json.dumps(transitions_data),
                json.dumps(ai_report_data),
                _pack_arrays(arrays),
            ),
        )
        conn.commit()


def get_analysis_run(run_id: str) -> dict[str, Any] | None:
    init_db()
    with get_db_connection() as conn:
        cursor = conn.execute(
            "SELECT id, created_at, target, area_hectares, geojson, metrics, transitions, ai_report FROM analysis_runs WHERE id = ?",
            (run_id,),
        )
        row = cursor.fetchone()
        if not row:
            return None
        return {
            "id": row["id"],
            "created_at": row["created_at"],
            "target": row["target"],
            "area_hectares": row["area_hectares"],
            "geojson": json.loads(row["geojson"]),
            "metrics": json.loads(row["metrics"]),
            "transitions": json.loads(row["transitions"]),
            "ai_report": json.loads(row["ai_report"]),
        }


def get_analysis_arrays(run_id: str) -> dict[str, np.ndarray] | None:
    init_db()
    with get_db_connection() as conn:
        row = conn.execute(
            "SELECT arrays_blob FROM analysis_runs WHERE id = ?", (run_id,)
        ).fetchone()
        if not row:
            return None
        return _unpack_arrays(row["arrays_blob"])


def list_analysis_runs(limit: int = 15) -> list[dict[str, Any]]:
    init_db()
    with get_db_connection() as conn:
        cursor = conn.execute(
            "SELECT id, created_at, target, area_hectares FROM analysis_runs ORDER BY created_at DESC LIMIT ?",
            (limit,),
        )
        return [dict(row) for row in cursor.fetchall()]
