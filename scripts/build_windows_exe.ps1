param(
    [string]$ConfigPath = "config/pilot.config.yaml",
    [string]$ExeName = "SentinelPilot",
    [switch]$IncludeOllamaRuntime = $true,
    [switch]$IncludeOllamaModels = $true
)

$ErrorActionPreference = "Stop"

$root = Resolve-Path (Join-Path $PSScriptRoot "..") | Select-Object -ExpandProperty Path
$python = Join-Path $root "venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    throw "Python executable not found at $python"
}

if (-not (Test-Path (Join-Path $root $ConfigPath))) {
    throw "Config file not found: $ConfigPath"
}

Write-Host "Using Python: $python"
Write-Host "Project root: $root"

# Ensure PyInstaller is available in the venv.
$pyinstallerCheck = & $python -c "import importlib.util,sys; sys.exit(0 if importlib.util.find_spec('PyInstaller') else 1)"
if ($LASTEXITCODE -ne 0) {
    Write-Host "Installing PyInstaller in venv..."
    & $python -m pip install pyinstaller
}

Push-Location $root
try {
    if (Test-Path "build") {
        try {
            Remove-Item -Recurse -Force "build" -ErrorAction Stop
        } catch {
            Write-Warning "Could not fully remove build directory: $($_.Exception.Message)"
        }
    }
    if (Test-Path "dist\$ExeName") {
        try {
            Remove-Item -Recurse -Force "dist\$ExeName" -ErrorAction Stop
        } catch {
            Write-Warning "Could not fully remove dist\${ExeName}: $($_.Exception.Message)"
        }
    }
    if (Test-Path "dist\$ExeName.exe") {
        try {
            Remove-Item -Force "dist\$ExeName.exe" -ErrorAction Stop
        } catch {
            Write-Warning "Could not fully remove dist\${ExeName}.exe: $($_.Exception.Message)"
        }
    }

    # Prepare bundle directory for PyInstaller embedding (onedir installer staging)
    $bundleDir = Join-Path $root "build\bundle_assets"
    if (Test-Path $bundleDir) {
        try {
            Remove-Item -Recurse -Force $bundleDir -ErrorAction Stop
        } catch {
            Write-Warning "Could not fully remove bundle dir: $($_.Exception.Message)"
        }
    }
    if (-not (Test-Path $bundleDir)) { New-Item -ItemType Directory -Path $bundleDir | Out-Null }

    # Copy config into bundle
    $bundleConfigDir = Join-Path $bundleDir "config"
    New-Item -ItemType Directory -Path $bundleConfigDir | Out-Null
    Copy-Item (Join-Path $root $ConfigPath) (Join-Path $bundleConfigDir "pilot.config.yaml") -Force

    $addDataArgs = @()
    $addDataArgs += "--add-data"
    $addDataArgs += ((Join-Path $bundleConfigDir "pilot.config.yaml") + ";config")

    if ($IncludeOllamaRuntime) {
        $ollamaCmd = Get-Command ollama -ErrorAction SilentlyContinue
        if ($ollamaCmd) {
            $ollamaDir = Split-Path -Parent $ollamaCmd.Source
            $targetOllamaDir = Join-Path $bundleDir "ollama"
            New-Item -ItemType Directory -Path $targetOllamaDir -Force | Out-Null
                Write-Host "Copying Ollama runtime from $ollamaDir (files + subfolders, excluding runtime cache/blobs)"
                Get-ChildItem -Path $ollamaDir | ForEach-Object {
                    if ($_.PSIsContainer) {
                        if ($_.Name -in @('blobs','cache','tmp')) { Write-Host "Skipping folder: $($_.Name)"; return }
                        Try { Copy-Item $_.FullName $targetOllamaDir -Recurse -Force -ErrorAction Stop } Catch { Write-Warning "Could not copy $($_.FullName): $($_.Exception.Message)" }
                    } else {
                        Try { Copy-Item $_.FullName $targetOllamaDir -Force -ErrorAction Stop } Catch { Write-Warning "Could not copy $($_.FullName): $($_.Exception.Message)" }
                    }
                }
            $addDataArgs += "--add-data"
            $addDataArgs += ($targetOllamaDir + ";ollama")
        } else {
            Write-Warning "Ollama CLI not found on PATH; runtime not bundled."
        }
    }

    if ($IncludeOllamaModels) {
        $sourceModelsDir = Join-Path $env:USERPROFILE ".ollama\models"
        if (Test-Path $sourceModelsDir) {
            $targetModelsDir = Join-Path $bundleDir "ollama-models"
            New-Item -ItemType Directory -Path $targetModelsDir -Force | Out-Null
            Write-Host "Copying Ollama model store from $sourceModelsDir (excluding blobs to avoid locks)"
            Get-ChildItem -Path $sourceModelsDir | ForEach-Object {
                if ($_.PSIsContainer) {
                    if ($_.Name -eq 'blobs') { Write-Host "Skipping model blobs folder: $($_.Name)"; return }
                    Try { Copy-Item $_.FullName $targetModelsDir -Recurse -Force -ErrorAction Stop } Catch { Write-Warning "Could not copy $($_.FullName): $($_.Exception.Message)" }
                } else {
                    Try { Copy-Item $_.FullName $targetModelsDir -Force -ErrorAction Stop } Catch { Write-Warning "Could not copy $($_.FullName): $($_.Exception.Message)" }
                }
            }
            $addDataArgs += "--add-data"
            $addDataArgs += ($targetModelsDir + ";ollama-models")
        } else {
            Write-Warning "No local Ollama model store found at $sourceModelsDir"
        }
    }

    # Build onefile EXE that embeds bundle assets
    $timestamp = (Get-Date -Format "yyyyMMddHHmmss")
    $workPath = Join-Path $root "build\pyinstaller_work_$timestamp"
    $distPath = Join-Path $root "dist"
    if (-not (Test-Path $workPath)) { New-Item -ItemType Directory -Path $workPath | Out-Null }
    if (-not (Test-Path $distPath)) { New-Item -ItemType Directory -Path $distPath | Out-Null }

    $pyinstallerArgs = @(
        "-m", "PyInstaller",
        "--noconfirm",
        "--clean",
        "--onedir",
        "--name", $ExeName,
        "--collect-submodules", "pyqtgraph",
        "--workpath", $workPath,
        "--distpath", $distPath
    )
    if ($addDataArgs) { $pyinstallerArgs += $addDataArgs }
    $pyinstallerArgs += "sentinel.py"

    Write-Host "Building onedir app bundle for installer packaging..."
    & $python @pyinstallerArgs

    if ($LASTEXITCODE -ne 0) {
        throw "PyInstaller build failed."
    }

    $distRoot = Join-Path $root "dist"
    Write-Host "Build complete: $(Join-Path $distRoot $ExeName)"
    Write-Host "Run with: .\dist\$ExeName\$ExeName.exe pilot --config config\pilot.config.yaml"

    # Cleanup bundle dir
    try { Remove-Item -Recurse -Force $bundleDir } catch { }
}
finally {
    Pop-Location
}
