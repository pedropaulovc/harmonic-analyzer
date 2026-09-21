#requires -Version 7.3

[CmdletBinding()]
param(
    [Parameter(Mandatory)]
    [string]$Worktree,

    [Parameter(Mandatory)]
    [string]$PoolHome,

    [Parameter(Mandatory)]
    [string]$LogDirectory,

    [Parameter(Mandatory)]
    [string[]]$Targets,

    [Parameter(Mandatory)]
    [ValidateRange(1, 180)]
    [int]$LeafTimeout,

    [ValidatePattern('\A[A-Za-z0-9_-]+\z')]
    [string]$Tag = 'run'
)

$ErrorActionPreference = 'Stop'
$script:PSNativeCommandUseErrorActionPreference = $false

function Resolve-ExistingDirectory {
    param(
        [Parameter(Mandatory)][string]$Path,
        [Parameter(Mandatory)][string]$ParameterName
    )

    if (-not [System.IO.Path]::IsPathFullyQualified($Path)) {
        throw "$ParameterName must be an absolute path: $Path"
    }
    if (-not (Test-Path -LiteralPath $Path -PathType Container)) {
        throw "$ParameterName is not an existing directory: $Path"
    }
    return Resolve-PhysicalDirectory -Path (Resolve-Path -LiteralPath $Path).Path
}

function Resolve-PhysicalDirectory {
    param([Parameter(Mandatory)][string]$Path)

    $fullPath = [System.IO.Path]::GetFullPath($Path)
    if (-not [System.IO.Directory]::Exists($fullPath)) {
        throw "directory does not exist: $Path"
    }

    $root = [System.IO.Path]::GetPathRoot($fullPath)
    $relative = [System.IO.Path]::GetRelativePath($root, $fullPath)
    $current = $root
    $separators = [char[]]@(
        [System.IO.Path]::DirectorySeparatorChar,
        [System.IO.Path]::AltDirectorySeparatorChar
    )
    foreach ($component in $relative.Split(
        $separators,
        [System.StringSplitOptions]::RemoveEmptyEntries
    )) {
        $current = Join-Path -Path $current -ChildPath $component
        $linkTarget = [System.IO.Directory]::ResolveLinkTarget($current, $true)
        if ($null -ne $linkTarget) {
            $current = $linkTarget.FullName
        }
    }
    return [System.IO.Path]::GetFullPath($current)
}

function Resolve-FutureDirectory {
    param(
        [Parameter(Mandatory)][string]$Path,
        [Parameter(Mandatory)][string]$ParameterName
    )

    if (-not [System.IO.Path]::IsPathFullyQualified($Path)) {
        throw "$ParameterName must be an absolute path: $Path"
    }

    $candidate = [System.IO.Path]::GetFullPath($Path)
    $missing = [System.Collections.Generic.List[string]]::new()
    $existing = $candidate
    while (-not (Test-Path -LiteralPath $existing)) {
        $leaf = Split-Path -Path $existing -Leaf
        $parent = Split-Path -Path $existing -Parent
        if ([string]::IsNullOrEmpty($leaf) -or $parent -eq $existing) {
            throw "$ParameterName cannot be resolved: $Path"
        }
        $missing.Insert(0, $leaf)
        $existing = $parent
    }
    if (-not (Test-Path -LiteralPath $existing -PathType Container)) {
        throw "$ParameterName has a non-directory parent: $existing"
    }

    $resolved = Resolve-PhysicalDirectory -Path $existing
    foreach ($component in $missing) {
        $resolved = Join-Path -Path $resolved -ChildPath $component
    }
    return [System.IO.Path]::GetFullPath($resolved)
}

function Test-PathWithin {
    param(
        [Parameter(Mandatory)][string]$Candidate,
        [Parameter(Mandatory)][string]$Root
    )

    $candidatePath = [System.IO.Path]::TrimEndingDirectorySeparator(
        [System.IO.Path]::GetFullPath($Candidate)
    )
    $rootPath = [System.IO.Path]::TrimEndingDirectorySeparator(
        [System.IO.Path]::GetFullPath($Root)
    )
    if ($candidatePath.Equals($rootPath, [System.StringComparison]::OrdinalIgnoreCase)) {
        return $true
    }
    return $candidatePath.StartsWith(
        $rootPath + [System.IO.Path]::DirectorySeparatorChar,
        [System.StringComparison]::OrdinalIgnoreCase
    )
}

function Write-JsonAtomic {
    param(
        [Parameter(Mandatory)][string]$Path,
        [Parameter(Mandatory)]$Value
    )

    if (Test-Path -LiteralPath $Path) {
        throw "refusing to overwrite existing launch record: $Path"
    }

    $directory = Split-Path -Path $Path -Parent
    $leaf = Split-Path -Path $Path -Leaf
    $temporary = Join-Path $directory ".$leaf.$([guid]::NewGuid().ToString('N')).tmp"
    try {
        $json = $Value | ConvertTo-Json -Depth 6 -Compress
        [System.IO.File]::WriteAllText(
            $temporary,
            $json + [System.Environment]::NewLine,
            [System.Text.UTF8Encoding]::new($false)
        )
        [System.IO.File]::Move($temporary, $Path)
    }
    finally {
        if (Test-Path -LiteralPath $temporary) {
            Remove-Item -LiteralPath $temporary -Force
        }
    }
}

