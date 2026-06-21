<#
.SYNOPSIS
  Delete build-cache entries not used for N days (default 7). Azure Files has no
  native lifecycle policy, so this is the eviction mechanism -- run daily by a
  Scheduled Task (register it with -Register).

.DESCRIPTION
  Cache entries are immutable content-addressed `<key>.tar.gz` blobs, so deleting
  an old one is always safe: it just becomes a miss and the next build that needs
  it rebuilds + re-pushes. Deletion keys on LastWriteTime, and _artifact_cache.py
  TOUCHES an entry on every cache HIT, so this is effectively LRU -- an artefact
  still in active use is kept alive even though its inputs never change; only
  genuinely-cold entries age out.

  -Register installs a daily Scheduled Task that runs this script (as the current
  user, only when logged on). That suits vm-solidworks: the SolidWorks COM seat
  ALREADY requires an interactive logged-in session, and only the logged-in user
  holds the cmdkey credential for the share -- a SYSTEM task would have no access.

.EXAMPLE
  scripts\azure\cleanup_build_cache.ps1 -DryRun        # show what would be deleted
  scripts\azure\cleanup_build_cache.ps1                # delete now
  scripts\azure\cleanup_build_cache.ps1 -Register      # install the daily 03:00 task
#>
[CmdletBinding()]
param(
  [int]$RetentionDays = 7,
  [string]$Path = $env:HARMONIC_CACHE_DIR,
  [switch]$DryRun,
  [switch]$Register,
  [string]$At = '03:00'
)
$ErrorActionPreference = 'Stop'
$TaskName = 'HarmonicAnalyzer-BuildCacheCleanup'

if ($Register) {
  $self = $MyInvocation.MyCommand.Path
  $action  = New-ScheduledTaskAction -Execute 'pwsh.exe' `
    -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$self`" -RetentionDays $RetentionDays"
  $trigger = New-ScheduledTaskTrigger -Daily -At $At
  # Run as the current (interactive) user -- they hold the share credential; a
  # SYSTEM principal could not reach the Azure Files UNC path.
  $principal = New-ScheduledTaskPrincipal -UserId ([Security.Principal.WindowsIdentity]::GetCurrent().Name) `
    -LogonType Interactive -RunLevel Limited
  Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger `
    -Principal $principal -Description 'Evict harmonic-analyzer build-cache entries older than N days' -Force | Out-Null
  Write-Host "Registered daily task '$TaskName' at $At (RetentionDays=$RetentionDays)."
  Write-Host "It cleans HARMONIC_CACHE_DIR as seen by '$($principal.UserId)'."
  return
}

if (-not $Path) { throw "No cache path. Set HARMONIC_CACHE_DIR or pass -Path." }
if (-not (Test-Path $Path)) { throw "Cache path not reachable: $Path (is the share mounted?)" }

$cutoff = (Get-Date).AddDays(-$RetentionDays)
Write-Host ">> evicting *.tar.gz under $Path older than $cutoff (RetentionDays=$RetentionDays)"

$stale = Get-ChildItem -Path $Path -Recurse -File -Filter '*.tar.gz' -ErrorAction SilentlyContinue |
  Where-Object { $_.LastWriteTime -lt $cutoff }

$count = 0; $bytes = 0L
foreach ($f in $stale) {
  $bytes += $f.Length; $count++
  if ($DryRun) { Write-Host "   would delete $($f.FullName)  ($([math]::Round($f.Length/1KB)) KB, $($f.LastWriteTime))" }
  else { Remove-Item $f.FullName -Force -ErrorAction SilentlyContinue }
}

if (-not $DryRun) {
  # Prune now-empty shard dirs (the 2-hex subfolders), leaving the share root.
  Get-ChildItem -Path $Path -Directory -ErrorAction SilentlyContinue | ForEach-Object {
    if (-not (Get-ChildItem $_.FullName -Recurse -File -ErrorAction SilentlyContinue)) {
      Remove-Item $_.FullName -Recurse -Force -ErrorAction SilentlyContinue
    }
  }
}

$verb = if ($DryRun) { 'would free' } else { 'freed' }
Write-Host (">> {0} {1} entr{2}, {3} MB" -f $verb, $count, $(if($count -eq 1){'y'}else{'ies'}), [math]::Round($bytes/1MB,1))
