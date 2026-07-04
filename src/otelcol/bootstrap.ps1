# Bootstrap the local OTel viewer stack into ./bin (all gitignored). No Docker,
# no admin - user-local downloads only. Re-runnable (re-downloads / overwrites).
#
#   dotnet   ASP.NET Core Runtime 9.0      -> bin/dotnet    (Aspire needs it)
#   aspire   Aspire.Dashboard.Sdk.win-x64  -> bin/aspire    (dashboard exe)
#   jaeger   jaeger v2 all-in-one          -> bin/jaeger    (traces viewer)
#   otelcol  OpenTelemetry Collector       -> bin/otelcol   (fan-out)
#
# After bootstrap, register auto-start tasks with register-startup-tasks.ps1.
param(
    [string]$AspireVersion  = '13.4.6',
    [string]$JaegerVersion  = '2.19.0',
    [string]$OtelcolVersion = '0.155.0',
    [string]$DotnetChannel  = '9.0'
)
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'   # Invoke-WebRequest is ~10x faster without the progress bar
$root = $PSScriptRoot
$bin  = "$root\bin"
New-Item -ItemType Directory -Force $bin | Out-Null

# --- .NET ASP.NET Core runtime (user-local, no admin) ---
Write-Host "==> ASP.NET Core Runtime $DotnetChannel -> bin/dotnet"
$dotnetDir = "$bin\dotnet"
$installer = "$bin\dotnet-install.ps1"
Invoke-WebRequest -Uri 'https://dot.net/v1/dotnet-install.ps1' -OutFile $installer
& $installer -Runtime aspnetcore -Channel $DotnetChannel -InstallDir $dotnetDir -NoPath
Remove-Item $installer -ErrorAction SilentlyContinue

# --- Aspire dashboard (NuGet flat-container) ---
Write-Host "==> Aspire.Dashboard.Sdk.win-x64 $AspireVersion -> bin/aspire"
$aspireDir = "$bin\aspire"
New-Item -ItemType Directory -Force $aspireDir | Out-Null
$nupkg = "$aspireDir\aspire-dashboard.nupkg"
Invoke-WebRequest -Uri "https://api.nuget.org/v3-flatcontainer/aspire.dashboard.sdk.win-x64/$AspireVersion/aspire.dashboard.sdk.win-x64.$AspireVersion.nupkg" -OutFile $nupkg
$pkg = "$aspireDir\pkg"
if (Test-Path $pkg) { Remove-Item -Recurse -Force $pkg }
Expand-Archive -Path $nupkg -DestinationPath $pkg -Force
Remove-Item $nupkg -ErrorAction SilentlyContinue

# --- Jaeger all-in-one ---
Write-Host "==> Jaeger $JaegerVersion -> bin/jaeger"
$jaegerDir = "$bin\jaeger"
New-Item -ItemType Directory -Force $jaegerDir | Out-Null
$zip = "$jaegerDir\jaeger.zip"
Invoke-WebRequest -Uri "https://github.com/jaegertracing/jaeger/releases/download/v$JaegerVersion/jaeger-$JaegerVersion-windows-amd64.zip" -OutFile $zip
Expand-Archive -Path $zip -DestinationPath $jaegerDir -Force
Remove-Item $zip -ErrorAction SilentlyContinue

# --- OpenTelemetry Collector ---
Write-Host "==> OpenTelemetry Collector $OtelcolVersion -> bin/otelcol"
$otelDir = "$bin\otelcol"
New-Item -ItemType Directory -Force $otelDir | Out-Null
$tgz = "$otelDir\otelcol.tar.gz"
Invoke-WebRequest -Uri "https://github.com/open-telemetry/opentelemetry-collector-releases/releases/download/v$OtelcolVersion/otelcol_${OtelcolVersion}_windows_amd64.tar.gz" -OutFile $tgz
tar -xf $tgz -C $otelDir
Remove-Item $tgz -ErrorAction SilentlyContinue

# --- Validate the collector config against the freshly downloaded binary ---
Write-Host "==> validating config.yaml"
& "$otelDir\otelcol.exe" validate --config "$root\config.yaml"

Write-Host ""
Write-Host "Bootstrap complete. Register auto-start tasks with:"
Write-Host "    powershell -ExecutionPolicy Bypass -File `"$root\register-startup-tasks.ps1`""
