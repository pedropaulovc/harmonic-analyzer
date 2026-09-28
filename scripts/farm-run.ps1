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

function Invoke-GitLines {
    param(
        [Parameter(Mandatory)][string]$Repository,
        [Parameter(Mandatory)][string[]]$Arguments
    )

    $output = @(& git -C $Repository @Arguments 2>&1)
    $code = $LASTEXITCODE
    if ($code -ne 0) {
        throw "git $($Arguments -join ' ') failed with exit $code`: $($output -join [System.Environment]::NewLine)"
    }
    return [string[]]@($output | ForEach-Object { [string]$_ })
}

function Get-ExcludedSubmodules {
    param(
        [Parameter(Mandatory)][string]$Repository,
        [Parameter(Mandatory)][string]$Commit
    )

    # The commit's own .farm-sources.json, normalized as build.py and the worker
    # normalize it; a missing file excludes nothing, a malformed one is refused.
    & git -C $Repository cat-file -e "$Commit`:.farm-sources.json" 2>$null
    if ($LASTEXITCODE -ne 0) {
        return [string[]]@()
    }
    $text = (Invoke-GitLines -Repository $Repository -Arguments @(
        'show', "$Commit`:.farm-sources.json"
    )) -join "`n"
    try {
        $declared = ConvertFrom-Json -InputObject $text -AsHashtable
    }
    catch {
        throw ".farm-sources.json at $Commit is not valid JSON: $($_.Exception.Message)"
    }
    if ($declared -isnot [System.Collections.IDictionary]) {
        throw ".farm-sources.json at $Commit must be a JSON object"
    }
    $paths = $declared['exclude_submodules']
    if ($null -eq $paths) {
        return [string[]]@()
    }
    if ($paths -is [string] -or $paths -isnot [System.Collections.IEnumerable]) {
        throw ".farm-sources.json at ${Commit}: exclude_submodules must be a list of strings"
    }
    $excluded = [System.Collections.Generic.List[string]]::new()
    foreach ($path in $paths) {
        if ($path -isnot [string]) {
            throw ".farm-sources.json at ${Commit}: exclude_submodules must be a list of strings"
        }
        $excluded.Add(($path -replace '^(\./)+', '' -replace '/+$', ''))
    }
    return [string[]]@($excluded)
}

function Invoke-TeedNative {
    param(
        [Parameter(Mandatory)][string]$LogPath,
        [Parameter(Mandatory)][string]$FilePath,
        [Parameter(Mandatory)][string[]]$ArgumentList
    )

    # Tee-Object cannot append to a -LiteralPath, and a -FilePath would treat
    # brackets in LogDirectory as wildcards; so append through one shared
    # handle that readers can open while the child is still streaming.
    $stream = [System.IO.FileStream]::new(
        $LogPath,
        [System.IO.FileMode]::Append,
        [System.IO.FileAccess]::Write,
        [System.IO.FileShare]::ReadWrite
    )
    $writer = [System.IO.StreamWriter]::new($stream, [System.Text.UTF8Encoding]::new($false))
    $writer.AutoFlush = $true
    try {
        & $FilePath @ArgumentList *>&1 | ForEach-Object {
            $writer.WriteLine([string]$_)
            $_
        }
    }
    finally {
        $writer.Dispose()
    }
}

function Invoke-LoggedNative {
    param(
        [Parameter(Mandatory)][string]$LogPath,
        [Parameter(Mandatory)][string]$FilePath,
        [Parameter(Mandatory)][string[]]$ArgumentList
    )

    Invoke-TeedNative -LogPath $LogPath -FilePath $FilePath -ArgumentList $ArgumentList
    $code = $LASTEXITCODE
    if ($code -ne 0) {
        throw "$FilePath $($ArgumentList -join ' ') failed with exit $code"
    }
}

function Write-LaunchLine {
    param(
        [Parameter(Mandatory)][string]$LogPath,
        [Parameter(Mandatory)][string]$Line
    )

    Write-Output $Line
    Add-Content -LiteralPath $LogPath -Value $Line -Encoding utf8
}

