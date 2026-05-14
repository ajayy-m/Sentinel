from __future__ import annotations

import unittest

from sentinel.core.preflight import TransportConfigurationCheck
from sentinel.core.schema import validate_payload_schema


class TestContracts(unittest.TestCase):
    def test_payload_schema_accepts_valid_metric_payload(self) -> None:
        payload = {
            "schema": "metric_payload",
            "protocol_version": "1.0",
            "node": {
                "node_id": "node-1",
                "hostname": "node-1-host",
                "os": "Linux",
                "platform": "x86_64",
            },
            "timestamp_utc": "2026-05-05T00:00:00Z",
            "metrics": {
                "cpu": {"usage_percent": 42.0},
                "memory": {"usage_percent": 55.0},
            },
        }

        valid, message = validate_payload_schema(payload)
        self.assertTrue(valid, message)
        self.assertEqual(message, "")

    def test_payload_schema_rejects_missing_node_id(self) -> None:
        payload = {
            "schema": "metric_payload",
            "protocol_version": "1.0",
            "node": {"hostname": "node-1-host"},
            "timestamp_utc": "2026-05-05T00:00:00Z",
            "metrics": {},
        }

        valid, message = validate_payload_schema(payload)
        self.assertFalse(valid)
        self.assertIn("node.node_id", message)

    def test_transport_configuration_check_accepts_tcp_mode(self) -> None:
        check = TransportConfigurationCheck(
            {
                "mode": "tcp",
                "endpoint": "tcp://127.0.0.1:5556",
                "collector_endpoints": ["tcp://collector-a:5556", "tcp://collector-b:5556"],
                "auth": {
                    "enabled": False,
                    "scheme": "hmac-sha256",
                    "shared_key": "",
                },
            }
        )

        valid, message = check.check()
        self.assertTrue(valid, message)

    def test_transport_configuration_check_rejects_bad_endpoint_and_auth(self) -> None:
        check = TransportConfigurationCheck(
            {
                "mode": "tcp",
                "endpoint": "http://127.0.0.1:5556",
                "collector_endpoints": ["tcp://collector-a:5556"],
                "auth": {
                    "enabled": True,
                    "scheme": "hmac-sha256",
                    "shared_key": "short-key",
                },
            }
        )

        valid, message = check.check()
        self.assertFalse(valid)
        self.assertTrue(
            "tcp://" in message or "shared_key" in message,
            message,
        )


if __name__ == "__main__":
    unittest.main()
