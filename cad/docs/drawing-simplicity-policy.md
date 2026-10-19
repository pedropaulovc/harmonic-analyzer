# Drawing simplicity policy

The drawing standard itself is [`drawing-guidelines.md`](./drawing-guidelines.md):
one set of numbered rules for part and assembly packages, followed by authors
and sent verbatim to the blind machinist reviewer. This file holds what the
reviewer must not see: how the repository implements those rules, where
per-part adjustments live, and the review gate. Per-part and per-assembly
adjustments are declared as `machinist_exceptions` under the package's own key
in `cad/config/parts/<dashed-name>.yaml` or
`cad/config/assemblies/<dashed-stem>.yaml`, and only the reviewed package's
own declarations reach its reviewer. Cite rules by the guideline's number and
title, for example "rule 5 (avoid excessive GD&T)".

It supersedes the "full GD&T vocabulary, applied functionally" verdict of
[`tolerance-gdt-assessment.md`](./tolerance-gdt-assessment.md) §1 wherever the
two disagree: that assessment listed what GD&T *could* express; the guidelines
fix what the prints *do* carry.

## Why

The fleet grew ~125 feature-control frames, 100+ datum tags, roughness symbols
on gear seats and hand-crank bores, boxed basic dimensions on non-critical
holes, and 5-12-line note blocks. Most of it came from adversarial "senior
machinist" reviews prompted to hunt for *missing* tolerances, datums and
finishes: a reviewer rewarded for gaps asks for a production-line inspection
package. Authors and reviewers now work from one standard, so a reviewer
cannot ask for what the authors were told to leave out.

## How the repository implements the guidelines

- **The model owns tolerance and precision (rules 3 and 4).** A band goes on
  the dimension as a native model tolerance
  (`_drawing_tolerances.set_dimension_*_tolerance`). Decimal places are authored
  by the part build (`<part>_spec.DRAWING_PRECISION`, applied natively on the
  `.SLDPRT`); the drawing imports the dimension verbatim and reads the
  precision back to prove it. A drawing script never rewrites precision at
  render time (`SetPrecision3`, `set_dimension_precision`) or types a spec
  constant into note text (`f"{DEPTH:.1f} DEEP"`). A value the sheet prints
  but no feature dimension carries is modelled, if need be by a hidden
  reference sketch whose one driving dimension is the value. The one
  exception is a pure reference dimension with no band and no model dimension
  to import; its places come from a `*_spec` constant
  (`DRAWING_REFERENCE_PRECISION`), never a literal. Migrated packages are
  gated by `test_drawing_specification_purity.py`; the rest of the fleet
  migrates incrementally.
  Purchased VN sizes are pure references: retain the supplier engineering
  drawing's units, fractions and displayed precision separately from the
  exact model value (for example 7/16 inch remains 11.1125 mm when displayed
  as .438 in). `_supplier_dimensions.supplier_reference_dimension` checks the
  native type/value and applies local units, precision and reference text
  without rebuilding between selections. It never changes the numeric value
  or supplies numeric replacement text. Supplier tolerance bands remain
  reference information; project general tolerances do not control purchased
  sizes. Finished/custom modification dimensions remain controlling and do
  not use this formatter.
  Shared purchased builders accept a synchronous optional
  `supplier_dimensions(adapter, views_by_orientation)` callback, keyed by
  `*Front`, `*Top`, `*Right` and `*Isometric`, after final view fitting and
  before the native contracts. Captions stay at the cell floor only on views
  carrying native supplier dimensions, reserving their existing cell whitespace.
  Dimensions must fit without silently reducing the geometry-selected view scale.
  Each hooked build supplies a build-local `settled_checks` sequence; the
  callback may append read-only closures before the builder forwards that same
  sequence to `finalize_drawing`. After its last rebuild and before saving,
  checks reacquire current native dimensions/attachments and use
  `_supplier_dimensions.assert_supplier_reference_dimension` plus source-specific
  attachment, tolerance and required-count assertions.
  The fastener builder also accepts `configuration="SupplierStock"` (or
  another saved configuration name) for a stock-state sheet: every view selects
  it and rebuilds before scale fitting, and the native contract verifies it
  again. This does not change the saved part's active/installed configuration.
  Sourced operating/suitability facts that have no honest geometric state may
  use `supplier_data=(...)`: a separate `SUPPLIER OPERATING DATA (REFERENCE)`
  footer block. Its full height is reserved before fitting, independently of
  the installation-note budget; it does not create fictitious model geometry.
- **Roughness grades (rule 6)** are the `_surface_finish` constants:
  `MACHINED_UM` (1.6) on `shaft_in_bushing` journals and bores,
  `cam_follower_contact` faces, the amplitude-bar slide, the knife edge and
  its seat; `GROUND_UM` (0.8) on knife edges and pivot-screw shoulders;
  `SEAT_UM` (3.2) on the one locating seat.
