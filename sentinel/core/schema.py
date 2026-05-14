"""
Schema versioning and validation for Sentinel payloads.

All data payloads must include a version field for forward/backward compatibility.
"""

from __future__ import annotations

from typing import Any

# Current protocol versions
SCHEMA_VERSION = "1.0"
PROTOCOL_VERSION = "1.0"

# Compatibility rules:
# - Agent sends SCHEMA_VERSION 1.0; Collector must accept >= 1.0
# - Payload changes must be additive (new fields, not removed/renamed)
# - Breaking changes require new major version (2.0, etc.)


def validate_payload_schema(payload: dict[str, Any]) -> tuple[bool, str]:
    """
    Validate payload schema and return (is_valid, error_message).
    
    Required fields:
    - schema: name (e.g., "metric_payload")
    - protocol_version: version string
    - node: node info dict
    - timestamp_utc: ISO timestamp
    - metrics: dict of metric categories
    """
    schema_name = payload.get("schema", "")
    if not schema_name:
        return False, "Missing 'schema' field"

    protocol_version = payload.get("protocol_version", "")
    if not protocol_version:
        return False, "Missing 'protocol_version' field"

    if not _version_compatible(protocol_version, PROTOCOL_VERSION):
        return False, f"Protocol version {protocol_version} not compatible with {PROTOCOL_VERSION}"

    if not payload.get("node"):
        return False, "Missing 'node' dict"

    node_id = payload.get("node", {}).get("node_id", "")
    if not node_id:
        return False, "Missing node.node_id"

    if not payload.get("timestamp_utc"):
        return False, "Missing 'timestamp_utc'"

    if not payload.get("metrics"):
        return False, "Missing 'metrics' dict"

    return True, ""


def _version_compatible(agent_version: str, collector_version: str) -> bool:
    """
    Check if agent protocol version is compatible with collector version.
    
    Rule: Same major version is compatible (1.0 compatible with 1.x)
    Different major versions are not compatible.
    """
    try:
        agent_parts = agent_version.split(".")
        collector_parts = collector_version.split(".")
        # Compare major version (first part)
        return agent_parts[0] == collector_parts[0]
    except (AttributeError, IndexError):
        return False


def document_payload_schema() -> str:
    """Return the canonical schema documentation."""
    return f"""
# Sentinel Payload Schema v{SCHEMA_VERSION}

## Metric Payload

{{
  "schema": "metric_payload",
  "protocol_version": "{PROTOCOL_VERSION}",
  "node": {{
    "node_id": "hostname-<hash>",
    "hostname": "...",
    "os": "Linux|Windows",
    "platform": "..."
  }},
  "timestamp_utc": "ISO8601 timestamp",
  "metrics": {{
    "cpu": {{ "usage_percent": 45.2, "load_avg": [1.2, 1.5, 1.1] }},
    "memory": {{ "usage_percent": 65.0 }},
    "disk": {{ "root_usage_percent": 72.3 }},
    "network": {{ "bytes_sent": 12345, "bytes_recv": 54321 }},
    "processes": {{ "count": 256 }}
  }}
}}

## Compatibility Policy

- Schema version {SCHEMA_VERSION} is the current standard.
- Protocol version {PROTOCOL_VERSION} must match between agent and collector on major version.
- New fields added to metrics are compatible (backward compatible).
- Renamed or removed fields require version bump.

## Change Events

Collector emits change events when node state changes (new process, service state change, etc.).

## Alerts

Threshold-based alerts (CPU > 95%, etc.) and anomalies are emitted as Alert records.

## Recommendations

AI-derived action recommendations are stored separately and require human promotion to action requests.

## Action Requests

Explicit action requests (service restart, kill process, etc.) with risk levels and exact commands.

## Approval Decisions

Human approval/rejection decisions stored immutably with actor, rationale, timestamp.
"""
