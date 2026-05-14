from __future__ import annotations

import logging
import random
import time
from datetime import UTC, datetime
from typing import Any

from sentinel.agent.transport import PushClient
from sentinel.core.identity import resolve_node_id

LOGGER = logging.getLogger(__name__)


def _build_synthetic_payload(config: dict[str, Any], node_id: str) -> dict[str, Any]:
    cpu = random.uniform(5.0, 98.0)
    memory = random.uniform(10.0, 97.0)
    disk = random.uniform(20.0, 95.0)

    return {
        "schema": "metric_payload",
        "protocol_version": config["system"]["protocol_version"],
        "node": {
            "node_id": node_id,
            "hostname": f"{node_id}-host",
            "os": "Linux",
            "platform": "synthetic",
        },
        "timestamp_utc": datetime.now(UTC).isoformat(),
        "metrics": {
            "cpu": {
                "usage_percent": cpu,
                "load_avg_1m": round(cpu / 25.0, 2),
            },
            "memory": {
                "total_bytes": float(16 * 1024 * 1024 * 1024),
                "used_bytes": float((memory / 100.0) * 16 * 1024 * 1024 * 1024),
                "available_bytes": float((1 - (memory / 100.0)) * 16 * 1024 * 1024 * 1024),
                "usage_percent": memory,
            },
            "disk": {
                "root_total_bytes": float(512 * 1024 * 1024 * 1024),
                "root_used_bytes": float((disk / 100.0) * 512 * 1024 * 1024 * 1024),
                "root_usage_percent": disk,
                "read_bytes": float(random.randint(10_000_000, 80_000_000)),
                "write_bytes": float(random.randint(5_000_000, 50_000_000)),
            },
            "network": {
                "bytes_sent": float(random.randint(1_000_000, 20_000_000)),
                "bytes_recv": float(random.randint(1_000_000, 25_000_000)),
                "packets_sent": float(random.randint(20_000, 90_000)),
                "packets_recv": float(random.randint(20_000, 90_000)),
            },
            "processes": {
                "count": float(random.randint(90, 260)),
            },
        },
    }


def run_simulator(
    config: dict[str, Any],
    nodes: int,
    interval_seconds: float,
    duration_seconds: int,
) -> None:
    endpoint = config["transport"]["endpoint"]
    send_timeout_ms = int(config.get("transport", {}).get("send_timeout_ms", 1000))
    node_count = max(1, min(200, int(nodes)))
    base_id = resolve_node_id(config)
    node_ids = [f"{base_id}-sim-{i:02d}" for i in range(1, node_count + 1)]

    client = PushClient(endpoint=endpoint, send_timeout_ms=send_timeout_ms)
    LOGGER.info(
        "Simulator started endpoint=%s nodes=%d interval=%.2fs duration=%ss",
        endpoint,
        node_count,
        interval_seconds,
        duration_seconds,
    )

    started = time.time()
    sent_payloads = 0

    try:
        while True:
            elapsed = time.time() - started
            if duration_seconds > 0 and elapsed >= duration_seconds:
                break

            timestamp = datetime.now(UTC).isoformat()
            for node_id in node_ids:
                payload = _build_synthetic_payload(config, node_id)
                payload["timestamp_utc"] = timestamp
                client.send(payload)
                sent_payloads += 1

            if sent_payloads % (node_count * 5) == 0:
                LOGGER.info("Simulator sent payloads=%d", sent_payloads)

            time.sleep(max(0.1, float(interval_seconds)))
    except KeyboardInterrupt:
        LOGGER.info("Simulator shutdown requested")
    finally:
        client.close()
        LOGGER.info("Simulator stopped payloads_sent=%d", sent_payloads)
