#requires -Version 7.3

[CmdletBinding(DefaultParameterSetName = 'Launch')]
param(
    [Parameter(Mandatory, ParameterSetName = 'Launch')]
    [string]$Worktree,

    [Parameter(Mandatory, ParameterSetName = 'Launch')]
    [string]$PoolHome,

    [Parameter(Mandatory)]
    [string]$LogDirectory,

    [Parameter(Mandatory, ParameterSetName = 'Launch')]
    [string[]]$Targets,

    [Parameter(Mandatory, ParameterSetName = 'Launch')]
    [ValidateRange(1, 180)]
    [int]$LeafTimeout,

    # Launch: the label recorded with the run. Status/Watch/Cancel: select the
    # newest run carrying it. List: filter by it.
    [ValidatePattern('\A[A-Za-z0-9_-]+\z')]
    [string]$Tag = 'run',

    [Parameter(Mandatory, ParameterSetName = 'Status')]
    [switch]$Status,

    [Parameter(Mandatory, ParameterSetName = 'Watch')]
    [switch]$Watch,

    [Parameter(Mandatory, ParameterSetName = 'Cancel')]
    [switch]$Cancel,

    [Parameter(Mandatory, ParameterSetName = 'List')]
    [switch]$List,

    [Parameter(ParameterSetName = 'Status')]
    [Parameter(ParameterSetName = 'Watch')]
    [Parameter(ParameterSetName = 'Cancel')]
    [ValidatePattern('\A\d{8}T\d{9}Z-[0-9a-f]{32}\z')]
    [string]$RunId,

    [Parameter(ParameterSetName = 'Watch')]
    [ValidateRange(1, 3600)]
    [int]$PollSeconds = 15,

    [Parameter(Mandatory, ParameterSetName = 'Cancel')]
    [ValidateNotNullOrEmpty()]
    [string]$Why,

    [Parameter(ParameterSetName = 'List')]
    [ValidateSet('running', 'succeeded', 'failed', 'cancelled', 'launcher-died')]
    [string]$State,

    [Parameter(ParameterSetName = 'List')]
    [ValidateRange(1, 8760)]
    [int]$MaxAgeHours
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

function Get-UnfinishedRunOutputs {
    param([Parameter(Mandatory)]$Record)

    # A launcher stopped between moving cad/out and writing .done has already
    # put its outputs where a finished run's are.
    if (Test-Path -LiteralPath $Record['outputs'] -PathType Container) {
        return $Record['outputs']
    }
    return Join-Path $Record['snapshot'] 'cad\out'
}

# A workflow this run created starts within one start_workflow round trip of
# its request; the bound only has to exclude a later re-creation of the ID.
$script:CreationWindowSeconds = 30

function Get-RunLeafRequests {
    param([Parameter(Mandatory)]$Record)

    # _farm._dispatch logs "Farm workflow requested" with an absolute timestamp
    # just before start_workflow; the console log only has relative times.
    $requests = @{}
    $logs = Join-Path (Get-UnfinishedRunOutputs -Record $Record) 'reports\telemetry\logs.jsonl'
    if (-not (Test-Path -LiteralPath $logs -PathType Leaf)) {
        return $requests
    }
    foreach ($match in Select-String -LiteralPath $logs -SimpleMatch 'Farm workflow requested: ') {
        $entry = $match.Line | ConvertFrom-Json -AsHashtable
        $workflowId = $entry['attributes']['workflow_id']
        if (-not $requests.ContainsKey($workflowId)) {
            $requests[$workflowId] = [System.Collections.Generic.List[datetime]]::new()
        }
        $requests[$workflowId].Add((ConvertTo-UtcTimestamp -Value $entry['timestamp']))
    }
    return $requests
}

# --- Tracking a recorded run: -Status, -Watch, -Cancel, -List -----------------
#
# Everything below reads the same three records a launch writes under
# -LogDirectory (<run-id>.run.json, .log, .done). A run's state is derived, never
# stored twice: .done's state when it exists, else `running` while the recorded
# launcher process is alive, else `launcher-died` -- the launcher is gone and
# wrote no .done, so the local outcome is unknown and remote leaves may still
# be running.

$script:WatchExitCodes = @{
    'succeeded' = 0
    'failed' = 20
    'launcher-died' = 21
    'cancelled' = 22
}
$script:RunIdPattern = '\A\d{8}T\d{9}Z-[0-9a-f]{32}\z'

function ConvertTo-UtcTimestamp {
    param([Parameter(Mandatory)]$Value)

    # ConvertFrom-Json turns ISO-8601 strings into DateTime; 7.3 has no -DateKind.
    if ($Value -is [System.DateTime]) {
        return $Value.ToUniversalTime()
    }
    return [System.DateTime]::Parse(
        [string]$Value,
        [System.Globalization.CultureInfo]::InvariantCulture,
        [System.Globalization.DateTimeStyles]::AdjustToUniversal -bor
        [System.Globalization.DateTimeStyles]::AssumeUniversal
    )
}

function Read-RunRecord {
    param([Parameter(Mandatory)][string]$Path)

    # Records are renamed into place, and a reader can briefly hit a sharing
    # violation right after the rename; it clears on its own.
    $timer = [System.Diagnostics.Stopwatch]::StartNew()
    while ($true) {
        try {
            $record = [System.IO.File]::ReadAllText($Path) | ConvertFrom-Json -AsHashtable
            break
        }
        catch [System.IO.IOException], [System.UnauthorizedAccessException] {
            if ($timer.Elapsed.TotalSeconds -ge 30) {
                throw
            }
            Start-Sleep -Milliseconds 50
        }
    }
    foreach ($key in @($record.Keys)) {
        if ($record[$key] -is [System.DateTime]) {
            $record[$key] = $record[$key].ToUniversalTime().ToString(
                'o',
                [System.Globalization.CultureInfo]::InvariantCulture
            )
        }
    }
    return $record
}

function Get-RunRecordPaths {
    param([Parameter(Mandatory)][string]$Directory)

    return @(
        Get-ChildItem -LiteralPath $Directory -Filter '*.run.json' -File |
            Where-Object { $_.Name.Substring(0, $_.Name.Length - '.run.json'.Length) -match $script:RunIdPattern } |
            Sort-Object -Property Name |
            ForEach-Object { $_.FullName }
    )
}

function Select-RunRecordPath {
    param(
        [Parameter(Mandatory)][string]$Directory,
        [string]$RunId,
        [string]$Tag
    )

    if ($RunId) {
        $path = Join-Path $Directory "$RunId.run.json"
        if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
            throw "no run record $path"
        }
        return $path
    }
    # Run IDs start with a UTC timestamp, so name order is start order.
    $matching = @(
        Get-RunRecordPaths -Directory $Directory | Where-Object {
            (Read-RunRecord -Path $_)['tag'] -ceq $Tag
        }
    )
    if ($matching.Count -eq 0) {
        throw "no run tagged '$Tag' under $Directory"
    }
    return $matching[-1]
}

