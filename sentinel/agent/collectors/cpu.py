from __future__ import annotations

import psutil


def collect_cpu() -> dict[str, float]:
    return {
        "usage_percent": psutil.cpu_percent(interval=None),
        "load_avg_1m": _load_avg_1m(),
    }


def _load_avg_1m() -> float:
    try:
        return float(psutil.getloadavg()[0])
    except (AttributeError, OSError):
        return -1.0
