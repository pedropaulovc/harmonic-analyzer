# Launch the .NET Aspire dashboard NATIVELY (no Docker - this Azure AMD VM has no
# nested virtualization, so Docker Desktop's Linux engine can't run here).
# Dashboard UI :18888, OTLP/HTTP :4319, OTLP/gRPC :4320. Logs + traces unified.
# Zero auth (local dev). NOTE: the spine's default OTLP port :18890 is owned by
# the fan-out Collector (start-otelcol.ps1), which forwards traces+logs here -
# so builds reach BOTH Aspire and Jaeger with no env var.
$root  = $PSScriptRoot
$tools = "$root\bin\aspire\pkg\tools"
$log   = "$root\bin\aspire\dashboard.log"

if (-not (Test-Path "$tools\Aspire.Dashboard.exe")) {
    throw "Aspire.Dashboard.exe not found under $tools - run bootstrap.ps1 first"
}

Get-Process Aspire.Dashboard -ErrorAction SilentlyContinue | Stop-Process -Force
Start-Sleep 1

$env:DOTNET_ROOT                             = "$root\bin\dotnet"       # user-local ASP.NET Core 9 runtime
$env:ASPNETCORE_URLS                         = "http://localhost:18888"
$env:DOTNET_DASHBOARD_OTLP_HTTP_ENDPOINT_URL = "http://localhost:4319"
$env:DOTNET_DASHBOARD_OTLP_ENDPOINT_URL      = "http://localhost:4320"
$env:Dashboard__Frontend__AuthMode          = "Unsecured"              # no browser login token
$env:Dashboard__Otlp__AuthMode              = "Unsecured"

# WorkingDirectory MUST be the exe dir so ContentRoot/wwwroot (Blazor assets) resolve.
$p = Start-Process -FilePath "$tools\Aspire.Dashboard.exe" -WorkingDirectory $tools `
        -RedirectStandardOutput $log -RedirectStandardError "$log.err" `
        -PassThru -WindowStyle Hidden
Write-Host "Aspire dashboard PID $($p.Id) -> http://localhost:18888  (OTLP/HTTP :4319, gRPC :4320)"
