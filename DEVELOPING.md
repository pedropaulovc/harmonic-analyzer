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
`farm_build.py` runs home), project cache/review-scratchpad directories,
and checkout-specific Claude directories under `LOCALAPPDATA`.
`HARMONIC_AGENT_SCRATCHPAD` adds both `harmonic-analyzer/farm-runs` (retired
launcher runs) and `harmonic-analyzer/machinist-review-evals`. Without that
override, running from an OMP `local` working directory (`OMPCODE=1`) adds its
`harmonic-analyzer/farm-runs`. Other sessions' OMP local
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
directory at `cad/out/reports/machinist-review/<stem>/`. A confirmed finding in
any gating category, blockers included, gates only when at least two of the
three runs raised it. The aggregate JSON and
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
caching the error. Review keys hash the PDF's ink, package exceptions, review code/import
closure, the selected kind's reviewer/severity prompts, shared reviewer/judge
prompts/schemas, the drawing guidelines' frontmatter `major_version` (not the
file's bytes; bump it when an edit should change verdicts) and the effective reviewer and judge
selections below, not the registry, enforcement declaration, recipe-skipped
infrastructure such as telemetry, or `pyproject.toml`/`uv.lock`: a dependency
release changes transport, not the verdict's inputs (#2882).

The PDF's ink is `_pdf_ink_digest.pdf_ink_digest`: every page's size, printed
characters and 144 dpi grayscale PDFium raster, with no tolerance. Two exports
of an unchanged drawing differ in export time, document `/ID` and font-subset
tags only, so a rebuild that prints the same sheet keeps its verdict, `SHIP`
or `FIX`, and one changed pixel or character misses the key (#2714).

On a key miss the leaf tries to carry a verdict (`_review_carry`, #2714): it compares the PDF
with the newest eight PDFs reviewed for that drawing under the same non-PDF
review inputs (`_machinist_review_context`, the review key without the PDF)
using the release drawing diff's page rule, `_drawing_diff.compare_drawings`:
the same page count and sizes, the same printed characters outside the BUILD/REV
values, and every ink pixel within 1 px of ink in the other PDF unless its grey
changed by 68 levels or less. A match stores that review's verdict, `SHIP` or
`FIX`, under the new key with `carry/provenance.json` naming the reviewed PDF's
key and SHA-256 and each page's stamps and differing-pixel count
(`review_carried` in `cache.jsonl`; a subdirectory, because `machinist_review.py`
reads every top-level `*.json` of a report directory as a review). So a
revision-stamp change or a one-pixel move rolls no reviewer, and a changed
character, a larger move, an extra page or a PDF that cannot be compared is
reviewed afresh. This is the owner's ruling of 2026-11-14 on #2714, and the
comparator's documented limits (its module docstring) now apply to verdict
reuse: a low-contrast edit, or one within a pixel of existing ink, that changes
no character carries the earlier verdict. The index is one create-only sidecar
per reviewed PDF, `machinist-review/epoch-<epoch>/<stem>/<context>/<review key>.pdf`,
written on a fresh review, a hit or an adoption, never for a carried verdict,
so every carry is measured against a sheet the reviewers saw. The search and
restore run in a `cache.carry <label>` span.

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
uv run python farm_build.py run build --leaf-timeout 90 `
    --display-name 'Summing lever - Codex high review' --tag summing-lever-codex-high
```

`farm_build.py` passes these inherited process variables through to the build
in its private snapshot; the reviews execute on that submitter, not on the
SolidWorks workers. Set them in the shell that runs `farm_build.py run`, not in
a different terminal after launch. No tracked config edit, `HARMONIC_CACHE_SALT`,
or forced cache refresh is needed. The standalone `cad/scripts/machinist_review.py` continues to use its
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

### Machinist-review sweep

A cached verdict stands until the sheet's ink changes, so a review that was
lenient once is never asked again. The opt-in `review_sweep` task (#2714)
reviews older sheets again without blocking anything. It is not in `build` or
`release`, never fails the invocation on a FIX, a finding or a review error
(only a malformed `HARMONIC_REVIEW_SWEEP_DAYS` is refused), and never replaces
a cached verdict:

```powershell
$env:HARMONIC_REVIEW_SWEEP_DAYS = '30'   # default; a whole number of days, or 'all'
uv run python farm_build.py run review_sweep:dt_pinion_cam review_sweep:sm_summing_assembly `
  --display-name 'review sweep' --leaf-timeout 150
```

`review_sweep` sweeps every drawing that opts in; `review_sweep:<stem>` sweeps
one. Each sheet first runs the build's own review leaf in LEARN. The leaf
restores, adopts or carries the verdict, or reviews a sheet that has none and
stores that verdict under its key, as a build would. If the verdict is a
review of this ink no older than `HARMONIC_REVIEW_SWEEP_DAYS`, the sheet is
`fresh`; if the leaf just reviewed it, it is `reviewed`. Otherwise (a carried
verdict, an older review, or `all`) the sheet is `re-reviewed` into
`cad/out/reports/review-sweep/<stem>/`. Expect about 2 minutes and $2.40 per
review. A teardown writes `review-sweep/summary.{md,json}` and one issue
draft, `review-sweep/issues/<stem>.md`, for each sheet whose fresh review
returned FIX with gating findings. The summary and drafts cover only the
sheets swept by that invocation; older records are deleted. A sweep and a
build's `check:machinist_review:<stem>` selected together take turns on a
per-drawing lock, so they never pay for the same review twice.

To file the drafts, one issue per sheet:

1. Read each finding against the sheet (`cad/out/pdf/<dashed stem>.pdf`) and
   delete from the draft every finding the sheet refutes; skip the sheet when
   none remain.
2. Look for an open issue first:
   `gh issue list --state open --label kind:dfm --search "<stem> in:title"`.
3. If one covers the sheet, add the remaining findings to it as a comment
   (`gh issue comment <N> --body-file <draft>`). Otherwise
   `gh issue create --label kind:dfm --title "<stem>: machinist-review sweep findings" --body-file <draft>`.

The sweep's own review does not change the build's verdict. To act on a
finding, change the sheet: the new ink is reviewed by the next build.

## Holistic review telemetry

Each aggregate emits one `machinist_review.aggregate` span, with a
`machinist_review.run` child per blind run and a `machinist_review.judge` child
when findings are judged. This is separate from `layout.audit`. On completion
the aggregate span carries `verdict` (`SHIP`, `FIX`, `ERROR`); requested
`run_count`, `completed_run_count`, `valid_run_count`, run `error_count`,
`input_finding_count`, `confirmed_count`, `rejected_count`, `gating_count`,
`judge_executed`, aggregate `error`, package `name`/`kind`, reviewer/model and
judge reviewer/model.

A `SHIP` can have partial run errors; use the counts to assess completeness. A
valid zero-finding review does not execute the findings judge. Caught failures
are represented by these attributes, not necessarily the SDK span status. These
signals do not alter the approval JSON or acceptance rules.

In Application Insights, these internal spans are in `dependencies`, with
attributes in `customDimensions`. The following queries count **observed
attempts**, not unique packages; ingestion can lag and sampling/retention can
limit observed totals. With Azure CLI, use `--offset 2h` (or a wider explicit
window) as well as the KQL time filter.

Completed aggregates in the last two hours:

```kusto
let completed = dependencies
| where timestamp > ago(2h) and name == "machinist_review.aggregate"
| extend package=tostring(customDimensions.name),
         package_kind=tostring(customDimensions.kind),
         verdict=tostring(customDimensions.verdict),
         error=tostring(customDimensions.error),
         completed_runs=toint(customDimensions.completed_run_count),
         valid_runs=toint(customDimensions.valid_run_count);
completed
| summarize attempts=count(), ship=countif(verdict == "SHIP"),
            fix=countif(verdict == "FIX"), errors=countif(verdict == "ERROR")
```

For the latest completed result per package **within this two-hour window**,
replace the final summary with the following. This is not an all-time package
approval inventory, and does not include a newer in-flight aggregate.

```kusto
completed
| summarize arg_max(timestamp, *) by package, package_kind
| project timestamp, package, package_kind, verdict, error, completed_runs,
          valid_runs, operation_Id
| order by timestamp desc
```

## Process travelers

`build` and `release` run every enrolled `prechips:<stem>` task, so a build
that produces the drawing PDFs also produces the traveler PDFs; `build_bare`
runs none. `release` ships each part's hobby sheet, which is the part's CNC
setup sheet, as `travelers/<slug>-traveler.pdf` in the
bundle (owner ruling 2026-11-14). prechips is not in `uv.lock`
([#2502](https://github.com/pedropaulovc/harmonic-analyzer/issues/2502)); the
wrapper runs the latest PyPI release with `uv tool run` outside the project
environment, logs its version once and records it on its spans, so it needs
`uv` and network access to PyPI. It prints the PDF with a headless Edge or
Chrome, found on `PATH` or at its default install location; set
`HARMONIC_PDF_BROWSER` to name another Chromium-family browser. The tasks run
on the submitter, including when SolidWorks leaves run on the farm, and always
run when requested. To render a part's travelers (`traveler.html` under
`--profile pro`, `traveler-hobby.html` under `--profile hobby` with setup
pictures, and that hobby sheet printed to `<slug>-traveler.pdf`) after its
scoped feature bundle exists under `cad/out/features/<stem>/`:

```text
uv run --frozen python -m doit prechips:<stem>
uv run --frozen python cad/scripts/prechips_traveler.py <stem>
uvx --from prechips@latest prechips traveler cad/process/<stem>/plan.toml --profile hobby --out <file>
```

The doit task also runs its `package:manifest:<stem>` task first, which needs
the `package:features:<stem>` leaf (a cache restore, or a SolidWorks leaf on a
miss). Without SolidWorks or a farm run, fetch the bundle from a release first,
then use the wrapper or `uvx` form:

```text
uv run --frozen python cad/scripts/fetch_features.py <stem> [--release vNN]
```

Releases cut after v50 carry the bundle of every part with its own drawing
under `features/<stem>/` (v50 and earlier carry only the parts whose drawing
declared requirements; asking one for another part fails with "the release
carries no ... bundle"). Releases cut with face inventories also carry, beside
each labelled STEP, its `.faces.json` inventory. The script range-reads only
those members of the release ZIP and refuses a bundle that does not bind its
STEP. It rebinds `features.toml` to this checkout's requirement declarations
over the fetched STEP, so a new or changed `requirement(...)` needs no farm,
and reports the bundle STALE (exit 2, nothing written; there is no override)
when the part's geometry inputs (`part:<stem>` or the labelled-STEP exporter)
differ between the release's tag and the working tree. A release that predates
face inventories can be neither rebound nor validated, so it is always STALE
(use a newer release). A
stale part needs a farm build of `package:features:<stem>`. A bound
`features.toml` records its geometry inputs' digests (`[geometry_inputs]`),
and the traveler wrapper and `cam_nc.py` refuse (exit 2, naming each changed
input) a bundle without them or built from other geometry, such as one copied
from another worktree; `fetch_features.py --check <stem>` reports the same
without fetching. After editing declarations on top of a local bundle,
`uv run --frozen python cad/scripts/fetch_features.py --rebind <stem>` rebinds
it (`export_features.py <stem>` alone writes no geometry inputs).

How a bundle gets its stamp depends on where it came from:

- **A release asset:** `fetch_features.py <stem>` stamps it, or reports it STALE.
- **A doit or farm build** of a commit with #3668 or later: `package:manifest:<stem>` stamps it.
- **Restored by hand** (the labelled STEPs and `.faces.json` inventories copied
  from a farm run's `out/features/<stem>/`, or a bundle bound before #3668):
  `uv run --frozen python cad/scripts/fetch_features.py --trust-step <stem> [--out cad/out]`
  binds `features.toml` from this checkout's declarations and stamps this
  checkout's geometry inputs. It cannot see what the STEP was built from and
  says so per part (`TRUSTING the STEP`). Use it only on a STEP built from this
  checkout's geometry inputs: a farm run of this commit, or of one whose
  `--check` findings would be empty. Exit 1 means there is no STEP or
  inventory, or the bundle does not validate; nothing is written.

Only exit 0
from both profiles and a printed PDF is success. Exit 2 from either profile is
a prechips refusal (bad input or a failed enforced check) and leaves no
traveler file; exit 1 means uv itself failed (no `uv`, no PyPI, or a `uv tool
run` error before prechips ran) or the browser was missing or failed to print.
Plan authoring and the shop files are described in
[`cad/process/README.md`](cad/process/README.md).

## NC programs

Milled parts are made on the CNC-converted PM-30MV (owner ruling
2026-11-17; the lathe stays manual). `build` and `release` run every enrolled
`cam:<stem>` task (each part with a `cad/process/<stem>/cam.py`; the rocker strap is the first),
and `build_bare` runs none. Each one runs the part's
`cad/process/<stem>/cam.py` recipe in headless FreeCAD and writes one G-code
file per program, `cycle_times.json` and `manifest.json` to
`cad/out/nc/<stem>/`; `release` ships them under `nc/<stem>/` and the cut
fails if any is missing or stale. The tasks run on the submitter (no farm
worker has FreeCAD), so the submitter needs FreeCAD 1.1 or later:
`$HARMONIC_FREECAD` names `freecadcmd`, otherwise the newest `FreeCAD
<version>` install is used, and the task fails when there is none. To post one
part's programs after its scoped feature bundle exists (from a build, or
`fetch_features.py` as above; `cam_nc.py` skips doit's feature leaf):

```text
uv run --frozen python -m doit cam:<stem>
uv run --frozen python cad/scripts/cam_nc.py <stem>
```

Recipes and their checks are described in
[`cad/process/README.md`](cad/process/README.md).
Posted NC is not machining approval: prove each program in air and check the
setup against the traveler first.

## Local pytest timing

Run the CAD and pipeline suite serially for comparable timings:

```text
uv run --locked python -m pytest -q --durations=50 --junitxml=<outside-worktree>/cad-pytest.xml
```

The configured suite covers `cad/scripts`, `cad/comparisons/tools` and `tests`,
including offline diagnostic tests.

Use an isolated worktree at a recorded commit and the same environment for
before/after runs. JUnit case times include fixture setup and teardown; a shared
fixture's cost is charged to its first consumer. Collection and session overhead
remain part of the suite wall time. Before collection imports any product
module, the root conftest turns the remote cache off, drops inherited farm run
settings (`HARMONIC_EXECUTOR`, `HARMONIC_FARM_*`, the `farm.execution` resource
attribute) and cache/Azure credential variables, points `SOLIDWORKS_POOL_CONFIG`
at a file that does not exist, sets `HARMONIC_SW_AUTOSTART=0`, blanks the
OTLP endpoints and redirects telemetry capture (`HARMONIC_TELEMETRY_DIR`) to a
per-session scratch directory; a test of any of these sets it explicitly. It
also isolates the buildgraph facts cache in a temporary directory, and refuses
`_watchdog._hard_exit` like a launch instead of ending pytest. On the main
thread the refusal fails the test. From a watchdog or deadline thread it also
interrupts the main thread: a deadline block busy in Python code then fails its
test, while a block in an untimed C-level wait or an interrupt outside any
deadline still hangs or aborts the run (#3182). Keep `NOSW_GUARD`
enabled and leave `HARMONIC_BUILDGRAPH_CACHE` unset. With the guard on
(Windows only), a test
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
which skips the child guard.

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

`check:recipe` runs every `test_*.py` a bare `pytest` collects from pyproject's
`testpaths` (honouring `norecursedirs`), except the files a dedicated gate owns
(`dodo._GATE_TESTS`) and the files in `dodo._UNGATED`, with
`pytest -q -p no:cacheprovider --collect-in-virtualenv -n 8 --dist worksteal`.
A new test file needs no enrollment; a test file that must not run in a gate
goes in `dodo._UNGATED` with its reason. dodo hands
pytest the collected file list, so `--collect-in-virtualenv` only skips repeated
parent-directory virtualenv-marker probes. Do not apply it to normal recursive
pytest discovery. The gate's `file_dep` is each collected test plus its
`module_deps_of` closure, plus the runtime-read inputs listed in
`_check_recipe_spec`; the collected inventory is also an `uptodate` value, so a
deleted test file re-runs the gate.

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
hook. That commit predates `farm_build.py` (which refuses such commits), so
launch it with the checkpoint's own `scripts/farm-run.ps1`: target
`assembly:pn_pen`, leaf timeout 90, display name
`DisplayData - Reproduce pinned pn matrix`, tag `display-data-repro`.
Retain the recorded run and use the protocol-compatible pool; do not invoke the
probe locally or transplant its hook into production.
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

## Farm builds (`farm_build.py`)

A farm build outlives every agent turn and every harness deadline: a cold
`build` closure runs for hours, and one leaf alone has measured 61.5 min.
[`farm_build.py`](farm_build.py) is the one entry point for it, for agents and
attended terminals alike (`build.py` is local-only):

```
uv run python farm_build.py run TARGET... --display-name "Owner - Why" --leaf-timeout MIN
        [--force-cache-refresh LABELS --force-cache-refresh-reason TEXT]
        [--tag T] [--worktree PATH] [--pool-home PATH] [--watch] [--runs-dir DIR]
uv run python farm_build.py watch  <run-id | tag> [--poll-seconds S]
uv run python farm_build.py status <run-id | tag>
uv run python farm_build.py list   [--tag T] [--state S] [--max-age-hours H]
uv run python farm_build.py cancel <run-id | tag> --why TEXT [--binding-wait-seconds S]
```

`run` validates its arguments and the worktree, writes `run.json`, starts a
detached supervisor (through a short-lived trampoline, breaking away from the
caller's job when Windows allows it, so no parent chain or harness tree-kill
reaches it) and waits only until the build has passed its preflight and
recorded its FIFO `build_id` (exit 0), or has stopped (that exit code). It never
retries, never cancels remote work and imposes no deadline. The supervisor:

1. joins a named kill-on-close Windows job (`job` in `run.json`) before it
   starts anything, so every process of the run dies with the supervisor and
   nothing can keep dispatching after it;
2. prepares a private snapshot of the commit
   ([the build snapshot](#the-build-snapshot));
3. runs `uv run --frozen python farm_build.py _build <run-dir>` from the
   snapshot, with `HARMONIC_REMOTE_CACHE_MODE=rw` and `SOLIDWORKS_POOL_HOME`;
   its output goes to `build.log`;
4. moves the snapshot's `cad/out` to `<run-dir>/out`, removes the snapshot and
   writes `status.json`.

The `_build` child is the commit's own farm client: it loads the commit's
`dodo.py`, runs the preflight below, then runs doit as
`run -n 8 --continue <targets>` inside the FIFO producer (`HARMONIC_FARM_PARALLELISM`
overrides 8). doit stays the local scheduler (freshness, cache restore, the
SolidWorks-free `check:*` tasks); every cache-missing COM leaf runs on the farm
(`dodo._cached_com_action` → `dodo._farm_build`). Eight leaves in flight keep
every worker busy; a hard-coded `-n 4` against five workers kept one idle for
88% of a cold build (2026-09-28, build `20260928T150817352Z`). `--continue`
collects later failures; any failed task still leaves the run nonzero.

### Prerequisites and refusals

`run` refuses with exit 2, before writing anything, when:

- the worktree has any uncommitted change or untracked file, or its HEAD is not
  reachable from a locally known `origin/*` ref (every leaf fetches that exact
  SHA; fetch and push first);
- a target is empty, starts with `-`, contains `=` (doit would take it as a
  command-line variable and build the default closure instead) or is `release`
  (see [farm releases](#farm-releases)); targets may also be comma-separated;
- `--display-name` or `--force-cache-refresh-reason` breaks the label rules
  below, a reason comes without refresh labels, or `--leaf-timeout` is outside
  1–180 minutes;
- the pool home (`--pool-home`, else `SOLIDWORKS_POOL_HOME`, else
  `../solidworks-pool`) lacks `farm.py` or `agent/protocol.py`;
- the runs directory is inside a Git worktree (snapshots are created under it).

The build's preflight runs before any producer registration, build ID or leaf
request. An unknown task exits 3 (doit's invalid-command code, naming it). Exit 2
follows, with a `farm:` diagnostic, when: the display name is invalid; a
would-be leaf anywhere in the requested closure is refused by the pool's
`agent/protocol.py` `leaf_admitted` (loaded in-process from that file, so no
installed `agent` package can answer for it; deliberately conservative for
`-s` and cache hits); a forced-refresh label is unknown, outside the selected
closure or not cache-keyed; the `check:undefined_names` Ruff scan fails; or the
fleet does not support farm protocol **7** (`farm.py agents --json`: a
`mismatch`/`unreadable` verdict, or only aged-out reports that are incompatible).
After preflight, `HARMONIC_FARM_ADMITTED_LEAVES` carries the admitted labels
to every action process; `run_leaf(task, cache_key)` refuses any task absent
from it before any request, span or reservation. The worker independently
limits its exported graph to the build/release closure.
Mixed agent versions are expected during rolling upgrades and are not checked;
the protocol version is. Azure credentials for the cache are required (`az login`).

Labels (`--display-name`, `--force-cache-refresh-reason`) are nonblank,
single-line, valid Unicode, at most 160 code points, with no control
characters (`Cc`), line/paragraph separators (`Zl`, `Zp`) or `Bidi_Control`
characters, so a label cannot spoof adjacent dashboard text; Arabic/Hebrew text
and emoji (including joiners) are fine. Use owner/session plus reason, e.g.
`--display-name 'InchPD - Add new drawing detail view to pd_transgear_stub v3'`;
a label starting with `-` needs `--display-name=-…`. The label becomes the
coordinator-authored Temporal memo `display_name`; the run id is the separate
`farm_run` metadata. Neither enters the workflow ID or cache key: protocol 7's
build-scoped workflow ID is `leaf:<build_id>:<task>:<cache key or
commit[:16]>:<timeout_s>s`, bound to one exact run. Builds reuse cache
artifacts but never attach to another build's execution.

Task names use prefixed underscores (`part:pn_pen_rod`), never dashes.
Canonical stems and drawing Numbers are defined in the
[subsystem identity guide](cad/docs/subsystem-identities.md); its migration
table translates identifiers recorded in older runs.

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

A farm key is computed on the submitter from its files, while every worker
builds the launch commit. If the submitter's tree changed mid-run (another
agent committing in the same worktree) the two would diverge: the worker
publishes the key for the launch commit and the submitter looks for another,
surfacing as `[cache_missing] exit 0` (#1114). So no build ever runs in the
caller's worktree:

1. `git worktree add --detach <runs>\snapshots\<12 hex> <commit>`, short-named
   to keep the deepest tracked path under `MAX_PATH`, with `core.longpaths`
   enabled for the run's own Git commands only.
2. `git submodule update --init --recursive` for every gitlink in the commit
   except those its `.farm-sources.json` `exclude_submodules` lists (the set the
   workers skip; possibly none). A commit without `farm_build.py` is refused.
3. The build runs `uv run --frozen` from the snapshot, so its environment is the
   snapshot's own `.venv` (uv hardlinks it from its cache in ≈ 7 s) and nothing
   touches the caller's worktree again. Commit or edit there freely.

Every snapshot starts with an empty `cad/out`, so `.doit.db` is fresh and each
task first looks for its key in the remote cache. Afterwards, whatever the
outcome, the snapshot's `cad/out` (restored artefacts, `.doit.db`,
`reports/cache.jsonl`, `reports/telemetry`) moves to `<run-dir>/out` and the
snapshot (with its `.venv`) is removed. If the move fails the snapshot holds the
only copy and is kept, `outputs` points into it, `cleanup_errors` says why and
the run is `failed`.

When a leaf reports `cache_missing`, or succeeds without its key, the
diagnostic names the remaining causes (`_farm.CACHE_MISSING_CAUSES`): a
differing `HARMONIC_CACHE_SALT`/account/container, or a recipe whose key is not
reproducible across machines.


### Farm releases

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

`farm_build.py run` refuses the `release` target: it would run in a disposable
snapshot, and cleanup would discard the publisher's post-release tracked image
and `release.yaml` updates. Run
`build export package:release package:manifest check:features_bound`
(`build` supplies drawing and check gates but binds only the enrolled parts'
`features.toml`; the release stages every feature bundle, so `package:manifest`
binds the rest and `check:features_bound` checks them, both on the submitter
and with no extra farm leaf, #3469). Once successful, copy the run's
complete `out/` (`status` → `outputs`) over the owning worktree's `cad/out`.
Then run `uv run --frozen python -m doit -s gallery`,
`uv run --frozen python -m doit -s prechips` (every enrolled traveler, rendered
from the restored feature bundles) and
`uv run --frozen python -m doit -s release -- vNN` there. The NC programs
arrive with the restored `out/`: the run's `build` posts them on the submitter,
which therefore needs FreeCAD 1.1+. This keeps the
gallery, travelers and publish in the owning worktree without local COM
redispatch; the cut fails if any traveler PDF or NC program is missing.

If the run was launched without `package:manifest check:features_bound`, its
restored `out/` lacks the other parts' `features.toml` (or, over a `cad/out`
that cut an earlier release, keeps that release's stale ones) and the cut stops
at `release.features_stage`. Bind every bundle seat-free in the owning worktree
before the cut. One `doit -s` invocation takes every task named on its command
line (doit clears each selected task's `task_dep`), so list them all at once
rather than one invocation per stem. Never run `doit -s` with no task named: it
would run the default `build` locally, SolidWorks included.

```powershell
$stems = @(Get-ChildItem cad/out/features -Directory | ForEach-Object Name)
if ($stems.Count -eq 0) { throw 'no feature bundles under cad/out/features' }
uv run --frozen python -m doit -s @($stems | ForEach-Object { "package:manifest:$_" })
if ($LASTEXITCODE -ne 0) { throw 'package:manifest failed' }
uv run --frozen python -m doit -s check:features_bound
```

Binding the 52 missing manifests of the 6d349882fd outputs with the tasks'
`export_features.py` took 226 s (about 4.3 s each), so all 133 take about ten
minutes; the doit invocation adds one graph load of about a minute.

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

### Tracking a run

Every command selects a run by id, or by `--tag` (its newest run), under the
runs root (`--runs-dir`, else `HARMONIC_FARM_RUNS`, else
`%LOCALAPPDATA%\ha-farm\runs`); a selection that matches nothing exits 2.
A run's state is derived, never trusted from one file: `status.json`'s `state`
when it exists (`succeeded`, `failed`, `cancelled`), else `running` while the
recorded supervisor (pid plus process creation time, so a reused PID never
counts) is alive, else **`launcher-died`**. Inability to read a process's
identity is an error, never evidence of death. Because the supervisor's job is
kill-on-close, `launcher-died` means its whole local tree is gone too; remote
leaves may still run.

- **`status`** prints one JSON object: `state`, `exit_code`, `build_id`,
  `commit`, `targets`, `display_name`, `leaf_timeout_minutes`, refresh labels,
  `cache_environment`, `supervisor` (`pid`, `created`, `alive`), `elapsed_s`,
  `log_idle_s`, `outputs` (the snapshot's `cad/out` while running, `out/`
  after; read `cache.jsonl` and `telemetry/traces.jsonl` from here), `counts`
  (cache `hits`, farm leaves `requested`/`succeeded`/`failed`/`in_flight`),
  every farm leaf, `unsettled_workflows` and `task_errors`.
- **`watch`** prints a line per leaf state change and per failed task, polling
  every `--poll-seconds` (15), and ends with the final status: exit **0**
  succeeded, **20** failed, **21** launcher-died (`LAUNCHER DIED` on the summary
  line), **22** cancelled. `run --watch` launches and then watches. Follow one
  leaf with the pool's `farm.py watch <workflow-id>`.
- **`list`** prints one JSON line per run, newest first.
- **`cancel --why`** terminates the run's job (every process at once, so the
  supervisor cannot record a `failed` outcome for its killed child) and the
  supervisor. If the build registered, it then closes producer ownership
  (`close_build … cancelled`: no new admissions; accepted reservations stay) and
  reconciles every `requested`/`bound` leaf through the coordinator: a recorded
  exact run is used directly, otherwise `leaf_status` is polled for at most
  `--binding-wait-seconds` (30). Only that exact bound run is cancelled, and
  only while `RUNNING` (`cancelled`, else `already-closed`); a typed
  `missing_closed` reply is `settled-untracked` and an operator-confirmed
  unbound `drained` reservation is `already-closed`. Anything else (pending
  reservation, `recovery_required`, a failed query) is unresolved: `cancel`
  exits 1 and changes nothing else, so retry the same command. Otherwise it
  preserves outputs, removes the snapshot and writes `status.json` with
  `state: "cancelled"`, `exit_code: null` and a `cancel` block (who, why, the
  supervisor's prior state, each workflow's outcome). On a finished run it only
  settles leaves still unsettled and keeps the run's own record. A successful
  remote cancellation does not prove native worker cleanup: capacity
  reassignment waits for the worker's physical-drain acknowledgement.

### Run records

Each run is one directory `<runs>\<run-id>\` (`yyyyMMddTHHmmssfffZ-<32 hex>`),
each file written atomically by the code that knows its contents:

| file | written by | contents |
|---|---|---|
| `run.json` | `run`, before anything starts | schema, `run_id`, `tag`, `display_name`, `targets`, `leaf_timeout_minutes`, refresh labels and reason, `worktree`, `git_common_dir`, `pool_home`, `commit`, `required_submodules`, `cache_environment`, `started_at`, `snapshot`, `environment`, `job` |
| `supervisor.json` | the trampoline | supervisor `pid` and `created` (FILETIME) |
| `build.log` | supervisor and build | Git, uv and doit output |
| `build.json` | the producer, before FIFO registration | `build_id`, `farm_run` |
| `leaves/<hash>.json` | `_farm._dispatch` | `task`, `workflow_id`, `build_id`, `farm_run`, `refresh_reason`, `state` (`requested` before submission — a failed write fails the leaf — then `bound` with `run_id`, then the result with `worker_id`, `attempt`, `exit_code`, `failure_category`, `failure_message`, `log_blob`) |
| `task-errors.json` | doit's reporter | each failed task and its last error line |
| `status.json` | supervisor or `cancel` | `state`, `exit_code`, `finished_at`, `elapsed_s`, `outputs`, `outputs_preserved`, `snapshot_removed`, `cleanup_errors`, `cancel` |
| `out/` | supervisor or `cancel` | the snapshot's `cad/out` |

Only exit 0 with outputs preserved is `succeeded`. `cache_environment` is
recorded because `HARMONIC_CACHE_ACCOUNT`, `HARMONIC_CACHE_CONTAINER` and
`HARMONIC_CACHE_SALT` move cache keys and workflow identity: an unchanged commit
is not by itself an unchanged key.

### Proof of a remote build

A `run` exit 0 means the build passed preflight; it does not prove any leaf
ran remotely. Neither a green `check:math` (local) nor a submitter cache hit
proves dispatch. A launch is proven remote only by all of: `status.json` with
`succeeded`/exit 0, a leaf record with a `run_id` and a real `worker_id`, a
completed `farm.run <task>` span naming that worker, a cache miss followed by a
restored artifact, and the artifact plus its `.execution` token in `out/`.

### Recovering a run across a handoff

Use `status` or `watch` on the recorded run:

1. **`running`.** Keep watching. Do not start another submitter for this work.
2. **`succeeded`, `failed` or `cancelled`.** The local outcome. Diagnose from
   `task_errors` and `build.log`. A failed or cancelled submitter can still have
   accepted remote reservations to settle.
3. **`launcher-died`** (watch exit 21). The local outcome is unknown and
   accepted remote work is not cancelled by losing the submitter. Not
   permission to relaunch: run `cancel` first.

`cancel` proves local stop, producer close and exact-run reconciliation, **not
physical drain**. Account for every recorded reservation before relaunching:

```powershell
uv run --frozen --project C:/src/solidworks-pool C:/src/solidworks-pool/farm.py leaf-status --build-id "<build-id>" --workflow-id "<workflow-id>" --json
# Only after leaf-status supplies the immutable binding.run_id:
uv run --frozen --project C:/src/solidworks-pool C:/src/solidworks-pool/farm.py status --run-id "<bound-run-id>" "<workflow-id>" --json
```

Require `state: "drained"` or `state: "missing_closed"` with **empty
`unconfirmed_attempts`** for every recorded reservation. Any unknown binding,
recovery-required state, unconfirmed attempt or CLI failure remains unresolved;
`NOT_FOUND` is never proof of absence or drain. Only then launch again: a
relaunch registers a new build ID and new native executions, reusing published
cache artifacts, never running executions. Take its inputs from `run.json`
(`commit`, `targets`, `leaf_timeout_minutes`, `cache_environment`), not from
the caller's current worktree, with a `--display-name` for the recovering
session. A dead run's outputs may still be in its snapshot's `cad/out`
(`status` → `outputs`); `cancel` moves them to `out/` before removing it.

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
`pd_transgear_knob_bush_geometry.HUB_LENGTH_BAND` (the cluster's `FIT_LENGTH_BAND_IN`)
and `SHOULDER_SEAT_GAP_MAX`, not the annotation-rich bush specification or the
`ARM.BAND_XXX` wall-band literal. The bush build consumes that same
geometry-owned band, without a public alias. `dt_crank_pinion_spec` and `dt_crankshaft_spec`
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
`drawing:<stem>`, the gates (`verify_soundness:<stem>`, `verify:kinematics`),
the neutral `export` and the release Pack-and-Go
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
An ordinary upload failure with no canonical entry remains fail-soft; `ro` and
`off` contracts are unchanged.

A gate produces no CAD artefact, so **its stamp is its cached output**
(`cad/out/reports/verify-*.ok`): identical inputs imply an
identical verdict, so restoring the stamp is restoring the proof. This is also
the mechanism behind farm builds: a cache-missing COM task dispatches one
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
parsed-YAML for configs, the syntax tree for recipe code), so a cache hit and
"doit up-to-date" always agree and a comment-only YAML or Python edit busts
neither. Paths are tagged **repo-relative**, so the key is identical across
machines and worktrees.

**Recipe code is keyed by its syntax tree** (`_buildgraph.syntax_digest`):
every module a recipe can import (`_local_modules`: the non-test Python under
`cad/scripts`) is digested as `ast.dump` of its parsed text, without positions.
Comments, blank lines, line breaks, quoting, number spelling and docstrings
move no COM leaf key; any change to the program does. A module whose text
names `__doc__` keeps its docstrings, since it can read them. Tests, the
skipped tooling modules, files outside `cad/scripts` and the
`SolidworksMCP-python` digest tiers keep their byte digests. The digest names
its scheme (`SOURCE_DIGEST_SCHEME`): change what the tree keeps and bump it,
which moves every COM leaf key once without touching the cache epoch (the
epoch also keys every machinist review and its carry index).

A build that only runs its code cannot see what the tree drops. A task whose
result holds source text lists `dodo._source_text_dep` beside its deps, a
`cad/out/.source-text/` digest of the text of the recipe code among them:
`cam:<stem>` (its manifest records the runtime's hash) and every `check:*` gate
(tests read sources). `check:machinist_review:<stem>` keys its review code by
bytes, so no verdict moved with this. Do not make a COM recipe read its own
source, docstrings or line numbers into a saved artefact (`inspect.getsource`,
`obj.__doc__`, frame line numbers); if one must, give its leaf the text dep.
The syntax tree depends on the interpreter's grammar: submitter and workers
run the Python that `.python-version` pins, as they already had to for the
`ast.dump`-based registry and catalog digests below.

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

Every part with its own drawing has a `package:features:<stem>` COM leaf
(`export_features.SUPPORTED_PARTS`, 131 parts) that labels every face and writes
its STEP and face inventory; it reads no drawing, so its key is the generic
exporter closure, that part's config reads and the native part identity. The
seat-free `package:manifest:<stem>` binds the drawing's declarations to that
inventory; only parts whose drawing declares requirements (`DECLARED_PARTS`)
list features. Feature declarations remain colocated in `draw_<stem>.py`.
Static AST discovery and source-path construction do not import those modules
while loading the task graph, but each declared part's manifest task depends on
its **entire own draw-module closure**, not just declaration expressions. An
own-draw edit re-runs only that manifest task; shared `_drawing_common`,
layout-audit, `_pdf_ink` and drawing-helper edits re-run every declared
manifest task, and none re-keys a COM leaf or a native part/assembly recipe. An
undeclared part's manifest reads no drawing: it depends on the exporter, its
`DRAWING_NOTES` owner closure, the notes/spec files read to find it, its builder
file, registry/config and its STEP and inventory.
Full `export` waits for the labelled STEPs, validates each against its
inventory and copies their exact bytes; its recipe reads no manifest or draw
closure. A `prechips:<stem>` traveler depends only on its own manifest task.
Feature leaves retain `uptodate: [False]`, so every invocation reaches the cache
probe even if local STEP and inventory targets exist. `cache_status` reports
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
`_drawing_edge_dimensions`, `_drawing_tables` and `_drawing_balloons`. A titled
native general (setting) table on an assembly sheet goes through
`_general_table.insert_general_table`, the one helper for it (one-line title,
2.8 mm a character); the dt_cone_gear_tl_arbor setup table, measured at 3.2 mm a
character under a two-line title, keeps its own placer.
`move_model_dimension` belongs to `_drawing_dimensions`; drawing scripts import
dimension-transfer helpers there, never from another part's drawing module.
Hole-callout selection probes live in `_drawing_hole_callout`; annotation style
and attachment assertions in `_drawing_attachment`; GD&T and leader extents in
`_drawing_annotation_extent`. Selection, projection, visible edges,
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
Socket-head recipes such as the catalogue-only 91251A108 share the pure
`_socket_head_dimensions` record; each SKU still owns its `DIMS` declaration.
The current knife-hanger hex-bolt, #10 washer and
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

The vendored COM adapter (`cad/scripts/solidworks_mcp/`) is an ordinary local
package, so a COM task's `file_dep` carries exactly the adapter files its import
closure reaches, like any other helper. See
[the vendored adapter notes](AGENTS.md#vendored-solidworks-adapter-cadscriptssolidworks_mcp).

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
stem contains `_vn_`, such as `part:sm_vn_counter_spring`) emits a
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
a foreign key mean something went wrong. A farm submitter never
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
must be deliberately replaced. It works locally and on the farm:

```powershell
uv run --frozen python build.py `
  --force-cache-refresh part:pn_pen_rod `
  --force-cache-refresh-reason 'Owner - Re-evaluate unchanged-input result' `
  part:pn_pen_rod
```

`farm_build.py run` takes the same two flags and records them in `run.json`.
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

## Deterministic COM request order

Every COM subprocess (`dodo._exec_com`: part, assembly, drawing and hook runs)
hashes str with `PYTHONHASHSEED=0` (`dodo._COM_ENV_PINS`, applied over any
inherited value). Under per-process hash randomisation, a build that orders
COM requests by iterating a set of str issues them in another order from build
to build: on 2026-11-11, 5 of 10 identical-source part rebuilds diverged on
`_drawing_precision._named_dimensions` and
`_supplier_spring_reference.add_supplier_reference_configurations`. Since
#2514 those, `_drawing_precision.apply_drawing_precision` (specs build
`DRAWING_PRECISION` from sets),
`_supplier_washer_model.assert_supplier_washer_references`,
`_assembly_patterns.assert_pattern_targets` and `build_pd_feed_rack`'s
reference-dimension loop iterate sorted names, and since #2655 so does the
vendored `sw_type_info.flag_methods` (one `GetIDsOfNames` request per method,
reached through `_com._flag`, `segment_point_objects` and
`dimension_full_name`). The pin stays as a backstop for any set iteration
still reaching SolidWorks. It re-keys nothing, since `dodo.py` is in no recipe
closure.

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
skipped, labelled or ordered under a placeholder. The pattern gates' loops
that only collect names into a set go through it too
(`_assembly_patterns._component_names`, since #2759), so an unnamed component
fails there as well. `_assembly.check_no_interference` names each
`IInterferenceDetectionMgr.GetInterferences` result's `IInterference.Components`
in the report's order, then reads configurations and volumes over the results
sorted by name pair; results sharing a pair keep the report's order among
themselves, so their volumes are sorted before they are summed or reported.
A part drawing view's one visible component needs no order
(`_drawing_edges.visible_view_entities` sorts only an assembly view's).
Exempt: scripts no doit task runs (`export_glb`, `diagnostics/`), and `_drawing_tables`'
failure evidence, whose `collect()` records a failed row's first native
component after the failure. `test_component_order.py` (`check:recipe`)
runs the Default Simplified pass over two enumeration orders and requires the
same requests, and requires an unnamed component to fail closed.

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
