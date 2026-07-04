# Launch Jaeger all-in-one NATIVELY (no Docker - this Azure AMD VM has no nested
# virtualization, so Docker Desktop's Linux engine can't run here).
# Jaeger v2 with no args = all-in-one, in-memory store:
#   UI :16686, OTLP/gRPC :4317, OTLP/HTTP :4318.
# Traces only - point the spine at it (or let the Collector fan-out feed it).
# (Aspire is the preferred viewer for unified logs+traces; Jaeger is the fallback.)
$root = $PSScriptRoot
$exe  = Get-ChildItem -Path "$root\bin\jaeger" -Recurse -Filter 'jaeger.exe' -ErrorAction SilentlyContinue |
            Select-Object -First 1 -ExpandProperty FullName
$log  = "$root\bin\jaeger\jaeger.log"

if (-not $exe) { throw "jaeger.exe not found under $root\bin\jaeger - run bootstrap.ps1 first" }

Get-Process jaeger -ErrorAction SilentlyContinue | Stop-Process -Force
Start-Sleep 1

$p = Start-Process -FilePath $exe `
        -RedirectStandardOutput $log -RedirectStandardError "$log.err" `
        -PassThru -WindowStyle Hidden
Write-Host "Jaeger PID $($p.Id) -> http://localhost:16686  (OTLP/HTTP :4318, gRPC :4317)"
