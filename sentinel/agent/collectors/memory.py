from __future__ import annotations

import psutil


def collect_memory() -> dict[str, float]:
    vm = psutil.virtual_memory()
    return {
        "total_bytes": float(vm.total),
        "used_bytes": float(vm.used),
        "available_bytes": float(vm.available),
        "usage_percent": float(vm.percent),
    }
