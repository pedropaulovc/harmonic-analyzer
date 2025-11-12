#!/usr/bin/env pwsh
# Export STL files to PNG images from multiple angles using OpenSCAD

param(
    [Parameter(Mandatory=$false)]
    [string]$StlFile = "",
    
    [Parameter(Mandatory=$false)]
    [string]$OutputDir = "renders",
    
    [Parameter(Mandatory=$false)]
    [int]$ImageSize = 1024,
    
    [Parameter(Mandatory=$false)]
    [int]$Distance = 500
)

# Check if OpenSCAD is installed
$openscad = Get-Command openscad -ErrorAction SilentlyContinue
if (-not $openscad) {
    Write-Error "OpenSCAD not found. Please install OpenSCAD and add it to PATH."
    exit 1
}

# Create output directory
if (-not (Test-Path $OutputDir)) {
    New-Item -ItemType Directory -Path $OutputDir | Out-Null
}

# Define camera angles: x,y,z,rot_x,rot_y,rot_z,distance
$angles = @{
    "front" = "0,0,0,55,0,25,$Distance"
    "back" = "0,0,0,55,0,205,$Distance"
    "left" = "0,0,0,55,0,115,$Distance"
    "right" = "0,0,0,55,0,295,$Distance"
    "top" = "0,0,0,0,0,0,$Distance"
    "bottom" = "0,0,0,180,0,0,$Distance"
    "iso" = "0,0,0,60,0,45,$Distance"
}

# Function to render a single STL file
function Render-STL {
    param([string]$FilePath)
    
    $baseName = [System.IO.Path]::GetFileNameWithoutExtension($FilePath)
    Write-Host "`nRendering: $baseName" -ForegroundColor Cyan
    
    # Create temporary SCAD file to import the STL
    $tempScad = Join-Path $env:TEMP "$baseName-temp.scad"
    $absoluteStlPath = (Resolve-Path $FilePath).Path -replace '\\', '/'
    "import(`"$absoluteStlPath`");" | Set-Content $tempScad
    
    foreach ($angle in $angles.GetEnumerator()) {
        $outputFile = Join-Path $OutputDir "$baseName-$($angle.Key).png"
        Write-Host "  $($angle.Key)... " -NoNewline
        
        $args = @(
            "-o", $outputFile,
            "--imgsize=$ImageSize,$ImageSize",
            "--camera=$($angle.Value)",
            "--colorscheme=BeforeDawn",
            "--render",
            $tempScad
        )
        
        $process = Start-Process -FilePath "openscad" -ArgumentList $args -NoNewWindow -Wait -PassThru
        
        if ($process.ExitCode -eq 0 -and (Test-Path $outputFile)) {
            Write-Host "✓" -ForegroundColor Green
        } else {
            Write-Host "✗" -ForegroundColor Red
        }
    }
    
    # Clean up temp file
    Remove-Item $tempScad -ErrorAction SilentlyContinue
}

# Main logic
if ($StlFile) {
    # Single file mode
    if (-not (Test-Path $StlFile)) {
        Write-Error "File not found: $StlFile"
        exit 1
    }
    Render-STL -FilePath $StlFile
} else {
    # Batch mode - process all STL files in current directory
    $stlFiles = Get-ChildItem -Filter "*.stl" -File
    
    if ($stlFiles.Count -eq 0) {
        Write-Warning "No STL files found in current directory."
        exit 0
    }
    
    Write-Host "Found $($stlFiles.Count) STL file(s)" -ForegroundColor Cyan
    
    foreach ($file in $stlFiles) {
        Render-STL -FilePath $file.FullName
    }
}

Write-Host "`nDone! Images saved to: $OutputDir" -ForegroundColor Green
