# Second SolidWorks VM: independent assembly performance work

Copy this document as the other coding agent's task prompt. It is an execution
brief, not a claim that the assembly changes have completed their merge gates.

## Objective and ownership

You own **assembly performance and independent saved-assembly validation** on
this VM. Another agent is working on drawing persistence, layout and drawing
defaults on a different machine. Do not wait for its drawing fixes to do your
assembly work. Do not edit drawing recipes, drawing helpers, templates or their
tests. Do not remote-control the other machine.

Start by loading the developing-solidworks skill and reading the checkout's
AGENTS.md. Use its local API bundle; verify inherited claims against current
code and native behavior. Use uv with this checkout's own virtual environment.

Repository: https://github.com/pedropaulovc/harmonic-analyzer

Starting revision: `bf7f92ad70376e59be8b0ace6147d35f197b879d`, pushed on
`perf/cad-build-and-drawing-entities`, draft parent PR #675.

Pinned SolidworksMCP-python submodule:
`e77bfda4de1962625da8a9a859eb0bbaf1e6f10f`.

Use a **fresh local clone**, not a shared folder, existing CAD output directory,
copied virtual environment, or another machine's doit database. From a suitable
local parent directory, with a new/nonexistent destination:

```powershell
git clone --recurse-submodules --branch perf/cad-build-and-drawing-entities https://github.com/pedropaulovc/harmonic-analyzer.git harmonic-analyzer-assembly-vm2
cd harmonic-analyzer-assembly-vm2
git switch -c perf/assembly-vm2 bf7f92ad70376e59be8b0ace6147d35f197b879d
git submodule update --init --recursive
uv sync
git fetch origin main
git log --oneline HEAD..origin/main
```

If main has advanced, follow the repository's rebase policy before starting
native work; record the actual tested root/submodule commits. Freeze imported
source and dependencies throughout each native experiment. Rebase only between
runs, never under a live COM process. Do not continuously pull the other agent's
changing feature branch while measuring.

## Independent resources and safety

- Use only this VM's licensed SolidWorks session and native artifacts generated
  in this clone. Record host, SolidWorks version/service pack, PID, root and
  imported adapter paths. Discover them locally; do not reuse the first VM's PID.
- First inventory open documents. Normal build wrappers may clear documents or
  recover SolidWorks: use a dedicated session with no user documents. Never
  discard, save over, or restart away someone else's unsaved work.
- Launch through the installed licensed launcher/shortcut or supported lifecycle
  library. For Makers/3DEXPERIENCE, bare EXE/COM activation is not the launch path.
  Do not assume this VM has the same edition, installation path or CEF problem.
- Keep the machine-global COM seat lock. All native jobs, including diagnostics,
  must use the existing locked wrappers. No concurrent native jobs on this VM;
  a second VM does not justify parallel COM calls within one SolidWorks process.
- Shared cache is **read-only** for dependency seeding, then **off** for uncached
  timing trials. Never publish experimental assembly artifacts or change shared
  cache salts/roles. Use process-scoped environment settings. If Azure credentials
  are unavailable, report the exact auth failure; local uncached builds are the
  planned independent path, not a claim that remote-cache validation passed.
- Never share `.doit.db`, `cad/out`, execution tokens, live documents or COM
  handles with the first VM. Recipe-equal native files need not have equal CAD
  identities. Preserve exact child execution-token checks and freshness guards.
- This task does not authorize registering add-ins or changing machine-wide
  registry/security settings. Neither is required for the assembly work.

## Starting evidence, not acceptance criteria

Read `cad/docs/pipeline/performance.md`. The first VM measured five uncached
channel builds: reference 509.550 s; prepared handles 320.197 s; retained drivers
with individual removal 334.959 s; batch removal 247.125 s and 264.880 s. Pose
writes decreased from 3,888 to 216. Construction gates passed, and the two batch
DOF manifests matched each other. **Independent saved-model verification is
still pending.** Do not compare your VM's wall time directly with those numbers
or infer a fleet failure rate from them.

The optimized channel construction is in `_channel_pose.py` and
`build_channel_assembly.py`. Earlier strategies are visible in git history:
`ad71c6bd` prepared handles, `c3a7914c` retained driver bank, `daa26d53` batch
removal, `025ca472` channel-only helper isolation. These commits are provenance;
do not roll the whole checkout back and accidentally change other build inputs.

