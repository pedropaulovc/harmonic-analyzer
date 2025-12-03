#!/usr/bin/env pwsh
#Requires -Version 7.0

<#
.SYNOPSIS
    Export a single STL file to PNG images from multiple angles using OpenSCAD.

.DESCRIPTION
    Renders a single STL file to PNG images from predefined camera angles using OpenSCAD.

.PARAMETER StlFile
    Path to the STL file to render. This parameter is required.

.PARAMETER OutputDir
    Output directory for rendered images. Default is "renders".

.PARAMETER ImageSize
    Image resolution in pixels (width and height). Default is 4096.

.PARAMETER Distance
    Camera distance from the object. Default is 150. Note: Less relevant when using viewall.

.PARAMETER ColorScheme
    OpenSCAD color scheme to use for rendering. Default is "Solarized".

.EXAMPLE
    .\export-stl-images.ps1 -StlFile "model.stl"
    Renders the specified STL file with default settings.

.EXAMPLE
    .\export-stl-images.ps1 -StlFile "model.stl" -Distance 50
    Renders a file with custom camera distance.

.EXAMPLE
    .\export-stl-images.ps1 -StlFile "model.stl" -ColorScheme "DeepOcean" -ImageSize 2048
    Renders a file with custom color scheme and image size.
#>

[CmdletBinding()]
param(
    [Parameter(Mandatory = $true, Position = 0)]
    [string]$StlFile,
    
    [Parameter(Mandatory = $false)]
    [string]$OutputDir = 'png-renders',
    
    [Parameter(Mandatory = $false)]
    [ValidateRange(256, 8192)]
    [int]$ImageSize = 4096,
    
    [Parameter(Mandatory = $false)]
    [ValidateRange(1, 1000)]
    [int]$Distance = 150,
    
    [Parameter(Mandatory = $false)]
    [ValidateSet('BeforeDawn', 'Cornfield', 'DeepOcean', 'Metallic', 'Sunset', 'Tomorrow', 'Starnight', 'Solarized')]
    [string]$ColorScheme = 'Solarized'
)

Set-StrictMode -Version Latest

# Resolve output directory relative to script location
$scriptDir = Split-Path -Parent $PSScriptRoot
$OutputDir = Join-Path -Path $scriptDir -ChildPath $OutputDir

# Check if OpenSCAD is installed
$openscad = Get-Command -Name openscad -ErrorAction SilentlyContinue
if (-not $openscad) {
    throw 'OpenSCAD not found. Please install OpenSCAD and add it to PATH.'
}

# Create output directory
if (-not (Test-Path -Path $OutputDir)) {
    $null = New-Item -ItemType Directory -Path $OutputDir
}

# Define camera angles: x,y,z,rot_x,rot_y,rot_z,distance
$script:Angles = @{
    'front'  = "0,0,0,90,0,0,$Distance"     # Looking along -Y axis
    'back'   = "0,0,0,90,0,180,$Distance"   # Looking along +Y axis
    'left'   = "0,0,0,90,0,90,$Distance"    # Looking along +X axis
    'right'  = "0,0,0,90,0,270,$Distance"   # Looking along -X axis
    'top'    = "0,0,0,0,0,0,$Distance"      # Looking along -Z axis
    'bottom' = "0,0,0,180,0,0,$Distance"    # Looking along +Z axis
    'iso-front-left'  = "0,0,0,60,0,315,$Distance"   # Isometric front-left
    'iso-front-right' = "0,0,0,60,0,45,$Distance"    # Isometric front-right
    'iso-back-left'   = "0,0,0,60,0,135,$Distance"   # Isometric back-left
    'iso-back-right'  = "0,0,0,60,0,225,$Distance"   # Isometric back-right
    'cabinet'         = "0,0,0,63.43,0,45,$Distance" # Cabinet projection
    'military-left'   = "0,0,0,45,0,45,$Distance"    # Military left
    'military-right'  = "0,0,0,45,0,315,$Distance"   # Military right
    'cavalier'        = "0,0,0,45,0,45,$Distance"    # Cavalier projection
}

function Invoke-StlRender {
    <#
    .SYNOPSIS
        Renders a single STL file to PNG images from multiple angles.
    #>
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)]
        [string]$FilePath
    )
    
    $baseName = [System.IO.Path]::GetFileNameWithoutExtension($FilePath)
    Write-Information "Rendering: $baseName"
    
    # Create output subfolder for this file
    $fileOutputDir = Join-Path -Path $OutputDir -ChildPath $baseName
    if (-not (Test-Path -Path $fileOutputDir)) {
        $null = New-Item -ItemType Directory -Path $fileOutputDir
    }
    
    # Create temporary SCAD file to import the STL
    $tempScad = Join-Path -Path ([System.IO.Path]::GetTempPath()) -ChildPath "$baseName-temp.scad"
    $absoluteStlPath = (Resolve-Path -Path $FilePath).Path -replace '\\', '/'
    "import(`"$absoluteStlPath`");" | Set-Content -Path $tempScad
    
    foreach ($angle in $script:Angles.GetEnumerator()) {
        $outputFile = Join-Path -Path $fileOutputDir -ChildPath "$($angle.Key).png"
        Write-Information "Rendering $($angle.Key) view..."
        
        $openScadArgs = @(
            '-o', $outputFile
            "--imgsize=$ImageSize,$ImageSize"
            "--camera=$($angle.Value)"
            "--colorscheme=$ColorScheme"
            '--view=axes,scales'
            '--viewall'
            '--projection=o'
            $tempScad
        )
        
        # Capture output directly
        $output = & openscad $openScadArgs 2>&1
        $exitCode = $LASTEXITCODE
        
        # Write output to verbose stream
        $output | ForEach-Object { Write-Verbose $_ }
        
        # Check for errors in output
        $errorMessages = $output | Where-Object { $_ -match 'ERROR:' }
        if ($errorMessages) {
            throw "OpenSCAD error while rendering $($angle.Key) view for $baseName`: $($errorMessages -join '; ')"
        }
        
        if ($exitCode -eq 0 -and (Test-Path -Path $outputFile)) {
            Write-Verbose "Successfully rendered $($angle.Key) view"
        }
        else {
            throw "Failed to render $($angle.Key) view for $baseName"
        }
    }
    
    # Clean up temp file
    Remove-Item -Path $tempScad -ErrorAction SilentlyContinue
}

# Main logic
if (-not (Test-Path -Path $StlFile)) {
    throw "File not found: $StlFile"
}

if ([System.IO.Path]::GetExtension($StlFile) -ne '.stl') {
    throw "Invalid file type. Only .stl files are supported."
}

Invoke-StlRender -FilePath $StlFile

Write-Information "Done! Images saved to: $OutputDir"