function New-EmptyFileExclusive {
    param([Parameter(Mandatory)][string]$Path)

    $stream = [System.IO.File]::Open(
        $Path,
        [System.IO.FileMode]::CreateNew,
        [System.IO.FileAccess]::Write,
        [System.IO.FileShare]::Read
    )
    $stream.Dispose()
}

$logCreated = $false
$startupRecordWritten = $false
try {
    $resolvedWorktree = Resolve-ExistingDirectory -Path $Worktree -ParameterName 'Worktree'
    $resolvedPoolHome = Resolve-ExistingDirectory -Path $PoolHome -ParameterName 'PoolHome'
    if (-not (Test-Path -LiteralPath (Join-Path $resolvedWorktree 'build.py') -PathType Leaf)) {
        throw "Worktree does not contain build.py: $resolvedWorktree"
    }
    if (-not (Test-Path -LiteralPath (Join-Path $resolvedPoolHome 'farm.py') -PathType Leaf)) {
        throw "PoolHome does not contain farm.py: $resolvedPoolHome"
    }

    $targetList = [System.Collections.Generic.List[string]]::new()
    foreach ($argument in @($Targets)) {
        foreach ($component in ([string]$argument).Split(',')) {
            $target = $component.Trim()
            if ([string]::IsNullOrEmpty($target)) {
                throw 'Targets contains an empty component'
            }
            if ($target.StartsWith('-', [System.StringComparison]::Ordinal)) {
                throw "Targets contains an option-like selection: $target"
            }
            if ($target.Contains('=')) {
                throw "Targets accepts task selections, not doit variables: $target"
            }
            $targetList.Add($target)
        }
    }
    if ($targetList.Count -eq 0) {
        throw 'Targets must contain at least one task selection'
    }
    [string[]]$normalizedTargets = @($targetList)

    $resolvedLogDirectory = Resolve-FutureDirectory -Path $LogDirectory -ParameterName 'LogDirectory'
    if (Test-PathWithin -Candidate $resolvedLogDirectory -Root $resolvedWorktree) {
        throw "LogDirectory must be outside the target worktree: $resolvedLogDirectory"
    }
    if (-not (Test-Path -LiteralPath $resolvedLogDirectory)) {
        [System.IO.Directory]::CreateDirectory($resolvedLogDirectory) | Out-Null
    }
    if (-not (Test-Path -LiteralPath $resolvedLogDirectory -PathType Container)) {
        throw "LogDirectory is not a directory: $resolvedLogDirectory"
    }
    $resolvedLogDirectory = Resolve-PhysicalDirectory -Path $resolvedLogDirectory
    if (Test-PathWithin -Candidate $resolvedLogDirectory -Root $resolvedWorktree) {
        throw "LogDirectory must be outside the target worktree: $resolvedLogDirectory"
    }

    $headOutput = @(& git -C $resolvedWorktree rev-parse --verify HEAD 2>&1)
    $gitCode = $LASTEXITCODE
    if ($gitCode -ne 0) {
        throw "git rev-parse failed with exit $gitCode`: $($headOutput -join [System.Environment]::NewLine)"
    }
    $commit = ([string]($headOutput | Select-Object -Last 1)).Trim()
    if (-not [System.Text.RegularExpressions.Regex]::IsMatch(
        $commit,
        '\A[0-9a-fA-F]{40}\z',
        [System.Text.RegularExpressions.RegexOptions]::CultureInvariant
    )) {
        throw "git rev-parse returned an invalid commit identity: $commit"
    }

    $originOutput = @(
        & git -C $resolvedWorktree for-each-ref "--contains=$commit" '--format=%(refname)' refs/remotes/origin 2>&1
    )
    $gitCode = $LASTEXITCODE
    if ($gitCode -ne 0) {
        throw "git origin reachability check failed with exit $gitCode`: $($originOutput -join [System.Environment]::NewLine)"
    }
    $knownOnOrigin = @(
        $originOutput | Where-Object {
            ([string]$_).Trim().StartsWith(
                'refs/remotes/origin/',
                [System.StringComparison]::Ordinal
            )
        }
    )
    if ($knownOnOrigin.Count -eq 0) {
        throw 'HEAD is not known on origin; fetch and push before launching'
    }

    $cacheEnvironment = [ordered]@{
        HARMONIC_CACHE_ACCOUNT = [System.Environment]::GetEnvironmentVariable('HARMONIC_CACHE_ACCOUNT', 'Process')
        HARMONIC_CACHE_CONTAINER = [System.Environment]::GetEnvironmentVariable('HARMONIC_CACHE_CONTAINER', 'Process')
        HARMONIC_CACHE_SALT = [System.Environment]::GetEnvironmentVariable('HARMONIC_CACHE_SALT', 'Process')
    }

    $buildArgs = @(
        'run', '--frozen', 'python', 'build.py',
        '--executor', 'farm',
        '--leaf-timeout', [string]$LeafTimeout,
        '--verbosity', 'info',
        '-n', '4',
        '--continue'
    ) + $normalizedTargets
    [string[]]$nativeArgv = @('uv') + $buildArgs

    do {
        $runId = '{0}-{1}' -f (
            [System.DateTime]::UtcNow.ToString(
                'yyyyMMddTHHmmssfffZ',
                [System.Globalization.CultureInfo]::InvariantCulture
            )
        ), ([guid]::NewGuid().ToString('N'))
        $recordPath = Join-Path $resolvedLogDirectory "$runId.run.json"
        $logPath = Join-Path $resolvedLogDirectory "$runId.log"
        $donePath = Join-Path $resolvedLogDirectory "$runId.done"
        $hasConflict = (
            (Test-Path -LiteralPath $recordPath) -or
            (Test-Path -LiteralPath $logPath) -or
            (Test-Path -LiteralPath $donePath)
        )
    } while ($hasConflict)

    New-EmptyFileExclusive -Path $logPath
    $logCreated = $true
    $startedAt = [System.DateTime]::UtcNow
    $timer = [System.Diagnostics.Stopwatch]::StartNew()
    $runRecord = [ordered]@{
        run_id = $runId
        state = 'running'
        worktree = $resolvedWorktree
        pool_home = $resolvedPoolHome
        commit = $commit
        targets = @($normalizedTargets)
        leaf_timeout_minutes = $LeafTimeout
        started_at = $startedAt.ToString('o', [System.Globalization.CultureInfo]::InvariantCulture)
        pid = $PID
        log = [System.IO.Path]::GetFullPath($logPath)
        done = [System.IO.Path]::GetFullPath($donePath)
        cache_environment = $cacheEnvironment
        tag = $Tag
        argv = @($nativeArgv)
    }
    Write-JsonAtomic -Path $recordPath -Value $runRecord
    $startupRecordWritten = $true
}
catch {
    $startupFailure = $_.Exception.Message
    if ($logCreated -and -not $startupRecordWritten -and (Test-Path -LiteralPath $logPath)) {
        try {
            Remove-Item -LiteralPath $logPath -Force
        }
        catch {
            $startupFailure = (
                "$startupFailure; additionally failed to remove unclaimed log " +
                "$logPath`: $($_.Exception.Message)"
            )
        }
    }
    [System.Console]::Error.WriteLine($startupFailure)
    exit 1
}

