# harmonic-analyzer review instructions

This repository builds a SolidWorks CAD reconstruction and the manufacturing
drawings a hobby machinist works from. **Codjiflo performs source-only code
review**, including CAD and drawing defects that can be established from source.
It does not perform native generation, visual sheet review or machinist signoff.

## Review boundary and separate author obligations

Review the PR-head diff and relevant source, configuration and documentation.
Do not run builds, tests, linters, native SolidWorks/COM operations, recipe
imports or drawing/render generation. Do not require those operations, generated
artifacts under `cad/out/`, regenerated sheets, visual inspection, a native seat
or a passing test run as prerequisites to completing this source review.
Missing native evidence is not by itself a Codjiflo finding or a reason for an
incomplete review. Do not infer a visual defect solely from an unrendered change.

**The author still must satisfy the repository's separate pre-merge native
geometry/readback, render inspection and sheet/machinist-review requirements.**
Affected sheets must be regenerated and reviewed under the direct/indirect
sheet policy in `cad/docs/drawing-simplicity-policy.md#the-gate`; automated
machinist review remains the default and human substitution still requires
explicit owner authorization. Codjiflo approval is only source-code approval:
it is not native sheet/machinist signoff and does not waive any global drawing
acceptance or merge gate.

Repository instructions about implementing, proving, generating or visually
reviewing CAD describe author obligations, not prerequisites for this read-only
Codjiflo review. Do not invoke implementation skills or treat their absence as
a review blocker. Read available applicable repository instructions as source
context; do not require unrelated area instructions for files outside that area.

## Applicability and required reading

Trace drawing-affecting changes through their source dependencies: drawing
scripts and specs/notes/sheet modules, drawing helpers, part and assembly
builders (`build_*.py`), their geometry/spec/config inputs, and machinist-review
machinery. For these changes read the relevant rules in
`cad/docs/drawing-guidelines.md` and their implementation in
`cad/docs/drawing-simplicity-policy.md` at the PR head. Read
`cad/scripts/prompts/machinist_review_<kind>.md` and its severity contract when
the change affects that reviewer or its inputs; this is source-contract review,
not a blind review of a sheet. A prose-only, web-only or infrastructure-only
change with no such dependency needs no CAD/drawing review.

Read the root `AGENTS.md` and applicable local `AGENTS.md` files present at the
PR head (`book/`, `logbook/`, `kickstarter/`, `web/`, `ai-story/`).

Owner rulings are recorded as code comments beside the constant they govern,
in a package's `machinist_exceptions` (`kind: accept` or `kind: minor`) in
`cad/config/parts/<dashed>.yaml` or `cad/config/assemblies/<dashed>.yaml`, or
in the policy's named-exception section. Do not re-raise a ruled matter. Do
flag a change that adds or widens such a ruling without stating that it is the
owner's ruling.

## Source-level CAD, drawing and review-gate checks

Apply these checks where the diff and relevant source support them. Cite the
guideline's rule number and title or the quoted policy sentence for a policy
finding, and identify the changed source and concrete failure scenario. Do not
claim the saved model or final sheet was inspected. Check at least:

- **Model owns tolerance and precision (rules 3, 4).** Bands are native model
  tolerances on the dimension. Precision is authored by the part build
  (`DRAWING_PRECISION`) and read back by the drawing. Flag a drawing change
  that newly introduces a render-time precision rewrite (`SetPrecision3`,
  `set_dimension_precision`) on a banded or controlling dimension, types a
  spec constant into note text (`f"{DEPTH:.1f} DEEP"`), or prints a value no
  model dimension carries. A pure reference dimension with no band and no
  model dimension to import may take its places from
  `DRAWING_REFERENCE_PRECISION`. The fleet migrates incrementally (migrated
  packages are gated by `test_drawing_specification_purity.py`): do not flag
  pre-existing unmigrated usage the diff only carries along. Callout text set
  through the shared `set_dimension_callouts` helper is established practice,
  not a violation by itself; flag it only where the policy names a
  builder-authored callout (for example the cylinder-bank settings) or when
  source-clean guards are removed.
