from __future__ import annotations

from typing import Any

ACTION_REQUEST_SCHEMA = "action_request"
ACTION_REQUEST_SCHEMA_VERSION = "1.0"
ACTION_RESULT_SCHEMA = "action_result"
ACTION_RESULT_SCHEMA_VERSION = "1.0"


def validate_action_request_contract(record: dict[str, Any]) -> tuple[bool, str]:
    if record.get("schema") != ACTION_REQUEST_SCHEMA:
        return False, f"Expected schema={ACTION_REQUEST_SCHEMA}"
    if str(record.get("schema_version", "")) != ACTION_REQUEST_SCHEMA_VERSION:
        return False, f"Expected action request schema_version={ACTION_REQUEST_SCHEMA_VERSION}"

    required_fields = ("node_id", "category", "action_type", "title", "command", "risk_level")
    for field in required_fields:
        if not str(record.get(field, "")).strip():
            return False, f"Missing action request field: {field}"

    return True, ""


def validate_action_result_contract(record: dict[str, Any]) -> tuple[bool, str]:
    if record.get("schema") != ACTION_RESULT_SCHEMA:
        return False, f"Expected schema={ACTION_RESULT_SCHEMA}"
    if str(record.get("schema_version", "")) != ACTION_RESULT_SCHEMA_VERSION:
        return False, f"Expected action result schema_version={ACTION_RESULT_SCHEMA_VERSION}"

    required_fields = ("request_id", "status", "backend", "command", "created_at_utc")
    for field in required_fields:
        if str(record.get(field, "")).strip() == "":
            return False, f"Missing action result field: {field}"

    return True, ""