function Test-LauncherAlive {
    param([Parameter(Mandatory)]$Record)

    $process = Get-Process -Id ([int]$Record['pid']) -ErrorAction SilentlyContinue
    if ($null -eq $process) {
        return $false
    }
    # The launcher started before it wrote started_at; a process with this PID
    # that started later is an unrelated process that reused it.
    $startedAt = ConvertTo-UtcTimestamp -Value $Record['started_at']
    try {
        return $process.StartTime.ToUniversalTime() -le $startedAt.AddSeconds(1)
    }
    catch {
        return $true
    }
}

function Read-SharedText {
    param([Parameter(Mandatory)][string]$Path)

    # The launcher appends to its log through a shared handle while we read.
    $stream = [System.IO.FileStream]::new(
        $Path,
        [System.IO.FileMode]::Open,
        [System.IO.FileAccess]::Read,
        [System.IO.FileShare]::ReadWrite -bor [System.IO.FileShare]::Delete
    )
    try {
        $reader = [System.IO.StreamReader]::new($stream, [System.Text.UTF8Encoding]::new($false))
        return $reader.ReadToEnd()
    }
    finally {
        $stream.Dispose()
    }
}

function Get-WorkflowTask {
    param([Parameter(Mandatory)][string]$WorkflowId)

    # _farm.workflow_id: leaf:<task>:<cache key or commit prefix>:<budget>s
    $match = [System.Text.RegularExpressions.Regex]::Match($WorkflowId, '\Aleaf:(.+):[^:]+:\d+s\z')
    if ($match.Success) {
        return $match.Groups[1].Value
    }
    return $WorkflowId
}

