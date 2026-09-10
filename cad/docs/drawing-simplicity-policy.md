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
2. **Decimal places carry the tolerance.** A dimension with no explicit band
   is governed by its decimal places. A tighter band goes ON that dimension
   as a native model tolerance (`_drawing_marks.set_dimension_*_tolerance`),
   never in a note and never as a frame. Three decimals mean "hold it"; two
   mean "routine". Do not print three decimals on a routine feature.
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
   intent, and never quotes other part numbers beyond "MATES WITH".
   The print defines the part by its geometry, not by how to make it
   (ASME Y14.5 §1.4(e)): "MACHINE BOTH POCKETS", "CAST", "MILL FROM SOLID"
   are not requirements — the dimensioned feature is. A process word is
   allowed only where it IS the requirement (REAM for a fit bore, a tap
   drill depth that matters, match-drill at assembly). Where something
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
   - Hidden lines ON in every orthographic view (both books); never dimension
     to a hidden line — cut a section or breakout instead.
   - One origin per view; the overall length is real and conspicuous.
   - Turned parts: oriented as they sit in the lathe, diameters on the side
     view (not leader-piled on the end view), lengths from one faced end.
   - Slots dimensioned to the radius centres; chamfers preferred to radii on
     edges; every shoulder fillet on a turned part has a size.
   - Hole callouts state the decimal Ø and the process (`Ø9.525 REAM THRU`,
     `Ø5.95 DRILL THRU`); clearance holes state the size, not the screw;
     taps are `1/4-20 ↧ 12` unless the tap-drill depth matters.
8. **Layout is contained, balanced, and uses the better sheet orientation.**
   The inner drawing border is a hard boundary: every view, dimension,
   extension line, leader, callout, note, balloon, and table stays wholly
   inside it, clear of zone labels and the title block, with visible air
   around the content. Touching or spilling through the border is a release
   blocker, not cosmetic polish. No leader crosses another leader, a view it
   does not annotate, or a dimension line; no text sits on a line.
   Projected orthographic views preserve ASME alignment; front, top, and side
   views are never staggered merely to improve composition. Correctness comes
   before visual balance. Resolve crowding by moving the aligned view group,
   choosing a better sheet orientation or scale, or repositioning nonprojected
   views and annotations.
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
   the parked/engaged setup. The current three-view sheets
   (`drawing_recipe_assembly.md`) are orientation placeholders and are
   EXPECTED to fail that review until they are built out; single-sheet part
   prints are the gate this policy enforces today.
10. **Inspection assumes a hobby shop, not a CMM.** Surface plate, height
   gauge, indicators, V-blocks, sine bar and gauge blocks are fair game, so a
   geometric control is never rejected as uninspectable, only as
   unnecessary. Where a frame is legitimate (rule 3) it is complete: datum
   feature symbols on reachable surfaces and basics for what it locates.

## The gate

`uv run cad/scripts/machinist_review.py <name>...` (or `--all`) renders the
verdict a blind senior machinist gives each drawing package under the calibrated
prompt in `cad/scripts/prompts/`. Parts use their single PNG; assemblies render
every PDF page and submit all sheet images to one review. A package passes when
the verdict is `SHIP` with no blocker, no over-specification and no clarity
finding. Minor findings are recorded, not gating. Each part's
`test_<part>_drawing.py` pins the simplified state (no frames unless allowlisted,
note line count, hidden lines on) so the fleet cannot regrow the complexity
between reviews.
