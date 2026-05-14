from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any
import json

from sentinel.core.contracts import ACTION_REQUEST_SCHEMA, ACTION_REQUEST_SCHEMA_VERSION


@dataclass(frozen=True)
class ActionRequest:
    node_id: str
    category: str
    action_type: str
    title: str
    description: str
    command: str
    risk_level: str
    source_category: str
    source_timestamp_utc: str
    evidence: dict[str, Any] = field(default_factory=dict)
    execution_mode: str = "approval_required"


@dataclass(frozen=True)
class ApprovalDecision:
    request_id: int
    approved: bool
    actor: str
    timestamp_utc: str
    rationale: str = ""
    execution_mode: str = "manual_review"


@dataclass
class GateConfig:
    request_cooldown_seconds: int = 30
    auto_promote_recommendations: bool = False


class ApprovalGate:
    def __init__(self, cfg: GateConfig) -> None:
        self._cfg = cfg
        self._last_request_at: dict[tuple[str, str], datetime] = {}
        self._request_counter = 0

    @classmethod
    def from_config(cls, config: dict[str, Any]) -> "ApprovalGate":
        gate_cfg = config.get("approval_gate", {})
        cfg = GateConfig(
            request_cooldown_seconds=max(5, int(gate_cfg.get("request_cooldown_seconds", 30))),
            auto_promote_recommendations=bool(gate_cfg.get("auto_promote_recommendations", False)),
        )
        return cls(cfg)

    def build_request_from_recommendation(
        self,
        recommendation: dict[str, Any],
        command: str,
        action_type: str,
        risk_level: str = "medium",
    ) -> ActionRequest | None:
        node_id = str(recommendation.get("node_id", "unknown"))
        category = str(recommendation.get("category", "general"))
        now = _parse_timestamp(str(recommendation.get("timestamp_utc", "")))

        key = (node_id, action_type)
        last_at = self._last_request_at.get(key)
        if last_at is not None and now - last_at < timedelta(seconds=self._cfg.request_cooldown_seconds):
            return None

        self._last_request_at[key] = now
        self._request_counter += 1

        return ActionRequest(
            node_id=node_id,
            category=category,
            action_type=action_type,
            title=str(recommendation.get("title", "Action requires approval")),
            description=str(recommendation.get("rationale", "")),
            command=command,
            risk_level=risk_level,
            source_category=category,
            source_timestamp_utc=str(recommendation.get("timestamp_utc", "unknown")),
            evidence=dict(recommendation.get("evidence", {})),
            execution_mode="approval_required",
        )

    def to_record(self, request: ActionRequest) -> dict[str, Any]:
        return {
            "schema": ACTION_REQUEST_SCHEMA,
            "schema_version": ACTION_REQUEST_SCHEMA_VERSION,
            "node_id": request.node_id,
            "category": request.category,
            "action_type": request.action_type,
            "title": request.title,
            "description": request.description,
            "command": request.command,
            "risk_level": request.risk_level,
            "source_category": request.source_category,
            "source_timestamp_utc": request.source_timestamp_utc,
            "evidence_json": json.dumps(request.evidence, sort_keys=True),
            "execution_mode": request.execution_mode,
        }

    def approve(self, request_id: int, actor: str, rationale: str = "") -> ApprovalDecision:
        return ApprovalDecision(
            request_id=request_id,
            approved=True,
            actor=actor,
            timestamp_utc=_utc_now(),
            rationale=rationale,
        )

    def reject(self, request_id: int, actor: str, rationale: str = "") -> ApprovalDecision:
        return ApprovalDecision(
            request_id=request_id,
            approved=False,
            actor=actor,
            timestamp_utc=_utc_now(),
            rationale=rationale,
        )


def _parse_timestamp(value: str) -> datetime:
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return datetime.now().astimezone()


def _utc_now() -> str:
    return datetime.now().astimezone().isoformat()
