# Drawing guidelines

The standard every part and assembly drawing package in this project is
drawn to and reviewed against. Authors follow it. Each blind machinist review
receives this file verbatim, followed by its own reviewer instructions.

Cite a rule by number and title, for example "rule 5 (avoid excessive GD&T)".

## Who reads these drawings

One builder, a first-time hobby machinist, making one of each part. The parts
are cut on a manual mill and lathe with DROs and assembled at a bench with
hand tools. Inspection and setting use what a well-equipped hobby shop owns:
rule, calipers, micrometers, pin, feeler and thread gauges, a square, a granite
surface plate with a height gauge and dial or test indicators, V-blocks, a sine
bar and gauge blocks, a between-centres or bench-centre setup, and a torque
screwdriver. There is no CMM, no optical comparator, no production line and no
jig the package does not tell the builder to make.

The machine is a hobby-scale scientific instrument, not aerospace hardware.
Parts that work with loose tolerances are the mark of a good design.

Fabrication prints are drawn in millimetres on ASME sheets in third-angle
projection. Fasteners, taps and drills are US customary (3/8, #14, 1/4-20).
Purchased VN reference dimensions reproduce the supplier engineering drawing's
units and displayed precision, with explicit units and reference parentheses;
they are not fabrication or incoming-inspection controls. Finished/custom
modifications retain their own controlling dimensions. That mix is intended;
a callout is defective only when its unit is genuinely ambiguous.

## Rule 1 — No questions, nothing extra

A good package passes two tests:

- **It has no questions.** Every feature can be laid out, cut, assembled and
  checked from what is drawn. Nothing needs a phone call, a verbal
  instruction or a napkin sketch.
- **It carries nothing the job does not need.** Extra tolerancing is a cost,
  not a courtesy. A tight band on a mundane feature, a frame where a plus/minus
  would do, a roughness symbol on a face that neither runs nor locates, a
  detail view of a plain chamfer: each costs setup and inspection time and
  tells the shop nothing. A busy print is not a well-engineered print.

A redundant correct dimension never hurt anyone; a missing one does. Where the
two tests seem to pull apart, answer the question.

## Specification

### Rule 2 — The title block is the general specification

Units, the one-, two- and three-place linear tolerances, the angular
tolerance, the DRILLED HOLES `+0.10 / 0` band, the edge break, the thread
class, the surface row, material and finish live in the title block and
nowhere else. A note or callout never restates them, and a reviewer never asks
for what the title block already says.

- The surface row is a process statement (`CAST/MACHINED`), not a roughness
  grade: a face with no roughness symbol may be left as cast or as machined,
  the builder's choice. As-cast skin can never meet a number, and "as
  machined" on a manual machine already lands where a general grade would.
- Where the material is not critical, the material field names the acceptable
  families as explicit alternatives (`LOW-CARBON STEEL OR GRAY IRON`). Do not
  force an unsupported grade or write "material not critical". A specific
  grade is required only where the part's function needs it.
- For a coated ferrous part, the Finish field also carries any masking and the
  corrosion protection of bare machined surfaces. Those are finish
  requirements, not manufacturing notes.
- The title block's standard rows (general tolerances, DRILLED HOLES, edge
  break, surface, thread class, "interpret per ASME Y14.5", the projection
  symbol) are the sheet format shared by every print, assembly sheets
  included. On an assembly they govern work done at assembly, such as
  match-drilling; they do not call for reinspecting supplied parts.

### Rule 3 — Decimal places carry the tolerance

A dimension with no explicit band is toleranced by its decimal places through
the title block. A drilled hole with no band is toleranced by the DRILLED
HOLES row.

- Three places mean "hold it", two mean "routine", one means "near enough".
  Three places on a drilled hole is a defect, and so are two places on a reamed
  bearing bore with no band. Two places is the ordinary spelling of a drilled
  hole (`Øn.nn DRILL THRU`), a tap or tap-drill depth and a routine location;
  it is never over-specification by itself.
- Noncritical overall sizes generally need one place (`.X`). Chamfers, edge
  breaks and clearance holes never need extra places.
