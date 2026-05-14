from __future__ import annotations

import psutil


def collect_processes() -> dict[str, float]:
    return {
        "count": float(len(psutil.pids())),
    }
