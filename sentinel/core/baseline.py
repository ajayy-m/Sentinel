from __future__ import annotations

from dataclasses import dataclass
from statistics import quantiles
from typing import Any


@dataclass
class BaselineConfig:
    cpu_window_size: int = 168
    process_window_size: int = 100
    memory_trend_window: int = 3
    cpu_multiplier: float = 1.1
    process_spike_offset: int = 20
    memory_trend_step: float = 5.0


class BaselineDetector:
    """Deterministic rule-only detector used as a comparison baseline."""

    def __init__(self, cfg: BaselineConfig | None = None) -> None:
        self._cfg = cfg or BaselineConfig()

    def detect_cpu_anomaly(self, cpu_pct: float, history: list[float]) -> bool:
        recent = self._trim_history(history, self._cfg.cpu_window_size)
        if len(recent) < 5:
            return cpu_pct >= 95.0
        p95 = self._percentile(recent, 95)
        return cpu_pct > p95 * self._cfg.cpu_multiplier

    def detect_memory_leak(self, memory_pct: float, history: list[float]) -> bool:
        recent = self._trim_history(history, self._cfg.memory_trend_window)
        if len(recent) < self._cfg.memory_trend_window:
            return False
        slopes = [recent[index + 1] - recent[index] for index in range(len(recent) - 1)]
        return all(slope > self._cfg.memory_trend_step for slope in slopes) and memory_pct >= recent[-1]

    def detect_process_spike(self, process_count: float, history: list[float]) -> bool:
        recent = self._trim_history(history, self._cfg.process_window_size)
        if len(recent) < 10:
            return process_count >= 250
        p90 = self._percentile(recent, 90)
        return process_count > p90 + self._cfg.process_spike_offset

    def evaluate_payload(
        self,
        payload: dict[str, Any],
        history: dict[str, list[float]],
    ) -> list[dict[str, Any]]:
        metrics = payload.get("metrics", {})
        results: list[dict[str, Any]] = []

        cpu = float(metrics.get("cpu", {}).get("usage_percent", 0.0))
        memory = float(metrics.get("memory", {}).get("usage_percent", 0.0))
        processes = float(metrics.get("processes", {}).get("count", 0.0))

        if self.detect_cpu_anomaly(cpu, history.get("cpu", [])):
            results.append(
                {
                    "metric": "cpu",
                    "severity": "warning",
                    "category": "baseline_rule",
                    "message": "CPU exceeded baseline percentile rule",
                }
            )

        if self.detect_memory_leak(memory, history.get("memory", [])):
            results.append(
                {
                    "metric": "memory",
                    "severity": "warning",
                    "category": "baseline_rule",
                    "message": "Memory trend increased above baseline rule",
                }
            )

        if self.detect_process_spike(processes, history.get("processes", [])):
            results.append(
                {
                    "metric": "processes",
                    "severity": "warning",
                    "category": "baseline_rule",
                    "message": "Process count exceeded baseline spike rule",
                }
            )

        return results

    def _trim_history(self, history: list[float], window_size: int) -> list[float]:
        if window_size <= 0:
            return list(history)
        return list(history[-window_size:])

    def _percentile(self, values: list[float], percentile: int) -> float:
        if not values:
            return 0.0
        if len(values) == 1:
            return float(values[0])

        quartiles = quantiles(values, n=100, method="inclusive")
        index = max(0, min(98, percentile - 1))
        return float(quartiles[index])