- A dimension that carries its own band (`Øn.nn +0.03/0`, or stacked limits
  such as `n.nn` over `0.0/-0.5`) is toleranced by that band. Its decimal
  places are only the number's spelling: never ask it to grow or drop a place,
  and never round it, which moves its limits.
- A three-place size with no band and no stated function is
  over-specification under this rule. It becomes a rule 4 matter only when the
  sheet or package gives it a function.
- A tighter band goes on the dimension itself, never in a note and never as a
  geometric frame.

### Rule 4 — Tighten only for function, and name the mate

Tolerances exist to make parts work at the least cost. Tight is right only
where a feature runs, slides, seals, locates or is pressed: a bearing journal
and its bore, a press or sweat fit, a slide, a knife edge and its seat, a gear
centre distance. A pass-through hole, a clearance bore, an outside profile or
a chamfer gets the loosest title-block band that serves it.

- **Every tight band names its mate.** A tight band is an explicit band
  narrower than the title-block band for its decimal places, a three-place
  size given a function, or any REAM callout (REAM marks a fit bore even when
  its band matches DRILLED HOLES). The reason for it is the mating part, so
  the callout, or a flagged note attached to it (rule 7), names the mate
  ("SLIDING FIT ON SHAFT, ITEM 4", or the mate's name and drawing or part
  number) and the fit it needs: running, sliding, press or locating. A gear
  centre distance names the mesh; a width that sets a stack names the stack.
  Where the mate alone does not show why the band is tight, add a few words
  of reason (`SETS MESH BACKLASH`, `KNIFE-EDGE SEAT`); see rule 7.
  The shop can then make the hole to the shaft instead of chasing a number.
  A tight band whose mate appears nowhere in the package is a blocker: either
  name the mate or loosen the band. A mate named somewhere in the package (a
  general note, a gear data block, another sheet) but not at the callout it
  serves is a clarity defect, not a blocker.
- **Matched or selectively fitted pairs.** For a one-off pair, the callout
  identifies the mate by name and assigned drawing or part number, and states
  the required clearance, interference or an unambiguous functional
  acceptance. Give diametral or radial clearance where applicable. "MATCH FIT"
  alone is incomplete. When the nominal is reference-only, the finished mate
  and the stated acceptance define the fit, and a reference nominal does not
  mean purchased stock. Where both parts carry controlled limits, those limits
  still apply and must produce the required fit; matching does not waive them.
  Interchangeable parts need their essential limits.
- **Stock that is good enough stays stock.** Where bar stock already meets the
  need, say so (`n STOCK OK`, `.nn (STOCK)`) or give a minimum cleanup size
  rather than a turned band.
- **Read a band as its total width.** `+0.005 / 0` is 5 µm wide, the same as
  ±0.0025. Keep the original nominal and the asymmetric limits when checking a
  fit; equal widths are not equal fits.
- **Necessity before capability.** Being printed does not make precision
  necessary. Unneeded precision is over-specification even when it is hard to
  achieve. Precision is a capability problem only when the function genuinely
  needs it AND a specific conflict with the allowed machining or verification
  route can be shown. DRO or micrometer resolution is not accuracy. Without
  stated equipment accuracy, condition or temperature control, describe burden
  and uncertainty; do not invent capability figures, stock or catalogue
  limits, or declare a size impossible. Do not assume grinding, lapping,
  temperature-controlled metrology or an ideal reamed hole. Precision may
  legitimately come from catalogue stock, such as a precision-ground shaft.
- **Never loosen a functional fit just to ease manufacture,** and never
  tighten a band to rescue a thin wall, a short thread or a stack (rules
  17–19). A proposed replacement band faces the same scrutiny: wider is not
  automatically better. If the right limits depend on a mate the sheet does not
  show, say so rather than inventing numbers.

### Rule 5 — Avoid excessive GD&T

Geometric tolerancing is a loaded gun in a crowded room. A feature-control
frame, and the datums it needs, appears only where a plus/minus on a dimension
cannot express the requirement AND the function demands it. On this machine
that is a short list of functional classes: the knife-edge system, the cams,
a pattern or feature that must match its mate or stay consistent across the
repeated channel parts, and a few gear-mesh and disc alignments whose running
clearance depends on it.

