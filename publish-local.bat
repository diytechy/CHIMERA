@echo off
echo Publishing CHIMERA pack to local Maven repository...
call gradlew.bat publishToMavenLocal
if %ERRORLEVEL% == 0 (
    echo.
    echo CHIMERA pack published successfully to local Maven.
) else (
    echo.
    echo ERROR: Failed to publish CHIMERA pack.
    exit /b %ERRORLEVEL%
)
