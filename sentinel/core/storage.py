from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any


class Storage:
    def __init__(self, database_path: str) -> None:
        self._db_path = Path(database_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self._db_path)
        self._conn.execute("PRAGMA journal_mode=WAL;")
        self._create_tables()

    def _create_tables(self) -> None:
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS metric_payloads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                node_id TEXT NOT NULL,
                timestamp_utc TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                created_at_utc TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
            )
            """
        )
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS change_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                node_id TEXT NOT NULL,
                event_type TEXT NOT NULL,
                severity TEXT NOT NULL,
                timestamp_utc TEXT NOT NULL,
                details_json TEXT NOT NULL,
                created_at_utc TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
            )
            """
        )
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS node_discoveries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                node_id TEXT NOT NULL,
                hostname TEXT NOT NULL,
                os_name TEXT NOT NULL,
                platform TEXT NOT NULL,
                timestamp_utc TEXT NOT NULL,
                created_at_utc TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
            )
            """
        )
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS health_summaries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                node_id TEXT NOT NULL,
                status TEXT NOT NULL,
                score INTEGER NOT NULL,
                timestamp_utc TEXT NOT NULL,
                reasons_json TEXT NOT NULL,
                created_at_utc TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
            )
            """
        )
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                node_id TEXT NOT NULL,
                severity TEXT NOT NULL,
                category TEXT NOT NULL,
                timestamp_utc TEXT NOT NULL,
                message TEXT NOT NULL,
                details_json TEXT NOT NULL,
                created_at_utc TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
            )
            """
        )
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS trend_summaries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                node_id TEXT NOT NULL,
                timestamp_utc TEXT NOT NULL,
                summary_json TEXT NOT NULL,
                created_at_utc TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
            )
            """
        )
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS anomaly_scores (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                node_id TEXT NOT NULL,
                metric TEXT NOT NULL,
                severity TEXT NOT NULL,
                score INTEGER NOT NULL,
                timestamp_utc TEXT NOT NULL,
                details_json TEXT NOT NULL,
                created_at_utc TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
            )
            """
        )
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS root_cause_hints (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                node_id TEXT NOT NULL,
                category TEXT NOT NULL,
                confidence TEXT NOT NULL,
                timestamp_utc TEXT NOT NULL,
                message TEXT NOT NULL,
                evidence_json TEXT NOT NULL,
                created_at_utc TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
            )
            """
        )
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS llm_queries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                question TEXT NOT NULL,
                response TEXT NOT NULL,
                node_id TEXT,
                metadata_json TEXT NOT NULL,
                timestamp_utc TEXT NOT NULL,
                created_at_utc TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
            )
            """
        )
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS llm_query_feedback (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                query_id INTEGER NOT NULL,
                helpful INTEGER NOT NULL,
                note TEXT,
                actor TEXT,
                timestamp_utc TEXT NOT NULL,
                created_at_utc TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
            )
            """
        )
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS action_recommendations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                node_id TEXT NOT NULL,
                category TEXT NOT NULL,
                priority TEXT NOT NULL,
                timestamp_utc TEXT NOT NULL,
                title TEXT NOT NULL,
                rationale TEXT NOT NULL,
                suggested_actions_json TEXT NOT NULL,
                evidence_json TEXT NOT NULL,
                execution_mode TEXT NOT NULL,
                created_at_utc TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
            )
            """
        )
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS action_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                node_id TEXT NOT NULL,
                category TEXT NOT NULL,
                action_type TEXT NOT NULL,
                title TEXT NOT NULL,
                description TEXT NOT NULL,
                command TEXT NOT NULL,
                risk_level TEXT NOT NULL,
                source_category TEXT NOT NULL,
                source_timestamp_utc TEXT NOT NULL,
                evidence_json TEXT NOT NULL,
                execution_mode TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at_utc TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
            )
            """
        )
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS approval_decisions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                request_id INTEGER NOT NULL,
                actor TEXT NOT NULL,
                approved INTEGER NOT NULL,
                rationale TEXT NOT NULL,
                timestamp_utc TEXT NOT NULL,
                execution_mode TEXT NOT NULL,
                created_at_utc TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
            )
            """
        )
        self._create_audit_immutability_guards()
        self._conn.commit()

    def _create_audit_immutability_guards(self) -> None:
        # Audit-critical tables are append-only; block in-place edits and deletes.
        self._conn.execute(
            """
            CREATE TRIGGER IF NOT EXISTS trg_block_update_action_requests
            BEFORE UPDATE ON action_requests
            BEGIN
                SELECT RAISE(ABORT, 'action_requests is append-only');
            END;
            """
        )
        self._conn.execute(
            """
            CREATE TRIGGER IF NOT EXISTS trg_block_delete_action_requests
            BEFORE DELETE ON action_requests
            BEGIN
                SELECT RAISE(ABORT, 'action_requests is append-only');
            END;
            """
        )
        self._conn.execute(
            """
            CREATE TRIGGER IF NOT EXISTS trg_block_update_approval_decisions
            BEFORE UPDATE ON approval_decisions
            BEGIN
                SELECT RAISE(ABORT, 'approval_decisions is append-only');
            END;
            """
        )
        self._conn.execute(
            """
            CREATE TRIGGER IF NOT EXISTS trg_block_delete_approval_decisions
            BEFORE DELETE ON approval_decisions
            BEGIN
                SELECT RAISE(ABORT, 'approval_decisions is append-only');
            END;
            """
        )

    def store_payload(self, payload: dict[str, Any]) -> None:
        node_id = str(payload.get("node", {}).get("node_id", "unknown"))
        timestamp_utc = str(payload.get("timestamp_utc", "unknown"))
        payload_json = json.dumps(payload, sort_keys=True)

        self._conn.execute(
            """
            INSERT INTO metric_payloads (node_id, timestamp_utc, payload_json)
            VALUES (?, ?, ?)
            """,
            (node_id, timestamp_utc, payload_json),
        )
        self._conn.commit()

    def store_change_event(self, event: dict[str, Any]) -> None:
        self._conn.execute(
            """
            INSERT INTO change_events (node_id, event_type, severity, timestamp_utc, details_json)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                str(event.get("node_id", "unknown")),
                str(event.get("event_type", "unknown")),
                str(event.get("severity", "info")),
                str(event.get("timestamp_utc", "unknown")),
                json.dumps(event.get("details", {}), sort_keys=True),
            ),
        )
        self._conn.commit()

    def store_discovery_event(self, discovery: dict[str, Any]) -> None:
        self._conn.execute(
            """
            INSERT INTO node_discoveries (node_id, hostname, os_name, platform, timestamp_utc)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                str(discovery.get("node_id", "unknown")),
                str(discovery.get("hostname", "unknown")),
                str(discovery.get("os_name", "unknown")),
                str(discovery.get("platform", "unknown")),
                str(discovery.get("timestamp_utc", "unknown")),
            ),
        )
        self._conn.commit()

    def store_health_summary(self, summary: dict[str, Any]) -> None:
        self._conn.execute(
            """
            INSERT INTO health_summaries (node_id, status, score, timestamp_utc, reasons_json)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                str(summary.get("node_id", "unknown")),
                str(summary.get("status", "healthy")),
                int(summary.get("score", 100)),
                str(summary.get("timestamp_utc", "unknown")),
                json.dumps(summary.get("reasons", []), sort_keys=True),
            ),
        )
        self._conn.commit()

    def store_alert(self, alert: dict[str, Any]) -> None:
        self._conn.execute(
            """
            INSERT INTO alerts (node_id, severity, category, timestamp_utc, message, details_json)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                str(alert.get("node_id", "unknown")),
                str(alert.get("severity", "info")),
                str(alert.get("category", "general")),
                str(alert.get("timestamp_utc", "unknown")),
                str(alert.get("message", "")),
                json.dumps(alert.get("details", {}), sort_keys=True),
            ),
        )
        self._conn.commit()

    def store_trend_summary(self, summary: dict[str, Any]) -> None:
        self._conn.execute(
            """
            INSERT INTO trend_summaries (node_id, timestamp_utc, summary_json)
            VALUES (?, ?, ?)
            """,
            (
                str(summary.get("node_id", "unknown")),
                str(summary.get("timestamp_utc", "unknown")),
                json.dumps(summary, sort_keys=True),
            ),
        )
        self._conn.commit()

    def store_anomaly_score(self, anomaly: dict[str, Any]) -> None:
        self._conn.execute(
            """
            INSERT INTO anomaly_scores (node_id, metric, severity, score, timestamp_utc, details_json)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                str(anomaly.get("node_id", "unknown")),
                str(anomaly.get("metric", "unknown")),
                str(anomaly.get("severity", "warning")),
                int(anomaly.get("score", 0)),
                str(anomaly.get("timestamp_utc", "unknown")),
                json.dumps(anomaly.get("details", {}), sort_keys=True),
            ),
        )
        self._conn.commit()

    def store_root_cause_hint(self, hint: dict[str, Any]) -> None:
        self._conn.execute(
            """
            INSERT INTO root_cause_hints (node_id, category, confidence, timestamp_utc, message, evidence_json)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                str(hint.get("node_id", "unknown")),
                str(hint.get("category", "unknown")),
                str(hint.get("confidence", "low")),
                str(hint.get("timestamp_utc", "unknown")),
                str(hint.get("message", "")),
                json.dumps(hint.get("evidence", {}), sort_keys=True),
            ),
        )
        self._conn.commit()

    def store_llm_query(self, question: str, response: str, node_id: str | None = None, metadata: dict[str, Any] | None = None, timestamp_utc: str | None = None) -> None:
        ts = timestamp_utc or str(metadata.get("timestamp_utc")) if metadata else "unknown"
        self._conn.execute(
            """
            INSERT INTO llm_queries (question, response, node_id, metadata_json, timestamp_utc)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                str(question),
                str(response),
                str(node_id) if node_id is not None else None,
                json.dumps(metadata or {}, sort_keys=True),
                str(timestamp_utc) if timestamp_utc is not None else ts,
            ),
        )
        self._conn.commit()

    def get_recent_llm_queries(self, limit: int = 20) -> list[dict[str, Any]]:
        cursor = self._conn.execute(
            "SELECT id, question, response, node_id, metadata_json, timestamp_utc FROM llm_queries ORDER BY id DESC LIMIT ?",
            (limit,),
        )
        rows = []
        for r in cursor.fetchall():
            rows.append(
                {
                    "id": r[0],
                    "question": r[1],
                    "response": r[2],
                    "node_id": r[3],
                    "metadata": json.loads(r[4]) if r[4] else {},
                    "timestamp_utc": r[5],
                }
            )
        return rows

    def store_llm_feedback(self, query_id: int, helpful: bool, note: str | None = None, actor: str | None = None, timestamp_utc: str | None = None) -> None:
        ts = timestamp_utc or "unknown"
        self._conn.execute(
            """
            INSERT INTO llm_query_feedback (query_id, helpful, note, actor, timestamp_utc)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                int(query_id),
                1 if helpful else 0,
                str(note) if note is not None else "",
                str(actor) if actor is not None else "",
                str(ts),
            ),
        )
        self._conn.commit()

    def store_action_recommendation(self, recommendation: dict[str, Any]) -> None:
        self._conn.execute(
            """
            INSERT INTO action_recommendations (
                node_id, category, priority, timestamp_utc, title, rationale,
                suggested_actions_json, evidence_json, execution_mode
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(recommendation.get("node_id", "unknown")),
                str(recommendation.get("category", "general")),
                str(recommendation.get("priority", "low")),
                str(recommendation.get("timestamp_utc", "unknown")),
                str(recommendation.get("title", "")),
                str(recommendation.get("rationale", "")),
                json.dumps(recommendation.get("suggested_actions", []), sort_keys=True),
                json.dumps(recommendation.get("evidence", {}), sort_keys=True),
                str(recommendation.get("execution_mode", "recommendation_only")),
            ),
        )
        self._conn.commit()

    def create_action_request(self, request: dict[str, Any], status: str = "pending") -> int:
        cursor = self._conn.execute(
            """
            INSERT INTO action_requests (
                node_id, category, action_type, title, description, command,
                risk_level, source_category, source_timestamp_utc, evidence_json,
                execution_mode, status
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(request.get("node_id", "unknown")),
                str(request.get("category", "general")),
                str(request.get("action_type", "general")),
                str(request.get("title", "")),
                str(request.get("description", "")),
                str(request.get("command", "")),
                str(request.get("risk_level", "medium")),
                str(request.get("source_category", "general")),
                str(request.get("source_timestamp_utc", "unknown")),
                json.dumps(request.get("evidence", {}), sort_keys=True),
                str(request.get("execution_mode", "approval_required")),
                status,
            ),
        )
        self._conn.commit()
        return int(cursor.lastrowid)

    def store_approval_decision(self, decision: dict[str, Any]) -> None:
        self._conn.execute(
            """
            INSERT INTO approval_decisions (
                request_id, actor, approved, rationale, timestamp_utc, execution_mode
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                int(decision.get("request_id", 0)),
                str(decision.get("actor", "unknown")),
                1 if bool(decision.get("approved", False)) else 0,
                str(decision.get("rationale", "")),
                str(decision.get("timestamp_utc", "unknown")),
                str(decision.get("execution_mode", "manual_review")),
            ),
        )
        self._conn.commit()

    def get_recent_payloads(self, limit: int = 10, node_id: str | None = None) -> list[dict[str, Any]]:
        safe_limit = max(1, int(limit))

        if node_id:
            cursor = self._conn.execute(
                """
                SELECT payload_json
                FROM metric_payloads
                WHERE node_id = ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (node_id, safe_limit),
            )
        else:
            cursor = self._conn.execute(
                """
                SELECT payload_json
                FROM metric_payloads
                ORDER BY id DESC
                LIMIT ?
                """,
                (safe_limit,),
            )

        rows = cursor.fetchall()
        return [json.loads(row[0]) for row in rows]

    def get_discovered_nodes(self, limit: int = 100) -> list[dict[str, Any]]:
        safe_limit = max(1, int(limit))
        cursor = self._conn.execute(
            """
            SELECT node_id, hostname, os_name, platform, timestamp_utc
            FROM node_discoveries
            WHERE node_id NOT LIKE ?
            ORDER BY id DESC
            LIMIT ?
            """,
            ('%-sim-%', safe_limit),
        )
        rows = cursor.fetchall()
        return [
            {
                "node_id": row[0],
                "hostname": row[1],
                "os_name": row[2],
                "platform": row[3],
                "timestamp_utc": row[4],
            }
            for row in rows
        ]

    def get_recent_change_events(self, limit: int = 10, node_id: str | None = None) -> list[dict[str, Any]]:
        safe_limit = max(1, int(limit))

        if node_id:
            cursor = self._conn.execute(
                """
                SELECT node_id, event_type, severity, timestamp_utc, details_json
                FROM change_events
                WHERE node_id = ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (node_id, safe_limit),
            )
        else:
            cursor = self._conn.execute(
                """
                SELECT node_id, event_type, severity, timestamp_utc, details_json
                FROM change_events
                WHERE node_id NOT LIKE ?
                ORDER BY id DESC
                LIMIT ?
                """,
                ('%-sim-%', safe_limit),
            )

        rows = cursor.fetchall()
        return [
            {
                "node_id": row[0],
                "event_type": row[1],
                "severity": row[2],
                "timestamp_utc": row[3],
                "details": json.loads(row[4]),
            }
            for row in rows
        ]

    def get_recent_health_summaries(
        self, limit: int = 10, node_id: str | None = None
    ) -> list[dict[str, Any]]:
        safe_limit = max(1, int(limit))

        if node_id:
            cursor = self._conn.execute(
                """
                SELECT node_id, status, score, timestamp_utc, reasons_json
                FROM health_summaries
                WHERE node_id = ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (node_id, safe_limit),
            )
        else:
            cursor = self._conn.execute(
                """
                SELECT node_id, status, score, timestamp_utc, reasons_json
                FROM health_summaries
                WHERE node_id NOT LIKE ?
                ORDER BY id DESC
                LIMIT ?
                """,
                ('%-sim-%', safe_limit),
            )

        rows = cursor.fetchall()
        return [
            {
                "node_id": row[0],
                "status": row[1],
                "score": row[2],
                "timestamp_utc": row[3],
                "reasons": json.loads(row[4]),
            }
            for row in rows
        ]

    def get_recent_alerts(self, limit: int = 10, node_id: str | None = None) -> list[dict[str, Any]]:
        safe_limit = max(1, int(limit))

        if node_id:
            cursor = self._conn.execute(
                """
                SELECT node_id, severity, category, timestamp_utc, message, details_json
                FROM alerts
                WHERE node_id = ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (node_id, safe_limit),
            )
        else:
            cursor = self._conn.execute(
                """
                SELECT node_id, severity, category, timestamp_utc, message, details_json
                FROM alerts
                WHERE node_id NOT LIKE ?
                ORDER BY id DESC
                LIMIT ?
                """,
                ('%-sim-%', safe_limit),
            )

        rows = cursor.fetchall()
        return [
            {
                "node_id": row[0],
                "severity": row[1],
                "category": row[2],
                "timestamp_utc": row[3],
                "message": row[4],
                "details": json.loads(row[5]),
            }
            for row in rows
        ]

    def get_recent_trend_summaries(
        self, limit: int = 10, node_id: str | None = None
    ) -> list[dict[str, Any]]:
        safe_limit = max(1, int(limit))

        if node_id:
            cursor = self._conn.execute(
                """
                SELECT summary_json
                FROM trend_summaries
                WHERE node_id = ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (node_id, safe_limit),
            )
        else:
            cursor = self._conn.execute(
                """
                SELECT summary_json
                FROM trend_summaries
                WHERE node_id NOT LIKE ?
                ORDER BY id DESC
                LIMIT ?
                """,
                ('%-sim-%', safe_limit),
            )

        rows = cursor.fetchall()
        return [json.loads(row[0]) for row in rows]

    def get_recent_anomaly_scores(
        self, limit: int = 10, node_id: str | None = None
    ) -> list[dict[str, Any]]:
        safe_limit = max(1, int(limit))

        if node_id:
            cursor = self._conn.execute(
                """
                SELECT node_id, metric, severity, score, timestamp_utc, details_json
                FROM anomaly_scores
                WHERE node_id = ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (node_id, safe_limit),
            )
        else:
            cursor = self._conn.execute(
                """
                SELECT node_id, metric, severity, score, timestamp_utc, details_json
                FROM anomaly_scores
                WHERE node_id NOT LIKE ?
                ORDER BY id DESC
                LIMIT ?
                """,
                ('%-sim-%', safe_limit),
            )

        rows = cursor.fetchall()
        return [
            {
                "node_id": row[0],
                "metric": row[1],
                "severity": row[2],
                "score": row[3],
                "timestamp_utc": row[4],
                "details": json.loads(row[5]),
            }
            for row in rows
        ]

    def get_recent_root_cause_hints(
        self, limit: int = 10, node_id: str | None = None
    ) -> list[dict[str, Any]]:
        safe_limit = max(1, int(limit))

        if node_id:
            cursor = self._conn.execute(
                """
                SELECT node_id, category, confidence, timestamp_utc, message, evidence_json
                FROM root_cause_hints
                WHERE node_id = ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (node_id, safe_limit),
            )
        else:
            cursor = self._conn.execute(
                """
                SELECT node_id, category, confidence, timestamp_utc, message, evidence_json
                FROM root_cause_hints
                WHERE category != ?
                  AND node_id NOT LIKE ?
                ORDER BY id DESC
                LIMIT ?
                """,
                ('llm_query', '%-sim-%', safe_limit),
            )

        rows = cursor.fetchall()
        return [
            {
                "node_id": row[0],
                "category": row[1],
                "confidence": row[2],
                "timestamp_utc": row[3],
                "message": row[4],
                "evidence": json.loads(row[5]),
            }
            for row in rows
        ]

    def get_recent_action_recommendations(
        self, limit: int = 10, node_id: str | None = None
    ) -> list[dict[str, Any]]:
        safe_limit = max(1, int(limit))

        if node_id:
            cursor = self._conn.execute(
                """
                SELECT node_id, category, priority, timestamp_utc, title, rationale,
                       suggested_actions_json, evidence_json, execution_mode
                FROM action_recommendations
                WHERE node_id = ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (node_id, safe_limit),
            )
        else:
            cursor = self._conn.execute(
                """
                SELECT node_id, category, priority, timestamp_utc, title, rationale,
                       suggested_actions_json, evidence_json, execution_mode
                FROM action_recommendations
                WHERE node_id NOT LIKE ?
                ORDER BY id DESC
                LIMIT ?
                """,
                ('%-sim-%', safe_limit),
            )

        rows = cursor.fetchall()
        return [
            {
                "node_id": row[0],
                "category": row[1],
                "priority": row[2],
                "timestamp_utc": row[3],
                "title": row[4],
                "rationale": row[5],
                "suggested_actions": json.loads(row[6]),
                "evidence": json.loads(row[7]),
                "execution_mode": row[8],
            }
            for row in rows
        ]

    def get_recent_action_requests(
        self, limit: int = 10, node_id: str | None = None, status: str | None = None
    ) -> list[dict[str, Any]]:
        safe_limit = max(1, int(limit))
        clauses: list[str] = []
        params: list[Any] = []

        if node_id:
            clauses.append("node_id = ?")
            params.append(node_id)
        if status:
            clauses.append("status = ?")
            params.append(status)

        where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        query = f"""
            SELECT id, node_id, category, action_type, title, description, command,
                   risk_level, source_category, source_timestamp_utc, evidence_json,
                   execution_mode, status
            FROM action_requests
            {where_sql}
            ORDER BY id DESC
            LIMIT ?
        """
        params.append(safe_limit)
        cursor = self._conn.execute(query, tuple(params))
        rows = cursor.fetchall()
        return [
            {
                "request_id": row[0],
                "node_id": row[1],
                "category": row[2],
                "action_type": row[3],
                "title": row[4],
                "description": row[5],
                "command": row[6],
                "risk_level": row[7],
                "source_category": row[8],
                "source_timestamp_utc": row[9],
                "evidence": json.loads(row[10]),
                "execution_mode": row[11],
                "status": row[12],
            }
            for row in rows
        ]

    def get_recent_approval_decisions(self, limit: int = 10) -> list[dict[str, Any]]:
        safe_limit = max(1, int(limit))
        cursor = self._conn.execute(
            """
            SELECT request_id, actor, approved, rationale, timestamp_utc, execution_mode
            FROM approval_decisions
            ORDER BY id DESC
            LIMIT ?
            """,
            (safe_limit,),
        )
        rows = cursor.fetchall()
        return [
            {
                "request_id": row[0],
                "actor": row[1],
                "approved": bool(row[2]),
                "rationale": row[3],
                "timestamp_utc": row[4],
                "execution_mode": row[5],
            }
            for row in rows
        ]

    def get_active_node_count(self) -> int:
        cursor = self._conn.execute(
            """
            SELECT COUNT(DISTINCT node_id)
            FROM (
                SELECT node_id FROM metric_payloads WHERE node_id NOT LIKE ?
                UNION
                SELECT node_id FROM node_discoveries WHERE node_id NOT LIKE ?
            )
            """,
            ('%-sim-%', '%-sim-%'),
        )
        row = cursor.fetchone()
        return int(row[0]) if row is not None and row[0] is not None else 0

    def purge_before(self, before_date: str, dry_run: bool = True) -> dict[str, int]:
        """
        Purge records older than before_date (YYYY-MM-DD) from non-audit tables.

        Audit tables remain immutable and are excluded from this operation.
        Returns per-table affected row counts.
        """
        tables = [
            "metric_payloads",
            "health_summaries",
            "alerts",
            "anomaly_scores",
            "root_cause_hints",
            "action_recommendations",
            "node_discoveries",
            "change_events",
            "trend_summaries",
        ]

        result: dict[str, int] = {}
        for table in tables:
            cursor = self._conn.execute(
                f"SELECT COUNT(*) FROM {table} WHERE datetime(created_at_utc) < datetime(?)",
                (before_date,),
            )
            row = cursor.fetchone()
            count = int(row[0]) if row is not None and row[0] is not None else 0
            result[table] = count

            if not dry_run and count > 0:
                self._conn.execute(
                    f"DELETE FROM {table} WHERE datetime(created_at_utc) < datetime(?)",
                    (before_date,),
                )

        if not dry_run:
            self._conn.commit()

        result["total"] = sum(result.values())
        return result

    def close(self) -> None:
        self._conn.close()
