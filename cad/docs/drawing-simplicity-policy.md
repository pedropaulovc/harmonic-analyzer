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
  The cylinder-bank assembly settings also author their native dimension
  callout text in the builder; the drawing reads it back instead of calling
  `SetText` on imported dimensions. That call can write through to the source
  model, as the [rack source-save controls](pipeline/evidence/vm2-datum-placement/source-hash-cause.md)
  demonstrated. Source-clean guards remain fail-closed before drawing export.
  Purchased supplier-reference sheets retain the supplier's explicit units,
  precision, exact fractions and source bands rather than project fabrication
  controls. `_supplier_dimensions` formats a visible native value without
  assigning `SystemValue` or replacing numeric text; sizes are parenthesized
  and unit-labelled. Model-owned hidden construction carriers are explicitly
  nominal supplier references, not claims of physical-edge or helical-thread
  attachment. Thread identification is below-text on the native nominal-major
  carrier. Source bands remain model-owned. Reference sketches are authored in
  the final transformed stock frame by `_supplier_screw_reference`; only
  threaded builders import the separate `_supplier_screw_save` saver.
  Source ownership requires native `IDimension` identity both with the source
  parameter and with a dimension enumerated from the intended model feature;
  matching names or values alone cannot prove membership. `IFeature` wrapper
  equality is diagnostic only: drawing-context owners can compare unequal
  even when the original model dimension is identical.
  Purchased nuts additionally prove one exact centred construction chord and
  its two distinct endpoints. Source endpoints must exhaust the model sketch's
  point inventory; both drawing attachments must match different members of
  that inventory mapped through `IView.GetCorresponding`. Complete mapping,
  native self-comparison and known-negative comparisons remain mandatory.
  Raw drawing/model point inequality is not a failed correspondence.
  Their native nominal-major, across-flats and thickness text blocks use the
  shared measured-shelf convention: seed offset mode at the actual arrow
  station, then move the complete text beyond the outside-arrow tail without
  changing the physical witnesses. Every reported text fragment participates,
  including both fraction parts and all three nominal-major rows. Native
  station/extent proof is not exact glyph or foreign-line clearance proof;
  retain every line, including fraction bars, and inspect the actual PDF ink,
  whole sheet and automated machinist result after regeneration.
  Front and Right reserve the same vertical annotation margins before fitting,
  so their physical projection centres remain aligned without moving a fitted
  view or changing its shared scale; per-view horizontal budgets remain intact.
  The boss-hook nut keys its existing installation instruction to the visible
  boundary of its z=0 bearing face, the face seated on the summing-lever boss
  by the assembly recipe. A native attached leader and its single linked
  legend are re-proved after the final rebuild; this flag does not establish
  full-thread engagement or waive the physical shortfall review.
  Numeric border zones owned by the drawing template are not installation-key
  candidates. Sheet- or foreign-view duplicates still fail; the whole-inventory
  linked-legend and instruction uniqueness checks remain unchanged.
  The five nut stems additionally enforce `text-clearance`, `text-on-line`,
  `dim-line-through-own-text`, `text-on-view` and `arrow-near-text`.
  `extension-through-own-text` remains reported rather than newly enforced:
  its merged-row bounds can cross a legitimate fraction bar while individual
  PDF glyphs clear it. Retain the raw finding and inspect those glyphs; this
  does not waive genuine witness or tail collisions or machinist review.
  After native export closes each purchased-nut drawing, its normal drawing
  leaf reopens that exact SLDDRW read-only, reacquires Front and its nominal
  dimension, and repeats the native owner, value and distinct mapped-endpoint
  proof. The source path and original authoring Front configuration must
  survive unchanged; this proves binding persistence, not independent catalogue
  configuration correctness. The reader closes only its own newly opened
  drawing without saving, verifies unchanged drawing bytes, and remains within
  the purchased wrapper's source-file preservation guard.
  The purchased-sheet hook reserves annotation lanes before fitting and runs
  source/configuration, native attachment/value/inventory and cell/ink checks
  after the final rebuild. The rendered supplier comparison remains necessary;
  a pre-fit allowance is not evidence that native ink fits.
  The clamp screw selects the purchased sheet's `tall_top` layout: a 96 mm
  outer Top cell retains the existing 46 mm annotation reserve, leaving
  50 mm for the measured native outline. The bottom-row cells' tops and
  the Isometric's bottom lower 32 mm; other sheets keep `standard`.
  Scale selection still tries the existing standard scales against complete
  native outlines,
  without subtracting fixed sheet-space padding. Short clamp-reference text
  is shelved only when its measured extent cannot clear the native arrow
  span; the measured arrow/witness stations stay fixed and final native
  paths, text and cell containment remain checked. Missing, duplicate, foreign
  or wrong-view native references refuse with expected and observed inventories.
  This layout contract is not a substitute for the rendered comparison with
  the supplier drawing.
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
  and stack asserts enforce it. Through-tapped receivers use actual retained
  material and external full-form overlap, not blind drilling depths or raw
  screw insertion (for example `require_through_seat_fit` in the harmonic
  base's pure fastener contract). Receiver capacity does not by itself prove
  a purchased screw's installed engagement; existing inspected minima and
  owner-declared shortfalls remain explicit. The 1.5D engagement minimum and
  the rule-17 wall targets (2.0 mm
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

The owner's **2026-10-20** ruling for **MHA-FR-01 `fr-harmonic-base` RV-02**
accepts one nonnumeric departure from rule 2: redundant default **2B** in that
package's generated native hole-table **SIZE cells only**. The package-local
declaration in [`fr-harmonic-base.yaml`](../config/parts/fr-harmonic-base.yaml)
is the reviewer-consumed register. Physical model threads remain class 2B,
and the five separate native tap callouts still omit the duplicate class.
The generated cells are not rewritten. This is not a general native-table
exemption and accepts no other specification, geometry or numeric shortfall.

## The gate

`uv run cad/scripts/machinist_review.py <name>... --before-pdf-dir <baseline>`
compares baseline PDFs with the current registered PDFs (`--pdf-dir <after>`
selects another output directory). For an explicit package, use `--name <stem>`
with `--before-pdf` and `--pdf`; repeat each PDF option in matching
sheet-document order. PNG CLI input is not supported. Both PDF versions are
required unless `--force` requests an
unconditional review of the after PDFs.

Before starting independent reviews, the findings judge inspects the repository
PDF diff tool's **overlaid** before/after pictures: shared ink is gray, removed
ink red, and added ink blue. It may skip a package only when the differences are
rendering noise, or an assembly drawing changes only one part's geometry without
affecting mating shown on the drawings. SolidWorks balloon placement is unstable:
movement of a balloon or leader is noise when both its number and referenced
part/region remain unchanged. That noise may coexist with a skippable single-part
geometry change. A different number or target requires review, as does uncertainty
about either. This allowance does not extend to dimension changes or other
annotation edits. Proximity of a changed feature to a joint alone does not prove
a mating effect; the judge compares the depicted connections and relative
placement. A hypothetical hidden effect of a small local feature is not a
depicted mating change. Uncertainty grounded in the visible assembly evidence
still requires a full review.
An unchanged overlay is inspected too; an image-generation or precheck failure
is not permission to skip. The report retains the before/after identities,
overlay evidence and decision. A skip returns `SHIP` with an explicit warning
that the machinist review was skipped due to minimal changes, not a claim that
a full review ran. The precheck does not establish that the baseline was
approved, and PDF overlays cannot reveal changes to review rules or owner
exceptions. Use `--force` when those require reassessment. It bypasses the
precheck; build gates and prompt benchmarks use it for unconditional reviews.

Packages selected for review run three independent blind senior-machinist
reviews (`--runs N` changes the count). The same judge session that inspected
the overlays later merges their findings; independent reviewers do not receive
the baseline or precheck context. Each run receives `drawing-guidelines.md`
followed by the reviewer
instructions for the package kind (`cad/scripts/prompts/machinist_review_part.md`
or `machinist_review_assembly.md`), with its classification slot expanded from
the matching `machinist_review_<kind>_severity.md` contract. The isolated
judge inspects the after sheets and receives that same kind-specific classification
and evidence contract, not the reviewer's detection or report instructions.
It vets every finding against the guidelines, text layer and owner exceptions,
and clusters duplicate claims. Categories follow the contract's defect-type
precedence rather than the original filing: the judge corrects misfiled claims,
confirms real findings, rejects misreads, and keeps contract-defined minor or
accepted-exception claims non-gating. Complete `--prompt-file` rubric overrides
remain opaque; repository templates must be composed before use as overrides.
Historical benchmark composition pins the reviewer rubric, resolving its
severity contract from the same Git ref rather than the working tree. The
benchmark judge and its kind-specific contract still come from the working
tree for both configurations, as before this change. A confirmed
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
  means no confirmed gating findings and no aggregate error, or an explicitly
  warned minimal-change skip. If valid runs return zero findings, findings
  adjudication is skipped. If all runs fail, or the judge fails after
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
