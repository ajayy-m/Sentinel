from __future__ import annotations

import json
import logging
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Any

from sentinel.core.contracts import ACTION_RESULT_SCHEMA, ACTION_RESULT_SCHEMA_VERSION

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class ExecutionRecord:
    schema: str
    schema_version: str
    request_id: int
    node_id: str
    action_type: str
    backend: str
    status: str
    command: str
    rationale: str
    actor: str
    created_at_utc: str
    notes: str = ""


@dataclass
class ExecutionConfig:
    enabled: bool = False
    backend: str = "dry_run"
    queue_dir: str = "./data/executions"


class ActionExecutionPlanner:
    """Safe, opt-in remote action execution planner.

    This framework intentionally does not execute commands by default. It only
    creates durable execution plans for later dispatch by a backend adapter.
    """

    def __init__(self, cfg: ExecutionConfig) -> None:
        self._cfg = cfg
        self._queue_dir = Path(cfg.queue_dir)
        self._queue_dir.mkdir(parents=True, exist_ok=True)
        self._queue_file = self._queue_dir / "execution_queue.jsonl"

    @classmethod
    def from_config(cls, config: dict[str, Any]) -> "ActionExecutionPlanner":
        exec_cfg = config.get("execution", {})
        cfg = ExecutionConfig(
            enabled=bool(exec_cfg.get("enabled", False)),
            backend=str(exec_cfg.get("backend", "dry_run")),
            queue_dir=str(exec_cfg.get("queue_dir", "./data/executions")),
        )
        return cls(cfg)

    def plan_from_request(
        self,
        request: dict[str, Any],
        decision: dict[str, Any],
    ) -> ExecutionRecord | None:
        if not self._cfg.enabled:
            return None
        if not bool(decision.get("approved", False)):
            return None

        record = ExecutionRecord(
            schema=ACTION_RESULT_SCHEMA,
            schema_version=ACTION_RESULT_SCHEMA_VERSION,
            request_id=int(request.get("request_id", 0)),
            node_id=str(request.get("node_id", "unknown")),
            action_type=str(request.get("action_type", "unknown")),
            backend=self._cfg.backend,
            status="planned",
            command=str(request.get("command", "")),
            rationale=str(decision.get("rationale", "")),
            actor=str(decision.get("actor", "unknown")),
            created_at_utc=datetime.now().astimezone().isoformat(),
            notes="No command executed; execution planning only.",
        )
        self._append_record(record)
        return record

    def _append_record(self, record: ExecutionRecord) -> None:
        try:
            with self._queue_file.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(asdict(record), sort_keys=True) + "\n")
        except Exception:
            LOGGER.exception("Failed to persist execution record")

    def list_records(self, limit: int = 50) -> list[ExecutionRecord]:
        if not self._queue_file.exists():
            return []

        lines = self._queue_file.read_text(encoding="utf-8").splitlines()
        records: list[ExecutionRecord] = []
        for line in lines[-max(1, int(limit)) :]:
            try:
                data = json.loads(line)
                data.setdefault("schema", ACTION_RESULT_SCHEMA)
                data.setdefault("schema_version", ACTION_RESULT_SCHEMA_VERSION)
                data.setdefault("notes", "")
                records.append(ExecutionRecord(**data))
            except Exception:
                continue
        return records
