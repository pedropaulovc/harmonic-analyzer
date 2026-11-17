---
# Bump major_version when an edit should change traveler machinist-review
# verdicts; other edits do not re-run cached reviews.
major_version: 1
---
# Traveler guidelines (machinist review v2)

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
- **Bench and bore transfer:** a metal-cutting miter saw or bandsaw, files,
  abrasive rolls and stones, a bench vise with soft jaws, a spring-loaded
  spindle tap guide, telescoping gauges and small-hole gauges read on the
  `.0001 in` outside micrometers, feeler leaves, and torque wrenches / torque
  screwdriver.

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

Before a traveler reaches machinist review, automated build checks have already
verified:

- **CAD bindings (`{{cad.*}}`):** bound part limits, hole coordinates, Z cut
  levels and blank-fit envelopes come directly from the part's exported
  `features.toml`.
- **`prechips` physics and shop screens:** `stock_fit`, `cutting_speeds`
  (RPM/SFM and chip load), `milling_deflection`, `turning_deflection`,
  `tool_sizing` (nominal cutter/drill/reamer vs. band), `gauge_capability`
  (declared gauge resolution vs. band), `vise_holding` and `lathe_holding`,
  adhesive bond shear/tensile derating per piece and depth step,
  `machine_capacity` (axis travels, Z stack and tool stickout), `drill_pecking`
  and `indexing`.
- **Posted NC verification (`_gcode` / `cam:<stem>`):** posted toolpath depths
  and profiles against the STEP model, rapid-above-stock and plunge-feed
  safety, spindle-off retracts above stock before every `M0` and `M6`, and
  probe `G38.2` / `G10 L20 P1` sequences.

Do not re-derive cutting forces, chatter, deflection, bond stress, spindle
power, chip load or machine-envelope math to second-guess gated numbers. Flag
physics or clearance only when **arithmetic on printed numbers** shows a
collision, an uncut web, an impossible measurement, or a direct contradiction
between two printed statements.

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
  it to assembly or a joined parent part (`finished after joining MHA-CH-06`,
  `drilled at assembly`).
- Every toleranced requirement on the drawing has either:
  - a **printed check** naming the feature, reference, instrument (where not
    obvious) and acceptance limits matching the drawing, or
  - an explicit **process-held statement** (`Not gauged, the program's
    interpolated path: …`) for CNC-interpolated contours or angles, accompanied
    by at least one gauged registration/size check that proves the setup and
    cutter offset landed in band.
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
  governs cutter clearance or clamping** is named specifically (`Mitee-Bite
  Pitbull 26000 (4-40)`, `5/16-18 × 5/8 button-head screw` with washer OD), not
  merely "edge clamps" or "washer and screw".
- Any adhesive, tape, wax, retaining compound or solvent whose bond strength,
  thickness or residue removal the route depends on is named by product/grade
  and critical size (`3M VHB 5906, .006 in`), just as rule 23 names a Loctite
  grade. Ordinary cutting oil needs no brand name unless a specific fluid is
  required.

### Rule T4 — Stock arrival and blank variation gates