Task discovery already improved from 15.645 s to 6.848/6.027 s, and six false
assembly dependency edges were removed. Re-measure rather than repeat those
changes. The historical telemetry and saved baseline CAD under paths beginning
`C:/src/ha-*` are **not available on your VM** and are not prerequisites. Generate
your own run manifests, native artifacts, renders and telemetry.

## Work sequence

1. **Build and independently verify the current optimized channel.** The current
   doit graph provides a per-assembly verification task; no standalone freshness
   bypass is needed:

   ```powershell
   $env:HARMONIC_REMOTE_CACHE_MODE = 'ro'
   uv run python -m doit -n 4 assembly:channel verify_soundness:channel
   ```

   A restored channel is useful verification evidence but is not an uncached
   build timing. For a from-scratch trial, disable remote caching and use the
   assembly's scoped clean/rebuild path in this dedicated clone. Inspect its
   exact targets first and preserve any native outputs needed for comparison.
   Do not delete the workspace, all outputs, or unrelated parts to force one job.

2. **Complete the assembly-only graph and saved-model gates.** Run:

   ```powershell
   uv run python -m doit -n 4 build_bare verify:soundness verify:kinematics
   ```

   Preserve all health, intended operational DOF, mate, interference and
   saved-rebuild checks. Inspect fresh renders of every assembly affected by
   your changes. A saved/reopened result, not only a successful construction
   call, is required. Use a separate frozen run for performance measurements;
   avoid other CPU-heavy tasks during those timings.

3. **Profile remaining assembly costs, then implement a bounded improvement.**
   Prioritize channel, summing and the top assembly using this VM's spans.
   Separate seat waiting, cache transfer, process startup, construction, refresh,
   verification and save time. Prefer fewer repeated COM traversals/rebuilds and
   native batching while preserving identity and solver invariants. Use paired
   baseline/candidate runs on the same VM and pinned child inputs; record failures
   and recovery costs rather than retaining successful runs only. Keep a working
   positive control before declaring a native API or strategy unusable.

4. **Check incremental behavior.** Record a no-change second assembly build and
   explain any unexpected COM work/cache miss from recipes and execution tokens.
   Test deliberate input changes only in an owned experimental branch/output
   set; distinguish a changed child identity from parent-save metadata churn.
   Do not weaken cache identity merely to manufacture hits.

5. **Package the result.** Commit scoped implementation, regression tests and
   `cad/docs/pipeline/assembly-vm2-results.md`. Keep large native files and raw
   logs out of git; retain them locally and publish a self-contained evidence
   attachment with referenced CAD dependencies together if sharing is needed.

## File boundary and integration

You may change assembly-specific builders/helpers, `_channel_pose.py`, `_cwm.py`,
`_assembly.py`, `_assembly_postbuild.py`, assembly verification code and directly
related tests. New assembly-only helpers, diagnostics and evidence documents are
encouraged where they keep recipe invalidation narrow.

Reserve `dodo.py`, `_common.py`, `_buildgraph.py`, `_artifact_cache.py`, `_telemetry.py`,
project dependencies and the adapter submodule for coordinated integration.
If a finding requires one of those shared surfaces, produce a separate minimal
patch/commit and repro, explicitly identify the overlap, and continue independent
assembly work. Do not mix it into unrelated edits or merge it unannounced.

Push your branch early and open a **draft stacked PR against
`perf/cad-build-and-drawing-entities`**, not against main. Follow the watch-pr
skill and repository review workflow. Do not merge the parent, force-push another
agent's branch, delete the parent branch, or squash. At code-complete mark your
PR ready before running its final tests, as AGENTS.md requires.

The primary agent owns final integration and the drawing fixes. The actual
`doit build` graph at this revision includes all drawings, so your assembly-only
run is **not the full merge gate**. Report assembly acceptance independently;
do not wait indefinitely for drawings or remove drawing tasks to turn the gate
green. Final integration still needs `uv run python -m doit -n 4` on the integrated
head, complete visual inspection and clean per-PR review.

## Required handback

Provide branch/PR and commit IDs; tested root/submodule revisions and VM/SW
version; exact commands and cache modes; per-trial wall times and failure counts;
trace IDs and artifact/input hashes; saved-model/DOF/health/interference outcomes;
renders inspected; cache/no-op observations; and unresolved risks. Clearly
separate implemented, natively proven, offline-only and proposed changes.

The user accepts aggressive strategies only with manageable conflict risk and
has suggested a target below 5%. Do not label a handful of passing trials as
proof of that bound. State the sample, tested conditions and what reliability
claim the evidence actually supports.
