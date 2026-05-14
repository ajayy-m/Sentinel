param(
    [string]$PrometheusExe = "",
    [string]$PrometheusConfig = "deploy/prometheus/prometheus.yml",
    [string]$GrafanaExe = ""
)

$root = Resolve-Path "$PSScriptRoot\.." | Select-Object -ExpandProperty Path

function Find-Exe([string]$candidate) {
    if (-not [string]::IsNullOrWhiteSpace($candidate) -and (Test-Path $candidate)) { return (Resolve-Path $candidate).ProviderPath }
    $name = Split-Path $candidate -Leaf
    if ($name -and (Get-Command $name -ErrorAction SilentlyContinue)) { return (Get-Command $name).Source }
    return $null
}

$promPath = Find-Exe $PrometheusExe
if (-not $promPath -and (Test-Path (Join-Path $root "prometheus.exe"))) { $promPath = (Resolve-Path (Join-Path $root "prometheus.exe")).ProviderPath }

if ($promPath) {
    Write-Host "Starting Prometheus: $promPath with config $PrometheusConfig"
    Start-Process -FilePath $promPath -ArgumentList "--config.file=$PrometheusConfig" -WorkingDirectory $root -WindowStyle Normal
} else {
    Write-Host "Prometheus executable not found. Pass the path via -PrometheusExe or place prometheus.exe in the repo root." 
}

$grafPath = Find-Exe $GrafanaExe
if (-not $grafPath -and (Test-Path (Join-Path $root "grafana-server.exe"))) { $grafPath = (Resolve-Path (Join-Path $root "grafana-server.exe")).ProviderPath }

if ($grafPath) {
    Write-Host "Starting Grafana server: $grafPath"
    Start-Process -FilePath $grafPath -WorkingDirectory $root -WindowStyle Normal
} else {
    Write-Host "Grafana executable not found. Pass the path via -GrafanaExe or place grafana-server.exe in the repo root." 
}

Write-Host "If you need help downloading Prometheus or Grafana binaries, see deploy/prometheus and deploy/grafana folders." 
