from __future__ import annotations

import json
import random
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class EvaluationSample:
    sample_id: str
    node_id: str
    scenario: str
    label: str
    payload: dict[str, Any]
    expected_alerts: list[str]
    expected_root_cause: str


class SyntheticEvaluationDatasetGenerator:
    """Generate labeled synthetic telemetry for baseline and AI evaluation."""

    def __init__(self, seed: int = 42) -> None:
        self._rng = random.Random(seed)

    def generate(self, samples_per_scenario: int = 25) -> list[EvaluationSample]:
        samples: list[EvaluationSample] = []
        scenarios = ("normal", "cpu_spike", "memory_leak", "process_spike", "multi_metric_spike")
        for scenario in scenarios:
            for index in range(samples_per_scenario):
                sample = self._build_sample(scenario=scenario, index=index)
                samples.append(sample)
        return samples

    def export_jsonl(self, output_path: str, samples_per_scenario: int = 25) -> str:
        samples = self.generate(samples_per_scenario=samples_per_scenario)
        target = Path(output_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("w", encoding="utf-8") as handle:
            for sample in samples:
                handle.write(json.dumps(sample.__dict__, sort_keys=True) + "\n")
        return str(target)

    def _build_sample(self, scenario: str, index: int) -> EvaluationSample:
        timestamp = datetime.now(UTC) - timedelta(minutes=index)
        node_id = f"eval-node-{index % 3 + 1}"
        cpu = self._normal_cpu()
        memory = self._normal_memory()
        disk = self._normal_disk()
        process_count = self._normal_process_count()
        label = "normal"
        expected_alerts: list[str] = []
        expected_root_cause = "baseline noise"

        if scenario == "cpu_spike":
            cpu = self._rng.uniform(92.0, 99.0)
            label = "anomaly"
            expected_alerts.append("cpu")
            expected_root_cause = "cpu saturation"
        elif scenario == "memory_leak":
            memory = self._rng.uniform(88.0, 98.0)
            label = "anomaly"
            expected_alerts.append("memory")
            expected_root_cause = "memory leak"
        elif scenario == "process_spike":
            process_count = self._rng.randint(260, 360)
            label = "anomaly"
            expected_alerts.append("processes")
            expected_root_cause = "process explosion"
        elif scenario == "multi_metric_spike":
            cpu = self._rng.uniform(90.0, 99.0)
            memory = self._rng.uniform(85.0, 97.0)
            process_count = self._rng.randint(250, 340)
            label = "anomaly"
            expected_alerts.extend(["cpu", "memory", "processes"])
            expected_root_cause = "correlated multi-metric incident"

        payload = {
            "schema": "metric_payload",
            "protocol_version": "1.0",
            "node": {
                "node_id": node_id,
                "hostname": f"{node_id}-host",
                "os": "Linux",
                "platform": "synthetic",
            },
            "timestamp_utc": timestamp.isoformat(),
            "metrics": {
                "cpu": {"usage_percent": cpu, "load_avg_1m": round(cpu / 25.0, 2)},
                "memory": {
                    "usage_percent": memory,
                    "total_bytes": float(16 * 1024 * 1024 * 1024),
                },
                "disk": {"root_usage_percent": disk},
                "processes": {"count": float(process_count)},
            },
        }

        return EvaluationSample(
            sample_id=f"{scenario}-{index:04d}",
            node_id=node_id,
            scenario=scenario,
            label=label,
            payload=payload,
            expected_alerts=expected_alerts,
            expected_root_cause=expected_root_cause,
        )

    def _normal_cpu(self) -> float:
        return self._rng.uniform(12.0, 55.0)

    def _normal_memory(self) -> float:
        return self._rng.uniform(15.0, 70.0)

    def _normal_disk(self) -> float:
        return self._rng.uniform(10.0, 75.0)

    def _normal_process_count(self) -> int:
        return self._rng.randint(70, 180)