- A position frame on a hole pattern that must match a mating pattern, or on
  a feature repeated identically across the channel parts, is in that short
  list; it is not over-specification. Everything else carries no frames and
  no datums. Perpendicularity on a shoulder, flatness on a clamp face or
  runout on a collar of a hand-cranked mechanism is over-specification.
  Running fits are a size band on the diameter plus, at most, a roughness
  symbol (rule 6).
- Where a frame is justified it is complete: datum feature symbols on real,
  reachable surfaces and basic dimensions for whatever it locates. A frame with
  a missing datum, a datum no one could set up on, or a located feature with no
  basic is a defect.
- A boxed basic dimension exists only to feed a surviving frame. Drop the box
  with the frame; the coordinate becomes an ordinary toleranced dimension.
- The hobby shop can inspect flatness, squareness, parallelism, runout and
  position (surface plate, height gauge, indicators, V-blocks, sine bar), so a
  frame is never rejected as uninspectable, only as unnecessary.
- Assembly sheets almost never need GD&T; use it only where a plus/minus on an
  assembly dimension cannot say what is needed.

### Rule 6 — Roughness symbols only where a surface runs, slides or locates

Because the surface row lets any face stay as cast (rule 2), a roughness symbol
is the only way a print requires a face to be cut at all. Use it sparingly and
deliberately:

| surface | grade |
|---|---|
| journal or bore that runs, cam-follower contact, slide, knife edge and its seat | Ra 1.6 µm |
| knife edge or pivot-screw shoulder that must be ground | Ra 0.8 µm |
| one static mating seat that locates the part on its neighbour (a foot on a base, a bolted register) | Ra 3.2 µm |

Gear seats, pinned or pressed bores, clamp faces, register faces that do not
locate, and every other face carry no symbol. A banded or reamed bore is not a
running bore by itself: a gear's D-bore or seat bore does not run. A symbol on
a face that neither runs nor locates is over-specification. Judge function
from the whole package: a thrust washer face, a thrust shoulder, or a face a
note says slides or bears does run.

### Rule 7 — Notes: few, flagged, never a method

At most four short lines of part-specific facts the views cannot carry: drill
versus ream, stock allowance (`n STOCK OK`, `SUPPLY n.nn MIN THICK`),
`CENTRES OK`, match-drill at assembly, a matched-fit statement with its mate
and acceptance, a loose-supplied set screw, a stated shortfall (rule 20), a
gear data block. A gear data block may carry REF values (module, transverse
DP, contact ratio), addendum modification and a backlash acceptance; those
are gear data, not narration.

- A note never restates the title block, never carries a dimension or a
  tolerance that belongs on a feature, and never explains what a datum letter
  is. Other part numbers appear only to identify a mate, and identifying a
  mate is always allowed.
- **Say why when it is not obvious.** A short functional reason is welcome
  where a tight band, a roughness symbol or a hardness would otherwise look
  arbitrary: `BEARING SURFACE`, `KNIFE-EDGE SEAT`, `SETS MESH BACKLASH`.
  Put it on the callout it explains; naming the mate (rule 4) is the commonest
  form. A reason says what the feature does, never how to make it, and it is
  never a defect in itself. What a note must not do is prescribe the process.
- The title block's Finish field (`AS DRAWN`, `DRAWN WIRE`, `BORE AS REAMED`)
  is a finish statement under rule 2, not a note line and not a method.
- **Flag it where it applies.** A requirement that matters (a matched fit, a
  match-drill, a "do not cut" face) goes on the feature callout or the assembly
  step with a leader to the feature, not buried in a general note block.
- **Geometry, not method** (ASME Y14.5 §1.4(e)). `MACHINE BOTH POCKETS`,
  `CAST`, `MILL FROM SOLID` are not requirements; the dimensioned feature is. A
  process word appears only where it is the requirement: REAM for a fit bore, a
  tap-drill depth that matters, matched fitting to an identified mate,
  match-drill at assembly.
