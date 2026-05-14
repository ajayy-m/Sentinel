from __future__ import annotations

import logging
import platform
import socket
import time
from datetime import UTC, datetime
from typing import Any

from sentinel.agent.collectors.cpu import collect_cpu
from sentinel.agent.collectors.disk import collect_disk
from sentinel.agent.collectors.gpu import collect_gpu
from sentinel.agent.collectors.memory import collect_memory
from sentinel.agent.collectors.network import collect_network
from sentinel.agent.collectors.processes import collect_processes
from sentinel.core.identity import resolve_node_id
from sentinel.discovery import AgentDiscoveryResponder, discover_collector, discover_collectors
from sentinel.agent.transport import PushClient
from sentinel.core.preflight import run_preflight_checks

LOGGER = logging.getLogger(__name__)


def _build_metrics() -> dict[str, Any]:
    return {
        "cpu": collect_cpu(),
        "gpu": collect_gpu(),
        "memory": collect_memory(),
        "disk": collect_disk(),
        "network": collect_network(),
        "processes": collect_processes(),
    }


def _build_payload(config: dict[str, Any]) -> dict[str, Any]:
    node_id = resolve_node_id(config)
    return {
        "schema": "metric_payload",
        "protocol_version": config["system"]["protocol_version"],
        "node": {
            "node_id": node_id,
            "hostname": socket.gethostname(),
            "os": platform.system(),
            "platform": platform.platform(),
        },
        "timestamp_utc": datetime.now(UTC).isoformat(),
        "metrics": _build_metrics(),
    }


def run_agent(config: dict[str, Any]) -> None:
    # Preflight checks: validate environment before starting
    run_preflight_checks(config)
    
    interval_seconds = float(config.get("agent", {}).get("interval_seconds", 2))
    send_timeout_ms = int(config.get("transport", {}).get("send_timeout_ms", 1000))
    discovery_cfg = config.get("transport", {}).get("discovery", {})
    discovery_retry_seconds = float(discovery_cfg.get("retry_seconds", 5.0))
    # If an endpoint is configured, we'll use it; otherwise attempt network discovery.
    fallback_endpoint = str(config.get("transport", {}).get("endpoint", "")).strip()
    configured_collectors = config.get("transport", {}).get("collector_endpoints") or config.get("transport", {}).get("endpoints")
    node_id = resolve_node_id(config)
    node_info = {
        "node_id": node_id,
        "hostname": socket.gethostname(),
        "os": platform.system(),
        "platform": platform.platform(),
    }

    client: PushClient | None = None
    current_endpoint = ""
    collector_candidates: list[str] = []
    collector_index = 0
    discovery_responder = AgentDiscoveryResponder.from_config(config, node_info=node_info)

    def _normalize_endpoints(value: Any) -> list[str]:
        if isinstance(value, str):
            value = [value]
        if isinstance(value, list):
            endpoints = [str(item).strip() for item in value if str(item).strip()]
            return list(dict.fromkeys(endpoints))
        return []

    def _refresh_collectors() -> list[str]:
        explicit = _normalize_endpoints(configured_collectors)
        if explicit:
            return explicit
        if fallback_endpoint:
            return [fallback_endpoint]
        return discover_collectors(config)

    def _resolve_endpoint() -> str | None:
        # Prefer explicit endpoint if provided
        if fallback_endpoint:
            return fallback_endpoint
        # Otherwise attempt network discovery (discover_collector will use sensible defaults)
        return discover_collector(config)

    auto_discovery = not bool(fallback_endpoint)
    LOGGER.info("Agent started for node_id=%s auto_discovery=%s", node_id, auto_discovery)

    last_metrics = None

    try:
        while True:
            if discovery_responder is not None:
                discovery_responder.poll()

            if client is None:
                if not collector_candidates:
                    collector_candidates = _refresh_collectors()
                    collector_index = 0

                if collector_candidates:
                    current_endpoint = collector_candidates[collector_index % len(collector_candidates)]
                else:
                    current_endpoint = _resolve_endpoint() or ""

                if not current_endpoint:
                    LOGGER.info("Collector not discovered yet; will retry in %.1fs", discovery_retry_seconds)
                    time.sleep(max(0.5, discovery_retry_seconds))
                    continue

                client = PushClient(endpoint=current_endpoint, send_timeout_ms=send_timeout_ms)
                LOGGER.info(
                    "Agent connected to collector endpoint=%s node_id=%s",
                    current_endpoint,
                    node_id,
                )

            # Build metrics and optionally compute deltas for diagnostics
            metrics = {
                "cpu": collect_cpu(),
                "gpu": collect_gpu(),
                "memory": collect_memory(),
                "disk": collect_disk(),
                "network": collect_network(),
                "processes": collect_processes(),
            }

            # Compute simple deltas for cumulative counters when diagnostic enabled
            diagnostic_enabled = bool(config.get("agent", {}).get("diagnostic", False))
            if diagnostic_enabled and 'last_metrics' in locals() and last_metrics is not None:
                try:
                    d_read = metrics["disk"].get("read_bytes", 0.0) - last_metrics["disk"].get("read_bytes", 0.0)
                    d_write = metrics["disk"].get("write_bytes", 0.0) - last_metrics["disk"].get("write_bytes", 0.0)
                    metrics["disk"]["read_bytes_delta"] = float(d_read)
                    metrics["disk"]["write_bytes_delta"] = float(d_write)

                    n_sent = metrics["network"].get("bytes_sent", 0.0) - last_metrics["network"].get("bytes_sent", 0.0)
                    n_recv = metrics["network"].get("bytes_recv", 0.0) - last_metrics["network"].get("bytes_recv", 0.0)
                    metrics["network"]["bytes_sent_delta"] = float(n_sent)
                    metrics["network"]["bytes_recv_delta"] = float(n_recv)
                except Exception:
                    # Best-effort diagnostics; do not fail the main loop
                    LOGGER.debug("Failed computing diagnostic deltas", exc_info=True)

            # persist last metrics for next iteration
            last_metrics = metrics

            payload = {
                "schema": "metric_payload",
                "protocol_version": config["system"]["protocol_version"],
                "node": {
                    "node_id": node_id,
                    "hostname": socket.gethostname(),
                    "os": platform.system(),
                    "platform": platform.platform(),
                },
                "timestamp_utc": datetime.now(UTC).isoformat(),
                "metrics": metrics,
            }
            try:
                client.send(payload)
                LOGGER.info("Sent metric payload at %s", payload["timestamp_utc"])
            except Exception as exc:
                LOGGER.warning("Send failed to %s: %s", current_endpoint, exc)
                client.close()
                client = None
                if collector_candidates:
                    collector_index = (collector_index + 1) % len(collector_candidates)
                    if collector_index == 0:
                        collector_candidates = _refresh_collectors()
                else:
                    collector_candidates = _refresh_collectors()
                    collector_index = 0
                time.sleep(max(0.5, discovery_retry_seconds))
                continue

            time.sleep(interval_seconds)
    except KeyboardInterrupt:
        LOGGER.info("Agent shutdown requested")
    finally:
        if discovery_responder is not None:
            discovery_responder.close()
        if client is not None:
            client.close()
