# Launch the OpenTelemetry Collector as a fan-out (no Docker). Receives OTLP on
# :18890 (HTTP) / :18889 (gRPC) - the spine's DEFAULT port, so a plain build with
# no env var lands here - and duplicates every trace to BOTH dashboards:
#   Aspire  http://localhost:4319  (traces + logs)
#   Jaeger  http://localhost:4318  (traces only)
$root = $PSScriptRoot
$exe  = "$root\bin\otelcol\otelcol.exe"
$cfg  = "$root\config.yaml"
$log  = "$root\bin\otelcol\otelcol.log"

if (-not (Test-Path $exe)) { throw "otelcol.exe not found at $exe - run bootstrap.ps1 first" }

Get-Process otelcol -ErrorAction SilentlyContinue | Stop-Process -Force
Start-Sleep 1

$p = Start-Process -FilePath $exe -ArgumentList "--config", "`"$cfg`"" `
        -RedirectStandardOutput $log -RedirectStandardError "$log.err" `
        -PassThru -WindowStyle Hidden
Write-Host "otelcol PID $($p.Id) -> OTLP in :18890 (HTTP) / :18889 (gRPC); fanning to Aspire :4319 + Jaeger :4318"
