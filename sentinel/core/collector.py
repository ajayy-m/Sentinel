from __future__ import annotations

import json
import logging
import time
from typing import Any

import msgpack
import zmq
from sentinel.core.anomaly import RollingAnomalyScorer
from sentinel.core.change_detector import ChangeDetector
from sentinel.core.pipeline import MetricPipeline
from sentinel.core.recommendations import RecommendationEngine
from sentinel.core.root_cause import RootCauseCorrelator
try:
    from sentinel.core.prometheus import record_collector_metrics, start_prometheus_exporter
except Exception:  # pragma: no cover - optional exporter
    def start_prometheus_exporter(config: dict[str, Any]):
        return None

    def record_collector_metrics(*, active_nodes: int = 0, discovered_nodes: int = 0, received_payloads: int = 0, dropped_new_nodes: int = 0, detected_events: int = 0, anomaly_count: int = 0, root_cause_hint_count: int = 0, recommendation_count: int = 0, latest_health_score: int = 0, payload: Any | None = None):
        return None
from sentinel.core.notifications import WebhookNotifier
from sentinel.core.storage import Storage
from sentinel.discovery import CollectorDiscoveryResponder, discover_nodes
from sentinel.core.preflight import run_preflight_checks

LOGGER = logging.getLogger(__name__)


def _apply_anomaly_impact_to_summary(
    summary: dict[str, Any], anomaly_scores: list[dict[str, Any]]
) -> dict[str, Any]:
    if not anomaly_scores:
        return summary

    result = dict(summary)
    reasons = list(result.get("reasons", []))
    score = int(result.get("score", 100))
    status = str(result.get("status", "healthy"))

    critical_count = sum(1 for item in anomaly_scores if item.get("severity") == "critical")
    warning_count = sum(1 for item in anomaly_scores if item.get("severity") == "warning")
    total_count = len(anomaly_scores)

    penalty = min(70, critical_count * 25 + warning_count * 10)
    score = max(0, score - penalty)

    if critical_count > 0:
        status = "critical"
    elif warning_count > 0 and status == "healthy":
        status = "warning"

    reasons.append(
        "anomaly_impact: "
        f"critical={critical_count}, warning={warning_count}, total={total_count}, penalty={penalty}"
    )

    result["score"] = score
    result["status"] = status
    result["reasons"] = reasons
    return result


class PullServer:
    def __init__(self, endpoint: str, receive_timeout_ms: int = 1000) -> None:
        self._context = zmq.Context.instance()
        self._socket = self._context.socket(zmq.PULL)
        self._socket.setsockopt(zmq.RCVTIMEO, receive_timeout_ms)
        self._socket.bind(endpoint)

    def receive(self) -> dict[str, Any] | None:
        try:
            raw = self._socket.recv()
        except zmq.Again:
            return None

        return msgpack.unpackb(raw, raw=False)

    def close(self) -> None:
        self._socket.close(linger=0)