- **No dimensions or methods in notes (rule 7).** Notes are few, flagged and
  never prescribe a machining method; dimensions, tolerances and assembly
  settings are associative native dimensions (hidden reference sketches when no
  feature carries the value), not free text.
- **Bands only for function, naming the mate (rule 4).** Flag a tight band
  whose mate appears nowhere in the package, or a band tightened where no
  running, sliding, sealing, locating or press function needs it (for
  example, where adjusting the nominal would let the title-block band hold the
  governing assert). Controlled limits on both parts of a pair are valid when
  they produce the required fit; interchangeable parts keep their essential
  limits. A matched pair needs the mate's name and number plus the required
  clearance or interference; "MATCH FIT" alone is incomplete.
- **GD&T allowlist (rule 5).** A feature-control frame or datum appears only
  where the package's own `machinist_exceptions` `accept` entry allows it.
  New frames, datums or boxed basics without one are findings.
- **Roughness (rule 6)** only from `_surface_finish` grades, on running,
  sliding or locating surfaces.
- **View construction (rules 8–15).** Check source-level view/configuration
  selection, visibility/finalization calls and dimension associations. Flag
  concrete layout arithmetic or placement defects supported by source, not
  speculative text overlap, leader crossings or final-sheet appearance.
- **Design for the shop (rules 16–21).** Walls/webs 2.0 mm target, 1.5 mm
  floor at the worst case; 1.5D thread engagement; fit-up adjustment only as a
  last resort; thresholds never loosened to admit a shortfall; a shortfall is
  stated as a plain fact only with a matching user-ruled `minor` entry; a
  geometry defect is fixed in the model, not papered over on the sheet.
- **Assemblies (rules 22–24).** Package completeness, mechanical locks for
  threaded joints under operating load (threadlocker is never the default),
  assembly sheets carry assembly information only.
- **Governance boundaries.** `cad/docs/drawing-guidelines.md` stays pristine:
  no part-specific callouts, PR/issue references, dated rulings or concrete
  part examples (examples use abstract `n.nn` templates). Per-package
  adjustments live only under that package's own key, never in a central file.
  `drawing-simplicity-policy.md` is author-side and must never reach a
  machinist reviewer or judge prompt. Printed text carries no rule numbers,
  ruling ids or governance words.
- **Opt-in mode.** A `MACHINIST_REVIEW` change from `ENFORCE` to `LEARN` or
  `OFF`, or a new `machinist_exceptions` entry, needs a stated owner reason.

### SDK and native API contracts

For changed adapter calls, check method existence, signatures, inherited mixins
and delegated helpers against the vendored `PyWin32Adapter` source where
available. For changed SolidWorks API calls, inspect any prepared local reference
under `$CODEX_HOME/plugins/cache/*/developing-solidworks/*/skills/developing-solidworks/`
(use `$HOME/.codex` when `CODEX_HOME` is unset). Read its `docs/`, `index/`,
`types/`, `enums/` and `examples/` directories directly; OMP disables skill and
rule discovery. These optional caches are provisioned separately by the runner
operator, not as a prerequisite to every review. If absent, continue with the
vendored source and repository documentation. Use read-only source/static/AST
analysis without importing recipes, constructing adapters or running test suites.
Do not invent an adapter method from the operation's name. If an API contract
cannot be resolved from available source/docs, identify the specific uncertainty
without claiming a verified mismatch or requiring native execution to finish.
Static API agreement does not prove native geometry or saved-artifact behavior.

### Source-level machinist-review contracts

Trace values and relationships across source packages to find concrete
contradictions, omitted manufacturing information, unbuildable geometry,
over-specification, BOM/step disagreements, missing acceptance criteria or
unlocked loaded threaded joints. These remain in scope when supported by the
source, even though Codjiflo does not inspect or certify the printed result.

