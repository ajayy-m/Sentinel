from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class NodeSnapshot:
    process_count: int
    hostname: str
    os_name: str


class ChangeDetector:
    def __init__(self, process_count_delta_threshold: int = 25) -> None:
        self._process_threshold = process_count_delta_threshold
        self._snapshots: dict[str, NodeSnapshot] = {}

    def detect(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
        node = payload.get("node", {})
        metrics = payload.get("metrics", {})
        processes = metrics.get("processes", {})

        node_id = str(node.get("node_id", "unknown"))
        timestamp_utc = str(payload.get("timestamp_utc", "unknown"))
        hostname = str(node.get("hostname", "unknown"))
        os_name = str(node.get("os", "unknown"))
        process_count = int(float(processes.get("count", 0)))

        current = NodeSnapshot(
            process_count=process_count,
            hostname=hostname,
            os_name=os_name,
        )

        events: list[dict[str, Any]] = []
        previous = self._snapshots.get(node_id)

        if previous is None:
            events.append(
                {
                    "node_id": node_id,
                    "event_type": "node_first_seen",
                    "severity": "info",
                    "timestamp_utc": timestamp_utc,
                    "details": {
                        "hostname": hostname,
                        "os": os_name,
                        "process_count": process_count,
                    },
                }
            )
        else:
            if previous.hostname != current.hostname:
                events.append(
                    {
                        "node_id": node_id,
                        "event_type": "hostname_changed",
                        "severity": "warning",
                        "timestamp_utc": timestamp_utc,
                        "details": {
                            "old": previous.hostname,
                            "new": current.hostname,
                        },
                    }
                )

            if previous.os_name != current.os_name:
                events.append(
                    {
                        "node_id": node_id,
                        "event_type": "os_changed",
                        "severity": "warning",
                        "timestamp_utc": timestamp_utc,
                        "details": {
                            "old": previous.os_name,
                            "new": current.os_name,
                        },
                    }
                )

            delta = current.process_count - previous.process_count
            if abs(delta) >= self._process_threshold:
                events.append(
                    {
                        "node_id": node_id,
                        "event_type": "process_count_spike",
                        "severity": "warning",
                        "timestamp_utc": timestamp_utc,
                        "details": {
                            "previous": previous.process_count,
                            "current": current.process_count,
                            "delta": delta,
                            "threshold": self._process_threshold,
                        },
                    }
                )

        self._snapshots[node_id] = current
        return events
