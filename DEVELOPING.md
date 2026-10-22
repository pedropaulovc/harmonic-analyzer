# Developing — local workflow notes

Practical, machine-local development notes that don't belong in `AGENTS.md`
(orientation) or the per-topic policy docs: local pytest timing, supervised farm
launches and the remote build cache.

Running ONE SolidWorks operation by hand (this checkout has no local seat, so it
goes to the farm)? Read
[`cad/docs/one-off-com-operations.md`](cad/docs/one-off-com-operations.md) first
— it is the decision tree, the seat/cache invariants and the evidence trail for
an ad-hoc COM operation, and it links back here for cache detail.

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

## Process traveler prerequisites

`prechips:<stem>` tasks run on the submitter, including when SolidWorks leaves
run on the farm. They need **FreeCAD 1.1** there; the Python dependency
`prechips==0.2.0` does not install the FreeCAD executable. prechips discovers the
Windows FreeCAD 1.1 installation or a command on `PATH`; set `FREECAD_CMD` when
it lives elsewhere:

```powershell
$env:FREECAD_CMD = "$env:LOCALAPPDATA\Programs\FreeCAD 1.1\bin\freecadcmd.exe"
uv run --frozen python -c "import prechips.kernel as k; print(k.discover_kernel())"
```

An unavailable kernel is a failure, not a geometry pass: required-unknown
findings exit 4 and the strict task accepts only exit 0. Enrollment is currently
empty, so ordinary builds do not run the stale tracked plans. Before enrolling
a migrated part, follow the binding and validation loop in
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

The startup-retry cases in `test_machinist_review.py` use a test-local MCP
poll clock and a fixed number of pending responses. A proxy of only that test's
`machinist_review.asyncio` binding arms a real startup `Timeout` when polling
consumes the unchanged 0.75-second budget; neither global asyncio nor the event
loop's clock is modified. Windows launch/pipe scheduling stays under the real,
unchanged overall timeout instead of consuming the synthetic startup budget.
Real cancellation/reaping, the local Python protocol child, 131-KB pipe draining,
no prompt before connection and two attempts remain exercised. Separate slow-start
and shared-overall-timeout tests still use real time.

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
Waits log every 30 seconds, with no queue deadline or failed-check retry.

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
  and prefixes exit 2 before joining the FIFO. Preflight normalizes PoolHome's
  full `agent_identity` with the pool's own `agent_identity_tag` and compares
  every current worker's reported `agent_version` tag in the existing fleet
  query. Mixed, missing or mismatching tags also exit 2; check out the deployed
  pool release at PoolHome, or finish the rollout before submitting.
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

### First-miss preparation and publisher ownership

Use an updated, committed pool checkout at the existing `-PoolHome`, with the
matching full agent identity deployed to the fleet. Remote misses require its
preparation publisher/readiness API and `agent/process_tree.py`; there is no new
producer package pin, adjacent-checkout fallback or automatic deployment. The
existing admission subprocess reads readiness from that exact PoolHome. Missing
preparation capability/configuration or a failure of this optional probe does
not itself reject cache-hit-only work. Probe failures carry only a sanitized
exception type, not configuration/error text. The first real remote miss refuses
unready preparation before that leaf connects or reserves capacity. Mandatory
identity, fleet admission and producer registration still apply to every build.

The first actual remote miss publishes the source/graph preparation once for the
build, before leaf dispatch. A cache-hit-only build does not publish or eagerly
export the graph. Producer registration and acknowledged lease still precede the
doit scheduler; publication is lazy within that scheduler, not a new registration
gate. Authentication, corrupt-artifact and publication errors surface rather than
silently reverting to another preparation path.

Spawned action processes coordinate through a `FileLock` and atomic receipts in
`HARMONIC_FARM_REQUESTS/preparation/`. The key includes the full build, source and
agent identities plus canonical repository and PoolHome roots. A successful
receipt is reused across processes; a failed publication is shared without a
fresh publisher retry in the same build. The receipt enters `publishing` before
the private body starts, so a crashed owner cannot be mistaken for a safe retry.
The nested directory does not add preparation records to the launcher's
root-level workflow request inventory.

