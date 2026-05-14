param(
    [string]$RepoRoot = ".",
    [switch]$RunFailFastCheck
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$rg = Get-Command rg -ErrorAction SilentlyContinue

function Find-Matches {
    param(
        [string]$Pattern,
        [string[]]$SourceGlobs
    )

    if ($rg) {
        $args = @("--line-number", "--color", "never")
        foreach ($glob in $SourceGlobs) {
            $args += @("-g", $glob)
        }
        $args += @("-e", $Pattern, ".")
        $result = & rg @args 2>$null
        if ($LASTEXITCODE -eq 0 -and $result) {
            return @($result)
        }
        return @()
    }

    # PowerShell fallback when rg is not available
    $files = @()
    foreach ($glob in $SourceGlobs) {
        $files += Get-ChildItem -Path $glob -File -Recurse -ErrorAction SilentlyContinue
    }
    $files = $files | Sort-Object -Property FullName -Unique
    if (-not $files) {
        return @()
    }

    $matches = Select-String -Path ($files.FullName) -Pattern $Pattern -AllMatches -ErrorAction SilentlyContinue
    return @($matches | ForEach-Object { "{0}:{1}:{2}" -f $_.Path, $_.LineNumber, $_.Line.Trim() })
}

Push-Location $RepoRoot
try {
    $sourceGlobs = @("sentinel/**/*.py", "sentinel.py", "config/config.yaml")

    $checks = @(
        @{
            Name = "Hardcoded Windows absolute paths";
            Pattern = "[A-Za-z]:\\\\";
            Severity = "critical";
        },
        @{
            Name = "Hardcoded Unix absolute paths";
            Pattern = "(?<![A-Za-z0-9_])/(home|root|opt|var|etc)/";
            Severity = "critical";
        },
        @{
            Name = "Hardcoded machine identifiers";
            Pattern = "DESKTOP-|LAPTOP-|WORKSTATION-|local-node";
            Severity = "critical";
        },
        @{
            Name = "Potential hardcoded private IPv4";
            Pattern = "(?<![0-9])(10\\.[0-9]{1,3}\\.[0-9]{1,3}\\.[0-9]{1,3}|172\\.(1[6-9]|2[0-9]|3[0-1])\\.[0-9]{1,3}\\.[0-9]{1,3}|192\\.168\\.[0-9]{1,3}\\.[0-9]{1,3})(?![0-9])";
            Severity = "critical";
        }
    )

    $criticalFailures = 0

    Write-Host "=== Sentinel Portability Verification ==="
    Write-Host "Source scope: $($sourceGlobs -join ', ')"

    foreach ($check in $checks) {
        Write-Host "`n[CHECK] $($check.Name)"
        $result = @(Find-Matches -Pattern $check.Pattern -SourceGlobs $sourceGlobs)
        if ($result -and $result.Count -gt 0) {
            Write-Host "FOUND:" -ForegroundColor Yellow
            $result | ForEach-Object { Write-Host "  $_" }
            if ($check.Severity -eq "critical") {
                $criticalFailures++
            }
        }
        else {
            Write-Host "PASS" -ForegroundColor Green
        }
    }

    if ($RunFailFastCheck) {
        Write-Host "`n[CHECK] Missing config fail-fast behavior"
        $pythonExe = Join-Path (Resolve-Path ".").Path "venv\Scripts\python.exe"
        if (-not (Test-Path $pythonExe)) {
            throw "Python executable not found at $pythonExe"
        }

        $previousErrorAction = $ErrorActionPreference
        $ErrorActionPreference = "Continue"
        $output = & $pythonExe sentinel.py collector --config does-not-exist.yaml 2>&1
        $exitCode = $LASTEXITCODE
        $ErrorActionPreference = $previousErrorAction

        if ($exitCode -eq 0) {
            Write-Host "FAIL: collector started with missing config" -ForegroundColor Red
            $criticalFailures++
        }
        else {
            Write-Host "PASS: missing config rejected" -ForegroundColor Green
            $output | Select-Object -First 5 | ForEach-Object { Write-Host "  $_" }
        }
    }

    Write-Host "`n=== Summary ==="
    if ($criticalFailures -gt 0) {
        Write-Host "FAILED: $criticalFailures critical portability issues" -ForegroundColor Red
        exit 1
    }

    Write-Host "PASSED: no critical portability issues detected" -ForegroundColor Green
    exit 0
}
finally {
    Pop-Location
}
