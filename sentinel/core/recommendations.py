from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any


@dataclass
class RecommendationConfig:
    cooldown_seconds: int = 30


class RecommendationEngine:
    def __init__(self, cfg: RecommendationConfig) -> None:
        self._cfg = cfg
        self._last_recommendation_at: dict[tuple[str, str], datetime] = {}

    @classmethod
    def from_config(cls, config: dict[str, Any]) -> "RecommendationEngine":
        rcfg = config.get("recommendations", {})
        cfg = RecommendationConfig(cooldown_seconds=max(5, int(rcfg.get("cooldown_seconds", 30))))
        return cls(cfg)

    def recommend(
        self,
        node_id: str,
        timestamp_utc: str,
        alerts: list[dict[str, Any]],
        root_cause_hints: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        recommendations: list[dict[str, Any]] = []

        severe_alerts = [a for a in alerts if a.get("severity") in {"warning", "critical"}]
        anomaly_alerts = [a for a in severe_alerts if a.get("category") == "anomaly"]

        if anomaly_alerts:
            rec = self._make_recommendation(
                node_id=node_id,
                category="observe_and_investigate",
                priority="medium",
                timestamp_utc=timestamp_utc,
                title="Investigate recurring anomaly window",
                rationale="Anomaly alerts are recurring; gather short diagnostic snapshot before remediation.",
                suggested_actions=[
                    "Review top CPU/memory/process consumers on the node",
                    "Compare process list against previous baseline",
                    "Check recent service restarts or deployments",
                ],
                evidence={"anomaly_alert_count": len(anomaly_alerts)},
            )
            if rec is not None:
                recommendations.append(rec)

        if any(h.get("category") == "metric_recurrence" for h in root_cause_hints):
            rec = self._make_recommendation(
                node_id=node_id,
                category="stabilize_metric_drift",
                priority="medium",
                timestamp_utc=timestamp_utc,
                title="Stabilize recurrent metric drift",
                rationale="Root-cause correlator found repeated anomalies across one or more metrics.",
                suggested_actions=[
                    "Validate scheduled tasks and background job timing",
                    "Increase sampling window for confirmation",
                    "Prepare reversible mitigation if pattern persists",
                ],
                evidence={
                    "root_cause_categories": [h.get("category", "unknown") for h in root_cause_hints],
                },
            )
            if rec is not None:
                recommendations.append(rec)

        return recommendations

    def _make_recommendation(
        self,
        node_id: str,
        category: str,
        priority: str,
        timestamp_utc: str,
        title: str,
        rationale: str,
        suggested_actions: list[str],
        evidence: dict[str, Any],
    ) -> dict[str, Any] | None:
        now = _parse_timestamp(timestamp_utc)
        key = (node_id, category)
        last_at = self._last_recommendation_at.get(key)
        if last_at is not None and now - last_at < timedelta(seconds=self._cfg.cooldown_seconds):
            return None

        self._last_recommendation_at[key] = now
        return {
            "node_id": node_id,
            "category": category,
            "priority": priority,
            "timestamp_utc": timestamp_utc,
            "title": title,
            "rationale": rationale,
            "suggested_actions": suggested_actions,
            "evidence": evidence,
            "execution_mode": "recommendation_only",
        }


def _parse_timestamp(timestamp_utc: str) -> datetime:
    try:
        return datetime.fromisoformat(timestamp_utc)
    except ValueError:
        return datetime.now().astimezone()