function Read-RunLog {
    param([Parameter(Mandatory)][string]$Path)

    # The log lines that mark a leaf's life, as build.py/_farm/_artifact_cache
    # print them at --verbosity info:
    #   Farm workflow requested: <workflow-id>      (_farm._dispatch)
    #   Farm workflow attached: <workflow-id>       (_farm._dispatch)
    #   [cache] HIT   <task> (<key12>) -> ...       (restore: a submitter hit, or
    #                                                a farm leaf's result arriving)
    #   TaskError - taskid:<task>                   (doit, then a traceback whose
    #                                                last exception line says why)
    $parsed = [ordered]@{
        leaves = [ordered]@{}
        hits = 0
        task_errors = [System.Collections.Generic.List[string]]::new()
        events = [System.Collections.Generic.List[string]]::new()
        last_write_utc = $null
    }
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        return $parsed
    }
    $parsed['last_write_utc'] = (Get-Item -LiteralPath $Path).LastWriteTimeUtc
    $text = Read-SharedText -Path $Path
    # A line still being written is read on the next pass, whole.
    $complete = $text.LastIndexOf("`n")
    if ($complete -lt 0) {
        return $parsed
    }
    $awaitingCause = $null
    foreach ($raw in $text.Substring(0, $complete).Split("`n")) {
        $line = $raw.TrimEnd("`r")
        $workflow = [System.Text.RegularExpressions.Regex]::Match(
            $line, 'Farm workflow (requested|attached): (\S+)'
        )
        if ($workflow.Success) {
            $verb = $workflow.Groups[1].Value
            $workflowId = $workflow.Groups[2].Value
            $task = Get-WorkflowTask -WorkflowId $workflowId
            $parsed['leaves'][$task] = [ordered]@{
                task = $task
                state = $verb
                workflow_id = $workflowId
                error = $null
            }
            $parsed['events'].Add("leaf $task $verb $workflowId")
            continue
        }
        $hit = [System.Text.RegularExpressions.Regex]::Match($line, '\[cache\] HIT\s+(\S+) \(')
        if ($hit.Success) {
            $task = $hit.Groups[1].Value
            $leaf = $parsed['leaves'][$task]
            if ($null -ne $leaf -and $leaf['state'] -in @('requested', 'attached')) {
                $leaf['state'] = 'succeeded'
                $parsed['events'].Add("leaf $task succeeded $($leaf['workflow_id'])")
            }
            elseif ($null -eq $leaf) {
                $parsed['hits'] += 1
            }
            continue
        }
        $taskError = [System.Text.RegularExpressions.Regex]::Match($line, '\ATaskError - taskid:(\S+)')
        if ($taskError.Success) {
            $task = $taskError.Groups[1].Value
            $leaf = $parsed['leaves'][$task]
            if ($null -eq $leaf) {
                $leaf = [ordered]@{ task = $task; state = 'failed'; workflow_id = $null; error = $null }
                $parsed['leaves'][$task] = $leaf
            }
            $leaf['state'] = 'failed'
            $parsed['task_errors'].Add($task)
            $parsed['events'].Add("leaf $task failed $($leaf['workflow_id'])".TrimEnd())
            $awaitingCause = $leaf
            continue
        }
        if ($null -ne $awaitingCause -and $line -match '\A[A-Za-z_][\w.]*(Error|Exception|Exit)\b') {
            $cause = if ($line.Length -gt 500) { $line.Substring(0, 500) + '...' } else { $line }
            $awaitingCause['error'] = $cause
            $parsed['events'].Add("error $($awaitingCause['task']): $cause")
            $awaitingCause = $null
        }
    }
    return $parsed
}

