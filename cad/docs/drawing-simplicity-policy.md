# Drawing simplicity policy

> Defines the contract for generated manufacturing drawings that have been
> migrated to it. A sheet opts in through its policy-specific offline contract;
> legacy sheets retain their previous drawing contract until that migration is
> complete. Supersedes the "full GD&T vocabulary, applied functionally" verdict
> of [`tolerance-gdt-assessment.md`](./tolerance-gdt-assessment.md) §1 for those
> migrated sheets wherever the two disagree: that assessment listed what GD&T
> *could* express; this policy fixes what the migrated prints *do* carry.
> Enforced by each migrated sheet's offline contract and by its machinist review
> (`cad/scripts/machinist_review.py`).

## Why

The fleet grew ~125 feature-control frames, 100+ datum tags, roughness symbols
on gear seats and hand-crank bores, boxed basic dimensions on non-critical
holes, and 5-12-line note blocks. Most of it came from adversarial "senior
machinist" reviews prompted to hunt for *missing* tolerances, datums and
finishes: a reviewer rewarded for gaps asks for a production-line inspection
package. The actual audience is a hobby machinist making one-off parts on a
manual mill and lathe with a DRO, checking them with a rule, caliper,
micrometer and a dial indicator. A print for that audience has **no
questions** and **nothing that is not needed to make the part** — the two
tests the shop-practice literature agrees on (Harvey, *Machine Shop Trade
Secrets*, ch. 9 "Help for Engineers"; Lipton, *Metalworking Sink or Swim*, ch.
2-3 on drawings, tolerancing and respecting the shop's time).

## The rules

1. **The title block is the general specification.** Units, `.XX` / `.XXX`
   linear tolerances, angular tolerance, the DRILLED HOLES `+0.10 / 0` row,
   edge break, the surface row, material and finish live there and nowhere
   else. A note or callout never restates them. The surface row is a process
   statement (`CAST/MACHINED`), not a roughness number: a part may
   be cast or cut from bar, as-cast skin can never meet a number, and "as
   machined" on a manual machine already lands where a general grade would.
   Where material is non-critical, name the acceptable families as explicit
   alternatives (`material_family` in the part registry, e.g.
   `LOW-CARBON STEEL OR GRAY IRON`) instead of forcing an unsupported grade or
   saying "material not critical". For a coated ferrous part, the Finish field
   also carries any masking and bare-surface corrosion protection; those
   instructions do not belong in Manufacturing Notes.
2. **Decimal places carry the tolerance, and the MODEL owns both.** A
   dimension with no explicit band is governed by its decimal places. A
   tighter band goes ON that dimension as a native model tolerance
   (`_drawing_marks.set_dimension_*_tolerance`), never in a note and never
   as a frame. Three decimals mean "hold it"; two mean "routine". Do not
   print three decimals on a routine feature. The decimal places are
   likewise a property of the model dimension: the part build authors them
   (`<part>_spec.DRAWING_PRECISION`, applied natively on the `.SLDPRT`) and
   the drawing imports the dimension verbatim, reading the precision back to
   prove it. A drawing script that rewrites precision at render time
   (`SetPrecision3`, `set_dimension_precision`) or types a spec constant
   into note text (`f"{DEPTH:.1f} DEEP"`) is hiding a part without its
   tolerance: the nominal the shop reads must be the model's value, at the
   model's precision, with the model's band. A value the sheet prints but no
   feature dimension carries is not an exemption -- model it, even if that
   takes a hidden reference sketch whose one driving dimension IS the value.
   The single exception is a pure REFERENCE dimension: a read-only restatement
   of values the model already owns, carrying no band and having no model
   dimension to import. Its places are still specification, so a migrated
   sheet reads them from a `*_spec` constant (`DRAWING_REFERENCE_PRECISION`),
   never from a literal. Migrated packages are gated by
   `test_drawing_specification_purity.py`; the remaining fleet is #766.
   A matched-fit callout identifies the mating part by name and its drawing
   or part number when assigned, and states the required clearance,
   interference, or unambiguous functional acceptance. Specify diametral or
   radial clearance where applicable. "MATCH FIT" alone is incomplete.
   When the nominal is reference-only, the finished identified mate and the
   stated acceptance define the fit; the nominal does not. Any retained
   dimensional limits still apply. On assembly sheets, an item reference may
   supply the identity when the package's BOM gives that item's name and
   assigned drawing or part number unambiguously.
3. **Geometric tolerancing is a last resort.** A feature-control frame (and
   the datums it needs) appears only where a ± on a dimension cannot express
   the requirement AND the machine's error model rewards it
   (assessment §2: the summing knife edge, the cams, channel-to-channel
   consistency). The allowlist:
   - **knife-edge system** — knife-mount bore; summing-lever knife seat and its
     20-hole spring pattern (one pattern position frame);
   - **cams** — pinion-cam eccentric-axis position (and any future cam);
   - **channel consistency** — at most one control per channel part
     (rocker arm, channel lever, amplitude bar, connecting rod) where a
     coordinate ± would let the 20 channels scatter.

   Everything else — frames, bases, crank parts, handles, knobs, brackets,
   blocks, pedestals, shafts, bushings, gears, screws — carries **no frames
   and no datums**. Running fits are size tolerances on the diameter plus, at
   most, a roughness symbol on the bearing surface. Perpendicularity of a
   shoulder, flatness of a seat, runout of a collar: not on this machine's
   prints unless the allowlist names the part.
4. **Basic (boxed) dimensions exist only to feed a surviving frame.** Drop the
   box with the frame; the coordinate becomes an ordinary toleranced
   dimension.
5. **Roughness symbols only on surfaces that run, slide, seat a knife or
   ball, or locate the part.** A `shaft_in_bushing` journal or bore, a
   `cam_follower_contact` face, the amplitude-bar slide, the knife edge and
   its seat carry `MACHINED_UM` (1.6). A static mating seat that locates the
   part on its neighbour (a pedestal foot on the base) carries `SEAT_UM`
   (3.2): the title block names no grade, so the one face that MUST be cut
   on a part that may otherwise stay as-cast says so. Gear seats, register
   faces, clamp faces and anything else are "cast/machined" per the title
   block and carry no symbol. `GROUND_UM` (0.8) is reserved for knife edges
   and pivot-screw shoulders.
6. **Notes: few, specific, never a dimension, never a method.** At most four
   short lines of part-specific facts a machinist cannot read off the views:
   drill vs. ream, stock allowance ("16 STOCK OK"), "CENTRES OK", match-drill
   at assembly, a loose-supplied set screw, a gear data block. A note never
   restates the title block, never carries a tolerance that belongs on a
   dimension, never explains what a datum letter is, never narrates design
   intent, and quotes other part numbers only to identify mating parts.
   The print defines the part by its geometry, not by how to make it
   (ASME Y14.5 §1.4(e)): "MACHINE BOTH POCKETS", "CAST", "MILL FROM SOLID"
   are not requirements — the dimensioned feature is. A process word is
   allowed only where it IS the requirement (REAM for a fit bore, a tap
   drill depth that matters, matched fitting to an identified mate with stated
   acceptance, match-drill at assembly). Matched-fit requirements belong on
   the feature callout or assembly step, not in a general note. Where something
   cannot be read off the views, the fix is a view (a section for an
   internal web), not a note. Coating application, masking, and oiling
   belong to the Finish field under rule 1, not this block. Notes that live
   in `<part>_notes.py` stay there (they are out of the part's rebuild
   closure by design).
7. **Views follow the machinist, not the modeller.**
   - Every drawing package includes a standard isometric projection for
     pictorial clarity. It is **Shaded With Edges** with precision geometry
     (draft/faceted quality off) and high-quality cosmetic threads. The
     isometric supplements the manufacturing views; it never replaces an
     orthographic, section, or detail view needed to define a feature.
   - Hidden lines only where they inform (ASME Y14.3: omit them when not
     required for clarity). Every internal feature whose SHAPE the print
     must convey — a stepped bore, a pocket floor, a cross-hole's position
     through a wall, a blind depth no callout states — is defined by SOLID
     lines in at least one view, section, or breakout. A standard hole
     (drill, ream, tap, counterbore, spotface, with its depth) is fully
     defined by its hole callout or hole-table row (ASME Y14.5) and needs
     neither hidden lines nor a section; do not add either for it. A view
     shows hidden lines only when some feature is communicated by them
     there (a cross-hole through a turned part; a blind depth no section
     covers); every other orthographic view is hidden-lines-removed so its
     dimensions and leaders sit on clean geometry. That usually means one
     hidden-line view per part, sometimes none when sections and callouts
     cover everything, occasionally two for orthogonal cross-hole
     families — it is a criterion, not a count. Assembly views
     are hidden-lines-removed. **Section views are always
     hidden-lines-removed**: the cut exists to show the interior in solid
     lines, so dashed edges in a section only say the cut was placed wrong.
     A section either shows the geometry beyond the cutting plane (the
     default) or is cut-surface-only (`IDrSection::SetDisplayOnlySurfaceCut`)
     — never cut-surface-only WITH hidden lines, which prints hatched slices
     floating among dashed ghosts of the material that was removed. A
     dimension that needs an edge behind the cut takes the full section, not
     hidden lines. Never dimension to a hidden line — cut a
     section or breakout instead. (This supersedes the earlier
     "hidden lines ON in every orthographic view" rule: on the castings it
     buried every dimension in dashed haystacks and drove the crowding
     that rule 8 now resolves with extra sheets.)
   - One origin per view, and it is a FEATURE: every location dimension
     starts on something the shop can indicate or pick up -- a finished
     face or edge, the axis of a real bore or boss -- never a construction
     centreline, a symmetry axis or the model origin with nothing there.
     "LOCATIONS FROM FRAME CENTRE" is mid-air with a note on it; a centre
     the machinist must first derive from a symmetric pattern is that
     derivation's own stack-up. Baseline (or ordinate) from that one datum,
     never chained feature to feature. (A Hole Wizard placement sketch
     cannot carry a datum point -- every point in it is a hole -- so a
     hole's model dims stay origin-based; the print dimensions it from the
     datum feature with a driven dimension picked on both features.) The
     overall length is real and conspicuous.
   - Turned parts: oriented as they sit in the lathe, diameters on the side
     view (not leader-piled on the end view), lengths from one faced end.
   - Slots dimensioned to the radius centres; chamfers preferred to radii on
     edges; every shoulder fillet on a turned part has a size.
   - Hole callouts state the decimal Ø and the process (`Ø9.525 REAM THRU`,
     `Ø5.95 DRILL THRU`); clearance holes state the size, not the screw.
     A blind tap states its required **full-thread depth**. State the deeper
     tap-drill depth too when it governs machinability; never let a modeled
     minor-diameter continuation, merged opposing holes, or a default
     through-thread callout imply usable thread where none is required.
8. **Layout is contained, balanced, and uses the better sheet orientation.**
   The inner drawing border is a hard boundary: every view, dimension,
   extension line, leader, callout, note, balloon, and table stays wholly
   inside it, clear of zone labels and the title block, with visible air
   around the content. Touching or spilling through the border is a release
   blocker, not cosmetic polish. No leader crosses another leader, a view it
   does not annotate, or a dimension line; no text sits on a line.
   Dimension text and feature callouts belong outside the depicted part or
   assembly silhouette by default; hole-table tags, balloons, and section
   identifiers are not feature callouts. Place text inside a silhouette only
   when a confined detail or a genuine sheet-space constraint makes that
   placement materially clearer than every exterior option. Convenience or
   fixed coordinates are not justification. Interior text never masks
   geometry, hides a feature, or crosses a line.
   Projected orthographic views preserve ASME alignment; front, top, and side
   views are never staggered merely to improve composition. Correctness comes
   before visual balance. Resolve crowding by moving the aligned view group,
   choosing a better sheet orientation or scale, repositioning nonprojected
   views and annotations — or, once those are exhausted, by **adding a
   sheet**. A drawing package is not limited to one sheet, and extra sheets
   are cheap; cramming is not. The diagnostic symptom of a sheet that is too
   crowded is callouts, dimensions, or notes belonging to one view or section
   overlapping, or being squeezed against, those of another. When that
   happens, move whole sections, detail views, or the hole table with its
   notes to a new sheet of the same package rather than shrinking scale,
   abbreviating qualifiers, or threading text between lines. Each sheet
   should then read cleanly on its own, with its views still at a useful scale.
   Choose landscape or portrait according to the view arrangement, useful
   drawing scale, and space needed by dimensions and notes. A sparse sheet
   with undersized views has the wrong orientation when rotating the layout
   would make the same content materially larger or easier to read. Each
   `DrawingSpec` records the choice explicitly. The layout audit
   (`_drawing_layout_check`) checks the selected template's border and
   title-block keep-out; the eye pass and machinist review judge every visible
   element's containment, balance, and fit.
9. **Assembly drawings are judged as complete assembly packages.** Every PDF
   sheet is rendered at full resolution and attached to one blind-review
   invocation. Acceptance cross-checks BOM rows, balloons, setup and assembly
   steps, and contradictions across all sheets. The review also asks for what
   a fitter needs: assembled views, an exploded view, a parts list with
   balloons, ordered assembly steps, the assembly-level fits and checks, and
   the parked/engaged setup. Legacy three-view sheets
   (`drawing_recipe_assembly.md`) are orientation placeholders and are
   EXPECTED to fail that review until they are built out.
10. **Inspection assumes a hobby shop, not a CMM.** Surface plate, height
   gauge, indicators, V-blocks, sine bar and gauge blocks are fair game, so a
   geometric control is never rejected as uninspectable, only as
   unnecessary. Where a frame is legitimate (rule 3) it is complete: datum
   feature symbols on reachable surfaces and basics for what it locates.

11. **Drawing review is the last DFM backstop, not drawing-only lint.** A
   review finding that the depicted part is physically impossible, implausible
   for every process allowed by the title block, contradictory, or missing a
   necessary physical feature may expose a CAD-model defect even when the
   drawing faithfully shows the model. Check that signal against the source
   CAD and primary visual evidence; never silence it with an invented
   dimension, radius, note, or process callout on the sheet. Fix a
   uniquely-supported omission in the CAD first, then regenerate the drawing.
   When the evidence permits materially different geometries or processes,
   escalate the exact feature, evidence, and viable choices to the user for a
   decision. A reviewer can still be wrong: validate the premise rather than
   blindly implementing the proposed fix.

12. **Walls, margins and stacks are judged at the worst case for a novice
   shop.** The builder is a first-time hobby machinist, so a design earns
   loose tolerances rather than demanding tight ones.
   - **Walls and webs.** Every machined wall or web has a target of
     **≥ 2.0 mm** and a hard floor of **1.5 mm**. That includes the
     thread-major envelope to an edge or another bore, a counterbore or
     countersink to an outside surface, and the ligament over a cross-hole.
   - **Worst case, not nominal.** Judge each wall at the worst case of the
     printed bands: the title block (`.X` ±0.8, `.XX` ±0.51, DRILLED HOLES
     `+0.10 / 0`) or the explicit band on the dimension, plus realistic drill
     wander for deep drilling. Not at nominal, and not by RSS.
   - **Fix with geometry.** A thin wall or razor margin is fixed by changing
     the geometry so the tolerances can be LOOSER, never by tightening a band
     or accepting a DFM minimum.
   - **Aim for the title-block bands.** A tighter band needs a functional
     reason. A unilateral band that one cutter pass produces on its own (a
     slot `+0.10 / 0` cut in one pass with a named end mill) is acceptable
     and counts as loose.
   - **Thread engagement.** A fastener engages **≥ 1.5D** of full thread in
     its receiver at the worst case. Count full threads only: a tap or die
     leaves about 1–1.5 incomplete threads, so give it a thread relief or a
     deeper tap drill rather than letting them eat the engagement. The CAD
     owns installed engagement, and the build's seat-fit and stack asserts
     (e.g. `require_blind_seat_fit`) are where it is enforced. Today those
     asserts check only ≥ 1D; raising them to 1.5D at the worst case is
     part of the rule-12 audit (#846). The assembly review checks it
     only where the package gives the numbers, and otherwise records it as
     not verifiable, without gating.
   - **Adjust at fit-up rather than stack.** Where loose bands cannot hold a
     worst-case stack, prefer a fit-up adjustment stated on the assembly
     steps (slot, shim, feeler-set, cut-to-fit, match-drill) over tightening
     part tolerances.
   - **Named exceptions.** A shortfall is acceptable only by the user's
     ruling, recorded by name in the table below. The thresholds above are
     never loosened to admit it, and a new row needs a new ruling.

## Named exceptions

Accepted shortfalls against rule 12. Each is specific to the parts named; it
is not precedent for anything else. Every sheet a row affects should state
the exception itself; the table is the backstop. The blind reviewer sees only the sheets,
so it reports a row's shortfall as a blocker unless the package itself states
the exception. A blocker that matches a row (same parts, shortfall within the
recorded range) is recorded against that row by the person running the gate
rather than fixed; any other finding on those parts still gates. The reviewer
cannot see this table either, so it files any exception a sheet states under
minor. The person running the gate checks each such minor entry against the
table; a stated exception with no matching row gates like a blocker.

| parts | shortfall | why accepted | ruled |
|---|---|---|---|

No rows are accepted yet.

Pending: cone gears T006–T024 webs (#846 / U38 study).

## The gate

`uv run cad/scripts/machinist_review.py <name>... --reviewer <claude|codex>` (or
`--all`) renders the verdict a blind senior machinist gives each drawing package
under the calibrated prompt in `cad/scripts/prompts/`. **The reviewer MUST be a
different model family from whoever authored or last edited the drawing
script.** An agent running on a Claude model (Fable, Opus, Sonnet) reviews with
`--reviewer codex`; an agent running on a Codex/GPT model reviews with
`--reviewer claude`. A same-family review shares the author's blind spots and
does not count as the gate, even when it returns `SHIP`. If the cross-family
reviewer is over quota, the user's standing last-resort rule applies and its
verdict counts: work authored by Sol or Opus is reviewed by a stronger model
(Astra or Fable), and work authored by Astra or Fable is reviewed by Astra or
Fable at high reasoning. `--reviewer claude` defaults to `claude-fable-5-1` at
medium effort, which is the Opus fallback.
Every review run names the author's family with `--author-family
<claude|gpt|mimo>`, and a same-family pair is refused. The author model is read
from the `Co-Authored-By:` trailer of the last commit that touched the drawing's
`draw_*.py`, and `--author-family`/`--author-model` must agree with it. Every
agent commit that touches a `draw_*.py` carries a model trailer, Codex sessions
included (for example `Co-Authored-By: GPT-6 Sol <noreply@openai.com>`); without
one the ledger can only record the claimed family, and a last-resort review
cannot count. A
cross-family run refused for usage limits keeps its report as
`<name>.<reviewer>.quota-refused.json`, one per reviewer, so a last-resort run
refused in turn is kept beside it and never replaces the evidence a retry
needs. A same-family `--last-resort` run is refused before
any reviewer runs unless that refusal is under 24 h old and the trailer's model
and the reviewer meet the tier rule.
An outage is different evidence from a quota refusal. When the user directs a
same-family fallback because the cross-family reviewer is down, the outage is
recorded in `cad/reviews/outages.json`: its id, the reviewer that is down, the
directed fallback reviewer and model, the user's words and date, the start
time, `ended_at` (null while open) and a redacted excerpt of the failing
output. A review run with `--outage <id>` (or ingested with it) by exactly that
fallback, inside the window, is recorded as `outage_fallback` and carries the
outage record. `check` accepts it only while the outage is open, and prints
the drawings on each outage's fallback. Closing the outage (setting
`ended_at`) turns every one of them into an unreviewed drawing that needs a
cross-family re-review before release.
Every accepted registry-drawing review is recorded in the tracked ledger
`cad/reviews/machinist-ledger.json`, together with the exact PDF it saw
(`cad/reviews/sheets/<sha256>.pdf`). Accepted means `SHIP`, or
`accepted_with_rulings`: a verdict whose every gating finding is answered, via
`--rebuttals <file>`, by a ruling recorded for that drawing in
`cad/reviews/finding-rulings.md`, cited by its id and that file (and line). A
ruling is the user's, or Main's adjudication under the user's standing
delegation; an adjudication counts only when it is recorded there with its
evidence, one row per ruling (`ruled_by` is `user` or `Main`). A ruling on
another drawing, or an id that merely appears in some other file, answers
nothing. A finding with no recorded ruling keeps the drawing failing.
`uv run cad/scripts/machinist_ledger.py check [<name>...]` exits nonzero for any
drawing whose current PDF matches no accepted, counting review. Each recorded
entry is re-proved every time the gate reads it, never taken from its `counts`
flag or an id alone: the author family under the author rulings in force (an
untrailered commit's corrected ruling changes it; a trailer cannot), the family
rule, a last resort's refusal evidence and tier rule, an outage fallback
against the current record of its outage, and each cited ruling still being a
row on that drawing. A malformed entry does not
count, and says why. Sheets match on
identical masked ink, or on an identical text layer (every string, positions
within 0.12 mm) plus ink within 2 px, so re-render noise passes and a changed
character does not. On a mismatch it writes the leftover pixels and the text
difference under `cad/out/reports/machinist-ledger/`. `release` depends on the
same check as `check:machinist`: every registered drawing without a counting
review of the sheet now rendered blocks the release, and the failure lists each
one with the command that clears it. A review that predates
the ledger is entered with `machinist_ledger.py ingest <verdict.json>
--author-family <family>`, which checks the exact PDF it reviewed.
`machinist_ledger.py backfill <root>...` does that for every `SHIP` on record
under the roots. It finds the exact PDF each one reviewed by sha256 wherever it
now lives, and ingests the newest `SHIP` whose sheets match the current render
under the same rule and that counts under the family rule. A record that is not a
machinist_review record (missing or mistyped fields, an unknown reviewer, a
naive time), including a quota report whose refusal cannot be read, is listed
as malformed and ignored, never fatal. So is a malformed backfill cache: it is
dropped and the run starts cold. A newer failing
verdict that reviewed the same sheets, or whose reviewed PDF is lost, blocks
the older `SHIP`, and `--apply` drops a recorded entry it contradicts. Only a
verdict the gate would weigh objects: a blind review of the registry drawing
under its kind's committed rubric with a valid, failing verdict, from a
reviewer whose `SHIP` would count: cross-family to the drawing's author, or
same-family with a qualifying quota refusal and the tier rule, or directed by
an open outage (either family, on a `both_families` drawing). A sighted,
custom-rubric or wrong-kind run does not, nor does a same-family run with no
such evidence. A draw
script whose last commit names no model takes its family from
`cad/reviews/author-rulings.json`. A per-drawing ruling names the family, the
exact commit it judged, who ruled and the evidence; a later commit to the
script is not covered. Otherwise the `untrailered` class rule applies: by the
user's ruling of 2026-09-25, an untrailered commit is Claude's, so a GPT
reviewer handles it, and the entry's provenance says `rule: no trailer`. A
trailer always wins over both. Where a per-drawing ruling and the class rule
disagree, the ruling row carries `both_families` with its reason, and the gate
then requires a counting review of the current sheets from each reviewer
family (claude and gpt), so one of them is cross-family whoever wrote the
script; each is filed in its own `both_families_<family>` slot. A same-family
`SHIP` with no quota refusal is ingested as `outage_fallback` when an open
outage in `cad/reviews/outages.json` directed it, but never as one half of a
`both_families` drawing: there it is filed as that family's half, and the
other family still has to review. The command is a
dry run that prints a per-drawing table unless given `--apply`, and it must run
against a render of the head being released (`--checkout`). A checkout whose
drawing registry, prompt builder, prompt files or committed rubric history
differ from the worktree running the command is refused; run that checkout's
own copy of the tool instead.
A review, and a ledger match, is always judged against the release render.
Renders of the same drawing from different hosts can differ in ink (glyph
rasterization in view labels, for one: the #857 screw sheet had digest
`f15e0a9bf12a` rendered locally and `f7036a4d4edb` on the farm). A digest
that differs because the render host differs is therefore neither a pass nor
a spurious failure: it means the sheet needs review on the release render,
and `check` and `backfill` report it as drift or unreviewed so that it gets
one.
Part and assembly packages render every native PDF page at 300 dpi and submit
all sheet images to one review, using the rubric for that package kind. A
downscaled contact-sheet preview is not a substitute for reviewing every page.
A package passes when
the verdict is `SHIP` with no blocker, no over-specification and no clarity
finding. A `FIX` whose gating findings are each answered by a recorded ruling
(the user's, or Main's adjudication) or a named exception is accepted only through `--rebuttals`, which cites the ruling
or row for every finding and records the verdict as `accepted_with_rulings`;
without it the runner passes `SHIP` only. The durable cure is still stating the
exception on the sheet so the reviewer files it under minor. Minor findings are recorded, not gating. Regression tests must defend
observable manufacturing contracts and plausible failures, not fixed note wording,
line counts, or mocked API-call sequences. Native drawing generation must verify
persisted dimension values, tolerances, reference state, and required view modes;
the exported sheet review checks clarity and unnecessary annotations. Add focused
behavioral tests for uncertain boundaries, without duplicating native readback
checks with mocks.
