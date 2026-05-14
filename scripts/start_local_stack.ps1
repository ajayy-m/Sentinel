param(
    [string]$Config = "config/config.yaml"
)

$root = Resolve-Path (Join-Path $PSScriptRoot '..') | Select-Object -ExpandProperty Path
$venvActivate = Join-Path $root 'venv\Scripts\Activate.ps1'
if (Test-Path $venvActivate) {
    Write-Host "Activating venv: $venvActivate"
    . $venvActivate
} else {
    Write-Host "Warning: venv activate not found at $venvActivate - continuing without venv activation"
}

$logDir = Join-Path $root 'logs'
if (-not (Test-Path $logDir)) { New-Item -ItemType Directory -Path $logDir | Out-Null }

try {
    $python = (Get-Command python -ErrorAction Stop).Source
} catch {
    Write-Host 'Python not found in PATH. Ensure your virtualenv is activated or Python is installed.'
    exit 1
}

Write-Host "Starting Sentinel components (collector, agent, ui) with config: $Config"

$collectorArgs = @('sentinel.py','collector','--config',$Config)
$agentArgs = @('sentinel.py','agent','--config',$Config)
$uiArgs = @('sentinel.py','ui','--config',$Config)

Start-Process -FilePath $python -ArgumentList $collectorArgs -RedirectStandardOutput (Join-Path $logDir 'collector.log') -RedirectStandardError (Join-Path $logDir 'collector.err') -WorkingDirectory $root -WindowStyle Normal
Start-Process -FilePath $python -ArgumentList $agentArgs -RedirectStandardOutput (Join-Path $logDir 'agent.log') -RedirectStandardError (Join-Path $logDir 'agent.err') -WorkingDirectory $root -WindowStyle Normal
Start-Process -FilePath $python -ArgumentList $uiArgs -RedirectStandardOutput (Join-Path $logDir 'ui.log') -RedirectStandardError (Join-Path $logDir 'ui.err') -WorkingDirectory $root -WindowStyle Normal

Write-Host "Launched collector, agent, and ui. Logs are in: $logDir"
