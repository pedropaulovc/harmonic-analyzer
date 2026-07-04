# Register the OTel viewer stack (Collector fan-out + Jaeger + .NET Aspire) as
# auto-start Windows scheduled tasks that launch the start-*.ps1 scripts in THIS
# folder. Run bootstrap.ps1 first to download the binaries into ./bin.
#
#   Default:    one task per component, triggered AT LOGON of the current user,
#               run in the user's session. No admin elevation required.
#   -AtStartup: trigger AT MACHINE BOOT as SYSTEM (session 0). Requires running
#               THIS script from an elevated (Administrator) PowerShell.
#
# Re-runnable: existing tasks of the same name are replaced (-Force). Localhost
# ports are reachable from your browser regardless of which session hosts them.
#
#   Collector  in OTLP 18890/18889  ->  Aspire 4319 + Jaeger 4318  (spine default)
#   Aspire     UI 18888  OTLP/HTTP 4319  OTLP/gRPC 4320            (logs + traces)
#   Jaeger     UI 16686  OTLP/HTTP 4318  OTLP/gRPC 4317            (traces only)
param([switch]$AtStartup)

$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot
$ps   = "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe"

$tasks = @(
    @{ Name = 'Harmonic-OTel-Collector'; Script = "$root\start-otelcol.ps1";
       Desc = 'harmonic-analyzer OTel fan-out: OpenTelemetry Collector (spine default OTLP 18890/18889) -> Aspire 4319 + Jaeger 4318' }
    @{ Name = 'Harmonic-OTel-Aspire'; Script = "$root\start-aspire.ps1";
       Desc = 'harmonic-analyzer OTel viewer: .NET Aspire dashboard (UI 18888, OTLP 4319) - unified logs+traces' }
    @{ Name = 'Harmonic-OTel-Jaeger'; Script = "$root\start-jaeger.ps1";
       Desc = 'harmonic-analyzer OTel viewer: Jaeger all-in-one (UI 16686, OTLP 4318) - traces only' }
)

# One-per-boot/logon trigger; keep the launched process alive indefinitely.
if ($AtStartup) {
    $trigger   = New-ScheduledTaskTrigger -AtStartup
    $principal = New-ScheduledTaskPrincipal -UserId 'SYSTEM' -LogonType ServiceAccount -RunLevel Highest
} else {
    $me        = "$env:USERDOMAIN\$env:USERNAME"
    $trigger   = New-ScheduledTaskTrigger -AtLogOn -User $me
    $principal = New-ScheduledTaskPrincipal -UserId $me -LogonType Interactive
}

$settings = New-ScheduledTaskSettingsSet `
                -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
                -StartWhenAvailable -MultipleInstances IgnoreNew `
                -ExecutionTimeLimit ([TimeSpan]::Zero)

foreach ($t in $tasks) {
    $action = New-ScheduledTaskAction -Execute $ps `
                -Argument "-NoProfile -NonInteractive -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$($t.Script)`""
    Register-ScheduledTask -TaskName $t.Name -Description $t.Desc `
        -Action $action -Trigger $trigger -Principal $principal -Settings $settings -Force | Out-Null
    Write-Host "Registered scheduled task '$($t.Name)'  ->  $($t.Script)"
}

$when = if ($AtStartup) { 'at machine boot (SYSTEM)' } else { "at logon of $env:USERNAME" }
Write-Host "Done. The OTel viewer stack will start $when."
