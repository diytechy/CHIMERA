@echo off
setlocal enabledelayedexpansion

REM ============================================================================
REM AuditAndPackage.bat
REM Main build script for Terra configuration package
REM
REM This script:
REM   1. Creates the package zip (name from pack.yml id:)
REM   2. Generates BiomeTable.csv with biome distribution percentages
REM   3. Audits biome configs and generates SuggestedImprovements.md
REM ============================================================================

echo.
echo ============================================
echo   Terra - Audit and Package Script
echo ============================================
echo.

REM Navigate to repository root (parent of .scripts)
cd /d "%~dp0\.."
set "REPO_ROOT=%CD%"

REM Read package name from pack.yml
set "PACK_ID="
for /f "tokens=2 delims=: " %%a in ('findstr /B "id:" pack.yml') do set "PACK_ID=%%a"
if "%PACK_ID%"=="" (
    echo [ERROR] Could not read 'id:' from pack.yml
    exit /b 1
)
echo Package ID: %PACK_ID%
echo.

REM ============================================================================
REM Check Python availability (required for biome table generation)
REM ============================================================================
set "PYTHON_CMD="
where python >nul 2>nul
if %ERRORLEVEL% equ 0 (
    set "PYTHON_CMD=python"
) else (
    where python3 >nul 2>nul
    if !ERRORLEVEL! equ 0 (
        set "PYTHON_CMD=python3"
    )
)

if "%PYTHON_CMD%"=="" (
    echo [WARNING] Python is not available. BiomeTable.csv generation will be skipped.
    echo   To install Python: https://www.python.org/downloads/
    set "PYTHON_AVAILABLE=0"
) else (
    echo Python found: %PYTHON_CMD%
    set "PYTHON_AVAILABLE=1"
)
echo.

REM ============================================================================
REM Check WSL availability (optional, for check-biomes.sh)
REM ============================================================================
set "WSL_AVAILABLE=0"
set "WSL_PATH="

where wsl >nul 2>nul
if %ERRORLEVEL% equ 0 (
    wsl which bash >nul 2>nul
    if !ERRORLEVEL! equ 0 (
        set "WSL_AVAILABLE=1"
        for /f "tokens=*" %%i in ('wsl wslpath -a "%REPO_ROOT%"') do set "WSL_PATH=%%i"
        echo WSL found: Available
    )
) else (
    echo WSL found: Not available
)
echo.

REM ============================================================================
REM Step 1: Create package (try WSL first, fallback to PowerShell)
REM ============================================================================
echo [Step 1/3] Creating package (%PACK_ID%.zip)...
echo --------------------------------------------

REM Create artifacts directory
if not exist ".artifacts" mkdir ".artifacts"

set "PACK_SUCCESS=0"

REM Try WSL/pack.sh first
if "%WSL_AVAILABLE%"=="1" (
    echo Attempting to create package via WSL...
    wsl bash -c "cd '%WSL_PATH%' && bash .scripts/pack.sh" 2>nul
    if !ERRORLEVEL! equ 0 (
        set "PACK_SUCCESS=1"
        echo [OK] Package created via WSL.
    ) else (
        echo [INFO] WSL pack.sh failed, falling back to PowerShell...
    )
)

REM Fallback to PowerShell if WSL failed or unavailable
if "%PACK_SUCCESS%"=="0" (
    echo Creating package via PowerShell...

    REM Remove existing zip if present
    if exist ".artifacts\%PACK_ID%.zip" del /q ".artifacts\%PACK_ID%.zip"
    echo Zipping %PACK_ID%...
    REM Pack contents allowlist — keep in sync with build.gradle.kts, pack.sh, and release-zip.yml.
    powershell -NoProfile -ExecutionPolicy Bypass -Command "$ErrorActionPreference = 'Stop'; $source = '%REPO_ROOT%'; $dest = '%REPO_ROOT%\.artifacts\%PACK_ID%.zip'; $names = @('pack.yml','meta.yml','customization.yml','substratum_meta.yml','biomes','biome-distribution','features','palettes','math','structures'); $items = $names | ForEach-Object { Join-Path $source $_ } | Where-Object { Test-Path $_ }; if ($items.Count -eq 0) { Write-Error 'No files to package'; exit 1 }; Compress-Archive -Path $items -DestinationPath $dest -Force; Write-Host ('Package created: ' + $dest)"

    if !ERRORLEVEL! neq 0 (
        echo [ERROR] Package creation failed!
        exit /b 1
    )
    echo [OK] Package created via PowerShell.
)
echo.

REM ============================================================================
REM Step 2: Generate BiomeTable.csv (using Python script)
REM ============================================================================
echo [Step 2/3] Generating BiomeTable.csv...
echo --------------------------------------------

if "%PYTHON_AVAILABLE%"=="1" (
    %PYTHON_CMD% .scripts\calculate_biome_percentages.py
    if !ERRORLEVEL! neq 0 (
        echo [ERROR] BiomeTable.csv generation failed!
        exit /b 1
    )
    echo [OK] BiomeTable.csv generated successfully.
) else (
    echo [WARNING] Python not available - BiomeTable.csv generation skipped.
    echo   Install Python from: https://www.python.org/downloads/
    echo   Required packages: pyyaml (install with: pip install pyyaml)
)
echo.

REM ============================================================================
REM Step 3: Audit biome configs (using bash script via WSL)
REM ============================================================================
echo [Step 3/3] Auditing biomes and generating SuggestedImprovements.md...
echo --------------------------------------------

if "%WSL_AVAILABLE%"=="1" (
    wsl bash -c "cd '%WSL_PATH%' && bash .scripts/check-biomes.sh"
    if !ERRORLEVEL! neq 0 (
        echo [WARNING] Biome audit completed with warnings.
    ) else (
        echo [OK] Biome audit completed.
    )
) else (
    echo [WARNING] WSL is not available. Biome audit skipped.
    echo.
    echo To enable YAML validation and linting, install WSL:
    echo   wsl --install
    echo.
    echo See: https://docs.microsoft.com/en-us/windows/wsl/install
)
echo.

:success
echo ============================================
echo   Build completed successfully!
echo ============================================
echo.
echo Outputs:
if exist ".artifacts\%PACK_ID%.zip" echo   - .artifacts\%PACK_ID%.zip
if exist ".artifacts\BiomeTable.csv" echo   - .artifacts\BiomeTable.csv
if exist ".artifacts\SuggestedImprovements.md" (
    echo   - .artifacts\SuggestedImprovements.md
) else (
    if exist "SuggestedImprovements.md" echo   - SuggestedImprovements.md
)
echo.

exit /b 0
