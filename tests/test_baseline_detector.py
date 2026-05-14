from __future__ import annotations

import unittest

from sentinel.core.baseline import BaselineDetector


class TestBaselineDetector(unittest.TestCase):
    def setUp(self) -> None:
        self.detector = BaselineDetector()

    def test_cpu_rule_flags_large_spike(self) -> None:
        history = [10.0, 12.0, 11.0, 13.0, 12.0, 14.0, 15.0, 13.0, 12.0, 14.0]
        self.assertTrue(self.detector.detect_cpu_anomaly(40.0, history))

    def test_memory_rule_flags_sustained_growth(self) -> None:
        history = [40.0, 47.0, 55.0]
        self.assertTrue(self.detector.detect_memory_leak(63.0, history))

    def test_process_rule_flags_spike(self) -> None:
        history = [100.0, 102.0, 99.0, 101.0, 103.0, 104.0, 102.0, 101.0, 100.0, 102.0]
        self.assertTrue(self.detector.detect_process_spike(140.0, history))

    def test_payload_evaluation_returns_rule_alerts(self) -> None:
        payload = {
            "metrics": {
                "cpu": {"usage_percent": 40.0},
                "memory": {"usage_percent": 63.0},
                "processes": {"count": 140.0},
            }
        }
        history = {
            "cpu": [10.0, 12.0, 11.0, 13.0, 12.0, 14.0, 15.0, 13.0, 12.0, 14.0],
            "memory": [40.0, 47.0, 55.0],
            "processes": [100.0, 102.0, 99.0, 101.0, 103.0, 104.0, 102.0, 101.0, 100.0, 102.0],
        }

        alerts = self.detector.evaluate_payload(payload, history)
        self.assertGreaterEqual(len(alerts), 2)
        self.assertTrue(all(alert["category"] == "baseline_rule" for alert in alerts))


if __name__ == "__main__":
    unittest.main()
