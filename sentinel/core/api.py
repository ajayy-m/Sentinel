from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any
from urllib.parse import parse_qs, urlparse

from sentinel.ai.llm import OllamaClient
from sentinel.core.storage import Storage

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class ApiConfig:
    enabled: bool = True
    host: str = "127.0.0.1"
    port: int = 8085


class _SentinelApiHandler(BaseHTTPRequestHandler):
    sqlite_path: str = "./data/sentinel.db"
    max_rows: int = 20
    llm_config: dict[str, Any] = {}

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        query = parse_qs(parsed.query)
        limit = max(1, int(query.get("limit", [str(self.max_rows)])[0]))
        node_id = query.get("node_id", [""])[0].strip() or None

        if parsed.path == "/health":
            self._send_json(200, self._build_health_summary(limit=limit))
            return
        if parsed.path == "/alerts":
            self._send_json(200, self._load_rows("alerts", limit=limit, node_id=node_id))
            return
        if parsed.path == "/recommendations":
            self._send_json(200, self._load_rows("recommendations", limit=limit, node_id=node_id))
            return
        if parsed.path == "/requests":
            self._send_json(200, self._load_rows("requests", limit=limit, node_id=node_id))
            return
        if parsed.path == "/decisions":
            self._send_json(200, self._load_rows("decisions", limit=limit, node_id=node_id))
            return
        if parsed.path == "/nodes":
            self._send_json(200, self._load_rows("nodes", limit=limit, node_id=node_id))
            return
        if parsed.path == "/summary":
            self._send_json(200, self._build_health_summary(limit=limit, include_rows=True))
            return

        self._send_json(404, {"error": "not_found", "paths": ["/health", "/alerts", "/recommendations", "/requests", "/decisions", "/nodes", "/summary"]})

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        
        if parsed.path == "/llm/query":
            content_length = int(self.headers.get("Content-Length", 0))
            try:
                body = self.rfile.read(content_length).decode("utf-8")
                data = json.loads(body)
                question = data.get("question", "").strip()
                if not question:
                    self._send_json(400, {"error": "missing_question"})
                    return
                response = self._handle_llm_query(question)
                self._send_json(200, {"response": response})
            except json.JSONDecodeError:
                self._send_json(400, {"error": "invalid_json"})
            except Exception as exc:  # pragma: no cover
                LOGGER.exception("Error handling LLM query: %s", exc)
                self._send_json(500, {"error": str(exc)})
            return

        self._send_json(404, {"error": "not_found", "paths": ["/health", "/alerts", "/recommendations", "/requests", "/decisions", "/nodes", "/summary", "POST /llm/query"]})

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A003
        msg = format % args if args else format
        LOGGER.info("API: %s", msg)

    def _handle_llm_query(self, question: str) -> str:
        """Handle a user query using the LLM with the current live fleet snapshot."""
        storage = Storage(self.sqlite_path)
        try:
            # Gather only the latest live snapshot values.
            health = storage.get_recent_health_summaries(limit=1)
            alerts = storage.get_recent_alerts(limit=1)
            hints = storage.get_recent_root_cause_hints(limit=1)
            recommendations = storage.get_recent_action_recommendations(limit=1)
            active_nodes = storage.get_active_node_count()
            discovered_nodes = storage.get_discovered_nodes(limit=1)

            context_parts = [
                "Use only the current live snapshot below. Do not blend in older alerts or historical trends.",
                f"Active nodes: {active_nodes}",
                f"Discovered nodes: {len(discovered_nodes)}",
            ]
            
            if health:
                latest_health = health[0]
                context_parts.append(f"Latest fleet status: {latest_health.get('status', 'unknown')} (score: {latest_health.get('score', 0)})")
            
            if alerts:
                alert = alerts[0]
                context_parts.append("\nLatest alert:")
                context_parts.append(f"  - [{alert.get('severity', 'unknown')}] {alert.get('node_id', 'unknown')}: {alert.get('message', '')}")
            
            if hints:
                hint = hints[0]
                context_parts.append("\nLatest root-cause hint:")
                context_parts.append(f"  - [{hint.get('category', 'unknown')}] {hint.get('node_id', 'unknown')}: {hint.get('message', '')}")
            
            if recommendations:
                rec = recommendations[0]
                context_parts.append("\nLatest recommendation:")
                context_parts.append(f"  - {rec.get('node_id', 'unknown')}: {rec.get('title', '')}")
            
            context = "\n".join(context_parts)

            # Initialize LLM client
            llm_cfg = self.llm_config.get("ai", {}).get("llm", {})
            if not llm_cfg:
                return "LLM is not configured. Please enable the LLM in config.yaml."
            
            try:
                llm = OllamaClient.from_config(self.llm_config)
            except Exception as e:
                return f"Failed to initialize LLM client: {e}"
            
            prompt = f"""You are a fleet monitoring assistant. Answer the user's question about the fleet status based only on the current live snapshot.

Context:
{context}

User question: {question}

Provide a concise, actionable answer. If the snapshot does not support a claim, say so explicitly."""
            
            try:
                response = llm.generate(prompt)
                if not response or response.strip() == "":
                    return "LLM returned an empty response. Check that Ollama is running."
                # Also persist the interactive query to history
                try:
                    storage.store_llm_query(
                        question=question,
                        response=response,
                        node_id=latest_health.get("node_id") if health and latest_health else None,
                        metadata={"context_summary": context[:2000], "source": "api.llm_query"},
                        timestamp_utc=datetime.now(timezone.utc).isoformat(),
                    )
                except Exception:
                    LOGGER.exception("Failed to persist llm query to storage")

                return response
            except Exception as e:
                return f"LLM generation error: {e}"
        except Exception as exc:
            LOGGER.exception("Error in LLM query handler: %s", exc)
            return f"Error querying LLM: {exc}"
        finally:
            storage.close()

    def _load_rows(self, kind: str, limit: int, node_id: str | None) -> dict[str, Any]:
        storage = Storage(self.sqlite_path)
        try:
            if kind == "alerts":
                rows = storage.get_recent_alerts(limit=limit, node_id=node_id)
            elif kind == "recommendations":
                rows = storage.get_recent_action_recommendations(limit=limit, node_id=node_id)
            elif kind == "requests":
                rows = storage.get_recent_action_requests(limit=limit, node_id=node_id)
            elif kind == "decisions":
                rows = storage.get_recent_approval_decisions(limit=limit)
            elif kind == "nodes":
                rows = storage.get_discovered_nodes(limit=limit)
            else:
                rows = []
            return {"count": len(rows), "items": rows}
        finally:
            storage.close()

    def _build_health_summary(self, limit: int, include_rows: bool = False) -> dict[str, Any]:
        storage = Storage(self.sqlite_path)
        try:
            health = storage.get_recent_health_summaries(limit=limit)
            alerts = storage.get_recent_alerts(limit=limit)
            hints = storage.get_recent_root_cause_hints(limit=limit)
            requests = storage.get_recent_action_requests(limit=limit)
            decisions = storage.get_recent_approval_decisions(limit=limit)
            nodes = storage.get_discovered_nodes(limit=limit)

            summary: dict[str, Any] = {
                "sqlite_path": self.sqlite_path,
                "active_node_count": storage.get_active_node_count(),
                "counts": {
                    "health_summaries": len(health),
                    "alerts": len(alerts),
                    "root_cause_hints": len(hints),
                    "action_requests": len(requests),
                    "approval_decisions": len(decisions),
                    "discovered_nodes": len(nodes),
                },
                "latest": {
                    "health_summary": health[0] if health else None,
                    "alert": alerts[0] if alerts else None,
                    "root_cause_hint": hints[0] if hints else None,
                    "action_request": requests[0] if requests else None,
                    "approval_decision": decisions[0] if decisions else None,
                    "discovered_node": nodes[0] if nodes else None,
                },
            }
            if include_rows:
                summary["rows"] = {
                    "health_summaries": health,
                    "alerts": alerts,
                    "root_cause_hints": hints,
                    "action_requests": requests,
                    "approval_decisions": decisions,
                    "discovered_nodes": nodes,
                }
            return summary
        finally:
            storage.close()

    def _send_json(self, status: int, payload: dict[str, Any]) -> None:
        data = json.dumps(payload, indent=2, sort_keys=True).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def create_api_server(config: dict[str, Any]) -> HTTPServer:
    api_cfg = config.get("integration", {}).get("api", {})
    host = str(api_cfg.get("host", "127.0.0.1"))
    port = int(api_cfg.get("port", 8085))
    sqlite_path = str(config.get("collector", {}).get("sqlite_path", "./data/sentinel.db"))

    handler = type(
        "SentinelApiHandler",
        (_SentinelApiHandler,),
        {
            "sqlite_path": sqlite_path,
            "max_rows": max(1, int(api_cfg.get("max_rows", 20))),
            "llm_config": config,
        },
    )

    return HTTPServer((host, port), handler)


def run_api(config: dict[str, Any]) -> None:
    api_cfg = config.get("integration", {}).get("api", {})
    if not bool(api_cfg.get("enabled", True)):
        LOGGER.warning("Integration API is disabled by config; starting anyway because the api role was requested")

    server = create_api_server(config)
    host, port = server.server_address
    LOGGER.info("Sentinel API listening host=%s port=%s", host, port)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        LOGGER.info("Sentinel API shutdown requested")
    finally:
        server.server_close()
