# Developing — local workflow notes

Practical, machine-local development notes that don't belong in `AGENTS.md`
(orientation) or the per-topic policy docs: local pytest timing, supervised farm
launches and the remote build cache.

Running ONE SolidWorks operation by hand (this checkout has no local seat, so it
goes to the farm)? Read
[`cad/docs/one-off-com-operations.md`](cad/docs/one-off-com-operations.md) first
— it is the decision tree, the seat/cache invariants and the evidence trail for
an ad-hoc COM operation, and it links back here for cache detail.

## Drawing units

Every part and assembly drawing package must declare `drawing_unit` explicitly
in its own config YAML. Use `drawing_unit: in`; only the six metric-only supplier
packages named in `test_package_unit_declarations.py` may declare `drawing_unit: mm`.
Nondrawing parts listed in `test_part_coverage.PART_DRAWING_EXEMPTIONS` do not
need a drawing-unit declaration.
The SolidWorks-free `check:graph` gate enforces the declarations. The legacy
helper fallback remains `mm`, so a drawing package's omitted declaration is an
error rather than a way to select drawing units. Existing inch declarations and
metric title-block rows remain in place; their cleanup is tracked in #2199.

See [the drawing policy](cad/docs/drawing-simplicity-policy.md) for model units,
printed precision and metric supplier dimensions on inch sheets.

## Read-only cleanup inventory (Windows)

Before a clean slate, inventory the machine without deleting files, pruning
worktrees, stopping processes, or touching the primary checkout:

```powershell
# Uses only Python's standard library; run with an existing Python 3.12+.
# No uv sync, SolidWorks seat, or farm launch is needed.
python scripts/scan_cleanup.py

# Optional bounded logical-size estimates; JSON still goes only to stdout.
python scripts/scan_cleanup.py --measure --max-entries 20000 --max-depth 6 --seconds 15

# Include another shallow search root, an exact path, or another Git registry.
python scripts/scan_cleanup.py --root C:/scratch --path C:/scratch/build.log `
    --git-repo C:/src/solidworks-pool
```

The scanner checks only immediate children of the main checkout's parent (and
the script checkout's parent when different), `C:/`, `C:/tmp`, `LOCALAPPDATA`,
`LOCALAPPDATA/Temp`, and `TEMP`/`TMP` for `ha-*`, `sp-*`, `harmonic-*`, `mr-*`,
and `machrev-*`. It also checks immediate children of `~/.claude/projects` for
names containing `harmonic`; these are name-only leads, not ownership proof.
It does **not** recursively search the drive, AppData, or Temp.
Default exact entries include `C:/farm-build`, the main and script checkouts'
`wip`, `logs`, `build.log`, and `cad/out`, plus `LOCALAPPDATA/ha-farm` (the
farm launcher's fallback home), project cache/review-scratchpad directories,
and checkout-specific Claude directories under `LOCALAPPDATA`.
`HARMONIC_AGENT_SCRATCHPAD` adds both `harmonic-analyzer/farm-runs` and
`harmonic-analyzer/machinist-review-evals`. Without that override, running from
an OMP `local` working directory (`OMPCODE=1`) adds its
`harmonic-analyzer/farm-runs`, matching the launcher. Other sessions' OMP local
directories are not globally discovered; supply their paths with `--path`.
Known temporary Codex homes, `PROGRAMDATA/harmonic-analyzer`, and the **shared**
`PROGRAMDATA/solidworks-pool/archive-cache` are exact entries too. Their presence
does not make shared caches or authentication links disposable. Missing exact
paths are reported too; repeat `--path` for other known build logs or WIP
locations rather than widening the search to an entire drive.

Git's read-only `worktree list --porcelain -z` supplies exact registered paths,
branches, detached HEADs, locks, and prunable annotations for this repository,
the main checkout's sibling `solidworks-pool` when present, and every
`--git-repo`. Git probes ignore inherited `GIT_*` environment overrides.
`locked` and `prunable` are present as `true` when Git reports them and omitted
otherwise; optional explanations appear separately as `locked_reason` and
`prunable_reason`. A Git failure is a warning, not
evidence that a directory is unregistered. `primary_checkout` identifies Git's
main worktree, even when the script is in a linked checkout; on probe failure
it falls back to the script checkout with a warning.
A checkout with a `.git` marker but no matching registration is explicitly
flagged unless a reparse point prevents inspection. Primary and queried
checkouts, their contents, and ancestors are protected and never sized, with
two narrow exceptions: the exact generated-output paths above, and separately
registered nested worktrees. A checkout root or ancestor remains protected,
including the currently queried linked checkout. Generated-output exemptions
do not apply to paths redirected elsewhere, including into source content.
Candidates enclosing a registered worktree are flagged for Git-state and
active-use review, even when the candidate itself is not a registered worktree.
Inspection failures remain protected and require manual review.

JSON separates project-specific locations from **unverified name-only leads**.
Neither a prefix match, an old modification time, a detached worktree, nor a
prunable annotation proves that removal is safe. The scanner does not inspect
dirty/untracked files or determine whether a process or agent still uses a path.
Review those separately before any subsequent cleanup; this script has no
delete mode.

Sizing is opt-in, skips symlinks and **all** Windows reparse points (including
junctions and non-link tags), and shares one entry/time budget across candidates.
Discovery likewise skips a root if it or any ancestor is a reparse point;
it does not resolve that root and traverse its target. Such skips, inaccessible
roots, and exhausted discovery budgets appear in both `discovery` and `warnings`.
For a known linked root, an operator can explicitly supply its real target
with `--root` after reviewing that target. Git-marker inspection is skipped
under reparse points and the review explains that attribution is incomplete.
Discovery has its own global `--discovery-entries` cap (default 20000).
Measurements record limits and per-entry errors; an unreadable child does not
prevent examining its remaining siblings. Bytes are logical file sizes, not
allocated or reclaimable disk space; partial totals are lower bounds. Candidates
whose canonical paths overlap an earlier measured candidate are not sized
again; totals still must not be summed across overlapping paths. The time budget
is checked between filesystem operations; it cannot interrupt a blocked
filesystem call. Git probes have a separate 15-second timeout each.

## Cached machinist-review leaves

`check:machinist_review:<stem>` is a SolidWorks-free, submitter-only task for
every drawing that opts in, included in `build` and `release` under both executors.
It waits for the drawing PDF, runs three parallel blind reviews and a
sheet-grounded judge on a cache miss, then caches the complete per-drawing report
directory at `cad/out/reports/machinist-review/<stem>/`. The aggregate JSON and
Markdown are named `<stem>.aggregate.{json,md}`; per-run JSON and retained attempt
evidence remain alongside them. A cache hit evaluates the same verdict without
calling a model.

Draw scripts default to `MachinistReviewMode.OFF`: no review task exists, so
`build` and `release` spend no model tokens on the sheet. To opt in, import
`MachinistReviewMode` from `_machinist_review_mode` and declare
`MACHINIST_REVIEW = MachinistReviewMode.LEARN` (`FIX`/`ERROR` warn) or
`MachinistReviewMode.ENFORCE` (they fail the build) at module level. The graph reads
only the AST, rejects other value forms, and reruns verdict consumption when the
mode changes without re-keying the review. `FIX` is stored before enforcement;
provider/runner errors are never cached or freshness-stamped. An explicitly forced
refresh that produces no cacheable verdict fails even in LEARN mode, without
caching the error. Review keys hash the PDF, package exceptions, review code/import
closure, the selected kind's reviewer/severity prompts, shared reviewer/judge
prompts/schemas, shared drawing guidelines and the effective reviewer and judge
selections below, not the registry, enforcement declaration, or recipe-skipped
infrastructure such as telemetry. Build leaves always pass `--force`, so bypassed
PDF-diff implementation, identity-pairing inputs, and the precheck prompt/schema
do not invalidate their review cache.

Both review CLIs use a **120-second** sheets MCP startup budget, capped by the
per-attempt timeout. The runner sets Claude's `MCP_TIMEOUT` (milliseconds) and
Codex's `mcp_servers.sheets.startup_timeout_sec` to that budget rather than relying
on their shorter independent defaults. Startup and review still share one
overall attempt timeout. A failed connection remains a provider/runner error,
never a cached verdict.

### Selecting the build-gate reviewer and judge

Build-gate reviews default to **Claude / `claude-opus-5-5` / `medium`** for both
stages. Set these process environment variables **before starting the build**:

| Variable | Meaning | Default |
| --- | --- | --- |
| `HARMONIC_MACHINIST_REVIEWER` | Blind-review CLI (`claude` or `codex`) | `claude` |
| `HARMONIC_MACHINIST_MODEL` | Blind-review model ID | Selected reviewer's default |
| `HARMONIC_MACHINIST_EFFORT` | Blind-review reasoning effort | Selected reviewer's default |
| `HARMONIC_MACHINIST_JUDGE_REVIEWER` | Judge CLI (`claude` or `codex`) | Selected blind-review CLI |
| `HARMONIC_MACHINIST_JUDGE_MODEL` | Judge model ID | Selected judge's default |
| `HARMONIC_MACHINIST_JUDGE_EFFORT` | Judge reasoning effort | Selected judge's default |

The judge inherits the selected blind-review backend unless
`HARMONIC_MACHINIST_JUDGE_REVIEWER` explicitly overrides it. Each stage then
resolves its model and effort independently from that stage's backend; review
model/effort overrides do not override the judge's model/effort. Codex defaults to
`gpt-6-astra` / `low`; Claude defaults to `claude-opus-5-5` / `medium`. For
**Codex / `gpt-6-astra` / `high` for both stages**, run in PowerShell:

```powershell
$env:HARMONIC_MACHINIST_REVIEWER = 'codex'
$env:HARMONIC_MACHINIST_MODEL = 'gpt-6-astra'
$env:HARMONIC_MACHINIST_EFFORT = 'high'
$env:HARMONIC_MACHINIST_JUDGE_REVIEWER = 'codex'
$env:HARMONIC_MACHINIST_JUDGE_MODEL = 'gpt-6-astra'
$env:HARMONIC_MACHINIST_JUDGE_EFFORT = 'high'

# One gate (its drawing dependency is still built if needed):
uv run --frozen python -m doit check:machinist_review:sm_summing_lever

# Or the complete farm build, from a clean, pushed worktree:
./scripts/farm-run.ps1 -Worktree (Get-Location).Path `
    -PoolHome C:/src/solidworks-pool -Targets build -LeafTimeout 90 `
    -DisplayName 'Summing lever - Codex high review' -Tag summing-lever-codex-high
```

`farm-run.ps1` preserves these inherited process variables when it invokes `uv`
from the private snapshot; the reviews execute on that submitter, not on the
SolidWorks workers. Set them in the shell/process that launches the script
(including the supervised launch process), not in a different terminal after
launch. No tracked config edit, `HARMONIC_CACHE_SALT`, or forced cache refresh is
needed. The standalone `cad/scripts/machinist_review.py` continues to use its
explicit `--reviewer/--model/--effort` and `--judge-reviewer/--judge-model/--judge-effort`
options, not these build-gate environment variables.

The graph resolves and freezes all six effective values once, before cache
prewarming or leaf execution, and supplies all six explicitly to the review CLI.
Unknown providers, unsupported provider efforts, and empty or malformed model IDs
fail graph loading rather than silently defaulting or changing provider. Claude
efforts are `low`, `medium`, `high`, `xhigh`, `max`; Codex efforts are `none`,
`minimal`, `low`, `medium`, `high`, `xhigh`, `max`. Model IDs remain explicit provider model IDs:
availability and model-specific effort support are checked by the selected CLI,
not by an offline model catalogue in the build graph. Quota/auth/provider errors
never switch provider and never cache a verdict.

Changing any effective selection invalidates that review's remote verdict key
and local doit freshness, including when returning to an earlier selection after
a successful run with another profile. Explicit default-equivalent values use
the same key as unset defaults. Selection is folded into the review-only SHA-256
contextual digest of the real `machinist_review_config.py` source dependency,
preserving ordinary cache provenance; it creates no runtime config file and does
not affect part, assembly, drawing or other CAD keys/freshness. Unset the six
variables above to restore defaults on the next build process.

## Holistic review telemetry

Each aggregate emits one completed `machinist_review.precheck` child span before
any independent reviewer starts, including when `--force` bypasses precheck.
This is separate from `layout.audit`. Attributes are:

| Signal | Attributes |
| --- | --- |
| Precheck | `name`, `kind`, `judge_reviewer`, `judge_model`, `forced`; `outcome` is `skip`, `review`, `bypass`, or `error`; `skip_kind` is `rendering_noise`, `assembly_single_part`, or `none`; `reason` and `error` are forwarded unchanged (empty when absent), subject to the backend's 8192-character attribute limit. Bypass has the reason `Precheck bypassed by --force.` |
| Aggregate completion | `verdict` (`SHIP`, `FIX`, `ERROR`); `decision_basis` (`precheck_skip`, `full_review`, `error`); all precheck classification/text fields prefixed `precheck_`; requested `run_count`, `completed_run_count`, `valid_run_count`, existing run `error_count`, `judge_executed`, aggregate `error`, package `name`/`kind`, reviewer/model and judge reviewer/model. |

`precheck_skip` plus `SHIP` means change triage **without full reviewers**, not
baseline approval. `full_review` can have partial run errors; use the counts,
not the basis alone, to assess completeness. A valid zero-finding review does
not execute the findings judge. `--force` is `bypass`, not a clean precheck;
precheck failures are `error`, not `review`. Caught failures are represented by
these outcome/error attributes, not necessarily the SDK span status. These
signals do not alter the approval JSON or acceptance rules.

In Application Insights, these internal spans are in `dependencies`, with
attributes in `customDimensions`. The following queries count **observed
attempts**, not unique packages; ingestion can lag and sampling/retention can
limit observed totals. With Azure CLI, use `--offset 2h` (or a wider explicit
window) as well as the KQL time filter.

Completed prechecks in the last two hours, including aggregates still running:

```kusto
let attempts = dependencies
| where timestamp > ago(2h) and name == "machinist_review.precheck"
| extend outcome=tostring(customDimensions.outcome),
         skip_kind=tostring(customDimensions.skip_kind),
         reason=tostring(customDimensions.reason),
         error=tostring(customDimensions.error);
attempts
| summarize attempts=count(), skips=countif(outcome == "skip"),
            reviews=countif(outcome == "review"),
            bypasses=countif(outcome == "bypass"), errors=countif(outcome == "error")
| extend eligible_prechecks=skips + reviews
| extend skip_percent=iff(eligible_prechecks == 0, real(null),
                         100.0 * skips / eligible_prechecks)
```

The skip-rate denominator excludes bypasses and failed prechecks. To inspect
skip kinds and verbatim reasons, replace the final summary above with:

```kusto
attempts
| summarize attempts=count() by outcome, skip_kind, reason, error
| order by attempts desc
```

Completed aggregate SHIP provenance (including raw bypass/error counts):

```kusto
let completed = dependencies
| where timestamp > ago(2h) and name == "machinist_review.aggregate"
| extend package=tostring(customDimensions.name),
         package_kind=tostring(customDimensions.kind),
         verdict=tostring(customDimensions.verdict),
         basis=tostring(customDimensions.decision_basis),
         outcome=tostring(customDimensions.precheck_outcome),
         skip_kind=tostring(customDimensions.precheck_skip_kind),
         reason=tostring(customDimensions.precheck_reason),
         error=tostring(customDimensions.error),
         completed_runs=toint(customDimensions.completed_run_count),
         valid_runs=toint(customDimensions.valid_run_count);
completed
| summarize attempts=count(),
            skip_ship=countif(verdict == "SHIP" and basis == "precheck_skip"),
            full_review_ship=countif(verdict == "SHIP" and basis == "full_review"),
            eligible_prechecks=countif(outcome in ("skip", "review")),
            bypasses=countif(outcome == "bypass"),
            precheck_errors=countif(outcome == "error"),
            aggregate_errors=countif(verdict == "ERROR")
| extend skip_ship_percent=iff(eligible_prechecks == 0, real(null),
                              100.0 * skip_ship / eligible_prechecks)
```

For the latest completed result per package **within this two-hour window**,
replace the final summary with the following. This is not an all-time package
approval inventory, and does not include a newer in-flight aggregate; use the
precheck query for prompt in-flight decisions.

```kusto
completed
| summarize arg_max(timestamp, *) by package, package_kind
| project timestamp, package, package_kind, verdict, basis, outcome, skip_kind,
          reason, error, completed_runs, valid_runs, operation_Id
