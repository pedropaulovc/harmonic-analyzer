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

The builder learned to read prints from a textbook and a shop handbook and
reads each callout once, at the machine. They know standard ASME symbols and
shop words; they do not know this project's private vocabulary, its CAD model
or why the designer chose a number. A phrase they would have to ask about is
a question under rule 1.

### What the shop holds

Every explicit band on a fabricated feature is judged against this table. It
is the declared capability of the shop above for one part cut by a first-time
machinist and checked with the listed tools. It is not a target, and it is
the only capability figure a review may use.

| feature, inch sheet | narrowest band held and checked | with |
|---|---|---|
| location of a drilled hole from a datum edge or bore | ±.005 | edge finder, DRO, spot drill; height gauge and pin |
| location of a reamed or bored hole or a milled step, up to 6 in from its datum | ±.002 | as above, then ream or bore; surface plate, pin, indicator |
| the same, more than 6 in from its datum, measured along the toleranced direction | ±.004 | DRO over long travel in a shop without temperature control |
| milled width, thickness or slot | ±.001 | micrometer, gauge blocks |
| turned diameter | ±.0005 | micrometer, made to the measured mate |
| turned length or shoulder | ±.001 | DRO, depth micrometer |
| reamed hole size | the reamer's size, banded no tighter than `+.0005 / 0` | pin gauges |
| angle | ±0.25° | sine bar and gauge blocks |
| flatness, parallelism, perpendicularity, runout | .001 per inch of feature, never under .001 total | surface plate, indicator, V-blocks |
| position of a reamed pattern | Ø.004 | surface plate, pins, height gauge |
| assembly gap, alignment or end play | ±.0005 | dial or test indicator, feeler gauges |

Unconverted millimetre sheets use the same rows at ±0.12, ±0.05, ±0.10,
±0.025, ±0.012, ±0.025 mm and Ø0.1 mm position.

A band narrower than its row cannot be reached by cutting to a number. It is
reached only by a **fit route** the sheet names at the feature:

- a matched fit to a named mate with its stated clearance, interference or
  acceptance (rule 4);
- match-drilling, reaming in place or transferring through the mate;
- a set-at-assembly feature (slot, shim, adjusting screw, feeler-set gap)
  whose setting and acceptance the assembly step gives (rule 19); or
- purchased precision stock (`STOCK OK`, drill rod, ground shaft, dowel).

Rule 4 applies the table.

