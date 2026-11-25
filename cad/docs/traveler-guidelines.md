---
# Bump major_version when an edit should change traveler machinist-review
# verdicts; other edits do not re-run cached reviews.
major_version: 3
---
# Traveler guidelines (machinist review v3)

The standard every process traveler (CNC setup sheet, manual-lathe traveler and
saw/bench sheet) in this project is written to and reviewed against. Authors
follow it. Each blind traveler review receives `drawing-guidelines.md` from its
title down, then this file from its title down, followed by its own reviewer
instructions.

Cite a traveler rule by its `T` number and title, for example "rule T10 (every
check can be done as written)", and a shared drawing rule by its number and
title, for example "rule 26 (standard forms only)".

## T0 — Who reads a traveler, and how it pairs with the drawing

One builder, the same first-time hobby machinist as `drawing-guidelines.md`,
reading the traveler **step by step at the machine** rather than once. Where a
part drawing defines *what* the finished part is (and bans manufacturing
methods under rule 7), the traveler defines *how* this shop cuts, holds and
checks it from arriving stock to finished part.

The declared shop is the equipment in `drawing-guidelines.md` ("Who reads these
drawings"), plus the shop's process equipment:

- **CNC mill:** a CNC-converted PM-30MV running FluidNC and CNCjs with manual
  tool change, an electronic tool setter (20 mm pad), a non-spinning 3D touch
  probe and a `.200 in` mechanical edge finder. Spindle speed (`100–2800 rpm`
  on the low belt) is set by hand on the headstock knob; X and Y have
  ballscrews.
- **Manual lathe:** a PM-1127VF-LB lathe (`70–380` and `380–2000 rpm`) with a
  two-axis DRO, chucks, live/dead centres and lathe boring bars; there is no
  milling boring head and no CNC lathe.
- **Bench, hand tools and bore checks:** assume a well-equipped home shop —
  most ordinary hand tools (files, stones, abrasive rolls, scrapers, blades,
  squares, clamps, hex keys, wrenches, torque wrenches / torque screwdriver,
  soft-jaw bench vise, miter saw or bandsaw, spring-loaded spindle tap guide,
  feeler leaves) are available even when not itemized on the Tools table. A
  fit bore is accepted with its mate, as "What the shop holds" says: the
  bought shaft or pin tried in it, or the made mate turned to it. A pin-gauge
  set in `.001 in` steps and telescoping gauges read on the `.0001 in` outside
  micrometers serve to read a hole for the mate's first cut (see rule T11
  for what they cannot accept). No traveler adds a plug gauge, a GO / NO-GO
  pin pair or a reamer bought for one band on its own account: a band that
  seems to need one is a drawing defect (drawing rule 4), raised against the
  drawing, not answered with a purchase. Where the part drawing still prints
  such a band, the traveler checks it as printed, with pin gauges where
  their step resolves the band and otherwise a named GO / NO-GO pair (rule
  T11), and the review summary reports the band as a
  drawing defect. A CMM, optical
  comparator, air gauge, bore micrometer, small-hole gauge or production
  metrology lab is not in the shop.

How `drawing-guidelines.md` applies to a traveler review:

- **Applies unchanged:** rule 1 (no questions, nothing extra), rules 2–4 (title
  block, decimal places, fit routes and "What the shop holds", as the authority
  for the part requirements the traveler must meet), rule 10 (pick-up from real
  physical features), rule 25 (every sheet agrees with every other) and rule 26
  (standard shop words and unit discipline).
- **Applies by analogy:** rule 22's step discipline (concise steps, check and
  remedy separated, consumables named) and rule 23's requirement to name
  adhesives and retaining compounds by product and grade.
- **Does not apply to travelers:** rule 7's ban on methods (methods are the
  traveler's purpose), rules 5–6 and 8–15 on schematic setup pictures (setup
  diagrams are process schematics, not ASME orthographic projections), and
  rules 22–24's assembly-BOM/balloon rules. Never re-review the companion part
  drawing's own drafting layout, GD&T or note count during a traveler review;
  the drawing has its own review and is taken as the specification authority.

