---
description: Download and unpack the latest SolidWorks API documentation for LLMs (project)
---

Download and unpack the latest SolidWorks API documentation from GitHub releases:

```powershell
# Get latest release info
$response = Invoke-RestMethod -Uri 'https://api.github.com/repos/pedropaulovc/offline-solidworks-api-docs/releases/latest'
$asset = $response.assets | Where-Object { $_.name -like '*llms.v*.zip' }

if (-not $asset) {
    Write-Error "Could not find llms zip file in release"
    exit 1
}

$downloadUrl = $asset.browser_download_url
Write-Output "Downloading from: $downloadUrl"

# Download
$tempPath = Join-Path $env:TEMP 'solidworks-docs.zip'
Invoke-WebRequest -Uri $downloadUrl -OutFile $tempPath
Write-Output "Downloaded to: $tempPath"

# Create target directory if it doesn't exist
$targetDir = ".claude\skills\developing-solidworks"
if (-not (Test-Path $targetDir)) {
    New-Item -ItemType Directory -Path $targetDir -Force | Out-Null
}

# Unpack with progress
Write-Output "Unpacking to: $targetDir"

Add-Type -AssemblyName System.IO.Compression.FileSystem
$zip = [System.IO.Compression.ZipFile]::OpenRead($tempPath)
$totalEntries = $zip.Entries.Count
$currentEntry = 0

foreach ($entry in $zip.Entries) {
    $currentEntry++
    $percent = [math]::Round(($currentEntry / $totalEntries) * 100)

    Write-Progress -Activity "Unpacking SolidWorks API docs" `
        -Status "$currentEntry / $totalEntries files ($percent%)" `
        -PercentComplete $percent

    $destPath = Join-Path $targetDir $entry.FullName
    $destDir = Split-Path $destPath -Parent

    if (-not (Test-Path $destDir)) {
        New-Item -ItemType Directory -Path $destDir -Force | Out-Null
    }

    if (-not $entry.FullName.EndsWith('/')) {
        [System.IO.Compression.ZipFileExtensions]::ExtractToFile($entry, $destPath, $true)
    }
}

$zip.Dispose()
Write-Progress -Activity "Unpacking SolidWorks API docs" -Completed

# Clean up
Remove-Item $tempPath
Write-Output "Done! Cleaned up temporary file."

# Show what was unpacked
Write-Output "Unpacked $totalEntries files to $targetDir"
```
