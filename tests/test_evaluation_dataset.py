from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from sentinel.core.evaluation_dataset import SyntheticEvaluationDatasetGenerator


class TestEvaluationDataset(unittest.TestCase):
    def test_generator_exports_labeled_jsonl(self) -> None:
        generator = SyntheticEvaluationDatasetGenerator(seed=7)

        with tempfile.TemporaryDirectory() as tmp_dir:
            output_path = Path(tmp_dir) / "evaluation-dataset.jsonl"
            exported = generator.export_jsonl(str(output_path), samples_per_scenario=2)

            self.assertTrue(Path(exported).exists())
            lines = Path(exported).read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(lines), 10)

            parsed = [json.loads(line) for line in lines]
            labels = {row["label"] for row in parsed}
            scenarios = {row["scenario"] for row in parsed}

            self.assertIn("normal", labels)
            self.assertIn("anomaly", labels)
            self.assertEqual(scenarios, {"normal", "cpu_spike", "memory_leak", "process_spike", "multi_metric_spike"})


if __name__ == "__main__":
    unittest.main()