### Division of labour with deterministic build gates

For a part enrolled in the CNC build, `build` and `release` run two
deterministic gates on the same plan the traveler prints from:

- **`prechips:<stem>`** renders the traveler and refuses it (no sheet at all)
  on a failed enforced check: `stock_fit`, `cutting_speeds`,
  `milling_deflection`, `turning_deflection`, `tool_sizing`,
  `gauge_capability`, `vise_holding`, `lathe_holding`, `machine_capacity`,
  `drill_pecking` and `indexing`. Its CAD values (`{{cad.*}}`) come from the
  part's exported `features.toml`.
- **`cam:<stem>`** posts the NC programs and checks each against the checks
  its recipe selects: cut depths and hole bottoms, spindle speeds per tool
  section (a speed change needs an `M0`), `M0` stops and `M6` tool changes
  with the tool retracted above the stock top, the spindle stopped where the
  recipe asks and an operator comment before each, a single probed work zero
  (`G38.2` then `G10 L20 P1`, spindle off), rapids above the stock top,
  program bounds and keep-out regions.

Do not recompute what those checks own: cutting speeds and chip load,
deflection, vise or chuck holding, machine travel, pecking, gauge resolution
against a band, or posted depths and retract heights. A traveler sheet is not
proof that the gates ran for it, and a gate does not read the sheet: still
report any step the sheet prints that contradicts itself, the drawing or a
safe stop (for example a hands-in step at an `M0` the sheet does not say is
retracted with the spindle off), and show arithmetic from printed numbers
whenever claiming two printed values collide or fail to clean up. Adhesive
and tape bond strength is not gated; judge it under rule T3.

---

## Specification and prerequisites

### Rule T1 — Identity, stock and units

- The header prints the part title, drawing number and revision. When the
  companion part drawing is supplied, the drawing number and revision match its
  title block, and the traveler's material sits within the drawing's permitted
  material alternatives.
- Arriving stock is stated by material condition, form, nominal cross-section,
  blank cut size and lot quantity (and supplier/SKU where stock condition or
  geometry depends on it).
- The header states the traveler's default unit (`Inches unless mm`) and any
  job-wide machine state (such as a single spindle belt range or single-piece
  flow across setups).

### Rule T2 — Every drawing requirement is made and accepted

- Every manufactured feature on the part drawing (faces, profiles, holes,
  reams, threads, slots, grooves, chamfers, reliefs) is produced by an
  operation on the traveler, unless the drawing or traveler explicitly defers
  it to assembly or a joined parent part (`finished after joining its parent
  part`, `drilled at assembly`).
- **Inspect what matters, not every dimension on the print.** This is a hobby
  machining process, not aerospace part manufacture: a CNC program or fixed
  tooling already holds interpolated contours, routine clearance-hole pitches
  and `.X` / `.XX` non-critical features once setup registration and cutter
  size are verified. Require explicit per-piece checks only where scrap risk or
  fit demands them (tight fit bores/journals, press or sliding thicknesses,
  critical stack datums, incoming stock gates); cover CNC-interpolated shapes
  and routine geometry with **First article only** checks or a brief
  process-held statement (`Not gauged, the program's interpolated path: …`)
  paired with one registration check. Never demand 100% dimensional inspection
  of a 20-piece hobby lot (see rule T10 and rule T15).
- Every `SHARP`, `NO BURR`, local edge-break override and surface-finish
  requirement on the drawing is carried into the traveler's cutting and
  deburring operations, never rounded over by a blanket edge break.
- Traveler acceptance limits match the drawing's limits: never looser (rule
  T14) and never tighter as final acceptance (rule T15). Tighten an in-process
  target only when a later operation or stress release needs stock left on, and
  say so.

### Rule T3 — Fixtures, hardware and consumables are identified

