from __future__ import annotations

import hashlib
import platform
import socket
import uuid
from typing import Any


def resolve_node_id(config: dict[str, Any] | None = None) -> str:
    """Return a stable node identifier, using config only if it is set."""
    config = config or {}
    configured = str(config.get("system", {}).get("node_id", "")).strip()
    if configured:
        return configured

    hostname = socket.gethostname().strip() or platform.node().strip() or "unknown-host"
    machine_seed = f"{hostname}|{platform.system()}|{platform.machine()}|{uuid.getnode()}"
    digest = hashlib.sha1(machine_seed.encode("utf-8")).hexdigest()[:12]
    return f"{hostname}-{digest}"
