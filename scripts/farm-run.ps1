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
    [string]$Tag = 'run',

    # Parent of the disposable build worktrees. Defaults to `fw` beside the
    # repository's main checkout (C:\src\fw for C:\src\harmonic-analyzer): git
    # and SolidWorks paths under it must stay short on Windows.
    [string]$WorkRoot
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

function Invoke-Git {
    param(
        [Parameter(Mandatory)][string]$Directory,
        [Parameter(Mandatory)][string[]]$Arguments
    )

    $output = @(& git -C $Directory @Arguments 2>&1 | ForEach-Object { [string]$_ })
    $code = $LASTEXITCODE
    if ($code -ne 0) {
        throw "git $($Arguments -join ' ') failed with exit $code`: $($output -join [System.Environment]::NewLine)"
    }
    return $output
}

function Write-LaunchLine {
    param(
        [Parameter(Mandatory)][string]$Path,
        [Parameter(Mandatory)][string]$Text
    )

    Add-Content -LiteralPath $Path -Value $Text -Encoding utf8
    [System.Console]::Out.WriteLine($Text)
}

function Get-ExcludedSubmodules {
    param([Parameter(Mandatory)][string]$Checkout)

    # Mirrors build.py `_excluded_submodules`: the commit's declaration, paths
    # normalized so `references/` and `./references` mean the same thing.
    $source = Join-Path $Checkout '.farm-sources.json'
    if (-not (Test-Path -LiteralPath $source -PathType Leaf)) {
        return @()
    }
    $declared = Get-Content -LiteralPath $source -Raw -Encoding utf8 | ConvertFrom-Json -AsHashtable
    if ($declared -isnot [System.Collections.IDictionary]) {
        throw '.farm-sources.json must be a JSON object'
    }
    $paths = @($declared['exclude_submodules'] | Where-Object { $null -ne $_ })
    $normalized = foreach ($path in $paths) {
        if ($path -isnot [string]) {
            throw '.farm-sources.json: exclude_submodules must be a list of strings'
        }
        $clean = $path.Replace('\', '/')
        while ($clean.StartsWith('./', [System.StringComparison]::Ordinal)) {
            $clean = $clean.Substring(2)
        }
        $clean.TrimEnd('/')
    }
    return @($normalized)
}

function Initialize-BuildSubmodules {
    param(
        [Parameter(Mandatory)][string]$Checkout,
        [Parameter(Mandatory)][string]$Caller,
        [Parameter(Mandatory)][string]$LogPath
    )

    if (-not (Test-Path -LiteralPath (Join-Path $Checkout '.gitmodules') -PathType Leaf)) {
        return
    }
    $excluded = Get-ExcludedSubmodules -Checkout $Checkout
    $declarations = Invoke-Git -Directory $Checkout -Arguments @(
        'config', '--file', '.gitmodules', '--get-regexp', '^submodule\..*\.path$'
    )
    foreach ($declaration in $declarations) {
        $path = ($declaration -split ' ', 2)[1].Trim()
        if ($excluded -contains $path) {
            Write-LaunchLine -Path $LogPath -Text "farm-launch submodule $path excluded by .farm-sources.json"
            continue
        }
        # Borrow objects from the caller's clone when it has one; the checkout
        # itself is still the gitlink this commit pins.
        $arguments = @('submodule', 'update', '--init', '--recursive')
        $callerSubmodule = Join-Path $Caller $path
        if (Test-Path -LiteralPath (Join-Path $callerSubmodule '.git')) {
            $reference = (Invoke-Git -Directory $callerSubmodule -Arguments @(
                'rev-parse', '--absolute-git-dir'
            ) | Select-Object -Last 1).Trim()
            $arguments += @('--reference', $reference)
        }
        $arguments += @('--', $path)
        Invoke-Git -Directory $Checkout -Arguments $arguments | ForEach-Object {
            Write-LaunchLine -Path $LogPath -Text $_
        }
    }
}

function Get-BuildOutputFiles {
    param([Parameter(Mandatory)][string]$Source)

    # Top-level dot entries (.doit.db, .drawing-registry) are the build
    # worktree's own doit state, keyed to its paths: never outputs.
    if (-not (Test-Path -LiteralPath $Source -PathType Container)) {
        return @()
    }
    $files = foreach ($entry in Get-ChildItem -LiteralPath $Source -Force) {
        if ($entry.Name.StartsWith('.', [System.StringComparison]::Ordinal)) {
            continue
        }
        if ($entry.PSIsContainer) {
            Get-ChildItem -LiteralPath $entry.FullName -Recurse -File -Force
            continue
        }
        $entry
    }
    return @($files)
}

function Copy-BuildOutputs {
    param(
        [Parameter(Mandatory)][string]$Source,
        [Parameter(Mandatory)][string]$Destination,
        [Parameter(Mandatory)][AllowEmptyCollection()][System.IO.FileInfo[]]$Files
    )

    $copied = 0
    foreach ($file in $Files) {
        $relative = [System.IO.Path]::GetRelativePath($Source, $file.FullName)
        $target = Join-Path $Destination $relative
        [System.IO.Directory]::CreateDirectory((Split-Path -Path $target -Parent)) | Out-Null
        if ($file.Extension -ne '.jsonl') {
            Copy-Item -LiteralPath $file.FullName -Destination $target -Force
            $copied++
            continue
        }
        # Append-only journals (telemetry, cache.jsonl) extend the caller's history.
        $reader = [System.IO.File]::OpenRead($file.FullName)
        try {
            $writer = [System.IO.File]::Open(
                $target,
                [System.IO.FileMode]::Append,
                [System.IO.FileAccess]::Write,
                [System.IO.FileShare]::Read
            )
            try {
                $reader.CopyTo($writer)
            }
            finally {
                $writer.Dispose()
            }
        }
        finally {
            $reader.Dispose()
        }
        $copied++
    }
    return $copied
}

function Remove-CallerTaskRecords {
    param(
        [Parameter(Mandatory)][string]$BuildDatabase,
        [Parameter(Mandatory)][string]$CallerDatabase,
        [Parameter(Mandatory)][ValidateSet('Recorded', 'All')][string]$Scope
    )

    # The copied artefacts now disagree with whatever the caller's .doit.db
    # recorded for the same tasks. Dropping those records makes the caller's
    # next local doit re-derive each key from its own inputs instead of
    # trusting an artefact it did not produce. doit drops a failed task's
    # record, so after a failed build the build database cannot name every
    # task whose outputs were copied: Scope All forgets every caller record.
    if (-not (Test-Path -LiteralPath $CallerDatabase -PathType Leaf)) {
        return @()
    }
    $caller = [System.Text.Json.Nodes.JsonNode]::Parse(
        [System.IO.File]::ReadAllText($CallerDatabase)
    ).AsObject()
    [string[]]$tasks = @($caller | ForEach-Object { $_.Key })
    if ($Scope -eq 'Recorded') {
        if (-not (Test-Path -LiteralPath $BuildDatabase -PathType Leaf)) {
            return @()
        }
        $build = [System.Text.Json.Nodes.JsonNode]::Parse(
            [System.IO.File]::ReadAllText($BuildDatabase)
        ).AsObject()
        $tasks = @($build | ForEach-Object { $_.Key })
    }
    $removed = [System.Collections.Generic.List[string]]::new()
    foreach ($task in $tasks) {
        if ($caller.Remove($task)) {
            $removed.Add($task)
        }
    }
    if ($removed.Count -eq 0) {
        return @()
    }
    $directory = Split-Path -Path $CallerDatabase -Parent
    $temporary = Join-Path $directory ".doit.db.$([guid]::NewGuid().ToString('N')).tmp"
    try {
        [System.IO.File]::WriteAllText(
            $temporary,
            $caller.ToJsonString(),
            [System.Text.UTF8Encoding]::new($false)
        )
        [System.IO.File]::Move($temporary, $CallerDatabase, $true)
    }
    finally {
        if (Test-Path -LiteralPath $temporary) {
            Remove-Item -LiteralPath $temporary -Force
        }
    }
    return @($removed)
}

function Enter-CallerOutputLock {
    param(
        [Parameter(Mandatory)][string]$CallerOutput,
        [Parameter(Mandatory)][string]$LogPath,
        [Parameter(Mandatory)][int]$TimeoutSeconds
    )

    # Serializes harvests into one caller: two launches finishing together
    # would otherwise race the copy and the read-modify-write of .doit.db,
    # and the later writer could restore records the earlier one dropped.
    # The OS releases the handle if this process dies, so a stale lock file
    # never blocks; the file itself is left in place on purpose.
    [System.IO.Directory]::CreateDirectory($CallerOutput) | Out-Null
    $lockPath = Join-Path $CallerOutput '.farm-harvest.lock'
    $deadline = [System.Diagnostics.Stopwatch]::StartNew()
    $announced = $false
    while ($true) {
        try {
            return [System.IO.File]::Open(
                $lockPath,
                [System.IO.FileMode]::OpenOrCreate,
                [System.IO.FileAccess]::ReadWrite,
                [System.IO.FileShare]::None
            )
        }
        catch [System.IO.IOException] {
            if ($deadline.Elapsed.TotalSeconds -ge $TimeoutSeconds) {
                throw "timed out after $TimeoutSeconds s waiting for $lockPath"
            }
            if (-not $announced) {
                Write-LaunchLine -Path $LogPath -Text "farm-launch waiting for $lockPath (another harvest into this caller)"
                $announced = $true
            }
            Start-Sleep -Milliseconds 200
        }
    }
}

function Remove-BuildWorktree {
    param(
        [Parameter(Mandatory)][string]$Caller,
        [Parameter(Mandatory)][string]$Path
    )

    & git -C $Caller worktree remove --force --force $Path 2>&1 | Out-Null
    try {
        if (Test-Path -LiteralPath $Path) {
            Remove-Item -LiteralPath $Path -Recurse -Force
        }
    }
    catch {
        [System.Console]::Error.WriteLine(
            "farm-launch could not remove build worktree $Path`: $($_.Exception.Message)"
        )
    }
    & git -C $Caller worktree prune 2>&1 | Out-Null
    return -not (Test-Path -LiteralPath $Path)
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
            if ($target -ceq 'release' -or $target -ceq 'gallery') {
                throw (
                    "Targets cannot include $target`: it runs on the submitter, reads the " +
                    'excluded references submodule, and release bumps a tracked file the ' +
                    'disposable build worktree would discard; run it from an attended terminal'
                )
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

    if ([string]::IsNullOrEmpty($WorkRoot)) {
        $commonDirectory = (Invoke-Git -Directory $resolvedWorktree -Arguments @(
            'rev-parse', '--path-format=absolute', '--git-common-dir'
        ) | Select-Object -Last 1).Trim()
        $mainCheckout = Split-Path -Path $commonDirectory -Parent
        $WorkRoot = Join-Path (Split-Path -Path $mainCheckout -Parent) 'fw'
    }
    $resolvedWorkRoot = Resolve-FutureDirectory -Path $WorkRoot -ParameterName 'WorkRoot'
    if (Test-PathWithin -Candidate $resolvedWorkRoot -Root $resolvedWorktree) {
        throw "WorkRoot must be outside the target worktree: $resolvedWorkRoot"
    }
    [System.IO.Directory]::CreateDirectory($resolvedWorkRoot) | Out-Null
    $resolvedWorkRoot = Resolve-PhysicalDirectory -Path $resolvedWorkRoot
    if (Test-PathWithin -Candidate $resolvedWorkRoot -Root $resolvedWorktree) {
        throw "WorkRoot must be outside the target worktree: $resolvedWorkRoot"
    }

    # The build never sees these edits; they are recorded so nobody mistakes
    # the run for a build of them.
    [string[]]$callerDirty = @(
        Invoke-Git -Directory $resolvedWorktree -Arguments @(
            'status', '--porcelain=v1', '--untracked-files=all'
        ) | Where-Object { $_.Length -gt 3 } | ForEach-Object { $_.Substring(3) }
    )

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
        $buildWorktree = Join-Path $resolvedWorkRoot $runGuid.Substring(0, 8)
        $hasConflict = (
            (Test-Path -LiteralPath $recordPath) -or
            (Test-Path -LiteralPath $logPath) -or
            (Test-Path -LiteralPath $donePath) -or
            (Test-Path -LiteralPath $buildWorktree)
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
        build_worktree = $buildWorktree
        caller_dirty = @($callerDirty)
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

function Write-WrapperDiagnostic {
    param([Parameter(Mandatory)][string]$Diagnostic)

    try {
        Add-Content -LiteralPath $logPath -Value $Diagnostic -Encoding utf8
    }
    catch {
        [System.Console]::Error.WriteLine(
            "$Diagnostic; additionally failed to append the diagnostic to $logPath`: $($_.Exception.Message)"
        )
    }
    [System.Console]::Error.WriteLine($Diagnostic)
}

$exitCode = 1
$buildRequested = $false
$phaseSeconds = [ordered]@{}
$phaseTimer = [System.Diagnostics.Stopwatch]::StartNew()
try {
    Write-Output "farm-launch started $runId $([System.IO.Path]::GetFullPath($recordPath))"
    if ($callerDirty.Count -gt 0) {
        Write-LaunchLine -Path $logPath -Text (
            "farm-launch WARNING: $($resolvedWorktree) has $($callerDirty.Count) uncommitted " +
            "path(s) that this run does NOT build; it builds commit $commit only: " +
            ($callerDirty -join ', ')
        )
    }

    # The submitter runs in a disposable worktree at the pinned commit with an
    # empty cad/out: no caller edit, .doit.db record or local artefact can
    # reach a cache key, and nothing done to the caller during the run can.
    $buildRequested = $true
    Invoke-Git -Directory $resolvedWorktree -Arguments @(
        'worktree', 'add', '--quiet', '--detach', $buildWorktree, $commit
    ) | ForEach-Object { Write-LaunchLine -Path $logPath -Text $_ }
    $buildHead = (Invoke-Git -Directory $buildWorktree -Arguments @(
        'rev-parse', '--verify', 'HEAD'
    ) | Select-Object -Last 1).Trim()
    if ($buildHead -ne $commit) {
        throw "build worktree HEAD $buildHead is not the pinned commit $commit"
    }
    Initialize-BuildSubmodules -Checkout $buildWorktree -Caller $resolvedWorktree -LogPath $logPath
    Write-LaunchLine -Path $logPath -Text "farm-launch building $commit in $buildWorktree"
    $phaseSeconds['prepare'] = [System.Math]::Round($phaseTimer.Elapsed.TotalSeconds, 3)
    $phaseTimer.Restart()

    $env:SOLIDWORKS_POOL_HOME = $resolvedPoolHome
    $env:HARMONIC_REMOTE_CACHE_MODE = 'rw'
    $env:PYTHONUNBUFFERED = '1'
    # uv must sync the build worktree's own .venv: the editable
    # SolidworksMCP-python source resolves against the checkout that syncs it.
    Remove-Item -Path Env:VIRTUAL_ENV, Env:UV_PROJECT_ENVIRONMENT -ErrorAction SilentlyContinue
    Push-Location -LiteralPath $buildWorktree
    # Tee-Object cannot append to a -LiteralPath, and the log already holds
    # the preparation lines.
    $logStream = [System.IO.File]::Open(
        $logPath,
        [System.IO.FileMode]::Append,
        [System.IO.FileAccess]::Write,
        [System.IO.FileShare]::ReadWrite
    )
    $logWriter = [System.IO.StreamWriter]::new($logStream, [System.Text.UTF8Encoding]::new($false))
    $logWriter.AutoFlush = $true
    try {
        & uv @buildArgs *>&1 | ForEach-Object {
            $line = [string]$_
            $logWriter.WriteLine($line)
            $line
        }
        $code = $LASTEXITCODE
    }
    finally {
        $logWriter.Dispose()
        Pop-Location
        $phaseSeconds['build'] = [System.Math]::Round($phaseTimer.Elapsed.TotalSeconds, 3)
        $phaseTimer.Restart()
    }
    if ($null -eq $code) {
        throw 'uv did not report a native exit code'
    }
    $exitCode = [int]$code
}
catch {
    $exitCode = 1
    Write-WrapperDiagnostic -Diagnostic "farm-launch wrapper failed: $($_.Exception.Message)"
}

$harvest = [ordered]@{
    outputs_copied_to = $null
    outputs_copied = 0
    caller_tasks_forgotten = @()
    build_worktree_changes = @()
    build_worktree_removed = $false
}
$harvestFailed = $false
if ($buildRequested -and (Test-Path -LiteralPath $buildWorktree -PathType Container)) {
    try {
        # A tracked or untracked change inside the build worktree means some
        # task wrote outside cad/out; it is recorded, never carried back.
        $harvest['build_worktree_changes'] = @(
            Invoke-Git -Directory $buildWorktree -Arguments @(
                'status', '--porcelain=v1', '--untracked-files=all'
            ) | Where-Object { $_.Length -gt 3 } | ForEach-Object { $_.Substring(3) }
        )
        if ($harvest['build_worktree_changes'].Count -gt 0) {
            Write-LaunchLine -Path $logPath -Text (
                'farm-launch WARNING: the build changed files outside cad/out, which are ' +
                'discarded with the build worktree: ' + ($harvest['build_worktree_changes'] -join ', ')
            )
        }
        $buildOut = Join-Path $buildWorktree 'cad/out'
        $callerOut = Join-Path $resolvedWorktree 'cad/out'
        $harvest['outputs_copied_to'] = $callerOut
        $harvestLock = Enter-CallerOutputLock `
            -CallerOutput $callerOut -LogPath $logPath -TimeoutSeconds 600
        try {
            # Records go BEFORE any file is overwritten: a harvest that dies
            # halfway then leaves the caller missing records (a re-probe),
            # never a stale record beside a replaced artefact.
            [System.IO.FileInfo[]]$outputFiles = @(Get-BuildOutputFiles -Source $buildOut)
            $harvest['caller_tasks_forgotten'] = @(
                Remove-CallerTaskRecords `
                    -BuildDatabase (Join-Path $buildOut '.doit.db') `
                    -CallerDatabase (Join-Path $callerOut '.doit.db') `
                    -Scope $(
                        # Only a failed build with outputs to copy back can
                        # overwrite a caller artefact its db misnames.
                        if ($exitCode -ne 0 -and $outputFiles.Count -gt 0) { 'All' } else { 'Recorded' }
                    )
            )
            $harvest['outputs_copied'] = Copy-BuildOutputs `
                -Source $buildOut -Destination $callerOut -Files $outputFiles
        }
        finally {
            $harvestLock.Dispose()
        }
        Write-LaunchLine -Path $logPath -Text (
            "farm-launch copied $($harvest['outputs_copied']) output file(s) to $callerOut; " +
            "forgot $($harvest['caller_tasks_forgotten'].Count) caller doit record(s)"
        )
    }
    catch {
        $harvestFailed = $true
        if ($exitCode -eq 0) {
            $exitCode = 1
        }
        Write-WrapperDiagnostic -Diagnostic (
            "farm-launch failed to copy outputs back; keeping $buildWorktree for inspection: " +
            $_.Exception.Message
        )
    }
    $phaseSeconds['harvest'] = [System.Math]::Round($phaseTimer.Elapsed.TotalSeconds, 3)
    $phaseTimer.Restart()
}
if ($buildRequested -and -not $harvestFailed) {
    $harvest['build_worktree_removed'] = Remove-BuildWorktree -Caller $resolvedWorktree -Path $buildWorktree
    if (-not $harvest['build_worktree_removed']) {
        Write-WrapperDiagnostic -Diagnostic "farm-launch WARNING: build worktree $buildWorktree was not removed"
    }
    $phaseSeconds['cleanup'] = [System.Math]::Round($phaseTimer.Elapsed.TotalSeconds, 3)
}
$terminalState = if ($exitCode -eq 0) { 'succeeded' } else { 'failed' }

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
foreach ($entry in $harvest.GetEnumerator()) {
    $doneRecord[$entry.Key] = $entry.Value
}
$doneRecord['phase_s'] = $phaseSeconds

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
