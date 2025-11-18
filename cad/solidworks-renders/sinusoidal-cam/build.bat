@echo off
REM Build script for SinusoidalCam standalone executable

echo ====================================
echo Building SinusoidalCam.exe
echo ====================================
echo.

REM Check if dotnet is available
where dotnet >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: .NET SDK not found. Please install .NET SDK from https://dotnet.microsoft.com/download
    pause
    exit /b 1
)

REM Build the project
echo Building project...
dotnet build -c Release

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo ERROR: Build failed!
    pause
    exit /b 1
)

echo.
echo ====================================
echo Build successful!
echo ====================================
echo.
echo Executable location: bin\Release\net48\SinusoidalCam.exe
echo.
echo To run: run.bat
echo.
pause
