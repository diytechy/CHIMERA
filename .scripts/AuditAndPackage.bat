@echo off
setlocal enabledelayedexpansion

REM ============================================================================
REM AuditAndPackage.bat
REM Main build script for Terra configuration package
REM
REM This script:
REM   1. Creates the package zip (name from pack.yml id:)
REM   2. Generates BiomeTable.csv with biome attributes
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
REM Check WSL availability (used for all steps if available)
REM ============================================================================
set "WSL_AVAILABLE=0"
set "WSL_PATH="

where wsl >nul 2>nul
if %ERRORLEVEL% equ 0 (
    wsl which bash >nul 2>nul
    if !ERRORLEVEL! equ 0 (
        set "WSL_AVAILABLE=1"
        for /f "tokens=*" %%i in ('wsl wslpath -a "%REPO_ROOT%"') do set "WSL_PATH=%%i"
    )
)

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

    powershell -NoProfile -ExecutionPolicy Bypass -Command "$ErrorActionPreference = 'Stop'; $source = '%REPO_ROOT%'; $dest = '%REPO_ROOT%\.artifacts\%PACK_ID%.zip'; $items = Get-ChildItem -Path $source -Exclude '.*' | Where-Object { -not $_.Name.StartsWith('.') }; if ($items.Count -eq 0) { Write-Error 'No files to package'; exit 1 }; Compress-Archive -Path $items.FullName -DestinationPath $dest -Force; Write-Host ('Package created: ' + $dest)"

    if !ERRORLEVEL! neq 0 (
        echo [ERROR] Package creation failed!
        exit /b 1
    )
    echo [OK] Package created via PowerShell.
)
echo.

REM ============================================================================
REM Step 2 and 3: Run bash scripts via WSL (if available)
REM ============================================================================

if "%WSL_AVAILABLE%"=="0" (
    echo [WARNING] WSL is not available. Skipping BiomeTable.csv generation and audit.
    echo.
    echo To enable full functionality, install WSL:
    echo   wsl --install
    echo.
    echo See: https://docs.microsoft.com/en-us/windows/wsl/install
    goto :success
)

echo [Step 2/3] Generating BiomeTable.csv...
echo --------------------------------------------
wsl bash -c "cd '%WSL_PATH%' && bash .scripts/generate-biome-table.sh"
if %ERRORLEVEL% neq 0 (
    echo [ERROR] BiomeTable.csv generation failed!
    exit /b 1
)
echo [OK] BiomeTable.csv generated successfully.
echo.

echo [Step 3/3] Auditing biomes and generating SuggestedImprovements.md...
echo --------------------------------------------
wsl bash -c "cd '%WSL_PATH%' && bash .scripts/check-biomes.sh"
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Biome audit failed!
    exit /b 1
)
echo [OK] Biome audit completed.
echo.

:success
echo ============================================
echo   Build completed successfully!
echo ============================================
echo.
echo Outputs:
if exist ".artifacts\%PACK_ID%.zip" echo   - .artifacts\%PACK_ID%.zip
if exist ".scripts\BiomeTable.csv" echo   - .scripts\BiomeTable.csv
if exist "SuggestedImprovements.md" echo   - SuggestedImprovements.md
echo.

exit /b 0
