# Sentinel Packaging and Deployment Guide

Date: 2026-05-04

## 1. Scope

This guide defines reproducible deployment for Linux and Windows using the same Sentinel config schema and command shape.

Supported runtime roles:
- collector
- agent
- ui (interactive only, not a background service)

## 2. Common Package Layout

Recommended install root:
- Linux: /opt/sentinel
- Windows: C:\Sentinel

Expected layout:

- sentinel.py
- sentinel/ (package)
- config/config.yaml
- .env (optional)
- venv/
- data/
- logs/

## 3. Dependency Manifest

Python packages (from requirements.txt):
- psutil>=5.9.0
- pyzmq>=26.0.0
- msgpack>=1.0.8
- PyYAML>=6.0.1
- PyQt6>=6.7.0
- pyqtgraph>=0.13.7
- requests>=2.31.0

System dependencies:
- Linux:
  - python3, python3-venv
  - systemd
- Windows:
  - Python 3.x
  - PowerShell 5.1+
  - NSSM (for service wrapping)

## 4. Config Portability Standard

Config schema is identical across OSes:
- same config/config.yaml structure
- same environment variable names
- same CLI shape

Examples:
- python sentinel.py collector --config config/config.yaml
- python sentinel.py agent --config config/config.yaml
- python sentinel.py ui --config config/config.yaml

No source edits should be required across deployments.

## 5. Linux Deployment (systemd)

Service templates included:
- deploy/linux/sentinel-collector.service
- deploy/linux/sentinel-agent.service

Install steps:

1. Create service user and directories:

```bash
sudo useradd -r -s /usr/sbin/nologin -M sentinel || true
sudo mkdir -p /opt/sentinel /etc/sentinel /opt/sentinel/data /opt/sentinel/logs
sudo chown -R sentinel:sentinel /opt/sentinel
```

2. Copy project and create virtual environment:

```bash
cd /opt/sentinel
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

3. Place runtime config:

```bash
sudo cp config/config.yaml /etc/sentinel/config.yaml
sudo cp .env.example /etc/sentinel/sentinel.env
```

4. Install service units:

```bash
sudo cp deploy/linux/sentinel-collector.service /etc/systemd/system/
sudo cp deploy/linux/sentinel-agent.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable sentinel-collector sentinel-agent
sudo systemctl start sentinel-collector sentinel-agent
```

5. Verify:

```bash
sudo systemctl status sentinel-collector --no-pager
sudo systemctl status sentinel-agent --no-pager
journalctl -u sentinel-collector -n 100 --no-pager
journalctl -u sentinel-agent -n 100 --no-pager
```

Optional: a lightweight in-app metrics exporter is available. Enable it by editing the `collector.prometheus` section in `config/config.yaml` if you want an HTTP `/metrics` endpoint for scraping by external systems.

Note: Prometheus/Grafana deployment artifacts were removed from this repository; the recommended approach is to use the in-app exporter or integrate with your existing monitoring stack as needed.

Docker Compose stack:

```bash
docker compose -f deploy/docker/docker-compose.yml up --build
```

The Compose stack now starts the Sentinel services only; integrate external monitoring separately if required.

## 6. Windows Deployment (service wrapper)

Script included:
- deploy/windows/install-services.ps1

Inputs:
- BasePath (default C:\Sentinel)
- ConfigPath (default C:\Sentinel\config\config.yaml)
- NssmPath (default C:\Tools\nssm\nssm.exe)

Install steps:

1. Prepare environment:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
cd C:\Sentinel
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install --upgrade pip
pip install -r requirements.txt
```

2. Install services with NSSM:

```powershell
.\deploy\windows\install-services.ps1 -BasePath "C:\Sentinel" -ConfigPath "C:\Sentinel\config\config.yaml" -NssmPath "C:\Tools\nssm\nssm.exe"
```

3. Start and verify:

```powershell
nssm start SentinelCollector
nssm start SentinelAgent
Get-Service SentinelCollector, SentinelAgent
```

4. Logs:
- C:\Sentinel\logs\collector.out.log
- C:\Sentinel\logs\collector.err.log
- C:\Sentinel\logs\agent.out.log
- C:\Sentinel\logs\agent.err.log

## 7. Upgrade Procedure

Goal: zero-config-schema drift and minimal interruption.

1. Snapshot and backup:
- Backup data/sentinel.db
- Backup config/config.yaml and .env

2. Stop services:
- Linux: systemctl stop sentinel-collector sentinel-agent
- Windows: nssm stop SentinelCollector; nssm stop SentinelAgent

3. Deploy new code:
- Replace source files
- Update dependencies: pip install -r requirements.txt

4. Run safety checks:
- python sentinel.py collector --config config/config.yaml (verify preflight)
- python sentinel.py report --config config/config.yaml --summary-only --limit 5

5. Restart services:
- Linux: systemctl start sentinel-collector sentinel-agent
- Windows: nssm start SentinelCollector; nssm start SentinelAgent

6. Post-checks:
- confirm payload ingest
- confirm UI/report reflects fresh data

## 8. Rollback Procedure

Use rollback when upgrade causes startup or ingest failure.

1. Stop services.
2. Restore previous code bundle.
3. Restore previous venv or reinstall previous pinned dependencies.
4. Restore last known good config if changed.
5. Restore DB backup only if schema/data corruption is confirmed.
6. Start services and validate report output.

Minimum validation after rollback:
- collector starts cleanly
- agent sends payloads
- report summary returns latest payload/health

## 9. Production Readiness Checks

Before promoting deployment:
- preflight passes on target host
- collector and agent run as services
- logs are writable
- data path is writable
- approval/audit tables remain append-only
- backup job is configured

## 10. Installer Artifacts

This repository now includes:
- deploy/linux/sentinel-collector.service
- deploy/linux/sentinel-agent.service
- deploy/windows/install-services.ps1

These are baseline templates and can be hardened per environment policy.

## 11. Windows EXE Packaging (Portable Pilot Bundle)

For pilot usage, Sentinel now supports a packaged EXE flow that launches:
- collector
- agent
- api
- ui

and auto-starts Ollama when configured on localhost.

### Build command

From the project root:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
.\scripts\build_windows_exe.ps1
```

The script builds an onedir package in:
- `dist\SentinelPilot\`

Default behavior:
- bundles `config/pilot.config.yaml`
- bundles Ollama runtime (if `ollama` is on PATH)
- bundles local Ollama model store from `%USERPROFILE%\.ollama\models` (if present)

Optional switches:

```powershell
.\scripts\build_windows_exe.ps1 -IncludeOllamaRuntime:$false -IncludeOllamaModels:$false
```

### Run packaged app

```powershell
cd .\dist\SentinelPilot
.\SentinelPilot.exe pilot --config config\pilot.config.yaml
```

When launched this way:
- `pilot` role starts collector/agent/api/ui together
- if Ollama is not reachable at `localhost:11434`, Sentinel attempts to start bundled `ollama\ollama.exe`
- if `ollama-models\` exists beside the EXE, `OLLAMA_MODELS` is set to that folder automatically

### Important model-bundling note

Large Ollama models are multi-GB assets and are best distributed as files beside the EXE (onedir).
This is more reliable than forcing all model blobs into a single onefile executable, which can lead to very large binaries, slow startup extraction, and platform size limits.