- **A missing view is not cured by a note.** Where something cannot be read off
  the views, add a view (a section for an internal web). A mirrored part is
  drawn in its own hand, never left to "LH OPPOSITE".

## Views

### Rule 8 — Include a shaded isometric

Every package, part or assembly, includes a standard isometric projection
rendered **Shaded With Edges** in precision quality: edges visible, geometry
not faceted, cosmetic threads not draft quality. An assembly shows the
finished assembly in its working pose. The isometric supplements the
manufacturing views; it never replaces an orthographic, section or detail view
needed to define a feature. A missing isometric, a plain shaded or wireframe
pictorial, or a visibly draft-quality one is a clarity defect.

### Rule 9 — Show internal shape in solid lines

Hidden lines appear only where they inform (ASME Y14.3).

- Every internal feature whose SHAPE the print must convey (a stepped bore, a
  pocket floor, a cross-hole's position through a wall, a blind depth no
  callout states) is drawn in solid lines in at least one view, section or
  breakout.
- A standard hole (drill, ream, tap, counterbore, spotface, with its depth) is
  fully defined by its callout or hole-table row. It needs neither hidden
  lines nor a section.
- A view carries hidden lines only when a feature in it is communicated by
  them, such as a cross-hole through a turned part. Every other orthographic
  view, and every assembly view, is hidden-lines-removed so its dimensions sit
  on clean geometry. This is a criterion, not a count.
- A section never carries hidden lines. It shows either the material beyond
  the cut in solid lines or only the cut faces. Hatched slices among dashed
  ghosts of removed material mean the cut is in the wrong place.
- Never dimension to a hidden line. Cut a section or breakout instead.

### Rule 10 — Dimension from a real feature

- Every location dimension starts on something the shop can touch, indicate
  or pick up: a finished face or edge, the axis of a real bore or boss, or a
  datum feature on a reachable surface. A construction centreline, a symmetry
  axis or a CAD origin with no feature there is mid-air and cannot be
  measured; a note such as `LOCATIONS FROM FRAME CENTRE` names the defect, it
  does not cure it. A centre the machinist must first derive from a
  symmetric pattern carries that derivation's own stack-up.
- One datum per view, then baseline or ordinate from it, never chained feature
  to feature, so tolerances do not accumulate. Give a bolt circle or radial
  pattern X/Y ordinates from that datum where the shop will set it up on a DRO.
- Prefer regular hole spacings that the shop can step off.
- The overall size is real and conspicuous. Nothing reads like an overall
  that is not one.
- Reference dimensions in parentheses are welcome.

### Rule 11 — Turned parts read like the lathe

- Draw the part as it sits in the lathe, with diameters on the side view, not
  leader-piled on the end view.
- Lengths run from a faced end. A part turned in two chuckings may dimension
  each side from the end faced in that chucking, with the overall length tying
  the two ends together. Do not mix the two ends within one setup's features.
- Every shoulder fillet has a size. Say `CENTRES OK` where centre holes do no
  harm.

### Rule 12 — Hole and slot callouts say what to do

- A hole callout gives the decimal Ø and the process: `Øn.nn REAM THRU`,
  `Øn.nn DRILL THRU`. A clearance hole gives its size, not "FOR 1/4-20 SHCS".
- A through tap can stay simple. A blind tap gives its required full-thread
  depth and, when it governs the operation, the separately deeper tap-drill
  depth. Those are not interchangeable; never let a modelled minor-diameter
  continuation or a default through-thread callout imply usable thread where
  none is required.
- A hole table may print the tap drill over the thread in the CAD system's
  standard two-line form. That is the table's format, not an added process
  constraint.
- Slots are dimensioned to their radius centres.

## Layout

### Rule 13 — Stay inside the border

The inner drawing border is a hard boundary. Every view, dimension, extension
line, leader, callout, note, balloon, table and assembly step stays wholly
inside it, clear of zone labels and the title block, with visible air around
the content. Touching or spilling through the border is a clarity defect,
never cosmetic polish.

### Rule 14 — Keep text off the part