Prints use decimal inches on ASME sheets in third-angle projection. During the
package-by-package conversion, unconverted packages remain in millimetres;
read each sheet's UNIT cell and its own title-block bands. Metric-only purchased
product lines retain explicitly labelled millimetre reference sheets.
Fasteners, taps and drills are US customary (3/8, #14, 1/4-20).
Fractions are reserved for as-bought stock and supplier dimensions, shown as
REF, untoleranced; the supplier's catalogue tolerance governs. They have no
general FRACTIONS tolerance row.

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
two tests seem to pull apart, answer the question. Repeated prose is not a
redundant dimension: the same reason printed on several dimensions, or a
paragraph on a leader, is a busy print (rule 7).

## Specification

### Rule 2 — The title block is the general specification

Units, the one-, two- and three-place linear tolerances, the angular
tolerance, the DRILLED HOLES band, the edge break, the thread
class, the surface row, material and finish live in the title block and
nowhere else. A note or callout never restates them, and a reviewer never asks
for what the title block already says.

Inch sheets use `.X ±.1`, `.XX ±.01`, `.XXX ±.005`, angular `±1°`,
DRILLED HOLES `+.004 / 0`, edge break `R.010` or `.010` chamfer, and
inside corners `R.040 MAX`. Unconverted millimetre sheets retain their printed
metric grades until their package is converted.

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

- On inch sheets, three places mean `.XXX ±.005`, two mean `.XX ±.01`,
  and one means `.X ±.1`. Use `.X` only for non-functional features such as
  profiles, chamfers and unmated overall lengths. A feature used by a stack,
  wall or fit check needs `.XX` or tighter. A clearance whose `.XX` band
  would leave too little room to the part it clears takes `.XXX` and names
  that part (`Ø1.083 CAP RECESS, CLEARS MHA-FR-VN-54 SKIRT`); that third
  place is not over-specification.
- Inch drill diameters, including native Hole Wizard callouts, use three
  decimal places. Their tolerance still comes from DRILLED HOLES, not the
  three-place linear grade. Keep the exact decimal of a named number, letter
  or fractional drill (`#30 DRILL Ø.1285`): that digit is the drill's size,
  not precision. A plain decimal with no drill named (`Ø.106`) is simply a
  size under DRILLED HOLES; it is not a rounded drill. Counterbore and
  countersink diameters and depths in a Hole
  Wizard callout print in its standard three-place form; they are clearance
  pockets toleranced by the `.XX` grade, not over-specification. Tap and
  tap-drill depths and routine locations normally use two places.
- On unconverted millimetre sheets, the existing one-, two- and three-place
  grades remain in force; drill diameters normally use two places.
- Fabricated nominals sit on their printed grid: `.01 in` for `.XX`,
  `.001 in` for `.XXX`. Gear, chain and rack pitch geometry, kinematic
  closures, supplier sizes and calibrated spring geometry are exempt.
- A dimension that carries its own band is toleranced by that band. Its
  nominal and deviations need enough places to preserve the authored limits;
  rounding them to the general grade is not permitted.
- A three-place non-drilled size with no band and no stated function is
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
  the callout, or a flagged note attached to it (rule 7), names the mate and
  the fit it needs: running, sliding, press, bonded or locating. A gear centre
  distance names the mesh; a width that sets a stack names the stack. Where
  the mate alone does not show why the band is tight, add a few words of
  reason (`SETS MESH BACKLASH`, `KNIFE-EDGE SEAT`); see rule 7. The shop can
  then make the hole to the shaft instead of chasing a number. A tight band
  whose mate appears nowhere in the package is a blocker: either name the
  mate or loosen the band. A mate named somewhere in the package (a general
  note, a gear data block, another sheet) but not at the callout it serves is
  a clarity defect, not a blocker. One feature with several tight dimensions
  (a groove's diameter and radius, a bore's size and depth) names its mate
  once, on one numbered flag note linked to every one of those dimensions;
  that note counts as at each callout, and repeating the mate on each
  dimension is narration (rule 7).
- **Every mate is named by its drawing number.** Any callout, note, table
  row or step that refers to another part (MATCHES, FOR, ON, IN, FITS,
  LOCATES, SETS, CLEARS, SEATS ON, HOLDS) names it by its assigned drawing
  number (`MHA-CH-06-TL-VN-83`), with its name where that helps. Every part
  in this project, purchased parts and kits included, has a drawing number;
  a kit member also names the member (`HGR15 RAIL OF MHA-CH-06-TL-VN-83`).
  A mate in the same parent assembly as the sheet's own part may be named by
  its short form: the full number less the leading part it shares with the
  sheet's own number (on MHA-CH-06-TL-21, `TL-24` is MHA-CH-06-TL-24 and
  `TL-VN-77` is MHA-CH-06-TL-VN-77). A mate outside that parent assembly
  takes its full number (`MHA-CH-13`). A catalogue or vendor code (`HGR15R`,
  `KP08`, `HGH15CA`), a file slug (`MG-WHEEL-AXLE`), a short form that does
  not complete to a number from the sheet's own prefix, or a bare item number
  on a sheet with no parts list is not a drawing number; a catalogue code may
  follow the drawing number. A mate
  serving several features is named once, on the pattern callout, hole-table
  row or one flagged note linked to the features (rule 7), never repeated on
  each dimension. A mate the package identifies uniquely but by the wrong
  form is a clarity defect; a mate that cannot be identified at all is a
  blocker. A drawing number is complete as printed in its registered form:
  subsystems number differently (`MHA-PD-07`, `MHA-PD-VN-57`,
  `MHA-CH-06-TL-21`), so never demand a sub-group code a number does not
  have.
- **Matched or selectively fitted pairs.** For a one-off pair, the callout
  identifies the mate by name and full drawing number, and states
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
- **Read a band as its total width.** `+.001 / 0 in` is `.001 in` wide,
  the same as `±.0005 in`. Keep the nominal and asymmetric limits when checking a
  fit; equal widths are not equal fits.
