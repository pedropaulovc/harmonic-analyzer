@echo off
REM Run script for SinusoidalCam standalone executable

echo ====================================
echo Running SinusoidalCam.exe
echo ====================================
echo.

REM Check if executable exists
if not exist "bin\Release\net48\SinusoidalCam.exe" (
    echo ERROR: Executable not found!
    echo Please build the project first using: build.bat
    echo.
    pause
    exit /b 1
)

REM Run the executable
"bin\Release\net48\SinusoidalCam.exe"

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo Program exited with error code: %ERRORLEVEL%
)

echo.
pause