function Get-RunStatus {
    param([Parameter(Mandatory)][string]$RecordPath)

    $record = Read-RunRecord -Path $RecordPath
    # Liveness first, then .done: the launcher writes .done before it exits, so
    # a launcher already gone with still no .done never wrote one.
    $alive = Test-LauncherAlive -Record $record
    $done = $null
    if (Test-Path -LiteralPath $record['done'] -PathType Leaf) {
        $done = Read-RunRecord -Path $record['done']
    }
    $state = if ($null -ne $done) { $done['state'] } elseif ($alive) { 'running' } else { 'launcher-died' }
    $log = Read-RunLog -Path $record['log']
    $leaves = @($log['leaves'].Values)
    $inFlight = @($leaves | Where-Object { $_['state'] -in @('requested', 'attached') })
    $now = [System.DateTime]::UtcNow
    $startedAt = ConvertTo-UtcTimestamp -Value $record['started_at']
    $orphans = @()
    if ($state -eq 'launcher-died') {
        $orphans = @(Get-RunProcesses -Record $record)
    }
    $status = [ordered]@{
        run_id = $record['run_id']
        tag = $record['tag']
        state = $state
        exit_code = if ($null -ne $done) { $done['exit_code'] } else { $null }
        launcher = [ordered]@{
            pid = $record['pid']
            alive = $alive
            # A dead launcher's build child may outlive it and keep dispatching.
            orphaned_processes = $orphans
        }
        commit = $record['commit']
        targets = @($record['targets'])
        leaf_timeout_minutes = $record['leaf_timeout_minutes']
        cache_environment = $record['cache_environment']
        started_at = $record['started_at']
        finished_at = if ($null -ne $done) { $done['finished_at'] } else { $null }
        elapsed_s = if ($null -ne $done) { $done['elapsed_s'] } else { [System.Math]::Round(($now - $startedAt).TotalSeconds, 1) }
        log_idle_s = if ($null -ne $log['last_write_utc']) { [System.Math]::Round(($now - $log['last_write_utc']).TotalSeconds, 1) } else { $null }
        worktree = $record['worktree']
        pool_home = $record['pool_home']
        record = [System.IO.Path]::GetFullPath($RecordPath)
        log = $record['log']
        done = $record['done']
        # .done's outputs is where they are; before it, the snapshot has them
        # until the launcher's cleanup moves them to the recorded path.
        outputs = if ($null -ne $done) { $done['outputs'] } else { Get-UnfinishedRunOutputs -Record $record }
        counts = [ordered]@{
            hits = $log['hits']
            requested = @($leaves | Where-Object { $null -ne $_['workflow_id'] }).Count
            succeeded = @($leaves | Where-Object { $_['state'] -eq 'succeeded' }).Count
            failed = @($leaves | Where-Object { $_['state'] -eq 'failed' }).Count
            in_flight = $inFlight.Count
        }
        leaves = $leaves
        in_flight_workflows = @($inFlight | ForEach-Object { $_['workflow_id'] })
        task_errors = @($log['task_errors'])
    }
    if ($null -ne $done -and $done.Contains('cancel')) {
        $status['cancel'] = $done['cancel']
    }
    return [pscustomobject]@{ status = $status; events = $log['events']; record = $record }
}

function Invoke-FarmCli {
    param(
        [Parameter(Mandatory)][string]$PoolHome,
        [Parameter(Mandatory)][string[]]$Arguments
    )

    # The pool is its own uv project; a caller's VIRTUAL_ENV must not leak in.
    $previous = $env:VIRTUAL_ENV
    $env:VIRTUAL_ENV = $null
    try {
        $output = @(& uv run --frozen --project $PoolHome (Join-Path $PoolHome 'farm.py') @Arguments 2>&1 |
                ForEach-Object { [string]$_ })
        return [pscustomobject]@{ code = $LASTEXITCODE; output = $output }
    }
    finally {
        $env:VIRTUAL_ENV = $previous
    }
}