- **Necessity, then the shop table.** Being printed does not make precision
  necessary. Unneeded precision is over-specification even when it is easy.
  Needed precision is then checked against "What the shop holds":
  - A band narrower than its row, with no fit route named at the feature, is
    unbuildable as a cut-to-number dimension. Quote the band, the row and the
    missing route. Do not decide whether the function could live with less;
    the designer either names the route or changes the design.
  - A band inside its row but narrower than `.002` total on a location,
    length or setting needs the same named fit route or a stated check at the
    feature (what it is checked against and with which listed tool). Missing
    that support is a clarity defect, not a claim that the band is impossible.
  - Use no figure the table does not give. DRO or micrometer resolution is not
    accuracy, and "the DRO reads to .0002" never excuses a band. Do not
    assume grinding, lapping, temperature-controlled metrology or an ideal
    reamed hole.
- **A clearance hole is never located tighter than its clearance.** With hole
  Ø H and fastener Ø F, its position tolerance is at least Ø(H−F) when both
  parts have clearance holes and Ø(H−F)/2 when the mate is tapped or pinned
  (± a quarter of that per axis). Where the fastener is not printed, a THRU
  hole with no REAM, dowel or register word carries no position tighter than
  Ø.010 and no location band tighter than ±.005. Tighter is over-specification.
- **Bands are written in inch steps.** An explicit inch band uses a plain
  inch step (`±.0005`, `±.001`, `±.002`, `±.005`, `+.001 / 0`), not a
  converted millimetre value (`±.0008`, `±.0009`, `Ø.0039`). A converted band
  is a clarity defect: it reads as a deliberate precision no one chose.
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

| surface | inch sheet, µin Ra | unconverted metric sheet, µm Ra |
|---|---|---|
| journal or bore that runs, cam-follower contact, slide, knife edge and its seat | 63 | 1.6 |
| knife edge or pivot-screw shoulder that must be ground | 32 | 0.8 |
| one static mating seat that locates the part on its neighbour (a foot on a base, a bolted register) | 125 | 3.2 |

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

- A note never restates the title block and never explains what a datum
  letter is. Ordinary sizes and locations sit on the views or in a hole
  table. A numbered note linked to its feature by a flag or `SEE NOTE n` may
  carry a fit-up or supply requirement with its limits (`SUPPLY .292 MIN;
  FITTED .153–.271 AT ASSEMBLY`); it then counts as being at the callout, and
  the feature carries no second controlling value. Other part numbers appear
  only to identify a mate.
- **Say why in a few words, once.** A short functional reason is welcome
  where a tight band, a roughness symbol or a hardness would otherwise look
  arbitrary: `BEARING SURFACE`, `KNIFE-EDGE SEAT`, `SETS MESH BACKLASH`,
  `SLIDING FIT ON MHA-CH-05`. A reason is one line of at most six words,
  beyond the mate's drawing number, on the callout it explains, once per
  feature or pattern. A matched-fit statement (rule 4) and a stated shortfall
  (rule 20) have their own forms and are not counted. Anything beyond that is
  narration and is over-specification: design rationale (`HOLDS … SCREWS
  CLEAR OF ITS CUT EDGES`, `MAX KEEPS D AT ENTRY`, `MIRRORS CL STATION`), a
  second reason on one feature, the same reason repeated on several
  dimensions, a reason on an overall or stock size that has no band of its
  own (an overall with an explicit tight band that sets a stack names that
  stack once under rule 4, and that is not narration), or an assembly
  instruction on a part sheet (`END FLUSH WITH CRANK ARM FRONT`, `ALL 8
  SCREWS START BY HAND`, `DISASSEMBLE AT MHA-DT-09`). Match-drilling or
  reaming at assembly with its mate is a requirement, not narration.
- **A location dimension carries its value and band and nothing else.** The
  mate or reason a location serves sits once on the hole's size callout,
  its hole-table row or a linked flag note.
- **A callout is short.** Size and process lines (Hole Wizard form, thread,
  depth, stacked limits, `nX`) plus at most two lines of words. Anything
  longer moves to a numbered flag note linked to the feature.
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
- Standard parts cut lengthwise in an assembly section (screws, pins,
  shafts, keys) are conventionally left unhatched; a hatched one is polish.
