from __future__ import annotations

import subprocess


def collect_gpu() -> dict[str, float]:
    """Collect basic GPU utilization metrics when NVIDIA tooling is available."""
    result = {
        "usage_percent": -1.0,
        "memory_used_bytes": -1.0,
        "memory_total_bytes": -1.0,
        "memory_usage_percent": -1.0,
    }

    try:
        completed = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=utilization.gpu,memory.used,memory.total",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            check=True,
            timeout=3,
        )
    except (FileNotFoundError, subprocess.SubprocessError, OSError):
        return result

    lines = [line.strip() for line in completed.stdout.splitlines() if line.strip()]
    if not lines:
        return result

    first = lines[0]
    parts = [part.strip() for part in first.split(",")]
    if len(parts) < 3:
        return result

    try:
        usage_percent = float(parts[0])
        memory_used_mib = float(parts[1])
        memory_total_mib = float(parts[2])
    except ValueError:
        return result

    memory_used_bytes = memory_used_mib * 1024 * 1024
    memory_total_bytes = memory_total_mib * 1024 * 1024
    memory_usage_percent = (memory_used_bytes / memory_total_bytes * 100.0) if memory_total_bytes > 0 else -1.0

    result.update(
        {
            "usage_percent": usage_percent,
            "memory_used_bytes": memory_used_bytes,
            "memory_total_bytes": memory_total_bytes,
            "memory_usage_percent": memory_usage_percent,
        }
    )
    return result