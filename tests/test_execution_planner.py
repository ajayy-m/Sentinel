from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from sentinel.core.execution import ActionExecutionPlanner


class TestExecutionPlanner(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp_dir = tempfile.TemporaryDirectory()
        self.queue_dir = Path(self._tmp_dir.name) / "execution-queue"

    def tearDown(self) -> None:
        self._tmp_dir.cleanup()

    def test_planner_writes_record_for_approved_request(self) -> None:
        planner = ActionExecutionPlanner.from_config(
            {
                "execution": {
                    "enabled": True,
                    "backend": "dry_run",
                    "queue_dir": str(self.queue_dir),
                }
            }
        )

        record = planner.plan_from_request(
            {
                "request_id": 12,
                "node_id": "node-a",
                "action_type": "restart_service",
                "command": "systemctl restart app",
            },
            {
                "approved": True,
                "actor": "operator",
                "rationale": "Approved during maintenance window",
            },
        )

        self.assertIsNotNone(record)
        self.assertTrue((self.queue_dir / "execution_queue.jsonl").exists())
        self.assertEqual(record.node_id, "node-a")
        self.assertEqual(record.status, "planned")

    def test_planner_ignores_rejected_request(self) -> None:
        planner = ActionExecutionPlanner.from_config(
            {
                "execution": {
                    "enabled": True,
                    "backend": "dry_run",
                    "queue_dir": str(self.queue_dir),
                }
            }
        )

        record = planner.plan_from_request(
            {
                "request_id": 13,
                "node_id": "node-b",
                "action_type": "kill_process",
                "command": "kill -9 1234",
            },
            {
                "approved": False,
                "actor": "operator",
                "rationale": "Too risky",
            },
        )

        self.assertIsNone(record)
        self.assertFalse((self.queue_dir / "execution_queue.jsonl").exists())


if __name__ == "__main__":
    unittest.main()