- A section never carries hidden lines. It shows either the material beyond
  the cut in solid lines or only the cut faces. Hatched slices among dashed
  ghosts of removed material mean the cut is in the wrong place.
- Never dimension to a hidden line. Cut a section or breakout instead.
- **Every section, detail and auxiliary view says what it shows.** It is
  labelled with a letter (`SECTION A-A`, `DETAIL B`, `VIEW C`), plus its scale
  when that differs from the sheet scale, and its cutting plane, detail
  boundary or viewing arrow sits on a parent view with the same letter. A
  view named only in prose (`LEVER TIP DETAIL`, `GRADUATED UNDERSIDE`), or an
  enlarged view with no boundary on a parent, is unlabelled. A rotated view
  says so. Projected principal views (front, top, side in third-angle
  alignment) need no label.
- **A section shows the whole cut or says which part of it is shown.** Where
  the cutting plane passes through several like features and the section is
  broken to one of them, the label names that feature (`SECTION A-A, HOLE
  A2`) or the plane is moved to cut a single feature. A section is never
  explained by a prose note; what it shows is read from its plane and label.
  If the builder cannot tell which feature's size, depth or orientation the
  section defines anywhere in the package, that is missing information.
- A callout never defers a size to another view (`FLOOR: SECTION B-B`).

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
- **Use a hole table when the holes outgrow dimensions.** When one view
  locates eight or more hole axes, or when a location dimension line would
  cross another dimension line, locate the holes with a tagged hole table
  instead of individual dimensions: an origin mark on a real datum (above),
  a tag at each hole, X and Y from that origin, the size callout once per tag
  group and one column naming the mate (rule 4). The view then carries the
  overall, the datum features and the non-hole geometry. Ordinate
  dimensioning with grouped hole callouts is an equal alternative for a view
  with no more than two hole sizes. A single regular pattern (`20X Ø.089 ON
  .250 PITCH`) counts as one axis. The CAD system's origin mark, drawn as
  arrows offset along the datum bore's centrelines, marks that bore; it is
  not a mid-air origin.
- **Identical holes take one callout.** Give them one `nX` callout or one
  table tag group, never a repeated callout per hole.
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
  bearing a shoulder gap or knockout access. A permanent pair the package
  names as one unit (rule 23) is exempt.
- Prefer coarse threads in soft receivers such as aluminium, and avoid #6-32
  and smaller taps in tough material.

### Rule 17 — Walls and webs: .080 in target, .060 in floor, at the worst case

Every machined wall or web on a converted inch package targets at least
`.080 in`, with a hard floor of `.060 in`. Unconverted metric packages keep
their existing 2.0 mm target and 1.5 mm floor until conversion.
That includes the thread major diameter to an edge or another bore, a
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
Engagement is not retention: rule 23 still applies to every fixed joint.

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
project owner and lives outside the drawing, as an owner exception supplied
to the review. A stated value below a hard floor (the `.060 in` wall, 1.5D
engagement, an adjustment range short of its worst-case stack) still gates
unless an owner exception covers that feature and value. A wall between the
floor and the target is advisory.

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
  this screw, align this axis to that face within so much. A step does one
  thing and is at most six printed lines. A check and its remedy (`IF THE
  FEELER STOPS, …`) are separate steps; a sequence that needs more is more
  steps, not a longer one. A setting table gives the reference, target,
  range and check in columns; a check with three or more measured variables
  uses a labelled sketch and a table, not equations in prose. Steps name
  parts by item number (with the BOM supplying the full drawing number) and
  directions by view names (rule 26), never a compass or a code the sheet
  does not define in a labelled table (`HD1`, `F1A`, `P1–P3`). A setting
  finer than `.XXX` names the indicator or gauge that reads it. A fit made at
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

### Rule 23 — Retain every fixed joint, and print how