def run_collector(config: dict[str, Any]) -> None:
    # Preflight checks: validate environment before starting
    run_preflight_checks(config)
    
    endpoint = config["transport"]["endpoint"]
    receive_timeout_ms = int(config.get("transport", {}).get("receive_timeout_ms", 1000))
    collector_cfg = config.get("collector", {})
    print_payload = bool(collector_cfg.get("print_payload", True))
    max_nodes_soft = int(collector_cfg.get("max_nodes_soft", 20))
    max_nodes_hard = int(collector_cfg.get("max_nodes_hard", 50))
    hard_limit_mode = str(collector_cfg.get("hard_limit_mode", "warn")).lower()
    storage_enabled = bool(collector_cfg.get("storage_enabled", True))
    sqlite_path = str(collector_cfg.get("sqlite_path", "./data/sentinel.db"))
    process_count_delta_threshold = int(collector_cfg.get("process_count_delta_threshold", 25))

    if max_nodes_soft < 1:
        raise ValueError("collector.max_nodes_soft must be >= 1")
    if max_nodes_hard < max_nodes_soft:
        raise ValueError("collector.max_nodes_hard must be >= collector.max_nodes_soft")
    if hard_limit_mode not in {"warn", "block"}:
        raise ValueError("collector.hard_limit_mode must be 'warn' or 'block'")

    server = PullServer(endpoint=endpoint, receive_timeout_ms=receive_timeout_ms)
    storage = Storage(sqlite_path) if storage_enabled else None
    detector = ChangeDetector(process_count_delta_threshold=process_count_delta_threshold)
    pipeline = MetricPipeline.from_config(config)
    anomaly_scorer = RollingAnomalyScorer.from_config(config)
    root_cause = RootCauseCorrelator.from_config(config)
    recommendation_engine = RecommendationEngine.from_config(config)
    discovery_responder = CollectorDiscoveryResponder.from_config(config)
    discovery_scan_seconds = float(collector_cfg.get("discovery_scan_seconds", 15.0))
    last_discovery_scan = 0.0
    prometheus_cfg = start_prometheus_exporter(config)
    webhook_notifier = WebhookNotifier.from_config(config)

    LOGGER.info(
        "Collector listening endpoint=%s soft_limit=%d hard_limit=%d hard_mode=%s storage=%s",
        endpoint,
        max_nodes_soft,
        max_nodes_hard,
        hard_limit_mode,
        sqlite_path if storage is not None else "disabled",
    )
    if prometheus_cfg is not None:
        LOGGER.info(
            "Prometheus exporter enabled host=%s port=%d",
            prometheus_cfg.host,
            prometheus_cfg.port,
        )

    active_nodes: set[str] = set()
    received_payloads = 0
    dropped_new_nodes = 0
    detected_events = 0
    anomaly_count = 0
    root_cause_hint_count = 0
    recommendation_count = 0
    discovered_nodes: set[str] = set()

    def _register_node(node_id: str) -> bool:
        if node_id in active_nodes:
            return True

        projected_count = len(active_nodes) + 1

        if projected_count > max_nodes_hard:
            if hard_limit_mode == "block":
                LOGGER.error(
                    "Hard node limit reached (%d). Blocking new node_id=%s",
                    max_nodes_hard,
                    node_id,
                )
                return False

            LOGGER.warning(
                "Hard node limit exceeded (%d). Allowing node_id=%s because hard_limit_mode=warn",
                max_nodes_hard,
                node_id,
            )

        if projected_count > max_nodes_soft:
            LOGGER.warning(
                "Soft node limit exceeded (%d). Active nodes now: %d",
                max_nodes_soft,
                projected_count,
            )

        active_nodes.add(node_id)
        LOGGER.info("Registered node_id=%s total_active_nodes=%d", node_id, len(active_nodes))
        return True

    def _record_discovered_node(node: dict[str, Any]) -> None:
        node_id = str(node.get("node_id", "unknown"))
        if not node_id or node_id in discovered_nodes:
            return
        discovered_nodes.add(node_id)
        _register_node(node_id)
        LOGGER.info(
            "Discovered node_id=%s hostname=%s os=%s",
            node_id,
            node.get("hostname", "unknown"),
            node.get("os", "unknown"),
        )
        if storage is not None:
            storage.store_discovery_event(
                {
                    "node_id": node_id,
                    "hostname": str(node.get("hostname", "unknown")),
                    "os_name": str(node.get("os", "unknown")),
                    "platform": str(node.get("platform", "unknown")),
                    "timestamp_utc": "auto-discovery",
                }
            )

    try:
        while True:
            if discovery_responder is not None:
                discovery_responder.poll()

            now = time.monotonic()
            if now - last_discovery_scan >= discovery_scan_seconds:
                last_discovery_scan = now
                for node in discover_nodes(config):
                    _record_discovered_node(node)

            payload = server.receive()
            if payload is None:
                continue

            node_id = payload.get("node", {}).get("node_id", "unknown")
            timestamp = payload.get("timestamp_utc", "unknown")

            # Count and gate new nodes dynamically based on runtime configuration.
            if not _register_node(str(node_id)):
                dropped_new_nodes += 1
                record_collector_metrics(
                    active_nodes=len(active_nodes),
                    discovered_nodes=len(discovered_nodes),
                    received_payloads=0,
                    dropped_new_nodes=1,
                )
                continue

            received_payloads += 1
            LOGGER.info("Received metric payload node_id=%s timestamp=%s", node_id, timestamp)

            events = detector.detect(payload)
            for event in events:
                detected_events += 1
                LOGGER.warning(
                    "Change detected node_id=%s event_type=%s severity=%s",
                    event.get("node_id", "unknown"),
                    event.get("event_type", "unknown"),
                    event.get("severity", "info"),
                )
                if storage is not None:
                    storage.store_change_event(event)

            summary, alerts = pipeline.evaluate(payload)

            for alert in alerts:
                LOGGER.warning(
                    "Alert generated node_id=%s severity=%s category=%s message=%s",
                    alert.get("node_id", "unknown"),
                    alert.get("severity", "warning"),
                    alert.get("category", "general"),
                    alert.get("message", ""),
                )
                if storage is not None:
                    storage.store_alert(alert)
                if webhook_notifier is not None:
                    webhook_notifier.notify("alert", alert)

            trend_summary, anomaly_scores = anomaly_scorer.evaluate(payload)
            if storage is not None:
                storage.store_trend_summary(trend_summary)

            for anomaly in anomaly_scores:
                anomaly_count += 1
                LOGGER.warning(
                    "Anomaly score node_id=%s metric=%s severity=%s score=%s",
                    anomaly.get("node_id", "unknown"),
                    anomaly.get("metric", "unknown"),
                    anomaly.get("severity", "warning"),
                    anomaly.get("score", 0),
                )
                if storage is not None:
                    storage.store_anomaly_score(anomaly)
                    storage.store_alert(
                        {
                            "node_id": anomaly.get("node_id", "unknown"),
                            "severity": anomaly.get("severity", "warning"),
                            "category": "anomaly",
                            "timestamp_utc": anomaly.get("timestamp_utc", "unknown"),
                            "message": f"Anomaly detected for {anomaly.get('metric', 'unknown')}",
                            "details": anomaly.get("details", {}),
                        }
                    )

            summary = _apply_anomaly_impact_to_summary(summary, anomaly_scores)
            if storage is not None:
                storage.store_health_summary(summary)

            hints = root_cause.correlate(
                node_id=str(node_id),
                timestamp_utc=str(timestamp),
                change_events=events,
                anomaly_scores=anomaly_scores,
            )
            for hint in hints:
                root_cause_hint_count += 1
                LOGGER.warning(
                    "Root cause hint node_id=%s category=%s confidence=%s message=%s",
                    hint.get("node_id", "unknown"),
                    hint.get("category", "unknown"),
                    hint.get("confidence", "low"),
                    hint.get("message", ""),
                )
                if storage is not None:
                    storage.store_root_cause_hint(hint)

            recommendations = recommendation_engine.recommend(
                node_id=str(node_id),
                timestamp_utc=str(timestamp),
                alerts=alerts + [
                    {
                        "node_id": anomaly.get("node_id", "unknown"),
                        "severity": anomaly.get("severity", "warning"),
                        "category": "anomaly",
                        "timestamp_utc": anomaly.get("timestamp_utc", "unknown"),
                        "message": f"Anomaly detected for {anomaly.get('metric', 'unknown')}",
                        "details": anomaly.get("details", {}),
                    }
                    for anomaly in anomaly_scores
                ],
                root_cause_hints=hints,
            )
            for recommendation in recommendations:
                recommendation_count += 1
                LOGGER.warning(
                    "Recommendation node_id=%s category=%s priority=%s title=%s",
                    recommendation.get("node_id", "unknown"),
                    recommendation.get("category", "general"),
                    recommendation.get("priority", "low"),
                    recommendation.get("title", ""),
                )
                if storage is not None:
                    storage.store_action_recommendation(recommendation)
                if webhook_notifier is not None:
                    webhook_notifier.notify("recommendation", recommendation)

            if storage is not None:
                storage.store_payload(payload)

            record_collector_metrics(
                active_nodes=len(active_nodes),
                discovered_nodes=len(discovered_nodes),
                received_payloads=1,
                detected_events=len(events),
                anomaly_count=len(anomaly_scores),
                root_cause_hint_count=len(hints),
                recommendation_count=len(recommendations),
                latest_health_score=int(summary.get("score", 0)),
                payload=payload,
            )

            if received_payloads % 25 == 0:
                LOGGER.info(
                    "Collector status payloads=%d active_nodes=%d dropped_new_nodes=%d detected_events=%d anomalies=%d root_cause_hints=%d recommendations=%d",
                    received_payloads,
                    len(active_nodes),
                    dropped_new_nodes,
                    detected_events,
                    anomaly_count,
                    root_cause_hint_count,
                    recommendation_count,
                )

            if print_payload:
                print(json.dumps(payload, indent=2, sort_keys=True))
    except KeyboardInterrupt:
        LOGGER.info("Collector shutdown requested")
    finally:
        server.close()
        if discovery_responder is not None:
            discovery_responder.close()
        if storage is not None:
            storage.close()
