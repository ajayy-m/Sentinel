from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from sentinel.core.storage import Storage


class TestStoragePurge(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp_dir = tempfile.TemporaryDirectory()
        db_path = Path(self._tmp_dir.name) / "sentinel_purge_test.db"
        self.storage = Storage(str(db_path))

    def tearDown(self) -> None:
        self.storage.close()
        self._tmp_dir.cleanup()

    def test_purge_dry_run_reports_without_deleting(self) -> None:
        self.storage.store_payload(
            {
                "node": {"node_id": "node-a"},
                "timestamp_utc": "2026-05-04T00:00:00Z",
                "metrics": {},
            }
        )

        summary = self.storage.purge_before(before_date="2099-01-01", dry_run=True)
        self.assertGreaterEqual(summary.get("metric_payloads", 0), 1)

        still_present = self.storage.get_recent_payloads(limit=10)
        self.assertEqual(len(still_present), 1)

    def test_purge_executes_for_non_audit_tables_only(self) -> None:
        self.storage.store_payload(
            {
                "node": {"node_id": "node-b"},
                "timestamp_utc": "2026-05-04T00:00:01Z",
                "metrics": {},
            }
        )
        request_id = self.storage.create_action_request(
            {
                "node_id": "node-b",
                "category": "ops",
                "action_type": "restart_service",
                "title": "Restart",
                "description": "desc",
                "command": "cmd",
                "risk_level": "medium",
                "source_category": "ops",
                "source_timestamp_utc": "2026-05-04T00:00:01Z",
                "evidence": {},
            }
        )

        summary = self.storage.purge_before(before_date="2099-01-01", dry_run=False)
        self.assertGreaterEqual(summary.get("metric_payloads", 0), 1)

        payloads_after = self.storage.get_recent_payloads(limit=10)
        self.assertEqual(len(payloads_after), 0)

        requests_after = self.storage.get_recent_action_requests(limit=10)
        self.assertEqual(len(requests_after), 1)
        self.assertEqual(requests_after[0].get("request_id"), request_id)


if __name__ == "__main__":
    unittest.main()