A fixed joint is two parts that operation needs to stay put against each
other: a hub, gear, cam, collar, pin, rod, stud, bushing or block on its mate,
threaded or not. A CAD mate, lock mate or passing kinematic check holds
nothing. For every fixed joint the package shows or depends on, say what
turns, rocks, reverses, pulls or is grabbed there, and print the physical
means that holds it. Choose it in this order: it holds the joint in use and
in ordinary handling; among those that do, it keeps the original machine's
visible form (a hidden bond beats an added visible screw); among those, it is
the simplest for a first-time builder at a bench; last, it best survives
handling. No particular device is required, and a reviewer's preference for
one adequate method over another is not a defect.

| load at the joint | counts | never counts on its own |
|---|---|---|
| static clamp: nothing moves, no torque about the fastener | seated screws; a one-screw part that could turn about its screw is located by a dowel, tongue, step or second screw | a lock in place of a locating feature |
| axial: a pin, rod, stud or bushing must not pull out or walk | press fit; bonded slip fit; thread to a shoulder; cross-pin; set screw into a spot; peened or staked end | set screw on a plain round; solder |
| friction torque: a member turns or rocks on a stationary shaft or screw | press or bonded fit; cross-pin; set screws bearing on a flat or spot (the member's light rubbing drag needs no further lock); jam nut; staked or peened tail; red threadlocker on a seated thread | a plain seated thread; `SNUG`; a set screw on a plain round |
| drive torque: the joint transmits working torque, usually reversing | key or flat with axial capture; cross- or taper pin; press or bonded fit; pressed drive pins; set screw on a flat, staked, for light torque only | set screw on a plain round; solder; threadlocker |
| adjuster: the thread's own turn sets a position, gap or preload | jam nut; pinch clamp across a slit; jam screw; locked nut; none only by owner ruling | threadlocker; stake |
| adjustable clamp: a member clamped at a setting along a rod or slot that must stay adjustable | a clamp screw or thumb screw bearing on the round, or a pinch clamp across a slit, with a step that sets it and checks it holds; a light-load clamp only | a bond, stake or flat that fixes the setting |
| pivot: a member swings or spins on a threaded shoulder | staked tap mouth on a flush tip (steel receiver); jam nut or cross-pin on the tail; red threadlocker on a seated shoulder | a shoulder alone |
| sheet, tube or wire to metal; wood to metal | braze with its filler; soft solder on a shear lap; retaining compound for a tube in a sleeve; epoxy for wood | solder in a torque or peel path |

- **A specified anaerobic bond is a fit, equal to a press fit.** A bonded
  joint prints its grade by number (`LOCTITE 638`, `609`; `641` where the
  part must come out), never a colour; the diametral clearance on the part
  sheet inside that grade's gap; degrease; apply to the pin, not a blind
  seat; keep compound off running lands; set inside the fixture time when
  it is set to a dimension; and the cure before first load or oiling. One
  general note per package may carry the degrease, apply and cure rules.
  Retaining compound and threadlocker are not interchangeable.
- **Red threadlocker (`262`, `263`) is a lock** on a seated thread of #10 or
  larger, printed with grade, degrease, cure and an acceptance; never on an
  adjuster or a joint that must open (below). Low- and medium-strength grades
  (`222`, `243`, `290`) are optional consumables and never the lock.
- **Print it where it is made.** The part sheet gives the fit or feature and
  its mate (rule 4): press with its interference, bonded with its clearance,
  a flat, spot, cross hole or taper at its station. The assembly step gives
  the method and grade, the press direction and its stop or flush limit, the
  stake points or nut order, and an acceptance the builder can do at the
  bench (`DOES NOT TURN OR SLIDE BY HAND`, `FLUSH`, `SWINGS FREE UNDER ITS
  OWN WEIGHT`). A press whose part slides in by hand is a slip fit; the step
  says what to do then. Every lock part is in the BOM and a view; every
  stake or peen is in a view or detail.
- **Keep what must open openable.** Pen and marker changes, adjusters, gear
  and feed setup, wear parts and the book's teaching splits stay releasable
  with hand tools. A bond or stake there is a defect. A permanent pair
  (a drum on its wheel) is fine when the unit comes off as a whole; releasing
  a bond takes about 250 °C, never next to wood, epoxy or paint.
- **A stake needs a steel receiver.** A gray-iron, hardened or thin-walled
  receiver takes another method.
- The duty does not lapse at the package boundary. A joint listed as an
  external interface, installed "at final assembly" or left to another
  package still needs its retention and step here, or a reference to the
  drawing and step that give them. A part in this package that rides on an
  unretained joint is a defect of this package.
- A cap or nut that retains a rotating cluster axially does not retain a
  different interface, such as the stud's own thread in its frame.
- The reviewer checks what is printed against this table and never computes a
  capacity or invents a load.

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

### Rule 26 — Standard forms only

A first-time builder reads these prints with ASME Y14.5 and a shop handbook
beside them. Every symbol, abbreviation and phrase is one they can look up.

- **Views.** Projected principal views need no names. Every other view
  carries a standard label (`SECTION A-A`, `DETAIL B`, `VIEW C`), never a
  prose name (`VIEW FROM THE BACK`). Notes and steps give directions by the
  standard view names (front, top, right side), never a compass (`NORTH`,
  `EAST`), a clock reading or a private convention.
- **Holes.** Size first, then process, then depth, with the Y14.5 symbols:
  `Ø.257 THRU`, `Ø.3750 +.0015/+.0010 REAM THRU`, `⌴ Ø.31 ↧ .19`,
  `⌵ Ø.312 X 82°`, `1/4-20 UNC ↧ .45`. A counterbore or countersink is
  written with its symbol, not in words; a depth is never deferred to a view.
  A depth printed as REF in the callout is complete when a controlling
  dimension on the views locates the floor (`↧ (.235)` with the floor at `.65`
  from the socket axis).
- **Words.** `MIN`, `MAX`, `REF`, `THRU` (the CAD form `THRU ALL` reads the
  same and is not a defect), `nX`, `°`, and the standard fit
  names (running, sliding, locational clearance, locational interference,
  press, drive, bonded with its LOCTITE grade). Private phrases a reader
  cannot look up are defects: `TO SUIT`, `ON SEAM`, `IN PHASE`, `MIRRORS`,
  `SAME X AS`, `AIR` for clearance,
  `BY EYE`, `TRUE D`. A location is a dimension or a table row, not a
  sentence; holes in line share a drawn centreline. A plain functional
  acceptance in ordinary words (`SLIDES IN, NO ROCK`, `TURNS FREE, NO
  RATTLE`) is a stated acceptance, not a private phrase. An `nX` count on a
  section that names its hole applies to that hole's table group.
- **Project labels.** A label made up for this project (`R816`, `CL`, `CR`,
  `TIE 1`) is defined where it first appears or in one linked key on the
  same sheet, or replaced by a hole-table tag or a standard numbered flag
  note. A symbol followed by a number (`R816`) is either a dimension with its
  unit or a defined label; the reader never has to choose.
- **Geometric symbols** (rule 5): position, perpendicularity, parallelism,
  flatness, runout, concentricity and profile with an equal bilateral zone,
  each with plain datums. No Ⓤ, Ⓟ, Ⓜ, Ⓛ, free-state or translation modifiers
  and no composite frames; where a profile would be unequally disposed,
  dimension the offset surface instead.
- **Units.** An inch sheet prints inch values. A metric pitch inherited from a
  purchased part is converted on the fabricated part's sheet, or carried in a
  hole-table column headed `mm` beside the inch columns; a view never mixes
  `mm` values with inch values. One linked flag note may state a purchased
  part's catalogue spacing in millimetres as REF (`B1 TO B2: 42.00 mm REF,
  KP08 CATALOGUE SPACING`) beside the inch dimensions that control it; that
  is a labelled reference, not mixed units.
- **Spelling slips** that a reader cannot misread (`45 DEG` for `45°`, `min.`
  for `MIN`, a thread class repeated on a callout) are polish, never a reason
  on their own to hold a sheet.

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
  Prints are decimal-inch with US fastener and drill sizes; unconverted
  packages stay millimetre until converted, and purchased metric product
  lines keep labelled millimetre reference sheets. Dual dimensions would
  double the text on crowded sheets, so a view carries one unit (rule 26).
- **Not applicable.** Welded low-quantity assemblies (#5), Delrin (#21), lead
  times (#23), returning borrowed tools (#27), revision highlighting (#3; each
  package is regenerated whole and the title block carries its revision), and
  flex clamping (#35) concern a contract shop rather than this one builder.
