#!/usr/bin/env pwsh
#Requires -Version 7.0

<#
.SYNOPSIS
    Build KCL files to STL and PNG renders.

.DESCRIPTION
    Exports KCL files to STL format, then generates PNG renders from multiple angles.
    Can process a single file or all KCL files in the project.

.PARAMETER KclFile
    Path to a specific KCL file to build. If not specified, builds all KCL files.

.PARAMETER SkipRender
    Skip PNG rendering step (only export to STL).

.PARAMETER ImageSize
    Image resolution for PNG renders. Default is 4096.

.PARAMETER ColorScheme
    OpenSCAD color scheme for renders. Default is "Solarized".

.EXAMPLE
    .\build.ps1 -KclFile rocker-arm-support.kcl
    Builds a specific KCL file.

.EXAMPLE
    .\build.ps1
    Builds all KCL files in the project.

.EXAMPLE
    .\build.ps1 -KclFile base.kcl -SkipRender
    Exports to STL only, skipping PNG generation.
#>

[CmdletBinding()]
param(
    [Parameter(Mandatory = $false, Position = 0)]
    [string]$KclFile,

    [Parameter(Mandatory = $false)]
    [switch]$SkipRender,

    [Parameter(Mandatory = $false)]
    [ValidateRange(256, 8192)]
    [int]$ImageSize = 4096,

    [Parameter(Mandatory = $false)]
    [ValidateSet('BeforeDawn', 'Cornfield', 'DeepOcean', 'Metallic', 'Sunset', 'Tomorrow', 'Starnight', 'Solarized')]
    [string]$ColorScheme = 'Solarized'
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

# Resolve paths
$scriptDir = Split-Path -Parent $PSScriptRoot
$stlDir = Join-Path -Path $scriptDir -ChildPath 'stl-renders'
$exportScript = Join-Path -Path $PSScriptRoot -ChildPath 'Export-StlToPng.ps1'

# Ensure directories exist
if (-not (Test-Path -Path $stlDir)) {
    $null = New-Item -ItemType Directory -Path $stlDir
}

# Check dependencies
$zoo = Get-Command -Name zoo -ErrorAction SilentlyContinue
if (-not $zoo) {
    throw 'Zoo CLI not found. Please install Zoo and add it to PATH.'
}

if (-not $SkipRender -and -not (Test-Path -Path $exportScript)) {
    throw "Export-StlToPng.ps1 not found at: $exportScript"
}

function Build-KclFile {
    <#
    .SYNOPSIS
        Build a single KCL file to STL and PNG.
    #>
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)]
        [string]$FilePath
    )

    $baseName = [System.IO.Path]::GetFileNameWithoutExtension($FilePath)
    $stlOutput = Join-Path -Path $stlDir -ChildPath "$baseName.stl"

    Write-Host "Building: $baseName" -ForegroundColor Cyan

    # Step 1: Export to STL
    Write-Host "  Exporting to STL..." -ForegroundColor Gray
    Push-Location -Path $scriptDir
    try {
        $output = & zoo kcl export --output-format=stl --deterministic $FilePath $scriptDir 2>&1
        $exitCode = $LASTEXITCODE

        if ($exitCode -ne 0) {
            Write-Error "Zoo export failed for $baseName"
            $output | ForEach-Object { Write-Host $_ -ForegroundColor Red }
            return $false
        }

        # Move output.stl to stl-renders/[basename].stl
        $tempStl = Join-Path -Path $scriptDir -ChildPath 'output.stl'
        if (Test-Path -Path $tempStl) {
            Move-Item -Path $tempStl -Destination $stlOutput -Force
            Write-Host "  STL saved: $stlOutput" -ForegroundColor Green
        }
        else {
            Write-Error "STL output not generated: $tempStl"
            return $false
        }
    }
    finally {
        Pop-Location
    }

    # Step 2: Generate PNG renders
    if (-not $SkipRender) {
        Write-Host "  Generating PNG renders..." -ForegroundColor Gray
        try {
            $renderArgs = @{
                StlFile     = $stlOutput
                ImageSize   = $ImageSize
                ColorScheme = $ColorScheme
            }
            & $exportScript @renderArgs -InformationAction Continue
            Write-Host "  PNG renders complete" -ForegroundColor Green
        }
        catch {
            Write-Warning "Failed to generate PNG renders for $baseName`: $_"
            return $false
        }
    }

    Write-Host "  Build complete: $baseName" -ForegroundColor Green
    return $true
}

# Main logic
try {
    if ($KclFile) {
        # Build single file
        $kclPath = if ([System.IO.Path]::IsPathRooted($KclFile)) {
            $KclFile
        }
        else {
            Join-Path -Path $scriptDir -ChildPath $KclFile
        }

        if (-not (Test-Path -Path $kclPath)) {
            throw "KCL file not found: $kclPath"
        }

        $success = Build-KclFile -FilePath $kclPath
        if (-not $success) {
            exit 1
        }
    }
    else {
        # Build all KCL files (exclude parameters.kcl if it exists)
        $kclFiles = Get-ChildItem -Path $scriptDir -Filter '*.kcl' |
            Where-Object { $_.Name -ne 'parameters.kcl' }

        if ($kclFiles.Count -eq 0) {
            throw "No KCL files found in: $scriptDir"
        }

        Write-Host "Building $($kclFiles.Count) KCL files..." -ForegroundColor Cyan
        Write-Host ""

        $results = @{
            Success = @()
            Failed  = @()
        }

        foreach ($file in $kclFiles) {
            $success = Build-KclFile -FilePath $file.FullName
            if ($success) {
                $results.Success += $file.Name
            }
            else {
                $results.Failed += $file.Name
            }
            Write-Host ""
        }

        # Summary
        Write-Host "Build Summary:" -ForegroundColor Cyan
        Write-Host "  Success: $($results.Success.Count)" -ForegroundColor Green
        if ($results.Failed.Count -gt 0) {
            Write-Host "  Failed: $($results.Failed.Count)" -ForegroundColor Red
            $results.Failed | ForEach-Object { Write-Host "    - $_" -ForegroundColor Red }
            exit 1
        }
    }

    Write-Host ""
    Write-Host "All builds completed successfully!" -ForegroundColor Green
}
catch {
    Write-Error $_
    exit 1
}