- **Notes (rule 7)** that live in `<part>_notes.py` stay there. A
  drawing-only note helper enters a part's rebuild closure only if its builder
  imports it. When a builder stamps notes into a saved model property, that
  helper is a part recipe input: a note edit rebuilds or restores the part
  under the changed key before a property-linked drawing can print it.
- **Views (rules 8–10).** A cut-surface-only section uses
  `IDrSection::SetDisplayOnlySurfaceCut` and never shows hidden lines. A Hole
  Wizard placement sketch cannot carry a datum point (every point in it is a
  hole), so a hole's model dimensions stay origin-based and the print
  dimensions it from the datum feature with a driven dimension picked on both
  features.
- **Layout (rules 13–15).** Each `DrawingSpec` records its sheet orientation.
  The layout audit (`_drawing_layout_check`) checks the template's border and
  title-block keep-out; the machinist review judges containment, balance and
  fit of every visible element. An eye pass never substitutes for it (merge
  gate 3 in the root `AGENTS.md`).
- **Fit-up at assembly (rule 19) is a last resort.** Slots, shims, cut-to-fit
  and match-drilling open space for sloppy work, so avoid them as much as
  possible: prefer geometry whose loose bands hold the stack at the worst
  case. A stated fit-up adjustment is the escape hatch when the stack cannot
  be held otherwise — never the design default.
- **Thread engagement (rule 18)** is owned by the CAD: the build's seat-fit
  and stack asserts (for example `require_blind_seat_fit`) enforce it. Today
  they check only ≥ 1D; raising them to 1.5D at the worst case is follow-up
  work. The 1.5D engagement minimum and the rule-17 wall targets (2.0 mm
  target, 1.5 mm floor) exist to be forgiving to a first-time hobby machinist:
  they are design margins for the shop class the guidelines describe, not
  capability limits.
- **Retention (rule 23).** Mechanical locks are the default, in preference
  order: dowels, set screws, jam nuts, cross-pins, keys or flats with axial
  capture, pinch clamps — then a brazed joint — then peening. Threadlocker is
  an option, never the default; on its own it locks nothing (rule 23).
  `cad/scripts/joint_retention.py` lists every threaded joint and audits the
  rule (`check:joint_retention`).
- **Legacy assembly sheets.** Three-view sheets from
  `drawing_recipe_assembly.md` are orientation placeholders and are expected
  to fail review until they are built out to rule 22.
- **Model defects found in review (rule 21).** Check the finding against the
  source CAD and primary visual evidence. Fix a uniquely supported omission in
  the CAD and regenerate. When the evidence permits materially different
  geometries or processes, escalate the feature, the evidence and the viable
  options to the user, with a sketch comparing them. A reviewer can be wrong:
  validate the premise rather than implementing its proposed fix.

## GD&T allowlist (rule 5)

A feature-control frame and its datums appear only where rule 5's functional
classes demand one and the project owner has accepted the specific control.
Which features may carry frames is a per-part adjustment: it is declared as a
`machinist_exceptions` entry (kind `accept`) under the package's own key in
its config YAML, carrying the functional reason, and only the reviewed
package's own declarations reach its reviewer. Everything else carries no
frames and no datums. A new entry needs a user ruling.

## Named exceptions

A shortfall against rules 17–19 (or another numeric rule) is acceptable only
by the user's own ruling, declared as a `machinist_exceptions` entry (kind
`minor`) under the package's own key in its config YAML. No one else rules,
and the thresholds are never loosened to admit a shortfall. Each entry is
specific to the part it names; it is not precedent.

The sheet states the shortfall as a plain manufacturing fact (rule 20);
`test_printed_text_rulings` keeps rule numbers, ruling ids and governance
words off printed text. The blind reviewer reports a stated shortfall under
minor. Whoever runs the gate matches each one to the part's declared entry
(same parts, shortfall within the declared range). A stated shortfall with no
matching declaration gates the package like a blocker. An emitter of an
approved declaration carries a comment naming it.

## The gate

`uv run cad/scripts/machinist_review.py <name>...` (or `--all`) runs three
independent blind senior-machinist reviews per package (`--runs N` changes the
count). Each run receives `drawing-guidelines.md` followed by the reviewer
instructions for the package kind (`cad/scripts/prompts/machinist_review_part.md`
or `machinist_review_assembly.md`). A separate isolated judge inspects the sheets,
vets every finding against the same guidelines, text layer and owner exceptions,
and clusters duplicate claims. It confirms real findings, rejects misreads, and
demotes advisory or accepted-exception claims to non-gating `minor`. A confirmed
finding gates only when at least two runs raised it independently (owner ruling
2026-10-18; `GATING_MIN_RUNS`, reduced to the number of valid runs when fewer
than two are valid). A confirmed finding from one run stays in the report as
non-gating evidence: across repeated rounds, lone confirmations moved from
round to round while the sheet itself converged.

