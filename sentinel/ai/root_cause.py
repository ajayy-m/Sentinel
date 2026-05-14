"""LLM-augmented root-cause analysis and correlation."""
from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any

from sentinel.ai.llm import OllamaClient

logger = logging.getLogger(__name__)


class LLMAugmentedRootCause:
    """
    Correlate anomalies and changes using both heuristics and LLM reasoning.
    
    Workflow:
    1. Collect all recent anomalies, changes, alerts
    2. Generate a structured summary for the LLM
    3. Ask the LLM to identify root causes and interactions
    4. Store results as hints with LLM-generated explanations
    """

    def __init__(self, llm_client: OllamaClient | None = None) -> None:
        self.llm = llm_client
        self._heuristic_hints: list[dict[str, Any]] = []

    @classmethod
    def from_config(cls, config: dict[str, Any]) -> "LLMAugmentedRootCause":
        """Create from config with optional LLM."""
        try:
            llm = OllamaClient.from_config(config)
            if llm.is_healthy():
                logger.info(f"LLM client initialized with model: {llm.model}")
                return cls(llm)
            else:
                logger.warning("Ollama not reachable; using heuristics only")
                return cls(None)
        except Exception as e:
            logger.warning(f"LLM initialization failed: {e}; using heuristics only")
            return cls(None)

    def analyze(
        self,
        node_id: str,
        anomalies: list[dict[str, Any]],
        changes: list[dict[str, Any]],
        alerts: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """
        Analyze node state and generate root-cause hints.
        
        Args:
            node_id: Target node
            anomalies: Recent anomaly records
            changes: Recent change events
            alerts: Recent alerts
            
        Returns:
            List of root-cause hints with explanations
        """
        hints = []

        # Heuristic layer: fast, always available
        heuristic_hints = self._analyze_heuristics(node_id, anomalies, changes, alerts)
        hints.extend(heuristic_hints)

        # LLM layer: deeper reasoning, optional
        if self.llm:
            try:
                llm_hints = self._analyze_with_llm(node_id, anomalies, changes, alerts)
                hints.extend(llm_hints)
            except Exception as e:
                logger.warning(f"LLM analysis failed: {e}; using heuristics only")

        return hints

    def _analyze_heuristics(
        self,
        node_id: str,
        anomalies: list[dict[str, Any]],
        changes: list[dict[str, Any]],
        alerts: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Fast heuristic-based correlation."""
        hints = []

        # Check for repeated anomalies on same metric
        metric_counts: dict[str, int] = {}
        for anom in anomalies:
            metric = anom.get("metric", "unknown")
            metric_counts[metric] = metric_counts.get(metric, 0) + 1

        for metric, count in metric_counts.items():
            if count >= 2:
                hints.append({
                    "node_id": node_id,
                    "category": "repeated_anomaly",
                    "confidence": min(100, count * 30),
                    "message": f"Repeated anomalies detected on {metric} ({count} occurrences)",
                    "timestamp_utc": datetime.now().astimezone().isoformat(),
                })

        # Check for correlated metrics
        metric_set = {anom.get("metric") for anom in anomalies}
        if "cpu_percent" in metric_set and "memory_percent" in metric_set:
            hints.append({
                "node_id": node_id,
                "category": "resource_contention",
                "confidence": 75,
                "message": "CPU and memory anomalies detected simultaneously; possible resource contention",
                "timestamp_utc": datetime.now().astimezone().isoformat(),
            })

        # Check for change + anomaly correlation
        if changes and anomalies:
            hints.append({
                "node_id": node_id,
                "category": "change_impact",
                "confidence": 60,
                "message": f"State change detected; {len(anomalies)} anomalies may be post-change impact",
                "timestamp_utc": datetime.now().astimezone().isoformat(),
            })

        return hints

    def _analyze_with_llm(
        self,
        node_id: str,
        anomalies: list[dict[str, Any]],
        changes: list[dict[str, Any]],
        alerts: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """LLM-based deep analysis."""
        if not self.llm:
            return []

        hints = []

        # Build structured context
        context = {
            "node_id": node_id,
            "anomalies_count": len(anomalies),
            "changes_count": len(changes),
            "alerts_count": len(alerts),
            "recent_anomalies": anomalies[-5:] if anomalies else [],
            "recent_changes": changes[-5:] if changes else [],
            "recent_alerts": alerts[-5:] if alerts else [],
        }

        prompt = f"""
You are a system monitoring expert. Analyze the following node metrics and state changes.
Provide 2-3 concise root-cause hypotheses. Be specific and actionable.

Node ID: {context['node_id']}
Recent anomalies ({context['anomalies_count']}): {json.dumps(context['recent_anomalies'], indent=2)}
Recent changes ({context['changes_count']}): {json.dumps(context['recent_changes'], indent=2)}
Recent alerts ({context['alerts_count']}): {json.dumps(context['recent_alerts'], indent=2)}

Format your response as:
ROOT_CAUSE_1: <hypothesis>
ROOT_CAUSE_2: <hypothesis>
ROOT_CAUSE_3: <hypothesis>
"""

        system_prompt = """You are a system monitoring expert specializing in root-cause analysis.
Provide concise, actionable insights based on system metrics and change events.
Focus on the most likely causes and their evidence."""

        try:
            response = self.llm.generate(
                prompt,
                system_prompt=system_prompt,
                temperature=0.5,
                max_tokens=256,
            )

            # Parse LLM response
            lines = response.split("\n")
            for i, line in enumerate(lines):
                if line.startswith("ROOT_CAUSE_"):
                    cause = line.split(":", 1)[1].strip() if ":" in line else ""
                    if cause:
                        hints.append({
                            "node_id": node_id,
                            "category": "llm_hypothesis",
                            "confidence": 65,
                            "message": cause,
                            "timestamp_utc": datetime.now().astimezone().isoformat(),
                        })
        except Exception as e:
            logger.warning(f"LLM analysis error: {e}")

        return hints
