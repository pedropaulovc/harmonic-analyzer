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

# Unpack
Write-Output "Unpacking to: $targetDir"
Expand-Archive -Path $tempPath -DestinationPath $targetDir -Force

# Clean up
Remove-Item $tempPath
Write-Output "Done! Cleaned up temporary file."

# Show what was unpacked
$fileCount = (Get-ChildItem -Path $targetDir -Recurse -File).Count
Write-Output "Unpacked $fileCount files to $targetDir"
