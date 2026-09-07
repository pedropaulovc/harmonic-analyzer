# VM2: extract narrower assembly dependencies onto main

Prepare a merge-ready, two-PR stack for the assembly dependency work from #677,
independent of the drawing stack. VM1 owns integration and merging of both
stacks. Leave the new PRs open after validation.

Your completed resolver batch remains frozen at #685,
`442cd6a2885ba789548c5f3b93509656a5e9dee1`. Preserve its worktree, native outputs,
receipts and accepted parent `19431a00`. Do not reuse that checkout for this task.

## Starting point and ownership

VM1 verified `origin/main` as `c6ab57dbdf73a733b32fb580bada81dab7fd758c`
on 2026-09-07. It already contains the isolated health-traversal improvement.
Start the extraction there; inspect and incorporate newer main commits before
the full native build. This is an integration task, not a frozen historical
benchmark. Main's adapter is `2269009ed56712867826516f4406afc98a0c2814`.
Keep the adapter selected by main; neither #677's `e77bfda4` nor #685's
`25bc99b1` is a reason to change it.

Load `/developing-solidworks` first. Use its bundled API documentation, native
Windows tools and this checkout's own uv environment. Inspect an existing path
or branch before using it; never overwrite another experiment.

```powershell
git fetch origin main perf/cad-drawing-foundations perf/assembly-cache-granularity
git worktree add -b perf/assembly-source-dependencies-isolated C:/src/ha-assembly-granularity-integration c6ab57dbdf73a733b32fb580bada81dab7fd758c
Set-Location C:/src/ha-assembly-granularity-integration
git submodule update --init --recursive
uv sync --frozen
git rev-parse HEAD
git -C SolidworksMCP-python rev-parse HEAD
```

Create the second branch, `perf/assembly-granularity-isolated`, from the completed
parser branch. Push early and open both PRs as drafts, with the second targeting
the first. Mark each ready when code-complete, before tests, and attach its
`watch-pr` monitor. Use merge commits, never squash or delete parent branches.

VM2 owns these changes in the new branches:

- `_buildgraph.py` and the relevant `test_buildgraph.py`/`test_dodo_recipe.py` hunks.
- `_assembly.py`, new `_assembly_patterns.py` and `_assembly_couplings.py`.
- Import-only changes in the five production callers and eight diagnostics
  touched by `840b0a42`, plus their component-pattern and isolation tests.
- `diagnostics/report_assembly_dependencies.py` and new extraction evidence.

All paths above are under `cad/scripts/`. VM1 will not independently extract
these assembly changes while this assignment is active. VM1 may finish the
separate #684 spare-deck correction in `build_paper_drive_assembly.py`; preserve
main's placement expressions if rebasing overlaps that file's import edit.

Do not edit or rebase #676, #677, #678, #680, #681, #675, #682, #684 or #685.
The original #677 is evidence and a source of bounded patches, not the new base.
Do not alter drawing code, manufacturing data, templates, memory, adapter code,
`_channel_pose.py`, `_cwm.py`, scheduler/cache behavior or exact execution tokens.
In particular, do not revive #678's withdrawn mass-read optimization.

## PR 1: current dependency parser

Extract these commits in order, inspecting their actual diffs first:

```text
ac8d9035fce78048c50e2bce071c0e794e3104db
592629bbd27fc694a53428f18d1fd6ef4bf190f4
e2d3af8b4df7522ff2869ddc1d209f9e2b1b2dd7
d35c50efd972208ace8ccf49e8e892b7cb2a7771
```

They contain the current `_buildgraph.py` changes from main through foundation
head `83147f2f`, their graph tests, and two recipe regressions. The middle pair
supplies canonical source-discovery support needed by the assembly split. The
first reuses that parser for config syntax; the last fixes its bare-module escape
case. Keep that pair together. Do not copy whole test files from a drawing parent.

Reproduce the source graph before relying on the earlier inspection. VM1 ran
both actual parsers against the same main builders: 125 artifact edges became
119, with the same 108 part names. The six removed edges were:

```text
frame       -> gooseneck, rocker_arm
drive_train -> channel, harmonic_base
channel     -> cylinder_gear, frame
```

These are parser observations, not permission to hardcode graph exceptions.
Preserve tests for aliases, keyword mutations, imported sources, memoization,
path-wrapper drift, canonical passthrough and conservative config escape handling.
Both main's 137-module import closure and the split's 139-module closure passed
the current source-import contract in VM1's read-only comparison. Re-run it on
your integrated files.

## PR 2: assembly helper split

Inspect and extract this sequence onto PR 1:

```text
62cc4d79e8b78618c33ccc8f7883e6e4a0c9c34f
840b0a421ec3bff27413ff7b68ae8098ddfa706c
aff115c4a679d1efc02c533ba3249e6c373a4440
```

