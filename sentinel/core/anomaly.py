from __future__ import annotations

import math
from collections import defaultdict, deque
from dataclasses import dataclass
from statistics import mean, pstdev
from typing import Any


@dataclass
class AnomalyConfig:
    window_size: int = 20
    min_samples: int = 8
    zscore_warn: float = 2.0
    zscore_critical: float = 3.0


class RollingAnomalyScorer:
    def __init__(self, cfg: AnomalyConfig) -> None:
        self._cfg = cfg
        self._history: dict[str, dict[str, deque[float]]] = defaultdict(
            lambda: defaultdict(lambda: deque(maxlen=self._cfg.window_size))
        )

    @classmethod
    def from_config(cls, config: dict[str, Any]) -> "RollingAnomalyScorer":
        anomaly_cfg = config.get("anomaly", {})
        cfg = AnomalyConfig(
            window_size=max(5, int(anomaly_cfg.get("window_size", 20))),
            min_samples=max(3, int(anomaly_cfg.get("min_samples", 8))),
            zscore_warn=float(anomaly_cfg.get("zscore_warn", 2.0)),
            zscore_critical=float(anomaly_cfg.get("zscore_critical", 3.0)),
        )
        return cls(cfg)

    def evaluate(self, payload: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        node_id = str(payload.get("node", {}).get("node_id", "unknown"))
        timestamp_utc = str(payload.get("timestamp_utc", "unknown"))
        metrics = payload.get("metrics", {})

        observed = {
            "cpu_usage_percent": float(metrics.get("cpu", {}).get("usage_percent", 0.0)),
            "memory_usage_percent": float(metrics.get("memory", {}).get("usage_percent", 0.0)),
            "disk_usage_percent": float(metrics.get("disk", {}).get("root_usage_percent", 0.0)),
            "process_count": float(metrics.get("processes", {}).get("count", 0.0)),
        }

        trend_metrics: dict[str, dict[str, float]] = {}
        anomalies: list[dict[str, Any]] = []

        for metric_name, value in observed.items():
            history = self._history[node_id][metric_name]
            history_values = list(history)

            metric_summary: dict[str, float] = {
                "current": value,
                "samples": float(len(history_values)),
            }

            if history_values:
                avg = mean(history_values)
                metric_summary["mean"] = avg
                metric_summary["delta_from_mean"] = value - avg
                metric_summary["trend_delta"] = value - history_values[0]

                if len(history_values) >= self._cfg.min_samples:
                    sigma = pstdev(history_values)
                    if sigma > 0:
                        z = (value - avg) / sigma
                        metric_summary["zscore"] = z

                        abs_z = abs(z)
                        if abs_z >= self._cfg.zscore_warn:
                            severity = "critical" if abs_z >= self._cfg.zscore_critical else "warning"
                            score = min(100, int(math.ceil(abs_z * 20)))
                            anomalies.append(
                                {
                                    "node_id": node_id,
                                    "metric": metric_name,
                                    "severity": severity,
                                    "score": score,
                                    "timestamp_utc": timestamp_utc,
                                    "details": {
                                        "value": value,
                                        "mean": avg,
                                        "stddev": sigma,
                                        "zscore": z,
                                        "window_size": len(history_values),
                                    },
                                }
                            )

            trend_metrics[metric_name] = metric_summary
            history.append(value)

        trend_summary = {
            "node_id": node_id,
            "timestamp_utc": timestamp_utc,
            "metrics": trend_metrics,
        }
        return trend_summary, anomalies
