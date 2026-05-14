from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

try:
    from sentinel.ai.llm import OllamaClient
    HAS_LLM = True
except ImportError:
    HAS_LLM = False


@dataclass
class RootCauseConfig:
    window_seconds: int = 60
    cooldown_seconds: int = 30
    min_repeated_anomalies: int = 2
    min_metric_instability_count: int = 3
    enable_llm: bool = False


class RootCauseCorrelator:
    def __init__(self, cfg: RootCauseConfig, llm_client: Any | None = None) -> None:
        self._cfg = cfg
        self._llm = llm_client
        self._signals: dict[str, deque[dict[str, Any]]] = defaultdict(deque)
        self._last_hint_at: dict[tuple[str, str], datetime] = {}

    @classmethod
    def from_config(cls, config: dict[str, Any]) -> "RootCauseCorrelator":
        rc_cfg = config.get("root_cause", {})
        cfg = RootCauseConfig(
            window_seconds=max(10, int(rc_cfg.get("window_seconds", 60))),
            cooldown_seconds=max(5, int(rc_cfg.get("cooldown_seconds", 30))),
            min_repeated_anomalies=max(1, int(rc_cfg.get("min_repeated_anomalies", 2))),
            min_metric_instability_count=max(
                2, int(rc_cfg.get("min_metric_instability_count", 3))
            ),
            enable_llm=bool(rc_cfg.get("enable_llm", False)),
        )
        
        llm_client = None
        if cfg.enable_llm and HAS_LLM:
            try:
                llm_client = OllamaClient.from_config(config)
                if not llm_client.is_healthy():
                    llm_client = None
            except Exception:
                pass
        
        return cls(cfg, llm_client)

    def correlate(
        self,
        node_id: str,
        timestamp_utc: str,
        change_events: list[dict[str, Any]],
        anomaly_scores: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        now = _parse_timestamp(timestamp_utc)
        recent = self._signals[node_id]

        for event in change_events:
            recent.append(
                {
                    "ts": now,
                    "kind": "change_event",
                    "event_type": str(event.get("event_type", "unknown")),
                    "severity": str(event.get("severity", "info")),
                }
            )

        for anomaly in anomaly_scores:
            recent.append(
                {
                    "ts": now,
                    "kind": "anomaly_score",
                    "metric": str(anomaly.get("metric", "unknown")),
                    "severity": str(anomaly.get("severity", "warning")),
                    "score": int(anomaly.get("score", 0)),
                }
            )

        self._trim(node_id, now)
        return self._build_hints(node_id, timestamp_utc)

    def _trim(self, node_id: str, now: datetime) -> None:
        cutoff = now - timedelta(seconds=self._cfg.window_seconds)
        queue = self._signals[node_id]
        while queue and queue[0]["ts"] < cutoff:
            queue.popleft()

    def _build_hints(self, node_id: str, timestamp_utc: str) -> list[dict[str, Any]]:
        queue = list(self._signals[node_id])

        has_process_spike_event = any(
            item.get("kind") == "change_event" and item.get("event_type") == "process_count_spike"
            for item in queue
        )
        process_anomalies = [
            item
            for item in queue
            if item.get("kind") == "anomaly_score" and item.get("metric") == "process_count"
        ]

        anomaly_by_metric: dict[str, int] = defaultdict(int)
        for item in queue:
            if item.get("kind") != "anomaly_score":
                continue
            metric_name = str(item.get("metric", "unknown"))
            anomaly_by_metric[metric_name] += 1

        high_anomaly_metrics = {
            item.get("metric")
            for item in queue
            if item.get("kind") == "anomaly_score" and item.get("severity") in {"warning", "critical"}
        }

        hints: list[dict[str, Any]] = []

        if has_process_spike_event and process_anomalies:
            hint = self._make_hint(
                node_id=node_id,
                category="process_activity",
                confidence="medium",
                timestamp_utc=timestamp_utc,
                message="Process count anomaly correlates with process spike event",
                evidence={
                    "process_anomaly_count": len(process_anomalies),
                    "window_seconds": self._cfg.window_seconds,
                },
            )
            if hint is not None:
                hints.append(hint)

        if len(process_anomalies) >= self._cfg.min_repeated_anomalies:
            hint = self._make_hint(
                node_id=node_id,
                category="repeated_process_anomaly",
                confidence="low",
                timestamp_utc=timestamp_utc,
                message="Process count anomaly is recurring within the correlation window",
                evidence={
                    "process_anomaly_count": len(process_anomalies),
                    "required": self._cfg.min_repeated_anomalies,
                    "window_seconds": self._cfg.window_seconds,
                },
            )
            if hint is not None:
                hints.append(hint)

        unstable_metrics = sorted(
            metric
            for metric, count in anomaly_by_metric.items()
            if count >= self._cfg.min_metric_instability_count and metric != "unknown"
        )
        if unstable_metrics:
            hint = self._make_hint(
                node_id=node_id,
                category="metric_recurrence",
                confidence="low",
                timestamp_utc=timestamp_utc,
                message="One or more metrics are repeatedly anomalous in a short window",
                evidence={
                    "unstable_metrics": unstable_metrics,
                    "required_count": self._cfg.min_metric_instability_count,
                    "window_seconds": self._cfg.window_seconds,
                },
            )
            if hint is not None:
                hints.append(hint)

        if len(high_anomaly_metrics) >= 2:
            hint = self._make_hint(
                node_id=node_id,
                category="multi_metric_instability",
                confidence="low",
                timestamp_utc=timestamp_utc,
                message="Multiple metrics show anomaly behavior in the same time window",
                evidence={
                    "metrics": sorted([m for m in high_anomaly_metrics if m]),
                    "window_seconds": self._cfg.window_seconds,
                },
            )
            if hint is not None:
                hints.append(hint)

        # Optional LLM augmentation for deeper reasoning
        if self._llm and process_anomalies:
            try:
                llm_hints = self._build_llm_hints(node_id, timestamp_utc, queue)
                hints.extend(llm_hints)
            except Exception:
                pass  # Gracefully fall back to heuristics

        return hints

    def _build_llm_hints(
        self,
        node_id: str,
        timestamp_utc: str,
        signals: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Generate additional hints using LLM reasoning on signal data."""
        hints = []
        
        import json
        
        # Summarize signals for LLM
        summary = {
            "node_id": node_id,
            "signal_count": len(signals),
            "anomalies": [s for s in signals if s.get("kind") == "anomaly_score"],
            "changes": [s for s in signals if s.get("kind") == "change_event"],
        }
        
        prompt = f"""You are a system expert analyzing monitoring signals.
Node {node_id} has shown these signals:
Anomalies: {len(summary['anomalies'])} events
Changes: {len(summary['changes'])} events

Provide 1-2 concise root-cause hypotheses based on this signal pattern.
Keep responses short and actionable."""

        try:
            response = self._llm.generate(
                prompt,
                system_prompt="You are a system monitoring expert.",
                temperature=0.5,
                max_tokens=128,
            )
            
            if response and response.strip():
                hint = self._make_hint(
                    node_id=node_id,
                    category="llm_hypothesis",
                    confidence="low",
                    timestamp_utc=timestamp_utc,
                    message=response[:256],
                    evidence={"signal_summary": summary},
                )
                if hint:
                    hints.append(hint)
        except Exception:
            pass  # LLM is optional
        
        return hints


    def _make_hint(
        self,
        node_id: str,
        category: str,
        confidence: str,
        timestamp_utc: str,
        message: str,
        evidence: dict[str, Any],
    ) -> dict[str, Any] | None:
        now = _parse_timestamp(timestamp_utc)
        key = (node_id, category)
        last_at = self._last_hint_at.get(key)
        if last_at is not None and now - last_at < timedelta(seconds=self._cfg.cooldown_seconds):
            return None

        self._last_hint_at[key] = now
        return {
            "node_id": node_id,
            "category": category,
            "confidence": confidence,
            "timestamp_utc": timestamp_utc,
            "message": message,
            "evidence": evidence,
        }


def _parse_timestamp(timestamp_utc: str) -> datetime:
    try:
        return datetime.fromisoformat(timestamp_utc)
    except ValueError:
        return datetime.now().astimezone()