$exitCode = 1
$terminalState = 'failed'
try {
    Write-Output "farm-launch started $runId $([System.IO.Path]::GetFullPath($recordPath))"
    $env:SOLIDWORKS_POOL_HOME = $resolvedPoolHome
    $env:HARMONIC_REMOTE_CACHE_MODE = 'rw'
    $env:PYTHONUNBUFFERED = '1'
    Push-Location -LiteralPath $resolvedWorktree
    try {
        & uv @buildArgs *>&1 | Tee-Object -FilePath $logPath
        $code = $LASTEXITCODE
    }
    finally {
        Pop-Location
    }
    if ($null -eq $code) {
        throw 'uv did not report a native exit code'
    }
    $exitCode = [int]$code
    if ($exitCode -eq 0) {
        $terminalState = 'succeeded'
    }
}
catch {
    $exitCode = 1
    $terminalState = 'failed'
    $diagnostic = "farm-launch wrapper failed: $($_.Exception.Message)"
    try {
        Add-Content -LiteralPath $logPath -Value $diagnostic -Encoding utf8
    }
    catch {
        [System.Console]::Error.WriteLine(
            "$diagnostic; additionally failed to append the diagnostic to $logPath`: $($_.Exception.Message)"
        )
    }
    [System.Console]::Error.WriteLine($diagnostic)
}

$timer.Stop()
$doneRecord = [ordered]@{}
foreach ($entry in $runRecord.GetEnumerator()) {
    $doneRecord[$entry.Key] = $entry.Value
}
$doneRecord['state'] = $terminalState
$doneRecord['exit_code'] = $exitCode
$doneRecord['elapsed_s'] = [System.Math]::Round($timer.Elapsed.TotalSeconds, 3)
$doneRecord['finished_at'] = [System.DateTime]::UtcNow.ToString(
    'o',
    [System.Globalization.CultureInfo]::InvariantCulture
)

try {
    Write-JsonAtomic -Path $donePath -Value $doneRecord
}
catch {
    [System.Console]::Error.WriteLine(
        "farm-launch failed to write terminal marker $donePath`: $($_.Exception.Message)"
    )
    if ($exitCode -eq 0) {
        $exitCode = 1
    }
    exit $exitCode
}

Write-Output ($doneRecord | ConvertTo-Json -Depth 6 -Compress)
exit $exitCode