- Dimension text and feature callouts sit outside the part or assembly
  silhouette by default. Hole-table tags, balloons and section identifiers are
  not feature callouts.
- Interior placement is acceptable only where a confined detail or a genuine
  lack of sheet space makes it materially clearer than every exterior option.
  Convenience is not a reason. Interior text never masks geometry, hides a
  feature or component, or crosses a line.
- No leader crosses another leader, a view it does not annotate, or a
  dimension line, and no text sits on or is struck by a line. That list is
  complete: a leader crossing an extension line or the outline of the feature
  it annotates, a radius or diameter line drawn through its centre, and
  extension lines crossing each other are conventional and not defects.

### Rule 15 — Balance the sheet; add a sheet before cramming

- Follow drafting convention: third-angle projection, distinct line weights,
  and projected front, top and side views kept in ASME alignment. Never stagger
  them for composition.
- The view group, tables and steps look intentional and balanced in the
  usable region, not bunched against one edge beside a large empty field.
  That is the whole test: a sparse sheet whose views are spread across the
  usable region, or a full-width view group in the template's normal
  position, is balanced. Correctness comes before balance.
- Choose landscape or portrait by the useful scale of the views and the room
  the dimensions, BOM and steps need. A sparse sheet with undersized views is
  in the wrong orientation when rotating the same content would make it
  materially larger or easier to read. Do not rotate for preference alone.
- Resolve crowding by moving the aligned group, changing orientation or scale,
  or moving non-projected views and annotations. Once those are exhausted, add
  a sheet. A package may have as many sheets as it needs. A sheet is too
  crowded when the callouts, balloons, steps or notes of one view overlap or
  press against another's; move whole sections, details, the hole table, the
  exploded view, the BOM or the step list to their own sheet. Never shrink
  views, abbreviate qualifiers or thread text between lines to make room, and
  never scale a view down just to fit a sheet.

## Design for the shop

Drawing review is where a design meets the shop. These rules judge the
depicted geometry, not only its annotation.

### Rule 16 — Design for the cutter

- At least one plausible one-off route allowed by the title block must produce
  every visible feature. Watch cutter and casting access, trapped geometry and
  vanishing walls.
- No perfectly sharp internal corners. Give internal corners a radius, as
  large as function allows, and say the largest radius acceptable when the
  corner matters, so the shop can pick a rigid cutter.
- Prefer a chamfer to a radius on an outside edge.
- Truncate a knife edge or acute point with a small stated flat or radius;
  dimension it to the theoretical sharp where that is the controlling size.
- Give a thread that runs to a shoulder a relief of at least one pitch.
- A press-fitted dowel or bearing needs a way out: never press a dowel into a
  blind hole without a knockout hole or extraction thread, and give a pressed
  bearing a shoulder gap or knockout access.
- Prefer coarse threads in soft receivers such as aluminium, and avoid #6-32
  and smaller taps in tough material.

### Rule 17 — Walls and webs: 2.0 mm target, 1.5 mm floor, at the worst case

Every machined wall or web targets at least 2.0 mm, with a hard floor of
1.5 mm. That includes the thread major diameter to an edge or another bore, a
counterbore or countersink to an outside surface, and the ligament over a
cross-hole. Judge it at the worst case of the printed bands (the title-block
band for its decimal places, DRILLED HOLES, or the explicit band) plus
realistic drill wander on a deep hole, never at nominal and never by
root-sum-square. Fix a thin wall with geometry so the bands can stay loose,
never with a tighter band.

### Rule 18 — Thread engagement: 1.5D of full thread

A fastener engages at least 1.5 × its nominal diameter of FULL thread in its
receiver at the worst case. Count only full threads: a tap or die leaves about
one to one and a half incomplete threads, and projection through a clearance
hole is not engagement. A blind tap leaves room beyond the full thread for the
tap's lead, and the thread major envelope never breaks through a nearby wall.
Engagement is not retention: rule 23 still applies to every exposed joint.

### Rule 19 — Absorb stacks at fit-up, not with tighter bands