function Get-RunProcesses {
    param([Parameter(Mandatory)]$Record)

    # The launcher (when it is still the recorded process) and everything it
    # started. A child keeps its ParentProcessId after its parent dies, so the
    # build a dead launcher left behind is still found; `started_at` and the
    # creation times keep an unrelated process that reused a PID out.
    $launcherId = [int]$Record['pid']
    $startedAt = ConvertTo-UtcTimestamp -Value $Record['started_at']
    $all = @(Get-CimInstance -ClassName Win32_Process -Property ProcessId, ParentProcessId, CreationDate, CommandLine)
    # With the launcher gone, its PID says nothing about who a process belongs
    # to: a direct child must also carry the recorded build command line.
    $buildCommand = @($Record['argv'] | Select-Object -Skip 1) -join ' '
    $byParent = @{}
    foreach ($process in $all) {
        $parent = [int]$process.ParentProcessId
        if (-not $byParent.ContainsKey($parent)) {
            $byParent[$parent] = [System.Collections.Generic.List[object]]::new()
        }
        $byParent[$parent].Add($process)
    }
    $holder = $all | Where-Object { [int]$_.ProcessId -eq $launcherId } | Select-Object -First 1
    $isLauncher = $null -ne $holder -and $holder.CreationDate.ToUniversalTime() -le $startedAt.AddSeconds(1)
    $found = [System.Collections.Generic.List[int]]::new()
    $queue = [System.Collections.Generic.Queue[object]]::new()
    if ($isLauncher) {
        $found.Add($launcherId)
    }
    foreach ($child in @($byParent[$launcherId])) {
        if ($null -eq $child -or [int]$child.ProcessId -eq $launcherId) {
            continue
        }
        $created = $child.CreationDate.ToUniversalTime()
        if ($created -lt $startedAt.AddSeconds(-1)) {
            continue
        }
        if ($null -ne $holder -and -not $isLauncher -and $created -ge $holder.CreationDate.ToUniversalTime()) {
            # A child of the process that reused the launcher's PID.
            continue
        }
        if (-not $isLauncher -and -not ([string]$child.CommandLine).Contains($buildCommand)) {
            continue
        }
        $queue.Enqueue($child)
    }
    while ($queue.Count -gt 0) {
        $current = $queue.Dequeue()
        $found.Add([int]$current.ProcessId)
        foreach ($child in @($byParent[[int]$current.ProcessId])) {
            if ($null -eq $child -or [int]$child.ProcessId -eq [int]$current.ProcessId) {
                continue
            }
            if ($child.CreationDate -lt $current.CreationDate) {
                continue
            }
            $queue.Enqueue($child)
        }
    }
    return @($found)
}

function Write-RunEvent {
    param(
        [Parameter(Mandatory)][string]$RunId,
        [Parameter(Mandatory)][string]$Text
    )

    $stamp = [System.DateTime]::UtcNow.ToString('HH:mm:ss', [System.Globalization.CultureInfo]::InvariantCulture)
    Write-Output "farm-run $stamp $RunId $Text"
}

function Invoke-RunStatus {
    param([Parameter(Mandatory)][string]$RecordPath)

    Write-Output ((Get-RunStatus -RecordPath $RecordPath).status | ConvertTo-Json -Depth 8 -Compress)
    $script:TrackExitCode = 0
}

function Invoke-RunWatch {
    param(
        [Parameter(Mandatory)][string]$RecordPath,
        [Parameter(Mandatory)][int]$PollSeconds
    )

    $emitted = 0
    $announced = $false
    while ($true) {
        $snapshot = Get-RunStatus -RecordPath $RecordPath
        $status = $snapshot.status
        if (-not $announced) {
            Write-RunEvent -RunId $status['run_id'] -Text (
                "watching tag=$($status['tag']) pid=$($status['launcher']['pid']) " +
                "state=$($status['state']) commit=$($status['commit']) targets=$($status['targets'] -join ',')"
            )
            $announced = $true
        }
        for ($index = $emitted; $index -lt $snapshot.events.Count; $index++) {
            Write-RunEvent -RunId $status['run_id'] -Text $snapshot.events[$index]
        }
        $emitted = $snapshot.events.Count
        if ($script:WatchExitCodes.ContainsKey($status['state'])) {
            $counts = $status['counts']
            $summary = (
                "end $($status['state']) exit_code=$($status['exit_code']) " +
                "hits=$($counts['hits']) farm=$($counts['requested']) succeeded=$($counts['succeeded']) " +
                "failed=$($counts['failed']) in_flight=$($counts['in_flight'])"
            )
            if ($status['state'] -eq 'launcher-died') {
                $summary += (
                    "; LAUNCHER DIED: pid $($status['launcher']['pid']) is gone and wrote no .done, " +
                    "log idle $($status['log_idle_s']) s; the remote leaves may still be running: " +
                    "farm-run.ps1 -Status for their workflow IDs, -Cancel to stop them"
                )
            }
            Write-RunEvent -RunId $status['run_id'] -Text $summary
            $status.Remove('leaves')
            Write-Output ($status | ConvertTo-Json -Depth 8 -Compress)
            $script:TrackExitCode = $script:WatchExitCodes[$status['state']]
            return
        }
        Start-Sleep -Seconds $PollSeconds
    }
}