- Cold-finished bar, extruded flat, tubing and sawn blanks vary in thickness,
  width and bow. Whenever a fixed-Z CNC program, fixed stop or preset pass
  assumes the arriving blank sits within a size window (so a thin blank would
  miss cleanup or a thick blank would overload the cutter or leave the part
  thick), an operation before the cut measures the blank, prints the acceptable
  range and states the stop action (`mic it, .125 nominal, every reading
  .122–.126, else stop`).
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
  the plate top; the file works .006 above it for the tape`) or the operator
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

- Every CNC operation names the program file it runs (`RS01_rough_faces`, or
  `Same file` for subsequent sections of one multi-tool program).
- Because spindle RPM is set manually on the PM-30MV and CNCjs pauses at tool
  changes and stops, every `M6` and `M0` handoff states:
  - the tool number (`T1`, `T2`, …) and tool description (matching the Tools
    table), plus collet stickout range where clearance or flute reach requires
    it (`.47–.50 out of the collet`);
  - the spindle speed to set by hand (`set 2650`), cutting oil/air where used,
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

### Rule T9 — Sequence physics: drill points, skins, stress and burrs

Judge the physical sequence for traps that scrap parts or break cutters:

- **Drill and reamer point length:** a twist drill's `118°` point adds `≈ 0.3D`
  past full diameter (and a reamer has its chamfer lead). Through-holes and
  chain-drilled reliefs must put the **full diameter** past the finished plane
  or part underside into a stated relief/counterbore without bottoming on the
  fixture floor or parallels.
- **Stress release on thin cold-finished stock:** removing stock heavily from
  one side of cold-finished bar bows thin parts. Roughing both faces, releasing
  clamps to let internal stress relax, reseating, and taking light finish passes
  (followed by surface-plate check/straightening after release if needed) is
  good shop practice; hogging one side to final size on a thin strip without
  relief is a defect when flatness or thickness depends on it.
- **Slivers, skins and waste pinch:** thin waste strips trapped against a fence,
  or loose waste pushed by live edge clamps once an outline cuts through, snap
  small carbide end mills. Milling thin slivers away first, leaving an onion
  skin until the wall is finished, and backing off side clamps on a taped
  through-cut are valid protections; cutting free a loose piece under live side
  clamping or cutting deeper than the tape into a precision sub-plate (unless a
  sacrificial spoilboard is intended) is a defect.
- **Deburring before datum seating and preserving sharp features:** sawn or
  milled burrs on an edge or face that seats on a precision plate/fence must be
  deburred before clamping; final deburring must remove any onion-skin or tab
  witness without undercutting a finished band and must explicitly spare edges
  marked `SHARP`.

**Arithmetic requirement:** every claim that a tool collides, fails to clean
up, leaves an uncut web, bottoms out, or cuts into a fixture must show its
arithmetic from printed numbers on the traveler or drawing. Work every ordinary
configuration first; if any ordinary configuration works, there is no finding.

---

## Inspection, legibility and mode-specific work

### Rule T10 — Every check can be done as written

- Every in-process or final check states **what** is measured, **from what
  reference and in what direction** (where geometry makes point-to-point vs.
  projected distance differ), **with which declared shop instrument**, and the
  **acceptance criterion** (numeric limits or a concrete functional check such
  as `lies flat on the surface plate without rocking`, `both edges sharp, no
  burr`).
- **Geometric measurability (caliper/gauge geometry):** verify with arithmetic
  that the named instrument's physical reading measures the toleranced
  quantity! In particular, calipers spanning from a bore or centre to an
  elevated or angled corner measure **slant (point-to-point) distance** (plus or
  minus half the bore diameter unless zeroed via a gauge pin), NOT horizontal
  `X` projection from a centreline. When slant vs. projected geometry shifts
  the reading by a meaningful fraction of (or more than) the tolerance band,
  asking the builder to read the projected drawing band directly with calipers
  will reject a nominal part; the traveler must either print a workable surface-plate
  / pin / height-gauge route or inspect a directly measurable span (such as
  symmetric tip-to-tip chord).
- **In-process gate remedies:** an in-process check happens while the part can
  still be saved or stopped before wasting downstream setups. It states what to
  do if out of band (`stop`, `scrap`, or a concrete rework action naming which
  setup/offset/pass skims it — never a vague "goes back for a skim" when the
  program cuts at a fixed Z). A check and its remedy are distinct sentences or
  sub-steps.
- **Lot frequency:** on multi-piece lots (`quantity > 1`), distinguish
  **First article only** checks (such as slot-pin waste-shift checks or pre/post
  unclamping spring checks) from per-blank gates and final acceptance.

### Rule T11 — Instruments stay within the declared shop

- Inspections use only gauges and tools in T0. Requiring a CMM, optical
  comparator, air gauge or unowned bore micrometer is a defect.
- Do not argue gauge resolution against a tolerance band when `prechips`
  `gauge_capability` owns it, EXCEPT when the prose names a transfer tool (such
  as telescoping gauges + micrometer, or calipers on a `.001` band) that
  contradicts how the check is physically read — note that `.0001 in`
  micrometers reading a telescoping gauge **is** this shop's accepted method for
  a `.0005 in` reamed bore when `.001 in`-step pin gauges are too coarse.

### Rule T12 — Operations read cleanly at the machine

- Operations are numbered in execution order (`10, 20, …`). Each numbered op
  covers **one coherent action group** in **at most six printed lines** on the
  rendered sheet (count printed lines in the Work cell on `view_sheet`,
  excluding a separate **Check:** line). Split multi-stage preparation/bonding
  essays into separate numbered ops.
- Program sub-sections that run continuously inside one NC file without operator
  intervention (such as roughing, finishing and cutting through an outline in
  one `RS04` run) should make clear they are stages of that running file rather
  than separate manual Cycle Starts.
- Follow the project's inch and shop notation (rule 26): no private slang, and
  avoid giving one word two conflicting meanings on the same sheet (for example,
  using `strap` in the Picture Key for a strap clamp on a traveler whose part
  is itself named `Rocker strap`).

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
    grayscale print and match how the setup diagrams use them (do not draw
    screw/washer hardware in a clamp fill whose legend calls it a strap);
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
- **Over-specification (defect):**
  - final inspection bands tighter than the part drawing's bands;
  - treating un-toleranced/reference features as pass/fail final acceptance
    rather than labelled in-process or diagnostic checks;
  - fixtures or inspection setups wildly disproportionate to a loose band;
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