Where parts stack up to a gap, clearance or alignment, either the loose bands
hold it at the worst case or a stated fit-up adjustment covers the whole
worst-case range: a slot, shim, feeler-set gap, cut-to-fit length or
match-drilled hole, named in the assembly step. A stack that silently depends
on tight part bands is a defect; the fix is an adjustment, not a tighter part.
A part that states a supply size and a set-at-assembly size for the same
feature (`SUPPLY n.nn MIN`, `n.nn SET AT ASSEMBLY n.nn–n.nn`) is describing
this adjustment, not contradicting itself.

### Rule 20 — State a known shortfall as a plain fact

Where a part knowingly falls short of rules 17–18 or another numeric rule, its
sheet (or the assembly step that sets it) states the shortfall and its value as
a manufacturing fact, for example `ENGAGEMENT n.nn MIN (n.nnD)` or
`WALL n.nn MIN`. The sheet never argues for it: no rule numbers and no words
such as EXCEPTION, ACCEPTED, RULING, POLICY or BOOK FIDELITY. Stating a
shortfall makes it visible; it does not approve it. Approval belongs to the
project owner and lives outside the drawing.

### Rule 21 — Fix the model, not the drawing

A drawing faithfully depicting a part can still expose a defect in the model: a
part that is physically impossible, implausible for every allowed process,
self-contradictory, or missing a necessary physical feature. Never paper over
it with an invented dimension, radius, note or process callout on the sheet.
Fix a uniquely supported omission in the model and regenerate the drawing.
When the evidence permits materially different geometries or processes, the
owner decides. Equally, never demand a preferred process or value when another
allowed route makes the part exactly as drawn.

## Assemblies

The parts arrive made to their own part drawings. An assembly package is
judged on what a fitter needs to assemble, set up and check the
sub-assembly, never on part fabrication.

### Rule 22 — An assembly package is complete

- An assembled view set showing the finished sub-assembly in its working
  pose, at a scale where every part is identifiable, plus the isometric
  (rule 8).
- An exploded view, or a sequence of them, showing order, orientation and
  which face mates to which.
- A parts list with item number, part number, description and quantity, and
  balloons tying every visible part to it. Every row is ballooned somewhere;
  every balloon has a row.
- Ordered assembly steps, each a short instruction the fitter can act on:
  press this bushing to this depth, set this mesh with this backlash, torque
  this screw, align this axis to that face within so much. A fit made at
  assembly (match-drill, ream in place, shim, adjust) names the mating parts
  as rule 4 requires; an item reference is enough when the BOM supplies the
  item's name and number unambiguously.
- The few assembly-level dimensions and checks that exist only once the parts
  are together (positions, gaps, clearances, travels, alignments, preloads),
  each with an unambiguous acceptance criterion and a way to check it.
- Setup and adjustment: anything with parked and engaged states, an adjusting
  screw, a zero or a spring tension states its as-shipped state and its
  setting procedure without ambiguity.
- Consumables and loose items: lubricant, thread locker, loose pins, shims,
  all named.

A three-view orientation sheet without these is a placeholder, not a package.

### Rule 23 — Lock threaded joints exposed to operating loads

For every threaded joint the package shows or depends on, identify what is
fixed and what turns, rocks, swings or reverses, and whether drag, torque
reversal, vibration or loss of preload can turn the threaded member or unload
its seat. A screw that a part pivots, swings or turns on is always exposed.
Such a joint shows its mechanical anti-loosening means in a view or detail and
the step that engages it: a jam nut, a nut locked by a pin or tab, a
cross-pin, a key or flat with axial capture, a pinch clamp across a slit
thread, or a staked or peened end.

- The duty does not lapse at the package boundary. A joint listed as an
  external interface, installed "at final assembly" or left to another
  package still needs its lock and locking step here, or a reference to the
  drawing and step that give them. A swinging or turning part in this package
  that rides on an unlocked screw is a defect of this package.
- A plain seated thread, shoulder, shim, unspecified tightening, lubricant or
  thread locker alone does not lock such a joint.
- A cap or nut that retains a rotating cluster axially does not lock a
  different interface, such as the stud's own thread in its frame.
