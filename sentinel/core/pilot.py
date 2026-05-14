from __future__ import annotations

import logging
import os
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path
import yaml
from typing import Any
from urllib.parse import urlparse

LOGGER = logging.getLogger(__name__)


def run_pilot(config: dict[str, Any], config_path: str, executable_path: str) -> None:
    """Start collector, agent, API, and UI together; stop all when UI exits.

    If local Ollama is configured and not reachable, attempt to start it from a
    bundled runtime first, then from PATH.
    """
    is_frozen = bool(getattr(sys, "frozen", False))
    app_root = Path(executable_path).resolve().parent if is_frozen else Path(__file__).resolve().parents[2]
    logs_dir = app_root / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)

    # Attempt to start a bundled Ollama and, if started on a custom port,
    # write a runtime config that points child processes at that local server.
    ollama_proc, runtime_base_url = _start_ollama_if_needed(config=config, app_root=app_root, logs_dir=logs_dir)

    # If we started an Ollama on a non-default port, write a temporary config
    # so spawned child processes use that endpoint.
    if runtime_base_url:
        try:
            runtime_cfg_path = Path(app_root) / "config" / "pilot.runtime.yaml"
            runtime_cfg_path.parent.mkdir(parents=True, exist_ok=True)
            # Make a shallow copy and update base_url
            runtime_cfg = dict(config)
            ai_cfg = runtime_cfg.get("ai", {})
            llm = ai_cfg.get("llm", {})
            llm["base_url"] = runtime_base_url
            ai_cfg["llm"] = llm
            runtime_cfg["ai"] = ai_cfg
            with runtime_cfg_path.open("w", encoding="utf-8") as fh:
                yaml.safe_dump(runtime_cfg, fh)
            config_path = str(runtime_cfg_path)
            LOGGER.info("Using runtime config for child processes: %s", config_path)
        except Exception:
            LOGGER.exception("Failed to write runtime config; continuing with original config_path")

    def _spawn(role: str) -> subprocess.Popen[str]:
        if is_frozen:
            cmd = [executable_path, role, "--config", config_path]
        else:
            cmd = [executable_path, "sentinel.py", role, "--config", config_path]

        proc = subprocess.Popen(  # noqa: S603
            cmd,
            cwd=str(app_root),
            text=True,
        )
        LOGGER.info("Started %s process pid=%s", role, proc.pid)
        return proc

    collector: subprocess.Popen[str] | None = None
    agent: subprocess.Popen[str] | None = None
    api: subprocess.Popen[str] | None = None
    ui: subprocess.Popen[str] | None = None

    try:
        collector = _spawn("collector")
        time.sleep(0.8)

        agent = _spawn("agent")
        time.sleep(0.8)

        api = _spawn("api")
        time.sleep(0.8)

        ui = _spawn("ui")
        LOGGER.info("Sentinel pilot running. Close UI window or Ctrl+C to stop all.")
        ui.wait()
    except KeyboardInterrupt:
        LOGGER.info("Pilot shutdown requested")
    finally:
        for name, proc in (("ui", ui), ("api", api), ("agent", agent), ("collector", collector)):
            if proc is None or proc.poll() is not None:
                continue
            LOGGER.info("Stopping %s process pid=%s", name, proc.pid)
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                LOGGER.warning("Force-killing %s process pid=%s", name, proc.pid)
                proc.kill()

        if ollama_proc is not None and ollama_proc.poll() is None:
            LOGGER.info("Stopping ollama process pid=%s", ollama_proc.pid)
            ollama_proc.terminate()
            try:
                ollama_proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                LOGGER.warning("Force-killing ollama process pid=%s", ollama_proc.pid)
                ollama_proc.kill()


def _start_ollama_if_needed(
    config: dict[str, Any],
    app_root: Path,
    logs_dir: Path,
) -> tuple[subprocess.Popen[str] | None, str | None]:
    llm_cfg = config.get("ai", {}).get("llm", {})
    base_url = str(llm_cfg.get("base_url", "http://127.0.0.1:11434"))
    parsed = urlparse(base_url)
    host = parsed.hostname or "127.0.0.1"
    port = parsed.port or 11434

    # Only auto-start local Ollama endpoints.
    if host not in {"127.0.0.1", "localhost"}:
        return None

    if _is_port_open(host, port):
        LOGGER.info("Ollama already reachable at %s:%s", host, port)
        return None

    bundled_ollama = app_root / "ollama" / "ollama.exe"
    ollama_cmd = str(bundled_ollama) if bundled_ollama.exists() else shutil.which("ollama")
    if not ollama_cmd:
        # If Ollama is available on PATH and the default port is open, we won't manage it
        if _is_port_open(host, port):
            LOGGER.info("Ollama already reachable at %s:%s", host, port)
            return None, None
        LOGGER.warning("Ollama runtime not found (expected bundled runtime or PATH entry)")
        return None, None

    env = os.environ.copy()
    bundled_models_dir = app_root / "ollama-models"
    if bundled_models_dir.exists():
        env["OLLAMA_MODELS"] = str(bundled_models_dir)
        LOGGER.info("Using bundled Ollama models at %s", bundled_models_dir)

    # If default port already in use by another Ollama, choose a free ephemeral port
    chosen_port = port
    if _is_port_open(host, port):
        # find an available port
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind((host, 0))
            chosen_port = s.getsockname()[1]

    out_log = logs_dir / "ollama.out.log"
    err_log = logs_dir / "ollama.err.log"

    LOGGER.info("Starting Ollama runtime from %s on port %s", ollama_cmd, chosen_port)
    stdout_handle = out_log.open("a", encoding="utf-8")
    stderr_handle = err_log.open("a", encoding="utf-8")
    # pass explicit --port to avoid conflicting with an existing system Ollama
    proc = subprocess.Popen(  # noqa: S603
        [ollama_cmd, "serve", "--port", str(chosen_port)],
        cwd=str(app_root),
        stdout=stdout_handle,
        stderr=stderr_handle,
        env=env,
        text=True,
    )

    # Give the runtime a moment to come up; continue even if slow.
    base_url = f"http://{host}:{chosen_port}"
    for _ in range(20):
        if _is_port_open(host, chosen_port):
            LOGGER.info("Ollama reachable at %s", base_url)
            break
        time.sleep(0.5)

    return proc, base_url


def _is_port_open(host: str, port: int) -> bool:
    try:
        with socket.create_connection((host, port), timeout=1.0):
            return True
    except OSError:
        return False
