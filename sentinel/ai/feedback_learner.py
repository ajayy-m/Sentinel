"""Feedback loop learning to improve recommendations based on operator decisions."""
from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

LOGGER = logging.getLogger(__name__)


class FeedbackLoopLearner:
    """Track operator feedback and learn patterns to improve future recommendations."""

    def __init__(self, feedback_db_path: str = "./data/recommendation_feedback.jsonl") -> None:
        self._db_path = Path(feedback_db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)

    def record_feedback(
        self,
        recommendation_id: int,
        recommendation: dict[str, Any],
        decision: str,  # "approved", "rejected", "modified"
        actor: str,
        rationale: str,
        actual_outcome: str | None = None,
    ) -> None:
        """
        Record feedback on a recommendation.

        Args:
            recommendation_id: ID of the recommendation
            recommendation: The recommendation object
            decision: User's decision (approved/rejected/modified)
            actor: Operator name/ID
            rationale: Reason for decision
            actual_outcome: What happened after the action (if known)
        """
        try:
            feedback_record = {
                "timestamp": datetime.now(UTC).isoformat(),
                "recommendation_id": recommendation_id,
                "node_id": recommendation.get("node_id"),
                "category": recommendation.get("category"),
                "priority": recommendation.get("priority"),
                "decision": decision,
                "actor": actor,
                "rationale": rationale,
                "outcome": actual_outcome,
                "was_llm_generated": recommendation.get("llm_generated", False),
            }

            # Append to JSONL file
            with open(self._db_path, "a") as f:
                f.write(json.dumps(feedback_record) + "\n")

            LOGGER.info(f"Feedback recorded for recommendation {recommendation_id}: {decision}")
        except Exception as e:
            LOGGER.error(f"Failed to record feedback: {e}")

    def get_feedback_summary(self, node_id: str | None = None) -> dict[str, Any]:
        """
        Get summary statistics on recommendation feedback.

        Args:
            node_id: Optional filter by node

        Returns:
            Summary stats: approval rate, common rejection reasons, etc.
        """
        if not self._db_path.exists():
            return {"total_feedback": 0}

        try:
            records = []
            with open(self._db_path, "r") as f:
                for line in f:
                    try:
                        records.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass

            if node_id:
                records = [r for r in records if r.get("node_id") == node_id]

            if not records:
                return {"total_feedback": 0}

            # Compute stats
            total = len(records)
            approved = len([r for r in records if r.get("decision") == "approved"])
            rejected = len([r for r in records if r.get("decision") == "rejected"])
            modified = len([r for r in records if r.get("decision") == "modified"])

            approval_rate = (approved / total) * 100 if total > 0 else 0

            # Common rejection reasons
            rejection_reasons = {}
            for r in records:
                if r.get("decision") == "rejected":
                    reason = r.get("rationale", "unknown")
                    rejection_reasons[reason] = rejection_reasons.get(reason, 0) + 1

            # LLM performance
            llm_recs = [r for r in records if r.get("was_llm_generated")]
            llm_approval_rate = (
                (len([r for r in llm_recs if r.get("decision") == "approved"]) / len(llm_recs) * 100)
                if llm_recs
                else 0
            )

            return {
                "total_feedback": total,
                "approved": approved,
                "rejected": rejected,
                "modified": modified,
                "approval_rate_pct": round(approval_rate, 2),
                "llm_approval_rate_pct": round(llm_approval_rate, 2),
                "common_rejection_reasons": dict(sorted(rejection_reasons.items(), key=lambda x: x[1], reverse=True)[:5]),
            }
        except Exception as e:
            LOGGER.error(f"Failed to get feedback summary: {e}")
            return {"error": str(e)}

    def get_learning_insights(self) -> dict[str, Any]:
        """
        Extract insights from feedback to guide future recommendations.

        Returns:
            Dictionary with actionable insights for tuning
        """
        if not self._db_path.exists():
            return {}

        try:
            records = []
            with open(self._db_path, "r") as f:
                for line in f:
                    try:
                        records.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass

            if not records:
                return {}

            # Analyze by category
            by_category = {}
            for r in records:
                cat = r.get("category", "unknown")
                if cat not in by_category:
                    by_category[cat] = {"approved": 0, "rejected": 0, "total": 0}

                by_category[cat]["total"] += 1
                if r.get("decision") == "approved":
                    by_category[cat]["approved"] += 1
                else:
                    by_category[cat]["rejected"] += 1

            # Calculate approval rates by category
            category_insights = {}
            for cat, stats in by_category.items():
                rate = (stats["approved"] / stats["total"] * 100) if stats["total"] > 0 else 0
                category_insights[cat] = {
                    "approval_rate": round(rate, 2),
                    "total_recs": stats["total"],
                    "recommendation": "keep_recommending" if rate > 70 else "tune_parameters" if rate > 40 else "consider_disabling",
                }

            # Most common outcomes
            outcomes = {}
            for r in records:
                if r.get("outcome"):
                    outcome = r.get("outcome", "unknown")
                    outcomes[outcome] = outcomes.get(outcome, 0) + 1

            insights = {
                "category_performance": category_insights,
                "common_outcomes": dict(sorted(outcomes.items(), key=lambda x: x[1], reverse=True)[:5]),
                "total_records_analyzed": len(records),
                "recommendation": "Model is performing well" if any(v["approval_rate"] > 70 for v in category_insights.values()) else "Consider retraining prompts",
            }

            return insights
        except Exception as e:
            LOGGER.error(f"Failed to extract learning insights: {e}")
            return {"error": str(e)}

    def export_training_data(self, output_path: str | None = None) -> str | None:
        """
        Export feedback data as training examples for future fine-tuning.

        Args:
            output_path: Where to save exported data (optional)

        Returns:
            Path to exported file or None if error
        """
        if not self._db_path.exists():
            return None

        try:
            export_path = Path(output_path or "./data/recommendation_training_data.jsonl")
            export_path.parent.mkdir(parents=True, exist_ok=True)

            with open(self._db_path, "r") as src, open(export_path, "w") as dst:
                for line in src:
                    try:
                        record = json.loads(line)
                        # Format as training example
                        training_example = {
                            "node": record.get("node_id"),
                            "recommendation_category": record.get("category"),
                            "priority": record.get("priority"),
                            "operator_decision": record.get("decision"),
                            "was_llm": record.get("was_llm_generated"),
                            "rationale": record.get("rationale"),
                            "outcome": record.get("outcome"),
                        }
                        dst.write(json.dumps(training_example) + "\n")
                    except json.JSONDecodeError:
                        pass

            LOGGER.info(f"Training data exported to {export_path}")
            return str(export_path)
        except Exception as e:
            LOGGER.error(f"Failed to export training data: {e}")
            return None
