from __future__ import annotations

import psutil


def collect_network() -> dict[str, float]:
    io = psutil.net_io_counters() or type(
        "Obj", (), {"bytes_sent": 0, "bytes_recv": 0, "packets_sent": 0, "packets_recv": 0}
    )

    return {
        "bytes_sent": float(io.bytes_sent),
        "bytes_recv": float(io.bytes_recv),
        "packets_sent": float(io.packets_sent),
        "packets_recv": float(io.packets_recv),
    }