The gate covers every sheet whose rendered output a PR changes, including a
sheet that changes only because CAD geometry, config or a helper it reads
changed. A sheet the PR's own drawing script or spec edits must pass as below.
A sheet changed only indirectly passes when its review adds no gating finding
beyond a review of `main`'s version of the same sheet run with the same
reviewer, model, effort and prompt (the report records each); the PR records
both verdicts and the finding diff.

- **Review with Claude Opus 5.5 by default** (`--reviewer claude`,
  `claude-opus-5-5` at medium effort). The machinist review does not follow
  the cross-family rule for code review: Opus may review every drawing,
  whichever model authored it. Another reviewer (`--reviewer codex`, or
  `--model claude-fable-5-1`) is allowed, for example when Opus is over
  quota; record the reviewer and model in the PR. An 80-case benchmark ranks
  Opus highest on expectations met at about a third of Fable's cost.
- Every review and judge must view every sheet through the private sheet server;
  full-resolution crops resolve fine detail. A contact sheet alone is not proof.
  The judge defaults independently to Claude Opus 5.5 at medium effort
  (`--judge-reviewer`, `--judge-model`, `--judge-effort` select alternatives).
- Before either Claude session receives its review/judge prompt, the runner uses
  that same CLI process's SDK control channel to await the private `sheets`
  connection and its `view_sheet`/`crop` tool catalogue. A separately probed
  server or a generic initialization event is not readiness evidence. Startup
  is bounded to 120 seconds within the existing per-attempt timeout; failed or
  incomplete connections retry as infrastructure errors in fresh isolated
  sessions, without submitting a drawing review. Startup diagnostics remain in
  retained raw stdout; SDK control responses are excluded from reviewer tool
  evidence. Valid drawing findings are not retried.
- The authoritative result is `<name>.aggregate.json` and its companion
  `<name>.aggregate.md`, not an individual run's verdict. `FIX` means at least one
  **confirmed** blocker, over-specification or clarity finding raised by two or
  more runs. Confirmed minor findings, single-run confirmations and rejected
  clusters remain in the report but do not gate. `SHIP`
  means no confirmed gating findings and no aggregate error. If valid runs return
  zero findings, the judge is skipped. If all runs fail, or the judge fails after
  retries (including incomplete/duplicate finding coverage), the result is
  `ERROR` and exits nonzero. Partial run failures remain visible alongside valid
  evidence; run reports and isolated judge transcripts are retained separately.
- A review counts as a merge gate's visual check only on the exact drawing
  version being merged.

Use `uv run cad/scripts/machinist_review_bench.py run --workspace <outside-git-root>
--evals <id-or-name>... --reviewer claude --baseline-ref origin/main` to compare
release-package reviews with the working-tree skill (`with_skill`) and the
baseline skill (`old_skill`); `--ref <git-ref>` pins `with_skill` instead.
Review model and reasoning controls are `--model` and `--effort`.
Use `--baseline-ref none` to run only `with_skill`, without loading or reviewing
the baseline prompt.
Alternatively, `import --workspace <outside-git-root> --evals <id-or-name>...
--config with_skill=<review-directory> --config old_skill=<review-directory>`
enrolls existing reviews without running another reviewer.
A single `--config with_skill=<review-directory>` or
`--config old_skill=<review-directory>` is also allowed; only the supplied
configuration is graded and displayed, with no comparison or delta columns.
Both commands create
an `iteration-N` outside Git, with descriptive eval names and per-configuration
`run-K/outputs/review.json`. Run `grade <iteration-directory>` to grade it with
Codex (defaults: `gpt-6.1-sol`, medium); `--grader-model`, `--grader-effort`,
`--grader-timeout` and `--jobs` control grading. Aggregation writes
`benchmark.json`, `benchmark.md`, and `failures.json`; failed assertions retain
their rule, polarity, confidence and grader evidence, with unknown legacy rule
or confidence recorded as `null`. Then run
`view <iteration-directory> --static <output.html>` for the skill-creator
viewer; `--skill-creator-path <checkout>` selects its installation. The bench
viewer includes formatted findings with highlighted rule citations and the
release drawing sheets, with links to full-size sheet images. Omit
`--workspace` to use `$HARMONIC_AGENT_SCRATCHPAD/harmonic-analyzer/machinist-review-evals`,
or, when unset,
`%LOCALAPPDATA%/harmonic-analyzer-agent-scratchpad/harmonic-analyzer/machinist-review-evals`.
The benchmark measures release-package/LLM review regressions; the separate
`machinist_review_eval.py` remains the frozen-PNG/human calibration tool.
A case whose drawing was renamed after its release names the current registry
package and the release's PDF basename in `release_pdf`; run and import read
that PDF.

Regression tests defend observable manufacturing contracts and plausible
failures, not note wording, line counts or mocked API-call sequences. Native
drawing generation verifies persisted dimension values, tolerances, reference
state and required view modes. A finish attachment identifies the controlled
model face and keeps its physical leader landing, not merely a non-dangling
transient silhouette. A sheet-derived linear reference reads back a linear
native dimension type before its system value is read as a length.
