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
     coordinate ± would let the 20 channels scatter;
   - **crank mesh** — MHA-DT-005's crank bore: one diametral angularity frame to
     the cone-journal bore (datum A), clocked by the foot seat (datum B) so the
     zone holds tilt as well as yaw, with the plan angle basic. The fixed-centre
     16T:64T crossed mesh loses running clearance to yaw and tilt of the crank
     axis (#906 pose study, `dt-logs/crankhub/crank-mesh-angle-20260926.jsonl`;
     user ruling 2026-09-28 requires only that the mesh never bind).
   - **disc cluster** — the MHA-PD-006 120T disc's rear face parallel to its
     clamp face (datum B); the MHA-PD-017 hub's flange rear face and spigot end
     square to its bore (datum A); the MHA-PD-010 sleeve's step face square to
     its bore (datum A). Unpreloaded on its sleeve, the clamped disc's rim
     wobble must stay inside the disc-to-platen air (R9-68; user ruling
     2026-10-02).
   - **hanger pivot** — the MHA-PD-020 pivot spacer's two faces square to its
     pressed bore (datum A). The preloaded MHA-VN-049 spring seats the hanger on
     those faces, so their squareness is the hanger's only tilt; it must hold
     the disc rim inside the disc-to-platen air (R9-71).
   - **paper-drive stock-form gears** — MHA-PD-006, MHA-PD-008 and
     MHA-PD-010: tooth-space radial runout to the actual running bore or
     journal axis, measured with a calibrated pin in each space, not by
     blank-OD runout or free-span variation. The disc's assembled running
     datum is the feed pinion bore, not its floating hub pilot. The integral
     knob shaft's core and front relief may carry runout to its running
     journal where the finite stock-cutter clearance requires it. These are
     the user's gear-tooth and bore-to-shaft critical classes, not a general
     permission to add frames to shafts.
     The tooth-pattern indicator requirement is a feature-local,
     model-property-linked callout, for example `TOOTH SPACE RUNOUT 0.05
     TIR TO A`, using the configured critical grade.
     Attach it to a real finite tooth flank, name the actual running datum,
     and keep the pin size and all-spaces line in the same callout. It is
     not a circular-runout frame on the blank OD and not a multi-line
     inspection procedure in Manufacturing Notes. On the disc sheet,
     distinguish the assembled feed-bore datum from the disc's own pilot.
   - **paper reducer location** — the transgear arm and arm plate's locating
     pattern and running-axis locations may carry the critical position
     controls required by the whole-stack stock-form gate, including the
     rigid two-hole registration's yaw. Use stock dowels in reamed holes;
     the mounting screws clamp but do not locate. A matched pair is reamed
     at the drawn, inspected gear-axis setting, not accepted as-made.
     Running-bore squareness and the arm's opposite seating faces may carry
     the configured controls needed at the actual projected gear and chain
     planes. Name those planes and reachable datum features; neither screw
     clearance nor assumed countersink centring is a location control.
   - **purchased paper rack acceptance** — the MHA-PD-005 rack sheet carries
     only its two incoming stock sizes (stock height and face width MAX)
     and the purchased-rack line. Its pitch accuracy is the catalogue
     part's; the assembly checks the running mesh over the whole engaged
     window (no tight spot, shake at every tooth). Keep numerical limits in
     the shared functional source, not a generic multi-line Manufacturing
     Notes block.

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
   in `<part>_notes.py` stay there. Drawing-only note helpers do not enter a
   part's rebuild closure unless its builder imports them. When a builder
   stamps notes into a saved model property, that helper is a part recipe
   input: a note edit must rebuild or restore the part under the changed key
   before a property-linked drawing can print it.
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
   title-block keep-out; the machinist review judges every visible
   element's containment, balance, and fit (an eye pass stands in only where
   no machinist review covers the sheet's version).
