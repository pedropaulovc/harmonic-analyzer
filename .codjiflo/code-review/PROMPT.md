# harmonic-analyzer review instructions

This repository builds a SolidWorks CAD reconstruction and the manufacturing
drawings a hobby machinist works from. A code change that compiles but
degrades a drawing ships a bad print. Review in three tiers, **in this order**,
and complete each tier before starting the next:

1. **Drawing simplicity policy** (tier 1)
2. **Machinist review lens** (tier 2)
3. **Code review: adapted e-code-review xhigh recipe** (tier 3)

Use repository tools to read files at the PR head. Cite every tier 1 and tier 2
finding by the guideline's rule number and title (for example "rule 5 (avoid
excessive GD&T)") or by the quoted policy sentence.

## Applicability and required reading

First decide from the diff whether the drawing tiers apply. They apply when
the diff can change a printed sheet or the machinist-review gate: drawing
scripts and their specs/notes/sheet modules, drawing helpers, part and
assembly builders (`build_*.py`), geometry and spec modules a builder reads,
`cad/config/`, and the review machinery (`machinist_review*.py`,
`cad/scripts/prompts/`, the guidelines and the policy). The policy's gate
covers "a sheet that changes only because CAD geometry, config or a helper it
reads changed", so a geometry-only change reaches tiers 1 and 2 through the
drawings that depend on it. A prose-only, `web/`-only or infrastructure-only
diff with no such path skips tiers 1 and 2; say so in the summary.

When the drawing tiers apply, read these at the PR head first:

- `cad/docs/drawing-guidelines.md`: the numbered rules (1–25) every part and
  assembly package follows.
- `cad/docs/drawing-simplicity-policy.md`: how the repository implements those
  rules, the GD&T allowlist, named exceptions and the machinist-review gate.
- `cad/scripts/prompts/machinist_review_part.md`,
  `cad/scripts/prompts/machinist_review_assembly.md` and their
  `machinist_review_<kind>_severity.md` contracts: what the blind machinist
  reviewer checks and how findings are classified.

Always read the root `AGENTS.md` and the `AGENTS.md` of every area a changed
file sits in (`book/`, `logbook/`, `kickstarter/`, `web/`, `ai-story/`).

Owner rulings are recorded as code comments beside the constant they govern,
in a package's `machinist_exceptions` (`kind: accept` or `kind: minor`) in
`cad/config/parts/<dashed>.yaml` or `cad/config/assemblies/<dashed>.yaml`, or
in the policy's named-exception section. Do not re-raise a ruled matter. Do
flag a change that adds or widens such a ruling without stating that it is the
owner's ruling.

## Tier 1: drawing simplicity policy

Applies per the applicability section above. For a geometry-only change,
judge the regenerated sheets of the affected parts and assemblies: walls,
engagement, access and stack consequences (rules 16–21) and any printed value
that moves. Check at least:

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
- **Views and layout (rules 8–15).** Shaded isometric present and in the
  `set_hidden_lines_removed` loop before finalization; internal shape in solid
  lines; dimensions from real features; text off the part and inside the
  border; add a sheet before cramming.
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

## Tier 2: machinist review lens

For every changed drawing script, spec, note, sheet, builder geometry or
config value that reaches a printed sheet, predict the printed result and
read it as the blind reviewer in `machinist_review_part.md` /
`machinist_review_assembly.md` would: one package, no CAD, no context, no one
to ask. Flag what that reviewer would
confirm under the severity contract:

- **Blockers:** contradictions across views or sheets (rule 25), missing
  information needed to make or check the part, unbuildable geometry.
- **Over-specification:** anything rule 1 calls extra (redundant tolerances,
  thread classes on callouts, roughness everywhere, inspection plans).
- **Clarity:** text over the part, leader crossings, crowded callout blocks,
  a lengthened callout that will shift a shoulder or leader.
- For assemblies: BOM/balloon/step disagreement, a step that installs a part
  the package does not contain, a check with no acceptance criterion, an
  unlocked loaded threaded joint.

Also flag changes to the review machinery that would bias it: prompts that
reward hunting for missing tolerances, reviewer input that leaks author-side
policy or another kind's template, judge or gating changes (`GATING_MIN_RUNS`,
verdict computation, caching of `FIX`) that weaken the gate, or review inputs
removed from the cache key.

## Tier 3: code review (adapted e-code-review xhigh)

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
`blocking` when it must be fixed before merge. Tier 1 and tier 2 violations
that would reach a printed sheet or weaken the machinist gate are blocking.

When the output cap forces a cut, keep findings in this order: tier 1 and
tier 2 blockers and every P0/P1 correctness bug first, then remaining tier 1,
then tier 2, then tier 3 correctness, then tier 3 cleanup, altitude and
conventions. In the summary, state which tiers applied, which were not
applicable (for example, no drawing-affecting change), and any cut findings.