- Every shop-made fixture, sub-plate, locating plug, soft jaw, arbor, template
  or gauge bar that a setup depends on is either:
  - standard shop equipment from T0, or
  - identified by its own drawing/fixture reference, or given enough setup/make
    dimensions on the sheet (or in a `Setup 0`) for the builder to make or
    verify the interface features the part's setups rely on (locating faces,
    pilot sizes, relief counterbores, clamp-nose and fence heights below the
    cut). Saying only "sub-plate (made beforehand)" when clearances, `G54`
    zeros and pilot fits depend on unprinted plate/plug geometry leaves the
    builder unable to build or verify the setup.
- Purchased workholding and hold-down hardware whose **envelope or height
  governs cutter clearance or clamping** is named specifically (the edge
  clamp's make, model and thread; the screw's thread, length and head type
  with its washer OD), not merely "edge clamps" or "washer and screw".
- Any adhesive, tape, wax, retaining compound or solvent whose bond strength,
  thickness or residue removal the route depends on is named by product,
  grade and critical thickness, just as rule 23 names a Loctite
  grade. Ordinary cutting oil needs no brand name unless a specific fluid is
  required.

### Rule T4 — Stock arrival and blank variation gates

- Cold-finished bar, extruded flat, tubing and sawn blanks vary in thickness,
  width and bow. Whenever a fixed-Z CNC program, fixed stop or preset pass
  assumes the arriving blank sits within a size window (so a thin blank would
  miss cleanup or a thick blank would overload the cutter or leave the part
  thick), an operation before the cut measures the blank, prints the acceptable
  range and states the stop action (`mic it, .nnn nominal, every reading
  .nnn–.nnn, else stop`). This incoming-stock gate is required even when the
  stock size is a REF or untoleranced size on the drawing; it is not the
  over-inspection rule T10 lists.
- Rough-sawn blank lengths and other supply sizes carry no tolerance band
  unless printed arithmetic shows that ordinary sawing variation (`±1/16 in`)
  breaks clamping, stop contact or stock cleanup in a later setup.

---

## Setups, zeros and operations

### Rule T5 — Workholding, seating and cutter clearance

- Every machining setup states **Holding**: what holds the work (vise jaws,
  parallels, sub-plate, chuck, collet, centres, tape, clamps, hold-down screw),
  which face seats down, which edge or end registers against which stop/fence,
  and any critical clamp stations or torque (where over-torquing bows a thin
  workpiece or crushes a tube).
- Every jaw, parallel, fence, stop, clamp nose, screw head or washer that a
  cutter passes over or beside stays clear of the lowest/closest cut: state the
  controlling height or clearance on the setup where tight, and verify hand-set
  clamp/stop heights during prove-out (rule T8).
- Mid-process holding changes (removing or inserting a locating plug so drills
  clear a relief, backing off edge clamps once a blank is taped so freed waste
  is not pinched into the cutter) are stated explicitly at the setup or op
  where they happen.
- Any adhesive, tape, wax, tab or onion-skin hold states a **release method**
  that does not bend, pry, nick or spring the finished part (`work a thin blade
  under it along its length; do not lever it up from one end`).

### Rule T6 — Work zero (`G54` / DRO) pick-up and persistence

- Every machining setup states **Datum**: each axis zero (`X0`, `Y0`, `Z0`) is
  placed on a real physical feature the builder can touch off, probe, indicate
  or edge-find (a faced fixture top, a milled fence or stop face, a vise fixed
  jaw, a faced bar end, a reamed bore axis — rule 10).
- On the CNC mill, the traveler makes clear how `Z0` ties to `M6` tool-length
  probing on the electronic tool setter, and when `G54` must be picked up or
  re-verified (once per vise/fixture installation, and after any fixture move,
  controller reset, stall or E-stop). Any tool too wide for the 20 mm tool
  setter pad (such as a large fly cutter) or that must never spin (`3D touch
  probe — SPINDLE OFF`) states its touch-off rule explicitly.
