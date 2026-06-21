<#
.SYNOPSIS
  Mount the Azure Files build-cache SMB share on this machine and wire up the
  HARMONIC_CACHE_* environment so `uv run python -m doit` uses it.

.DESCRIPTION
  1. Fetches the storage account key (via az; or pass -StorageKey to avoid az).
  2. Persists the SMB credential with cmdkey, so the UNC path authenticates
     automatically across reboots and from non-interactive build sessions.
  3. Optionally maps a drive letter (-MapDrive) for humans.
  4. Verifies the share is reachable and writable/readable as requested.
  5. Sets HARMONIC_CACHE_DIR / HARMONIC_CACHE_MODE / HARMONIC_CACHE_SALT.

  Backend is `dir` (cad/scripts/_artifact_cache.py) -- HARMONIC_CACHE_DIR points
  at the share's UNC path, so no drive letter is required for the build itself.

.NOTES
  SMB needs TCP 445 to <account>.file.core.windows.net. That's open between Azure
  VMs in-region (vm-solidworks <-> other Azure builders). From an on-prem/home
  machine many ISPs block outbound 445 -- you'd need a VPN, a private endpoint, or
  SMB-over-QUIC. The script tests 445 up front and tells you which case you're in.

  -Mode rw is for the SolidWorks seat (pull + push). -Mode ro is for seat-less
  pullers. -Scope Machine sets env for ALL users (needs an elevated shell);
  default User scope needs no elevation.
#>
[CmdletBinding()]
param(
  [ValidateSet('ro','rw')] [string]$Mode = 'ro',
  [string]$Salt = '',
  [string]$StorageAccount = 'stswbuildcache07aba2',
  [string]$Share = 'buildcache',
  [string]$ResourceGroup = 'RG-SOLIDWORKS-DEV',
  [string]$StorageKey = '',
  [switch]$MapDrive,
  [string]$DriveLetter = 'Z',
  [ValidateSet('User','Machine')] [string]$Scope = 'User'
)
$ErrorActionPreference = 'Stop'

$host_fqdn = "$StorageAccount.file.core.windows.net"
$unc = "\\$host_fqdn\$Share"

Write-Host ">> testing TCP 445 to $host_fqdn ..."
$ok445 = (Test-NetConnection -ComputerName $host_fqdn -Port 445 -WarningAction SilentlyContinue).TcpTestSucceeded
if (-not $ok445) {
  throw "Port 445 to $host_fqdn is blocked. From on-prem/home you need a VPN, a " +
        "private endpoint, or SMB-over-QUIC. (Azure VMs in $ResourceGroup's region " +
        "can reach it directly.)"
}

if (-not $StorageKey) {
  Write-Host ">> fetching storage key via az ..."
  $StorageKey = az storage account keys list `
    --account-name $StorageAccount --resource-group $ResourceGroup `
    --query "[0].value" -o tsv --only-show-errors
  if (-not $StorageKey) { throw "Could not get the storage key (az logged in?). Pass -StorageKey." }
}

Write-Host ">> persisting SMB credential (cmdkey) for $host_fqdn ..."
# Azure Files SMB auth: user = AZURE\<account>, password = account key.
cmdkey /add:$host_fqdn /user:"AZURE\$StorageAccount" /pass:$StorageKey | Out-Null

if ($MapDrive) {
  Write-Host ">> mapping ${DriveLetter}: -> $unc (persistent) ..."
  net use "${DriveLetter}:" $unc /persistent:yes /user:"AZURE\$StorageAccount" $StorageKey | Out-Null
}

Write-Host ">> verifying access ..."
if (-not (Test-Path $unc)) { throw "Share $unc not reachable after mount." }
if ($Mode -eq 'rw') {
  $probe = Join-Path $unc (".rwprobe-{0}" -f $PID)
  Set-Content -Path $probe -Value 'ok' -ErrorAction Stop
  Remove-Item $probe -Force
  Write-Host "   read-write OK"
} else {
  Get-ChildItem $unc -ErrorAction Stop | Out-Null
  Write-Host "   read OK"
}

Write-Host ">> setting HARMONIC_CACHE_* ($Scope scope) ..."
[Environment]::SetEnvironmentVariable('HARMONIC_CACHE_DIR',  $unc,  $Scope)
[Environment]::SetEnvironmentVariable('HARMONIC_CACHE_MODE', $Mode, $Scope)
if ($Salt) { [Environment]::SetEnvironmentVariable('HARMONIC_CACHE_SALT', $Salt, $Scope) }
# Make them effective in THIS session too (SetEnvironmentVariable only affects new ones).
$env:HARMONIC_CACHE_DIR  = $unc
$env:HARMONIC_CACHE_MODE = $Mode
if ($Salt) { $env:HARMONIC_CACHE_SALT = $Salt }

Write-Host ""
Write-Host "Build cache ready:"
Write-Host "    HARMONIC_CACHE_DIR  = $unc"
Write-Host "    HARMONIC_CACHE_MODE = $Mode"
if ($Salt) { Write-Host "    HARMONIC_CACHE_SALT = $Salt" }
Write-Host ""
Write-Host "Open a NEW shell (so the persisted env vars load) and run:  uv run python -m doit"
