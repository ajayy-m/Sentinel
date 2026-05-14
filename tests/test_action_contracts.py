from __future__ import annotations

import unittest

from sentinel.core.contracts import (
    ACTION_REQUEST_SCHEMA,
    ACTION_REQUEST_SCHEMA_VERSION,
    ACTION_RESULT_SCHEMA,
    ACTION_RESULT_SCHEMA_VERSION,
    validate_action_request_contract,
    validate_action_result_contract,
)


class TestActionContracts(unittest.TestCase):
    def test_action_request_contract_accepts_versioned_record(self) -> None:
        record = {
            "schema": ACTION_REQUEST_SCHEMA,
            "schema_version": ACTION_REQUEST_SCHEMA_VERSION,
            "node_id": "node-1",
            "category": "stabilize_metric_drift",
            "action_type": "restart_service",
            "title": "Restart service",
            "command": "systemctl restart my-service",
            "risk_level": "medium",
        }

        valid, message = validate_action_request_contract(record)
        self.assertTrue(valid, message)
        self.assertEqual(message, "")

    def test_action_request_contract_rejects_bad_version(self) -> None:
        record = {
            "schema": ACTION_REQUEST_SCHEMA,
            "schema_version": "2.0",
            "node_id": "node-1",
            "category": "stabilize_metric_drift",
            "action_type": "restart_service",
            "title": "Restart service",
            "command": "systemctl restart my-service",
            "risk_level": "medium",
        }

        valid, message = validate_action_request_contract(record)
        self.assertFalse(valid)
        self.assertIn(ACTION_REQUEST_SCHEMA_VERSION, message)

    def test_action_result_contract_accepts_versioned_record(self) -> None:
        record = {
            "schema": ACTION_RESULT_SCHEMA,
            "schema_version": ACTION_RESULT_SCHEMA_VERSION,
            "request_id": 10,
            "status": "planned",
            "backend": "dry_run",
            "command": "systemctl restart my-service",
            "created_at_utc": "2026-05-05T00:00:00Z",
        }

        valid, message = validate_action_result_contract(record)
        self.assertTrue(valid, message)
        self.assertEqual(message, "")

    def test_action_result_contract_rejects_missing_backend(self) -> None:
        record = {
            "schema": ACTION_RESULT_SCHEMA,
            "schema_version": ACTION_RESULT_SCHEMA_VERSION,
            "request_id": 10,
            "status": "planned",
            "command": "systemctl restart my-service",
            "created_at_utc": "2026-05-05T00:00:00Z",
        }

        valid, message = validate_action_result_contract(record)
        self.assertFalse(valid)
        self.assertIn("backend", message)


if __name__ == "__main__":
    unittest.main()