function Invoke-RunList {
    param(
        [Parameter(Mandatory)][string]$Directory,
        [string]$Tag,
        [string]$State,
        [int]$MaxAgeHours
    )

    $now = [System.DateTime]::UtcNow
    $paths = @(Get-RunRecordPaths -Directory $Directory)
    [array]::Reverse($paths)
    foreach ($path in $paths) {
        $record = Read-RunRecord -Path $path
        if ($Tag -and $record['tag'] -cne $Tag) {
            continue
        }
        $startedAt = ConvertTo-UtcTimestamp -Value $record['started_at']
        if ($MaxAgeHours -and ($now - $startedAt).TotalHours -gt $MaxAgeHours) {
            continue
        }
        $alive = Test-LauncherAlive -Record $record
        $done = $null
        if (Test-Path -LiteralPath $record['done'] -PathType Leaf) {
            $done = Read-RunRecord -Path $record['done']
        }
        $runState = if ($null -ne $done) { $done['state'] } elseif ($alive) { 'running' } else { 'launcher-died' }
        if ($State -and $runState -ne $State) {
            continue
        }
        Write-Output ([ordered]@{
                run_id = $record['run_id']
                tag = $record['tag']
                state = $runState
                exit_code = if ($null -ne $done) { $done['exit_code'] } else { $null }
                started_at = $record['started_at']
                finished_at = if ($null -ne $done) { $done['finished_at'] } else { $null }
                commit = $record['commit']
                targets = @($record['targets'])
                pid = $record['pid']
                record = $path
            } | ConvertTo-Json -Depth 4 -Compress)
    }
    $script:TrackExitCode = 0
}

