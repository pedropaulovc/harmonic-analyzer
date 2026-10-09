# Developing — local workflow notes

Practical, machine-local development notes that don't belong in `AGENTS.md`
(orientation) or the per-topic policy docs. Right now: supervised farm launches
and the remote build cache.

Running ONE SolidWorks operation by hand (this checkout has no local seat, so it
goes to the farm)? Read
[`cad/docs/one-off-com-operations.md`](cad/docs/one-off-com-operations.md) first
— it is the decision tree, the seat/cache invariants and the evidence trail for
an ad-hoc COM operation, and it links back here for cache detail.

## Supervised farm launches

A farm build outlives every agent turn and every harness deadline: a cold
`build` closure runs for hours, and one leaf alone has measured 61.5 min. So an
agent never runs `build.py --executor farm` under a Bash job, a 300 s tool
deadline or any other finite local timer. It starts the tracked launcher
[`scripts/farm-run.ps1`](scripts/farm-run.ps1) under a persistent `hub`
process and hands the recorded run to whoever comes next. An attended terminal
may still run `build.py` directly (its drift guard is below, under
[the build snapshot](#the-build-snapshot)); everything else here is the
contract for an agent-driven launch.

The launcher is a foreground runner, not a second scheduler: it validates its
inputs, writes a startup record, builds a private snapshot of the pushed HEAD,
runs exactly one `uv run … build.py` child from that snapshot, tees its output
to a log outside the worktree, keeps the snapshot's outputs, removes the
snapshot, and writes a terminal record carrying the child's own exit code. A
launch never retries, never cancels a remote workflow, never detaches and never
imposes a local deadline. The same script tracks what it launched, from the same
records under the same `-LogDirectory`: `-Status`, `-Watch`, `-List` and the one
explicit way to stop a run, `-Cancel` (see
[tracking a run](#tracking-a-run-status-watch-list-cancel)).

### Prerequisites

- **PowerShell 7.3 or newer** (`#requires -Version 7.3`). The launcher clears
  `$PSNativeCommandUseErrorActionPreference` for itself so a caller's preference
  cannot turn a native exit 23 into a PowerShell exception.
- **The worktree's HEAD is pushed.** Every leaf fetches that exact SHA from the
  approved repository, so the launcher refuses a HEAD that no locally known
  `origin/*` ref reaches: `HEAD is not known on origin; fetch and push before
  launching`. Fetch and push first; the launcher does neither for you.
- **A clean worktree.** The launcher builds the pushed HEAD only, so it refuses
  any uncommitted change, untracked file or moved submodule in `-Worktree`
  (`Worktree has uncommitted changes; …`, listing the paths) rather than
  silently leave it out of the build.
- **A protocol-compatible pool checkout** at `-PoolHome`, holding `farm.py`, and
  Azure credentials for the cache (`az login`; `off` is refused).
- **A log directory outside every Git worktree.** An explicit
  `HARMONIC_AGENT_SCRATCHPAD` uses
  `<root>\harmonic-analyzer\farm-runs`. For an OMP persistent process, when
  `OMPCODE=1` and its working-directory basename is `local`, the launcher uses
  `<working-directory>\harmonic-analyzer\farm-runs`. Otherwise it falls back to
  `%LOCALAPPDATA%\ha-farm\runs`. Pass `-LogDirectory` to override the default.
  In OMP, run `realpath local://` in the outer shell and set the persistent
  process working directory to that host path; the PowerShell process cannot
  resolve the OMP-only URI itself. The directory holds run records, logs,
  snapshots, shared environments and outputs. The launcher enables
  `core.longpaths=true` only for itself and its child processes, without
  changing the user's Git configuration.
  A snapshot inside some worktree would show up there as an untracked nested
  checkout, so a `-LogDirectory` inside any Git work tree is refused before
  anything is created. A new path under the drive root, such as
  `C:/farm-runs/knife-hanger`, is valid even if only `C:/` exists yet.

### Parameters

| parameter | required | meaning |
|---|:---:|---|
| `-Worktree` | yes | absolute path to the checkout whose pushed HEAD is built; the build runs from a private snapshot of that commit, never from here |
| `-PoolHome` | yes | absolute path to the `solidworks-pool` checkout; exported as `SOLIDWORKS_POOL_HOME` |
| `-LogDirectory` | no | optional absolute path for run files and outputs; defaults under the agent scratchpad and must resolve outside every Git worktree |
| `-Targets` | yes | doit task names as ONE comma-separated string (`part:pn_pen_rod,part:dt_cone_gear`) |
| `-LeafTimeout` | yes | per-attempt remote leaf budget in minutes, 1–180 |
| `-DisplayName` | yes, Launch only | short owner/session plus reason; nonblank, single-line, no control characters, at most 160 characters; tracking commands such as `-Watch` do not require it |
| `-Tag` | no | label recorded with the run (letters, digits, `_`, `-`); defaults to `run` |

An explicit `HARMONIC_AGENT_SCRATCHPAD` always wins. Otherwise, an OMP
persistent process automatically uses its resolved `local` working directory
when `OMPCODE=1`; a direct PowerShell launch falls back to
`%LOCALAPPDATA%\ha-farm\runs`. Pass the resulting absolute path when handing a
run to an agent on another host.

For example, use `-DisplayName 'InchPD - Add new drawing detail view to pd_transgear_stub v3'`.
The launcher records it as `display_name`, passes one `--display-name=<label>` argument,
and exports `HARMONIC_FARM_DISPLAY_NAME` to the build. An attended direct farm
build must supply `--display-name` (also accepted as `-DisplayName`) or that
environment variable; local builds and non-executing commands such as `--help`
and `list` do not need it. An explicit option overrides the inherited value.
Labels retain surrounding whitespace and must be valid Unicode encodable as
UTF-8; malformed surrogate text, Unicode control characters (`Cc`) and
line/paragraph separators (`Zl`, `Zp`) are rejected. Unicode `Bidi_Control`
characters are also refused so a label cannot spoof adjacent dashboard text.
Ordinary Arabic/Hebrew text and valid emoji, including joiners, are allowed.
The 160-character limit counts Unicode scalar values (code points), not
UTF-16 code units or grapheme clusters: each supplementary-plane emoji counts
once, while each combining mark and joiner counts separately.
Invalid labels are refused before contacting the farm, after doit has rejected
any invalid task selection.
For a direct label beginning with `-`, use `--display-name="-Owner - Reason"`
so it is not parsed as an option. Wrapper options are never abbreviated.
For the native `pwsh -File` launcher, attach a dash-leading label with a colon,
for example `-DisplayName:'-DisplayName'`; a separate value matching a known
PowerShell parameter name would otherwise be parsed as another parameter.
Launcher stdout JSON and its logs use UTF-8, including detached Windows launches.

Every new leaf execution has Temporal memo `display_name`, separate from the
optional launcher ownership memo `farm_run`. Neither label enters `LeafRequest`,
the workflow ID or the cache key. If another session requests an already-running
leaf, `USE_EXISTING` attaches to it without replacing either creator memo:
the queued/running display label continues to identify the creator, not the
latest attaching session.

Targets are *selections*, not variables, and they arrive as one string. `pwsh
-File` binds a single token per parameter, so a repeated `-Targets` or a
space-separated list is rejected before the script runs: pass
`"part:pn_pen_rod,part:dt_cone_gear"`. The launcher splits that string on commas,
trims each component, and rejects an empty set, an empty component, a token
starting with `-`, and a token containing `=`. That last rule matters: doit
removes a `name=value` argument as a command-line variable, so a mistyped
target would leave no selection at all and silently launch the full default
build. Task names use prefixed underscores (`part:pn_pen_rod`), never dashes — a dashed
name is rejected by `build.py` before the fleet is contacted.
Canonical stems and drawing Numbers are defined in the
[subsystem identity guide](cad/docs/subsystem-identities.md); its migration
table translates identifiers recorded in older runs.

The launcher sets `SOLIDWORKS_POOL_HOME`, `HARMONIC_REMOTE_CACHE_MODE=rw`,
`PYTHONUNBUFFERED=1` and `VIRTUAL_ENV=<shared environment>`, then runs, from the
snapshot:

```
uv run --frozen --no-sync --active python build.py --executor farm \
  --display-name "InchPD - Build pen rod" --leaf-timeout <minutes> \
  --verbosity info --continue <targets...>
```

The launcher passes no `-n`, so `build.py` inserts `-n 8`
(`HARMONIC_FARM_PARALLELISM`): more leaves in flight than the fleet has workers,
so no worker idles between leaves. A hard-coded `-n 4` against five workers kept
exactly four leaves running 88% of a cold build and one worker idle throughout
(2026-09-28, build `20260928T150817352Z`).
`--continue` collects later failures instead of stopping at the first; any failed
task still leaves the run nonzero.

### The build snapshot

A farm key is computed on the submitter from the local files, while every
worker builds the commit `_farm_preflight` recorded at launch. If the tree the
submitter reads changes mid-run — another agent commits or edits in the same
worktree — the two diverge: the worker publishes the key for the launch commit
and the submitter looks for a different one. That is issue #1114, where it
surfaced as `[cache_missing] exit 0`. The launcher therefore never runs
`build.py` in `-Worktree`:

1. `git worktree add --detach <LogDirectory>\snapshots\<12 hex> <commit>` —
   a private checkout of the launch commit, short-named to keep the deepest
   tracked path under `MAX_PATH`.
2. `git submodule update --init --recursive` for every gitlink in the commit
   except those its `.farm-sources.json` `exclude_submodules` lists (the same
   set the workers skip).
3. A shared environment at `<LogDirectory>\envs\<key>`, where `<key>` hashes
   the commit's `uv.lock`, `pyproject.toml`, `.python-version` and required
   gitlinks, reused by every launch with the same dependencies. The first
   launch for a key creates it in a staging directory of its own
   (`<key>.staging-<12 hex>`: `uv venv --relocatable`, then
   `uv sync --frozen --no-editable --active`), writes the
   `.farm-run-environment.json` marker, and only after uv has exited renames
   it to `<key>`. No launcher ever syncs into or deletes a directory another
   one may be using, even when a killed launcher's uv outlives it; two
   launchers racing on one key both sync, one rename wins, and the other
   discards its copy and adopts the winner's. `--no-editable` keeps the
   environment free of pointers into any snapshot, so snapshots come and go
   while it is in use, and `--relocatable` keeps its entry points valid
   across the rename.
4. The build runs from the snapshot with `VIRTUAL_ENV` set to that environment
   and `--no-sync --active`, so neither `uv` nor `build.py` touches `-Worktree`
   again. Commit, edit or check out anything there mid-run; this run cannot
   see it.

Measured on this workstation (2047 tracked files, one required submodule):
`worktree add` ≈ 1.9 s, submodule init ≈ 1.7–3.2 s, a first `uv sync` of a new
environment ≈ 7 s, a reused environment 0 s — so ≈ 12–13 s on a new dependency
set and ≈ 4–5 s otherwise, against leaves measured in minutes. Each launch
records its own figure as `launch_overhead_s`.

Every snapshot starts with an empty `cad/out`, so `.doit.db` is fresh and each
task first looks for its key in the remote cache; nothing from the caller's
`cad/out` is read or written. When the child exits, whatever the outcome, the
launcher moves the snapshot's `cad/out` (restored artefacts, `.doit.db`,
`reports/cache.jsonl`, `reports/telemetry`, logs) to
`<LogDirectory>\<run-id>.out` and runs `git worktree remove --force` on the
snapshot. `.done`'s `outputs` is where they actually are. If the move fails,
the snapshot holds the only copy, so it is kept, `outputs` points into it,
the reason is in `cleanup_errors`, and the run ends `failed` with a nonzero
exit even when the build itself exited 0 — its outputs are not where a
finished run's are. The shared environments stay; delete an `envs\<key>`
directory, or a `<key>.staging-*` left by a killed launcher, only when no
launcher is running.

A direct `build.py --executor farm` in an attended terminal has no snapshot. It
guards the same hazard instead. Before each leaf dispatch it runs
`git diff --raw --ignore-submodules=none <launch commit>` (plus a
`git rev-parse HEAD` only once something differs) and refuses the dispatch if
a change can move that leaf's key: any path under `cad/` (every recipe input
lives there, and a key folds its dependencies' recipes), `dodo.py`,
`build.py`, `pyproject.toml`, `uv.lock`, `.python-version`,
`.farm-sources.json`, `.gitmodules`, any `.gitattributes`, any submodule, or
one of the task's own recorded key inputs. The task stops with
`submitter checkout changed since launch: HEAD A -> B; changed: <files>; the
farm builds A, so keys would not match. Launch from an untouched worktree
(scripts/farm-run.ps1 does this).` A README or test edit dispatches normally;
untracked files and a new commit with an identical tree never count. When a
leaf then reports `cache_missing`, or succeeds without its key, every tracked
difference is reported the same way, since each is a lead; without any, the
failure names its other likely causes instead.

### Supervised farm releases

Never launch the `release` target through `farm-run.ps1`: it runs in a
disposable snapshot, and cleanup would discard the publisher's post-release
tracked image and `release.yaml` updates. Launch with
`-Targets "build,export,package:release,preflight"` (`build` supplies drawing
and check gates). Once successful, restore the complete `cad/out` from the
recorded `.done` `outputs` path (normally `<LogDirectory>\<run-id>.out`) into
the owning worktree. Then run `uv run --frozen python -m doit -s gallery`
followed by `uv run --frozen python -m doit -s release -- vNN` there. This keeps
the gallery and publish in the owning worktree without local COM redispatch.

### Starting one under the supervisor

Start it with `hub` `op: "start"`, never with Bash. `persist: true` is what lets
the run survive the launching agent's turn and a session handoff; `detached`
would lose live monitoring, so it is not used.

```jsonc
{
  "op": "start",
  "name": "farm-pen-rod-smoke",            // unique; record it in the brief
  "cwd": "<host path returned by realpath local://>",
  "application": "pwsh.exe",
  "args": [
    "-NoProfile", "-NonInteractive",
    "-File", "C:/src/harmonic-analyzer/scripts/farm-run.ps1",
    "-Worktree", "C:/src/harmonic-smoke",
    "-PoolHome", "C:/src/solidworks-pool",
    "-Targets", "part:pn_pen_rod",
    "-LeafTimeout", "90",
    "-DisplayName", "InchPD - Build pen rod",
    "-Tag", "smoke"
  ],
  "pty": false,
  "persist": true,
  "progress": "wake",
  "ready": { "log": "farm-launch started", "timeout": 120 }
}
```

The full closure is the same call with `"-Targets", "build"` and
`"-Tag", "full-build"`. Do not `hub stop` a live launcher to quiet the console —
retune it with `op: "monitor"`, `progress: "ambient"` or `"off"`. The watcher is
[`-Watch`](#tracking-a-run-status-watch-list-cancel), not the hub's console and
not a loop waiting for `.done`. To hand off, pass the run id from the readiness
line and the effective `-LogDirectory` (the default when omitted, or the
explicit override); a successor tracks the run with the same command, whether
or not the hub is still around.

### Tracking a run: status, watch, list, cancel

Every operation selects one run by `-RunId <run-id>` or `-Tag <tag>` (the newest
run with that tag). The default `-LogDirectory` is recomputed from the current
process environment and working directory. Omit it only when that computed
default resolves to the launch's effective `-LogDirectory`. Without a matching
`HARMONIC_AGENT_SCRATCHPAD` or an explicit `-LogDirectory`, an OMP launch
requires the tracking process to use the same resolved `local` `cwd`. If the
launch used an explicit override, or the computed defaults differ, pass the
launch's effective `-LogDirectory`: it is the parent directory of the
`.run.json` path printed on the `farm-launch started` readiness line. This also
applies to the `hub` process used for `-Watch`. If the computed default does
not match, tracking searches that other directory instead of the launch
directory. A selection that matches nothing, or both selectors at once, exits 2.

```powershell
$launcher = 'C:/src/harmonic-analyzer/scripts/farm-run.ps1'
$runRecordPath = '<absolute .run.json path from the farm-launch started line>'
$logDirectory = Split-Path -Path $runRecordPath -Parent
pwsh -NoProfile -File $launcher -LogDirectory $logDirectory -Status -RunId <run-id>
pwsh -NoProfile -File $launcher -LogDirectory $logDirectory -Watch  -Tag full-build
pwsh -NoProfile -File $launcher -LogDirectory $logDirectory -List   -State running -MaxAgeHours 24
pwsh -NoProfile -File $launcher -LogDirectory $logDirectory -Cancel -RunId <run-id> -Why 'superseded by <sha>'
```

The run's state is derived, never trusted from one file: `.done`'s `state` when
it exists (`succeeded`, `failed` or `cancelled`), otherwise `running` while the
recorded `pid` is alive (a PID reused by a process that started after the run is
not the launcher), otherwise **`launcher-died`** — the launcher is gone and wrote
no `.done`.

- **`-Status`** prints one JSON object: `state`, `exit_code`, `launcher`
  (`pid`, `alive`, and for a dead launcher the `orphaned_processes` it left —
  a build child outlives a killed launcher and keeps dispatching), `commit`,
  `targets`, `leaf_timeout_minutes`, `display_name`, `cache_environment`, `counts` (cache
  `hits`, farm leaves `requested`/`succeeded`/`failed`/`in_flight`), every farm
  leaf with its `workflow_id` and state, `in_flight_workflows`,
  `unsettled_workflows` (every leaf with a workflow id and no result: the
  in-flight ones plus those the build saw fail, since a local Temporal or
  protocol fault fails the task while its workflow may still run), `task_errors`,
  `log_idle_s` and `outputs` (the snapshot's `cad\out` while running,
  `.done`'s `outputs` after). Tools that only need a run's `cad/out` —
  `cache.jsonl`, `telemetry/traces.jsonl` — read `outputs` from here.
  Leaves come from the log plus `<run-id>.requests\`: the launcher sets
  `HARMONIC_FARM_REQUESTS` to that directory, and `_farm._dispatch` writes one
  `{task, workflow_id}` file there before it creates the workflow (a failed
  write fails the leaf before dispatch). The log is the launcher's copy of the
  build's output, so stopping the launcher mid-dispatch can drop a `Farm
  workflow requested` line; the file cannot be dropped that way.
- **`-Watch`** is the required watcher for an agent-launched build. It prints a
  line per leaf state change (`requested`, `attached`, `succeeded`, `failed`,
  each with its workflow id — follow one leaf with `farm.py watch <id>`) and per
  new `TaskError` with the exception that ended it, polling every
  `-PollSeconds` (15). It exits when the run is terminal, ending with the
  final `-Status` object: **0** succeeded, **20** failed, **21** launcher-died
  (`LAUNCHER DIED` on the summary line), **22** cancelled. Run it under the
  same kind of persistent supervisor as the launch, with `progress: "wake"`.
- **`-List`** prints one JSON line per run, newest first, filtered by `-Tag`,
  `-State` and `-MaxAgeHours`. Both `-Status` and `-List` report `display_name`
  as `null` for historical runs recorded before labels were required.
- **`-Cancel -Why <reason>`** stops the launcher and every process it started,
  including a build a dead launcher left behind. The launcher joins a named
  Windows job object (`job` in the run record) before it starts anything, so
  every descendant is a member whichever of its ancestors died: `uv run` does
  not take its python with it, and a build whose launcher and uv are both gone
  has no parent chain back to the run. The job's name lives while a process
  holds a handle to it; the launcher's handle is inheritable, so uv, the venv
  python and the build each hold one. A record from a launcher that predates
  run jobs falls back to the parent chain (a process under a dead
  launcher's PID counts only if its command line names the run: the recorded
  build command, the run's snapshot — git worktree add/remove, submodule
  update, uv sync — or its private uv staging environment).
  It rescans until a scan finds no process started since the last (at most
  10 rounds, else an error). Each process is stopped through a handle whose
  start time matches the scan's, so a PID reused after the scan is never
  killed, and a stopped process still running 60 s later is an error, since it
  may still be dispatching. It then cancels each of
  `unsettled_workflows` that `farm.py status` reports `RUNNING`,
  with the reason and run id on the cancellation. Workflows are shared by ID
  (`USE_EXISTING`), so two leaves are kept. One is a leaf a sibling run in the
  same `-LogDirectory` is still waiting on (`kept-shared`; a `launcher-died`
  sibling counts while its build outlives it). The other is a leaf another
  submitter created (`kept-foreign`). The launcher sets `HARMONIC_FARM_RUN`
  to its run id, and `_farm._dispatch` stamps it on the workflow's memo
  (`farm_run`). Temporal writes a memo only on the start that creates the
  execution, so an attach leaves the creator's in place, and `farm.py status
  --json` reports it. A leaf counts as this run's only when `farm_run` equals
  its run id. A leaf created without one (a direct `build.py --executor farm`)
  is kept, and so is every leaf when `farm.py` predates `farm_run`
  (pedropaulovc/solidworks-pool#165). Siblings are scanned right before each
  `farm.py cancel`, not up front, so a sibling that attaches while `-Cancel`
  queries the farm keeps its leaf, and one that finishes meanwhile no longer
  does. A sibling that attaches during
  the cancel call itself (one `farm.py` round trip) still loses it: its leaf
  fails as cancelled and a rerun rebuilds it. A submitter outside this
  `-LogDirectory` that attached *after* this run created a leaf is invisible,
  and that leaf is cancelled with the rest. Only farm-side reference counting
  would close both gaps.
  A leaf the farm reports absent is not settled on that answer: its request
  record is written before the start RPC, and a build killed mid-RPC can
  leave a start the farm commits a moment later. `-Cancel` asks again once
  `-SettleSeconds` (30) have passed since it stopped the run's processes, and
  handles a leaf that has appeared like any other; one still absent is
  `not-found`.
  If any leaf cannot be accounted for (`farm.py` failed on
  authentication, network or CLI), `-Cancel` exits 1 and changes nothing
  else: no `.done`, the snapshot kept, the run still `launcher-died`. Retry the
  same command. Otherwise it does the cleanup the launcher never ran —
  outputs moved to `<run-id>.out`, snapshot removed — and writes `.done` with
  `state: "cancelled"`, `exit_code: null` and a `cancel` block recording who,
  why, the stopped PIDs and each workflow's outcome (`cancelled`,
  `already-closed`, `not-found`, `kept-shared`, `kept-foreign`). A cleanup
  failure still writes `.done` (with `cleanup_errors`) and exits 1.
  On a run that already finished, `-Cancel` stops nothing and leaves `.done`
  as the launcher wrote it; it only cancels that run's leaves still
  `RUNNING` (a failed run's leaf may be) and prints each outcome, exiting 1
  if one could not be accounted for.

### The two records

Before the child starts, the launcher prints its readiness line and writes
`<run-id>.run.json`:

The timestamped record example below preserves its pre-migration target and
commit. Current selections use `part:pn_pen_rod`; consult the
[migration table](cad/docs/subsystem-identities.md#identity-migration-table)
when reading older run records.

```
farm-launch started 20260920T173011482Z-3f7b1c9a2d5e4081b6c3a9f0d4e27516 C:\src\dt-logs\farm-runs\20260920T173011482Z-3f7b1c9a2d5e4081b6c3a9f0d4e27516.run.json
```

```json
{
  "run_id": "20260920T173011482Z-3f7b1c9a2d5e4081b6c3a9f0d4e27516",
  "state": "running",
  "worktree": "C:\\src\\harmonic-smoke",
  "pool_home": "C:\\src\\solidworks-pool",
  "commit": "4101ff0fa54988a9f1464a9a0c5833b79a918975",
  "targets": ["part:pen_rod"],
  "leaf_timeout_minutes": 90,
  "display_name": "InchPD - Build pen rod",
  "started_at": "2026-09-20T17:30:11.4820000Z",
  "pid": 24680,
  "log": "C:\\src\\dt-logs\\farm-runs\\20260920T173011482Z-3f7b1c9a2d5e4081b6c3a9f0d4e27516.log",
  "done": "C:\\src\\dt-logs\\farm-runs\\20260920T173011482Z-3f7b1c9a2d5e4081b6c3a9f0d4e27516.done",
  "cache_environment": {
    "HARMONIC_CACHE_ACCOUNT": null,
    "HARMONIC_CACHE_CONTAINER": null,
    "HARMONIC_CACHE_SALT": null
  },
  "tag": "smoke",
  "argv": ["uv", "run", "--frozen", "--no-sync", "--active", "python", "build.py",
           "--executor", "farm", "--display-name=InchPD - Build pen rod",
           "--leaf-timeout", "90", "--verbosity", "info",
           "--continue", "part:pen_rod"],
  "snapshot": "C:\\src\\dt-logs\\farm-runs\\snapshots\\3f7b1c9a2d5e",
  "outputs": "C:\\src\\dt-logs\\farm-runs\\20260920T173011482Z-3f7b1c9a2d5e4081b6c3a9f0d4e27516.out",
  "environment": "C:\\src\\dt-logs\\farm-runs\\envs\\9c41d07a2be35f18",
  "requests": "C:\\src\\dt-logs\\farm-runs\\20260920T173011482Z-3f7b1c9a2d5e4081b6c3a9f0d4e27516.requests",
  "job": "Local\\harmonic-farm-run-20260920T173011482Z-3f7b1c9a2d5e4081b6c3a9f0d4e27516"
}
```

Validation failures happen *before* that record: they print a diagnostic and
exit nonzero without claiming a build started. Once the startup record exists,
every catchable outcome writes `<run-id>.done`, which repeats every field above
and adds the result (the launcher also echoes the finished record to stdout as
one compressed JSON line):

```json
{
  "run_id": "20260920T173011482Z-3f7b1c9a2d5e4081b6c3a9f0d4e27516",
  "state": "succeeded",
  "...": "the identity fields from the startup record, unchanged, except outputs",
  "exit_code": 0,
  "elapsed_s": 1487.216,
  "finished_at": "2026-09-20T17:54:58.6980000Z",
  "launch_overhead_s": 4.412,
  "environment_reused": true,
  "outputs": "C:\\src\\dt-logs\\farm-runs\\20260920T173011482Z-3f7b1c9a2d5e4081b6c3a9f0d4e27516.out",
  "outputs_preserved": true,
  "snapshot_removed": true,
  "cleanup_errors": []
}
```

`.done`'s `outputs` is where the run's `cad/out` actually is: the planned
`<run-id>.out`, the kept snapshot's `cad\out` when moving it failed (then
`outputs_preserved` is false and the run is `failed`), or `null` when the
build produced none. Only exit 0 with its outputs preserved is `succeeded`; a
wrapper exception is `failed` with exit 1 and its diagnostic in the log. A run
ID is
`yyyyMMddTHHmmssfffZ-<32 lowercase hex GUID characters>`, so it is
collision-resistant, and the launcher never overwrites an existing record, log,
marker, outputs or requests directory, or snapshot: the files for one run are
`<run-id>.run.json`, `<run-id>.log`, `<run-id>.done` and the `<run-id>.out`
and `<run-id>.requests` directories, with `-Tag` recorded inside them rather
than in their names.

`cache_environment` is in the record because `HARMONIC_CACHE_ACCOUNT`,
`HARMONIC_CACHE_CONTAINER` and `HARMONIC_CACHE_SALT` move cache keys and
workflow identity. An unchanged Git commit does not by itself mean an unchanged
key; compare these before reusing or resuming a run.

### Readiness is not proof of a build

`farm-launch started` means the wrapper initialized its log and startup record.
It is emitted before the child invocation, so it does not prove that `uv` started
or that the launcher is still running. Check the supervisor and terminal record
before handing off. Neither a green `check:math` (a local, SolidWorks-free gate)
nor a submitter cache hit proves dispatch. A launch is proven remote only by all
of: a `.done` with `state: "succeeded"` and `exit_code: 0`, an attached workflow
ID in the log, a completed `farm.run <task>` span naming a real worker, a
cache-miss followed by a restored artifact, and the artifact plus its
`.execution` token in `<run-id>.out`.

### Recovering a run across a handoff

`-Status` the recorded run id (or `-Watch` it, which ends in the same object):

1. **`running`.** The launcher is alive. Keep watching with `-Watch`. Do not
   start a second submitter for the same work.
2. **`succeeded`, `failed` or `cancelled`.** That is the outcome. `succeeded`
   with exit 0 is a finished run; `failed` is a finished failure to diagnose
   from `task_errors` and the log.
3. **`launcher-died`** (watch exit 21). The launcher is gone and wrote no
   `.done`, so the local outcome is *unknown*. It is not a cancellation, and it
   is not permission to relaunch. The remote work is very likely still running:
   `_farm.run_leaf` shares workflows by ID (`USE_EXISTING`), so killing the
   submitter never cancelled anything — and `launcher.orphaned_processes`
   lists a build child that may still be dispatching.

In case 3, either abandon the run with `-Cancel -Why …` (it stops the orphans,
cancels the leaves no live sibling needs, keeps the outputs and removes the
snapshot), or finish it. To finish it, query every workflow in
`unsettled_workflows` — every leaf with a workflow id and no result, not
one representative — from the pool checkout:

```powershell
uv run --frozen --project C:/src/solidworks-pool C:/src/solidworks-pool/farm.py status "<workflow-id>" --json
uv run --frozen --project C:/src/solidworks-pool C:/src/solidworks-pool/farm.py watch  "<workflow-id>"
```

Follow a RUNNING workflow under a supervised monitor until it is terminal, then
finish the bookkeeping from the *run record*, never from the caller's worktree:
the snapshot contract lets that worktree move on mid-run, so its HEAD says
nothing about what was launched. The recorded identity is `commit`, `targets`,
`leaf_timeout_minutes` and `cache_environment`. Launch `scripts/farm-run.ps1`
again with exactly those — `-Worktree` pointed at a clean checkout whose HEAD
is `commit` (the kept snapshot itself, or a fresh
`git worktree add --detach <path> <commit>`), `-Targets` and `-LeafTimeout`
from the record, and `HARMONIC_CACHE_ACCOUNT`/`CONTAINER`/`SALT` set (or unset)
to match `cache_environment`. Supply `-DisplayName` with the recovering session's
owner and reason; historical records may have no label. This metadata does not
change identity, and a rejoined workflow still retains its creator's label.
Same commit, cache environment and budget give
the same keys and workflow IDs, so every finished leaf restores from the cache
and a running one is rejoined rather than duplicated. The leaf budget is part
of the workflow ID, so changing it during recovery creates a different
workflow instead of rejoining the one already running. Never cancel a shared
workflow automatically.

A launcher that died before its `.done` never ran its cleanup, so its snapshot
is still registered and its outputs are still in `<snapshot>\cad\out` (the
status `outputs`). `-Cancel` does that cleanup. If you finished the run by
relaunching instead, copy what you need out of that `cad\out`, then remove the
snapshot from any checkout of the repository:
`git worktree remove --force <snapshot>` followed by `git worktree prune`. A
snapshot is only ever the recorded commit; removing it loses nothing else.

Relaunching the recorded invocation is allowed in exactly one case: an
authenticated `NOT_FOUND` for an ID that was *requested* but never *attached*.
That pair of log lines exists precisely for the window between server acceptance
and the submitter's acknowledgement. Everything else stays unresolved and blocks
an automatic relaunch: `NOT_FOUND` for an attached ID, a missing or unreadable
identifier, a checkout at any commit other than the recorded one or a different
cache environment, or a `status` call that failed on authentication, network or
CLI error. An auth or network failure is never a `NOT_FOUND`.

### Finite form-cut gear profiles

`cad/scripts/stock_form_cutter.py` owns the finite cutter geometry, independent
of configuration and native builders. Stock selection uses the lowest-count
master in the declared cutter range; below-base continuation is radial, with no
upper extrapolation. A virtual helical count selects the cutter, never the
physical tooth count. Every printed blank/tool-translation corner must retain
support, tip land and the actual root envelope.

Native and numerical consumers share the normalized core curves. Volume gates
use the bounded Green-area oracle; material membership retains the translated
root's partial sectors. `DT6-FORM1` is an explicitly named custom six-tooth tool,
not a stock-range alias. Non-conjugate pairs require the named stock-form contact
study, continuous carrying contact and signed transmission-error allocation;
neither an ideal-involute contact ratio nor a plausible native volume certifies
their mesh. Keep sizing and contact-study modules out of part dependency
closures. The qualified design record and native acceptance must refer to the
same frozen geometry and manufactured bands.

### Swing-cluster gravity calibration

After the farm finishes, the maintained, SolidWorks-free collector reads seven
native STLs (nine placed instances), never imports builders or COM, and never
writes into the source tree:

```powershell
uv run --frozen python cad/scripts/diagnostics/collect_dt_swing_gravity.py --outroot C:/src/dt-logs/farm-runs/20261008T164225457Z-6a2365ac09404a98b9cde46767f8d792.out --source-root C:/src/ha-gstd-inch-train --report C:/src/dt-logs/inch-train-swing-gravity.json
```

For subsequent calibrations, substitute the completed run and its matching source
tree. STL has no units or commit metadata: the collector checks the source
exporter's enforced **mm / preserved part-local origin** settings and reports
source/mesh SHA-256 hashes, but cannot prove those sources generated those bytes.
The example artifacts were built at `fb97437db18ac88669256295638cc87b802f9592`;
review any governing geometry/material differences before using a rebased source.

Method provenance is #859, original `03b51bce2` (main equivalent `964b1229f`):
the c486 STL-centroid basis with later analytic weight-volume updates. The
collector preserves that hybrid method: current native-STL centroids on the
assembly's actual transforms, analytic weight volumes for arbor, pivot shaft,
collar, handle and cam pins, mesh volumes for drum and brackets, brass 8500
kg/m³ nominal / 8800 corner, steel 7800, and gravity 9.80665 m/s². It welds only
vertices within **1e-5 mm** using SciPy KD-tree radius pairs and union-find;
watertightness and consistent winding remain separate strict predicates. It
does not grid-round, fill holes, remove faces or repair winding.

Install all five `recommended_calibration` entries together in
`cad/scripts/build_dt_drive_train_assembly.py`: both moment tuples, mass, basis
and `SWING_GRAVITY_FINGERPRINT`. Use the report's measured/analytic values, not
the mesh-only comparison. The frozen fingerprint includes dimensions, pressure
angle and actual tooth-floor diameter/depth; never replace it with live config
aliases. Update the nearby calibration provenance comment with the completed run
and the exact governing source.
Then run the **undeselected**
`test_dt_drive_train_support_layout.py::test_swing_gravity_basis_is_the_current_parts`
and `test_dt_swing_gravity_collector.py`, followed by `check:recipe` and the release
gates. After any governing geometry or material changes, preserve the previously
measured values and let the stale-basis guard refuse until the replacement report
has been collected from the changed native parts.


## Remote build-artifact cache

Every task that opens SolidWorks is cached: `part:<stem>`, `assembly:<stem>`,
`drawing:<stem>`, the gates (`verify_soundness:<stem>`, `verify:kinematics`,
`preflight`), the neutral `export` and the release Pack-and-Go
(`package:release`). They are the slow part of the pipeline — a part is ~20 s and
a full assembly ~500 s. Their outputs are a pure
function of their hashed inputs, so a shared cache lets one machine **download a
prebuilt `.SLDPRT`/`.SLDASM`/`.SLDDRW`/`.STL`/`.PDF`** for an unchanged input set
instead of
driving SolidWorks. A seat-less machine can pull; a builder pulls **and**
publishes. Implementation: `cad/scripts/_artifact_cache.py`.

A gate produces no CAD artefact, so **its stamp is its cached output**
(`cad/out/reports/verify-*.ok`, `preflight.ok`): identical inputs imply an
identical verdict, so restoring the stamp is restoring the proof. This is also
the mechanism behind `--executor farm`: a cache-missing COM task dispatches one
farm leaf and then restores what the worker published, which is how a machine
with no SolidWorks seat runs a whole release.

### TL;DR — it just works

Both dev seats are pre-authorized and the default role is `rw`, so **a clean
checkout needs zero setup**: it pulls what the other seat built and publishes
what it builds. You only touch anything to *opt out* or to bust the cache after a
SolidWorks upgrade.

### How keys work

Each task is keyed by a SHA-256 of its `file_dep` set, folded **exactly** like
doit's staleness check (`ContentChecker._digest`: raw bytes for binaries,
parsed-YAML for configs), so a cache hit and "doit up-to-date" always agree and a
comment-only YAML edit busts neither. Paths are tagged **repo-relative**, so the
key is identical across machines and worktrees.

Assembly and drawing keys also include SHA-256 identity tokens for the exact CAD
artifacts they reference. SolidWorks persistent-reference IDs and persisted
rebuild stamps may differ between two same-recipe builds, so a recipe key alone
is unsafe for an assembly or drawing. Restoring the same cached dependency
reproduces the same identity token and can restore its matched downstream output
with no COM work; another artifact misses and rebuilds/refreshes once. Assembly
tokens propagate the guarantee through subassembly levels to the top model.

Drawing recipes include the selected `_drawing_registry.py` row and the shared
registry implementation, recorded under `cad/out/.drawing-registry/`. Adding or
editing another row does not invalidate an independent drawing. Shared helper,
template, schema and source-model identity changes still invalidate it. Consumers
that read other rows or use an unclassified registry access retain the full
registry dependency.

Switching to these per-drawing dependencies changes existing drawing cache keys
once. It does not reuse legacy keys; subsequent unrelated row changes stay
isolated. A scoped drawing build need not regenerate the rest of the fleet.

The `file_dep` set for a COM task also folds the **`SolidworksMCP-python`
submodule** — the vendored COM adapter (`solidworks_mcp`) is imported at runtime
by `_common`/`_assembly` (mate/plane/feature creation), so its source is a genuine
build input, yet it is an installed package, not a repo-local `_*.py` helper, so
`module_deps_of` never walked it (issue #144). `dodo._submodule_dep()` folds a
content-hash of the submodule's `src/solidworks_mcp` tree (repo-relative-tagged,
so cross-machine-stable) in as **one synthetic dep** — a small gitignored
`cad/out/reports/.solidworks-mcp-submodule.digest` sidecar whose content is that
hash — added only in the COM dep builders (`_part_file_deps` / `_recipe_files`), so
a submodule bump (committed pin **or** a dirty local edit) busts every COM key and
forces a rebuild, while the SolidWorks-free `check:*` tasks stay off it. Guarded by
`check:recipe` (`test_dodo_recipe.py`). *Migration:* this shifts every COM cache
key once — the build self-heals over one run (a rebuild re-stamps the ledger and
republishes), or run `doit reset-dep`.

Private/experimental work is cached too, with no namespacing: a unique input set
yields a unique key, so an experiment is stored under its own key and never
collides with the canonical artefacts. Two seats share a blob only when their
inputs are byte-identical.

### Debugging a miss (provenance & diagnostics)

A key is `sha256(epoch + salt + Σ(relpath, digest))`, so an unexpected key shift
is almost always **one dep digest moving**. Four best-effort tools surface that
without reconstructing build history from terminal scrollback (none can fail a
build):

- **`doit cache_status`** — the one-command answer to *"why did this miss?"*. For
  every cacheable COM task (part, assembly, drawing, gate, `export`,
  `package:release`) it prints `HIT`/`MISS` (a backend presence probe — a
  HEAD,
  not a download) + the 12-char key, and for a miss the full `(digest, relpath)`
  list that produced the key. Compare two seats' output and the moved digest is the
  culprit. Args after `--`:
  - label substrings to filter — `doit cache_status -- cone_gear`
  - `miss` — only the misses
  - `all` — dump dep digests for **every** task, not just misses
  - a `DRIFT(last published …)` flag appears when a task's current key differs from
    the last key *this seat* published (see below).
- **`HARMONIC_CACHE_DEBUG=1`** — during a real `doit` build, logs each
  `(digest, relpath)` feeding every key and the resulting key, tagged by task. Turn
  it on for the build you're diagnosing rather than reasoning after the fact.
- **`cad/out/reports/cache.jsonl`** — an append-only event log (one JSON object per
  restore/store: `ts`, `event`, `label`, `key`, `epoch`, `salt`). Events:
  `store` / `store_skip` (ro seat) / `store_empty` / `store_error`,
  `restore_hit` / `restore_miss` / `restore_hit_drift` / `restore_error` /
  `restore_locked` (a HIT whose extract a share lock refused — the one restore
  failure that raises instead of "building locally", see AGENTS.md's seat
  contract). Post-hoc
  debugging reads this file instead of scrollback. Gitignored (under `cad/out/`).
  Every record also carries the recipe (`schema`, `recipe_known`, `input_count`,
  `inputs: [{path, digest}, ...]`) and remote manifest integrity metadata. Misses
  and drift retain `previous_key` / `previous_inputs` from the local sidecar when
  available; successful hits and stores now retain their own full inputs too.
- **App Insights cache manifests** — `cache.miss`, `cache.hit`, and successful
  `cache.store` span events keep the existing `label` and 12-character `key`,
  and add `key_full`, `epoch`, `salt`, and `manifest_*` fields. Each is followed
  by structured DEBUG logs with message `cache.provenance`, carrying the *same
  canonical recipe as cache.jsonl* in ordered ASCII JSON fragments
  (`chunk_index`, `chunk`). Logs correlate to the task trace/span and use the
  `build-infra` service; warning-level consoles suppress them. No dependency
  opens a span. The SHA-256 of the complete canonical payload is `manifest_id`.
  Recipe epoch/salt are captured when the key is computed, not from a later
  environment. An arbitrary key not computed with a label in this process is
  explicitly unknown (`recipe_known=false`, `manifest_input_count=-1`).

  The SDK exports through OTLP without a project-specific truncation override;
  span event retention defaults to 128 and configured SDK limits may be lower.
  Chunks are therefore logs, not span events: they cannot evict cache decisions
  or other task events. Azure customDimensions values allow 8192 characters, so
  each chunk is at most 6000 ASCII characters/bytes. There is **no input/chunk
  cap**: every known recipe is emitted in full. `manifest_transport=logs`,
  `manifest_chunk_count` is the required count, `manifest_emitted_chunks` is the
  planned count, `manifest_chars` is the full payload length, and
  `manifest_input_count` is the complete input count. `manifest_complete=true`
  is **not an ingestion guarantee**: exporters, sampling, retention, or an SDK
  attribute limit can still omit/truncate records.

  Retrieve the decision and fragments remotely, for example:

  ```kusto
  traces
  | where message in ("cache.miss", "cache.hit", "cache.store", "cache.provenance")
  | extend record_name=message
  | where tostring(customDimensions["label"]) == "part:vn_counter_spring"
  | project timestamp, operation_Id, record_name,
      label=tostring(customDimensions["label"]),
      key_full=tostring(customDimensions["key_full"]),
      manifest_id=tostring(customDimensions["manifest_id"]),
      schema=toint(customDimensions["manifest_schema"]),
      transport=tostring(customDimensions["manifest_transport"]),
      complete=tobool(customDimensions["manifest_complete"]),
      chunks=toint(customDimensions["manifest_chunk_count"]),
      emitted=toint(customDimensions["manifest_emitted_chunks"]),
      chars=toint(customDimensions["manifest_chars"]),
      inputs=toint(customDimensions["manifest_input_count"]),
      chunk_index=toint(customDimensions["chunk_index"]),
      chunk=tostring(customDimensions["chunk"])
  | order by timestamp asc, manifest_id asc, chunk_index asc
  ```

  First require all mandatory decision metadata, with the expected types:
  full key, manifest identity/schema/transport, completeness, character count,
  required/planned chunk counts, and input count. Missing metadata means
  incomplete evidence, even if the remaining `complete` flag is true.
  Require each matching fragment to have a valid integer index and string chunk.
  Reassemble by manifest identity (and operation when inspecting one decision).
  Deduplicate identical fragments by zero-based index; reject conflicting
  duplicates. Require `complete=true`, planned count equal to required count,
  every index `0..chunks-1`, exact concatenated character count, SHA-256 equal to
  `manifest_id`, and decoded `recipe_known=true` with `len(inputs)` equal to both
  input counts. Reject incomplete evidence rather than treating an omitted dep
  as unchanged. Find the last earlier **successful `cache.hit` or `cache.store`**
  for the same label with a verified manifest, then compare full keys, epoch/salt,
  and path/digest lists against the miss. This works across disposable snapshots
  with no previous-key sidecar; older successful events without manifests cannot
  establish a complete baseline. All provenance emission is best-effort and
  cannot change cache outcomes.

**Vendor-part builds are actionable.** An actual `part:vn_*` build emits a
`!!` / OTel `WARN` immediately before its COM execution, with structured `label`
and `cache.key` (the 12-character prefix shared with phase spans and the console),
plus the full `key_full` for correlation with cache events and recipe manifests.
This happens on a local seat or the farm worker, not on the submitter's dispatch,
a cache probe, a miss that becomes a hit while waiting for the seat, or
`drawing:vn_*`. Vendor-part rebuilds should be rare: compare the recorded cache
inputs with the previous key, investigate the changed dependency, and refactor
unnecessary dependencies rather than treating every miss as expected. The warning
marks one build execution, including an execution that later fails; COM recovery
retries do not emit duplicate vendor-build warnings.

**Store-skip-on-hit drift.** `restore` returns early on a HIT and never re-stores,
so a seat can *serve* a key it never *published* (this is what bit the v0.9.0 cut:
key shifts across refactor waves meant the final key was never written for 22 of 73
parts, even though every one had a valid on-disk SLDPRT). To surface it, each
successful `store` stamps `cad/out/reports/cache-keys/<label>.key` with the key this
seat published; on a later HIT under a *different* key, `restore` logs a `WARN` and
a `restore_hit_drift` event — and `cache_status` shows the `DRIFT(...)` flag.

The `WARN` is for a seat that **publishes what it builds**, because only there does
a foreign key mean something went wrong. A submitter under `--executor farm` never
reaches `store` (the worker builds and publishes every cache-missing leaf), and a
`ro` seat declines to publish, so for those *every* hit is under a key they could
not have published: warning would fire on the correct path and teach you to ignore
the flag. They log it at debug instead and still append the `restore_hit_drift`
event with `"drift_expected": true` and a `"drift_reason"` of `executor=farm` or
`cache_mode=ro` — so `jq 'select(.event=="restore_hit_drift" and
.drift_expected==false)' cache.jsonl` is the post-hoc list of *real* drift.

### Backend: Azure Blob over HTTPS (443)

One content-addressed `<key>.tar.gz` blob per task in container `buildcache` on
storage account `stswbuildcache07aba2`. Reached over **443** — works from any
network, including ISPs that block SMB/445 (e.g. Comcast), with no VPN or mounted
drive. Auth is **keyless** via `DefaultAzureCredential`:

- **dev box** → your `az login` token. Run `az login` once.
- **builder (`vm-solidworks`)** → its system-assigned managed identity
  (granted *Storage Blob Data Contributor*); nothing to log in.

A machine without the data-plane RBAC role is **fail-soft**: its push is denied
and the build proceeds normally (a miss/error never fails a build).

### Roles and how to set them

Role is one of `off` | `ro` (pull only) | `rw` (pull + push). Resolved in order:

1. `HARMONIC_REMOTE_CACHE_MODE` env var, if set
2. `.harmonic-remote-cache-mode` — a **gitignored one-line file at the repo root**
   (`C:\src\harmonic-analyzer\.harmonic-remote-cache-mode`), contents just `off`/`ro`/`rw`
3. `_DEFAULT_MODE` = **`rw`** (the fallback)

`.harmonic-remote-cache-mode` is **per-clone** (not global) and never committed. To
downgrade a seat — e.g. a collaborator without Azure access — drop the file at the
repo root:

```powershell
Set-Content .harmonic-remote-cache-mode off    # disable (no pull, no push)
Set-Content .harmonic-remote-cache-mode ro     # pull only
```

Or, equivalently, without a file: `$env:HARMONIC_REMOTE_CACHE_MODE = 'off'`.

Check the resolved role:

```powershell
uv run python -c "import sys; sys.path.insert(0,'cad/scripts'); import _artifact_cache as c; print(c._mode())"
```

### Defaults you can override

Account, container, and salt are committed constants in `_artifact_cache.py`
(`_DEFAULT_ACCOUNT`, `_DEFAULT_CONTAINER`, `_DEFAULT_SALT`). Each is overridable by
its matching `HARMONIC_CACHE_*` env var (CI, tests, an unlanded salt bump). None
is a secret — the account is RBAC-gated with public blob access off.

### Busting the cache (salt / epoch)

The toolchain (SolidWorks major version, COM adapter) is **not** in any
`file_dep`, so a SW upgrade that changes geometry would otherwise serve a stale
hit. Mix-ins guard this:

- **`_DEFAULT_SALT`** (e.g. `sw2024-sp3`) — bump it in the **same commit** that
  adapts to a new SolidWorks version, so the cache busts in lockstep with the
  code. All seats must agree on the salt or they never share hits.
- **`_CACHE_EPOCH`** — bump to invalidate *every* entry pipeline-wide (e.g. a
  pack-format change).

### Retention — server-side, no job

Account **last-access-time tracking** + a lifecycle rule
`delete daysAfterLastAccessTimeGreaterThan: 7`. A restore is a blob *read*, which
bumps last-access, so an artefact in active use keeps itself alive (true LRU). No
scheduled cleanup task, no client-side touch.

### Provisioning (one-time, operator)

`scripts/azure/provision_build_cache.ps1` is idempotent and does everything:
creates the container, enables last-access tracking, sets the lifecycle policy,
and grants `Storage Blob Data Contributor` to the signed-in operator and the
`vm-solidworks` managed identity. Run it once with `az` logged into the Dev/Test
subscription.

### Caveats

- The `rw` default means *any* clone attempts a push. Safe (RBAC denies an
  unauthorized seat, fail-soft), but an unauthorized seat pays a credential-probe
  delay per build — set `.harmonic-remote-cache-mode off` there.
- Cross-machine hit rate depends on identical input **bytes**. Without a
  `.gitattributes` normalizing line endings, a `.py` re-materialized with
  different EOLs hashes differently → a miss (never a wrong artefact). Add
  `*.py text eol=lf` if hit rate disappoints.

## Native projected geometric-control zones

The canonical `_gtol_spec.GeometricControl.projected_zone_height_mm` is optional:
`None` preserves the ordinary XML payload and migrated ordinary frames are not
repopulated; an authored height must be finite and positive. Readback gating is
stricter for **all** feature-control frames: complete semantic signatures pay
projection enablement/height, tolerance-zone diameter and datum order; drawings
also check a freshly fetched frame after rebuild. Part and drawing helpers consume
the same spec through current `IGtolFrame.SetSymbolXml` / `GetSymbolXml`.
Direct drawing calls must source both tolerance and projected height from a
part-spec contract; `drawing-gdt-provenance` checks both keyword values.

The populated offline API reference (bundle v3.12.1) documents
[Gtol Frame XML Schema](https://help.solidworks.com/2026/english/api/sldworksapiprogguide/Overview/Gtol_Frame_XML_Schema.htm).
The installed R2026x `data/xmlschema/swGtolFrameXmlSchema-public-2.xsd` confirms
`FeatureInfo/ProjectedToleranceZone` (`xs:boolean`) followed by `Projection`
(`xs:decimal`), before datum compartments. The repository serializes the height
using the same mm numeric-text convention as `PrimaryToleranceValue`. No primary
source states the native unit of `Projection`; its actual physical interpretation
remains a farm proof requirement. No exponent-form decimal or free-text `P` suffix
is authored. `ProjectionRange` is not supported: nonzero readback refuses a
different ranged zone.

`IGtol.SetPTZHeight2` / `GetPTZHeight2` are explicitly pre-2022-only APIs and are
never a fallback on current frames. The existing old-format seed uses the void
`SetFrameSymbols2`, BOOL `SetFrameValues2`, and checked `ConvertFormat` status
before any projected XML is applied. The enrolled `test_gtol_spec.py` and
`test_drawing_specification_purity.py` include source-only contract tests; these
are not native execution evidence. Parent offline checks and the farm gate must
cover **every drawing with direct or spec-projected FCFs**, including ordinary
frames. Farm evidence must capture ordinary/projected readback, reopen saved
SLDPRT and drawing frames, and inspect rendered tolerance value, circled-P symbol,
height and physical units on model and drawing, specifically after migration.

Projected controls additionally use the LOWER-only `_native_projected_zone` reader.
`capture_projected_gtol(model, gtol, *, expected_xml, key, phase, migrated=None)`
records exact expected/applied `GetSymbolXml` strings, the requested source height
in mm and the readback **XML numeric** height, plus actual document path/title/type.
Its native `GetUserUnit(swLengthUnit)` observation includes raw `IUserUnit.UnitType`,
`SpecificUnitType`, `GetConversionFactor()` and `GetFullUnitName(False)`. Neither
the conversion-factor direction nor `Projection` physical units are inferred.
Receipts explicitly say `physical_projection_unit_qualification="UNQUALIFIED"`
and `physical_projection_unit_verified=False`: they permit first-farm evidence
acquisition, not production publication without separate physical/render proof.
Ordinary `None` controls never invoke this additional reader or unit getters.
Saved-file receipts use `migrated=None`: migration history was not observed there.
Authoring callers pass their actually observed conversion-path Boolean.

After saving a projected part, or after `finalize_drawing` has closed a projected
drawing, callers use the same synchronous public API:
Saved drawing lookup covers canonically named `project_part_pmi` frames only.
An unnamed direct `add_feature_control_frame` projection has immediate semantic
capture but fails saved typed-control lookup; it is not silently accepted.

```python
from _native_projected_zone import require_saved_projected_gtols

require_saved_projected_gtols(adapter, artifacts["part"], controls, label=part_name)
# Drawing caller instead passes artifacts["drawing"], after finalize_drawing.
```

The reader never saves the audited target; its open-part reload never discards
dirty native part state. An open part must have
`GetSaveFlag() is False`; the current `IModelDocExtension.ReloadOrReplace` receives
`(False, same_saved_path, False, True)` in the documented order
`(ReadOnly, ReplaceFileName, DiscardChanges, ForceReload)`, with integer status 0
required. It reacquires the document and named annotation handles and rejects
changed native unit context. Already-closed files open read-only/silent through
connected-compatible `OpenDoc7`; the target is closed in `finally`, even after a
failed open that loaded it, and void `CloseDoc` is verified by native lookup.
Caller-held document, feature, face and annotation handles become stale after
reload; reacquire them from the refreshed `adapter.currentModel`.
The documented `CloseDoc` API also closes any non-active hidden documents and
discards their dirty state. Target identity checks do **not** prevent that API
side effect: perform this audit in an isolated farm context, without other dirty
hidden documents resident. This is not a general no-discard guarantee.
Wrong document identity, missing/duplicate/wrong-type annotation, non-string or
malformed XML, omitted projection or wrong height all refuse. An open drawing is
refused rather than silently discarded; its caller must finalize/close first.
The saved reader cannot turn an arbitrary phase label or stale handle into
saved-file proof. A broken identity/title/close lookup fails instead of closing
an unidentifiable document. Native physical unit and migrated rendered-P checks
remain mandatory parent farm gates; document-unit getters alone cannot waive them.

The source-only `test_native_projected_zone.py` covers these native getter shapes,
raw evidence, honest unqualified status, reload refusal/fresh-handle semantics,
multi-sheet annotation enumeration and read-only-open cleanup. Existing
`test_gtol_spec.py` also covers canonical writer capture and ordinary-path bypass.
These authored tests are pending parent centralized checks and native farm proof.