| order by timestamp desc
```

## Process travelers

`prechips:<stem>` tasks are opt-in: `build` and `release` do not run them, and
releases carry no travelers while prechips stabilises (owner ruling 2026-11-11,
[#2502](https://github.com/pedropaulovc/harmonic-analyzer/issues/2502)).
prechips is not in `uv.lock`; the wrapper runs the latest PyPI release with
`uv tool run` outside the project environment, logs its version once and
records it on its spans, so it needs `uv` and network access to PyPI. The
tasks run on the submitter, including when SolidWorks leaves run on the farm,
and always run when requested. To render a part's two travelers
(`traveler.html` under `--profile pro`, `traveler-hobby.html` under
`--profile hobby` with setup pictures) after its scoped feature bundle exists
under `cad/out/features/<stem>/` (from a build or a release asset):

```text
uv run --frozen python -m doit prechips:<stem>
uv run --frozen python cad/scripts/prechips_traveler.py <stem>
uvx --from prechips@latest prechips traveler cad/process/<stem>/plan.toml --profile hobby --out <file>
```

The doit task also runs its `package:features:<stem>` leaf first. Only exit 0
from both profiles is success. Exit 2 from either is a prechips refusal (bad
input or a failed enforced check) and leaves neither file; exit 1 means uv
itself failed (no `uv`, no PyPI, or a `uv tool run` error before prechips ran).
Plan authoring and the shop files are described in
[`cad/process/README.md`](cad/process/README.md).

## Local pytest timing

Run the CAD and pipeline suite serially for comparable timings:

```text
uv run --locked python -m pytest -q --durations=50 --junitxml=<outside-worktree>/cad-pytest.xml
```

The configured suite covers `cad/scripts`, `cad/comparisons/tools` and `tests`,
including offline diagnostic tests. To include the web Python tests, prepare the
dependencies and approved model cache using the
[fresh-checkout instructions](web/README.md#fresh-checkout-tests-and-approved-model-cache),
then use:

```text
uv run --locked --group web python -m pytest . -q --durations=50 --junitxml=<outside-worktree>/all-pytest.xml
```

Use an isolated worktree at a recorded commit and the same environment for
before/after runs. JUnit case times include fixture setup and teardown; a shared
fixture's cost is charged to its first consumer. Collection and session overhead
remain part of the suite wall time. Telemetry appends to that worktree's ignored
`cad/out/reports/telemetry`, and the root conftest isolates the buildgraph facts
cache in a temporary directory. Keep `NOSW_GUARD` enabled and leave
`HARMONIC_BUILDGRAPH_CACHE` unset. With the guard on (Windows only), a test
fails if it starts SolidWorks or its 3DEXPERIENCE launchers, shell-opens
anything (`os.startfile`, `ShellExecute(Ex)`, `explorer`/`rundll32`, a `cmd`
or PowerShell command that starts, opens or evaluates something, or names a
SolidWorks document), starts a service or another user's process, activates
SolidWorks, a SolidWorks document or a program-launching COM class
(`Shell.Application`, `WScript.Shell`, MMC, Task Scheduler, WMI), or reaches
dodo's `_exec_com` with its real subprocess runner. Fake the runner instead;
`tests/_child_guard/harmonic_solidworks_guard.py` lists every entry point.
The guard covers every Python child too: the
conftest puts `tests/_child_guard` first on `PYTHONPATH` and sets
`HARMONIC_TEST_FORBID_SOLIDWORKS`, so `python -m doit`, `build.py`, a git diff
helper or a build script started by a test loads the same refusals through
`sitecustomize`, exits 97 on one, and fails the test that started it. The
threat model is accidental launches only: the guard catches repo code and
tests that start SolidWorks by mistake, through the APIs that code uses and
their obvious neighbours. Deliberate evasion is out of scope: a native binary,
raw ole32 activation through ctypes, a shell verb built at runtime, or a child
run with `-I`, `-E` or `-S`, or with an environment that drops `PYTHONPATH`,
which skips the child guard. The vendored `SolidworksMCP-python` tests are
excluded because they can take the farm's SolidWorks licence.

Reuse source facts only within an unchanged-source scan, or immutable baseline
bytes for private mutation fixtures. Keep each case's writable checkout, task
state and invalidation checks isolated. Error-budget timings must retain the
configured draws, seeds, reference cases and numerical acceptance checks.

The oblique-jig drawing's fake native owners use a per-test, saved source path,
not the real `cad/out/sldasm` source. On Windows, a file disappearing between a
resolver's native lookup and prefix-removal probe can leave `\\?\` on only one
of two resolutions of the same input, so a fixture reading live build outputs is
not isolated from concurrent artifact publication.

The startup-retry cases in `test_machinist_review.py` use a test-local MCP
poll clock and a fixed number of pending responses. A proxy of only that test's
`machinist_review.asyncio` binding arms a real startup `Timeout` when polling
consumes the unchanged 0.75-second budget; neither global asyncio nor the event
loop's clock is modified. Windows launch/pipe scheduling stays under the real,
unchanged overall timeout instead of consuming the synthetic startup budget.
Real cancellation/reaping, the local Python protocol child, 131-KB pipe draining,
no prompt before connection and two attempts remain exercised. Separate slow-start
and shared-overall-timeout tests still use real time.

The aggregate SDK leader-timeout regression expires a real `asyncio.timeout(0)`
inside only the fake leader's connection, cancelling a pending await. It keeps
the ordinary attempt deadline for successful followers: a shared 200-ms budget
also times out credential loading and staging under parallel load. The regression
still requires leader disconnection before either follower is constructed, both
followers to succeed, and every SDK client to disconnect.

The refresh-carrier regression in `tests/test_farm_mode.py` runs a real nested
pytest against the cache test with a private `--basetemp`, plugin autoload and
ambient pytest arguments disabled, and global/signal OTLP endpoints explicitly
empty before collection imports telemetry. It preserves the inherited child
SolidWorks guard and deliberately retains the build refresh carrier: root
conftest must remove that carrier itself. Synthetic stale sibling runs must
survive, so the child cannot prune other sessions' evidence. Child stdout/stderr
are retained under the outer test's temporary directory even on timeout; the
30-second deadline is unchanged.

### Finite stock-envelope endpoint reuse

`paper_drive_stock_envelope._endcut_integral_bounds` carries each branch cell's
evaluated endpoints into its children and evaluates their shared midpoint once.
Reuse is confined to the same profile, branch and exact parameter within one
invocation; there is no persistent point cache. Cell arithmetic, heap priority
and serial ordering, left/right child order, outward `nextafter` accumulation
and stopping decisions must remain unchanged.

For #1621, a controlled fresh-process comparison matched all 31 hexadecimal
value rows, including every hub seat-area corner and feed-pinion/knob consumer
bounds. Instrumented point calls fell from 1,167,916 to 292,195; worker elapsed
time was 4.7161 s before versus 2.7085 s after, with hub import 3.4351 s versus
1.9520 s. These measurements cover one paired pure-data import/bounds comparison
with the same counting wrapper, not recipe-gate, native-build or whole-build
timings. Changing this helper still changes source digests for native consumers whose
dependency closures include it; exact numerical bounds do not avoid that
cache invalidation or replace the applicable native gate.

### Recipe gate scheduling

`check:recipe` alone runs its complete explicit test inventory with
`pytest -q -p no:cacheprovider --collect-in-virtualenv -n 8 --dist worksteal`.
`--collect-in-virtualenv` is safe here only because the gate supplies an explicit
file list: it avoids repeated parent-directory virtualenv-marker probes without
expanding that inventory. Do not apply it to normal recursive pytest discovery.

Enroll new SolidWorks-free test files in `dodo.task_check`;
`test_check_gate_enrollment.py` rejects uncollected files. Release packaging's
fake-seat cleanup and error-preservation contracts
(`test_package_native_cleanup.py`) run in `check:recipe` beside failure forensics.

In one ordered, unchanged 291-file, serial (`-n 0`) collect-only pair, baseline
collection took **75.1735279 s** versus **38.6164179 s** with the flag; the
**11,513 node-ID multisets were identical**. This is collection-only evidence,
not a recipe execution or whole-build speedup measurement.
Local offline `check:*` gates share a host-wide CPU-worker budget across doit
processes, worktrees, and farm snapshots: `round(logical CPUs × 0.8)`, minimum
one. On amet's 16 logical CPUs that allows 13 workers, not one gate at a time.
Single-process checks cost one slot. A recipe requests up to eight; another
recipe can use the remaining five concurrently. Admission rewrites pytest's
`-n`/`--numprocesses` argument to the number actually granted, including
`auto`/`logical` requests, which use the configured host budget. A parallel suite
waits for at least half its requested
workers (rounded up, after capping the request to host capacity); an insufficient
provisional allocation is released immediately. This avoids launching a long
recipe at one worker just because short checks temporarily occupy the host.
Worker counts stay fixed for that suite's lifetime.
Pytest checks without an explicit parallel-worker request receive command-line
`-n 0`; inherited `PYTEST_ADDOPTS` or configuration `addopts` cannot silently
turn a one-slot check into an unbudgeted worker pool.
This is a concurrency target, not a hard CPU-utilization cap: I/O waits,
subprocesses inside tests, and unrelated applications affect measured usage.

`_local_check.py` uses `%PROGRAMDATA%/harmonic-analyzer/local-check.lock` for
brief allocation and adjacent numbered slot locks for execution. A check
holds its own slots before importing its entry point. A dead submitter cannot
release a still-running check's capacity; the OS releases slots when the check
exits, including a crash. No partial allocation waits for more slots, so
competing suites cannot deadlock. Never delete lock files to unblock a queue.

Remote farm leaves and cached machinist reviews use separate budgets. Doit
still owns dependency checks and success stamps. The `local.check.wait` span
measures admission latency; logs record requested/granted workers, host
capacity, and execution `held_s`. Top-level telemetry context is unchanged.
A refused admission logs at once and then every 30 seconds, with no queue
deadline or failed-check retry.

`HARMONIC_LOCAL_CHECK_LOCK` selects the lock namespace and
`HARMONIC_LOCAL_CHECK_CPU_SLOTS` overrides capacity (a positive integer).
Tests use isolated namespaces and small capacities. Production submitters
must agree on both settings and use this admission version. Older snapshots
do not participate correctly; resume paused launches from updated commits.
Direct pytest bypasses admission; use
`uv run python cad/scripts/_local_check.py check:manual -m pytest ...` for
manual suites alongside builds. Nested pytest/xdist children belong to the
enclosing check and must not acquire admission again.

Work stealing rebalances individual tests instead of pinning the dominant
recipe-test file to one worker. Each worker still pays collection costs, and
module/session-scoped fixtures may execute in multiple workers; tests must not
rely on shared mutable fixture state across processes.

The coordinator compared the same frozen source (`4d89b02fb`) and production
recipe inventory sequentially on that host, changing only xdist scheduling:

| Scheduler | Process wall time |
|---|---:|
| serial | 1366.4064949 s |
| 8 workers, `loadfile` | 1114.6658742 s |
| 8 workers, `worksteal` | 532.3394605 s |

`worksteal` reduced recipe-gate wall time by **61.04% (2.5668×)** against serial.
The coordinator's retained process logs and JUnit reports are the evidence:
serial and worksteal had identical counters of `(classname, name, outcome)` for
all **11,498 cases** (11,493 passed, 2 skipped, 3 xfailed). The serial/loadfile
reports are `recipe-fixed-0.xml` and `recipe-fixed-8.xml`; the worksteal report
is `recipe-worksteal-8.xml`, from the same frozen source.
See [PR #1622](https://github.com/pedropaulovc/harmonic-analyzer/pull/1622)
for the benchmark handoff. These measurements precede the additional nested
guard regressions and measure **only `check:recipe`**, not a full build or the
end-to-end 5× target in #1621.

For a serial/parallel comparison of the **production recipe inventory**, run
these commands sequentially from the isolated worktree's root. They derive the
argv from `task_check()` rather than substituting a broader `pytest cad/scripts`
run, and bypass the stamp so both runs execute. Replace the JUnit paths with
distinct absolute paths outside the worktree; keep the guard and environment
settings above. These admitted runs do not update the gate's success stamp.

```powershell
# Serial baseline: remove only the recipe gate's four xdist arguments.
uv run --locked python -c "import dodo, subprocess; t = next(t for t in dodo.task_check() if t['name'] == 'recipe'); c = list(t['actions'][0][1][0]); i = c.index('-n'); del c[i:i+4]; raise SystemExit(subprocess.call(dodo._local_check.command(c + ['--durations=50', '--junitxml=C:/outside-worktree/recipe-serial.xml'], 'check:recipe'), cwd=dodo.REPO_ROOT))"
# Parallel: run the production argv unchanged, plus timing/report options.
uv run --locked python -c "import dodo, subprocess; t = next(t for t in dodo.task_check() if t['name'] == 'recipe'); c = list(t['actions'][0][1][0]); raise SystemExit(subprocess.call(dodo._local_check.command(c + ['--durations=50', '--junitxml=C:/outside-worktree/recipe-parallel.xml'], 'check:recipe'), cwd=dodo.REPO_ROOT))"
```

Compare full case inventories and outcomes as well as process wall time; JUnit
case-time sums are not parallel wall time. `worksteal` does not isolate writes to
shared repository paths across files or workers. Tests must use temporary paths
for mutable outputs; retain `-p no:cacheprovider` to avoid the shared Windows
pytest-cache rename race even when multiple doit gates run concurrently.

Each xdist worker owns a separate child-refusal log; nested sessions and Python
descendants retain their worker's log, so a refusal fails its owning test rather
than unrelated siblings. Both the pytest-process guard and inherited child
guard permit injected fake COM runners while refusing real subprocess runners.
When pytest configures an inherited worker, existing guard hooks hand refusals to
pytest's raising/recording handler instead of terminating the worker. This
process-local handoff is not inherited by fresh Python children: they still log
and exit 97 on a refusal.
Nested pytest sessions forward unconsumed refusals when enforcing a test failure
or finishing collection, even if their caller ignores the failed subprocess.
Expected refusals consumed by guard self-tests are not forwarded. Nested xdist
workers return refusal evidence to their controller through worker results,
never by writing into a sibling's refusal log.

## Persisted assembly display data

Assembly publication requires both a fresh native rebuild-state proof and a
strict check of the saved `Contents/DisplayLists` part flags. A clean
`NeedsRebuild2 == 0` does **not** prove that eDrawings has complete saved previews.
Full builds and refreshes gate persisted bytes before publication; even an
unchanged refresh rejects invalid saved bytes instead of certifying a no-save hit.
`assert_saved_display_data(path)` is strictly read-only.

### Preventive display-data mark

The production fix is preventive, not a repair. Before an assembly is saved
natively for the first time (`SaveAs3` copy) and before every changed in-place
or reconcile `Save3`, `_mark_assembly_display_data` enumerates the **existing**
configurations of the open model and sets the supported
`IConfiguration.LargeDesignReviewMark = True` on **every** one of them. A
configuration that already reads back `True` is skipped, so no extra native call
dirties it; otherwise the assignment is read back with an identity-strict
`is True` check on the `VT_BOOL` value (no generic truthiness) and fails closed
if any configuration does not report the mark. It never calls
`ShowConfiguration2`, never creates or rebuilds configurations, and never
changes geometry; the active configuration is checked to be the same before and
after. A null configuration, a missing active configuration or a
configuration-API error aborts the save.

The mark is only defined for multi-configuration assemblies. Exactly one
configuration is a recorded not-applicable outcome and the save proceeds
unmarked; zero configurations or a failed enumeration is **not** not-applicable
and aborts. One telemetry span wraps the whole loop with the configuration count,
names and outcome; there are no per-configuration spans.

An unchanged, complete assembly is a full no-op: reconciliation and refresh
never mark and never save it, so its bytes stay identical.

### Reconcile cycle

Reconciliation runs the strict read-only saved-data preflight, then opens the
assembly. If `NeedsRebuild2 == 0` it returns without writing. Otherwise it keeps
the original cycle: rebuild every configuration with the rest-of-run
configuration last, `AddRebuildSaveMark` with readback, the display-data mark
above, exactly one validated `Save3(1)`, a fresh reopen proving
`NeedsRebuild2 == 0`, and the strict saved-data gate. There is no display-only
repair `Save3`, no extra verification reopen and no separate zero-flag branch:
a supported zero flag in the saved output simply fails. Native saves require the
native `(bool, int, int)` result tuple: false or errors fail, warnings are
logged, and there is no generic retry or repair of unsupported formats. In-place
saves and refreshes apply the same strict preflight and output validation and
do not catch `IncompleteSavedDisplayData`.

### Saved-data parser

The parser supports only the empirically observed v37/v40 layout, not a
documented SOLIDWORKS format. It checks every exact display-list stream, compressed
completion, sizes and CRC32, with a 64 MiB expanded limit per stream, and validates
recognized `.SLDPRT` records and flags; nothing else is interpreted. Legitimate
zero `.SLDASM` container flags are excluded. Missing, malformed, unknown,
overlapping or extended-length records fail closed; zero flags are classified
(`IncompleteSavedDisplayData`) only after **all** streams and records validate,
so a structural fault is never masked by an earlier zero flag, and neither
outcome authorizes any save. Observed decoys and verified directory-copy
references delimit inspection; the remaining footer, absent configurations and
actual rendered eDrawings visibility are not proven by this gate — it observes
part records, nothing more. A tagged part-path string with the same prefix is
not distinguishable from a component record.

### Pinned native reproduction (historical evidence)

The temporary probe, builder hook and pn-only output declarations were removed
from tip; no private per-instance flag setter and no diagnostic hook ships, and
the diagnostic source is not imported by production. The runs below are the
evidence that selected the preventive mark; the C→E→F differential is **not**
the production fix.

Reproduce the original causal matrix only from an isolated checkout at
`f4927b968cb93cb46da933b1d011ebded120cede`, which retains the probe and builder
hook. Under [the persistent supervisor](#starting-one-under-the-supervisor), use
the existing `farm-run.ps1` launch shape with `"-Worktree", "<checkpoint checkout>"`,
`"-PoolHome", "C:/src/solidworks-pool"`, `"-Targets", "assembly:pn_pen"`,
`"-LeafTimeout", "90"`, `"-DisplayName", "DisplayData - Reproduce pinned pn matrix"`
and a unique `"-Tag", "display-data-repro"` / supervisor process name. Keep logs
outside worktrees, retain the recorded run and use the protocol-compatible pool;
do not invoke the probe locally or transplant its hook into production.
The observed protocol-6 run was
`20261012T071150070Z-5c47034df7644314b3136e88072c9fd6`.

In its cached-hanger-twice plus threaded-screw fixture:

- C (`refcfg-c-both-rebuild-copy11`): all three part flags were 1,
  `NeedsRebuild2 == 1`, and eDrawings hid 0 components.
- E (`refcfg-e-reconcile-save1`): the then-production derived/Default
  `EditRebuild3` / `AddRebuildSaveMark` / `Save3(1)` sequence left the first unique
  hanger and screw flags at 0, the duplicate hanger at 1,
  `NeedsRebuild2 == 0`, and 1 hidden component.
- F (`refcfg-f-fresh-resave-save1`): freshly opening E and only `Save3(1)`-saving
  produced all flags 1, `NeedsRebuild2 == 0`, and 0 hidden components, without
  configuration switching, rebuilding or mark writes.

The original full pn assembly had 8 zero flags across 10 groups and 8 hidden
components; `normal-resave-inherited` yielded 0 hidden components without adding
LDR marks. All referenced input hashes stayed unchanged. These are differential
native-save and eDrawings observations: the internal first-unique-record-specific
mechanism remains **UNPROVEN**, not an inferred SOLIDWORKS implementation detail.

The stronger, selecting evidence is the independent diagnostic matrix at
`7caba42893615b78541204fc6d79ac710c206bf7`, run on the actual pn assembly with
the unchanged production builder on SOLIDWORKS 2026
([`pn-pen-display-matrix.json`](https://github.com/user-attachments/files/33348209/pn-pen-display-matrix.json)):

- Marking **both** `Default` and `Default Simplified` before the first
  `SaveAs3` copy (option 11), followed by the original first reconciliation
  `Save3(1, 0, 0)`, produced 16 part records with 0 zero flags, all 8 parts
  visible in eDrawings, `NeedsRebuild2 == 0` and `GetSaveFlag == False`.
- Marking **only** `Default` produced 8 zero flags and 8 hidden components.

This proves the preventive mark for that assembly and fixture; other assemblies
await the full-farm build and native eDrawings visibility review.

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
- **A protocol- and identity-compatible pool checkout** at `-PoolHome`, holding
  `farm.py`, `pyproject.toml` and `agent/protocol.py`, plus Azure credentials for
  the cache (`az login`; `off` is refused).
  Preflight checks every would-be leaf in the entire requested closure with
  that checkout's authoritative `agent.protocol.leaf_admitted`; refused tasks
  and prefixes exit 2 before joining the FIFO. Mixed agent versions are expected
  during rolling upgrades and are not checked; the protocol version is.
  This is deliberately conservative for doit `-s`/`--single` and cache hits:
  the entire requested closure is prechecked, even when some leaves would not
  execute.
  After successful preflight, the parent exports the admitted label set as
  `HARMONIC_FARM_ADMITTED_LEAVES` only while executing the doit command in its
  producer context, restores the prior value afterward, and lets workers
  inherit it. Actual `run_leaf(task, cache_key)` dispatch checks that set before
  any request, span/config/identity lookup or reservation. A missing or invalid
  set, or a task absent from it, raises a local `RuntimeError` naming the task
  and its lack of preflight admission; the guard uses no copied prefix list.
  The worker independently limits its exported graph to the build/release
  closure; preflight admission does not enforce that restriction.
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

### Validated selective worker execution

Selective execution is an internal worker path, not a different recipe or a
`--single` shortcut. The committed `build.py` literal
`SELECTIVE_EXECUTION_CAPABILITY = "canonical-closure-v1"` declares support; the
pool reads it without importing the producer and records it in the trusted graph.
An environment variable or invocation argument cannot declare that capability.
Supported older immutable sources without the declaration retain the explicit
`canonical-full-v1` loader. A missing, forged or mismatching graph, an unsupported
declaration, or a canonical validation error never falls back to the full loader.

The normal generators and selective loader reuse the same per-name builders.
The latter constructs exactly the exported dependency closure as genuine doit
Tasks, including checks, verification, package and export dependencies. It retains
trackers, value savers, wrappers, action results, hooks, stamps, refresh behavior
and group/subtask metadata. Validation runs after an isolated `TaskControl` pass
has inferred task dependencies from file dependencies. It compares task names,
task/file dependencies, targets and Python callable identities against the trusted
graph, and checks live target ownership so an existing output cannot hide an
omitted producer.
Path ownership and comparison of file dependencies and targets use OS-normalized
path identity; serialized paths and graph hashes retain their original spelling.
On Windows this uses `normcase`, not per-directory case-sensitivity detection, so
case-sensitive directories may conservatively reject distinct output claims.
Task names, callable names and action arguments remain case-sensitive.

The selective loader first imports `dodo` under the caller's working directory.
It then validates that the provider's `REPO_ROOT` matches its workspace and
changes to that workspace before loading doit configuration or invoking the
canonical task/ownership providers and task actions. Factory inputs and actions
therefore use workspace-relative paths; module import has no such cwd guarantee.
The authority check itself does not change cwd when it refuses a provider.

Serialized Python is never executed. Action arguments come from the live
canonical factories, not graph JSON; the producer deliberately does not duplicate
the pool's action-argument normalizer. This contract is currently bound to graph
schema **3**, farm protocol **7**, and the exact exported task/action record shapes.
Changing any of those requires an explicit paired producer/exporter migration,
not field stripping, an environment opt-in or a validation fallback. The existing
source/request/lock/Git/environment checks and requested-result-key probe/forced
execution flow remain required.

Trusted graph export alone uses the pool's `canonical-farm-v1` profile: build-order
seed `farm`, machinist reviewer `claude`, local executor, read-only remote cache,
and no inherited refresh carrier. This does **not** pin live action arguments or
remove supported runtime reviewer overrides. Actual worker execution keeps its
writable-cache policy and request-scoped refresh contract.

Activation requires the companion pool worker implementation: it reads the
committed declaration and supplies all three internal
`--farm-execution-{graph,task,identity}` options to a local, serial worker run.
The normal farm launcher does not supply those options. Older workers continue
their ordinary full-loader invocation; the new worker release and the explicitly
selected `PoolHome` must match under existing fleet-identity admission before
selective farm execution is available. No controller wire change is required.

This staged feature leaves ordinary farm submission and lifecycle handling
unchanged. It adds no preparation-publication API or publisher-configuration
requirement; preparation transport is a separate change.

### Interpreting selective execution measurements

Worker markers separate dependency/build import, dodo import, task construction,
ownership indexing and control validation. `first_action` marks the first actual
doit action; `selected_action` marks the requested root's action, so dependency
restoration can lie between them. A head-only loader harness stops at the
loader/TaskControl handoff: its readiness marker is not an observed action or
live-leaf head and excludes dependency-status/DB work, restoration, body and COM.
Use independent ordinary-generator snapshots, identical committed source and graph,
the same locked interpreter/cache conditions, paired repeated processes and spread
as well as medians. Do not infer end-to-end savings from a body-contaminated run.

For file-only comparison runs, pass explicit empty strings for
`OTEL_EXPORTER_OTLP_ENDPOINT`, `OTEL_EXPORTER_OTLP_TRACES_ENDPOINT` and
`OTEL_EXPORTER_OTLP_LOGS_ENDPOINT` before Python imports. Absent variables can
re-enable default discovery; use a launcher that preserves empty child values.
Existing COM-free `check:math` component measurements do not establish native
output equivalence or the whole-farm **25% overhead-reduction target**.

### Parameters

| parameter | required | meaning |
|---|:---:|---|
| `-Worktree` | yes | absolute path to the checkout whose pushed HEAD is built; the build runs from a private snapshot of that commit, never from here |
| `-PoolHome` | yes | absolute path to the `solidworks-pool` checkout; exported as `SOLIDWORKS_POOL_HOME` |
| `-LogDirectory` | no | optional absolute path for run files and outputs; defaults under the agent scratchpad and must resolve outside every Git worktree |
| `-Targets` | yes | doit task names as ONE comma-separated string (`part:pn_pen_rod,part:dt_cone_gear`) |
| `-LeafTimeout` | yes | per-attempt remote leaf budget in minutes, 1–180 |
| `-DisplayName` | yes, Launch only | short owner/session plus reason; nonblank, single-line, no control characters, at most 160 characters; tracking commands such as `-Watch` do not require it |
| `-ForceCacheRefresh` | no, Launch only | string array of exact remote-cache leaf task names; each string may also be comma-separated |
| `-ForceCacheRefreshReason` | with refresh labels only | why these cached outputs must be overwritten; same text/Unicode rules as `-DisplayName` |
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

Every new leaf execution has coordinator-authored Temporal memo `display_name`,
separate from optional launcher metadata `farm_run`. Neither label enters the
workflow ID or cache key. Protocol 7 retains the build-scoped workflow ID,
`leaf:<build_id>:<task>:<cache key or commit[:16]>:<timeout_s>s`, and binds each
accepted reservation to an exact workflow run. Builds can reuse cache artifacts,
but never attach to another build's execution. The display label identifies
the build that owns the execution.

Old native workflow-ID formats are unsupported by the launcher, including
status inspection and remote cancellation. Finish or cancel those runs with
their matched old tools **before** the coordinated cutover to an idle,
physically drained fleet; there is no runtime legacy fallback. Cancellation
still stops safely attributed local processes before rejecting invalid remote
identities (exit 2), without remote commands or output/snapshot cleanup.

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

### FIFO capacity reservations

After successful preflight, the parent build creates a fresh timestamp-and-GUID
`build_id` (`YYYYMMDDTHHMMSS.ffffffZ-32hex`), ignoring any inherited
`HARMONIC_FARM_BUILD_ID`, and registers with the protocol-7 fleet's singleton
`solidworks-build-fifo-7` coordinator. After registration
is acknowledged with an open, valid producer lease, its doit scheduler starts
immediately, even with zero reserved capacity or ownership reported as waiting.
Local/cache work and dependency preparation can progress in every build; native-ready
leaves submit reservations even when that build currently has no worker allocation.
The coordinator, not a producer-side exclusive gate, controls native admission.

Capacity is reserved in registration FIFO order using actual usable workers.
Unused reserved workers transfer to the next open build after 180 seconds idle;
each further transfer starts a fresh 180-second interval. Assignment or physical
release starts the idle clock; producer heartbeats do not reset it. Admissions
consume the newest idle worker first, preserving older surplus transfer clocks.
The oldest open unfinished producer retains a one-worker floor through DAG gaps.
For five usable workers and wholly idle builds A/B/C, reservations start A=5,
become A=1/B=4 after 180 seconds, then A=1/C=4 after another 180 seconds.
Occupied workers are never preempted. If the head's worker disappears while
surviving workers are occupied by younger builds, its floor remains explicitly
unsatisfied until physical release; zero usable capacity is also explicit.
Closing or expiry releases idle reservations, not occupied/drain obligations.

`build-status --build-id <build_id>` exposes `reserved_capacity` and `occupied_capacity`;
`fifo-status` exposes an active-build list, `head_build_id`, `usable_capacity`,
`occupied_capacity`,
`reserved_idle_capacity`, `capacity_observed_at` and any `capacity_error`.
Reserved idle capacity is not permission for another build to steal that worker.

The supported runtime is Python 3.12–3.14 (`pyproject.toml` and `uv.lock`);
`.python-version` selects 3.14 for development rather than narrowing that
contract. Cancellation joins the parent renewal thread, closes the named build
even if registration's reply was still uncertain, and restores the inherited
build-ID environment. A producer whose registration was not acknowledged never
enters the scheduler.

Only the parent renews its producer lease, every 15 seconds on an independent
background thread, from acknowledged registration through closure. Renewal does
not poll `build-status` or wait for capacity or exclusive ownership. Spawned action
processes inherit `HARMONIC_FARM_BUILD_ID` but do not renew the lease. The coordinator's 120-second
producer lease expires after a killed or disconnected parent. This 120-second
lease is distinct from the 180-second idle-capacity transfer timer. Transient
heartbeat RPC failures are retried only while the last acknowledged lease remains
valid; an uncertain heartbeat reuses its sequence and update ID.
Queries and duplicate replies do not extend that deadline. Expiry or an explicit
coordinator refusal fails the producer closed, with no reopening or late renewal.
Normal completion closes ownership as `finished`, task failure as `failed`,
and an interrupted parent as `cancelled`. A failed final close RPC is a warning:
server lease expiry fences ownership, so the command's actual exit code is kept.
This does not suppress an earlier ownership loss or an artifact/action error.
Closing ownership alone never cancels remote leaves.

The producer records its build and each leaf request before submitting a
reservation to the coordinator. The coordinator owns leaf startup and exact-run
binding. Accepted reservations remain outstanding even when startup or its
response is uncertain; absence of a workflow is not evidence of no accepted
work. Closing or expiry blocks new admissions but does not discard accepted
reservations. A worker occupied by accepted work cannot be reassigned until those
reservations settle and every attempt acknowledges actual native execution and
cleanup completion. Other builds can still use their own reserved workers.
Temporal workflow closure, timeout, cancellation and producer lease expiry do
not prove physical drain. Unknown or unconfirmed attempts keep the affected
capacity fenced fail-closed until physical-drain evidence is supplied through
the pool operator surface.
`leaf-status` exposes failed startup, grant or history observation as
`state: "recovery_required"` with typed `error_code` and `error` fields. The
producer fails the affected action rather than polling forever or attaching to
a binding whose recovery failed. These reservations remain fail-closed.

Once a leaf reservation is accepted but not yet bound, transient transport
failures reading `leaf_status` retry the same `LeafKey` for at most 120 consecutive
seconds, including any RPC in progress. A successful reserved reply starts a new
read-outage budget; healthy startup polling is not given a total time limit.
This independent monotonic transport budget is not an acknowledged producer
lease: only the parent renews ownership and the coordinator fences native
admissions. Reconciliation never resubmits, starts or cancels the canonical leaf.
Foreign keys/bindings, recovery-required status, invalid states and definitive
RPC refusals fail immediately. Exhausting the read budget fails the local action
without discarding the accepted reservation or manufacturing a result.

For a settled failed reservation, an operator can supply independently checked
physical-drain evidence with `farm.py confirm-reservation-drained --build-id <id>
--workflow-id <wf> --evidence <text>`. An unbound reservation must omit `--run-id`.
A bound reservation requires `--run-id <run>` matching its immutable exact-run
binding, no pending starter or watcher, and every known attempt already drained.
The coordinator rejects confirmation without those conditions; it never infers
physical drain from missing history. Confirm a bound attempt separately with the
pool's exact-run `confirm-attempt-drained` command before reservation recovery.
Both are explicit operator confirmations; neither workflow closure nor a missing
run is their evidence source. Worker drain signals require actual native cleanup.
The operator-versus-worker source distinction is a trust convention, not a
separate enforced authorization boundary: both operator updates require explicit
evidence, and callers must not manufacture it from Temporal state.

A parked pre-grant workflow ignores ordinary cancellation. When recovery
involves a stale or foreign execution, independently verify that native execution
and cleanup have physically stopped, then terminate only that exact stale/foreign
run in the Temporal UI before sending an operator drain confirmation. Check its
run ID rather than acting on a later execution sharing the canonical workflow ID.
Termination is cleanup of the Temporal execution, not evidence of physical drain.

An already-running coordinator is reused, but a terminal coordinator cannot be
recreated as an empty singleton: that would forget accepted work and drain
obligations. Recovery requires physical-drain evidence and a reviewed,
snapshot-aware recovery or history reset, not another producer launch.

Protocol **7** is a hard wire cutover from protocol 6: both repositories advertise
7 and exact-equality admission refuses older clients or workers. `LeafRequest`
adds optional `refresh_reason`, validated before any work; only that leaf's child
process receives the refresh carrier. No protocol-6 compatibility shim is provided.
Protocol 7 also moves the coordinator/workflow identities:
`solidworks-build-fifo-7`, workflow type `BuildFifo7`, and native type `BuildLeaf7`.
A protocol-7 controller must never replay the protocol-6 coordinator: its accepted
protocol-6 `submit_leaf` updates fail protocol-7 validation on replay, which is a
nondeterminism error (seen 2026-10-17 when protocol 7 first shipped under the old
identity). The producer still describes the coordinator under the bounded RPC
deadline and requires exactly `BuildFifo7`; a reused ID with any other workflow
type is refused
without updates, termination or replay. The handle remains unpinned across
continue-as-new. This type identity check does not replace wire-protocol
preflight or the required coordinated cutover.
Paired producer, pool coordinator and worker deployment
requires an idle fleet with all old physical work drained, no outstanding
reservations and no unconfirmed attempts. The matching pool commit is a required
external paired dependency, not a compatibility shim or implicit source pin.
Do not deploy from this implementation worktree; live-history migration requires
a separately reviewed replay/migration plan.


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

During the rolling-main trial, the release manager continuously full-builds
`main`. Individual PRs and stacks may merge after their authors provide focused
source checks, appropriate native proof and the applicable code/render reviews;
they do not need a full build of their own. Changed sheets still require
automated machinist review under the existing direct/indirect sheet policy.
Substituting human machinist review requires explicit owner authorization. See
[the merge requirements](AGENTS.md#minimum-merge-gate-every-pr).

The release manager attributes rolling-main failures and immediately delegates
a simple, bounded repair for roll-forward; otherwise the attributable PR is
rolled back. The daily release may publish only from green main, with a
successful full build and all release checks for the exact source commit
and artifacts being released. The trial does not change the task graph,
executors, cache contracts or release checks.

Never launch the `release` target through `farm-run.ps1`: it runs in a
disposable snapshot, and cleanup would discard the publisher's post-release
tracked image and `release.yaml` updates. Launch
with `-Targets "build,export,package:release,preflight"` (`build` supplies drawing
and check gates). Once successful, restore the complete `cad/out` from the
recorded `.done` `outputs` path (normally `<LogDirectory>\<run-id>.out`) into
the owning worktree. Then run `uv run --frozen python -m doit -s gallery`
followed by `uv run --frozen python -m doit -s release -- vNN` there. This keeps
the gallery and publish in the owning worktree without local COM redispatch.

Every release also prepares and attaches
`harmonic-analyzer-vNN-drawing-diff.zip`, separately from the main CAD bundle,
the existing 3D changed-parts PNGs and the logs asset. Extract it and open
`index.html` for per-page drawing overlays and `summary.json` for the complete
changed/added/removed/unchanged inventory. Red is old-only/removed ink, blue is
new-only/added ink, and light gray is common ink. Only changed pages get PNGs;
the index and summary still ship when no drawing changes remain.

The drawing baseline is the highest published, non-draft, non-prerelease compact
`vNN` below the version being cut, not an orphan local tag. The publisher fetches
only the previous CAD ZIP's directory and PDF members over HTTP ranges; it does
not download the full CAD asset. Missing assets, authentication/network failures,
malformed archives, unsafe/ambiguous member names and unreadable PDFs block the
release before tagging. A genuine historical bundle without PDFs is an empty
drawing baseline; on the first release every current drawing is added.

All PDF drawings and pages participate, including added and removed drawings or
pages. Only geometrically identified BUILD/REV value glyphs are masked, not the
whole title block. At 144 dpi, ink is matched in both directions against the
darkest pixel within one pixel along each axis (Chebyshev distance), allowing
68 grayscale levels on the 0–255 scale. This bounded tolerance omits thin
red/blue edge differences without a changed-area or page-percentage cutoff:
even a single isolated pixel above that contrast bound remains a change if
there is no matching nearby ink. Added/removed pages and page-size changes are
always included, even when blank. The exact rule and parameters are recorded
in `summary.json` and explained in the HTML index.

The one-pixel bound is 0.176 mm per axis on the printed page. Ink movement or
thickness changes within that bound and contrast changes of at most 68 levels
can be missed, including embedded-image shading and regenerated break lines.
Gaps or bridges up to two pixels (0.35 mm) and pattern changes inside dense ink
can also be missed when every changed pixel is near existing ink.
Printed-character inventory changes disable both tolerances; the inventory is
a visible-character multiset, not a semantic check of text order or placement.
This is a visual triage aid, not proof of manufacturing/CAD equivalence. The
v42/v43 knob-cup page 1 and cone-gear page 18 calibration required at most 68
and 51 unmatched grayscale levels with a one-pixel neighborhood; increasing
the radius to two pixels still required 52 and 51 levels. The smaller spatial
bound avoids doubling the displacement blind spot. The drawing ZIP is
staged beside `cad/out/release/harmonic-analyzer-vNN.zip`, not inside it, leaving
the main bundle's provenance/integrity contract unchanged. `--no-publish`
prepares the same drawing ZIP and reports its path and notes without uploading
anything.

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
`"-Tag", "full-build"`. The release manager uses it for rolling-main validation
and release qualification. A miss on any changed part or drawing cascades into
the top assembly, its drawing and its soundness gate, the slowest leaves on the
farm, so authors iterate on the touched leaves only. An individual PR or stack
does not need this full closure to merge. Do not `hub stop` a live launcher to
quiet the console;
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
no `.done`. Liveness uses native `System.Diagnostics.Process` PID lookup and
`StartTime`, not WMI. An absent PID or a creation time at or after the recorded
run start is not the launcher; inability to read the process identity remains
an error (exit 2), never evidence of launcher death. Thus `-Status`, `-Watch`
and `-List` keep working for a live launcher during WMI query failures when
native identity is readable. A process that exits between PID lookup and
creation-time inspection is treated as absent.

`-Cancel` and a dead launcher's orphan reporting still use `Win32_Process`
CIM queries for descendant ownership. A transient WMI fault (`Call cancelled`,
shutting down, transport or RPC failure, quota violation, retry later) is
retried up to four times over about 4 s, each retry a `WARNING:` line on stderr.
A persistent or other query fault ends that operation with exit 2 and the
CIM error, not a successful outcome.

The Windows launcher tests separate hermetic retry contracts from real
process-tree integration: `test_win32_process_preserves_cim_retry_contract`
executes the parsed production wrapper against synthetic transient failures,
then deterministic rows/empty success or persistent failure; a separate synthetic
dead-launcher status test preserves the full exit-2 fail-closed contract. Orphan
fixtures record their parent's own PID and wait for an explicit socket release;
they do not need a CIM lookup or expire during slow test startup. Cleanup waits
on a handle whose creation time matches the one the spawning parent read from its
own child handle; only that pinned handle is ever terminated, never a PID Windows
may have reused. Ownership and
cancellation integration (including some setup) still queries the real WMI
provider. Persistent provider failures remain test failures, not skips or proof
that ownership is empty (see
[#1617](https://github.com/pedropaulovc/harmonic-analyzer/issues/1617)).

If the final run-record refresh fails, the launcher still writes `.done` with
the actual build outcome and reports the refresh error in `cleanup_errors`.
It keeps the snapshot and records its output path instead of authorizing cleanup
from stale identity data. Corrupt or conflicting metadata may still make
`-Status` refuse the record; repair that metadata before using it for cancellation.

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
  `HARMONIC_FARM_REQUESTS` to that directory. The parent writes `build.json`
  with `{build_id, farm_run}`; `_farm._dispatch` atomically writes one
  `{task, workflow_id, build_id, farm_run, refresh_reason}` file before submitting a reservation
  (a failed write fails the leaf before submission). Status also reports
  `build_id`, recovered from durable registration metadata or the registration
  log and persisted in the run record. Native IDs encode their exact build
  scope and task directly; task parsing never needs registration metadata.
  Before registration, a run has no `build_id` or native leaves and remains
  inspectable. Stopping the launcher can drop a logged request line but cannot
  erase the durable request.
- **`-Watch`** is the required watcher for an agent-launched build. It prints a
  line per leaf state change (`requested`, `attached`, `succeeded`, `failed`,
  each with its workflow id — follow one leaf with `farm.py watch <id>`) and per
  new `TaskError` with the exception that ended it, polling every
  `-PollSeconds` (15). It exits when the run is terminal, ending with the
  final `-Status` object: **0** succeeded, **20** failed, **21** launcher-died
  (`LAUNCHER DIED` on the summary line), **22** cancelled. Run it under the
  same kind of persistent supervisor as the launch, with `progress: "wake"`.
- **`-List`** prints one JSON line per run, newest first, filtered by `-Tag`,
  `-State` and `-MaxAgeHours`.
- **`-Cancel -Why <reason>`** stops the launcher and every process it started,
  including a build a dead launcher left behind. The launcher joins a named
  Windows job object (`job` in the run record) before it starts anything, so
  every descendant is a member whichever of its ancestors died: `uv run` does
  not take its python with it, and a build whose launcher and uv are both gone
  has no parent chain back to the run. The job's name lives while a process
  holds a handle to it; the launcher's handle is inheritable, so uv, the venv
  python and the build each hold one. A process under a dead launcher's PID
  counts only if its command line names the run: the recorded build command,
  the run's snapshot — git worktree add/remove, submodule update, uv sync —
  or its private uv staging environment.
  It rescans until a scan finds no process started since the last (at most
  10 rounds, else an error). Each process is stopped through a handle whose
  start time matches the scan's, so a PID reused after the scan is never
  killed, and a stopped process still running 60 s later is an error, since it
  may still be dispatching. It then closes registered producer ownership
  with `farm.py close-build <build_id> --reason cancelled`, blocking new
  admissions while retaining accepted reservations. It reconciles each request
  with `farm.py leaf-status --build-id <id> --workflow-id <wf> --json`.
  Reserved work is polled for at most `-BindingWaitSeconds` (30 by default;
  0 performs one query). A still-pending accepted reservation is `unresolved`,
  not absent; the request and snapshot remain for a later `-Cancel`, and the
  reservation's physical-drain obligation remains fenced. A typed `recovery_required` or `error_code` response
  stops reconciliation immediately and calls for operator recovery.
  Status and cancellation of a bound leaf use `--run-id <run>` so a later
  execution with the same canonical workflow ID cannot be cancelled by mistake.

  Cancellation trusts the validated coordinator binding for the owning build
  and cancels only that exact run; `farm_run` is launcher metadata, never an
  ownership or shared-execution gate. There is no legacy shared-ID cancellation
  path. A run stopped before registration has no native work to reconcile.

  The typed `missing_closed` coordinator reply is `settled-untracked`: producer
  ownership is fenced closed and no retained reservation remains to reconcile.
  This includes both never-accepted requests and accepted, physically drained
  history later pruned; it does not establish whether a leaf was ever submitted
  or executed. No workflow status or cancellation is inferred from the canonical
  ID. An operator-confirmed, unbound `drained` reservation is
  `already-closed`. A fresh unknown reservation, failed query, exhausted binding
  wait or missing exact bound execution remains `unresolved`: cancellation exits
  1 without writing `.done` or cleaning the snapshot. Retry the same command; do
  not erase the request or infer drain from error text.
  A successful remote cancellation still does not prove native worker cleanup:
  capacity reassignment waits for the worker's physical-drain acknowledgement.
  If any leaf cannot be accounted for (`farm.py` failed on
  authentication, network or CLI), `-Cancel` exits 1 and changes nothing
  else: no `.done`, the snapshot kept, the run still `launcher-died`. Retry the
  same command. Otherwise it does the cleanup the launcher never ran —
  outputs moved to `<run-id>.out`, snapshot removed — and writes `.done` with
  `state: "cancelled"`, `exit_code: null` and a `cancel` block recording who,
  why, the stopped PIDs and each workflow's outcome (`cancelled`,
  `already-closed`, `settled-untracked`). An unresolved or failed reconciliation
  is reported without authorizing cleanup. A cleanup
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

Use `-Status -RunId <run-id>` or `-Watch -RunId <run-id>` on the recorded
protocol-7 run:

1. **`running`.** Keep watching. Do not start another submitter for this work.
2. **`succeeded`, `failed` or `cancelled`.** This is the local launcher's
   outcome. Diagnose failures from `task_errors` and the log. A failed or
   cancelled submitter can still have accepted remote reservations to settle.
3. **`launcher-died`** (watch exit 21). The launcher wrote no `.done`, so its
   local outcome is unknown. Accepted remote work is not cancelled by losing
   the submitter, and `launcher.orphaned_processes` may name local children
   that can still dispatch. This is not permission to relaunch.

Before recovery, stop any record-attributed local producer/orphans and close
its producer lease so no new reservations can appear. The supervised
`-Cancel -RunId <run-id> -Why …` path does this and reconciles recorded native
reservations through the coordinator's exact-run bindings. Its success proves
local stop, producer close and exact-run reconciliation, **not physical drain**.
It can write `.done` and remove the local snapshot while remote attempt fences
persist. Invalid identities or unresolved bindings can block that cleanup;
unconfirmed physical attempts always block relaunch, not necessarily cleanup.

Account for **every recorded native reservation**, not one representative and
not only the `unsettled_workflows` subset. Use the run's `build_id` and each
workflow ID from `leaves` and the durable request records. Resolve the
reservation before querying its execution:

```powershell
# After stopping the record-attributed local producer, close its lease:
uv run --frozen --project C:/src/solidworks-pool C:/src/solidworks-pool/farm.py close-build "<build-id>" --reason cancelled
uv run --frozen --project C:/src/solidworks-pool C:/src/solidworks-pool/farm.py leaf-status --build-id "<build-id>" --workflow-id "<workflow-id>" --json
# Only after leaf-status supplies the immutable binding.run_id:
uv run --frozen --project C:/src/solidworks-pool C:/src/solidworks-pool/farm.py status --run-id "<bound-run-id>" "<workflow-id>" --json
# Optional progress monitor; watch has no --run-id option:
uv run --frozen --project C:/src/solidworks-pool C:/src/solidworks-pool/farm.py watch "<workflow-id>"
```

Follow each exact bound execution under a supervised monitor until terminal,
then query `leaf-status` again for coordinator-confirmed physical settlement.
Neither terminal workflow status nor a successful `-Cancel` proves drain.
For **every recorded reservation**, require `state: "drained"` or the
authoritative `state: "missing_closed"`, with **empty `unconfirmed_attempts`**
in either case (`missing_closed` also has no binding). Any unknown binding,
recovery-required state, unconfirmed physical
attempt, unreadable record, or authentication/network/CLI failure remains
unresolved. `NOT_FOUND` is **never** proof of absence or drain, whether the log
says requested or attached; there is no relaunch exception for that result.

Only after all recorded reservations are settled may you launch again.
Every relaunch registers a **new build ID** and therefore creates distinct
native workflow executions, even with the same commit, task, cache key and
timeout. It reuses published cache artifacts, **not running executions**.
There is no cross-build rejoin or sibling-sharing guarantee.

Recover inputs from the *run record*, not the caller's current worktree: its
recorded `commit`, `targets`, `leaf_timeout_minutes` and `cache_environment`
describe what was launched. Point `-Worktree` at a clean checkout of that
commit (the retained snapshot or a fresh checkout), use the recorded targets
and leaf budget, and set or unset `HARMONIC_CACHE_ACCOUNT`/`CONTAINER`/`SALT`
to match. Supply `-DisplayName` for the recovering session's owner and reason.
Unchanged inputs permit cache restores; a miss executes under the new build's
identity, not an old workflow's binding.

A dead launcher's outputs may still be in `<snapshot>\cad\out`, named by
`status.outputs`. Preserve required artifacts before local cleanup. A successful
`-Cancel` can perform the recorded cleanup before remote fences clear, so keep
checking coordinator settlement before relaunch. If manual cleanup is needed,
especially after an invalid remote identity makes `-Cancel` exit 2 without
automatic cleanup, first confirm **all** recorded reservations settled as
above and copy any required `cad\out` artifacts. Then, from another checkout:

```powershell
git worktree remove --force <snapshot>
git worktree prune
```

Old native workflow-ID formats are unsupported by this launcher: finish or cancel
those runs with matching old tools before changing tools. Protocol 6 to 7 keeps
the ID format, but deployment still requires the coordinated, idle, physically
drained wire-protocol cutover described above.

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

Pure physical part specifications keep interface grades and tooth/hole datum
geometry independent of calibration publication. They must not import a
qualification gate even inside a function: recipe dependencies include the
complete lexical import closure. `transgear_cluster_fit` reads the geometry-owned
`pd_transgear_arm_plate_geometry.HUB_FACE_TO_MOUNTING_BAND`, derived from
`HUB_STATION_PLACES = 3` through the existing `printed_band_mm` title-block reader,
not the annotation-rich plate specification or the `ARM.BAND_XXX` wall-band
literal. The plate specification consumes that same geometry-owned precision,
without a public alias. `dt_crank_pinion_spec` and `dt_crankshaft_spec`
therefore supply physical data without pulling cone/crank qualification into PD
interface consumers. `crank_mesh_stack.require_selected_pin_clocking()` owns the
current-source phase gate; native crankshaft and DT assembly callers retain it
before any adapter action.

The cone native factory reads only the source-qualified ALL20 packet
`cad/calibration/dt-cone-stock-form.json`; absent, stale, partial, stationary
DESIGN or numerically refused data cannot fall back to an ideal profile.
Retained seat/AF/face/cutter/grade inputs have a separate identity from selected
OUTPUT geometry, so publishing the authentic JSON does not circularly change
the measurement input. A packet becomes a declared per-file recipe and
farm-package input only when its genuine JSON and its CAD-relative entry in
`_buildgraph.REGISTERED_CALIBRATION_INPUTS` are committed together. The production
registration is currently empty: neither the cone nor crank packet is published.
Do not declare absent packets in check/part/assembly/drawing inputs or supply
placeholder JSON. Registered inputs remain dependencies if deleted; native,
budget and direct packet readers continue to refuse missing or unqualified data.
Numerical qualification requires the actual six-source engine receipt, whole
booked source domain,
nominal plus all sixteen printed-profile pairs, continuous first-contact/
handover and paid full-period seam proof, actual RootArc FREE INNER air and
untared physical signed reads. Cone driver-root/full-drum material clearance
retains .02 mm; directed drum-root/full-cone MATERIAL clearance retains .10 mm.
Both complete finite-material receipts must cover the same source/phase and
physical driven approach. First-contact surface exclusions or RootMAX disks
cannot substitute for caps, volume or containment.
The stock-phase reference is the actual selected 3D q0 root at all 21 stalls
after physical `OPERATING_NOTCH_UP` setup, not a planar recomputation or a
subtracted saved-CAD bias. Its paid CLOCK-subdomain/whole-phase envelopes
retain all seventeen profile cases; crank ideal advance is added separately.
Each `actual_read_phases` record is a direct query at the requested physical
driver angle, with the genuine reference root, centre-point enclosure and
numerical bound; a periodic endpoint cannot supply that point observation.
Whole-period cells retain correlated same-source upper-minus-lower root
differences. SOURCE inspection backlash scales that proved angular interval
by the retained inspection radius; its separate physical pitch arc uses the
actual driven pitch radius, never independent root-interval subtraction.
The whole-period signed envelope is the canonical all-cell, both-sided seam
receipt, not an independently rebuilt hull of uncertified rows. The CLOCK
subdomain excludes exactly `cone_flat_free_clock`, `BoreFlatClock` and
`drum_tooth_to_cam_notch_clock`; those three independently paid phase terms
remain in the full production SOURCE domain. The drum pattern-to-CAM-notch
term is paid at every read, including the initial zero, without datum removal.
Its native `PatternNotchPhase@NotchProfile` is a separate driven 90-degree
BASIC locator from the actual seed-gap ray to the existing kerf axis. It does
not alter the lobe-to-kerf `NotchPhase` or its .25-degree cam-phase tolerance.
The drawing reads the published pattern-clock grade lazily and prints a
separate critical angular-error callout; no grade is inferred from a general
angle tolerance. The .02-degree shop candidate may be drawn only after actual
budget admission. An UNKNOWN or tighter admissible grade refuses production
drawing issuance; report the tighter value instead of publishing the candidate.
Only the unconditional `FULL_PRODUCTION_SOURCE_DOMAIN` with
`production_source_domain=true` and functional `production_source_qualified`
reports can supply the native full-source gate. A conditional installed-grade
DESIGN cannot be promoted. Mathematical `DESIGN_NOMINAL_SUBDOMAIN` q0 and
`BUDGET_CLOCK_NOMINAL_SUBDOMAIN` receipts deliberately retain
`production_source_domain=false`; their independent supplier-bound
`source_domain_proved` evidence serves only those stock-phase roles. Missing
own cone/drum receiving grades remain UNKNOWN, not zero/default allowances.
The parent authenticates deployed diagnostic bytes; native leaves validate
the frozen receipt and current pure geometry without importing those engines.
`native_certificate=false` permits the first native farm observation; it is
not native acceptance, numerical success or a waived publication gate.

### Swing-cluster gravity calibration

After the farm finishes, the maintained, SolidWorks-free collector reads seven
native STLs (nine placed instances), never imports builders or COM, and never
writes into the source tree:

```powershell
uv run --frozen python cad/scripts/diagnostics/collect_dt_swing_gravity.py --outroot C:/src/dt-logs/farm-runs/20261010T084710772Z-bcad1a8e9e664595b56e918f9cc4f1e4.out --source-root C:/src/ha-swing-0d454 --report C:/src/dt-logs/swing-gravity-r15.json
```

For subsequent calibrations, substitute the completed run and its matching source
tree. STL has no units or commit metadata: the collector checks the source
exporter's enforced **mm / preserved part-local origin** settings and reports
source/mesh SHA-256 hashes, but cannot prove those sources generated those bytes.
The example artifacts were built at `0d454fa91c238af5be268fa7733def9e003b30e6`,
checked out detached as the source root;
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
a full assembly ~500 s. Hashed inputs identify reusable geometry, not necessarily
identical native bytes. A shared cache lets one machine **download a
prebuilt `.SLDPRT`/`.SLDASM`/`.SLDDRW`/`.STL`/`.PDF`** for an unchanged input set
instead of
driving SolidWorks. A seat-less machine can pull; a builder pulls **and**
publishes. Implementation: `cad/scripts/_artifact_cache.py`.

**Canonical first-writer publication (#1428).** An ordinary publisher creates only
if the key is absent. Both single-upload and staged-block commits are conditional;
they attach `archive_sha256`, `archive_size` and `epoch` metadata atomically with
the archive. Downloads validate hash/size/epoch from the SDK response properties
before unpacking (the SDK pins the initial ETag across ranged downloads).

After any upload error, including an ambiguous timeout or `InvalidBlockList`,
a present canonical entry means `lost`, not `stored`. The action must restore the
entire winning archive before succeeding. Restore validates all archive paths and
inventoried replacement targets, then stages the complete payload before deleting
anything. It replaces only inventoried files/directories (including optional
outputs absent from the winner and loser-only directory members), never their
shared parents or unrelated siblings. Winner-only dynamically discovered files
are still installed without expanding recursive deletion to archive-supplied
directories. Native adoption takes the COM seat and uses the existing
release-once/reprobe recovery for deletion or installation locks; unavailable,
still-locked or hash-invalid canonical bytes are fatal. Replacement is not a
multi-output transaction: a later lock may leave partial outputs, but never a
successful cache HIT. Part and assembly execution tokens are
re-stamped; assembly input ledgers are rewritten. Drawing/generic COM bundles
adopt all archived outputs, and machinist review re-reads the winning aggregate
before enforcing/stamping it. LEARN softens machinist verdicts, not adoption
failures: inability to clean/restore/read winning evidence is fatal even in LEARN.
Ordinary explode-base alias loss is ignored without adopting it over the current
full-key outputs. An ordinary upload failure with no canonical entry remains
fail-soft; `ro` and `off` contracts are unchanged.

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

Each `key_inputs` call resolves each dependency's path tag once and reuses it
for sorting and provenance, while digesting the original path. Equal tags retain
input order, including duplicates. Resolution is fresh between calls: there is
no global path cache. This does not promise an atomic filesystem snapshot if an
alias changes between tag resolution and content digesting.

YAML digest checks read fresh file bytes on every call, then reuse the canonical
MD5 through a process-local, 256-entry `lru_cache` keyed only by those bytes.
There is no path, stat, or mtime cache; parsed values are not retained. YAML
canonicalization and exact cache-key identities remain unchanged. The controlled
comparison for [#1621](https://github.com/pedropaulovc/harmonic-analyzer/issues/1621)
matched all 225 tracked YAML digests and all 419 available API key/input sets
across three repetitions. Of those key sets, 235 had missing native prerequisites
and do not establish full live-artifact parity. The candidate recorded 225 misses
and 9,744 hits (97.74%); this is digest-reuse evidence, not a whole-build speedup
claim. See the [measurement details](https://github.com/pedropaulovc/harmonic-analyzer/pull/1626#issuecomment-6244324157).

Assembly and drawing keys also include SHA-256 identity tokens for the exact CAD
artifacts they reference. SolidWorks persistent-reference IDs and persisted
rebuild stamps may differ between two same-recipe builds, so a recipe key alone
is unsafe for an assembly or drawing. Restoring the same cached dependency
reproduces the same identity token and can restore its matched downstream output
with no COM work; another artifact misses and rebuilds/refreshes once. Assembly
tokens propagate the guarantee through subassembly levels to the top model.

Drawing recipes include the selected `_drawing_registry.py` row and the shared
registry implementation, recorded under `cad/out/.drawing-registry/`. The row
schema (`DrawingSpec`, `DrawingLayout`), `DRAWING_TEMPLATES` and
`layout_report_path` live in `_drawing_types.py`: shared drawing helpers import
that module and never the row table, and only draw scripts read their own row
as `DRAWINGS_BY_NAME["<own name>"]`. Adding or editing another row does not
invalidate an independent drawing; `check:recipe` pins this for every drawing.
Shared helper, template, schema and source-model identity changes still
invalidate it. Consumers that read other rows or use an unclassified registry
access retain the full registry dependency.

Assembly contracts narrow the same way for drawings: a drawing folds only the
`cad/config/assemblies/<stem>.yaml` files its closure names as
`assembly_contract("<literal stem>")` (`_buildgraph.assembly_contract_reads`),
so a new kit's contract re-keys no unrelated sheet. A closure that passes a
runtime stem keeps the whole family: today the top-level assembly drawing (its
BOM reads every component's number in a loop) and the paper-drive assembly
drawing (its explode module reaches `_assembly`).

Switching to these per-drawing dependencies changes existing drawing cache keys
once. It does not reuse legacy keys; subsequent unrelated row changes stay
isolated. A scoped drawing build need not regenerate the rest of the fleet.

Feature declarations remain colocated in `draw_<stem>.py`. Static AST discovery
and source-path construction do not import those modules while loading the task
graph, but each `package:features:<stem>` source key includes its **entire own draw-module
closure**, not just declaration expressions. An own-draw edit re-keys only that
feature leaf; shared `_drawing_common`, layout-audit, `_pdf_ink` and drawing-helper
edits re-key all 18 enrolled feature leaves, not native part/assembly recipes.
Full `export` waits for scoped bundles, validates them and copies their exact
STEP bytes; its recipe consumes bundle outputs rather than draw closures
directly. An opt-in `prechips:<stem>` depends only on its own feature leaf.
Feature leaves retain `uptodate: [False]`, so every invocation reaches the cache
probe even if local manifest and STEP targets exist. `cache_status` reports
individual `package:features:<stem>` keys, not an aggregate `package:features` COM key.
See [drawing requirements and travelers](cad/docs/pipeline/features-travelers.md)
for sourced precision, printed-literal authority and explicit descriptor consumption.
The declaration migration's spec edits cause a one-time native part/assembly
re-key; moving the unchanged dimension mover into `_drawing_common` causes a
one-time shared drawing re-key. Account for these in the release farm build,
separately from the ongoing feature-leaf coupling above.

GD&T consumers import focused modules directly: `_gtol_identity` names PMI,
`_gtol_symbols` defines symbols and zones, `_gtol_frame` handles frame signatures
and XML, and `_gtol_controls` validates datum/control declarations. Face selectors
live in `_gtol_cylinder`, `_gtol_cone`, `_gtol_planar`, `_gtol_sphere` and
`_gtol_torus`; `_gtol_face` holds their shared protocol and geometry contract.
COM geometry reads and face traversal live separately in `_gtol_face_read` and
`_gtol_face_resolve`. There is no aggregate facade: the dependency graph counts
every import, including `TYPE_CHECKING`, at file granularity. This keeps edits to
one selector or frame representation out of unrelated spec/cache closures while
still invalidating every consumer of the changed module.

Drawing recipes follow the same direct-import rule. `_drawing_common` holds the
universal session, document-policy, export and finalization core, summary stamping
and the adapter's process-global center-mark observer registration. Specialized
authoring lives in `_drawing_notes`, `_drawing_leader_notes`, `_drawing_gdt`,
`_drawing_finish`, `_drawing_sections`, `_drawing_centerline`,
`_drawing_hole_callout`, `_drawing_dimension_import`, `_drawing_dimensions`,
`_drawing_edge_dimensions`, `_drawing_tables` and `_drawing_balloons`.
`move_model_dimension` belongs to `_drawing_dimensions`; drawing scripts import
dimension-transfer helpers there, never from another part's drawing module.
Hole-callout selection probes live in `_drawing_hole_callout`; annotation style
and attachment assertions in `_drawing_attachment`; GD&T layout and element
collection in `_drawing_layout_collect`. Selection, projection, visible edges,
view configurations and sheet creation have separate helpers too. Hidden-line
policy lives in `_drawing_view_display`. Import the concern that owns the
operation, never an aggregate facade.

Local Python dependencies are file-granular, including imports inside functions.
Stock fastener metadata therefore lives beside each diagnostic SKU callable
(`_stock_recipe.stock_recipe`), and each production builder statically imports
only its recipe. Threaded builders explicitly supply the `_simplified_part` save
callback; unthreaded builds do not depend on simplified-configuration derivation.
Simplified naming, assembly-component fingerprints, shared pure BOM identity and
part-side configuration saves live in separate helpers. Vendor dimensions are
pure per-SKU inputs shared by the recipe and its specs, rather than dimensions
imported through recipe code or a family-wide table.
The catalogue-only 91251A108 and former-hanger 91251A157 socket-head diagnostic
recipes share the pure `_socket_head_dimensions` record; each SKU still owns
its `DIMS` declaration. The current knife-hanger hex-bolt, #10 washer and
knife-mount-dowel specs import their own pure per-SKU `DIMS`, not a socket-head,
washer or dowel COM recipe. Production replays 92314A253 as modified stock:
retain the hex head, cut the under-head length to 46.70 ±0.15 mm and apply
the finished thread-tail and end-prep requirements, without new head-minimum
inspection. The ordinary hex head seats on its SAE washer on the frame's
whole faced top, 36.50 ±0.05 mm above the finished underside. The new
96659A104 washer supplies MHA-SM-VN-54 (category Number MHA-VN-060); it does not
revive the retired MHA-VN-026
washer. These inputs remain file-granular rather than depending on the
obsolete production socket-head hanger route.

The `file_dep` set for a COM task also folds the **`SolidworksMCP-python`
submodule** — the vendored COM adapter (`solidworks_mcp`) is imported at runtime
by `_session`/`_com`/`_assembly` (session access, COM binding, mate/plane/feature creation), so its source is a genuine
build input, yet it is an installed package, not a repo-local `_*.py` helper, so
`module_deps_of` never walked it (issue #144). The submodule digest helpers fold
repo-relative-tagged source content into gitignored synthetic dependencies under
`cad/out/reports/`. Parts exclude `assembly.py`, `motion.py` and `drawing.py`;
assemblies exclude `drawing.py`; drawing tasks include the whole tree. A pin
bump or dirty local edit changes only the tiers that include the affected source,
while SolidWorks-free `check:*` tasks stay off these digests. See
[the three-tier source rules](AGENTS.md#three-tier-submodule-digest-part-vs-assembly-vs-drawing).
`check:recipe` (`test_dodo_recipe.py`) guards the dependency construction.
Scoped `package:features:<stem>` and full neutral export use the assembly tier (whole
submodule minus `drawing.py`): face naming and `SaveAs3` do not call drawing-doc
helpers. This excludes only submodule drawing code, not the feature source
key's entire main-repo draw-module closure.

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
  every cacheable COM task (part, assembly, drawing, gate, `package:features:<stem>`,
  `export`, `package:release`) it prints `HIT`/`MISS` (a backend presence probe — a
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
  `store` / `store_lost` (canonical adoption required) / `store_skip` (ro seat) /
  `store_empty` / `store_error`,
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
  | where tostring(customDimensions["label"]) == "part:sm_vn_counter_spring"
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

**Vendor-part builds are actionable.** An actual vendor-part `part:` build (its
stem contains `_vn_`, such as `part:sm_vn_counter_spring` or
`part:ch_rocker_arm_tl_vn_oblique_rail_kit`) emits a
`!!` / OTel `WARN` immediately before its COM execution, with structured `label`
and `cache.key` (the 12-character prefix shared with phase spans and the console),
plus the full `key_full` for correlation with cache events and recipe manifests.
This happens on a local seat or the farm worker, not on the submitter's dispatch,
a cache probe, a miss that becomes a hit while waiting for the seat, or
the matching `drawing:` task. Vendor-part rebuilds should be rare: compare the recorded cache
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

The published cache backend shares its credential and reuses tokens across blob
clients for matching token requests. Refresh is singleflight per request identity
and starts five minutes before expiry (or at the token's earlier `refresh_on`
time). Backoff does not hold a lock or delay unrelated identities. Speculative
prewarm uses a private client and one acquisition attempt, without retry backoff.
An authenticated client can be published even if the warm HEAD reports a
storage-side error, avoiding a redundant token traversal; authentication failures
remain private. Failed or losing speculative clients and their credentials are
closed. The first real probe can proceed independently after its bounded wait.

Only transient credential unavailability is retried: at most three acquisition
attempts, with one- then two-second backoffs. Typed observations distinguish
unavailability caused by subprocess/network timeouts or transport failures from
missing configuration. Managed-identity endpoint discovery that has never
successfully supplied a token is unavailable, not a retryable transport outage:
an absent IMDS endpoint on a non-Azure host costs one traversal and no backoff.
After that managed-identity link has succeeded, transient outages can use the
bounded retry policy. First-fetch CLI invocation timeouts remain retryable.
Genuine authentication failures fail immediately.

Exhausted transient unavailability suppresses **additional retries** for that
request identity for 30 seconds, but never caches or replays an exception across
acquisitions. Concurrent callers joining the same in-flight acquisition share
its result or original exception through the singleflight future.
Every later acquisition still makes one fresh attempt, so a recovered credential
can immediately restore published artifacts, including after farm success.
Successful acquisition clears retry suppression; after the deadline, the full
bounded retry budget is available again.
Unhashable request options bypass token reuse without preventing acquisition.
Every retry emits a `cache.credential.retry` span event and warning when telemetry
is already loaded; a bare pool probe never imports/configures telemetry for this.
Structured observations identify each chain link, its outcome, exception,
immediate cause and matched transient cause types. The acquisition span records
the attempt count and whether retries were suppressed, with the remaining
suppression duration. No token, claims or raw exception message is recorded by
retry telemetry. Exhausted credential
failures retain their original exception and follow the existing restore/store
error path. In particular, a farm success still requires a successful restore of
the exact key: credential failure cannot make `cache_missing` pass.

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

### Local archive reuse and file-backed transfers

Workers and producers use the same `_artifact_cache.py` transfer path. Packing
writes a private temporary file; downloads use the Azure SDK's `readinto` on a
seekable file, then verify its complete SHA-256 and length before unpacking.
Large uploads read bounded blocks instead of slicing a whole in-memory archive.
Transfer concurrency remains **8**: `readall` was already parallel, so using
`readinto` is a memory/copy optimization, not itself a network-speed improvement.

Every restore starts with a GET bounded to **8 MiB**. Small archives complete in
that one request, without a preceding HEAD. The response's epoch, archive
SHA-256, total length and ETag establish the current canonical identity. For
archives larger than 8 MiB and no larger than the local store cap, a matching
`objects/<sha256>` file can supply the remaining bytes. A warm local hit still
pays for that first network prefix; it is not a zero-network restore.
`cache.archive` reports `archive_bytes`, `network_bytes`, `probe_bytes`,
`reused_bytes` and local outcomes. `cache.download` spans time the probe and
remaining network body separately; their `bytes`/`network_bytes` count network
payload, not the whole archive on a local hit. Failed transfers whose partial
body count is unknown are marked `network_bytes_known=false`. The enclosing
`cache.fetch` reports archive bytes and total fetch work; local-store operations
and verification have separate timing spans. `cache.download` and
`cache.upload` are archive transfers only: sidecar blobs (the shadow COM
recordings) use `cache.sidecar.download` / `cache.sidecar.upload` (`bytes`) and
`cache.sidecar.list` (`prefix`, `count`).
The archive summary keeps lookup and final outcomes, but no aggregate
`local_reason`: reasons belong to the phase-specific `cache.local_store` spans.
For example, a corrupt lookup retains its integrity reason without labeling
successful replacement persistence as corrupt.

Local objects are leaf-writable. Before copying, the reader checks that the
opened regular file has the authoritative expected length. Every reuse then
copies and hashes the complete object into a **process-owned temporary file**,
reading at most one byte past the expected length to detect growth. Unpacking
reads that same handle, not a reopened shared path. Corrupted objects are not
served, and a failed LRU timestamp touch cannot discard a verified copy.
On a local miss, the SDK continues the original response with ETag-pinned
parallel ranges; the completed temporary file must pass the same integrity
checks. There is no recipe-to-ETag mapping: a same-key refresh is resolved from
the current response metadata, not from previously cached recipe bytes.

“Process-owned” is not a security boundary against other processes running as
the same Windows principal, which can already modify `cad/out`. Likewise, the
path guards refuse observed aliases and misconfiguration; they do not isolate
the filesystem namespace from a hostile process with store-owner privileges.
Store ACLs must keep namespace replacement within the trusted seat principal.

`HARMONIC_ARCHIVE_CACHE_ROOT` selects only these allowlisted locations:

- **Producer default:** `%LOCALAPPDATA%/harmonic-analyzer/archive-cache/v1`.
- **Worker:** `C:/ProgramData/solidworks-pool/archive-cache/v1`, explicitly
  supplied by the worker/job runner.

An override must be exactly one of those roots, outside `REPO_ROOT`, with no
workspace overlap. Relative paths, aliases and UNC paths are refused for
**local-store access**, not for an otherwise valid remote restore. Without
either `LOCALAPPDATA` or an explicit approved root, local reuse is disabled;
file-backed remote transfers still work. Typed local-store refusals and local
filesystem I/O failures skip only the affected optional work. Diagnostics expose
the reason through `cache.local_store` outcomes; a verified remote result is
retained. Busy locks, corrupt objects and capacity skips are distinguishable
from a normal local miss. Azure/auth errors, remote integrity failures and
unrelated programming errors are not swallowed by this local-store policy;
forced-refresh publication requirements remain unchanged.

The new local store has a **16 GiB archive capacity**, separate from Azure
retention. It reserves room before writing a publication temp and uses explicit
mtime updates for LRU order. A host-local lock coordinates capacity admission
and eviction; cross-process object leases prevent eviction of active readers.
Each lock acquisition waits at most **50 ms** before skipping optional work.
These leases are exclusive. Single-leaf workers normally avoid contention, but
parallel producers can encounter a busy lookup and download the remaining
remote body again. Busy store or object locks can also skip local persistence.
This is an intentional bounded-wait tradeoff, not a guarantee that concurrent
producers share one body download.
If unleased objects cannot make enough room, persistence is skipped. Archives
larger than the cap are transferred without being retained locally.

Eviction runs on capacity admission, not on warm hits. It removes only regular
hash-named objects and recognized interrupted-publication temps inside this new
store, skipping aliased and nonregular entries without touching their targets.
Object leases use a fixed set of **256 shards** plus the store lock; stable
lease files are never unlinked, avoiding split-lock inode races.
A lease on one digest can conservatively skip another digest in the same shard.
Lookup and persistence report busy outcomes; eviction reports these skips as
`busy_entries`, separately from its aggregate `skipped_entries`, so contention
is distinguishable from a cold store.
Its `reason` distinguishes normal `admission` from `corrupt_replacement`.
Concurrent writers use unique temps and publish atomically. A writer finding an
already-present same-address object skips redundant persistence and eviction;
the next reader still verifies that object's bytes. Persistence copies the
already-verified process-owned download without a redundant second hash.
No source, native output, other cache directory or remote blob is deleted by
this local capacity policy.

### Busting the cache (salt / epoch)

The toolchain (SolidWorks major version, COM adapter) is **not** in any
`file_dep`, so a SW upgrade that changes geometry would otherwise serve a stale
hit. Mix-ins guard this:

- **`_DEFAULT_SALT`** (e.g. `sw2024-sp3`) — bump it in the **same commit** that
  adapts to a new SolidWorks version, so the cache busts in lockstep with the
  code. All seats must agree on the salt or they never share hits.
- **`_CACHE_EPOCH`** — bump to invalidate *every* entry pipeline-wide (e.g. a
  pack-format change).

**Epoch 4 cutover:** canonical publication and payload-integrity metadata invalidate
every leaf key once. There is no epoch-3 fallback or copy-warming; old unconditional
writers cannot overwrite epoch-4 entries. Use fresh snapshots rather than mixing
persistent pre-cutover native outputs with the new identity graph. This is a
pipeline-wide cold cutover, not a narrow drawing/render closure; cold native/full
build validation is a separately authorized operation.

### Refreshing one unchanged leaf

Use a forced refresh when the input key must stay unchanged but its cached result
must be deliberately replaced. It works under either executor:

```powershell
uv run --frozen python build.py --executor local `
  --force-cache-refresh part:pn_pen_rod `
  --force-cache-refresh-reason 'Owner - Re-evaluate unchanged-input result' `
  part:pn_pen_rod
```

