from __future__ import annotations

import json
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer

from sentinel.core.notifications import WebhookNotifier


class _CaptureHandler(BaseHTTPRequestHandler):
    captured: list[dict[str, object]] = []

    def do_POST(self) -> None:  # noqa: N802
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length).decode("utf-8")
        _CaptureHandler.captured.append(json.loads(body))
        self.send_response(200)
        self.end_headers()

    def log_message(self, format: str, *args):  # noqa: A003
        return


class TestWebhookNotifier(unittest.TestCase):
    def setUp(self) -> None:
        _CaptureHandler.captured = []
        self.server = HTTPServer(("127.0.0.1", 0), _CaptureHandler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        time.sleep(0.05)

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()

    def test_notifier_posts_event_payload(self) -> None:
        host, port = self.server.server_address
        notifier = WebhookNotifier.from_config(
            {
                "integration": {
                    "webhooks": {
                        "enabled": True,
                        "urls": [f"http://{host}:{port}/hook"],
                        "timeout_seconds": 2.0,
                    }
                }
            }
        )
        self.assertIsNotNone(notifier)

        notifier.notify("alert", {"node_id": "node-webhook", "message": "CPU high"})

        self.assertEqual(len(_CaptureHandler.captured), 1)
        self.assertEqual(_CaptureHandler.captured[0]["event_type"], "alert")
        self.assertEqual(_CaptureHandler.captured[0]["payload"]["node_id"], "node-webhook")


if __name__ == "__main__":
    unittest.main()
