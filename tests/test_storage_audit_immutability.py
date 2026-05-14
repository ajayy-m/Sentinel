from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from sentinel.core.storage import Storage


class TestStorageAuditImmutability(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp_dir = tempfile.TemporaryDirectory()
        db_path = Path(self._tmp_dir.name) / "sentinel_test.db"
        self.storage = Storage(str(db_path))

    def tearDown(self) -> None:
        self.storage.close()
        self._tmp_dir.cleanup()

    def test_action_requests_are_append_only(self) -> None:
        request_id = self.storage.create_action_request(
            {
                "node_id": "node-1",
                "category": "stabilize_metric_drift",
                "action_type": "restart_service",
                "title": "Restart service",
                "description": "Try restarting service safely",
                "command": "systemctl restart my-service",
                "risk_level": "medium",
                "source_category": "anomaly",
                "source_timestamp_utc": "2026-05-04T00:00:00Z",
                "evidence": {"metric": "cpu"},
                "execution_mode": "approval_required",
            }
        )

        with self.assertRaises(sqlite3.IntegrityError):
            self.storage._conn.execute(
                "UPDATE action_requests SET status = ? WHERE id = ?",
                ("approved", request_id),
            )

        with self.assertRaises(sqlite3.IntegrityError):
            self.storage._conn.execute(
                "DELETE FROM action_requests WHERE id = ?",
                (request_id,),
            )

    def test_approval_decisions_are_append_only(self) -> None:
        request_id = self.storage.create_action_request(
            {
                "node_id": "node-2",
                "category": "stabilize_metric_drift",
                "action_type": "kill_process",
                "title": "Kill runaway process",
                "description": "Stop non-critical runaway process",
                "command": "kill -9 1234",
                "risk_level": "high",
                "source_category": "anomaly",
                "source_timestamp_utc": "2026-05-04T00:00:01Z",
                "evidence": {"pid": 1234},
                "execution_mode": "approval_required",
            }
        )
        self.storage.store_approval_decision(
            {
                "request_id": request_id,
                "actor": "operator",
                "approved": True,
                "rationale": "Safe maintenance window",
                "timestamp_utc": "2026-05-04T00:00:02Z",
                "execution_mode": "manual_review",
            }
        )

        with self.assertRaises(sqlite3.IntegrityError):
            self.storage._conn.execute(
                "UPDATE approval_decisions SET actor = ? WHERE request_id = ?",
                ("other-operator", request_id),
            )

        with self.assertRaises(sqlite3.IntegrityError):
            self.storage._conn.execute(
                "DELETE FROM approval_decisions WHERE request_id = ?",
                (request_id,),
            )


if __name__ == "__main__":
    unittest.main()
