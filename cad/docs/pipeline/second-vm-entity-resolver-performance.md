# VM2: make entity-based drawing selection faster

This is the next work assignment, not completed validation. Use a new child PR
of #682. Keep the accepted crank-arm migration and its native evidence intact.
Portfolio status remains on the [project board](https://github.com/users/pedropaulovc/projects/1).

## Objective and starting point

Reduce the COM cost of resolving model entities while preserving all 15 migrated
crank-arm selection sites, the accepted print, source values and native identity
checks. Prefer batching feature/face/edge reads within one resolution call.

Start at **19431a0088519bd8755b941a3da73a699c0ed7e1**, PR #682. Its accepted code
is `09c050de61c15e87f2f1138051ea4fc902431851`; subsequent changes record evidence.
The adapter pin is **25bc99b1ae39d8c0e004867e9b5c0f2068f2abc2**.
Read `cad/docs/pipeline/crank-arm-entities-results.md`, especially
"Accepted result and limits", before changing anything.

That production observation took **26.566008 s**, including **5.192939 s** in
the entity bank. The earlier coordinate-pick observation was 14.911039 s.
Those samples do not establish a repeatable regression or speedup. Measure the
accepted entity implementation against your candidate under matched conditions;
do not optimize by reverting to coordinate selection or dropping checks.

VM1 owns integration of #680/#681/#675/#682, the spare assembly fix, and the
gear BSURF diagnostic. Do not rebase, force-push, or edit those branches. VM1 will
rebase your bounded child diff after acceptance. This frozen comparison can run
independently while the parent integration moves.

## Checkout and file ownership

Load `/developing-solidworks` first. Follow the current repository instructions,
use bundled API docs, Windows-native tools, and uv in this checkout's own venv.
If the proposed path or branch already exists, inspect it before choosing a new
name; do not overwrite another run.

```powershell
git fetch origin main perf/crank-arm-semantic-entities
git worktree add -b perf/entity-resolver-batching C:/src/ha-entity-resolver-batching 19431a0088519bd8755b941a3da73a699c0ed7e1
Set-Location C:/src/ha-entity-resolver-batching
git submodule update --init --recursive
uv sync --frozen
git rev-parse HEAD
git -C SolidworksMCP-python rev-parse HEAD
```

This frozen experimental base is intentional. If main has advanced, record the
delta and retain it for the later integration rebase; do not mix that delta into
the paired benchmark. Check main again before the eventual full integration
build and rebase then. Do not edit any Python source, test, spec or adapter in a
checkout while its native run is active.

Exclusive production ownership for this batch:

- `cad/scripts/_drawing_entities.py`.
- `cad/scripts/test_entity_resolution_drawing.py` and new resolver-only tests
  named `test_*_drawing.py` so the recipe gate discovers them.
- A new `cad/scripts/diagnostics/probe_entity_resolver_performance.py` and its
  tests, if needed for a repeatable comparison.
- A new `cad/docs/performance/entity-resolver-batching.md` for results.
- Crank-specific diagnostic instrumentation only when needed to run the same
  accepted checks on a newly generated local source and baseline.

VM1 will leave the production resolver and its test file unchanged during this
assignment. Do not change the adapter, `_common.py`, `_part_pmi.py`, drawing
layout/annotation helpers, part builders, specs, configuration, templates,
memory files, manufacturing content, or the accepted crank-arm layout. Propose
an expansion if profiling shows the useful fix lies outside this boundary.

## First experiment

`_ScopedEntities` currently caches feature face arrays and resolved selectors.
It still calls `_resolve_face_requests` separately for different faces on one
feature and reads a face's edges separately for different boundary requests.
Measure whether those paths repeat native geometry or binding work on the
actual crank roles. Existing caches may already remove some apparent repeats.

Instrument the invoking COM thread and report counts plus elapsed time for
feature lookup, face enumeration, surface/curve geometry reads and wrapper
binding. Keep profiling runs separate from uninstrumented acceptance/timing.
Do not add cumulative profile rows from overlapping calls or other threads.

If repeated reads dominate, batch requests by their actual ownership scope and
reuse measured geometry for the lifetime of one `ModelEntities.resolve()` call.
Union the requested edge kinds before reading geometry where appropriate.
Keep enough native handles alive for that operation, then release the bank.
Do not persist COM handles or geometry across resolves, rebuilds, configuration
changes, document closes, or source replacement. A process-wide/filename cache
is outside this assignment. Never treat Python wrapper identity as proof of
native entity identity.

Keep the exact supported selector semantics and matching tolerances. Missing,
ambiguous, malformed and null geometry must still fail with useful diagnostics.
Feature-scoped requests must not fall back to a body scan or nearest sheet pick.
No retries, silent exclusions or added save/rebuild calls belong in the resolver.

## Native comparison and acceptance

1. Preserve VM2's accepted #682 reports and outputs. Generate the new checkout's
   source through doit and retain its actual SHA/token and baseline drawing.
   Do not copy a `.doit.db`, execution token, gate stamp, venv or prepared entry
   from another checkout. Establish new diagnostic pins from actual native
   observations; never rewrite them merely to satisfy a failed assertion.
2. Use only one licensed SW instance on this VM and the machine-global COM seat.
   Attach to an explicitly inventoried PID with `HARMONIC_SW_AUTOSTART=0`.
   Use `HARMONIC_REMOTE_CACHE_MODE=off` for measured builds. Keep saved source
   files unchanged across paired runs and record SW revision, memory and input
   hashes. Close only documents owned by the experiment between variants.
3. Warm and validate each variant's prepared-template entry before measuring.
   Benchmark at least three alternating ABBA blocks of the real resolver on
   stationary, correctly configured native input. Each call gets a fresh bank.
   Retain every sample, call count and any failure. Compare returned roles by
   native source/view identity, not names or rendered similarity.
4. Measure uninstrumented production drawings too, through
   `uv run python -m doit -a -s drawing:crank_arm` once its dependencies are
   genuinely current. `-a` without `-s` also forces the part and changes its CAD
   identity. Compare matched baseline/candidate runs; keep setup, resolver,
   recipe, save/export and verification durations separate. Report distributions
   and absolute savings. An isolated resolver win is not a fleet speedup.
5. Run the unchanged complete crank acceptance: all 14 explicit attachment
   roles, all 13 raw drawing dimensions, source/tolerance/text/BASIC/arc checks,
   first cold reopen, view movement/scaling, in-place save, second fresh-handle
   reopen, factory guards and exact original/copy/token hashes. Preserve the
   existing documented geometry exclusions and roundoff policy without widening
   them. The moved/scaled sheet proves associations, not print acceptance.
6. Inspect fresh production and cold full sheets plus readable detail crops.
   The accepted layout should remain unchanged. If measured output differs,
   identify why and fix it before calling the candidate accepted.
7. Add fail-first tests for repeated scopes, mixed circle/line requests,
   ambiguity, missing/null geometry, separate resolve calls and error cleanup.
   Run affected resolver/consumer tests and the full COM-free recipe, graph and
   part-isolation gates. The frozen baseline has the reported fillister
   registration/test contradiction; leave both sides unchanged and report that
   failure explicitly. It does not excuse any additional failure.

A useful target is to cut the roughly five-second resolver cost substantially
without increasing total recipe time. This is an investigation target, not an
acceptance shortcut. If there is no repeatable benefit, retain the benchmark and
negative result without promoting the optimization. Do not infer a below-5%
failure rate from a few clean runs; report the actual trial count and failures.

## Delivery and merge boundary

Push early and open a draft child PR targeting `perf/crank-arm-semantic-entities`.
Mark it ready when code-complete, before tests, and use the watch-pr skill.
One clean latest-code CodeRabbit **or** Codex review is enough. Use the installed
Windows CodeRabbit CLI if hosted quota is unavailable; no WSL or billing changes.
Give the reviewer the exact accepted baseline commit and relevant pinned helper
sources if it misreads an inherited signature. Preserve the complete receipt.

Deliver the PR/head and adapter hashes, complete diff ownership list, paired raw
timings/counts, source hashes, native/cold/visual receipts, test results, review
receipt and limitations. Keep the result open for VM1 integration. After rebase,
the full `uv run python -m doit -n 4` pipeline and affected render inspection
must pass on the integrated stack head before bottom-up merge. Do not mark this
batch merge-ready solely from the isolated crank checks.
