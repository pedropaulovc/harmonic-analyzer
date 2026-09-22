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

A worktree whose launcher is still alive is skipped. A record is untrusted
input: its build_worktree is removed only when git lists it as a detached
linked worktree of the record's caller repository and its name is the run
GUID's first eight characters; anything else is reported as `unverified` and
left alone. Removing a build worktree
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

function Get-OwnershipProblem {
    param([Parameter(Mandatory)]$Record)

    # A record is external JSON, so its build_worktree is deleted recursively
    # only when git agrees it is what the launcher made: a detached linked
    # worktree of the recorded caller's repository, named for this run.
    $buildWorktree = [System.IO.Path]::GetFullPath([string]$Record.build_worktree)
    $match = [System.Text.RegularExpressions.Regex]::Match(
        [string]$Record.run_id,
        '\A\d{8}T\d{9}Z-(?<guid>[0-9a-f]{32})\z'
    )
    if (-not $match.Success) {
        return "run_id $($Record.run_id) is not a launcher run id"
    }
    if ((Split-Path -Path $buildWorktree -Leaf) -cne $match.Groups['guid'].Value.Substring(0, 8)) {
        return "its name does not match run $($Record.run_id)"
    }
    $caller = [string]$Record.worktree
    if ([string]::IsNullOrEmpty($caller) -or -not (Test-Path -LiteralPath $caller -PathType Container)) {
        return "the recorded caller worktree $caller is gone"
    }
    $listing = @(& git -C $caller worktree list --porcelain 2>$null)
    if ($LASTEXITCODE -ne 0) {
        return "git cannot list the worktrees of $caller"
    }
    $entries = ($listing -join "`n") -split "`n`n"
    foreach ($entry in $entries | Select-Object -Skip 1) {
        $lines = $entry -split "`n"
        $path = ($lines | Where-Object { $_.StartsWith('worktree ') } | Select-Object -First 1)
        if ($null -eq $path) {
            continue
        }
        $registered = [System.IO.Path]::GetFullPath($path.Substring('worktree '.Length))
        if (-not $registered.Equals($buildWorktree, [System.StringComparison]::OrdinalIgnoreCase)) {
            continue
        }
        if ($lines -notcontains 'detached') {
            return 'it is a linked worktree with a branch checked out'
        }
        return $null
    }
    return "it is not a linked worktree of $caller"
}

function Remove-LeftoverWorktree {
    param(
        [Parameter(Mandatory)][string]$Caller,
        [Parameter(Mandatory)][string]$Path
    )

    & git -C $Caller worktree remove --force --force $Path 2>&1 | Out-Null
    if (Test-Path -LiteralPath $Path) {
        Remove-Item -LiteralPath $Path -Recurse -Force
    }
    & git -C $Caller worktree prune 2>&1 | Out-Null
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
        $problem = Get-OwnershipProblem -Record $record
        if ($null -ne $problem) {
            Write-Warning "not removing $buildWorktree for $($record.run_id): $problem"
            $reason = 'unverified'
        }
        elseif ($PSCmdlet.ShouldProcess($buildWorktree, "remove build worktree of $($record.run_id) ($reason)")) {
            $removed = Remove-LeftoverWorktree -Caller ([string]$record.worktree) -Path $buildWorktree
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
