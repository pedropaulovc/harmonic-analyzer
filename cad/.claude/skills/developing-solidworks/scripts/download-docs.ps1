# Download and unpack the latest SolidWorks API documentation from GitHub releases
$response = Invoke-RestMethod -Uri 'https://api.github.com/repos/pedropaulovc/offline-solidworks-api-docs/releases/latest'
$asset = $response.assets | Where-Object { $_.name -like '*llms.v*.zip' }

if (-not $asset) {
    Write-Error "Could not find llms zip file in release"
    exit 1
}

$downloadUrl = $asset.browser_download_url
Write-Output "Downloading from: $downloadUrl"

# Download with progress
$tempPath = Join-Path $env:TEMP 'solidworks-docs.zip'
$totalSize = $asset.size
$totalSizeMB = [math]::Round($totalSize / 1MB, 2)

Write-Output "File size: $totalSizeMB MB"

# Use WebClient for progress tracking
$webClient = New-Object System.Net.WebClient
$stopwatch = [System.Diagnostics.Stopwatch]::StartNew()
$lastBytes = 0
$lastTime = 0

$progressHandler = {
    param($sender, $e)
    $percent = $e.ProgressPercentage
    $receivedMB = [math]::Round($e.BytesReceived / 1MB, 2)

    # Calculate speed
    $elapsed = $stopwatch.ElapsedMilliseconds
    if ($elapsed -gt $script:lastTime + 500) {
        $bytesThisPeriod = $e.BytesReceived - $script:lastBytes
        $timePeriod = ($elapsed - $script:lastTime) / 1000
        $speedMBps = [math]::Round(($bytesThisPeriod / 1MB) / $timePeriod, 2)
        $script:lastBytes = $e.BytesReceived
        $script:lastTime = $elapsed
        $script:currentSpeed = $speedMBps
    }

    $speedDisplay = if ($script:currentSpeed) { "$($script:currentSpeed) MB/s" } else { "calculating..." }

    Write-Progress -Activity "Downloading SolidWorks API docs" `
        -Status "$receivedMB / $totalSizeMB MB ($speedDisplay)" `
        -PercentComplete $percent
}

$completedHandler = {
    Write-Progress -Activity "Downloading SolidWorks API docs" -Completed
}

Register-ObjectEvent -InputObject $webClient -EventName DownloadProgressChanged -Action $progressHandler | Out-Null
Register-ObjectEvent -InputObject $webClient -EventName DownloadFileCompleted -Action $completedHandler | Out-Null

$webClient.DownloadFileAsync([Uri]$downloadUrl, $tempPath)

# Wait for download to complete
while ($webClient.IsBusy) {
    Start-Sleep -Milliseconds 100
}

$stopwatch.Stop()
$webClient.Dispose()
Get-EventSubscriber | Unregister-Event

Write-Output "Downloaded to: $tempPath"

# Create target directory if it doesn't exist
$targetDir = Join-Path $PSScriptRoot ".."
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