For agent farm launches, pass `-ForceCacheRefresh @('part:pn_pen_rod')` and
`-ForceCacheRefreshReason 'Owner - Re-evaluate unchanged-input result'` to the
supervised launcher with the normal worktree, targets, display name and budget.
The launcher records `force_cache_refresh` and `force_cache_refresh_reason`.
Direct attended `build.py --executor farm` uses the same wrapper flags.
`--force-cache-refresh` is repeatable and accepts comma-separated labels; each
must be an exact remote-cache-keyed leaf in the selected task closure. A plain
stamped check, aggregator, traveler or gallery task is refused. The declaration
is the action's `@_cache.keyed_action` marker, so cache-keyed non-COM leaves
qualify without a prefix allowlist.
With doit `-s`/`--single`, refresh labels must be explicitly selected: dependency
tasks are not executed and therefore cannot be refreshed through a parent.

A reason is mandatory: nonblank single-line text, no controls or bidi-control
characters, valid Unicode, at most 160 code points (the display-name rules).
A reason without refresh labels is refused. Invalid reasons,
unknown/non-cached/out-of-closure labels and cache
mode other than `rw` exit 2 before any fleet query or action. The request is scoped
to this invocation, overriding doit freshness as well as both cache probes; every
dispatch of a listed label refreshes again. A successful execution must publish
(`store` returns `stored`), otherwise the task fails rather than swallowing an
upload failure. Refresh is the sole same-key replacement: the first intentional
refresh probe captures the entry's ETag or absence **before expensive work or seat
wait**. Under-seat re-probes and publication reuse it, never recapture it. Existing
entries replace only with that ETag; initially absent entries create only if still
absent. Any conflict/error fails the refresh loudly. This is not a salt change or
persistent invalidation.
For an assembly, refresh reruns the full recipe and its hooks rather than reloading
the previous local target; an unchanged sidecar must not republish suspect bytes.
For an explode-qualified root assembly, refresh also snapshots its base alias before
work, then CAS-publishes the alias after root publication. A conflict/error on either
is fatal. **Root + alias are not an atomic pair:** alias failure may leave a new
root with the old alias. Other already-published explode-variant full keys are not
replaced. Concurrent consumers can fail strict `cache_missing` if an identity was
replaced; the requested-key contract is unchanged and never substitutes other keys.
Every new process/redispatch captures its own first snapshot. Overlapping stale
or zombie attempts fail CAS loudly when their precondition changes.

