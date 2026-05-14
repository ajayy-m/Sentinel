from __future__ import annotations

import json
import tempfile
import threading
import time
import unittest
from pathlib import Path
from urllib.request import urlopen

from sentinel.core.api import create_api_server
from sentinel.core.storage import Storage


class TestIntegrationApi(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp_dir = tempfile.TemporaryDirectory()
        db_path = Path(self._tmp_dir.name) / "sentinel_api_test.db"
        self.storage = Storage(str(db_path))
        self.storage.store_payload(
            {
                "node": {"node_id": "node-api"},
                "timestamp_utc": "2026-05-05T00:00:00Z",
                "metrics": {"cpu": {"usage_percent": 33.0}},
            }
        )
        self.storage.store_alert(
            {
                "node_id": "node-api",
                "severity": "warning",
                "category": "cpu",
                "timestamp_utc": "2026-05-05T00:00:00Z",
                "message": "CPU high",
                "details": {},
            }
        )
        self.server = create_api_server(
            {
                "collector": {"sqlite_path": str(db_path)},
                "integration": {"api": {"host": "127.0.0.1", "port": 0, "max_rows": 5}},
            }
        )
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        time.sleep(0.05)

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.storage.close()
        self._tmp_dir.cleanup()

    def test_health_endpoint_returns_summary(self) -> None:
        host, port = self.server.server_address
        with urlopen(f"http://{host}:{port}/health") as response:
            payload = json.loads(response.read().decode("utf-8"))

        self.assertEqual(payload["active_node_count"], 1)
        self.assertEqual(payload["counts"]["alerts"], 1)

    def test_alerts_endpoint_returns_items(self) -> None:
        host, port = self.server.server_address
        with urlopen(f"http://{host}:{port}/alerts?limit=1") as response:
            payload = json.loads(response.read().decode("utf-8"))

        self.assertEqual(payload["count"], 1)
        self.assertEqual(payload["items"][0]["message"], "CPU high")


if __name__ == "__main__":
    unittest.main()