Also flag changes to the review machinery that would bias it: prompts that
reward hunting for missing tolerances, reviewer input that leaks author-side
policy or another kind's template, judge or gating changes (`GATING_MIN_RUNS`,
verdict computation, caching of `FIX`) that weaken the gate, or review inputs
removed from the cache key.

## Code review (adapted e-code-review xhigh)

Recall-oriented: surface a nameable concrete failure scenario even when
uncertain; do not invent findings to fill a quota.

**Phase 1: candidates.** Run these ten angles in sequence in this context; do
not spawn subagents. Each surfaces up to eight candidates; one angle's
conclusion never suppresses another's.

1. Line-by-line diff scan. Read every hunk and its enclosing function; unchanged
   lines of a touched function are in scope. Ask what input, state, timing or
   platform makes each line wrong: inverted conditions, off-by-one, null
   dereference, missing `await`, falsy zero, wrong-variable copy, swallowed
   exceptions, unescaped regex metacharacters.
2. Removed-behavior auditor. For each deleted or rewritten line, name the
   invariant it enforced and find where the new code re-establishes it: dropped
   guards, error paths, narrowed validation, deleted live test coverage.
3. Cross-file tracer. Find callers of each changed function; check new
   preconditions, return shapes, exceptions and ordering. Check callees made
   unsafe by parallel changes.
4. Language pitfalls: Python mutable defaults, late-binding closures,
   PYTHONHASHSEED-salted `hash()` in anything persisted or keyed, float
   equality, Windows path/encoding/CRLF handling, COM late- versus early-binding
   and out-parameter shapes, PowerShell quoting.
5. Wrapper/proxy correctness: wrappers route to the wrapped instance and
   forward every method callers use.
6. Reuse: name the existing helper the new code re-implements.
7. Simplification: redundant state, copy-paste variants, deep nesting, dead
   code.
8. Efficiency: redundant work or I/O, sequential independent operations, work
   added to hot paths or startup, COM seat time wasted.
9. Altitude: the fix addresses the root cause at the right depth; a special
   case layered on shared infrastructure is a finding.
10. Conventions: quote an exact rule from the applicable `AGENTS.md` and the
    exact violating line. Repository-specific rules to check include: COM work
    only through `_cached_com_action`; machine-stable `file_dep`s and outputs
    under `cad/out/`; recipe closures are file-granular, so unrelated imports
    widen cache keys; inert modules (`_seat_forensics`, `_telemetry`,
    `_watchdog`) only at pinned call sites; status logging through
    `_telemetry`, not `print`; new COM entry points open a span; new
    `_config` accessors mapped in `_buildgraph`; new `test_*.py` enrolled in a
    `check:*` gate; no CadQuery code; no backwards-compatibility shims; Ruff
    `F821` fixed by definition, never `# noqa`.

Cleanup, altitude and conventions candidates state the concrete cost in place
of a crash scenario.

**Phase 2: dedup only.** Pool candidates; merge only same defect, same
location, same reason. Do not run verifiers or drop on uncertainty.

**Phase 3: gap sweep.** Re-read the diff and enclosing functions as a fresh
reviewer looking only for defects not yet listed (up to eight): moved code
that dropped a guard; nondeterministic hashing or ordering feeding a cache
key or digest; lock-scope shrink; setup/teardown asymmetry; flipped defaults.

## Ranking and output

Rank by severity: P0 critical, P1 high, P2 normal, P3 low. Mark a finding
`blocking` when it must be fixed before merge. Source-level defects that would
produce a bad drawing or weaken the machinist gate can be blocking; missing
native generation, sheet review or test evidence alone is not a source defect.

When the output cap forces a cut, keep P0/P1 correctness bugs first, then
remaining correctness and source-level CAD/drawing/gate defects, then cleanup,
altitude and conventions. In the summary, state the source scope reviewed, any
specific unresolved source/API uncertainty and any cut findings. State that
native generation and visual sheet/machinist review were not performed and
remain separate author pre-merge obligations; do not present source approval as
that signoff.