`HARMONIC_CACHE_REFRESH` carries compact JSON `{"labels":["part:pn_pen_rod"],
"reason":"Owner - Re-evaluate unchanged-input result"}` during the submitter run.
The protocol-7 `LeafRequest.refresh_reason` carries only the matching task's
reason; its worker injects a one-label carrier only into that leaf process.
Workflow IDs are unchanged. The submitter's post-success download still restores
the just-published bytes. Each bypassed probe emits a `!!` warning with label,
12-hex key and reason, a `cache.refresh` span event with `label`, `key`, `reason`,
and a `refresh` record in `cad/out/reports/cache.jsonl` carrying the same reason.

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

## COM conversation recording (shadow)

Every part build that runs (a cache miss or a forced refresh, on a local seat or
a farm leaf) under a cache role that can publish (`rw`) is recorded, and the
recording is replayed in the shadow of the build. In `ro` or `off` a part builds
exactly as unrecorded (`_replay_shadow.plan`): a recording nobody can publish
would be pure cost. In the default mode, `reuse`, a part whose key misses is
first replayed, with SolidWorks absent, against the nearest earlier real
build's recording bound to its archive; when that proves the current source
issues the same conversation, the earlier archive becomes this key's outputs
and no COM runs ("Reuse" below). Every other build is recorded and judged
exactly as in `shadow` mode, where nothing is reused: every output, exit code
and cache key is what an unrecorded build produces.

