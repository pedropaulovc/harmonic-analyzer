# Second SolidWorks VM: assembly performance, batch 2

Copy this document as the second VM agent's next task prompt. It supersedes the
first handoff's work list, not the repository's safety or merge gates.

## Objective and starting point

Reduce avoidable assembly rebuilds, then accelerate the measured native
drive-train bottleneck. You own assembly work on this VM. The primary agent
retains drawing recipes, layout, title persistence, templates and adapter work.
Neither stream needs the other's live SolidWorks session or output directory.

Repository: https://github.com/pedropaulovc/harmonic-analyzer

Finish PR [#676](https://github.com/pedropaulovc/harmonic-analyzer/pull/676)'s
candidate assembly acceptance, identity checks and evidence first. Do not wait
for the primary machine's drawing/full-stack merge gate to begin this batch.
Do not put this batch's unrelated changes into #676.

At handoff, #676 was inspected at
`60178f31d384eb45f540774faf9948b0a4bc0813`, branch `perf/assembly-vm2`, targeting
`perf/cad-build-and-drawing-entities` (#675). Use #676's actual final accepted
candidate head as your baseline; record its full SHA and submodule SHA. The
inspected adapter was `e77bfda4de1962625da8a9a859eb0bbaf1e6f10f`. Do not reset to
these historical pins if the PR has advanced.

Reuse your existing independent VM2 clone, its own venv, build database and
locally generated artifacts. Before changing branches, finish native jobs,
inventory open documents, preserve a closed-document baseline and verify a clean
worktree. Fetch the parent and main, follow AGENTS.md's rebase policy between
runs, then branch `perf/assembly-cache-granularity` from the recorded baseline.
If #676 is still open, stack against `perf/assembly-vm2`; if merged, use the
branch containing its accepted changes. Never delete a parent branch with open
stacked children. Do not continuously pull a moving branch during measurements.

Start by loading developing-solidworks and reading local AGENTS.md. Use the
bundled API documentation before web research. Treat both old notes and this
brief's optimization hypotheses as claims to test, not established limitations.

## What the preceding batch actually established

Read `cad/docs/pipeline/assembly-vm2-results.md` at your baseline for the run
manifests. The inspected version reported:

| Measurement | Result |
| --- | ---: |
| Drive-train build after seat acquisition | 474.850 s |
| Harmonic-analyzer build after seat acquisition | 310.180 s |
| Channel build after seat acquisition | 225.280 s |
| Summing build after seat acquisition | 34.660 s |
| No-change `build_bare`, cache off | 10.400 s, zero COM work |
| Top-assembly health gate, existing / candidate median | 8.242 / 0.651 s |

The fleet baseline passed assembly construction, all eight saved soundness
checks, kinematics and visual inspection. It was not the full drawing-inclusive
merge gate. The health candidate passed 24 paired diagnostic cases; final
candidate acceptance and identity checks were still outstanding in that version.
All seed dependencies were locally built after read-only cache misses, so this
does not demonstrate remote cache hits. Summing's 753 s seat wait was not its
35 s native build cost.

## Batch A: narrower assembly recipe dependencies

The initial multi-checkout audit in `cad/docs/pipeline/performance.md` found
18 assembly cache hits and 149 misses. `_assembly.py` changed in 39 of 102
observed miss-key transitions; only one transition was identity-only. This
motivates splitting helpers, but does not establish how many misses a split
would prevent or predict its eventual hit rate.

1. Produce a before/after consumer matrix for assembly helpers, builders,
   refresh, verification and part isolation. Use the actual transitive
   `module_deps_of` closures and generated task dependencies, not just direct
   imports. Identify useful narrow groups before choosing module boundaries.
2. Extract specialized helpers into modules imported directly by their consumers.
   Pattern construction and specialized mate helpers are candidates, not a
   prescribed architecture. Keep common placement/ledger primitives shared where
   genuinely used. Separate verification-only work from construction where the
   actual call graph permits it; gates called while building remain build inputs.
3. Preserve behavior in this PR: no solver-policy, geometry, tolerance, mate,
   health-traversal or persistent-identity changes. Carry #676's accepted health
   improvement intact. Do not add an umbrella re-export that reconnects all the
   extracted modules, or move them behind dynamic imports invisible to the graph.
4. Prove invalidation both ways using isolated test fixtures: an extracted helper
   edit changes every real consumer's recipe/cache key but leaves unrelated
   assembly construction recipes and all leaf-part recipes unchanged. Distinguish
   direct recipe invalidation from legitimate parent refresh caused by a changed
   child's execution token. Broadly shared helper edits must still invalidate all
   their real consumers. Show actual task keys, not only a smaller import count.
5. Keep source-manifest discovery and freshness guards trustworthy. In particular,
   `_AssemblySources` and `test_buildgraph.py` currently recognize canonical
   placement passthroughs in `_assembly`. Leaving those primitives there avoids
   changing this contract. If moving them is justified, transfer the complete
   positive and negative contract tests to the new providers; do not whitelist
   arbitrary source-producing imports or weaken tests merely to make the split
   pass. Keep verify-only dependencies enrolled in verify freshness.

Own `_assembly.py`, new assembly-only helpers, assembly builders,
`_assembly_postbuild.py`, `refresh_assembly.py`, `verify.py`, and their focused
tests/diagnostics. Import-only migrations in other callers are allowed; do not
change drawing behavior. `test_buildgraph.py`, `test_part_isolation.py` and
`test_dodo_recipe.py` changes that prove this split are in scope.

Leave `dodo.py`, `_buildgraph.py`, `_common.py`, `_artifact_cache.py`, telemetry,
shared config, dependencies and the adapter unchanged unless a demonstrated
correctness issue makes a small integration change necessary. Put any such
change in a separate, explicitly described commit for primary-agent integration;
do not launch a second cache or scheduler redesign. Prefer a split that works
with the current graph. No other-machine changes are prerequisites.

Acceptance: pass the COM-free gates below, perform one assembly-fleet acceptance
run on the frozen candidate, inspect all affected renders, and repeat the
no-change run with zero COM work. Report reduced invalidation coverage separately
from steady-state native speed: moving functions alone should not be described
as faster SolidWorks execution. Record the one-time key migration cost too.

## Batch B: one measured drive-train construction improvement

Put native behavior changes in a separate PR stacked above accepted Batch A.
Use the new dependency boundaries rather than recombining the helpers.

- Profile a fresh local drive-train construction at a frozen revision. Separate
  lock waiting, cache transfer, open/resolve, insert, placement, mate authoring,
  solver rebuilds, validation, save and render time. Account for nested spans
  without double counting. Cache off does not bypass doit's up-to-date check:
  prove the trial actually constructs the assembly, preserving the baseline
  artifacts before forcing construction through the supported build path.
- Choose the largest measured reducible phase. Aggressive batching, native
  patterns, bulk insertion and deferred solving are welcome if applicable.
  Read the relevant local API docs, establish a working native positive control,
  and change one behavior at a time. Do not remove gates, freeze operational DOF,
  silently repair failed mates, or change geometry to manufacture a speedup.
- Compare baseline and candidate with the same parts/configurations and recorded
  native identities, alternating trial order. Aim for at least three successful
  runs per variant; report individual times, session age, retries and failures.
  Do not drop failed or recovered attempts from the reliability accounting.
- Validate cold save/reopen, expected free-DOF families, health, interference,
  kinematics and renders. Include a real dependent-part change, a same-recipe
  rebuild with a new child identity, and a no-change run. Use an isolated local
  fixture for change trials; do not mutate production configuration mid-run.
- Retain a candidate only when measured savings justify its complexity and all
  invariants hold. If the tested approach loses or is inconclusive, retain its
  reproducible diagnostic/evidence and remove the unhelpful production change.
  Enumerate tested and untested variants instead of declaring an API unusable.

Do not start coherent cache bundles or concurrent COM workers in this batch.
Those remain separate proposals requiring their own measured benefit and safety
design. The existing exact child execution tokens and one-seat lock stay intact.

## Independent execution and delivery

Use uv in this clone's venv. Do not share output roots, execution tokens, build
databases or live documents across machines. Seed dependencies with process-local
`HARMONIC_REMOTE_CACHE_MODE=ro`; use `off` for uncached native comparisons. Do not
publish experimental artifacts. Report authentication failures explicitly; a
local build can continue independently but is not remote-cache validation.

Use this VM's licensed launcher/lifecycle helper and existing machine-global seat
lock for every COM operation, diagnostics included. Discover its installation,
edition, PID and open documents locally. Do not assume the first VM's CEF error
applies here. Never discard user documents or restart away unsaved work. Freeze
code, dependencies and configuration during each native run; edit/rebase only
after it finishes. Snapshot and verify inputs around probes that might save
referenced models. Do not use cross-machine COM or run two native jobs on one seat.

Run the relevant enrolled COM-free gates:

```powershell
uv run python -m doit -n 4 check:recipe check:graph check:config check:math check:partiso check:cache check:watchdog
```

Assembly acceptance and the subsequent no-change check are:

```powershell
uv run python -m doit -n 4 build_bare verify:soundness verify:kinematics
uv run python -m doit -n 4 build_bare
```

These are assembly acceptance, not a waiver of the repository's full
`uv run python -m doit -n 4` merge gate. The primary agent coordinates that gate
and drawing inspection at the final stack head. Each PR still needs its own
clean CodeRabbit or Codex review; either one is sufficient. Open each draft PR
early, mark ready at code-complete before
tests, and follow watch-pr for review/CI changes. Do not merge the stack or delete
its parents as part of this handoff.

For each PR deliver a concise results document with root/adapter SHAs, commands,
host/SW version, source and artifact hashes, trace/log IDs, native output paths,
before/after times, gate outcomes and inspected renders. Keep raw evidence locally
with an exact manifest and instructions to regenerate it on another seat. Report
sample counts and observed failures; a small successful series does not establish
the user's requested less-than-5% conflict rate. Distinguish source-control
conflicts, stale-reference/cache failures and native solver failures.

Batch A is complete when narrower invalidation and unchanged native behavior are
proven. Batch B is complete when one worthwhile improvement is accepted or the
bounded candidate has a reproducible negative result. Hand back remaining ranked
opportunities instead of silently expanding into the primary agent's drawing work.