- Whenever a setup claims `G54 unchanged`, every intervening action must leave
  those physical zero surfaces undisturbed. If a tape layer, shim or flip shifts
  the work relative to `Z0`, state whether the NC program offsets for it (`Z0
  the plate top; the file works .011 above it for the tape stack`) or the operator
  re-zeros.
- On the manual lathe, state the `Z0` faced end for each chucking (rule 11) and
  keep diameter vs. radius convention unambiguous.

### Rule T7 — 3D orientation through flips and reseats

- Faces, ends and edges whose identity matters across operations are named when
  first established (`face 1, the first one roughed`) and tracked consistently
  through every flip, reseat, bond and deburr step.
- Every flip or reseat states **both** which face ends up on top (or down on
  the seat) **and** which edge/end seats against `X0` and `Y0`. Watch the
  geometry of "flip end for end" vs. "turn over": rotating a strip in its own
  plane swaps ends without changing which face is up; rolling it over front-to-back
  swaps faces *and* puts the opposite long edge against the fence; turning it
  over while swapping ends swaps faces *and* keeps the same long edge on the
  fence when symmetric, or mirrors asymmetric features. Say which face is up/down
  and which edge touches the fence so a first-time builder cannot load the blank
  wrong-face-up or mirror an asymmetric part.
- A broken face-tracking chain (for example, finishing `face 2` twice or
  putting the wrong face against the datum) is a blocker contradiction.

### Rule T8 — CNC program handoffs (`M0` / `M6`) and prove-out

- Every CNC operation names the program file it runs (`Pnn_rough_faces`, or
  `Same file` for subsequent sections of one multi-tool program).
- Because spindle RPM is set manually on the PM-30MV and CNCjs pauses at tool
  changes and stops, every `M6` and `M0` handoff states:
  - the tool number (`T1`, `T2`, …) and tool description (matching the Tools
    table), plus collet stickout range where clearance or flute reach requires
    it (`.nn–.nn out of the collet`);
  - the spindle speed to set by hand (`set nnnn`), cutting oil/air where used,
    and any special retract behavior worth knowing (`feeds in and out, spindle
    running: no rapid leaves the bore`);
  - every physical action the operator performs while stopped (mic thickness,
    unclamp, flip, reclamp) before pressing `Cycle Start`.
- Hands-in operator actions (measuring on the machine, unclamping, flipping,
  removing waste, wiping) happen **only** before `Cycle Start`, after program
  end, or at an explicit `M0`/`M6` stop.
- **First-run prove-out:** a CNC traveler states once (in the header or first
  CNC setup) that each program is proved before cutting metal on the first part
  (for example, single-block / air pass with `Z` offset above the work and a
  physical check that installed clamp/fence heights sit below the lowest cut).

### Rule T9 — Sequence and handling traps that code gates do not model

Parametric depth, clamp clearance, deflection and holding belong to
`prechips` and `cam:<stem>` as listed above, not to manual re-calculation
here. Focus sequence review on qualitative shop-floor traps in the written
steps:

- **Thin-bar distortion and stress release:** hogging one side of cold-finished
  bar bows thin parts; roughing both faces, releasing clamps to let stress
  relax, reseating, and taking light finish passes is good practice, whereas
  one-sided heavy removal on a thin strip without stress release or a
  straightening step is a defect when flatness or thickness governs.
- **Live clamping on parted waste and fragile release:** live side/edge clamps
  left engaged across a through-cut pinch freed waste into small end mills, and
  levering a thin taped part up from one end bends it; backing clamps off once
  bonded/screwed and working a thin blade along the length are valid
  protections, whereas prying or pinching freed pieces is a defect.
- **Unmodelled setup collisions or incomplete cuts visible in the text:** if
  two printed instructions directly contradict each other (for example, leaving
  a locating plug in a counterbore during the setup that drills through into
  that counterbore, or a printed drill/cut depth visibly shorter than the
  printed part thickness plus `0.3D` drill point when no relief is used), show
  the arithmetic from printed numbers. Work every ordinary configuration first;
  if any ordinary configuration works, there is no finding.