### What is recorded

`_cached_part_action` runs the part script through
`cad/scripts/com_replay.py record` instead of directly: the same script as
`__main__` (same `argv[0]` and `sys.path[0]`), on the same seat, under the same
seat lock, trace, log tee and exit codes. The recorder
(`_com_conversation.py`) logs every request and response crossing pywin32's
`_oleobj_` boundary, plus the files SolidWorks wrote, into
`cad/out/replay/<stem>/`:

| file | content |
| --- | --- |
| `conversation.jsonl.gz` | the request/response log |
| `conversation.jsonl.gz.files/` | gzip captures of the files SolidWorks saved, flat as `000000.gz`, `000001.gz`, ...; the log's trailer maps each to its call, output path, SHA-256 and size |
| `summary.json` | exit code, faults (with `recovery`), engine SHA-256, request counts, engine and audit clock |
| `shadow.json`, `shadow-replay.log`, `shadow-diff.log` | the last shadow evaluation (`shadow` and `reuse` modes; in `reuse` the replay log is the pre-build replay's) |
| `reuse.json`, `shadow-replay.log` | a reused build instead of the files above: the reuse record (as in `cache.jsonl`) and its replay's log |

Captures never mirror the output's own path: the recording directory is
deeper than `cad/out`, and on 2026-11-10 a mirrored capture of a PNG's
`.capture.bmp` reached 271 characters on a farm worker, past Windows' 260
(workers and SolidWorks have no long-path support). Every path a recording
and its shadow replay create is budgeted (`_replay_shadow.path_needs`);
`test_every_part_recording_fits_the_windows_path_limit` checks every part
under the farm's checkout root and requires 32 characters of headroom (41 at
worst today), and a
checkout too deep for a recording's own paths builds unrecorded with a WARN.

Every COM subprocess (`dodo._exec_com`: the recording driver, its unrecorded
re-run, an unrecorded part build, and assembly, drawing and hook runs) hashes
str with `PYTHONHASHSEED=0` (`dodo._COM_ENV_PINS`, applied over any inherited
value). Under per-process hash randomisation, a build that orders COM
requests by iterating a set of str issues them in another order from build to
build: on 2026-11-11, 5 of 10 identical-source part rebuilds diverged on
`_drawing_precision._named_dimensions` and
`_supplier_spring_reference.add_supplier_reference_configurations`. Since
#2514 those, `_drawing_precision.apply_drawing_precision` (specs build
`DRAWING_PRECISION` from sets),
`_supplier_washer_model.assert_supplier_washer_references`,
`_assembly_patterns.assert_pattern_targets` and `build_pd_platen_rack`'s
reference-dimension loop iterate sorted names, and since #2655 so does the
vendored `sw_type_info.flag_methods` (one `GetIDsOfNames` request per method,
reached through `_com._flag`, `segment_point_objects` and
`dimension_full_name`). The pin stays: the seed is a process input the replay
pins. It re-keys nothing, since `dodo.py` is in no recipe closure. The seed is
in the log's environment. A replay runs with the fresh recording's
environment and refuses (`input_mismatch`) a base recorded under another seed
or none.

