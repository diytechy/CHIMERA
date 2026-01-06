@echo off
setlocal enabledelayedexpansion

REM ============================================================================
REM AuditAndPackage.bat
REM Main build script for Terra Origen configuration package
REM
REM This script:
REM   1. Creates the Overworld.zip package from all configuration files
REM   2. Generates BiomeTable.csv with biome attributes
REM   3. Validates biome configurations (color definitions)
REM ============================================================================

echo.
echo ============================================
echo   Terra Origen - Audit and Package Script
echo ============================================
echo.

REM Navigate to repository root (parent of .scripts)
cd /d "%~dp0\.."
set "REPO_ROOT=%CD%"

REM ============================================================================
REM Step 1: Create package using PowerShell
REM ============================================================================
echo [Step 1/3] Creating package (Overworld.zip)...
echo --------------------------------------------

REM Create artifacts directory
if not exist ".artifacts" mkdir ".artifacts"

REM Remove existing zip if present
if exist ".artifacts\Overworld.zip" del /q ".artifacts\Overworld.zip"

REM Use PowerShell to create zip (excludes hidden files/folders)
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
    "$ErrorActionPreference = 'Stop'; ^
    $source = '%REPO_ROOT%'; ^
    $dest = '%REPO_ROOT%\.artifacts\Overworld.zip'; ^
    $items = Get-ChildItem -Path $source -Exclude '.*' | Where-Object { -not $_.Name.StartsWith('.') }; ^
    if ($items.Count -eq 0) { Write-Error 'No files to package'; exit 1 }; ^
    Compress-Archive -Path $items.FullName -DestinationPath $dest -Force; ^
    Write-Host \"Package created: $dest\""

if %ERRORLEVEL% neq 0 (
    echo [ERROR] Package creation failed!
    exit /b 1
)
echo [OK] Package created successfully.
echo.

REM ============================================================================
REM Step 2 and 3: Run bash scripts via WSL (if available)
REM ============================================================================

REM Check if WSL is available
where wsl >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo [WARNING] WSL is not available. Skipping BiomeTable.csv generation and validation.
    echo.
    echo To enable full functionality, install WSL:
    echo   wsl --install
    echo.
    echo See: https://docs.microsoft.com/en-us/windows/wsl/install
    goto :success
)

REM Check if bash is available in WSL
wsl which bash >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo [WARNING] Bash is not available in WSL. Skipping BiomeTable.csv generation and validation.
    echo Please ensure a Linux distribution is installed in WSL.
    goto :success
)

REM Get WSL path for the repo
for /f "tokens=*" %%i in ('wsl wslpath -a "%REPO_ROOT%"') do set "WSL_PATH=%%i"

echo [Step 2/3] Generating BiomeTable.csv...
echo --------------------------------------------
wsl bash -c "cd '%WSL_PATH%' && bash .scripts/generate-biome-table.sh"
if %ERRORLEVEL% neq 0 (
    echo [ERROR] BiomeTable.csv generation failed!
    exit /b 1
)
echo [OK] BiomeTable.csv generated successfully.
echo.

echo [Step 3/3] Validating biome configurations...
echo --------------------------------------------
wsl bash -c "cd '%WSL_PATH%' && bash .scripts/check-biomes.sh"
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Biome validation failed! See errors above.
    exit /b 1
)
echo [OK] Biome validation passed.
echo.

:success
echo ============================================
echo   Build completed successfully!
echo ============================================
echo.
echo Outputs:
echo   - .artifacts\Overworld.zip
if exist ".scripts\BiomeTable.csv" echo   - .scripts\BiomeTable.csv
echo.

exit /b 0
