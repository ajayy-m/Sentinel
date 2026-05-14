from __future__ import annotations

import json
import logging
import socket
import time
from typing import Any

LOGGER = logging.getLogger(__name__)

DISCOVERY_MAGIC = "sentinel-discovery-v1"
DEFAULT_COLLECTOR_DISCOVERY_PORT = 37020
DEFAULT_AGENT_DISCOVERY_PORT = 37021


def _safe_json_loads(raw: bytes) -> dict[str, Any] | None:
    try:
        decoded = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    return decoded if isinstance(decoded, dict) else None


def _transport_discovery_config(config: dict[str, Any]) -> dict[str, Any]:
    return config.get("transport", {}).get("discovery", {})


def _collector_port(config: dict[str, Any]) -> int:
    discovery_cfg = _transport_discovery_config(config)
    return int(discovery_cfg.get("collector_port", DEFAULT_COLLECTOR_DISCOVERY_PORT))


def _agent_port(config: dict[str, Any]) -> int:
    discovery_cfg = _transport_discovery_config(config)
    return int(discovery_cfg.get("agent_port", DEFAULT_AGENT_DISCOVERY_PORT))


def _collectors_from_config(config: dict[str, Any]) -> list[str]:
    transport_cfg = config.get("transport", {})
    configured = transport_cfg.get("collector_endpoints") or transport_cfg.get("endpoints")
    if isinstance(configured, str):
        configured = [configured]
    if isinstance(configured, list):
        endpoints = [str(item).strip() for item in configured if str(item).strip()]
        return list(dict.fromkeys(endpoints))
    return []


class _BaseDiscoverySocket:
    def __init__(self, port: int) -> None:
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._socket.bind(("0.0.0.0", port))
        self._socket.setblocking(False)

    def close(self) -> None:
        self._socket.close()


class CollectorDiscoveryResponder(_BaseDiscoverySocket):
    def __init__(self, endpoint: str, protocol_version: str, port: int) -> None:
        super().__init__(port)
        self._endpoint = endpoint
        self._protocol_version = protocol_version

    @classmethod
    def from_config(cls, config: dict[str, Any]) -> "CollectorDiscoveryResponder | None":
        discovery_cfg = _transport_discovery_config(config)
        if not bool(discovery_cfg.get("enabled", False)):
            return None
        return cls(
            endpoint=str(config.get("transport", {}).get("endpoint", "")),
            protocol_version=str(config.get("system", {}).get("protocol_version", "1.0")),
            port=_collector_port(config),
        )

    def poll(self) -> int:
        handled = 0
        while True:
            try:
                raw, addr = self._socket.recvfrom(4096)
            except BlockingIOError:
                break
            except OSError:
                break

            message = _safe_json_loads(raw)
            if not message or message.get("magic") != DISCOVERY_MAGIC:
                continue
            if message.get("type") != "discover_collector":
                continue

            response = json.dumps(
                {
                    "magic": DISCOVERY_MAGIC,
                    "type": "collector_response",
                    "protocol_version": self._protocol_version,
                    "endpoint": self._endpoint,
                }
            ).encode("utf-8")

            try:
                self._socket.sendto(response, addr)
                handled += 1
            except OSError:
                LOGGER.debug("Collector discovery response failed for %s", addr)

        return handled


class AgentDiscoveryResponder(_BaseDiscoverySocket):
    def __init__(self, node_info: dict[str, Any], port: int) -> None:
        super().__init__(port)
        self._node_info = node_info

    @classmethod
    def from_config(cls, config: dict[str, Any], node_info: dict[str, Any]) -> "AgentDiscoveryResponder | None":
        discovery_cfg = _transport_discovery_config(config)
        if not bool(discovery_cfg.get("enabled", False)):
            return None
        return cls(node_info=node_info, port=_agent_port(config))

    def poll(self) -> int:
        handled = 0
        while True:
            try:
                raw, addr = self._socket.recvfrom(4096)
            except BlockingIOError:
                break
            except OSError:
                break

            message = _safe_json_loads(raw)
            if not message or message.get("magic") != DISCOVERY_MAGIC:
                continue
            if message.get("type") != "discover_nodes":
                continue

            response = json.dumps(
                {
                    "magic": DISCOVERY_MAGIC,
                    "type": "node_response",
                    "node": self._node_info,
                }
            ).encode("utf-8")

            try:
                self._socket.sendto(response, addr)
                handled += 1
            except OSError:
                LOGGER.debug("Agent discovery response failed for %s", addr)

        return handled