9. **Assembly drawings are judged as complete assembly packages.** Every PDF
   sheet is rendered at full resolution and attached to one blind-review
   invocation. Acceptance cross-checks BOM rows, balloons, setup and assembly
   steps, and contradictions across all sheets. The review also asks for what
   a fitter needs: assembled views, an exploded view, a parts list with
   balloons, ordered assembly steps, the assembly-level fits and checks, and
   the parked/engaged setup. Legacy three-view sheets
   (`drawing_recipe_assembly.md`) are orientation placeholders and are
   EXPECTED to fail that review until they are built out.

   **Operational retention is an assembly requirement, distinct from thread
   engagement.** Every threaded support or fastener exposed to a rotating
   member's drag, torque reversal or loss of preload has a mechanical
   anti-loosening means (a jam nut, a nut locked by a pin or tab, a
   cross-pin, a key or flat with axial capture, a pinch clamp across a slit
   thread, a staked or peened end), shown in an assembly view or detail and
   installed by a named assembly step. A plain seated thread, shoulder, shim
   or threadlocker alone does not qualify, and a cap that retains a cluster
   axially is not proof that the stud under it is locked to its frame. A
   static clamp that no operating torque reaches needs no lock, and its row
   in the joint table says why. Missing or unverifiable retention gates the
   assembly review; the rule-12 allowance for engagement the package cannot
   show does not waive it. `cad/scripts/joint_retention.py` lists every
   threaded joint and audits this rule (`check:joint_retention`). A
   departure needs an explicit joint-specific user ruling, never an inferred
   exception.
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
   not verifiable, without gating. Engagement is not retention: rule 9
   still requires a mechanical lock on every exposed joint.
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
the shortfall itself; the table is the backstop. A sheet states it as a plain
manufacturing fact, the shortfall and its value (for example "ENGAGEMENT
5.72 MIN (0.90D)"), and never cites a rule number, a ruling id, or the
words EXCEPTION, ACCEPTED, RULING, POLICY or BOOK FIDELITY
(test_printed_text_rulings enforces this); this table is where the governance
lives. The blind reviewer sees only the sheets, so it may still report a row's
stated shortfall. A finding that matches a row (same parts, shortfall within
the recorded range) is recorded against that row by the person running the
gate rather than fixed; any other finding on those parts still gates, and a
stated shortfall with no matching row gates like a blocker. In code, the emitter
that prints a row's shortfall carries the comment `# Named exception:
MHA-<subsystem>-nnn <shortfall>`, naming its row; test_printed_text_rulings requires a
tagged emitter for every row, printing the shortfall it names.

| parts | shortfall | why accepted | ruled |
|---|---|---|---|
| MHA-VN-031 post-to-platform screws, 2X (MSC 40923906, 1/4-20 × 4 in slotted fillister, modelled at `vn_post_mount_screw_spec.CUT_LENGTH_MM` -- the nominal post and plate's flush length less half the cut-to-fit acceptance -- and cut to fit at assembly: short of the MHA-DT-020 underside, never proud) into the MHA-DT-020 1/4 plate | 1/4-20 thread engagement 0.90D minimum at the worst case (5.72 of 6.35, edge breaks counted), under the 1.5D rule | the fillister is cut to fit and never stands proud of the plate, which swings over the base; the receiver remains the 1/4 plate and its engagement is unchanged by the taller post or longer supplied screw | User, U37c/U41, 2026-09-24; stock length updated for the 90 mm post, 2026-10-08 |
| MHA-DT-003 cone gear T006 | Root-to-bore web 0.64 at the worst case (DT6-FORM1 option (a) printed floor MIN Ø2.136 over the 1/32 in bore at its largest), under the 1.5 floor; floor 0.62 | the book's 6-tooth floor leaves no usable bore that meets 1.5 under it; the 1/32 in bore is the shaft's smallest land and an integral pinion is blocked by tip-first assembly. T012 meets the 2.0 target (2.01 worst case) | User, U40, 2026-09-23; DT6-FORM1 option (a), 2026-10-10 |
| MHA-DT-003 cone gear T006, in mesh with MHA-DT-012 | Contact ratio with the 120T drum 0.77 at the nominal set centre (REF), under the 1.0 rule; gated instead on its DT6-FORM1 relief standing >= 0.010 clear of every printed drum-tip path over its RSS centre range, and >= 0.02 backlash at the closing corner (`test_standard_mesh_checks`) | no full-depth six-tooth form reaches a contact ratio of 1 against the shared 20 deg 120T drum, and the book's tooth counts are kept. T012-T120 meet the 1.0 rule at the nominal set centre; their RSS-corner ratios are reference only | User, 2026-10-10 (T006 option (a), named exception) |
| MHA-DT-009 crank taper pin, Ø2.1 keeper-ring cross-hole 3.7 from the big end (the sheet states the web as a MIN) | Cross-hole web to the pin surface 1.56 at the worst case of the printed bands (1.88 nominal), under the 2.0 target; floor 1.5 | The round Ø10 keeper ring's wire arc needs the Ø2.1 hole through the Ø5.9 pin. No round-ring geometry reaches 2.0 in this pin (a bigger ring or a thinner wire gets about 1.68), and a thicker pin would re-bore the taper-reamed hub and shaft | User, 2026-09-30 (#1140) |
| MHA-VN-017 cone tip adjuster (McMaster 94025A164, #10-32 × 3/8 cup-tip set screw) in the tapped-through #10-32 of the MHA-DT-021 cone tip block (the MHA-DT-000 step that sets it states it) | #10-32 thread engagement 1.0D minimum at the worst case: 4.87 of full thread under the north countersink with the tip's print-worst axial stack and the set end play counted, printed as the 4.82 floor the block's working window guarantees (asserted at import), under the 1.5D rule | the screw carries only the shaft's end-play thrust (no clamp load; the pinch screw across the slit locks it), and a block deep enough for 1.5D would push the MHA-VN-016 stack collar into the block's south face at the worst case | User, option (a), 2026-09-29 |
| MHA-DT-035 crank handle butt cup, pocket bored to suit the MHA-DT-032 head | pocket wall 0.8 at the worst case (the Ø8.20 ±0.10 body over the Ø6.5 maximum pocket, stated on the sheet as MIN POCKET WALL 0.8), under the 1.5 floor; the floor keeps 1.5 | the wall carries no load: the head bears on the floor and the oak round the bonded body backs it; a 1.5 wall pushes the butt to Ø13.4 against the photographed ~Ø10 (ch30 eight-views-4) | User, 2026-09-30 (approved CadQuery concept v4) |
| MHA-DT-008 crank handle end round, turned on the oak clear of the bonded MHA-DT-035 cup | the flat oak end round the counterbore mouth is 0.45 wide at nominal; at the worst case the oak feathers to nothing (largest counterbore, contour turned its allowance small, 0.10 bore eccentricity); 1.0 in from the oak end it holds 1.98 round the Ø8.5 maximum counterbore (asserted at import) | the original's rounded butt closes on the steel cup (ch11 p.14, ch30 eight-views-4); the end is turned after the cup is bonded, so the steel backs the edge | User, 2026-09-30 (approved CadQuery concept v4) |
| MHA-PD-009 removable #25 sprocket (T12 / T18 / T24 configurations), Ø2.5 drive-pin holes on the Ø14 circle round the Ø10.3 bore (the sheet states the web as a MIN) | Bore-to-pin-hole web 0.60 nominal, 0.47 at the worst case of the printed bands (both holes drilled +0.10/0, each pin centre ±0.025), under the 1.5 floor | photo-faithful to the ch23 p.56 catalog view, where the two holes nearly touch the bore; the web carries no load (the pins drive through the hole walls, and the thumbnut, seated on the collar's pilot, only retains the plate on its pins, R9-70) | User, 2026-09-30 |
| MHA-PD-022 transgear drive collar, Ø17.5 brass collar supplied long and rear-faced to fit against the integral pinion's front face, carrying the two pressed MHA-VN-038 dowels (the sheet states it) | Drive-pin hole to collar rim 0.56 nominal, 0.48 at the worst case of the crank's seat bands, under the 1.5 floor | the collar must stay inside the #25 plates wrapping the T12 on the crank, and both shafts share one Ø17.5 seat interface on the Ø14 pin circle of the photographed sprocket (TG-16); the dowels are pressed into holes reamed through the collar and bear on the wheel, not the rim | User, 2026-09-30 (TG-16 twin; moved from the historical MHA-078 interim collar, round 10) |
| MHA-DT-011 crankshaft, Ø17.5 × 5.8 seat spigot on the integral collar carrying the two pressed MHA-VN-044 dowels (the sheet states it) | Drive-pin hole to spigot rim 0.56 nominal, 0.48 at the worst case of the printed bands, under the 1.5 floor | the spigot is the knob collar's seat face, kept inside the #25 plates wrapping the T12 (0.18 radial air to a real ANSI plate); the dowels are pressed in blind holes and bear on the wheel, not the rim | User, 2026-09-30 |
| MHA-CH-006-TL-03 rocker arm rod diamond pin, Ø3.0 +0/−0.2 neck and Ø4.5 collar over the Ø2.000 +0.010/0 reamed bore holding the bonded gauge pin (the sheet states both walls as a MIN) | Neck wall to bore 0.50 nominal, 0.39 at the worst case of the printed bands and the Ø4.5 .X collar wall 0.84 at its worst case, both under the 1.5 floor | the bore and neck sizes are the shop-additions §3 route; the neck stays Ø3.0 for the S4 op 25/27 cutter clearance, and the bonded pin fills the bore, so the section is solid in service. Conditions (stated on the sheet): the pin is an orientation locator and light tangential stop under hand load only, with no clamping or cutting load on the neck; the Ø2.0 bore is reamed first and the neck OD finish-turned in the same chucking; the pin is bonded set to its projection, filling the bore through the neck (its shortest inserted length runs past the deepest neck, asserted at import) | Ruled by Main (coordinator), 2026-10-07, following Pedro's §3 route (bonded Class X gauge pin); Pedro may overturn. |
| MHA-PD-010 feed pinion, D-flat wall: the retained 3.500 flat plane on the Ø8.2 h6 boss over the Ø3.900 +0.016/+0.004 G7 running bore on the MHA-PD-023 h6 pin (the sheet states WALL 1.52 MIN) | Wall from the flat to the nominal bore 1.550; 1.527 at the worst printed bands (flat 3.485, bore Ø3.916), floored to 1.52 MIN; under the 2.0 target, with the existing 1.5 floor retained | the integral matching D-bore of MHA-PD-017 carries the light disc drive, not a set screw. The retained 3.500 flat plane leaves 0.600 nominal depth on the smaller boss and a 4.271 nominal chord (4.253 minimum); the boss diameter provides stock-cutter run-out clearance while the pin's Ø3.9 running bore and flat plane preserve the existing wall. The hub's round bore locates and its matching flat drives; no cup-point seating requirement applies | User, 2026-10-02 (R9-68); retained flat-plane/light D-bore rationale approved by Main for the stock-cutter cutover |
| MHA-PD-020 transgear pivot spacer, brass ring Ø8.600 ±0.13 over the Ø4.900 ±0.13 bore on the MHA-VN-041 shoulder (the sheet states the wall as a MIN) | Bore-to-O.D. wall 1.85 nominal, 1.72 at the worst case of the printed bands (O.D. −0.13, bore +0.13), under the 2.0 target; floor 1.5 | the O.D. is held down by the swept clearance to the arm's lock stations (0.14 worst at Ø8.6 with the ring floating on the shoulder, R9-61), and the bore runs on the Ø4.7625 shoulder of the stock pivot screw; the ring only spaces the arm off the bar's back face | User, ruling 8, 2026-09-30 |
| MHA-VN-041 transgear pivot screw (McMaster 91829A205, 3/16 × 1/2 slotted shoulder screw, #8-32 thread) through MHA-PD-020 and MHA-PD-018 into the #8-32 blind tap of the MHA-PD-007 support bar (its sheet's installation line states it) | #8-32 thread engagement 0.72D nominal (2.997 of full thread: the 4.7625 thread less the vendor's 1.765 neck and ramp), 0.52D minimum at the worst case (2.203 = 0.529D after the 1 P first thread, printed floored), under the 1.5D rule | the joint carries only the shoulder's seating preload, and the arm runs on the shoulder, not the thread; every Ø3/16 McMaster shoulder option has the same thread, and a bigger shoulder changes the photographed head. The installation line sets it with low-strength threadlocker | User, ruling 11, 2026-09-30; re-stated by R9-7 (coordinator, 2026-09-30) after the vendor model showed the thread-relief neck ruling 11's 0.94D left out |
| MHA-CH-006-TL-01 rocker vise blank-end stop (shop fixture): one ISO 4762 M6 × 16 socket head cap screw (bought length 15.65–16.35, js15) through the lug into the M6 × depth 6 tap of a bought Kanetec MB-PM magnetic base (the screw hole's callout states it) | M6 thread engagement 2.72 of full thread minimum at the worst case (printed 2.7 MIN, 0.45D): the 15.65 short screw at the longest 10.800 ±0.13 grip (printed at three places), less the screw end's 2 P incomplete thread (ISO 4753), under the 1.5D rule. Engagement plus tip clearance is fixed at the tap depth less 2 P (4.0), so the 16.35 long screw at the shortest grip leaves the tip 0.32 clear of the tap bottom (the callout states TIP 0.3 MIN CLEAR OF TAP BOTTOM) | the stop takes only the hand-seating push of the blank before the jaws close, never a cutting or clamping load (its sheet says so); the M6 × 6 tap is the vendor's (Kanetec catalogue 057_068, MB-PM: 40 × 40 × 40, 600 N), and no screw engages more of it without risking the tap bottom | Main, option A, 2026-10-07 (#1248) |
| MHA-CH-006-TL-04 rocker arm hub filing buttons, 2X (the sheet states RIM WALL 1.78 MIN) | rim wall 1.78 MIN (rule-12 target 2.0, floor 1.5) | both diameters are fixed by the parent (hub filed Ø and the pivot-stud fit); hand-filing clamp load only; Pedro may overturn | Ruled by Main (coordinator), 2026-10-07 |
| MHA-CH-006-TL-07 rocker arm pivot washer (the sheet states WALL 1.64 MIN) | pivot washer wall 1.64 MIN (rule-12 target 2.0, floor 1.5) | OD set by as-supplied Ø10 drill rod; bore must clear the max shoulder; unhardened; screw clamp load only; Pedro may overturn | Ruled by Main (coordinator), 2026-10-08 |
| MHA-MG-001 magnifying bracket counterbore floor and MHA-SM-003 summing lever bracket tap-drill wall, with MHA-VN-050 screws (McMaster 91794A077, #2-56 × 1/4 fillister) | Counterbore bearing floor 1.525 MIN and tap-drill lateral wall 1.501 MIN at the worst case of the printed joint-specific bands, below the 2.0 target but above the unchanged 1.5 floor; each affected sheet states its MIN. | The user's option-B joint keeps the full-thread major envelope inside the 5.08 rib and permits only the smaller drill/point to continue along the lever plate's mid-plane. The shallow counterbore retains at least 1.5D of full engagement without bottoming; its head deliberately protrudes 0.5582 nominal. Specific ±0.05 positions/depths and ±0.10 drill depth are authorized, not a relaxation of any threshold. | User, option B and clarified binding constraints, 2026-10-08 |

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
Part and assembly packages render every native PDF page at 300 dpi and submit
all sheet images to one review, using the rubric for that package kind. A
downscaled contact-sheet preview is not a substitute for reviewing every page.
A package passes when
the verdict is `SHIP` with no blocker, no over-specification and no clarity
finding. The runner passes `SHIP` only, so a `FIX` whose only gating findings
are blockers matching a named exception still exits nonzero; it is accepted by
hand, citing the row in the PR, and the durable cure is stating the exception
on the sheet so the reviewer files it under minor. Minor findings are recorded, not gating. Regression tests must defend
observable manufacturing contracts and plausible failures, not fixed note wording,
line counts, or mocked API-call sequences. Native drawing generation must verify
persisted dimension values, tolerances, reference state, and required view modes.
A finish attachment must identify the controlled model face and keep its
physical leader landing, not merely a non-dangling transient silhouette. A
sheet-derived linear reference must read back a linear native dimension type
before its system value is read as a length.
The exported sheet review checks clarity and unnecessary annotations. Add focused
behavioral tests for uncertain boundaries, without duplicating native readback
checks with mocks.
