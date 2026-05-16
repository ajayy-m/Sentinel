param(
    [string]$ExeName = "SentinelPilot",
    [string]$InstallerScript = "installer/windows/SentinelPilot.iss",
    [string]$InstallDir = "{localappdata}\Sentinel",
    [string]$AppVersion = "0.1.0",
    [switch]$IncludeOllamaRuntime = $true,
    [switch]$IncludeOllamaModels = $true
)

$ErrorActionPreference = "Stop"

$root = Resolve-Path (Join-Path $PSScriptRoot "..") | Select-Object -ExpandProperty Path
$stageScript = Join-Path $root "scripts\build_windows_exe.ps1"
$issPath = Join-Path $root $InstallerScript
$sourceDir = Join-Path $root "dist\$ExeName"
$installerOutDir = Join-Path $root "dist\installer"

if (-not (Test-Path $stageScript)) {
    throw "Staging build script not found at $stageScript"
}
if (-not (Test-Path $issPath)) {
    throw "Installer script not found at $issPath"
}

Write-Host "Staging installable app bundle..."
& $stageScript -ExeName $ExeName -IncludeOllamaRuntime:$IncludeOllamaRuntime -IncludeOllamaModels:$IncludeOllamaModels
if ($LASTEXITCODE -ne 0) {
    throw "App bundle staging failed."
}

if (-not (Test-Path $sourceDir)) {
    throw "Staged app folder not found at $sourceDir"
}

if (-not (Test-Path $installerOutDir)) {
    New-Item -ItemType Directory -Path $installerOutDir | Out-Null
}

function Get-InnoSetupCompiler {
    $iscc = Get-Command ISCC.exe -ErrorAction SilentlyContinue
    if ($iscc) {
        return $iscc.Source
    }

    $candidatePaths = @(
        "${env:LOCALAPPDATA}\Programs\Inno Setup 6\ISCC.exe",
        "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
        "${env:ProgramFiles}\Inno Setup 6\ISCC.exe",
        "${env:LOCALAPPDATA}\Programs\Inno Setup 5\ISCC.exe",
        "${env:ProgramFiles(x86)}\Inno Setup 5\ISCC.exe",
        "${env:ProgramFiles}\Inno Setup 5\ISCC.exe"
    )

    foreach ($candidate in $candidatePaths) {
        if ($candidate -and (Test-Path $candidate)) {
            return $candidate
        }
    }

    throw "Inno Setup Compiler (ISCC.exe) not found. Install Inno Setup or add ISCC.exe to PATH."
}

$isccPath = Get-InnoSetupCompiler

Write-Host "Compiling Windows installer with $isccPath"
$compilerArgs = @(
    "/DAppName=Sentinel",
    "/DAppVersion=$AppVersion",
    "/DSourceDir=$sourceDir",
    "/DAppInstallDir=$InstallDir",
    "/DOutputDir=$installerOutDir",
    $issPath
)
& $isccPath @compilerArgs

if ($LASTEXITCODE -ne 0) {
    throw "Installer compilation failed."
}

Write-Host "Installer created at $(Join-Path $installerOutDir 'SentinelPilot-Setup.exe')"