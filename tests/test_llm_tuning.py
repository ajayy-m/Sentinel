from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from sentinel.ai.feedback_learner import FeedbackLoopLearner
from sentinel.ai.tuning import LLMTuningPipeline


class TestLLMTuningPipeline(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp_dir = tempfile.TemporaryDirectory()
        self.feedback_path = Path(self._tmp_dir.name) / "feedback.jsonl"
        self.output_path = Path(self._tmp_dir.name) / "tuning-report.json"

    def tearDown(self) -> None:
        self._tmp_dir.cleanup()

    def test_generate_suggestions_from_low_approval_feedback(self) -> None:
        learner = FeedbackLoopLearner(feedback_db_path=str(self.feedback_path))
        learner.record_feedback(
            recommendation_id=1,
            recommendation={"node_id": "node-a", "category": "investigate", "priority": "high"},
            decision="rejected",
            actor="operator-1",
            rationale="Too vague",
        )
        learner.record_feedback(
            recommendation_id=2,
            recommendation={"node_id": "node-a", "category": "investigate", "priority": "high"},
            decision="approved",
            actor="operator-2",
            rationale="Good",
        )
        learner.record_feedback(
            recommendation_id=3,
            recommendation={"node_id": "node-a", "category": "remediate", "priority": "high"},
            decision="rejected",
            actor="operator-1",
            rationale="Unsafe",
        )

        pipeline = LLMTuningPipeline(feedback_path=str(self.feedback_path))
        report = pipeline.generate_suggestions()

        self.assertIn("summary", report)
        self.assertTrue(report["suggestions"])
        settings = {item["setting"] for item in report["suggestions"]}
        self.assertIn("temperature", settings)

        exported = pipeline.export_report(str(self.output_path))
        self.assertTrue(Path(exported).exists())


if __name__ == "__main__":
    unittest.main()
