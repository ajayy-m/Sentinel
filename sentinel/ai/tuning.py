from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any

from sentinel.ai.feedback_learner import FeedbackLoopLearner


@dataclass(frozen=True)
class LLMTuningSuggestion:
    area: str
    setting: str
    current_value: Any
    recommended_value: Any
    rationale: str


class LLMTuningPipeline:
    """Offline tuning pipeline that converts feedback into prompt/config suggestions."""

    def __init__(self, feedback_path: str = "./data/recommendation_feedback.jsonl") -> None:
        self._learner = FeedbackLoopLearner(feedback_db_path=feedback_path)

    def generate_suggestions(self) -> dict[str, Any]:
        summary = self._learner.get_feedback_summary()
        insights = self._learner.get_learning_insights()
        suggestions: list[LLMTuningSuggestion] = []

        approval_rate = float(summary.get("approval_rate_pct", 0.0))
        llm_approval_rate = float(summary.get("llm_approval_rate_pct", 0.0))

        if approval_rate < 50.0:
            suggestions.append(
                LLMTuningSuggestion(
                    area="recommendations",
                    setting="temperature",
                    current_value=0.4,
                    recommended_value=0.25,
                    rationale="Low operator approval suggests recommendations should be more deterministic.",
                )
            )
            suggestions.append(
                LLMTuningSuggestion(
                    area="recommendations",
                    setting="max_tokens",
                    current_value=400,
                    recommended_value=250,
                    rationale="Shorter outputs reduce vague recommendations and speed operator review.",
                )
            )

        if llm_approval_rate < 45.0 and summary.get("total_feedback", 0) > 5:
            suggestions.append(
                LLMTuningSuggestion(
                    area="llm",
                    setting="system_prompt_detail",
                    current_value="medium",
                    recommended_value="high",
                    rationale="LLM-generated recommendations appear weaker than non-LLM ones and need richer context.",
                )
            )

        category_performance = insights.get("category_performance", {}) if isinstance(insights, dict) else {}
        if isinstance(category_performance, dict):
            low_trust_categories = [
                category for category, data in category_performance.items() if float(data.get("approval_rate", 0.0)) < 40.0
            ]
            if low_trust_categories:
                suggestions.append(
                    LLMTuningSuggestion(
                        area="prompting",
                        setting="category_specific_prompts",
                        current_value="disabled",
                        recommended_value=low_trust_categories,
                        rationale="These recommendation categories are underperforming and should receive more explicit prompt templates.",
                    )
                )

        report = {
            "summary": summary,
            "insights": insights,
            "suggestions": [asdict(item) for item in suggestions],
        }
        return report

    def export_report(self, output_path: str) -> str:
        report = self.generate_suggestions()
        target = Path(output_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
        return str(target)
