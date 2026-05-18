@echo off
REM Windows batch launcher wrapper for SentinelPilot
REM Captures errors and keeps console visible for diagnostics

setlocal enabledelayedexpansion

REM Get the script directory (install folder)
set "APP_DIR=%~dp0"
cd /d "%APP_DIR%"

REM Log file for error capture
set "LOG_FILE=%TEMP%\SentinelPilot-Error-%RANDOM%-%RANDOM%.log"

echo Starting SentinelPilot from: %APP_DIR% >> "%LOG_FILE%" 2>&1
echo Working Directory: %cd% >> "%LOG_FILE%" 2>&1
echo. >> "%LOG_FILE%" 2>&1

REM Check if config file exists
if not exist "config\pilot.config.yaml" (
    echo ERROR: config\pilot.config.yaml not found >> "%LOG_FILE%" 2>&1
    echo. >> "%LOG_FILE%" 2>&1
    echo Config search paths: >> "%LOG_FILE%" 2>&1
    echo   - %APP_DIR%config\pilot.config.yaml >> "%LOG_FILE%" 2>&1
    dir /s /b config 2>> "%LOG_FILE%" 1>> "%LOG_FILE%"
)

REM Check if main EXE exists
if not exist "SentinelPilot.exe" (
    echo ERROR: SentinelPilot.exe not found >> "%LOG_FILE%" 2>&1
    echo Current directory contents: >> "%LOG_FILE%" 2>&1
    dir >> "%LOG_FILE%" 2>&1
)

echo Launching: SentinelPilot.exe pilot --config config\pilot.config.yaml >> "%LOG_FILE%" 2>&1
echo. >> "%LOG_FILE%" 2>&1

REM Launch the main app and capture output
SentinelPilot.exe pilot --config config\pilot.config.yaml >> "%LOG_FILE%" 2>&1
set EXITCODE=%ERRORLEVEL%

echo. >> "%LOG_FILE%" 2>&1
echo SentinelPilot exited with code: %EXITCODE% >> "%LOG_FILE%" 2>&1

REM If there was an error, show it to the user
if %EXITCODE% neq 0 (
    echo.
    echo ================================================================
    echo SentinelPilot encountered an error (exit code: %EXITCODE%)
    echo ================================================================
    echo.
    type "%LOG_FILE%"
    echo.
    echo Diagnostic log saved to: %LOG_FILE%
    echo.
    pause
) else (
    del "%LOG_FILE%" >nul 2>&1
)

exit /b %EXITCODE%
