param(
    [string]$Config = "config/pilot.config.yaml",
    [int]$SimulatorNodes = 1,
    [int]$SimulatorDurationSeconds = 0,
    [double]$SimulatorIntervalSeconds = 5.0,
    [switch]$NoSimulator = $false
)

$root = Resolve-Path (Join-Path $PSScriptRoot '..') | Select-Object -ExpandProperty Path
$python = Join-Path $root 'venv\Scripts\python.exe'
if (-not (Test-Path $python)) {
    Write-Host "Python executable not found at $python"
    exit 1
}

$logDir = Join-Path $root 'logs'
if (-not (Test-Path $logDir)) {
    New-Item -ItemType Directory -Path $logDir | Out-Null
}

$collectorLog = Join-Path $logDir 'pilot-collector.log'
$agentLog = Join-Path $logDir 'pilot-agent.log'
$uiLog = Join-Path $logDir 'pilot-ui.log'
$apiLog = Join-Path $logDir 'pilot-api.log'
$simLog = Join-Path $logDir 'pilot-simulator.log'
$ollamaLog = Join-Path $logDir 'ollama.log'

function Test-OllamaReady {
    try {
        Invoke-RestMethod -Uri 'http://127.0.0.1:11434/api/tags' -Method Get -TimeoutSec 2 | Out-Null
        return $true
    } catch {
        return $false
    }
}

function Start-OllamaIfNeeded {
    if (Test-OllamaReady) {
        Write-Host 'Ollama is already running.'
        return
    }

    $ollama = Get-Command ollama -ErrorAction SilentlyContinue
    if (-not $ollama) {
        Write-Host 'Ollama CLI not found on PATH; LLM features will remain unavailable.'
        return
    }

    Write-Host 'Starting Ollama automatically for LLM support...'
    Start-Process -FilePath $ollama.Source -ArgumentList @('serve') -WorkingDirectory $root -RedirectStandardOutput $ollamaLog -RedirectStandardError (Join-Path $logDir 'ollama.err') | Out-Null
}

if ($NoSimulator) {
    @'
import sqlite3

db_path = './data/sentinel-pilot.db'
tables = [
    'metric_payloads',
    'node_discoveries',
    'health_summaries',
    'alerts',
    'anomaly_scores',
    'root_cause_hints',
    'action_recommendations',
    'trend_summaries',
    'change_events',
    'llm_queries',
]

conn = sqlite3.connect(db_path)
cursor = conn.cursor()
for table in tables:
    cursor.execute(f"DELETE FROM {table} WHERE node_id LIKE ?", ('%-sim-%',))
cursor.execute("DELETE FROM root_cause_hints WHERE category = ?", ('llm_query',))
conn.commit()
conn.close()
print('Simulator rows purged before startup')
'@ | & $python -
}

Start-OllamaIfNeeded

Write-Host "Starting pilot stack with config: $Config"
Write-Host "Logs: $logDir"

Start-Process -FilePath $python -ArgumentList @('sentinel.py', 'collector', '--config', $Config) -WorkingDirectory $root -RedirectStandardOutput $collectorLog -RedirectStandardError (Join-Path $logDir 'pilot-collector.err') | Out-Null
Start-Process -FilePath $python -ArgumentList @('sentinel.py', 'agent', '--config', $Config) -WorkingDirectory $root -RedirectStandardOutput $agentLog -RedirectStandardError (Join-Path $logDir 'pilot-agent.err') | Out-Null
Start-Process -FilePath $python -ArgumentList @('sentinel.py', 'ui', '--config', $Config) -WorkingDirectory $root -RedirectStandardOutput $uiLog -RedirectStandardError (Join-Path $logDir 'pilot-ui.err') | Out-Null
Start-Process -FilePath $python -ArgumentList @('sentinel.py', 'api', '--config', $Config) -WorkingDirectory $root -RedirectStandardOutput $apiLog -RedirectStandardError (Join-Path $logDir 'pilot-api.err') | Out-Null

if (-not $NoSimulator) {
    Start-Process -FilePath $python -ArgumentList @(
        'sentinel.py', 'simulate',
        '--config', $Config,
        '--nodes', $SimulatorNodes,
        '--duration-seconds', $SimulatorDurationSeconds,
        '--interval-seconds', $SimulatorIntervalSeconds
    ) -WorkingDirectory $root -RedirectStandardOutput $simLog -RedirectStandardError (Join-Path $logDir 'pilot-simulator.err') | Out-Null
}

Write-Host "Pilot collector, agent, UI, and API launched."
if (-not $NoSimulator) {
    Write-Host "Simulator launched (synthetic metrics)."
} else {
    Write-Host "Simulator disabled. Collector will discover real nodes."
}
Write-Host "Collector metrics: http://localhost:8000/metrics"
Write-Host "Integration API: http://localhost:8085/health"
Write-Host "Prometheus/Grafana can be attached using the native helper if desired."