function Invoke-RunCancel {
    param(
        [Parameter(Mandatory)][string]$Directory,
        [Parameter(Mandatory)][string]$RecordPath,
        [Parameter(Mandatory)][string]$Why
    )

    $snapshot = Get-RunStatus -RecordPath $RecordPath
    $status = $snapshot.status
    $record = $snapshot.record
    $runId = $status['run_id']
    if ($status['state'] -notin @('running', 'launcher-died')) {
        Write-RunEvent -RunId $runId -Text "already finished: $($status['state']); nothing to cancel"
        $script:TrackExitCode = 0
        return
    }

    $errors = [System.Collections.Generic.List[string]]::new()
    $killed = [System.Collections.Generic.List[int]]::new()
    $launcherWas = $status['state']
    $runStartedAt = ConvertTo-UtcTimestamp -Value $record['started_at']
    # The launcher first, so it cannot react to its child dying by writing a
    # `failed` .done; then everything it started (uv, build.py) -- including a
    # build a dead launcher left running, which would keep dispatching leaves.
    $tree = @(Get-RunProcesses -Record $record)
    foreach ($processId in $tree) {
        try {
            Stop-Process -Id $processId -Force -ErrorAction Stop
            $killed.Add($processId)
        }
        catch [Microsoft.PowerShell.Commands.ProcessCommandException] {
            # Already exited between the listing and the stop.
        }
        catch {
            $errors.Add("could not stop process $processId`: $($_.Exception.Message)")
        }
    }
    if ($killed.Count -gt 0) {
        Wait-Process -Id $killed -Timeout 60 -ErrorAction SilentlyContinue
        Write-RunEvent -RunId $runId -Text "stopped launcher pid $($record['pid']) and its processes: $($killed -join ',')"
    }
    if (Test-Path -LiteralPath $record['done'] -PathType Leaf) {
        # The launcher finished on its own before it was stopped.
        $finished = Read-RunRecord -Path $record['done']
        Write-RunEvent -RunId $runId -Text "finished on its own first: $($finished['state']); nothing to cancel"
        $script:TrackExitCode = 0
        return
    }

    # Re-read: the log is final now that nothing writes it.
    $inFlight = @((Get-RunStatus -RecordPath $RecordPath).status['in_flight_workflows'])
    # Workflows are shared by ID (USE_EXISTING): a live sibling run that is
    # waiting on the same leaf keeps it.
    $shared = @{}
    foreach ($path in @(Get-RunRecordPaths -Directory $Directory)) {
        if ([System.IO.Path]::GetFullPath($path) -eq [System.IO.Path]::GetFullPath($RecordPath)) {
            continue
        }
        $other = Get-RunStatus -RecordPath $path
        # A dead sibling whose build outlived it is still waiting on its leaves.
        $waiting = $other.status['state'] -eq 'running' -or
            ($other.status['state'] -eq 'launcher-died' -and @($other.status['launcher']['orphaned_processes']).Count -gt 0)
        if (-not $waiting) {
            continue
        }
        foreach ($workflowId in $other.status['in_flight_workflows']) {
            $shared[$workflowId] = $other.status['run_id']
        }
    }
    # When this run asked the farm for each leaf, from its own telemetry.
    $requests = Get-RunLeafRequests -Record $record

    $outcomes = [System.Collections.Generic.List[object]]::new()
    $reason = "$Why (farm-run.ps1 -Cancel $runId)"
    foreach ($workflowId in $inFlight) {
        $outcome = [ordered]@{ workflow_id = $workflowId; outcome = $null; detail = $null }
        $outcomes.Add($outcome)
        if ($shared.ContainsKey($workflowId)) {
            $outcome['outcome'] = 'kept-shared'
            $outcome['detail'] = "run $($shared[$workflowId]) is still waiting on it"
            Write-RunEvent -RunId $runId -Text "kept $workflowId`: $($outcome['detail'])"
            continue
        }
        $query = Invoke-FarmCli -PoolHome $record['pool_home'] -Arguments @('status', '--json', $workflowId)
        if ($query.code -ne 0) {
            $text = $query.output -join ' '
            if ($text -match 'workflow not found') {
                # Requested, but the submitter died before the farm recorded it.
                $outcome['outcome'] = 'not-found'
            }
            else {
                $outcome['outcome'] = 'error'
                $errors.Add("farm.py status $workflowId exited $($query.code): $text")
            }
            $outcome['detail'] = $text
            Write-RunEvent -RunId $runId -Text "$($outcome['outcome']) $workflowId"
            continue
        }
        $described = ($query.output | Where-Object { $_.TrimStart().StartsWith('{') } | Select-Object -Last 1) |
            ConvertFrom-Json -AsHashtable
        if ($described['status'] -ne 'RUNNING') {
            $outcome['outcome'] = 'already-closed'
            $outcome['detail'] = $described['status']
            Write-RunEvent -RunId $runId -Text "already closed $workflowId`: $($described['status'])"
            continue
        }
        if ($null -eq $described['start_time']) {
            $outcome['outcome'] = 'error'
            $errors.Add("farm.py status $workflowId gave no start_time; cannot tell who started it")
            Write-RunEvent -RunId $runId -Text "error $workflowId"
            continue
        }
        $workflowStarted = ConvertTo-UtcTimestamp -Value $described['start_time']
        $requested = if ($requests.ContainsKey($workflowId)) { $requests[$workflowId] } else { @() }
        $createdHere = @($requested | Where-Object {
                # farm.py truncates start_time to the second; creation follows
                # the request by one start_workflow round trip.
                $workflowStarted -ge $_.AddTicks(-($_.Ticks % [System.TimeSpan]::TicksPerSecond)) -and
                $workflowStarted -le $_.AddSeconds($script:CreationWindowSeconds)
            }).Count -gt 0
        if (-not $createdHere) {
            # USE_EXISTING cannot say who created a workflow, so only one the
            # farm started right after this run's own request is this run's;
            # anything else was another submitter's, and this run attached.
            $outcome['outcome'] = 'kept-foreign'
            $outcome['detail'] = "started $($workflowStarted.ToString('o')), not within $($script:CreationWindowSeconds) s of a request by this run"
            Write-RunEvent -RunId $runId -Text "kept $workflowId`: $($outcome['detail'])"
            continue
        }
        $cancelled = Invoke-FarmCli -PoolHome $record['pool_home'] -Arguments @('cancel', '--why', $reason, $workflowId)
        $outcome['detail'] = $cancelled.output -join ' '
        if ($cancelled.code -eq 0) {
            $outcome['outcome'] = 'cancelled'
        }
        else {
            $outcome['outcome'] = 'error'
            $errors.Add("farm.py cancel $workflowId exited $($cancelled.code): $($outcome['detail'])")
        }
        Write-RunEvent -RunId $runId -Text "$($outcome['outcome']) $workflowId"
    }

    if ($errors.Count -gt 0) {
        # Some leaf is unaccounted for: leave the run `launcher-died`, with its
        # snapshot and no .done, so the same -Cancel can be retried.
        foreach ($outcome in $outcomes) {
            Write-Output ($outcome | ConvertTo-Json -Depth 4 -Compress)
        }
        foreach ($problem in $errors) {
            [System.Console]::Error.WriteLine("farm-run cancel: $problem")
        }
        [System.Console]::Error.WriteLine("farm-run cancel: not finished; no .done written; retry -Cancel")
        $script:TrackExitCode = 1
        return
    }

    # The launcher never ran its own cleanup: keep the outputs and remove the
    # snapshot exactly as it would have.
    $cleanup = Complete-Snapshot `
        -Worktree $record['worktree'] `
        -SnapshotPath $record['snapshot'] `
        -OutputsPath $record['outputs']
    foreach ($problem in $cleanup['cleanup_errors']) {
        $errors.Add($problem)
    }
    if ($null -eq $cleanup['outputs'] -and (Test-Path -LiteralPath $record['outputs'] -PathType Container)) {
        # The launcher was stopped between moving cad/out and writing .done:
        # its outputs are already where a finished run's are.
        $cleanup['outputs'] = $record['outputs']
        $cleanup['outputs_preserved'] = $true
    }

    $startedAt = $runStartedAt
    $now = [System.DateTime]::UtcNow
    $doneRecord = [ordered]@{}
    foreach ($entry in $record.GetEnumerator()) {
        $doneRecord[$entry.Key] = $entry.Value
    }
    $doneRecord['state'] = 'cancelled'
    $doneRecord['exit_code'] = $null
    $doneRecord['elapsed_s'] = [System.Math]::Round(($now - $startedAt).TotalSeconds, 3)
    $doneRecord['finished_at'] = $now.ToString('o', [System.Globalization.CultureInfo]::InvariantCulture)
    $doneRecord['launch_overhead_s'] = $null
    $doneRecord['environment_reused'] = $null
    $doneRecord['outputs'] = $cleanup['outputs']
    $doneRecord['outputs_preserved'] = $cleanup['outputs_preserved']
    $doneRecord['snapshot_removed'] = $cleanup['snapshot_removed']
    $doneRecord['cleanup_errors'] = @($cleanup['cleanup_errors'])
    $doneRecord['cancel'] = [ordered]@{
        why = $Why
        by = "$([System.Environment]::UserName)@$([System.Environment]::MachineName)"
        launcher = $launcherWas
        stopped_pids = @($killed)
        workflows = @($outcomes)
        errors = @($errors)
    }
    Write-JsonAtomic -Path $record['done'] -Value $doneRecord
    Write-Output ($doneRecord | ConvertTo-Json -Depth 8 -Compress)
    if ($errors.Count -gt 0) {
        foreach ($problem in $errors) {
            [System.Console]::Error.WriteLine("farm-run cancel: $problem")
        }
        $script:TrackExitCode = 1
        return
    }
    $script:TrackExitCode = 0
}

if ($PSCmdlet.ParameterSetName -ne 'Launch') {
    try {
        $trackedDirectory = Resolve-ExistingDirectory -Path $LogDirectory -ParameterName 'LogDirectory'
        $selectsRun = $PSCmdlet.ParameterSetName -in @('Status', 'Watch', 'Cancel')
        if ($selectsRun -and -not $RunId -and -not $PSBoundParameters.ContainsKey('Tag')) {
            throw "-$($PSCmdlet.ParameterSetName) needs -RunId or -Tag"
        }
        if ($selectsRun -and $RunId -and $PSBoundParameters.ContainsKey('Tag')) {
            throw "-$($PSCmdlet.ParameterSetName) takes -RunId or -Tag, not both"
        }
        $listTag = if ($PSBoundParameters.ContainsKey('Tag')) { $Tag } else { $null }
        # Each operation streams its lines to stdout and sets TrackExitCode.
        $script:TrackExitCode = 2
        switch ($PSCmdlet.ParameterSetName) {
            'List' {
                Invoke-RunList -Directory $trackedDirectory -Tag $listTag -State $State -MaxAgeHours $MaxAgeHours
            }
            default {
                $selected = Select-RunRecordPath -Directory $trackedDirectory -RunId $RunId -Tag $listTag
                switch ($PSCmdlet.ParameterSetName) {
                    'Status' { Invoke-RunStatus -RecordPath $selected }
                    'Watch' { Invoke-RunWatch -RecordPath $selected -PollSeconds $PollSeconds }
                    'Cancel' { Invoke-RunCancel -Directory $trackedDirectory -RecordPath $selected -Why $Why }
                }
            }
        }
    }
    catch {
        [System.Console]::Error.WriteLine("farm-run $($PSCmdlet.ParameterSetName.ToLowerInvariant()): $($_.Exception.Message)")
        exit 2
    }
    exit $script:TrackExitCode
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
