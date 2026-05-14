"""
Startup preflight checks for Sentinel.

Validates environment, dependencies, and configuration before entering steady state.
"""

from __future__ import annotations

import logging
import socket
import subprocess
import sys
from pathlib import Path
from typing import Any

LOGGER = logging.getLogger(__name__)


class PreflightCheck:
    """Base class for preflight checks."""

    def check(self) -> tuple[bool, str]:
        """Return (passed, message)."""
        raise NotImplementedError

    def severity(self) -> str:
        """Return 'critical', 'warning', or 'info'."""
        raise NotImplementedError


class WritableDataDirectory(PreflightCheck):
    def __init__(self, path: str) -> None:
        self.path = Path(path)

    def check(self) -> tuple[bool, str]:
        try:
            self.path.mkdir(parents=True, exist_ok=True)
            test_file = self.path / ".sentinel_test"
            test_file.write_text("test")
            test_file.unlink()
            return True, f"✓ Data directory writable: {self.path}"
        except Exception as e:
            return False, f"✗ Data directory not writable: {self.path} ({e})"

    def severity(self) -> str:
        return "critical"


class WritableLogDirectory(PreflightCheck):
    def __init__(self, path: str) -> None:
        self.path = Path(path)

    def check(self) -> tuple[bool, str]:
        try:
            self.path.mkdir(parents=True, exist_ok=True)
            test_file = self.path / ".sentinel_test"
            test_file.write_text("test")
            test_file.unlink()
            return True, f"✓ Log directory writable: {self.path}"
        except Exception as e:
            return False, f"✗ Log directory not writable: {self.path} ({e})"

    def severity(self) -> str:
        return "critical"


class DependencyAvailable(PreflightCheck):
    def __init__(self, module_name: str, package_name: str | None = None) -> None:
        self.module_name = module_name
        self.package_name = package_name or module_name

    def check(self) -> tuple[bool, str]:
        try:
            __import__(self.module_name)
            return True, f"✓ Module available: {self.module_name}"
        except ImportError:
            return False, f"✗ Module not found: {self.module_name} (install: pip install {self.package_name})"

    def severity(self) -> str:
        return "critical"


class OptionalCapabilityProbe(PreflightCheck):
    def __init__(self, name: str, probe_fn) -> None:
        self.name = name
        self.probe_fn = probe_fn

    def check(self) -> tuple[bool, str]:
        try:
            result = self.probe_fn()
            return True, f"✓ {self.name}: available ({result})"
        except Exception as e:
            return False, f"⊘ {self.name}: not available ({e})"

    def severity(self) -> str:
        return "info"


class NetworkConnectivity(PreflightCheck):
    def __init__(self, host: str, port: int, label: str) -> None:
        self.host = host
        self.port = port
        self.label = label

    def check(self) -> tuple[bool, str]:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2)
            result = sock.connect_ex((self.host, self.port))
            sock.close()
            if result == 0:
                return True, f"✓ Network connectivity: {self.label} ({self.host}:{self.port})"
            else:
                return False, f"✗ Network connectivity: {self.label} ({self.host}:{self.port}) unreachable"
        except Exception as e:
            return False, f"✗ Network connectivity: {self.label} ({e})"

    def severity(self) -> str:
        return "warning"


class TransportConfigurationCheck(PreflightCheck):
    def __init__(self, transport_cfg: dict[str, Any]) -> None:
        self.transport_cfg = transport_cfg

    def check(self) -> tuple[bool, str]:
        mode = str(self.transport_cfg.get("mode", "tcp")).lower()
        if mode != "tcp":
            return False, f"✗ Transport mode unsupported: {mode} (supported: tcp)"

        endpoint = str(self.transport_cfg.get("endpoint", "")).strip()
        if not endpoint.startswith("tcp://"):
            return False, f"✗ Transport endpoint must use tcp:// for mode=tcp ({endpoint or 'missing'})"

        collector_endpoints = self.transport_cfg.get("collector_endpoints") or []
        if isinstance(collector_endpoints, str):
            collector_endpoints = [collector_endpoints]
        if not isinstance(collector_endpoints, list):
            return False, "✗ collector_endpoints must be a list when configured"

        for collector_endpoint in collector_endpoints:
            collector_endpoint = str(collector_endpoint).strip()
            if collector_endpoint and not collector_endpoint.startswith("tcp://"):
                return False, (
                    f"✗ collector_endpoints entries must use tcp:// for mode=tcp ({collector_endpoint})"
                )

        auth_cfg = self.transport_cfg.get("auth", {})
        if not isinstance(auth_cfg, dict):
            return False, "✗ transport.auth must be a mapping when configured"

        if bool(auth_cfg.get("enabled", False)):
            scheme = str(auth_cfg.get("scheme", "hmac-sha256")).lower()
            if scheme not in {"hmac-sha256", "curve"}:
                return False, f"✗ Unsupported transport.auth.scheme: {scheme}"

            if scheme == "hmac-sha256":
                shared_key = str(auth_cfg.get("shared_key", "")).strip()
                if len(shared_key) < 16:
                    return False, "✗ transport.auth.shared_key must be at least 16 characters when enabled"

        return True, f"✓ Transport configuration valid: mode={mode}, endpoint={endpoint}, auth={'enabled' if bool(auth_cfg.get('enabled', False)) else 'disabled'}"

    def severity(self) -> str:
        return "critical"


