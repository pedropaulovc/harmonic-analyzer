[CmdletBinding(SupportsShouldProcess)]
param(
    [Parameter()]
    [string]$SharedRoot,

    [Parameter()]
    [string]$SourceToolboxRoot,

    [Parameter()]
    [switch]$NoConfigure,

    [Parameter()]
    [switch]$Check
)

$ErrorActionPreference = 'Stop'
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$script = Join-Path $repoRoot 'cad\scripts\provision_solidworks_seat.py'
$arguments = @('run', 'python', '-u', $script)

if ($SharedRoot) {
    $arguments += @('--shared-root', $SharedRoot)
}
if ($SourceToolboxRoot) {
    $arguments += @('--source-toolbox-root', $SourceToolboxRoot)
}
if ($NoConfigure) {
    $arguments += '--no-configure'
}
if ($Check) {
    $arguments += '--check'
}
if ($WhatIfPreference) {
    $arguments += '--what-if'
}

if (-not $PSCmdlet.ShouldProcess('SolidWorks build seat', 'Provision drawing and BA Hole Wizard standards')) {
    return
}

Push-Location $repoRoot
try {
    & uv @arguments
    if ($LASTEXITCODE -ne 0) {
        throw "SolidWorks seat provisioning failed with exit code $LASTEXITCODE"
    }
}
finally {
    Pop-Location
}

