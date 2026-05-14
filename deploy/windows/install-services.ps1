param(
    [string]$BasePath = "C:\Sentinel",
    [string]$ConfigPath = "C:\Sentinel\config\config.yaml",
    [string]$NssmPath = "C:\Tools\nssm\nssm.exe"
)

$pythonExe = Join-Path $BasePath "venv\Scripts\python.exe"
$sentinelPy = Join-Path $BasePath "sentinel.py"

if (!(Test-Path $NssmPath)) {
    throw "NSSM not found at $NssmPath"
}
if (!(Test-Path $pythonExe)) {
    throw "Python executable not found at $pythonExe"
}
if (!(Test-Path $sentinelPy)) {
    throw "sentinel.py not found at $sentinelPy"
}

& $NssmPath install SentinelCollector $pythonExe "$sentinelPy collector --config $ConfigPath"
& $NssmPath set SentinelCollector AppDirectory $BasePath
& $NssmPath set SentinelCollector Start SERVICE_AUTO_START
& $NssmPath set SentinelCollector AppStdout (Join-Path $BasePath "logs\collector.out.log")
& $NssmPath set SentinelCollector AppStderr (Join-Path $BasePath "logs\collector.err.log")

& $NssmPath install SentinelAgent $pythonExe "$sentinelPy agent --config $ConfigPath"
& $NssmPath set SentinelAgent AppDirectory $BasePath
& $NssmPath set SentinelAgent Start SERVICE_AUTO_START
& $NssmPath set SentinelAgent AppStdout (Join-Path $BasePath "logs\agent.out.log")
& $NssmPath set SentinelAgent AppStderr (Join-Path $BasePath "logs\agent.err.log")

Write-Host "Services installed. Start with:"
Write-Host "  nssm start SentinelCollector"
Write-Host "  nssm start SentinelAgent"
