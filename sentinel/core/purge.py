from __future__ import annotations

import json
from datetime import date
from typing import Any

from sentinel.core.storage import Storage


def run_purge(
    config: dict[str, Any],
    before: str,
    dry_run: bool = True,
    confirm: bool = False,
) -> None:
    if not before:
        raise ValueError("--before is required for purge mode (YYYY-MM-DD)")

    # Validate date shape early for clear operator feedback.
    date.fromisoformat(before)

    if not dry_run and not confirm:
        raise ValueError("Refusing destructive purge without --confirm")

    collector_cfg = config.get("collector", {})
    sqlite_path = str(collector_cfg.get("sqlite_path", "./data/sentinel.db"))

    storage = Storage(sqlite_path)
    try:
        result = storage.purge_before(before_date=before, dry_run=dry_run)
        output = {
            "sqlite_path": sqlite_path,
            "before": before,
            "dry_run": dry_run,
            "purged": result,
            "note": "Audit tables (action_requests, approval_decisions) are immutable and excluded.",
        }
        print(json.dumps(output, indent=2, sort_keys=True))
    finally:
        storage.close()