def discover_collector(config: dict[str, Any]) -> str | None:
    collectors = discover_collectors(config)
    return collectors[0] if collectors else None


def discover_collectors(config: dict[str, Any]) -> list[str]:
    transport_cfg = config.get("transport", {})

    configured_collectors = _collectors_from_config(config)
    if configured_collectors:
        return configured_collectors

    # If an endpoint is explicitly configured, prefer it and skip network discovery.
    endpoint_cfg = str(transport_cfg.get("endpoint", "")).strip()
    if endpoint_cfg:
        return [endpoint_cfg]

    port = _collector_port(config)
    discovery_cfg = _transport_discovery_config(config)
    # Use discovery config when present, otherwise fall back to sensible defaults
    broadcast_address = str(discovery_cfg.get("broadcast_address", "255.255.255.255"))
    timeout_seconds = float(discovery_cfg.get("timeout_seconds", 1.0))
    attempts = max(1, int(discovery_cfg.get("attempts", 3)))
    protocol_version = str(config.get("system", {}).get("protocol_version", "1.0"))
    node_id = str(config.get("system", {}).get("node_id", "unknown"))

    request = json.dumps(
        {
            "magic": DISCOVERY_MAGIC,
            "type": "discover_collector",
            "protocol_version": protocol_version,
            "node_id": node_id,
        }
    ).encode("utf-8")

    # Create a UDP socket and allow broadcasts; bind to all interfaces
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.settimeout(max(0.05, timeout_seconds))
        sock.bind(("0.0.0.0", 0))

        discovered: list[str] = []
        for _ in range(attempts):
            try:
                sock.sendto(request, (broadcast_address, port))
            except OSError:
                LOGGER.debug("Discovery broadcast failed")
                continue

            deadline = time.monotonic() + timeout_seconds
            while time.monotonic() < deadline:
                try:
                    raw, _ = sock.recvfrom(4096)
                except OSError:
                    break

                response = _safe_json_loads(raw)
                if not response:
                    continue
                if response.get("magic") != DISCOVERY_MAGIC:
                    continue
                if response.get("type") != "collector_response":
                    continue

                endpoint = str(response.get("endpoint", "")).strip()
                if endpoint and endpoint not in discovered:
                    discovered.append(endpoint)

        return discovered
    finally:
        sock.close()


def discover_nodes(config: dict[str, Any]) -> list[dict[str, Any]]:
    transport_cfg = config.get("transport", {})
    discovery_cfg = _transport_discovery_config(config)
    if not bool(discovery_cfg.get("enabled", False)):
        return []

    port = _agent_port(config)
    broadcast_address = str(discovery_cfg.get("broadcast_address", "255.255.255.255"))
    timeout_seconds = float(discovery_cfg.get("scan_timeout_seconds", 0.25))
    attempts = max(1, int(discovery_cfg.get("scan_attempts", 2)))
    max_responses = max(1, int(discovery_cfg.get("max_scan_responses", 256)))
    protocol_version = str(config.get("system", {}).get("protocol_version", "1.0"))

    request = json.dumps(
        {
            "magic": DISCOVERY_MAGIC,
            "type": "discover_nodes",
            "protocol_version": protocol_version,
            "collector_endpoint": str(transport_cfg.get("endpoint", "")),
        }
    ).encode("utf-8")

    discovered: dict[str, dict[str, Any]] = {}
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.settimeout(timeout_seconds)
        sock.bind(("", 0))

        for _ in range(attempts):
            try:
                sock.sendto(request, (broadcast_address, port))
            except OSError:
                LOGGER.debug("Node discovery broadcast failed")
                continue

            while len(discovered) < max_responses:
                try:
                    raw, _ = sock.recvfrom(4096)
                except OSError:
                    break

                response = _safe_json_loads(raw)
                if not response:
                    continue
                if response.get("magic") != DISCOVERY_MAGIC:
                    continue
                if response.get("type") != "node_response":
                    continue

                node = response.get("node")
                if isinstance(node, dict):
                    node_id = str(node.get("node_id", "unknown"))
                    if node_id:
                        discovered[node_id] = node
    finally:
        sock.close()

    return list(discovered.values())
