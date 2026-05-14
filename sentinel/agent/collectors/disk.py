from __future__ import annotations

import os

import psutil


def collect_disk() -> dict[str, float]:
    root = psutil.disk_usage(os.path.abspath(os.sep))
    io = psutil.disk_io_counters() or type("Obj", (), {"read_bytes": 0, "write_bytes": 0})

    return {
        "root_total_bytes": float(root.total),
        "root_used_bytes": float(root.used),
        "root_usage_percent": float(root.percent),
        "read_bytes": float(io.read_bytes),
        "write_bytes": float(io.write_bytes),
    }