def run_preflight_checks(config: dict[str, Any]) -> None:
    """Run all preflight checks and report readiness."""

    collector_cfg = config.get("collector", {})
    transport_cfg = config.get("transport", {})
    
    sqlite_path = str(collector_cfg.get("sqlite_path", "./data/sentinel.db"))
    data_dir = str(Path(sqlite_path).parent)
    log_dir = "./logs"

    def _probe_nvidia_gpu() -> str:
        """Return concise GPU summary without process-level details."""
        result = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=name,driver_version,memory.total",
                "--format=csv,noheader",
            ],
            capture_output=True,
            text=True,
            check=True,
            timeout=3,
        )
        lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
        if not lines:
            return "GPU detected"
        if len(lines) == 1:
            return lines[0]
        return f"{len(lines)} GPUs ({lines[0]})"

    def _probe_ollama() -> str:
        sock = socket.create_connection(("localhost", 11434), timeout=1)
        sock.close()
        return "localhost:11434 reachable"

    checks: list[PreflightCheck] = [
        # Critical checks
        WritableDataDirectory(data_dir),
        WritableLogDirectory(log_dir),
        DependencyAvailable("zmq", "pyzmq"),
        DependencyAvailable("msgpack"),
        DependencyAvailable("psutil"),
        DependencyAvailable("yaml", "pyyaml"),
        TransportConfigurationCheck(transport_cfg),
        # Optional checks
        OptionalCapabilityProbe(
            "PyQt6 UI",
            lambda: __import__("PyQt6.QtWidgets"),
        ),
        OptionalCapabilityProbe(
            "NVIDIA GPU (for Ollama)",
            _probe_nvidia_gpu,
        ),
        OptionalCapabilityProbe(
            "Ollama LLM service",
            _probe_ollama,
        ),
    ]

    # Add network checks if in collector/agent mode
    endpoint = transport_cfg.get("endpoint", "tcp://127.0.0.1:5556")
    if "tcp://" in endpoint:
        try:
            host, port_str = endpoint.replace("tcp://", "").split(":")
            port = int(port_str)
            # Only check if not localhost (localhost is assumed available)
            if host not in ("127.0.0.1", "localhost"):
                checks.append(NetworkConnectivity(host, port, f"Collector ({endpoint})"))
        except (ValueError, AttributeError):
            pass

    # Run all checks
    critical_passed = True
    results = []

    for check in checks:
        passed, message = check.check()
        severity = check.severity()

        if severity == "critical" and not passed:
            critical_passed = False

        results.append((severity, message, passed))

    # Print report
    LOGGER.info("=" * 70)
    LOGGER.info("SENTINEL PREFLIGHT CHECK REPORT")
    LOGGER.info("=" * 70)

    for severity, message, passed in results:
        if severity == "critical":
            prefix = "CRITICAL" if not passed else "OK"
        elif severity == "warning":
            prefix = "WARN" if not passed else "OK"
        else:
            prefix = "INFO"

        LOGGER.info(f"[{prefix:8s}] {message}")

    LOGGER.info("=" * 70)

    if not critical_passed:
        LOGGER.critical("PREFLIGHT FAILED: Critical checks did not pass. Aborting startup.")
        sys.exit(1)

    LOGGER.info("PREFLIGHT PASSED: Ready to start Sentinel.")
    LOGGER.info("=" * 70)