function Initialize-SharedEnvironment {
    param(
        [Parameter(Mandatory)][string]$EnvironmentPath,
        [Parameter(Mandatory)][string]$SnapshotPath,
        [Parameter(Mandatory)][string]$LogPath,
        [Parameter(Mandatory)][string]$StagingSuffix,
        [Parameter(Mandatory)]$Identity
    )

    # One environment per dependency identity, synced once and never again:
    # every run that shares it builds from a snapshot whose uv.lock,
    # pyproject.toml, .python-version and required submodule pins are
    # identical, and the environment holds no editable pointer into any
    # snapshot (--no-editable), so a finished run's snapshot can go away while
    # another run still imports from the environment.
    #
    # It is published whole: each launcher syncs into a staging directory of
    # its own and renames it into place only after uv has exited and the marker
    # is written. No launcher ever deletes or syncs into a directory another
    # process may be using -- not even when a killed launcher's uv outlives it
    # -- and the rename either publishes or finds a published one. The venv is
    # created --relocatable so its entry points survive that rename.
    $marker = Join-Path $EnvironmentPath '.farm-run-environment.json'
    if (Test-Path -LiteralPath $marker -PathType Leaf) {
        return $true
    }
    if (Test-Path -LiteralPath $EnvironmentPath) {
        throw (
            "Shared environment $EnvironmentPath exists without its marker; launchers only " +
            "ever publish complete environments, so remove it once no launcher uses it"
        )
    }
    [System.IO.Directory]::CreateDirectory((Split-Path -Path $EnvironmentPath -Parent)) | Out-Null
    $staging = "$EnvironmentPath.staging-$StagingSuffix"
    $previous = $env:VIRTUAL_ENV
    Push-Location -LiteralPath $SnapshotPath
    try {
        Invoke-LoggedNative -LogPath $LogPath -FilePath 'uv' -ArgumentList @(
            'venv', '--quiet', '--relocatable', $staging
        ) | Out-Host
        $env:VIRTUAL_ENV = $staging
        Invoke-LoggedNative -LogPath $LogPath -FilePath 'uv' -ArgumentList @(
            'sync', '--frozen', '--no-editable', '--active'
        ) | Out-Host
        Write-JsonAtomic -Path (Join-Path $staging '.farm-run-environment.json') -Value $Identity
    }
    catch {
        Remove-Item -LiteralPath $staging -Recurse -Force -ErrorAction SilentlyContinue
        throw "uv sync of the shared environment $EnvironmentPath failed: $($_.Exception.Message)"
    }
    finally {
        Pop-Location
        $env:VIRTUAL_ENV = $previous
    }
    try {
        [System.IO.Directory]::Move($staging, $EnvironmentPath)
        return $false
    }
    catch {
        if (-not (Test-Path -LiteralPath $marker -PathType Leaf)) {
            throw "could not publish the shared environment $staging as $EnvironmentPath`: $($_.Exception.Message)"
        }
        # Another launcher published the same dependencies first; its copy is
        # identical, and ours was never used.
        Remove-Item -LiteralPath $staging -Recurse -Force -ErrorAction SilentlyContinue
        Add-Content -LiteralPath $LogPath -Encoding utf8 -Value (
            "farm-launch environment $EnvironmentPath was published by another launcher first; using it"
        )
        return $true
    }
}