- **Deburring vs. datum seats and `SHARP` features:** sawn or milled burrs on a
  seating face/edge must come off before clamping on a precision datum, and
  final deburring must remove skin/tab witnesses while sparing any edge the
  drawing marks `SHARP`.

---

## Inspection, legibility and mode-specific work

### Rule T10 — Every check is doable, and travelers avoid over-inspection

This is a hobby shop making one machine (or a small 20-piece channel set), not
an aerospace supplier writing AS9102 inspection sheets. **Over-inspection is a
defect** (`over_specification`, rule T15) just as a broken check is:

- **Flag over-inspection:**
  - requiring per-piece inspection across a multi-piece lot (`quantity > 1`) on
    CNC-repeated contours, angles, `.X`/`.XX` profile features or routine hole
    locations that cannot drift independently once the setup and first article
    are proved (those belong at most under **First article only** or
    `Not gauged, the program's path`);
  - repeating the same measurement in multiple ops/setups without an
    intervening cut or stress release that could change it;
  - multi-step surface-plate / sine-bar / gauge-block metrology setups on loose
    title-block bands where calipers, a rule, a mating part or the CNC program
    itself suffices;
  - checking un-toleranced or reference `(REF)` dimensions as pass/fail final
    acceptance (a T4 incoming-stock gate and a labelled in-process target are
    not over-inspection).
- **Every kept check is doable as written:** each in-process or final check
  states **what** is measured, **from what reference and in what direction**
  (where slant vs. projected distance differs), **with which declared shop
  instrument**, and the **acceptance criterion** (numeric limits or plain
  functional check such as `lies flat on the surface plate without rocking`,
  `both edges sharp, no burr`).
- **Geometric measurability (caliper/gauge geometry):** verify with arithmetic
  that the named instrument's physical reading measures the toleranced
  quantity. Calipers spanning from a bore or centre to an elevated or angled
  corner measure **slant (point-to-point) distance**, not horizontal `X`
  projection from a centreline; when that slant shifts the reading across or
  outside the band on a nominal part, either print a workable route or gauge a
  directly measurable span (such as symmetric tip-to-tip length).
- **In-process gate remedies:** an in-process check happens while the part can
  still be saved or stopped before wasting downstream setups, and states a
  concrete fail action (`stop`, `scrap`, or how to re-skim — never a vague
  `goes back for a skim` on a fixed-Z file). Keep check and remedy distinct.

### Rule T11 — Instruments stay within the declared shop

- Inspections use only gauges and tools in T0. Requiring a CMM, optical
  comparator, air gauge, bore micrometer or small-hole gauge is a defect.
- Do not argue gauge resolution against a tolerance band when `prechips`
  `gauge_capability` owns it, EXCEPT when the prose names a transfer tool that
  contradicts how the check is physically read. A telescoping gauge read on a
  micrometer repeats to about `.0005 in`, so it does not accept a bore band of
  `.0005 in` or similar. Where the drawing prints no band on the bore, it is
  accepted with its mate (T0). Where the drawing still prints such a band,
  the traveler checks it with pin gauges where their `.001 in` step resolves
  the band, and otherwise with a named GO / NO-GO plug gauge pair, and the
  review summary reports the band as a drawing defect.
  Calipers on a `.001 in` band are the same defect.

### Rule T12 — Operations read cleanly at the machine

- Operations are numbered in execution order (`10, 20, …`). Each numbered op
  covers **one coherent action group** in **at most six printed lines** on the
  rendered sheet (count printed lines in the Work cell on `view_sheet`,
  excluding a separate **Check:** line). Split multi-stage preparation/bonding
  essays into separate numbered ops.