- A static clamp that no operating torque reaches needs no lock.

### Rule 24 — Assembly sheets carry assembly information only

Part tolerances, materials and finishes belong on the part drawings; repeating
them on an assembly is clutter. Torque values may be given once in a general
note rather than per screw. This rule governs assembly sheets only; a part
sheet's notes are judged by rule 7.

## Every package

### Rule 25 — Every sheet agrees with every other

A package is reviewed as a whole. A dimension supplied on another sheet is not
missing, but any contradiction is a blocker, because the builder cannot tell
which statement to obey. A contradiction is two statements that cannot both be
obeyed. That includes:

- two views that cannot both be true of one part, such as a projection that
  disagrees with its neighbour;
- a callout, note, table or step that disagrees with the views or with
  another statement, for example "BOTH ENDS" against "PLAIN END UNCUT", or a
  station table ordered opposite to the views;
- conflicting title blocks;
- on an assembly, item numbers, quantities or descriptions that disagree
  across BOMs and balloons, and setup or assembly steps that disagree across
  sheet boundaries.

Statements that can both be obeyed are not a contradiction: a tighter local
band inside the title-block band, a material picked from the title block's
listed alternatives, the same size spelled with different places (`Øn.n` and
`Øn.nn`), a supply size and a set-at-assembly size (rule 19), or a view-scale
label differing from the title-block scale on a DO NOT SCALE sheet. Judge
those under rules 2, 3 or 7 at their own severity.

## Sources and departures

The rules distil three shop-floor sources. Their text lives in the
`references` submodule.

| source | where | used in |
|---|---|---|
| James Harvey, *Machine Shop Trade Secrets*, 2nd ed. (Industrial Press, 2013), ch. 9 "Help for Engineers", tips 1–37 | `references/machine-shop-trade-secrets-harvey-2e/` | 1 (#1, #2), 3 (#4), 4 (#15, #37), 6 (#34), 7 (#11, #13), 9 (#17), 10 (#6, #9, #18, #25), 11 (#16, #20, #24), 12 (#12, #13, #14, #19, #33), 16 (#7, #8, #10, #22, #26, #29, #32, #36) |
| Tom Lipton, *Metalworking Sink or Swim* (Industrial Press, 2009), ch. 2 "Brain Food" (communication, drawing and sketching) and ch. 3 "Bean Counter Lounge" (tolerancing and drawing advice to engineers) | `references/metalworking-sink-or-swim-lipton/` | 1, 4 (stock and cleanup allowance, fit by function, explain why), 5 ("a loaded gun"), 7 (leader-flagged notes, no "opposite hand"), 9 (section instead of dimensioning hidden features), 10 (ordinate patterns), 11 (faced-end datums, two for two-sided parts), 15 (conventions, add a sheet, never scale to fit), 16 (theoretical sharp, knife edges, thread relief) |
| HardTurn, "Why Do Engineers Overengineer Everything?" (YouTube, 2026-10-09), <https://www.youtube.com/watch?v=91nUum8PkXA> | `references/hardturn-why-engineers-overengineer/` | 1 (busy prints, needless detail views), 3 (no extra places on chamfers and radii), 4 (tight only for bearing, sealing, press and critical bores; say why; pass-through holes stay loose), 16 (state the allowable corner radius up front) |

Deliberate departures:

- **Hidden lines.** Harvey (#30) and Lipton ask for hidden lines in every view,
  or a statement that they were left out. These drawings follow ASME Y14.3
  instead and show them only where they inform (rule 9): on castings,
  hidden lines in every view buried the dimensions.
- **Units.** Harvey (#28) asks for inch equivalents after metric dimensions.
  The shop's DROs read millimetres, and dual dimensions would double the text
  on crowded sheets, so prints stay in millimetres (with US fastener and drill
  sizes).
- **Not applicable.** Welded low-quantity assemblies (#5), Delrin (#21), lead
  times (#23), returning borrowed tools (#27), revision highlighting (#3; each
  package is regenerated whole and the title block carries its revision), and
  flex clamping (#35) concern a contract shop rather than this one builder.