function Complete-Snapshot {
    param(
        [Parameter(Mandatory)][string]$Worktree,
        [Parameter(Mandatory)][string]$SnapshotPath,
        [Parameter(Mandatory)][string]$OutputsPath
    )

    # The snapshot's tracked content is the recorded commit, reproducible at
    # will; what only this run produced is its cad/out (restored artefacts,
    # reports, cache.jsonl, logs). Keep that on every outcome, then remove the
    # snapshot -- unless its outputs could not be moved out, in which case the
    # snapshot itself is the only copy and stays for forensics. ``outputs`` is
    # where they actually are afterwards ($null when the build made none).
    $result = [ordered]@{
        outputs = $null
        outputs_preserved = $false
        outputs_stranded = $false
        snapshot_removed = $false
        cleanup_errors = [System.Collections.Generic.List[string]]::new()
    }
    if (-not (Test-Path -LiteralPath $SnapshotPath)) {
        $result['snapshot_removed'] = $true
        return $result
    }
    $snapshotOutputs = Join-Path $SnapshotPath 'cad\out'
    if (Test-Path -LiteralPath $snapshotOutputs -PathType Container) {
        try {
            [System.IO.Directory]::Move($snapshotOutputs, $OutputsPath)
            $result['outputs'] = $OutputsPath
            $result['outputs_preserved'] = $true
        }
        catch {
            $result['outputs'] = $snapshotOutputs
            $result['outputs_stranded'] = $true
            $result['cleanup_errors'].Add(
                "could not move $snapshotOutputs to $OutputsPath; the snapshot is kept: $($_.Exception.Message)"
            )
            return $result
        }
    }
    $removal = @(& git -C $Worktree worktree remove --force $SnapshotPath 2>&1)
    $code = $LASTEXITCODE
    if ($code -eq 0) {
        $result['snapshot_removed'] = $true
    }
    else {
        $result['cleanup_errors'].Add(
            "git worktree remove --force $SnapshotPath failed with exit $code`: $($removal -join ' ')"
        )
    }
    return $result
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
    # The build snapshots live under LogDirectory. Inside any Git worktree they
    # would appear there as an untracked nested checkout -- dirtying a tree some
    # other farm preflight may need clean -- so refuse every worktree, not just
    # the target, before creating anything.
    $probe = $resolvedLogDirectory
    while (-not (Test-Path -LiteralPath $probe)) {
        $probe = Split-Path -Path $probe -Parent
    }
    $insideOutput = @(& git -C $probe rev-parse --is-inside-work-tree 2>$null)
    if ($LASTEXITCODE -eq 0 -and ([string]($insideOutput | Select-Object -Last 1)).Trim() -eq 'true') {
        throw "LogDirectory must be outside every Git worktree (build snapshots are created under it): $resolvedLogDirectory"
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

    # The build runs from a snapshot of the pushed HEAD, so an uncommitted edit
    # here would silently not be built. Refuse it, as build.py's preflight did
    # when the build ran in this tree. --no-optional-locks: never write the
    # caller's index.
    $dirty = Invoke-GitLines -Repository $resolvedWorktree -Arguments @(
        '--no-optional-locks', 'status', '--porcelain=v1', '--untracked-files=all'
    )
    if ($dirty.Count -gt 0) {
        throw (
            "Worktree has uncommitted changes; the launcher builds its pushed HEAD only, " +
            "so commit and push them first:" + [System.Environment]::NewLine +
            (($dirty | ForEach-Object { "  $_" }) -join [System.Environment]::NewLine)
        )
    }

    $excludedSubmodules = Get-ExcludedSubmodules -Repository $resolvedWorktree -Commit $commit
    $requiredSubmodules = [System.Collections.Generic.List[string]]::new()
    $environmentInputs = [System.Collections.Generic.List[string]]::new()
    $environmentInputs.Add('farm-run-environment/1 uv-sync --frozen --no-editable')
    foreach ($line in (Invoke-GitLines -Repository $resolvedWorktree -Arguments @(
        'ls-tree', '--full-tree', $commit, '--', 'uv.lock', 'pyproject.toml', '.python-version'
    ))) {
        $environmentInputs.Add($line)
    }
    foreach ($line in (Invoke-GitLines -Repository $resolvedWorktree -Arguments @(
        'ls-tree', '-r', '--full-tree', $commit
    ))) {
        if (-not $line.StartsWith('160000 commit ', [System.StringComparison]::Ordinal)) {
            continue
        }
        $path = $line.Split("`t", 2)[1]
        if ($excludedSubmodules -contains $path) {
            continue
        }
        $requiredSubmodules.Add($path)
        $environmentInputs.Add($line)
    }
    $environmentKey = [System.Convert]::ToHexString(
        [System.Security.Cryptography.SHA256]::HashData(
            [System.Text.Encoding]::UTF8.GetBytes(($environmentInputs -join "`n"))
        )
    ).Substring(0, 16).ToLowerInvariant()
    $environmentPath = Join-Path (Join-Path $resolvedLogDirectory 'envs') $environmentKey

    $cacheEnvironment = [ordered]@{
        HARMONIC_CACHE_ACCOUNT = [System.Environment]::GetEnvironmentVariable('HARMONIC_CACHE_ACCOUNT', 'Process')
        HARMONIC_CACHE_CONTAINER = [System.Environment]::GetEnvironmentVariable('HARMONIC_CACHE_CONTAINER', 'Process')
        HARMONIC_CACHE_SALT = [System.Environment]::GetEnvironmentVariable('HARMONIC_CACHE_SALT', 'Process')
    }

    # The shared environment is already synced (Initialize-SharedEnvironment),
    # so the build never re-syncs it (--no-sync) and runs in it rather than in
    # a per-snapshot .venv (--active, which reads VIRTUAL_ENV). VIRTUAL_ENV is
    # also what build.py strips before it runs the pool's own uv project, so
    # the shared environment cannot leak into the pool.
    # No -n: build.py keeps HARMONIC_FARM_PARALLELISM (default 8) leaves in
    # flight, more than the fleet's worker count, so a worker never idles
    # waiting for the submitter to hand it the next ready leaf.
    $buildArgs = @(
        'run', '--frozen', '--no-sync', '--active', 'python', 'build.py',
        '--executor', 'farm',
        '--leaf-timeout', [string]$LeafTimeout,
        '--verbosity', 'info',
        '--continue'
    ) + $normalizedTargets
    [string[]]$nativeArgv = @('uv') + $buildArgs

    do {
        $runGuid = [guid]::NewGuid().ToString('N')
        $runId = '{0}-{1}' -f (
            [System.DateTime]::UtcNow.ToString(
                'yyyyMMddTHHmmssfffZ',
                [System.Globalization.CultureInfo]::InvariantCulture
            )
        ), $runGuid
        $recordPath = Join-Path $resolvedLogDirectory "$runId.run.json"
        $logPath = Join-Path $resolvedLogDirectory "$runId.log"
        $donePath = Join-Path $resolvedLogDirectory "$runId.done"
        $outputsPath = Join-Path $resolvedLogDirectory "$runId.out"
        # A short name keeps the snapshot's deepest tracked path under MAX_PATH;
        # the run record maps it back to the run.
        $snapshotPath = Join-Path (Join-Path $resolvedLogDirectory 'snapshots') $runGuid.Substring(0, 12)
        $hasConflict = (
            (Test-Path -LiteralPath $recordPath) -or
            (Test-Path -LiteralPath $logPath) -or
            (Test-Path -LiteralPath $donePath) -or
            (Test-Path -LiteralPath $outputsPath) -or
            (Test-Path -LiteralPath $snapshotPath)
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
        snapshot = $snapshotPath
        outputs = $outputsPath
        environment = $environmentPath
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
$launchOverhead = $null
$environmentReused = $null
try {
    Write-Output "farm-launch started $runId $([System.IO.Path]::GetFullPath($recordPath))"
    $env:SOLIDWORKS_POOL_HOME = $resolvedPoolHome
    $env:HARMONIC_REMOTE_CACHE_MODE = 'rw'
    $env:PYTHONUNBUFFERED = '1'

    # The submitter keys every task from the files it sees when it reaches the
    # task, while every worker builds $commit. Building from a private detached
    # snapshot of $commit means an edit or a commit in the caller's worktree
    # mid-run cannot reach the submitter (#1114).
    $prepareTimer = [System.Diagnostics.Stopwatch]::StartNew()
    [System.IO.Directory]::CreateDirectory((Split-Path -Path $snapshotPath -Parent)) | Out-Null
    Invoke-LoggedNative -LogPath $logPath -FilePath 'git' -ArgumentList @(
        '-C', $resolvedWorktree, 'worktree', 'add', '--quiet', '--detach', $snapshotPath, $commit
    )
    if ($requiredSubmodules.Count -gt 0) {
        Invoke-LoggedNative -LogPath $logPath -FilePath 'git' -ArgumentList (
            @('-C', $snapshotPath, 'submodule', 'update', '--quiet', '--init', '--recursive', '--') +
            @($requiredSubmodules)
        )
    }
    $environmentReused = Initialize-SharedEnvironment `
        -EnvironmentPath $environmentPath `
        -SnapshotPath $snapshotPath `
        -LogPath $logPath `
        -StagingSuffix $runGuid.Substring(0, 12) `
        -Identity ([ordered]@{
            inputs = @($environmentInputs)
            created_by_run = $runId
            commit = $commit
            created_at = [System.DateTime]::UtcNow.ToString(
                'o',
                [System.Globalization.CultureInfo]::InvariantCulture
            )
        })
    $prepareTimer.Stop()
    $launchOverhead = [System.Math]::Round($prepareTimer.Elapsed.TotalSeconds, 3)
    $environmentState = if ($environmentReused) { 'reused' } else { 'created' }
    Write-LaunchLine -LogPath $logPath -Line (
        "farm-launch snapshot $snapshotPath at $commit ready in $launchOverhead s; " +
        "environment $environmentState`: $environmentPath"
    )

    $env:VIRTUAL_ENV = $environmentPath
    Push-Location -LiteralPath $snapshotPath
    try {
        Invoke-TeedNative -LogPath $logPath -FilePath 'uv' -ArgumentList $buildArgs
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

try {
    $cleanup = Complete-Snapshot `
        -Worktree $resolvedWorktree `
        -SnapshotPath $snapshotPath `
        -OutputsPath $outputsPath
}
catch {
    # Never let cleanup cost the terminal record.
    $strandedOutputs = Join-Path $snapshotPath 'cad\out'
    $preserved = Test-Path -LiteralPath $outputsPath
    $stranded = (-not $preserved) -and (Test-Path -LiteralPath $strandedOutputs)
    $cleanup = [ordered]@{
        outputs = if ($preserved) { $outputsPath } elseif ($stranded) { $strandedOutputs } else { $null }
        outputs_preserved = $preserved
        outputs_stranded = $stranded
        snapshot_removed = -not (Test-Path -LiteralPath $snapshotPath)
        cleanup_errors = @("snapshot cleanup failed: $($_.Exception.Message)")
    }
}
if ($cleanup['outputs_stranded']) {
    # The build's outputs are only in the kept snapshot, not where the record
    # says a finished run's outputs are: whatever the child did, this run is
    # not complete until someone recovers them.
    $terminalState = 'failed'
    if ($exitCode -eq 0) {
        $exitCode = 1
    }
}
foreach ($problem in $cleanup['cleanup_errors']) {
    $line = "farm-launch cleanup: $problem"
    [System.Console]::Error.WriteLine($line)
    try {
        Add-Content -LiteralPath $logPath -Value $line -Encoding utf8
    }
    catch {
        [System.Console]::Error.WriteLine("farm-launch could not log the cleanup problem: $($_.Exception.Message)")
    }
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
$doneRecord['launch_overhead_s'] = $launchOverhead
$doneRecord['environment_reused'] = $environmentReused
$doneRecord['outputs'] = $cleanup['outputs']
$doneRecord['outputs_preserved'] = $cleanup['outputs_preserved']
$doneRecord['snapshot_removed'] = $cleanup['snapshot_removed']
$doneRecord['cleanup_errors'] = @($cleanup['cleanup_errors'])

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
