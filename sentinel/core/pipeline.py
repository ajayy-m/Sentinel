from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class PipelineConfig:
    cpu_warn_percent: float = 80.0
    cpu_critical_percent: float = 95.0
    memory_warn_percent: float = 80.0
    memory_critical_percent: float = 95.0
    disk_warn_percent: float = 85.0
    disk_critical_percent: float = 95.0
    warning_score_threshold: int = 70
    critical_score_threshold: int = 40


class MetricPipeline:
    def __init__(self, cfg: PipelineConfig) -> None:
        self._cfg = cfg

    @classmethod
    def from_config(cls, config: dict[str, Any]) -> "MetricPipeline":
        pipeline_cfg = config.get("pipeline", {})
        cfg = PipelineConfig(
            cpu_warn_percent=float(pipeline_cfg.get("cpu_warn_percent", 80.0)),
            cpu_critical_percent=float(pipeline_cfg.get("cpu_critical_percent", 95.0)),
            memory_warn_percent=float(pipeline_cfg.get("memory_warn_percent", 80.0)),
            memory_critical_percent=float(pipeline_cfg.get("memory_critical_percent", 95.0)),
            disk_warn_percent=float(pipeline_cfg.get("disk_warn_percent", 85.0)),
            disk_critical_percent=float(pipeline_cfg.get("disk_critical_percent", 95.0)),
            warning_score_threshold=int(pipeline_cfg.get("warning_score_threshold", 70)),
            critical_score_threshold=int(pipeline_cfg.get("critical_score_threshold", 40)),
        )
        return cls(cfg)

    def evaluate(self, payload: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        node_id = str(payload.get("node", {}).get("node_id", "unknown"))
        timestamp_utc = str(payload.get("timestamp_utc", "unknown"))
        metrics = payload.get("metrics", {})

        cpu_percent = float(metrics.get("cpu", {}).get("usage_percent", 0.0))
        memory_percent = float(metrics.get("memory", {}).get("usage_percent", 0.0))
        disk_percent = float(metrics.get("disk", {}).get("root_usage_percent", 0.0))

        score = 100
        reasons: list[str] = []
        alerts: list[dict[str, Any]] = []

        score, reasons, alerts = self._apply_metric(
            node_id,
            timestamp_utc,
            score,
            reasons,
            alerts,
            metric_name="cpu_usage_percent",
            value=cpu_percent,
            warn=self._cfg.cpu_warn_percent,
            critical=self._cfg.cpu_critical_percent,
            category="cpu",
        )
        score, reasons, alerts = self._apply_metric(
            node_id,
            timestamp_utc,
            score,
            reasons,
            alerts,
            metric_name="memory_usage_percent",
            value=memory_percent,
            warn=self._cfg.memory_warn_percent,
            critical=self._cfg.memory_critical_percent,
            category="memory",
        )
        score, reasons, alerts = self._apply_metric(
            node_id,
            timestamp_utc,
            score,
            reasons,
            alerts,
            metric_name="disk_root_usage_percent",
            value=disk_percent,
            warn=self._cfg.disk_warn_percent,
            critical=self._cfg.disk_critical_percent,
            category="disk",
        )

        status = "healthy"
        if score <= self._cfg.critical_score_threshold:
            status = "critical"
        elif score <= self._cfg.warning_score_threshold:
            status = "warning"

        summary = {
            "node_id": node_id,
            "timestamp_utc": timestamp_utc,
            "score": max(0, score),
            "status": status,
            "reasons": reasons,
        }
        return summary, alerts

    def _apply_metric(
        self,
        node_id: str,
        timestamp_utc: str,
        score: int,
        reasons: list[str],
        alerts: list[dict[str, Any]],
        metric_name: str,
        value: float,
        warn: float,
        critical: float,
        category: str,
    ) -> tuple[int, list[str], list[dict[str, Any]]]:
        if value >= critical:
            score -= 35
            reason = f"{metric_name} is critical at {value:.1f}% (>= {critical:.1f}%)"
            reasons.append(reason)
            alerts.append(
                {
                    "node_id": node_id,
                    "severity": "critical",
                    "category": category,
                    "timestamp_utc": timestamp_utc,
                    "message": reason,
                    "details": {
                        "metric": metric_name,
                        "value": value,
                        "threshold": critical,
                    },
                }
            )
        elif value >= warn:
            score -= 15
            reason = f"{metric_name} is high at {value:.1f}% (>= {warn:.1f}%)"
            reasons.append(reason)
            alerts.append(
                {
                    "node_id": node_id,
                    "severity": "warning",
                    "category": category,
                    "timestamp_utc": timestamp_utc,
                    "message": reason,
                    "details": {
                        "metric": metric_name,
                        "value": value,
                        "threshold": warn,
                    },
                }
            )

        return score, reasons, alerts