The first adds the reporter and experiment document; the second changes runtime
imports and tests; the third records the old VM2 acceptance. Label the imported
results document as historical and add a separate
`cad/docs/pipeline/assembly-granularity-integration-results.md` for this run.
Do not relabel old measurements or source hashes as new acceptance.

VM1 compared all 82 assembly definitions on current main with the split: their
ASTs were identical. Check this again after integration. Move helpers and change
imports without changing function bodies, component placement, mate construction,
DOF contracts, health/save checks or refresh behavior. The core must not import
the specialized helpers back.

The expected direct recipe consumers are:

| edited helper | assemblies whose full-rebuild recipe changes |
|---|---|
| patterns | frame, drive_train, magnifier, paper_drive |
| couplings | drive_train, paper_drive |
| core | all eight assemblies |

Parent task keys can still change transitively. The top assembly's task key
must follow changed children even when its own full-rebuild recipe stays stable.
Every leaf part recipe and key should remain unchanged. Prove both directions;
a smaller consumer count alone could hide a missed dependency.

## Evidence and native acceptance

Retain separate reports for original main, parser-only, and parser-plus-split.
The reporter in `aff115c4` reads production recipe/key functions without COM or
cache transfers. Use a local baseline copy of that reporter if needed before
its introducing commit, record its hash, and keep it out of unrelated changes.
It may refresh digest sidecars: run it only in an inactive checkout.

```powershell
$env:HARMONIC_REMOTE_CACHE_MODE = 'off'
uv run python cad/scripts/diagnostics/report_assembly_dependencies.py cad/out/reports/assembly-granularity-integration/after.json
uv run python -m doit check:recipe check:graph check:partiso check:cache
```

Use the reporter's output argument for each distinct before/after receipt.
Retain actual helper-mutation tests proving the 4/2/all-eight consumer sets,
ancestor key propagation, unchanged 108 leaf keys, and identity-only changes.
Use isolated copied inputs for mutations, never an active native checkout.
Keep byte-churn immunity and verify/drawing exact-token dependencies intact.

Before native work, fetch main again, rebase the bottom then the child if needed,
and confirm the checkout, venv, adapter and native sources are consistent. Build
required parts through doit in this checkout. Do not combine another worktree's
native files with fabricated/restamped tokens or a copied freshness ledger.
Preserve any known-good snapshot before the migration; enumerate exact paths
and hashes. Follow the skill for attaching to the licensed seat, inventory and
document ownership. The machine-global seat lock and watchdog remain mandatory.

Freeze all imported source/config/adapter files while the native run is active.
With cache transfers disabled, run the full pipeline at the stack head:

```powershell
$env:HARMONIC_SW_AUTOSTART = '0'
$env:HARMONIC_REMOTE_CACHE_MODE = 'off'
uv run python -m doit -n 4
```

The first candidate run must actually construct all eight assemblies, then pass
all saved soundness and kinematic checks and every drawing/gate in the full graph.
Retain task dispositions and telemetry; a cache-only pass does not demonstrate
the native migration. Compare geometry fingerprints, DOF manifests and source
contracts with the same-main baseline. Inspect all eight fresh assembly renders
and any drawing outputs changed by the migration. If a baseline defect appears,
record it and coordinate its correction rather than waiving the visual check.

Repeat the exact-head full command with no changes. Require zero COM activity
and record total wall time, cache dispositions and trace boundaries. Do not use
`reset-dep`, rewrite tokens, loosen identity checks or delete broad output trees
to obtain a no-op. Source edits require the affected gates to run again.

The earlier #677 record reports a 2,532-second migration and a 10.99-second
no-op on a different parent and adapter. Those are historical results. This
split reduces rebuild invalidation; it does not inherently speed up an individual
SolidWorks solve. Record failures, retries and recoveries as well as successes.
A small successful sample does not establish a below-5% conflict/failure rate.

## Review and return

Get one clean CodeRabbit or Codex review for each new PR's latest code. Use the
Windows CodeRabbit CLI if hosted quota is unavailable; do not use WSL or change
billing. Put extra review context outside the changed-file set. Retain the full
local receipt before another review can prune it, and compare its stored diff
and source contents with the requested base/head; metadata alone is insufficient.

The top full build and visual inspection cover both PRs. Each still needs its
own review. If API access is rate-limited, retain the exact error and local
evidence; missing watcher output is not approval.

Return both PR URLs and heads, actual base/adapter, exact file ownership,
before/after report hashes, native artifact/token manifest, full-build and
zero-COM no-op receipts, inspected renders, review receipts and remaining limits.
Keep the accepted #682/#685 worktrees and artifacts untouched. VM1 will merge
the new stack bottom-up after checking these receipts.
