from __future__ import annotations

import json
import sqlite3
from datetime import date, datetime
from pathlib import Path
from typing import Any

try:
    import pyarrow as pa
    import pyarrow.parquet as pq
except ImportError as exc:  # pragma: no cover - exercised by runtime dependency install
    pa = None  # type: ignore[assignment]
    pq = None  # type: ignore[assignment]
    _PARQUET_IMPORT_ERROR = exc
else:
    _PARQUET_IMPORT_ERROR = None


ARCHIVE_TABLES: tuple[str, ...] = (
    "metric_payloads",
    "change_events",
    "node_discoveries",
    "health_summaries",
    "alerts",
    "trend_summaries",
    "anomaly_scores",
    "root_cause_hints",
    "action_recommendations",
)


def run_archive(
    config: dict[str, Any],
    before: str,
    output_dir: str = "./data/archive",
    dry_run: bool = True,
) -> None:
    if not before:
        raise ValueError("--before is required for archive mode (YYYY-MM-DD)")
    date.fromisoformat(before)

    if pa is None or pq is None:
        raise RuntimeError(
            "Parquet export requires pyarrow. Install with: pip install pyarrow"
        ) from _PARQUET_IMPORT_ERROR

    collector_cfg = config.get("collector", {})
    sqlite_path = str(collector_cfg.get("sqlite_path", "./data/sentinel.db"))
    archive_root = Path(output_dir)
    archive_root.mkdir(parents=True, exist_ok=True)

    manifest: dict[str, Any] = {
        "sqlite_path": sqlite_path,
        "before": before,
        "dry_run": dry_run,
        "output_dir": str(archive_root),
        "tables": {},
        "total_rows": 0,
    }

    conn = sqlite3.connect(sqlite_path)
    try:
        for table in ARCHIVE_TABLES:
            cursor = conn.execute(
                f"SELECT * FROM {table} WHERE datetime(created_at_utc) < datetime(?) ORDER BY id ASC",
                (before,),
            )
            rows = cursor.fetchall()
            if not rows:
                continue

            columns = [description[0] for description in cursor.description or ()]
            row_dicts = [dict(zip(columns, row)) for row in rows]
            target_dir = archive_root / table / f"before={before}"
            target_dir.mkdir(parents=True, exist_ok=True)
            target_file = target_dir / f"{table}.parquet"

            manifest["tables"][table] = {
                "rows": len(row_dicts),
                "output_file": str(target_file),
            }
            manifest["total_rows"] += len(row_dicts)

            if not dry_run:
                table_data = {column: [row.get(column) for row in row_dicts] for column in columns}
                arrow_table = pa.Table.from_pydict(table_data)
                pq.write_table(arrow_table, target_file)
    finally:
        conn.close()

    if not dry_run:
        manifest_path = archive_root / f"manifest-before={before}.json"
        manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")

    print(json.dumps(manifest, indent=2, sort_keys=True))
