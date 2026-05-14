from __future__ import annotations

import logging
import subprocess
import time
from pathlib import Path

LOGGER = logging.getLogger(__name__)


def run_stack(config_path: str, python_executable: str) -> None:
    """
    Start collector, agent, and UI together as child processes.

    Lifecycle model:
    - collector starts first
    - agent starts second
    - UI starts last (foreground)
    - when UI exits (or Ctrl+C), background processes are terminated
    """
    repo_root = Path(__file__).resolve().parents[2]

    def _spawn(role: str) -> subprocess.Popen[str]:
        cmd = [python_executable, "sentinel.py", role, "--config", config_path]
        proc = subprocess.Popen(  # noqa: S603
            cmd,
            cwd=str(repo_root),
            text=True,
        )
        LOGGER.info("Started %s process pid=%s", role, proc.pid)
        return proc

    collector: subprocess.Popen[str] | None = None
    agent: subprocess.Popen[str] | None = None
    ui: subprocess.Popen[str] | None = None

    try:
        collector = _spawn("collector")
        time.sleep(0.8)

        agent = _spawn("agent")
        time.sleep(0.8)

        ui = _spawn("ui")
        LOGGER.info("Sentinel stack running. Close UI window or press Ctrl+C to stop all.")

        ui_return_code = ui.wait()
        LOGGER.info("UI exited with code=%s; stopping background services", ui_return_code)
    except KeyboardInterrupt:
        LOGGER.info("Stack shutdown requested")
    finally:
        for name, proc in (("agent", agent), ("collector", collector), ("ui", ui)):
            if proc is None:
                continue
            if proc.poll() is not None:
                continue

            LOGGER.info("Stopping %s process pid=%s", name, proc.pid)
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                LOGGER.warning("Force-killing %s process pid=%s", name, proc.pid)
                proc.kill()
