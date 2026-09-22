#requires -Version 7.3

<#
.SYNOPSIS
Removes build worktrees that farm-run.ps1 left behind.

.DESCRIPTION
farm-run.ps1 removes its disposable build worktree itself. One survives when
the copy-back failed (kept for inspection), when removal failed (a held file
handle), or when the launcher was killed before it could clean up. This script
reads the launch records in each -LogDirectory and removes a record's
build_worktree when the run is over:

- `done`: the record's .done marker exists, or
- `launcher-gone`: there is no .done and the launcher PID is no longer the
  process that wrote the record (it exited, or Windows reused the PID).

A worktree whose launcher is still alive is skipped. Removing a build worktree
never touches remote farm workflows; recover those from the launch log as
DEVELOPING.md describes before relaunching.

.EXAMPLE
pwsh -NoProfile -File scripts/farm-prune.ps1 -LogDirectory "C:/src/dt-logs/farm-runs,C:/src/dt-logs/pinned-control" -WhatIf
#>
[CmdletBinding(SupportsShouldProcess)]
param(
    [Parameter(Mandatory)]
    [string[]]$LogDirectory
)

$ErrorActionPreference = 'Stop'
$script:PSNativeCommandUseErrorActionPreference = $false

function Test-LauncherAlive {
    param([Parameter(Mandatory)]$Record)

    $process = Get-Process -Id ([int]$Record.pid) -ErrorAction SilentlyContinue
    if ($null -eq $process) {
        return $false
    }
    $startedAt = [System.DateTimeOffset]::Parse(
        [string]$Record.started_at,
        [System.Globalization.CultureInfo]::InvariantCulture
    ).UtcDateTime
    # The launcher starts before it writes started_at; a process that started
    # later only reuses the PID.
    return $process.StartTime.ToUniversalTime() -le $startedAt
}

function Remove-LeftoverWorktree {
    param([Parameter(Mandatory)][string]$Path)

    $commonDirectory = (& git -C $Path rev-parse --path-format=absolute --git-common-dir 2>$null |
        Select-Object -Last 1)
    $repository = if ($LASTEXITCODE -eq 0 -and $commonDirectory) {
        Split-Path -Path $commonDirectory.Trim() -Parent
    }
    if ($repository) {
        & git -C $repository worktree remove --force --force $Path 2>&1 | Out-Null
    }
    if (Test-Path -LiteralPath $Path) {
        Remove-Item -LiteralPath $Path -Recurse -Force
    }
    if ($repository) {
        & git -C $repository worktree prune 2>&1 | Out-Null
    }
    return -not (Test-Path -LiteralPath $Path)
}

# `pwsh -File` binds one token per parameter, so several directories arrive as
# one comma-separated string, as farm-run.ps1's -Targets do.
$directories = @($LogDirectory | ForEach-Object { $_.Split(',') } | ForEach-Object { $_.Trim() } |
    Where-Object { $_ })
foreach ($directory in $directories) {
    foreach ($recordFile in Get-ChildItem -LiteralPath $directory -Filter '*.run.json' -File) {
        $record = Get-Content -LiteralPath $recordFile.FullName -Raw -Encoding utf8 | ConvertFrom-Json
        $buildWorktree = [string]$record.build_worktree
        if ([string]::IsNullOrEmpty($buildWorktree) -or
            -not (Test-Path -LiteralPath $buildWorktree -PathType Container)) {
            continue
        }

        $reason = if (Test-Path -LiteralPath ([string]$record.done) -PathType Leaf) {
            'done'
        }
        elseif (-not (Test-LauncherAlive -Record $record)) {
            'launcher-gone'
        }
        if ($null -eq $reason) {
            Write-Verbose "skipping $buildWorktree`: launcher $($record.pid) of $($record.run_id) is still running"
            continue
        }

        $removed = $false
        if ($PSCmdlet.ShouldProcess($buildWorktree, "remove build worktree of $($record.run_id) ($reason)")) {
            $removed = Remove-LeftoverWorktree -Path $buildWorktree
            if (-not $removed) {
                Write-Warning "could not remove $buildWorktree; close whatever holds it open and rerun"
            }
        }
        [pscustomobject]@{
            run_id = [string]$record.run_id
            build_worktree = $buildWorktree
            reason = $reason
            removed = $removed
        }
    }
}