SolidWorks also hands back a component enumeration
(`IAssemblyDoc.GetComponents`, `IComponent2.GetChildren`,
`IView.GetVisibleComponents`, `IView.GetVisibleDrawingComponents`,
`IDrawingComponent.GetChildren`, `IBomTableAnnotation.GetComponents2`) in an
order that varies between builds, even on one seat (#2686: three orders of
`ms_measuring_stick`'s six components in three builds, two on one seat). A
loop that follows it asks different questions in a different order whenever
what it asks depends on the component (a per-path cache, a filter, a
conditional write, a first match), and an assembly drawing whose balloon
anchor search walks the view's components that way prints differently. So
every assembly-, drawing- and verify-tier loop over one iterates
`_component_order.by_name` (or `drawing_components_by_name`) on the
enumeration's result: each element is bound and its name read in the order
given, one bind and one read each and nothing else, then visited in ascending
natural name order (`part-2` before `part-10`, a pattern seed before its
instances). The depth-first tree walks (balloon leaves, drawing visibility,
configuration instance paths, the complete machine's spare sprocket) stack
each level reversed, so they too visit siblings in ascending order.
Callers use the name it returns instead of reading it again, and an element
that is `None` or answers no name raises there: an unnamed component is never
skipped, labelled or ordered under a placeholder. Only those name reads'
answers follow the seat, and two seats' recordings pair their elements by
name; the recorder still numbers the elements' handles in the seat's order. A
loop that only collects names into a set is left as it is (its requests are
the same name reads), and a part drawing view's one visible component needs
no order (`_drawing_edges.visible_view_entities` sorts only an assembly
view's). Exempt: scripts no doit task runs (`build_motion_study`,
`build_mobility_probe`, `export_glb`, `diagnostics/`), and `_drawing_tables`'
failure evidence, whose `collect()` records a failed row's first native
component after the failure. `test_component_order.py` (`check:recipe`)
runs the Default Simplified pass over two enumeration orders and requires the
same requests, and requires an unnamed component to fail closed.

Gates are not recorded; FULL assembly builds and drawings are, and nothing of
theirs is reused ("Assemblies and drawings" below). Nothing under
`cad/out/replay` or `cad/out/rs` is a doit target, `file_dep` or cache-key
input, and the four modules (`_replay_shadow.py`, `_com_conversation.py`,
`_com_outcome.py`, `com_replay.py`) are in no recipe closure
(`test_recording_modules_stay_out_of_every_recipe_closure`,
`test_recordings_are_no_task_input_or_output`).

### The switch

`HARMONIC_COM_REPLAY` is read in one place (`_replay_shadow.mode`). It holds
comma-separated items, each a mode for every kind (`shadow`) or for one kind
(`part=`, `assembly=` or `drawing=`), a later item winning: `shadow,drawing=off`
shadows parts and assemblies and leaves drawings unrecorded. Unset or empty is
`_replay_shadow.DEFAULT_MODES`: parts `reuse`, assemblies and drawings `shadow`.
An assembly or drawing never runs above `shadow` (`reuse` shadows them). The
modes, for a part:

| value | effect |
| --- | --- |
| `reuse` (default, also unset or empty) | before the seat, try to reuse a real build's bound archive ("Reuse" below); otherwise as `shadow` |
| `shadow` | record, publish, then evaluate a shadow replay; nothing is reused (a forced refresh still revokes what it replaces) |
| `record` | record and publish; no lookup or replay (a forced refresh still revokes what it replaces) |
| `off` | the kill switch: the build runs the command it ran before recording existed, and the engine is never imported |

Anything else (an unknown mode or kind) is treated as `off` for every kind with
one warning. A farm leaf takes the mode from the worker's environment, not the
submitter's: environment variables are not forwarded to workers, so the fleet's
mode is the in-source default. To turn reuse off for the whole fleet without
touching workers, set `DEFAULT_MODES[BuildKind.PART]` in `_replay_shadow.py` to
`ReplayMode.SHADOW` (or a kind's entry to `ReplayMode.OFF` to stop recording
it) and launch from that commit; because the module is in no recipe closure, no
cache key moves. On one machine, `HARMONIC_COM_REPLAY=shadow` (or
`part=shadow`) does the same for local builds.

### Failure handling

A failure of the recorder's own code (never the script's or SolidWorks') is
classed by where it happened (`_com_conversation.Recovery`):

| site | recovery |
| --- | --- |
| keeping the files a call wrote, encoding its response, writing its log line (calls, adoptions, comparisons, hashes) | `degraded` |
| file-access accounting (the audit hook) | `degraded` |
| closing the recording window after the build | `degraded` |
| anything before or while the call is forwarded (request encoding, path accounting, argument preparation) | `rerun` |
| building the proxy of a returned object; applying a byref write-back | `rerun` |
| opening the recording window; reading the seat's revision | `rerun` |

- **`degraded`.** The real call has completed and the build has its result:
  recording stops there, the result is returned, and the build finishes
  through the pass-through recorder with its own exit code and outputs.
  The recording is unusable: `dodo` logs a WARN, adds a `replay.record_fault`
  event (`recovery=degraded`) to the task span and a `replay_record_fault`
  record to `cad/out/reports/cache.jsonl`, and publishes nothing. No re-run.
- **`rerun`.** The script's result cannot be guaranteed: the build aborts
  (`RecordFault`, which no `except Exception` can swallow) and the driver
  exits `92` (`EXIT_RECORD_FAULT`). `dodo._exec_com` reports it the same way
  (`recovery=rerun`), then re-runs the build **once, unrecorded**, on the same
  seat. That re-run's exit code is the task's.
- **Script or SolidWorks failure.** Exit codes, including the watchdog's 86–89,
  pass through the driver unchanged and get today's handling. This mechanism
  never retries them.
- **Observation.** Publication, lookup and replay run after the seat is
  released and the part archive is stored. Each is best-effort; none can fail
  the build or change an output.

### Publication and base selection

The recording is published beside the part archive as two create-only sidecar
blobs in the build cache container, named from the part key:

```text
com-replay/epoch-<cache epoch>/<engine sha[:16]>/<stem>/bundle/<part key>.tar      log + captures
com-replay/epoch-<cache epoch>/<engine sha[:16]>/<stem>/manifest/<part key>.json   manifest
```

The cache layer puts the epoch after the registered prefix
(`_artifact_cache._sidecar_blob`; callers name `com-replay/<engine>/...`), so
an epoch bump lists and fetches none of the older sidecars, which age out under
retention without a warning. Manifests and bundles live under sibling
prefixes, so the base lookup lists manifests only, every page of them, and
then takes the newest: no cut is ever made in the listing's name order.

The engine digest in the prefix is the SHA-256 of `_com_conversation.py`
alone (the log header's `engine`): changing that module starts a fresh set of
bases, since a replay refuses a log of another engine. The comparison of two
recordings (`_com_outcome`), the driver (`com_replay.py`) and `_replay_shadow`
are outside it and can change without retiring the published recordings.

The manifest holds the stem, key, per-input digests (the cache's
`key_inputs`), the cache salt and epoch (the two key inputs that are not
files), the engine SHA-256, the SolidWorks revision (`sw_revision`, the seat's
`RevisionNumber`) and file version (`sw_build`, `_replay_shadow.seat_build`:
the version resource of the `SLDWORKS.exe` that `SldWorks.Application`'s COM
registration starts, read from the registry without starting SolidWorks),
request counts, the bundle's SHA-256, and `archive`: the SHA-256 and size of
the archive this very process committed under the key
(`_artifact_cache.publication`). Only a build that stored the key's archive
publishes its recording: one whose store lost the race made none of the key's
archive, so its recording describes another build's part (`publish=lost`),
and one whose store failed or stored nothing publishes nothing either
(`publish` is then the store's outcome, or `unstored`). Every manifest a build
publishes is therefore bound; those published before binding existed are
unbound (`archive` null), which shadow lookups use and reuse never does. A
reused key publishes no recording at all ("Reuse" below). The bundle is
published first; only the writer whose bundle was stored then writes the
manifest. A bundle that already `exists` is another writer's bytes, which
this manifest's digest and counts do not describe, so that publication ends
at the bundle (`publish=exists`). Failing to publish is a soft outcome. If an
input changed while the part built, the inputs no longer match the key and
nothing is published. Sidecars follow the container's 7-day last-access
retention.

Known limit: a lookup reads up to 8 manifests and downloads at most one
bundle, so a manifest's last access stays fresher than its bundle's and it can
outlive it. A base whose bundle has expired yields `unavailable` (class
`infrastructure`). The reuse lookup applies the same bound of 8 newest
manifests before filtering for a real build's bound recording under this salt,
so legacy or other-salt manifests can crowd every bound base out of it
(`no_bound_base`).

In `shadow` mode, the base is the earlier recording of the same stem and engine
with the fewest differing key inputs; a tie goes to the newest. A base recorded
under another cache salt differs by one more input, `(cache salt)` (class
`salt`); the salt is never a filter, so a build under a throwaway salt still
finds the recordings made under another. The SolidWorks revision is not a
selection criterion: the replay refuses a base of another revision (below). The
lookup makes one listing and at most 8 manifest reads, newest first, within
3 s. Past that budget, the shadow step is skipped (`lookup=budget`).

### The shadow replay

The base bundle is downloaded and verified into a fresh work directory
`cad/out/rs/<8 random characters>/` (`b` the bundle, `o` the replay's output
root, `t` its temporary files), short so that a replayed output's path is the
build's own plus 14 characters (`\rs\<8 random characters>\o`). Old-format
bundles (captures mirrored under their output paths) are never a base: the
manifest schema, the log schema and the engine digest in the blob prefix all
exclude them.
Then the CURRENT part script is replayed against the base log in a subprocess
with SolidWorks absent. Before it runs a line of the script, the replay checks
the inputs that are not Python source and refuses (`input_mismatch`) on any
difference: the log schema, the engine, the declared environment keys, every
file outside the output root a COM argument named, and the SolidWorks revision.
The revision is compared header to header: the base log's against this build's
own fresh recording (`--seat-log`), both read by the recorder from
`ISldWorks.RevisionNumber` before its window (also in `summary.json`
`sw_revision`). An unknown revision on either side refuses too. The replay
serves recorded responses and refuses live COM, writes outside its scratch,
and non-loopback network. The worker slot gets a hard 120 s budget; the seat is
not held. Next, the base log is compared with this build's own fresh recording
(`com_replay.py diff`, `_com_outcome.judge`):

- `ground_truth`: `same` when the fresh build issued exactly the base's
  requests in the base's order, `diverged` when it did not.
- `truth_cause`: what preceded the first request difference.
  `response:<member>` names the nearest earlier answer that differs beyond
  noise; `request` means every earlier answer agreed, so the script asked
  something else. Noise is SolidWorks' new-document title counters (`Part11`
  against `Part12`), the masked provenance value, and floats within 1e-9 of
  their value's largest float. The named answer need not have steered the
  request: when a source edit follows a reordering, the reordering is named.
  `response:title_counter` means the diverging request is the base's but for
  a title counter an earlier answer carried (ms_stick before #2514,
  2026-11-12: a dimension's full name, `D3@MinorPattern@Part24.Part`, written
  into an equation; the build now writes `D3@MinorPattern`, as SolidWorks
  accepts for `D3@TickPattern`), so on a `noop` it is `seat_nondeterminism`.
  `error:<type>` means judging the cause raised (message in
  `outcome_details.truth_cause`); on a `noop` that is `noop_outcome_unknown`,
  never `noop_unexplained_divergence`.
- `artefact_outcome`: whether the fresh build made the base's part, from four
  signals that do not depend on call order (`outcome_signals`):

  | signal | compared |
  | --- | --- |
  | `mass` | every mass-property measurement, as a multiset per kind: one `*.GetMassProperties*` answer (one body), or every answer read from one `IMassProperty` object, in the order read (so a volume stays paired with its own centre and inertia). Each measurement must pair with one of the other build's within tolerance, by an assignment (Kuhn's augmenting paths; closeness is not transitive, so pairing greedily or by a sort key could strand one). A documented `*.GetMassProperties*` array (centre of mass x/y/z, volume or area or length, area or circumference, mass, six moments, an optional accuracy, per the API reference) is compared quantity by quantity, each within 1e-9 of its own largest component; any other answer within 1e-9 of its largest component. A centre of mass is also within 1e-9 of the part's length (cube root of its largest volume), since a symmetric part's centre is noise around zero. The first measurement the assignment cannot pair is reported with the other build's unpaired measurement nearest to it (in tolerances) and the quantity farthest beyond tolerance against that one |
  | `requests` | the multiset of recipe requests, handles erased, noise normalised |
  | `answers` | the multiset of (request, answer) pairs, but for mass properties and answers about the session (`IModelDoc2.SummaryInfo` dates, `ISldWorks.GetUserPreference*`). Per request (member and canonical arguments) whose answers differ in the multiset, every answer of one build must pair one-to-one, by assignment, with one of the other's to that request whose structure and normalised strings are equal and whose floats lie within 2^25 ulps of the answer's largest float (`_ANSWER_ULPS`: at most 7.5e-9 of it, 0.23 nm on a 34 mm coordinate); a request answered more often in one build, or an answer left unpaired, is `different`. Measured basis, 2026-11-12: over 57 fleet recording pairs, 553,379 answers to the same request at the same point were bit-identical, within 1e-9, or a billion tolerances and more apart (bodies or faces listed in another order); the exception, `dt_crank_drive_gear`'s `IFace2.GetClosestPointOn` onto an edge of a planar face, lay up to 9.5e6 ulps (6.6e-11 m, 1.9 × 1e-9) apart and had raised a false alarm. What the bound could hide: a source change whose only trace is a float answer moved by less than 7.5e-9 of its value, with requests, mass and STL unchanged. `truth_cause` keeps the 1e-9 rule, so such an answer before a request divergence is still named its cause. A subnormal float (below `sys.float_info.min`, 2.2e-308) compares as 0.0 (`_measured`): no measurement is that small. Such floats are integers SolidWorks packs into doubles (`IEdge.GetCurveParams2`'s curve type, tag and sense) or memory read as doubles: on 2026-11-12 `pn_vn_pen_set_screw`'s `ISurface.CylinderParams` of faces that are no cylinder answered the high half of a module address, which differed between two workers, and raised a false alarm. Over the 87 saved recordings of 33 stems (107 same-stem pairs) the rule changed that pair's verdict to `same` and no other; its 6 answers were the only ones anywhere that differed in subnormal floats alone. What it could hide: a change confined to packed integers in an answer with no normal float (none recorded); in an answer with one, packed integers already lie within the bound |
  | `stl` | each exported STL's geometry, whatever its triangulation and float32 noise. Each vertex one STL lacks pairs one-to-one with the other's within eps, 4 float32 ulps of the STL's largest \|coordinate\| (Chebyshev distance; 3.05e-5 mm on a 100 mm part); a vertex with no counterpart within eps, several, one both STLs have, or a counterpart another vertex is also within eps of compares `different`. Both STLs then take one representative per pair, and per plane must have the same outline (the edges just one of the plane's triangles uses, in its winding) and the same area within 1e-9 of the total. A plane is the triangles whose unit normal (to 1e-4) and offset (to 1e-3 mm) bins touch. A curved face has no plane: each flat facet is one, so a curved face re-tessellated over the same vertices compares `different` (a missed reuse, never an unsound one). Triangle order, corner rotation, facet normals and the header are no part of it; a file that is not a well-formed binary STL of finite coordinates is compared byte for byte. A path whose vertices were paired reports the count, eps and the largest shift, `same` or not |

  `same`: all four are present and agree. `different`: one differs, or is in
  one log only. `unknown`: nothing differs, but neither log holds a
  mass-property snapshot or an STL export, a capture cannot be read, or
  judging a signal raised (that signal is `absent`, its error its
  `outcome_details` entry; the diff's result and request divergence are
  kept). SLDPRT and BMP captures are no signal: a part file's bytes differ on
  every save, a screenshot's with the seat.

  What the STL tolerance can hide: a change that moves every vertex it moves
  by less than eps (31 nm on fr_nameplate's 100 mm), keeps the vertex count
  and keeps every plane's outline. `mass` still catches such a move of any
  face larger than 1e-9 of the volume over eps (0.18 mm² on fr_nameplate);
  `requests` and `answers` add nothing when the requests are identical.

Every verdict has a `verdict_class`:

| class | verdicts | meaning |
| --- | --- | --- |
| `noop` | `noop` | the replay found the base's requests |
| `divergence` | `diverged`, `exhausted`, `unconsumed` | the replay judged the requests different |
| `refusal` | `input_mismatch`, `sandbox` | the replay declined to judge, by design |
| `infrastructure` | `error`, `timeout`, `unavailable` | no judgement, for a reason of the machinery's own |

What a `noop` proves, and what it does not:

| proves | does not prove |
| --- | --- |
| under the base's recorded answers, the current source issues exactly the base's recipe requests (the masked provenance value aside) | that a fresh build gets the same answers |
| the inputs a replay pins match: log schema, engine, environment keys, the files COM arguments name, SolidWorks revision | what the source does on branches the recorded answers never took |
| | anything SolidWorks reads outside COM arguments (registry, preferences, seat state), the arguments of recipe-inert calls (compared by count only), the masked value |
| | that the part file is byte-identical |

Because Python's inputs are pinned, a fresh build whose requests diverge from
the base after a `noop` was steered by SolidWorks, not by the source. Request
equality therefore measures the seat and stays telemetry; the outcome is the
oracle. Every `noop` gets exactly one `noop_judgement`; each but `confirmed`
(the base's exact requests and the base's part) is also a marker:

- A **soundness alarm** (`soundness_alarm`) is a `noop` whose
  `artefact_outcome` is `different` and that is no `seat_path_divergence`:
  if recordings had been reused, another part would have been reused. It is
  logged at ERROR (`[com-replay] SOUNDNESS ALARM ...`, bounded evidence with
  the signals and the diff's `seat_path`), revokes the base, and never fails
  the build.
- `seat_nondeterminism` is a `noop` with `ground_truth=diverged`,
  `truth_cause=response:<member>` and `artefact_outcome=same`: SolidWorks
  answered differently and the part is the same. It is counted (a marker on
  the INFO line, a field in the record and span), never an alarm.
- `seat_path_divergence` is a `noop` with `ground_truth=diverged`,
  `truth_cause=response:<member>` and `artefact_outcome=different` only in the
  requests and answers (the `mass` and `stl` signals `same`), whose requests
  differ from the base's only by detours: the diff's `seat_path` (judged by
  `_com_outcome.seat_path` for exactly such a diff, `None` otherwise) has
  `path=detour`. A detour is a block of requests one build made and the other
  did not, of pywin32 protocol and listed reads and selections only
  (`_DETOUR_READS`, `_DETOUR_SELECTS`, by exact member; a method call or a
  property get, never a put; a member not listed is no read, whatever its
  name), right after the one selection (`SelectByID2`, `IEntity.Select2` or
  `Select4`) whose answer steered it. Every other answer to a request both
  builds made, including a request other than a selection right before a
  block, must be the same under the `answers` signal's rules. In both builds
  the selection before each block and those in it must select in one
  document the log establishes (a `SelectByID2` through the extension an
  `IModelDoc2.Extension` get answered, an entity of a body
  `IPartDoc.GetBodies2` answered; handles followed through `QueryInterface`),
  and `ClearSelection2` on that document must come after the block before
  anything but a read, a selection (a clear on another document is one) or
  the measure tool's own `IMeasure.ArcOption`. The streams are aligned
  greedily and bounded: at most 16 blocks of at most 4096 calls, each
  resuming on 8 equal requests or the end of both. Anything else
  (`unaligned`, `not_read`, `answer`, `selection_kept`, or `error`, a judge
  fault) stays a soundness alarm. It is counted (a marker on the INFO line,
  `seat_path_divergence` and `seat_path`, the verdict, in the record and
  span), never an alarm, never a revocation, on the shadow and the audit path
  alike. 2026-11-12, `mg_magnifying_wheel`: an edge `SelectByID2` by a point
  answered False on one build of five, and the vendored
  `_select_entity_geometric` fallback found the closest edge (164
  `IEdge.GetClosestPointOn`) and selected it itself; mass properties within
  1e-14, the STL byte-identical. Its face variant (`IBody2.GetFaces`,
  `IFace2.GetClosestPointOn`) is listed too.
- `noop_unexplained_divergence` is a `noop` with `ground_truth=diverged`,
  `artefact_outcome=same` and no earlier answer differing
  (`truth_cause=request`): neither the source nor SolidWorks explains the
  divergence, which contradicts the premise above (an input the replay does
  not pin). It is counted and logged at WARN with the same bounded evidence.
- `noop_outcome_unknown` is a `noop` whose outcome is `unknown` or was never
  compared, or whose divergence's cause could not be judged
  (`truth_cause=error:<type>`): neither an alarm nor evidence of soundness,
  counted apart.
- A `divergence`-class verdict with `ground_truth=same` is a
  `false_divergence`, meaning a missed reuse that is not unsafe. Refusals and
  infrastructure verdicts are never false divergences; count them by
  `verdict_class`.
- `judge_fault`, on any verdict, is a judgement that raised: a
  `truth_cause` of `error:<type>` or a signal `absent` because judging it
  raised (the diff's `judge_faults`, each a `step` and its `error`), not
  because neither log holds it; it is counted (the marker, `judge_fault` and
  the faulted steps as `judge_faults` in the record and span) and logged at
  WARN with the bounded evidence, so a judge that faults on every build does
  not pass for no-ops that are legitimately unknown.

The bounded evidence lists the short fields first (verdict, served and
recorded counts, ground truth, truth cause, outcome and signals, judge
faults, where the requests diverged, the differing inputs) and the outcome
details last, clipped to what is left of 4000 characters.

The work directory is removed afterwards.

Observed SolidWorks variation (2026-11-11): `IBody2.GetFaces` listed the same
faces of one body in another order between builds, including two consecutive
documents of one SolidWorks session. Every reordering moved a -Y planar face,
right after a Hole Wizard feature was finalised, and
`_holes.find_planar_face` measured the faces in the order listed (it still
does, but since #2514 it ranks faces on rounded values with the bounding box
as the last key, so the order no longer decides which face it picks). On
`part:dt_cone_swing_platform` this raised the fleet's first alarm under the
earlier request-equality rule: the replay was a `noop` and the fresh build's
requests diverged at the face search, yet its mass properties, request and
answer multisets and STL were the base's. Two request-identical
`dt_crank_pinion` builds wrote the same STL triangles in another order, with
corners rotated and normals off in the last bits. Later that day a
`dt_cone_swing_platform` build listed that face search's faces in a third
order and wrote 35 of the STL's 1226 triangles otherwise: the same 724
vertices, a polygon of the top face and two side-wall rectangles split along
other diagonals, mass properties within the last bit. It raised an alarm
under a triangle-multiset `stl` signal, now replaced by the geometric one
above. A `sh_vn_chain_link` build measured one configuration's four
bodies in another order (`IBody2.GetBodies2` listed them otherwise, each
body with its own face count), the same bodies as the base's; `mass` matched
by call order would have read another part. Over that day's 38 consecutive
same-part recording pairs, all 26 request-identical pairs and both reordered
`dt_cone_swing_platform` pairs compare `same`; every pair with a source or
configuration edit compares `different`, including the property-only edits.
The re-triangulated platform pair and the reordered chain-link pair compare
`same`.

On 2026-11-12 a `fr_nameplate` build raised an alarm with the base's exact
requests and answers: 458 of its 25348 STL vertices differed. 455 differed by
float64 residues on the top face, 0 against ±2e-16 to 9e-16 mm (float32 keeps
them at zero), and 3 by 1-2 float32 ulps (at most 4.8e-7 mm); same body, all
291 face normals byte-identical, mass properties within 5 float64 ulps. Of
the 13 fresh builds of it then kept in the remote cache, 10 on five workers
wrote byte-identical STLs and 3 (on three of those workers) each moved
415-458 vertices, by at most 7.2e-7 mm: run-to-run noise, not a worker's.
With the vertex tolerance all 13 compare `same`. Over 101 saved recording
pairs it changes only that alarm's verdict (now `same`): all 56
request-identical pairs compare `same`, and the 45 diverged pairs keep their
verdicts, the 7 with a real STL change (vertex sets 9.5e-4 and 0.025 mm
apart, Hausdorff) still `different`.

### Reuse

In mode `reuse` (the default) a part key that misses under `rw`, on a local
seat or a farm worker, is first offered to `_replay_shadow.reuse_attempt`,
before the seat is taken, inside span `replay.reuse part:<stem>`. It reuses
only when every check below holds, in this order; the first that fails
declines with its reason:

1. Not a forced refresh (`forced_refresh`; the refresh revokes what it
   replaces, see "Revocation"), and the inputs still make the key
   (`inputs_moved`).
2. A base: the nearest recording of the stem under this engine (only real
   builds publish one) whose manifest is bound to its archive (`archive`),
   made under this cache salt (keys are revision-agnostic only within a
   salt) and of another key; the usual 8-manifest, 3 s lookup (`no_base`;
   `no_bound_base` when recordings exist but none qualifies,
   without replaying; `time_cap`). The base must not be revoked
   (`revoked_base`, without replaying; a revocation that cannot be read
   declines `fault`).
3. The same SolidWorks: the base's `sw_build` is this machine's
   (`seat_differs`, also when either is unknown).
4. No differing input is a document SolidWorks opens itself
   (`SOLIDWORKS_DOCUMENTS`: templates, models, drawings, DXF/STEP and other
   imports, fonts, libraries) or acts on the seat outside the recorded window
   (`outside_window_inputs`: `_session.py` and every keyed module it imports,
   derived by `_buildgraph.module_deps_of`, today `_com.py` and `_paths.py`;
   `_session.run_build` connects, discards, pins the template and tears down
   outside the window, and a replay replaces it whole), even when the recipe
   also executes it inside the window (`unjudged_input`). An edit to one of
   them therefore re-keys every part and declines every reuse: in the 30
   days to 2026-11-12, 3 of 3957 commits touching `cad/scripts/*.py` did
   (all `_paths.py`).
5. The base bundle, verified against its manifest (`base_bundle_missing`).
6. A replay of the current source against it with SolidWorks absent
   (`com_replay.py replay`, `--seat-log` the base's own log: the replay
   stands for the base's seat; under the process inputs the build would get,
   `dodo._com_process_inputs`). Before its verdict counts, no differing input
   may be one a COM argument of the base names, which SolidWorks opens by
   path whatever the script also does with it (`solidworks_inputs`;
   `unjudged_input`). Then the verdict must be a clean `noop` (`diverged`,
   `input_mismatch`, `sandbox`, `replay_error`, `time_cap`), every differing
   input must be one the replayed recipe imported or read (`python_files`:
   the driver's audit hook on `open` and `import`, crediting an event to the
   recipe when a frame of the build script is nearer it than one of the
   engine, so nothing the engine loads or reads for itself is listed, nor
   the replay's own outputs; `unjudged_input`), SolidWorks may open no
   output-root file the base did not capture (`solidworks_out_inputs`;
   `unjudged_input`), and no replayed request may carry a document title
   counter, the seat's session state the replay serves from the base
   (`title_echoes`, also when unreported; `seat_state_echo`).
7. The base key's canonical archive, downloaded and verified as a restore
   verifies it (`base_archive_missing`), is the one the recording is bound to
   (`unbound_base`: a refresh replaced it).
8. The replay's outputs (`com_outputs` and `py_outputs`) are exactly the
   archive's members, all within the task's declared outputs, with the
   native part among them (`output_set_differs`); every output Python wrote
   is its member byte for byte (`python_output_differs`), but for one field:
   a member-export certificate (`reports/part-neutral/<stem>.json`) names
   the SHA-256 of the native part (`execution_identity`), and a recording
   keeps that part as SaveAs3 wrote it, before the build's in-place Save3,
   so the replay's certificate may differ from the archive's in that field
   alone, each side naming its own native part's digest.
9. The inputs still make the key (`inputs_moved`).

The template's identity is its key input: every build pins the default part
template to `cad/templates/harmonic-analyzer.PRTDOT` before the recorded
window (`_session._pin_default_part_template`; `NewPart()` names no path), so
a key with an unchanged template digest built on the same template, and a
changed one declines at step 4.

Then `dodo._reuse_part` makes the reuse, with no COM seat and no
`sw.connect`: its `task part:<stem>` span carries `cache=reuse` and
`com=none`. It installs the archive as a HIT restores one, checks every
installed file against its member, re-stamps the `.execution` token and
requires it to equal the base's native SHA-256 (`token_mismatch`), validates,
publishes the create-only marker
`com-replay/epoch-<n>/<engine[:16]>/<stem>/reused/<new key>.json`
(`origin_key`, the base archive's SHA-256 and size, `marked_utc`, the
checkout's `commit`; an existing marker naming another origin falls through),
then stores the outputs under the new key through the normal create-only
store (`lost` adopts the winner, as for a build). A reused key publishes no
recording or bundle: only real builds are bases, so every later key replays
against a real build's recording, never against a reuse.

A reuse never costs a build: an exception in any phase (lookup, bundle,
replay, archive, verify, install, mark) declines `fault` with a WARN, and a
failed install, token check or marker falls through the same way; the build
then runs on the seat, which rewrites every output. A restore lock during
the install (`RestoreLocked`: an output open in a SolidWorks session) is such
a fault: the attempt declines and the seat builds, rather than releasing the
documents and retrying, which is acceptable. Once the outputs are stored,
nothing of the reuse can fail the task: a local record that cannot be kept is
a WARN. A build that was not reused is recorded and judged after it as in
`shadow` mode; when the attempt already replayed against a base, that replay
is the shadow's and only the comparison (`com_replay.py diff`) runs after the
build, judged `input_mismatch` if the build's seat reported another
`sw_revision` than the base's. The exit-92 re-run happens inside the seat
build, after the attempt, and is never reused; `ro`/`off` roles and the farm
submitter make no attempt (the worker does).

**Audit.** One would-be reuse in eight (`AUDIT_ONE_IN`; the first 8 bytes of
the key's SHA-256, so every seat and rerun samples the same keys) builds on
the seat anyway (`reuse_decision=audited`) and is judged with the pre-build
replay's verdict, so the soundness alarm stays live on exactly the path that
reuses.

**Revocation.** A create-only
`com-replay/epoch-<n>/<engine[:16]>/<stem>/revoked/<base key>.json` retires a
base: no attempt reuses it again (`revoked_base`). It is written when a
shadow or audit judgement raises a `SOUNDNESS ALARM` against the base (the
`replay_shadow` record's `revoked`; a `seat_path_divergence` revokes nothing),
and when a forced cache refresh targets a key in modes `reuse`, `shadow` or
`record` under `rw`: the origin its `reused/` marker names is revoked, and so
is the key itself when a recording of it is published (it is a base). A
revocation that cannot be written is a WARN and never fails the build; one
that cannot be read declines the attempt (`fault`).

**Soundness.** A reuse claims the base's archive is an outcome the current
source's build could have had. The replay fed the current source the base's
recorded responses and saw it issue every recorded request, bit for bit
(canonical arguments, floats as `float.hex`) and in order, and nothing more.
A live build on a seat that answers those requests as the base's seat did
therefore issues the base's conversation, so SolidWorks writes what it wrote
for the base (the archive's native part, STL and captures), and Python, which
saw the same responses, writes what the replay wrote, which equals the
archive's members byte for byte. The seat answers as the base's did when it
is the same SolidWorks (`sw_build`), started from the same state (the same
template, by key; the same outside-window inputs; nothing in the window
inherited from earlier documents, which `_session` discards), under the same
process inputs (`PYTHONHASHSEED`, the read guards: pinned by the replay's
input check) and the same files SolidWorks opens by path (digests pinned by
the replay, and every differing one declines). Every other differing key
input was imported or read by the replayed recipe inside the window, so its
whole effect on the part went through the requests and Python outputs just
compared. The archive is the one the recorded build stored (binding), so
another writer's bytes are never reused; the token check is an integrity
check that the installed native part is the base's bytes. Dependents' keys
still move when the part's key moves (they fold the part's recipe digest,
`dodo._stable_artefact_digest`), so a reuse saves the part leaf only, and
the dependents rebuild against the reused part.

Not proven off-seat:

- That SolidWorks answers the same conversation the same way on two seats of
  one `sw_build`. It does not, byte for byte: face and body order and STL
  vertices vary from run to run (`seat_nondeterminism`, the 2026-11-12
  `fr_nameplate` vertices). The claim is only that the archive is one outcome
  of the current source, which the audit and the alarm keep measuring.
- That a `seat_path_divergence`'s detour selected what the base's path
  selected. The claim rests on the base's mass properties and STL, on the
  detour being only reads and selections, and on the selection being cleared
  on its document before any later request that is not a read or a
  selection; a request that consumed the selection inside that window (the
  measurement after the 2026-11-12 detour) is compared like any other, answer
  for answer. A document is known by its handle's root through
  `QueryInterface` answers, so one document reached by two routes (two
  `ActiveDoc` reads) counts as two: an alarm, the safe direction.
- That the seat's state outside the template and the build's own document
  settings is the same: system options, add-ins, material and Toolbox
  databases and licensing are machine image, not inputs.
- That `sw_build` (the executable's file version) identifies the SolidWorks:
  service-pack DLLs updated without the executable would pass.
- That every file Python reads goes through `open`: a C extension reading one
  itself leaves it out of `python_files`, which only declines (the safe
  direction), but a file SolidWorks opens through a path no COM argument
  names (a relative path, an environment variable) is not seen at all.
- Provenance: a reused part carries the base's `Generator` stamp (the replay
  masks it), so a base built from a work-in-progress checkout under `rw`
  spreads its `-dirty` commit to every key that reuses it. Same-key cache
  hits already carry the stamp of whichever build stored them; the marker's
  `commit` names the reusing checkout.

The native proof of reuse, on one throwaway salt: a record pass whose
manifests are all bound (`replay_shadow` records `bound=true`, `sw_build`
set); an inert-edit pass that reuses every edited part (`reuse=reused`,
`com=none`, no `sw.connect`, tokens equal to the bases'); a geometry-edit pass
that declines and builds; dependents (assemblies, drawings and
`verify_soundness`) rebuilding green against the reused parts; and audited
builds judged with no `SOUNDNESS ALARM`.

Reading a proof pass: under one salt, a key reuses only when its source
differs from a recorded real build's. Unchanged source under the same salt
hits the cache, and a fresh salt has no base of its own (`no_bound_base`, or
`no_base`), so same salt plus different source is the only way a proof pass
reuses. Each part's
`[com-replay] part:<stem>: reuse=` INFO line says what happened:
`reuse=reused | base=<key>` installed that base's archive with no COM;
`reuse=audited` and every `reuse=declined:<reason>` built on the seat, the
reason naming the first check that failed. A proof that must drive
SolidWorks (seat behaviour, timing, native outputs) forces a cache refresh
(which also revokes what it replaces) or runs under a fresh salt.

`_com_conversation.py`'s module docstring still says nothing is reused from a
recording. Editing it would change the engine digest, which scopes every
published recording, so it stays until the next engine change.

Reuse decisions and per-phase cost (drop `by stem` for the fleet; decline
reasons are `declined:<reason>`):

```kusto
dependencies
| where timestamp > ago(7d) and name startswith "replay.reuse "
| extend stem=tostring(customDimensions.label),
         decision=tostring(customDimensions["replay.reuse_decision"]),
         replay_s=todouble(customDimensions["replay.replay_s"]),
         archive_s=todouble(customDimensions["replay.archive_s"])
| summarize attempts=count(), p50_s=percentile(duration, 50) / 1000.0,
            p95_replay_s=percentile(replay_s, 95), p95_archive_s=percentile(archive_s, 95)
            by decision, stem
| order by attempts desc
```

Audited builds and their judgements:

```kusto
dependencies
| where timestamp > ago(7d) and name startswith "replay.after_build "
      and tostring(customDimensions["replay.reuse_decision"]) == "audited"
| join kind=leftouter (dependencies
    | where name startswith "replay.shadow "
    | project operation_Id, alarm=tolower(tostring(customDimensions["replay.soundness_alarm"])) == "true",
              verdict=tostring(customDimensions["replay.verdict"])) on operation_Id
| summarize audited=count(), alarms=countif(alarm) by verdict
```

The same from a local `cache.jsonl`:

```sh
jq -s '
  [.[] | select(.event == "replay_reuse")] as $r
  | {
    decisions: ($r | group_by(.reuse_decision)
                | map({key: .[0].reuse_decision, value: length}) | from_entries),
    faults: [$r[] | select(.decline == "fault") | {label, phase, detail}],
    reused: [$r[] | select(.reuse_decision == "reused")
             | {label, key, base_key, marker, seconds}],
    audited: [.[] | select(.event == "replay_shadow" and .reuse_decision == "audited")
              | {label, key, verdict, ground_truth, soundness_alarm}]
  }' cad/out/reports/cache.jsonl
```

To turn reuse off, see "The switch": `DEFAULT_MODES[BuildKind.PART] =
ReplayMode.SHADOW` for the fleet, `HARMONIC_COM_REPLAY=part=shadow` on one
machine.

### What it costs a task

A recorded part task pays on its own wall clock in up to three places:

1. **On the seat**, inside the `task part:<stem>` span. The recorder's time
   inside the recording window is `replay.engine_s` + `replay.escape_audit_s`
   on the `replay.record_overhead` span (`replay.overhead_pct` relates it to
   the rest of the window). The driver's start before the window and its
   summary after it are seat-held as well and are not in those attributes:
   the whole seat-held difference is the `task` span's duration against an
   unrecorded build of the same part on the same seat.
2. **Off the seat**, after the part archive is stored: the
   `replay.after_build <label>` span encloses every part of the step (key
   re-hash, bundle, uploads, lookup, bundle download, replay and comparison
   subprocesses, the `cache.jsonl` record and the INFO line). The lookup is
   bounded by 3 s and the evaluation by 120 s; publication only by the
   cache's transfer timeouts; `record` mode ends after publication. A farm
   leaf's process runs this one task, so the step lengthens the leaf by its
   whole duration, with the seat idle.
3. **Before the seat**, in mode `reuse`: the `replay.reuse <label>` span (a
   lookup bounded by 3 s, then bundle, replay and archive within 120 s). A
   reuse replaces the build and the step after it with this and the store;
   a declined attempt adds it, and a replay that ran is not repeated after
   the build (only the comparison runs).

Per build, the added task time is a sum over the part tasks under `rw` that
miss (or are forced refreshes). In mode `reuse`, every miss that makes an
attempt (a forced refresh makes none) adds the mean `replay.reuse` duration
over those attempts. Every task that then builds on the seat (declined,
audited, or no attempt) adds the mean seat-held overhead plus the mean
`replay.after_build` duration; after an attempt that already replayed,
`replay.after_build` holds only the comparison. A reused task runs neither:
its seat build and `replay.after_build` are replaced by its `replay.reuse`
span plus the store, so it costs that and saves the build. Part cache hits,
gates and every task under `ro`/`off` add nothing; recorded assemblies and
drawings pay the first two ("Assemblies and drawings" below). How
much of that sum reaches a build's wall clock depends on how many part
leaves run at once and which of them are on the critical path; the farm's
slot time grows by the whole sum.

```kusto
dependencies
| where timestamp > ago(7d)
      and (name startswith "replay.reuse " or name startswith "replay.after_build ")
| extend step=tostring(split(name, " ")[0]),
         result=iff(name startswith "replay.reuse ",
                  tostring(customDimensions["replay.reuse_decision"]),
                  tostring(customDimensions["replay.outcome"])),
         s=duration / 1000.0
| summarize tasks=count(), mean_s=avg(s), p50_s=percentile(s, 50),
            p95_s=percentile(s, 95), max_s=max(s), total_s=sum(s) by step, result
| order by step asc, total_s desc
```

### Where results land

All spans are on service `build-infra` and carry `label=<kind>:<stem>`:

| span | attributes |
| --- | --- |
| `replay.reuse <label>` | mode `reuse`, before the seat: `replay.reuse_decision` (`reused`/`audited`/`declined:<reason>`), `replay.decline`, `replay.detail`, `replay.phase` (faults only), `replay.lookup`/`listed`/`read`/`unusable`, `replay.base_key`, `replay.differing_count`, `replay.differing_classes`, `replay.verdict`, `replay.served`, `replay.recorded`, `replay.<phase>_s` (`lookup`, `bundle`, `replay`, `archive`, `verify`, `publish`), `replay.bundle_bytes`, `replay.archive_bytes`, `replay.token`, `replay.store`, `replay.marker` (the `reused/` marker's publication); a reuse's `task <label>` span (`cache=reuse`, `com=none`) is inside it |
| `replay.after_build <label>` | `replay.outcome`, `replay.reuse_decision` (mode `reuse`); encloses every span below and the whole off-seat step |
| `replay.record_overhead <label>` | `replay.engine_s`, `replay.escape_audit_s`, `replay.window_s`, `replay.overhead_pct`, `replay.recipe_requests`, `replay.inert_calls`, `replay.capture_stored_bytes` |
| `replay.publish <label>` | `replay.publish` (`stored`/`exists`/`skip`/`off`/`error`; for a build that stored no archive, the store's outcome: `lost`, `empty`, `error`, or `unstored`), `replay.bundle_bytes`, `replay.bound` |
| `replay.base_lookup <label>` | `replay.lookup` (`found`/`none`/`budget`/`off`), `replay.listed`, `replay.read`; an assembly or drawing also `replay.candidates` and `replay.same_children` |
| `replay.shadow <label>` | `replay.verdict`, `replay.verdict_class`, `replay.recorded`, `replay.served`, `replay.divergence_member`/`_field`/`_caller`/`_index`, `replay.inert_recorded`/`_served`/`_unserved`, `replay.substitutions`, `replay.base_key`, `replay.differing_count`, `replay.differing_classes`, `replay.ground_truth`, `replay.truth_cause`, `replay.artefact_outcome`, `replay.outcome_signals` (`mass:same,requests:same,...`), `replay.noop_judgement` (no-ops only), `replay.soundness_alarm`, `replay.seat_nondeterminism`, `replay.seat_path_divergence`, `replay.seat_path` (`detour`/`unaligned`/`not_read`/`answer`/`selection_kept`/`error`, judged diffs only), `replay.noop_unexplained_divergence`, `replay.noop_outcome_unknown`, `replay.false_divergence`, `replay.judge_fault`, `replay.judge_faults` (`truth_cause,stl,...`, faults only), `replay.wall_s` |
| `replay.split <label>` | an assembly or drawing, mode `shadow` ("Assemblies and drawings"): `replay.split`, `replay.candidates`, `replay.same_children`, `replay.children_unreadable` (`children_unknown` only), `replay.base_key`, `replay.differing_count`, `replay.differing_classes`, `replay.own_differing`, `replay.recipe_requests`, `replay.base_recipe_requests`, `replay.ground_truth`, `replay.truth_cause`, `replay.artefact_outcome`, `replay.outcome_signals`, `replay.noop_judgement` (`OutputJudgement`, no-ops only), `replay.title_echo`, `replay.name_bound` (arrays bound by name, when any), `replay.output_nondeterminism`, `replay.output_cause` (`jagged_outline`/`seat_display`/`answers`), `replay.unexplained_output_divergence`, `replay.display`, `replay.base_display`, `replay.seat_nondeterminism`, `replay.seat_path_divergence`, `replay.seat_path`, `replay.noop_outcome_unknown`, `replay.judge_fault`, `replay.judge_faults`, `replay.wall_s` |
| `replay.evidence <label>` | an assembly's or drawing's evidence copy ("Evidence copies"): `replay.evidence` (`stored`/`exists`/`skip`/`off`/`error`) |

The sidecar transfers inside them are `cache.sidecar.upload`,
`cache.sidecar.download` and `cache.sidecar.list`.

Each recorded build also appends one `replay_shadow` record to
`cad/out/reports/cache.jsonl`, whose `outcome` is one of:

- `record_fault` (with `recovery` and `where`): nothing published
- `no_recording`
- `inputs_moved`
- `recorded`
- `no_base`
- `evaluated`, which also carries the verdict fields
- `error`

and ends with one INFO line in the task log, for example:

```text
[com-replay] part:pd_transgear_arm_plate: evaluated | publish=stored bytes=412160 | lookup=found base=f1016ee56b74 differing=1 listed=3 read=3 0.412s | shadow=noop served=1874/1874 9.84s | truth=same | outcome=same cause=-
```

(`-` marks a step the build never reached). A `SOUNDNESS ALARM`,
`seat_nondeterminism`, `seat_path_divergence`, `noop_unexplained_divergence`,
(an assembly or drawing) `output_nondeterminism cause=<cause>`,
`unexplained_output_divergence` or `title_echo`, `noop_outcome_unknown`,
`judge_fault` or `children_unreadable` marker ends the line when it applies;
in mode `reuse` a `reuse=<decision>` segment follows the outcome. On a farm
leaf `cache.jsonl` stays on the worker, so use Application Insights for
fleet-wide results. The `replay_shadow` record's outcome fields are
`artefact_outcome`, `truth_cause` and `seat_path` (the diff's verdict, when
judged): `outcome` is the step's. It also carries `bound` (the manifest names
the archive this process stored), in mode `reuse` `reuse_decision`, and after
a `SOUNDNESS ALARM` `revoked` (the base's revocation: `stored`, `exists`, or
`error` after a WARN).

Every reuse attempt appends one `replay_reuse` record (the span's fields, with
`seconds` per phase) and logs one INFO line, for example:

```text
[com-replay] part:sh_widget: reuse=reused | base=0f3c19a2b7d4 differing=1 | shadow=noop served=1874/1874 | lookup=0.21s bundle=0.35s replay=9.84s archive=0.62s verify=0.01s publish=0.48s | store=stored marker=stored
```

A decline ends the line with its detail instead of the store segment.

Verdict classes, alarms, seat nondeterminism, seat path divergences,
unexplained divergences, unconfirmed no-ops, false divergences and judge
faults per stem (drop `by stem` for the fleet total):

```kusto
dependencies
| where timestamp > ago(7d) and name startswith "replay.shadow "
| extend stem=tostring(customDimensions.label),
         kind=tostring(customDimensions["replay.verdict_class"]),
         alarm=tolower(tostring(customDimensions["replay.soundness_alarm"])) == "true",
         seat=tolower(tostring(customDimensions["replay.seat_nondeterminism"])) == "true",
         seat_path=tolower(tostring(customDimensions["replay.seat_path_divergence"])) == "true",
         unknown=tolower(tostring(customDimensions["replay.noop_outcome_unknown"])) == "true",
         unexplained=tolower(tostring(customDimensions["replay.noop_unexplained_divergence"])) == "true",
         false_divergence=tolower(tostring(customDimensions["replay.false_divergence"])) == "true",
         judge_fault=tolower(tostring(customDimensions["replay.judge_fault"])) == "true",
         wall=todouble(customDimensions["replay.wall_s"])
| summarize evaluated=count(), noop=countif(kind == "noop"),
            divergence=countif(kind == "divergence"),
            refusal=countif(kind == "refusal"),
            infrastructure=countif(kind == "infrastructure"),
            alarms=countif(alarm), seat_nondeterminism=countif(seat),
            seat_path_divergence=countif(seat_path),
            noop_unexplained_divergence=countif(unexplained),
            noop_outcome_unknown=countif(unknown),
            false_divergences=countif(false_divergence),
            judge_faults=countif(judge_fault),
            p50_wall_s=percentile(wall, 50), p95_wall_s=percentile(wall, 95)
            by stem
| order by alarms desc, evaluated desc
```

Recording overhead percentiles:

```kusto
dependencies
| where timestamp > ago(7d) and name startswith "replay.record_overhead "
| extend stem=tostring(customDimensions.label),
         pct=todouble(customDimensions["replay.overhead_pct"]),
         engine=todouble(customDimensions["replay.engine_s"])
| summarize builds=count(), p50_pct=percentile(pct, 50), p95_pct=percentile(pct, 95),
            max_pct=max(pct), p95_engine_s=percentile(engine, 95) by stem
```

Recorder faults, soundness alarms, unexplained divergences and judge faults
(log records):

```kusto
traces
| where timestamp > ago(7d) and message startswith "[com-replay]"
| extend label=tostring(customDimensions.label),
         recovery=tostring(customDimensions.recovery),
         kind=case(message has "SOUNDNESS ALARM", "alarm",
                   message has "noop_unexplained_divergence", "unexplained",
                   message startswith "[com-replay] output_nondeterminism ", "output_nondeterminism",
                   message startswith "[com-replay] unexplained_output_divergence ", "unexplained_output",
                   message startswith "[com-replay] judge_fault ", "judge_fault",
                   message has "recorder fault", "record_fault", "other")
| summarize count(), last=max(timestamp), example=take_any(message)
            by kind, recovery, label
```

The same from a local `cache.jsonl` (bash or PowerShell 7.3+):

```sh
jq -s '
  [.[] | select(.event == "replay_shadow")] as $s
  | [.[] | select(.event == "replay_record_fault")] as $f
  | def pct(p): sort | if length == 0 then null else .[((length - 1) * p | floor)] end;
  {
    overall: ($s | group_by(.verdict // .outcome)
              | map({key: (.[0].verdict // .[0].outcome), value: length}) | from_entries),
    classes: ([$s[] | select(.verdict_class)] | group_by(.verdict_class)
              | map({key: .[0].verdict_class, value: length}) | from_entries),
    false_divergences: [$s[] | select(.false_divergence == true)] | length,
    seat_nondeterminism: [$s[] | select(.seat_nondeterminism == true)] | length,
    seat_path_divergence: [$s[] | select(.seat_path_divergence == true) | {label, key, base_key, truth_cause, seat_path}],
    noop_unexplained_divergence: [$s[] | select(.noop_unexplained_divergence == true)] | length,
    noop_outcome_unknown: [$s[] | select(.noop_outcome_unknown == true)] | length,
    judge_faults: [$s[] | select(.judge_fault == true) | {label, key, base_key, verdict, judge_faults}],
    per_stem: ($s | group_by(.label) | map({
      label: .[0].label,
      verdicts: (group_by(.verdict // .outcome)
                 | map({key: (.[0].verdict // .[0].outcome), value: length}) | from_entries),
      alarms: map(select(.soundness_alarm == true)) | length,
      overhead_pct_p50: ([.[].overhead.overhead_pct // empty] | pct(0.5)),
      overhead_pct_p95: ([.[].overhead.overhead_pct // empty] | pct(0.95))
    })),
    alarms: [$s[] | select(.soundness_alarm == true) | {label, key, base_key, alarm_evidence}],
    record_faults: [$f[] | {label, key, recovery, where, fault_type, message}],
    overhead_pct_p95: ([$s[].overhead.overhead_pct // empty] | pct(0.95))
  }' cad/out/reports/cache.jsonl
```

Only part, FULL assembly and drawing builds that actually run under `rw`
produce records, so a target restored from the cache records nothing. To
exercise specific leaves, force a refresh of them (see "Refreshing one
unchanged leaf").

### Assemblies and drawings

Measured 2026-11-09..12, assemblies cost 34 seat-hours and drawings 35, and
91% of that was builds whose own closure (script, helpers, configuration)
changed. Keying them on their children's content instead saves about 1%. The
question part reuse answered for parts is open for them: when an assembly's or
drawing's own closure changes and its children do not, how often does the new
source issue the identical COM conversation? These recordings answer it. They
are telemetry only: every output, exit code and cache key is an unrecorded
build's, and nothing is ever reused.

**What is recorded.** A FULL assembly build (`build_or_refresh`'s FULL tier,
including the fallback after a failed EXPLODE) and every drawing build
(`_cached_drawing_action`, through `_cached_com_action(recorded=...)`) run
under the same driver as a part, planned by `_replay_shadow.plan_dependent`,
which describes the build (script, argument, children, sidecars) only once the
mode and cache role call for a recording; a description that raises builds
unrecorded with a WARN.
A drawing script keeps its argument: `com_replay.py record <script> ... --kind
drawing -- <artifact stem>` puts it back into `sys.argv` around the engine
(whose `run_script` passes none). The driver itself splits its arguments at
the first `--` before argparse sees them: argparse before Python 3.12.7
(CPython gh-59317) binds a `*` positional after the script's path to `[]` and
rejects the stem. A recorder fault's unrecorded re-run (exit 92)
is `python <script> <artifact stem>`. REFRESH tiers (`refresh_assembly.py
<stem> <tier>`) are not recorded: another script and argument, which no FULL
recording could be judged against, and the farm always builds FULL. A
`POST_ASSEMBLY` hook (none today) would run after the recorded window. The
recording lives in `cad/out/replay/<kind>-<stem>/` and is published under
`com-replay/<engine 16>/<kind>-<stem>/` (stems hold no `-`, so a drawing never
shares its part's recordings); the engine is unchanged, so part recordings and
part reuse are untouched. An assembly's bundle also carries `outputs/`: the
files Python writes beside it that the outcome compares (every assembly cache
output but the models, the renders and the input ledger: `.massprops.sha`,
`.dof.json`, the jig's `.sweep.json`, the top assembly's BOM), copied when the
driver exits 0, before a lost store could adopt the winner's.

**Children.** `dodo._child_identities` names every model the build opens, by
the SHA-256 in its `.execution` token: an assembly's references, transitively
through subassemblies; a drawing's part, or its assembly plus that assembly's
children. A token that holds none names why instead: `missing`, `unreadable:
<error>` or `malformed: <content>`. The manifest carries them as `children`,
with `kind`, `argv`, `replay_gaps` and `display`. A build with such a child
can match no base: the judgement logs one WARN naming each child and its
reason, and the record (`children_unreadable`), the `replay.split` span and
the INFO line's `children_unreadable` marker carry it, so a worker that lacks
a token is told from one that cannot read it.

**Judgement** (`_replay_shadow._judge_dependent`, after the store, off the
seat). Nothing is replayed. The lookup reads at most 16 manifests of the stem,
newest first, within 3 s. A candidate is another recording of the same kind
under the same cache salt; the base is the nearest candidate (fewest differing
key inputs, then newest) made on exactly the same children. The fresh
recording, the ground truth of what the current source asked, is then diffed
against the base's (`com_replay.py diff --kind <kind>`):

| `split` | meaning |
| --- | --- |
| `noop` | same children, the base's exact requests (with component arrays bound by name, `name_bound`), or the same requests but for the title counters the script echoed (`title_echo`): the own-closure change was a no-op for SolidWorks |
| `diverged` | same children, other requests; `truth_cause` says what preceded the first difference: `request` (the source asked something else) or `response:<member>` (SolidWorks answered differently first; `seat_nondeterminism` when it also made the same model, `seat_path_divergence` when the requests differ only by detours of reads and selections on the same geometry) |
| `children_changed` | candidates were read, none made on these children: not comparable |
| `children_unknown` | a child's token held no SHA-256 (`children_unreadable` names which and why) |
| `oversize`, `timeout`, `unavailable`, `error` | no judgement: a log past 500,000 calls, the 60 s comparison budget, the base bundle, the diff |

No candidate at all (or the lookup's budget spent) is the record outcome
`no_base`. The outcome is judged per kind (`_com_outcome.SIGNALS`): an
assembly on `mass`, `requests`, `answers` and `sidecars` (byte for byte); a
drawing on `requests`, `answers` and `pdf`, the ink of every PDF SolidWorks
wrote (text runs and path pieces per page, coordinates to 1 um), never its
bytes, which carry the export's date. Nothing of these kinds is reused, so a
`noop` is never an alarm; its `noop_judgement` (`OutputJudgement`) is one of:

| `noop_judgement` | meaning |
| --- | --- |
| `confirmed` | the base's assembly or drawing |
| `output_nondeterminism` | another output, and the seat was seen to differ: `output_cause=jagged_outline` when the PDFs differ only by a jagged crop outline drawn again, else `seat_display` when the two recordings' drawing displays differ, else `answers` (SolidWorks answered some request otherwise); WARN |
| `unexplained_output_divergence` | another output, though SolidWorks answered alike: nothing recorded explains it; WARN |
| `noop_outcome_unknown` | a signal absent, or no comparison |

Both WARNs (`[com-replay] output_nondeterminism <label>: ...`, `[com-replay]
unexplained_output_divergence <label>: ...`) carry bounded evidence with each
signal's detail (`output_evidence` in the record). 2026-11-12,
`ms_stop_plate`: one seat's 1010x678 pixel drawing window against another's
1010x598 moved two leader tips 0.45 and 0.17 mm with every request the same.

`display` is the window a drawing's sheet picks hit-test in, read from the
recording's own answers to `_seat_forensics.display_geometry`'s inert probes
(`com_replay._display`: `view_window` from `IModelView.GetVisibleBox`,
`px_per_mm` from `IModelView.ProjectModelPoint`), so it costs no COM call.
Only a drawing's recording (`record --kind drawing`) reads it on the seat, and
only from its probe lines (`com_replay._logged_display`, streaming the log
without loading it: 3.9 ms against 33.9 ms for a full load on the 6,371-call
log of the 10.97 MB `ms_measuring_stick_assembly` drawing bundle); a part's
or an assembly's never does. The summary and the manifest carry it, and
`com_replay.py diff` reads it from both logs, off the seat (`display`:
`base`, `new`), so a base whose manifest predates it is judged too; the record
carries the two (`display`, `base_display`: `<w>x<h> px/mm=<p>`).

`title_echo` (`_com_outcome.title_echo`): the first difference was a title
counter the script echoed (`truth_cause=response:title_counter`), and the
whole streams are the same requests once title counters are masked, every
answer the same but for noise. The split is `noop`; `ground_truth=diverged`
and the cause are kept, and the INFO line ends with `title_echo`. A
dependent's streams are the name-bound ones (below), and its answers may also
differ where the seat made them differ (`_com_outcome._order_only`), its
requests still the base's throughout:

- a session read (`IModelDoc2.SummaryInfo`, `ISldWorks.GetUserPreference*`);
- `swFileLoadWarning_NeedsRegen` (32) in `ISldWorks.OpenDoc6`'s warnings
  (`_com_outcome._IGNORED_WARNINGS`, here and in the `answers` signal below),
  only where the script then reads the opened document's
  `IModelDocExtension.NeedsRebuild2` through its Extension, with no call that
  may act on the document before it (`_com_outcome._rebuild_checked`), and
  both builds read the same state. Reopening the assembly the script just
  saved, 30 of 33 recordings (2026-11-13..14) read 32 and 3 read 0, two seats
  that had read 32 before, while that read, compared exactly, was 1 in all
  33. `dt_drive_train` built twice under one key differed in that bit alone.
  Any other open (a drawing's of the model it shows), the errors and every
  other warning bit stay exact;
- a read of an object an enumeration listed (the outermost handle array it
  descends from), when that enumeration is the base's in another order: its
  elements' records (each element's calls, in order, on it or on what it
  answered: member, arguments and answer, handles erased, title counters
  masked) are the base's records permuted, and every call on or with any of
  its objects is a read: a get, a wrap, a dispid lookup, a QueryInterface, or
  one of the methods `_com_outcome._READ_METHODS` lists because the API
  reference has them return a value and set nothing
  (`IComponent2.GetPathName`, `IComponent2.GetTotalTransform`).

A handle argument that names an object of such an enumeration is recorded as
what it names, not by number (#2761): the element it descends from, by that
element's own record, and its place among the objects that element's calls
allocated. The same request names another element once the seat listed them
in another order. `IInterference.Volume` answers are matched within 1e-6 of
the larger of the two (`_com_outcome._APPROXIMATE`), here and in the `answers`
signal below: SolidWorks computes an interference's volume to the modeller's
tolerance, and `pd_paper_drive`'s arm-to-screw overlap read 12.285502 mm³ in
three builds of identical geometry, 5.2e-7 apart (2026-11-14). The band is
relative only, so a vanished interference (0) still differs at any size, and
how many interferences there are and which components each pairs are
compared exactly.

A record that is not the base's (a name changed, a read or a question moved
between elements) or a call that acts on an element (a selection of the first
element is another component once the seat listed it in another order) is no
echo. Not caught: an order-dependent pick carried only by an index into
another enumeration the script did not read. The first same-key pairs after
#2730 (2026-11-14, `ch_channel` and `dt_drive_train`) are such echoes: the
title echoed into `SelectByID2` before any array was bound, then the
interference report and the component-pattern name sets read in the seat's
order, and two save dates. So is `pd_paper_drive`'s inert own edit that day:
its chain classification reads each interfering component's path and
transform.

The judge names a dependent's causes more finely than a part's (only for
`_com_outcome.DEPENDENT_KINDS`; a part's reuse and audit judgement is
unchanged). `truth_cause` names the earliest answer before the divergence
that differs beyond noise, where a part's names the nearest. It passes over a
renumbering, an answer that differs only by handles both builds numbered with
that very answer (an object's number is its allocation order, so one more
object listed earlier renumbers every later one), and names it only when
nothing else differed; a handle either build had numbered before is another
object, a real difference. A diverging request that is the base's
member on the same object, with arguments the same but for float noise
(`REL_TOL`), after an answer that differed only by float noise, is that
answer's `response:<member>`: the script carried SolidWorks' noise into a
request (2026-11-13, `dt_cone_tip_gear` and `fr_top_frame`: an annotation
position 1 ulp apart, then `SetPosition2` 1 ulp apart). Any other request
difference stays `request`. The `answers` signal compares
`IModelDoc2.ClosestDistance` by its distance only: between parallel faces any
pair of points witnesses it (`dt_drive_train` built twice under one key: the
same 6.882839 mm, witnesses 17.47 mm apart). It compares a dependent's
`IInterference.Volume` within 1e-6, relative, and a rebuild-checked
`ISldWorks.OpenDoc6` without the NeedsRegen warning bit (above). A drawing whose `pdf` signal
differs gets `pdf_cause=jagged_outline` (`_com_outcome.jagged_outline`) only
when every condition holds:

- both recordings read the same jagged views, meaning each view's last
  `IView.GetOutline` box on a handle whose `IView.CropViewJaggedOutline` read
  True, with no later move of that view;
- the PDFs have the same pages, sizes and text runs;
- on each page that differs, the differing path pieces are one solid stroke
  inside one such box and form open chains;
- those chains end at the same points on both sides, and each of those points
  is an end of an unchanged piece.

SolidWorks breaks such an outline along a random wiggle each time it draws it.
On 2026-11-13, three builds of `dt_pinion_arbor` with the same requests drew
three wiggles in detail A. The box is not tied to a sheet, so a multi-sheet
drawing's other sheets are bounded by it too. What remains possible is a real
edit that re-routes a line of the same stroke, inside such a view, between the
same two unchanged points.

The recorder numbers handles in allocation order, so the elements of an array
answer such as `IAssemblyDoc.GetComponents` are numbered in the seat's
enumeration order. A script that reads every component's name and then visits
the components in name order (the sort #2686 brings) therefore asks the same
thing of each component under a seat-dependent number. Before a dependent's
split, `_com_outcome.name_bound` binds such an array to the base's by name. It
does so only when all of these hold:

- both builds issued every request up to it, and it, alike but for title
  counters (a title the script echoed earlier, `title_echo`'s case, does not
  stop the walk), and it was answered with the same handle numbers;
- the calls right after it identify every element and do nothing else: pywin32
  wraps (`GetTypeInfo`), `early_bound` QueryInterfaces, and one identity read
  per element (`*.Name2`, or `IDrawingComponent.Name` for a drawing view's
  components);
- each build's names are distinct and are the same set in both builds.

When the array is bound, the new build is read as if SolidWorks had enumerated
in the base's order. The array's answer stays as recorded (the same numbers as
the base's), and the pre-pass is put in the base's element order. Each element
handle, including those the pre-pass allocated, is renamed to the base's handle
of the same-named component, in the pre-pass and in every later call. The
engine's comparison then runs on that stream. The diff keeps how many arrays
were bound and the positional divergence they replaced (`name_bound`; the
record and span carry `name_bound`, the count). A binding that raises is a
judge fault (`judge_faults` step `name_bound`), and the comparison stays
positional. Anything else stays positional too: a visit in enumeration order
(the explode authors' `by_name` dicts iterate in insertion order) or a request
on another component than the base's still diverges.

**Evidence copies.** A recording left unpublished because another writer's
bytes already stand under its key (`_replay_shadow.EVIDENCE_OF`:
`publish=exists`, the key's recording names held another's, as on a forced
refresh; `publish=lost`, another build committed the key's archive first, as
when two seats build one key) is the only copy of that build's conversation.
Unless its split is a `confirmed` `noop`, it is stored create-only under
`com-replay/<engine 16>/<kind>-<stem>/evidence/<key>/<recording id>.tar` and
`.json` (`_replay_shadow.evidence_names`; the manifest names that bundle and
carries `evidence_of`: split, judgement, cause, base key), outside
`manifest/`, so no lookup ever lists it as a base, and within the same
512 MiB bound. The record, the `replay.evidence` span and the INFO line
(`publish=<exists|lost> bytes=<n> evidence=<outcome>`) carry the outcome
(`stored`, `exists`, `error`, the cache's `skip`/`off`, or `oversize`).

`own_differing` counts the differing key inputs that are not child
identities. The seat path (`_com_outcome.seat_path`) is judged for these kinds
as for a part, since the same vendored selection fallback runs in their
scripts, on their own geometry (`_com_outcome.GEOMETRY`): an assembly's mass
and sidecars, a drawing's PDF ink. A `noop` never has a seat path; a
`diverged` one whose requests differ only by detours on the same geometry is
`seat_path_divergence` (counted, never an alarm).

**What a replay would need.** Each summary and manifest carries
`replay_gaps`, measured on the recording (`com_replay._replay_gaps`): `argv`
(arguments the engine's replay would not pass), `out_paths_unredirected`
(output-root paths the log names outside `sldprt/`, `sldasm/`, `png/` and
`stl/`, the only ones the replay redirects: a drawing's `slddrw/` and `pdf/`),
`out_inputs` (named output-root files the log did not capture as written: the
models it opened, which a replay would have to stage at their recorded bytes)
and `python_out_reads` (output-root files the script's own Python read, an
upper bound). Their counts size a second engine identity for these kinds.

**Bounds and cost.** Every recording name fits the farm's path budget with 32
characters to spare (`test_every_dependent_recording_has_a_name_of_its_own_within_the_path_limit`);
an assembly's or drawing's bundle whose files exceed 512 MiB on disk
(`bundle_size`) is never built in memory, published or kept
(`publish=oversize`). On 788 recorded
part builds (2026-11-12) the recorder cost 1.8% of the window at p50 and 2.8%
at p95, at 101 recipe requests per window second (p95 156) and 176 bundle
bytes per request (p95 680); the diff took about 3 s plus 0.5 ms per request.
At those rates a 1,500 s assembly would add 30 to 45 s on the seat and log up
to 2.4e5 requests, about 2 minutes of diff. The comparison runs inside the
leaf's doit action, after the store but before the leaf's process exits and
reports, so on a farm worker it holds the leaf's slot with the seat idle: it
is capped at 60 s (`DEPENDENT_SECONDS`), which judges builds of up to about
1e5 requests and reads `timeout` for the largest assemblies. The INFO line
shows the seat cost as `record=+<engine and audit s>/<window s> <percent>`:

```text
[com-replay] drawing:pn_pen: evaluated | publish=stored bytes=2310144 | lookup=found base=9c1e04b2a7f3 differing=2 own=1 listed=4 read=4 0.388s | split=noop same_children=3/4 41.2s | truth=same | outcome=same cause=- | record=+12.41s/598.7s 2.11%
```

The three-way split per stem:

```kusto
dependencies
| where timestamp > ago(7d) and name startswith "replay.split "
| extend label=tostring(customDimensions.label),
         kind=tostring(split(tostring(customDimensions.label), ":")[0]),
         split=tostring(customDimensions["replay.split"]),
         cause=tostring(customDimensions["replay.truth_cause"]),
         nondeterminism=tostring(customDimensions["replay.output_cause"]),
         unexplained=tolower(tostring(customDimensions["replay.unexplained_output_divergence"])) == "true",
         echo=tolower(tostring(customDimensions["replay.title_echo"])) == "true",
         detour=tolower(tostring(customDimensions["replay.seat_path_divergence"])) == "true"
| summarize judged=count(), noop=countif(split == "noop"),
            diverged_request=countif(split == "diverged" and cause == "request"),
            diverged_seat=countif(split == "diverged" and cause startswith "response:"),
            seat_path=countif(detour),
            children_changed=countif(split == "children_changed"),
            children_unknown=countif(split == "children_unknown"),
            no_judgement=countif(split !in ("noop", "diverged", "children_changed",
                                            "children_unknown")),
            title_echo=countif(echo),
            seat_display=countif(nondeterminism == "seat_display"),
            jagged_outline=countif(nondeterminism == "jagged_outline"),
            answers=countif(nondeterminism == "answers"),
            unexplained_output=countif(unexplained)
            by kind, label
| extend noop_share=round(1.0 * noop / max_of(noop + diverged_request, 1), 3)
| order by kind asc, judged desc
```

The seat cost per kind:

```kusto
dependencies
| where timestamp > ago(7d) and name startswith "replay.record_overhead "
| extend kind=tostring(split(tostring(customDimensions.label), ":")[0]),
         seat_s=todouble(customDimensions["replay.engine_s"])
                + todouble(customDimensions["replay.escape_audit_s"]),
         pct=todouble(customDimensions["replay.overhead_pct"])
| summarize builds=count(), p50_seat_s=percentile(seat_s, 50),
            p95_seat_s=percentile(seat_s, 95), p50_pct=percentile(pct, 50),
            p95_pct=percentile(pct, 95) by kind
```

## Native projected geometric-control zones

The canonical `_gtol_controls.GeometricControl.projected_zone_height_mm` is optional:
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
before any projected XML is applied. The enrolled `test_gtol_contracts.py` and
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
`OpenDoc6` (never `OpenDoc7`, whose ViewOnly spec cannot be told from a load still
in progress); the target is closed in `finally`, even after a
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
`test_gtol_contracts.py` also covers canonical writer capture and ordinary-path bypass.
These authored tests are pending parent centralized checks and native farm proof.

## Native equation-curve stock gaps

`_gear.equation_curve` is the canonical stock-gap curve creator. `_gear` uses
it internally and `build_dt_cone_gear` imports it directly. It preserves the
authored expressions, range `[0, 1]` and locked endpoints while using
`ISketchManager.AddToDB=True` to avoid creation-time snapping/inference. The
native BOOL property is checked after enabling and after restoring its previous
value in `finally`; DEBUG records show the actual before/enabled/restored values.

`ensure_fully_defined` remains strict. Its explicit equation-curve FIX whitelist
may target only registered equation curves whose actual `ISketchSegment.Status`
is `swUnderConstrained`. Already fully-constrained curves are skipped; unknown,
invalid, over-constrained, no-solution and autosolve-off entity statuses refuse.
The sketch must report fully defined before any consuming feature is created.
There is no automatic relation deletion or over-defined status waiver.

Both entry and post-FIX `over_defined` results log ERROR evidence for every
`ISketchRelationManager.GetRelations(swAll)` relation before raising. Records
include raw relation/entity types, typed point/segment IDs and constraint
statuses, nullable entries, document path, sketch constrained status and
read-only `AddToDB`/`AutoInference`/`AutoSolve` observations. Separate
`swOverDefining`, `swDangling` and `swBroken` inventories report native filter
results. `ISketchRelation` has no `SolveStatus`, `Status` or `IsDangling` accessor:
relation solve status stays UNKNOWN rather than joining fresh wrappers by
Python identity. Failed reads remain unavailable evidence, not empty proof;
diagnostic failure never masks the strict sketch failure. Before-FIX and
successful final inventories are DEBUG only; the escalation WARN remains.
