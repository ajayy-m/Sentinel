from __future__ import annotations

import json
from typing import Any

from sentinel.core.storage import Storage


def _compact_payload(payload: dict[str, Any]) -> dict[str, Any]:
    metrics = payload.get("metrics", {})
    return {
        "timestamp_utc": payload.get("timestamp_utc", "unknown"),
        "node": payload.get("node", {}),
        "cpu_usage_percent": float(metrics.get("cpu", {}).get("usage_percent", 0.0)),
        "memory_usage_percent": float(metrics.get("memory", {}).get("usage_percent", 0.0)),
        "disk_usage_percent": float(metrics.get("disk", {}).get("root_usage_percent", 0.0)),
        "process_count": float(metrics.get("processes", {}).get("count", 0.0)),
    }


def run_report(
    config: dict[str, Any],
    node_id: str | None = None,
    limit: int = 5,
    summary_only: bool = False,
    compact_payloads: bool = False,
) -> None:
    collector_cfg = config.get("collector", {})
    sqlite_path = str(collector_cfg.get("sqlite_path", "./data/sentinel.db"))

    storage = Storage(sqlite_path)
    try:
        recent_payloads = storage.get_recent_payloads(limit=limit, node_id=node_id)
        recent_change_events = storage.get_recent_change_events(limit=limit, node_id=node_id)
        recent_health_summaries = storage.get_recent_health_summaries(limit=limit, node_id=node_id)
        recent_alerts = storage.get_recent_alerts(limit=limit, node_id=node_id)
        recent_trend_summaries = storage.get_recent_trend_summaries(limit=limit, node_id=node_id)
        recent_anomaly_scores = storage.get_recent_anomaly_scores(limit=limit, node_id=node_id)
        recent_root_cause_hints = storage.get_recent_root_cause_hints(limit=limit, node_id=node_id)
        recent_action_recommendations = storage.get_recent_action_recommendations(
            limit=limit, node_id=node_id
        )
        recent_action_requests = storage.get_recent_action_requests(limit=limit, node_id=node_id)
        recent_approval_decisions = storage.get_recent_approval_decisions(limit=limit)

        if compact_payloads:
            recent_payloads = [_compact_payload(item) for item in recent_payloads]

        if summary_only:
            summary: dict[str, Any] = {
                "sqlite_path": sqlite_path,
                "active_node_count": storage.get_active_node_count(),
                "counts": {
                    "recent_payloads": len(recent_payloads),
                    "recent_change_events": len(recent_change_events),
                    "recent_health_summaries": len(recent_health_summaries),
                    "recent_alerts": len(recent_alerts),
                    "recent_trend_summaries": len(recent_trend_summaries),
                    "recent_anomaly_scores": len(recent_anomaly_scores),
                    "recent_root_cause_hints": len(recent_root_cause_hints),
                    "recent_action_recommendations": len(recent_action_recommendations),
                    "recent_action_requests": len(recent_action_requests),
                    "recent_approval_decisions": len(recent_approval_decisions),
                },
                "latest": {
                    "payload": _compact_payload(recent_payloads[0]) if recent_payloads else None,
                    "health_summary": recent_health_summaries[0] if recent_health_summaries else None,
                    "alert": recent_alerts[0] if recent_alerts else None,
                    "anomaly_score": recent_anomaly_scores[0] if recent_anomaly_scores else None,
                    "root_cause_hint": recent_root_cause_hints[0] if recent_root_cause_hints else None,
                    "action_recommendation": (
                        recent_action_recommendations[0] if recent_action_recommendations else None
                    ),
                    "action_request": recent_action_requests[0] if recent_action_requests else None,
                    "approval_decision": recent_approval_decisions[0] if recent_approval_decisions else None,
                },
            }
            print(json.dumps(summary, indent=2, sort_keys=True))
            return

        summary: dict[str, Any] = {
            "sqlite_path": sqlite_path,
            "active_node_count": storage.get_active_node_count(),
            "recent_payloads": recent_payloads,
            "recent_change_events": recent_change_events,
            "recent_health_summaries": recent_health_summaries,
            "recent_alerts": recent_alerts,
            "recent_trend_summaries": recent_trend_summaries,
            "recent_anomaly_scores": recent_anomaly_scores,
            "recent_root_cause_hints": recent_root_cause_hints,
            "recent_action_recommendations": recent_action_recommendations,
            "recent_action_requests": recent_action_requests,
            "recent_approval_decisions": recent_approval_decisions,
        }
        print(json.dumps(summary, indent=2, sort_keys=True))
    finally:
        storage.close()
