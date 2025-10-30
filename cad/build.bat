@echo off
REM Build script for console-bracket CAD model
REM Generates STL and renders from KCL source

setlocal

set KCL_FILE=console-bracket.kcl
set STL_FILE=console-bracket.stl
set RENDER_SCRIPT=render_bracket.py
set RENDER_DIR=renders
set BLENDER="C:\Program Files\Blender Foundation\Blender 4.5\blender.exe"

if "%1"=="clean" goto clean
if "%1"=="stl" goto stl
if "%1"=="renders" goto renders
if "%1"=="help" goto help

:all
echo Building all targets...
call :stl
call :renders
goto end

:stl
echo.
echo Exporting KCL to STL...
zoo kcl export --output-format=stl %KCL_FILE% .
if exist output.stl (
    move /Y output.stl %STL_FILE% >nul
    echo Generated: %STL_FILE%
) else (
    echo Error: Failed to generate STL
    exit /b 1
)
goto :eof

:renders
echo.
echo Creating renders directory...
if not exist %RENDER_DIR% mkdir %RENDER_DIR%
echo Rendering views with Blender...
%BLENDER% --background --python %RENDER_SCRIPT%
echo Generated renders in %RENDER_DIR%/
goto :eof

:clean
echo Cleaning generated files...
if exist %STL_FILE% del /Q %STL_FILE%
if exist output.stl del /Q output.stl
if exist %RENDER_DIR% rmdir /S /Q %RENDER_DIR%
echo Clean complete
goto end

:help
echo Available commands:
echo   build.bat        - Generate STL and renders (default)
echo   build.bat stl    - Generate STL file from KCL
echo   build.bat renders - Generate Blender renders from STL
echo   build.bat clean  - Remove generated files
echo   build.bat help   - Show this help message
goto end

:end
endlocal
