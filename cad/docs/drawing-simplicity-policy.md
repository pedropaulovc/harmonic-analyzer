# Drawing simplicity policy

The drawing standard itself is [`drawing-guidelines.md`](./drawing-guidelines.md):
one set of numbered rules for part and assembly packages, followed by authors
and sent verbatim to the blind machinist reviewer. This file holds what the
reviewer must not see: how the repository implements those rules, the
project-specific GD&T allowlist, the named exceptions, and the review gate.
Cite rules by the guideline's number and title, for example "rule 5 (avoid
excessive GD&T)".

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
  gated by `test_drawing_specification_purity.py`; the rest of the fleet is
  #766.
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
  fit of every visible element.
- **Thread engagement (rule 18)** is owned by the CAD: the build's seat-fit
  and stack asserts (for example `require_blind_seat_fit`) enforce it. Today
  they check only ≥ 1D; raising them to 1.5D at the worst case is #846.
- **Retention (rule 23).** `cad/scripts/joint_retention.py` lists every
  threaded joint and audits the rule (`check:joint_retention`).
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

A feature-control frame and its datums appear only on these features
(assessment §2 plus the user's later rulings). Everything else carries no
frames and no datums.

- **Knife-edge system.** The knife-mount 2X dowel-hole pattern (one position
  frame under its 2X Ø, Ø0.13 to the top seat, datum A, at the BASIC 12.700
  span, datum feature B on that frame), its bore (⌖Ø0.20 to A|B with ⊥Ø0.05
  to B stacked under it) and its #6-32 hanger tap (Ø0.10 to A|B, so the
  crossbar's Ø4.318 clearance hole still floats round the screw); the top
  frame's two knife-hanger dowel slots (⌖0.05 to the round dowel hole at
  their own station, BASIC 12.700 from it, datum B front / C rear, B|C▷ and
  C|B▷, so the two knife mounts' dowel lines stay square to the knife-edge
  line); the summing-lever knife seat and its 20-hole spring pattern (one
  pattern position frame).
- **Cams.** The pinion-cam eccentric-axis position, and any future cam.
- **Channel consistency.** At most one control per channel part (rocker arm,
  channel lever, amplitude bar, connecting rod) where a coordinate ± would let
  the 20 channels scatter.
- **Crank mesh.** MHA-DT-005's crank bore: one diametral angularity frame to
  the cone-journal bore (datum A), clocked by the foot seat (datum B), with the
  plan angle basic. The fixed-centre 16T:64T crossed mesh loses running
  clearance to yaw and tilt of the crank axis (#906; user ruling 2026-09-28:
  the mesh must never bind).
- **Disc cluster.** The MHA-PD-006 120T disc's rear face parallel to its clamp
  face (datum B); the MHA-PD-017 hub's flange rear face and spigot end square
  to its bore (datum A); the MHA-PD-010 sleeve's step face square to its bore
  (datum A). The clamped disc's rim wobble must stay inside the disc-to-platen
  air (user ruling 2026-10-02).
- **Hanger pivot.** The MHA-PD-020 pivot spacer's two faces square to its
  pressed bore (datum A): the preloaded MHA-VN-049 spring seats the hanger on
  them, so their squareness is the hanger's only tilt.

A new entry needs a user ruling.

## Named exceptions

A shortfall against rules 17–19 (or another numeric rule) is acceptable only
by the user's own ruling, recorded as a row below. No one else rules, and the
thresholds are never loosened to admit a shortfall. Each row is specific to
the parts it names; it is not precedent.

The sheet states the shortfall as a plain manufacturing fact (rule 20);
`test_printed_text_rulings` keeps rule numbers, ruling ids and governance
words off printed text. The blind reviewer reports a stated shortfall under
minor. Whoever runs the gate matches each one to a row here (same parts,
shortfall within the recorded range). A stated shortfall with no matching row
gates the package like a blocker. An emitter of an approved row carries a
comment naming that row.

The table was reset on 2026-10-11. Earlier rows, several ruled by coordinating
agents rather than the user, are pending the user's decision on each part's
machinist-review issue. Until the user rules (restore the row / change geometry),
emitters of reset rows carry `# Pending exception ruling: <part> <shortfall> (#issue)`.
The sheet still states the shortfall as a plain fact (rule 20); until a row is
restored, the affected packages fail the gate.

Reset rows are recorded on issues #967, #968, #971, #974, #975, #976, #986,
#989, #991, #992, #994, #1019, #1294, #1295, #1367, #1368, #1369, #1370,
#1371, #1372, #1373, #1374, #1375, #1376, #1377, #1378, #1379, #1380,
#1381, #1382, #1383, #1384, #1385, #1386 and #1387.

| parts | shortfall | why accepted | ruled |
|---|---|---|---|

## The gate

`uv run cad/scripts/machinist_review.py <name>... --reviewer <claude|codex>` (or
`--all`) renders each package's verdict from a blind senior machinist. The
prompt is `drawing-guidelines.md` followed by the reviewer instructions for
the package kind (`cad/scripts/prompts/machinist_review_part.md` or
`machinist_review_assembly.md`).

- **The reviewer MUST be a different model family from whoever authored or
  last edited the drawing script.** An agent on a Claude model (Fable, Opus,
  Sonnet) reviews with `--reviewer codex`; an agent on a Codex/GPT model
  reviews with `--reviewer claude`. A same-family review does not count, even
  when it returns `SHIP`. If the cross-family reviewer is over quota, the
  user's standing last-resort rule applies: work authored by Sol or Opus is
  reviewed by Astra or Fable, and work authored by Astra or Fable by Astra or
  Fable at high reasoning. Defaults: `claude-fable-5-1` at medium effort,
  `gpt-6-astra` at low.
- Every native PDF page is rendered at 300 dpi and all sheets go to one
  review. A downscaled contact sheet is not a substitute.
- A package passes on `SHIP` with no blocker, over-specification or clarity
  finding; minor findings are recorded, not gating. The runner passes `SHIP`
  only. A `FIX` whose only gating findings match a named exception still
  exits nonzero; accept it by hand, citing the row in the PR, and state the
  shortfall on the sheet so the reviewer files it under minor next time.
- A review counts as a merge gate's visual check only on the exact drawing
  version being merged.

Regression tests defend observable manufacturing contracts and plausible
failures, not note wording, line counts or mocked API-call sequences. Native
drawing generation verifies persisted dimension values, tolerances, reference
state and required view modes. A finish attachment identifies the controlled
model face and keeps its physical leader landing, not merely a non-dangling
transient silhouette. A sheet-derived linear reference reads back a linear
native dimension type before its system value is read as a length.