Readiness declares one **900-second operation deadline** and a **10-second
supervision margin**. The original absolute deadline starts before receipt-lock
waiting and uv/Popen setup; later phases cannot acquire another 900 seconds.
Process and receipt-lock waits use slices of at most one second and observe
pending `asyncio.Runner` task cancellation, including the first SIGINT.
The margin is only for terminal-receipt observation and cleanup, not new
publication work. Owned-tree cleanup gets one deadline
`min(now + 5, operation_deadline + 10)` shared by termination and reaping.
These bounds do not change native-leaf budgets, FIFO grace or build lifetime.
Every publication deadline, remaining-time calculation, elapsed metric and
cleanup subtraction uses the selected pool's `publication_clock()` authority
(`perf_counter`). Do not mix it with `monotonic()` across Windows Python 3.12
and 3.14 processes. The cross-interpreter clock proof covers CPython 3.12–3.14;
reverify it when upgrading the toolchain. Native/FIFO duration clocks are unchanged.

HA loads the selected pool's pure private-body argv/receipt helpers and invokes
that body through its existing, sole `ProcessTree`; it does not invoke the
supervising public CLI/API underneath another job or process group. Stdout and
stderr remain inherited stage diagnostics; the bounded, parent-owned receipt
is separate and decoded by the selected pool's protocol authority. Every result
requires confirmation that the created tree stopped, even after a normal root
exit. Windows creates the root suspended and assigns its Job Object before
resuming it; POSIX confirms the owned root and process group. An uncertain
adoption kills only the stored root handle before terminating/reaping its owned
tree. No process-name kill or pre-existing SOLIDWORKS seat is involved.
Unconfirmed cleanup raises `PoolProcessCleanupError`, retains owned result
storage, and leaves the shared receipt nonterminal.

The launcher's requests root remains launcher-owned. An attended direct build
without an inherited requests root owns a temporary root for its producer/action
worker lifetime. Any primary exception, interrupt, nonzero runner result or
completion without an explicit zero-success outcome retains that owned requests
root without scanning or deleting it: doit may still have unjoined processes or
threads that have not reached their preparation lock yet, even when it converts
`InvalidTask` to return code 2 instead of raising. A missing receipt is not
cleanup evidence on these paths. Existing failures retain their outcome and
receive a warning naming the retained root; primary exceptions also receive a
note and are not replaced by a secondary cleanup fault.

Only explicit zero-success, joined runner completion permits cleanup. The normal
doit process and thread paths join their workers before returning. Cleanup then
requires canonical, matching-build terminal preparation receipts and nonblocking
free locks. Nonterminal, corrupt,
unreadable, mismatched, unknown or aliased preparation entries retain the root.
An otherwise successful build still fails loudly when retention is required or
directory cleanup fails. Inherited launcher-owned roots are never deleted here.
Preserve diagnostics and do not edit/delete a receipt or lock to retry inside
the same build. Establish that all owned publishers stopped before recovery
through a fresh build identity.
There is no automatic sweep of retained failed-build roots. After preserving the
diagnostics and confirming that the build's runner and publisher process trees
have exited, remove only the exact owned root named in its warning; do not use a
wildcard sweep that can include active builds.

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

This retains JSON telemetry capture while preventing the default local OTLP
endpoint from adding exporter timeout delays. An **11-second head** is also a
target, not an established portfolio result.

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
tracked image, `release.yaml` and migrated/enrolled process-plan revision updates. Launch
with `-Targets "build,export,package:release,preflight"` (`build` supplies drawing,
check and enrolled traveler gates). Once successful, restore the complete `cad/out` from the
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
registry implementation, recorded under `cad/out/.drawing-registry/`. Adding or
editing another row does not invalidate an independent drawing. Shared helper,
template, schema and source-model identity changes still invalidate it. Consumers
that read other rows or use an unclassified registry access retain the full
registry dependency.

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
directly. An enrolled `prechips:<stem>` depends only on its own feature leaf.
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
`part:ch_rocker_arm_tl_vn_oblique_rail`) emits a
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
and verification have separate timing spans.
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
