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
may still run `build.py` directly; everything below is the contract for an
agent-driven launch.

The launcher is a foreground runner, not a second scheduler: it validates its
inputs, writes a startup record, runs exactly one `uv run … build.py` child,
tees its output to a log outside the worktree, and writes a terminal record
carrying the child's own exit code. It never retries, never cancels a remote
workflow, never detaches and never imposes a local deadline. Cancelling a farm
workflow is always a separate, explicit `farm.py cancel`.

### Prerequisites

- **PowerShell 7.3 or newer** (`#requires -Version 7.3`). The launcher clears
  `$PSNativeCommandUseErrorActionPreference` for itself so a caller's preference
  cannot turn a native exit 23 into a PowerShell exception.
- **The worktree's HEAD is pushed.** Every leaf fetches that exact SHA from the
  approved repository, so the launcher refuses a HEAD that no locally known
  `origin/*` ref reaches: `HEAD is not known on origin; fetch and push before
  launching`. Fetch and push first; the launcher does neither for you.
- **A clean worktree.** `build.py`'s farm preflight refuses dirty project inputs
  or dirty initialized submodules.
- **A protocol-compatible pool checkout** at `-PoolHome`, holding `farm.py`, and
  Azure credentials for the cache (`az login`; `off` is refused).
- **A log directory outside the worktree.** Run records and logs must never land
  in the tree whose cleanliness preflight checks.

### Parameters

| parameter | required | meaning |
|---|:---:|---|
| `-Worktree` | yes | absolute path to the checkout that supplies `build.py` and the environment; the build runs from here |
| `-PoolHome` | yes | absolute path to the `solidworks-pool` checkout; exported as `SOLIDWORKS_POOL_HOME` |
| `-LogDirectory` | yes | absolute path for the log and the run records; created if missing, and rejected if it resolves inside `-Worktree` |
| `-Targets` | yes | doit task names as ONE comma-separated string (`part:pen_rod,part:cone_gear`) |
| `-LeafTimeout` | yes | per-attempt remote leaf budget in minutes, 1–180 |
| `-Tag` | no | label recorded with the run (letters, digits, `_`, `-`); defaults to `run` |

Targets are *selections*, not variables, and they arrive as one string. `pwsh
-File` binds a single token per parameter, so a repeated `-Targets` or a
space-separated list is rejected before the script runs: pass
`"part:pen_rod,part:cone_gear"`. The launcher splits that string on commas,
trims each component, and rejects an empty set, an empty component, a token
starting with `-`, and a token containing `=`. That last rule matters: doit
removes a `name=value` argument as a command-line variable, so a mistyped
target would leave no selection at all and silently launch the full default
build. Task names use underscores (`part:pen_rod`), never dashes — a dashed
name is rejected by `build.py` before the fleet is contacted.

The launcher sets `SOLIDWORKS_POOL_HOME`, `HARMONIC_REMOTE_CACHE_MODE=rw` and
`PYTHONUNBUFFERED=1`, then runs, from the worktree:

```
uv run --frozen python build.py --executor farm --leaf-timeout <minutes> \
  --verbosity info -n 4 --continue <targets...>
```

`-n 4` is the submitter's own concurrency, passed explicitly so it wins over the
`-n 8` (`HARMONIC_FARM_PARALLELISM`) that `build.py` would otherwise insert.
`--continue` collects later failures instead of stopping at the first; any failed
task still leaves the run nonzero.

### Starting one under the supervisor

Start it with `hub` `op: "start"`, never with Bash. `persist: true` is what lets
the run survive the launching agent's turn and a session handoff; `detached`
would lose live monitoring, so it is not used.

```jsonc
{
  "op": "start",
  "name": "farm-pen-rod-smoke",            // unique; record it in the brief
  "application": "pwsh.exe",
  "args": [
    "-NoProfile", "-NonInteractive",
    "-File", "C:/src/harmonic-analyzer/scripts/farm-run.ps1",
    "-Worktree", "C:/src/harmonic-smoke",
    "-PoolHome", "C:/src/solidworks-pool",
    "-LogDirectory", "C:/src/dt-logs/farm-runs",
    "-Targets", "part:pen_rod",
    "-LeafTimeout", "90",
    "-Tag", "smoke"
  ],
  "pty": false,
  "persist": true,
  "progress": "wake",
  "ready": { "log": "farm-launch started", "timeout": 120 }
}
```

The full closure is the same call with `"-Targets", "build"` and
`"-Tag", "full-build"`. To hand off, pass the hub name and the record paths on;
do not `hub stop` a live launcher to quiet the console — retune it with
`op: "monitor"`, `progress: "ambient"` or `"off"`.

### The two records

Before the child starts, the launcher prints its readiness line and writes
`<run-id>.run.json`:

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
  "argv": ["uv", "run", "--frozen", "python", "build.py", "--executor", "farm",
           "--leaf-timeout", "90", "--verbosity", "info", "-n", "4",
           "--continue", "part:pen_rod"]
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
  "...": "the identity fields from the startup record, unchanged",
  "exit_code": 0,
  "elapsed_s": 1487.216,
  "finished_at": "2026-09-20T17:54:58.6980000Z"
}
```

Only exit 0 is `succeeded`; a wrapper exception is `failed` with exit 1 and its
diagnostic in the log. A run ID is
`yyyyMMddTHHmmssfffZ-<32 lowercase hex GUID characters>`, so it is
collision-resistant, and the launcher never overwrites an existing record, log
or marker: the three files for one run are `<run-id>.run.json`, `<run-id>.log`
and `<run-id>.done`, with `-Tag` recorded inside them rather than in their
names.

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
`.execution` token on disk.

### Recovering a run across a handoff

Read the records first, in this order:

1. **The supervisor is alive** (`hub ps` shows the name). Attach and monitor it.
   Do not start a second submitter for the same work.
2. **`.done` exists.** That is the outcome. `succeeded` with exit 0 is a finished
   run; anything else is a finished failure to diagnose from the log.
3. **The supervisor is gone and there is no `.done`.** The local outcome is
   *unknown*. It is not a cancellation, and it is not permission to relaunch.
   The remote work is very likely still running: `_farm.run_leaf` shares
   workflows by ID (`USE_EXISTING`), so killing the submitter never cancelled
   anything.

In case 3, harvest every workflow ID the log recorded — both
`Farm workflow requested: <id>` and `Farm workflow attached: <id>` lines, for
*all* leaves, not one representative — and query each from the pool checkout:

```powershell
uv run --frozen --project C:/src/solidworks-pool C:/src/solidworks-pool/farm.py status "<workflow-id>" --json
uv run --frozen --project C:/src/solidworks-pool C:/src/solidworks-pool/farm.py logs   "<workflow-id>" --follow
```

Follow a RUNNING workflow under a supervised monitor until it is terminal, then
finish the bookkeeping with the *unchanged* worktree, HEAD, targets and leaf
budget. The leaf budget is part of the workflow ID, so changing it during
recovery creates a different workflow instead of rejoining the one already
running. Never cancel a shared workflow automatically.

Relaunching the unchanged invocation is allowed in exactly one case: an
authenticated `NOT_FOUND` for an ID that was *requested* but never *attached*.
That pair of log lines exists precisely for the window between server acceptance
and the submitter's acknowledgement. Everything else stays unresolved and blocks
an automatic relaunch: `NOT_FOUND` for an attached ID, a missing or unreadable
identifier, a changed worktree or cache environment, or a `status` call that
failed on authentication, network or CLI error. An auth or network failure is
never a `NOT_FOUND`.

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
is almost always **one dep digest moving**. Three best-effort tools surface that
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