- Program sub-sections that run continuously inside one NC file without operator
  intervention (such as roughing, finishing and cutting through an outline in
  one `Pnn` run) should make clear they are stages of that running file rather
  than separate manual Cycle Starts.
- Follow the project's inch and shop notation (rule 26): no private slang, and
  avoid giving one word two conflicting meanings on the same sheet (for example,
  a Picture Key word that is also the part's own name).

### Rule T13 — Setup diagrams and printed layout

- Every setup on a hobby traveler carries a schematic diagram consistent with
  the Picture Key and the setup's Holding, Datum and Work text.
- Schematic simplification is expected (a single cutter-path arrow may stand for
  multi-pass facing; dimensions need not follow ASME Y14.5 projection rules).
  However:
  - every callout leader and dimension witness must land on the **actual feature
    and station** it names — never floating in blank air and never pointing to
    an off-centre station on a curved edge whose height there lies outside the
    stated centreline band;
  - Picture Key fills, hatches and labels must remain distinguishable in
    grayscale print and match how the setup diagrams use them (do not draw one
    kind of hardware in a fill whose legend names another);
  - clamps backed off or plugs removed in a setup must match the diagram;
  - no unresolved template tokens (`{{…}}`, `?`, `NaN`), clipped text, colliding
    labels or mid-row page splits may appear on the rendered PDF pages.

### Rule T14 — Cross-document consistency

Between the traveler and its companion part drawing (and across the traveler's
own header, diagrams, ops, settings column and inspection block), any two
statements that cannot both be obeyed are a **blocker contradiction** (rule 25):

- part number, revision, material or default unit disagreement;
- a printed size, tolerance band, hole diameter, station, count or `SHARP` /
  edge-break requirement that differs from the drawing;
- an op instruction whose RPM, feed, tool or Z height contradicts its own
  `Tool / settings` column or `Holding` / `Datum` header;
- a final check measured from a different datum or along a different direction
  than the drawing's where the geometric difference can pass bad parts or
  reject good ones.

### Rule T15 — Nothing extra (over-specification on travelers)

A hobby traveler is a practical setup sheet, **not** aerospace production
paperwork and **not** a second engineering drawing:

- **Welcome (not over-specification):** brief one-clause shop reasons that tell
  a novice *why* a step prevents scrap or crash (`the rough passes' stress is
  let go before the finish cuts`, `no rapid leaves the bore`, `a tight slot
  means a waste piece has moved`).
- **Over-specification and over-inspection (defect):**
  - **over-inspection (rule T10):** per-piece lot gauging of CNC-repeated
    `.X`/`.XX` features that first-article prove-out already locks in, duplicate
    checks with no intervening cut/release, or surface-plate metrology rituals
    on loose bands;
  - final inspection bands tighter than the part drawing's bands;
  - treating un-toleranced or `(REF)` features as pass/fail final acceptance
    rather than labelled in-process or diagnostic checks;
  - fixtures wildly disproportionate to a loose band;
  - multi-sentence design-history or physics essays inside an op row;
  - production QA paperwork (FAI / AS9102 forms, operator sign-off blocks, lot
    traceability, SPC/Cpk, calibration logs, PPE boilerplate).

### Rule T16 — Manual lathe setups

- State the chucking/collet, approximate stickout, and tailstock centre or
  steady-rest support; use a centre hole only when the drawing permits `CENTRES
  OK` or the centred end is later parted/faced off.
- Lengths run from the end faced in that chucking (rule 11), with DRO zero
  stated clearly; allow stock for parting and face the second end to overall
  length when held in a second chucking.
- Indicate a second chucking true only when coaxiality/runout across chuckings
  matters functionally, and only within "What the shop holds".
- Keep facing and parting tools on centre; check threads with a thread gauge or
  the mating part.

### Rule T17 — Saw, bench and manual secondary operations

- Sawing states cut length, stock orientation on the saw bed, and deburring
  before a blank seats against a precision plate, fence or vise jaw.
- Hand tapping names the tap drill (if not already drilled), guides the tap
  square (spindle tap guide or tapping block) when thread squareness matters,
  and states thread depth/acceptance.
- Manual filing, stoning or straightening on the surface plate states what
  surface/edge is worked, what edge stays `SHARP`, and the concrete flatness or
  dimensional recheck afterward.
- Operations performed *at assembly* (match-drilling, reaming in place, Loctite
  assembly bonding) belong in the assembly package, not as uncontextualized
  steps on a standalone part traveler.

---

## The sheet head and the route

### Rule T18 — The sheet head reads at a glance

The head of a traveler is everything printed between the stock line and the
Tools table on sheet 1. The builder reads it once before starting and comes
back to it at every stop (owner 2026-11-25: "first page traveler has wall of
text"). On the rendered sheet:

- **No prose block over 60 words.** A block is one paragraph, one list item
  or one table cell. Count the printed words on `view_sheet`; a block over 60
  is a finding, and so is a head printed as one paragraph holding several
  unrelated instructions, whatever its length.
- **Discrete, titled items, one idea each.** Instructions print as short
  items under a title or a row label (`This job`, `Switching on`, `Feed
  Hold`), never as a run of sentences on different subjects.
- **Safety-critical instructions are set apart and findable.** Collision
  avoidance (a stop, rod, clamp or plug to clear before a move or touch-off),
  re-zero and homing rules, Feed Hold / Reset and E-stop recovery each print
  as their own labelled item or row, and a rule particular to this job is in
  a block of its own (boxed, ruled or headed `STOP`), never mid-paragraph.
- **Standing shop rules are stated once, in the shop's words.** Rules that
  are the same on every mill sheet (units and `G21`, belt range, homing, the
  re-check of a zero, Feed Hold / Reset, prove-out, burrs off before a face
  seats) print as one shop-wide block. The head may not restate one of them
  in different words elsewhere, or give a different value or condition.
- **The head does not repeat a setup page.** A head sentence that only says
  again what a setup's Holding, Datum or op already prints (a T-number list
  the Tools table carries, a check or a mark an op makes) is a finding: cut
  it, or point to the setup. An overview the setups do not give in one place
  (which setups serve which part, program prefixes, where finished sizes are
  tabled) belongs in the head.

### Rule T19 — No wasted or repeated work in the route

The owner asks reviewers to be skeptical that setups are efficient (owner
2026-11-24: "ask agent to be skeptical if setups are efficient"). Walk the
route once in order and ask of every op: *does a later op undo or repeat
this?* and *could this be done once, later?* Report each hit with both op
numbers:

- **Wasted work:** a bench or finishing op (deburr, edge break, stone,
  polish, wash, finish coat) on a surface or edge that a later op cuts,
  faces or re-machines, so the later op removes what the earlier one did.
- **Duplicated hand work:** the same hand operation on the same feature in two
  setups with no reason printed for the first (deburring the same tap mouths
  twice, washing twice with no machining between).
- **Cleaning before more machining:** a wash, degrease or finish-prep step
  followed by further machining of the part before the finish it prepares for.
- **Repeated inspection:** a measurement repeated with nothing changed between
  (rule T10).

**Not wasted (never report):** an early op that a later cut, seat or check
depends on, even though a later op removes its surface: burrs filed off before
a face seats on parallels, a fixed jaw or a mate (rule T9); tap or drill exits
scraped flush and a no-rock seat check before a bolted pair is bored; a skim
that gives the next setup its datum; and **an orienting or identity mark** (a
part number such as F1 or K1, a face letter, a scribed end) that tells the
operator how to load the blank or which part it is, even when a later cut
removes it and a later op marks it again (owner 2026-11-25: marks on a face a
later cut removes are "Allowed"). If the printed sheet says why the first op
is needed, it is not duplicated.
A route that merely could be combined or reordered, with nothing
undone or repeated, is a non-gating `polish` note; do not propose a different
process for a route that works (rule T15).
