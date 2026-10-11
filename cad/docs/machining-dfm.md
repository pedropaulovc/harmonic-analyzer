# Machining DFM — per-part manufacturability pass (Tier-1)

> Companion to [`tolerance-gdt-assessment.md`](./tolerance-gdt-assessment.md). That doc's §6 tiers
> the parts by **tolerance/fit/GD&T** effort; this one is the **machinability** layer for the same
> Tier-1 parts — *can the machinist actually cut this, in what stock, in how many setups, and where
> will it fight back.* Generic DFM checklists ("radius internal corners", "minimize setups") are
> useless as bare bullets; every row below is attached to a **named feature with a real number** from
> the build script. Audience + toolchain per §1/§11: period **brass + steel**, **manual mill + lathe
> primary (fidelity)**, **PM-30MV CNC for the repeat parts**, Fusion 360 CAM off the STEP export.

All numbers are from the `cad/scripts/build_*.py` sources (mm). Where a part is modeled as a
**casting** but you intend to cut it from bar, that is a *substitution* — flagged, because the
geometry is casting-shaped, not milling-shaped.

## The headlines (read these first)

- **Three parts carry the whole risk. Everything else is generous.**
  1. **`dt-cone-gear` T006** — minimum root-to-bore web **0.64 mm** on a **Ø4.31 mm OD gear with a 1/32 in (Ø0.794 mm) bore**.
     The terminal journal was cut to 1/32 in so the 48DP PA20 gap floor keeps at least the 0.62 mm
     web floor, the one named web exception ([`gear-standard.md`](./gear-standard.md#what-it-costs)).
     The single hardest part in the machine. These teeth are cut as involute flanks closed by a gap
     floor printed as a MIN diameter; T006's floor, cut by DT6-FORM1, is Ø2.136 MIN / Ø2.201 MAX. After a forced T006
     rebuild, `build_dt_cone_gear.py` measures the native floor edges and requires them at the printed
     MIN radius within 0.002 mm. T012 shares the 1/32 in terminal and its web is 2.02 mm at the worst
     case, over the 2.0 target; the T018 and T024 webs meet the target on the S1 bores.
     Period mitigation: the tip gears were a harder yellow metal.
  2. **`sm-summing-lever` knife edge** — the sharp top-vertex ridge of a hex trunnion that protrudes
     **21.717 mm unsupported** past each end of a casting-shaped organic lever. Delicate (nicks/rounds)
     *and* fixturing-hostile from bar. Per §6 the edge should be a **separate hardened tool-steel
     insert**, not this parent — which also removes it from this part's machining hazard.
  3. **`dt-cone-gear-shaft` tip** — a **Ø0.79375 mm (1/32 in) terminal land, about 33.6 mm long in steel (L/D 42)**,
     carrying the T012/T006 seats and the MHA-VN-016 stack collar, its cup tip seated in the MHA-VN-017 adjuster.
     Support the slender work with a follower/steady and take a light finishing cut;
     the terminal D-flat continues from the T018 step through the shaft tip.
     Break the two long torque corners of the terminal flat no more than 0.02 mm; the 0.420 AF
     already pays for that break. The model leaves these corners sharp and the sheet prints the break
     as a callout, `TORQUE CORNERS: STONE BURR ONLY, 0.02 MAX`, because it is below the title block's
     R0.25 edge break. The stepped collar (Ø17.05 body, Ø6.40 × 3.5 nose, 11.5 overall) has a
     finished bore of Ø0.849 ±0.030. Its set screw's ground dog prints the same way:
     `DOG EDGE: STONE BURR ONLY, 0.02 MAX`. To fit the collar, hold the gear stack south on the shaft's thrust collar,
     set the original 0.45 ±0.10 feeler off the T006 thrust face, seat both collar bore ends on the
     round back of the terminal, snug the ground dog wholly on the unbroken flat, then remove the feeler.
     Never run or swing a loose collar. The post and stack setup steps are listed in
     `dt_tip_collar_air.installation_requirements()`.

- **The CNC repeat families (make N identical on the PM-30MV — this is where CNC earns its keep):**
  | family | qty | why CNC |
  |---|---|---|
  | `dt-cylinder-gear` (+ integral cam) | 20 | 120 teeth + eccentric cam + 0.4 mm index notch, all co-phased +Y — hand-repeating 20× scatters the phase |
  | `dt-cone-gear` | 20 | involute teeth cut with stock 48DP PA20 range cutters indexed on a dividing head; T006 alone needs a special cutter (see [Cutter plan](#cutter-plan)); wire-EDM = outsource alt |
  | `pivot-bushing` / `lever-bushing` | 19 each | turned spacers whose **length** sets channel pitch — length consistency across the set is the point |
  | `ch-rocker-arm` | 20 | flat R800 profile, one setup — ideal CNC profile part |
  | `ch-connecting-rod` | 20 | flat 2D outline from 1018 plate, stepped both faces, slotted fork → 2.5D |
  | `sm-knife-mount` | 2 | trivial prismatic block, 2 identical |

- **Casting-vs-bar substitution (2 T1 parts are castings in the registry):** `sm-summing-lever` and
  `fr-rocker-arm-support` carry `material: Gray Cast Iron` in `cad/config/parts/*.yaml`
  (`ch-connecting-rod` is now 1018 plate, Main ruling 2026-10). The support is a **benign**
  substitution — it cuts fine from bar. The **lever is
  not** — its ribbed/leaf organic form is casting-native and hogging it from solid means 4–5 setups
  around cantilevered plates. Decide **cast, fabricate (weld/silver-solder up from simple stock), or
  accept the multi-setup hog** before you start; the support is just a stock choice, the lever is a
  real decision.
  - **`sm-knife-mount` is a material *conflict*, not a settled casting:** its registry
    (`parts/sm-knife-mount.yaml`) and assessment §6 say **Brass**, but `build_sm_knife_mount.py` hardcodes
    `MATERIAL = "Gray Cast Iron"`. The registry value is what stamps the BOM/drawing custom property, so
    the intended stock is a **brass bar block** (trivial) — the script constant looks stale. Reconcile
    before it reaches a drawing (gap below).

- `fr-rocker-arm-support` carries four **5/16 through clearance drills**. Four
  McMaster 92240A540 1/4-20 UNC-2A × 3/4 in hex-head screws install from the
  top into blind UNC-2B taps in `fr-harmonic-base`: the exact vendor under-head
  washer transition seats on the support, leaving 12.422 mm installed
  engagement (1.956D). The seat is sized at its printed .XX worst case:
  13.20 mm full thread (0.25 mm tip reserve at the low limit) and 20.60 mm
  cylindrical tap-drill depth (five 1.27 mm pitches past the thread).
  Other receivers are threaded too; the `sm-knife-mount` #6-32 bottoming hanger-screw tap is one
  example. The 20 `dt-cone-gear`s and the 64T `dt-crank-drive-gear` transmit torque
  through matching D-bores on the shaft's D-flat lands; the cylinder gears
  ride free on their stationary arbor. The gears seat against each other,
  without an adhesive joint or spacers, from the collar-supported 64T to T006.

### Blind-thread DFM rule

Applied from the [thread-depth DFM walkthrough](https://www.youtube.com/watch?v=c1o3ZQY25jI)
(12:30–21:30):

- Specify the **installed engagement**, **usable full-thread depth**, and
  deeper **tap-drill depth** separately. Screw projection through a clearance
  part is not engagement, and a modeled tap-minor cylinder is not full thread.
- Ordinary steel/iron joints rarely need more than 2–3 diameters of engagement;
  1.5D is adequate here. More thread adds tapping risk without adding useful
  clamp capacity.
- A machine plug tap needs four chamfered lead threads plus one pitch of
  margin beyond the usable full threads. A bottoming tap reduces that allowance
  to one or two pitches; use it only when the design actually needs threads
  near the bottom.
- Model the tap-minor diameter, then check the **major-diameter envelope**
  against outer walls and neighboring cavities. The drill fitting does not
  prove the finished thread avoids breakout.
- About 3D is the practical machine-tapping depth ceiling. If a design demands
  full thread substantially beyond that, redesign the joint or thread-mill it
  instead of encoding an optimistic tap callout.

---

## Per-part rows

### Summing lever & knife edge (T1 — least forgiving interface)

| part | stock / form | key features | machinability hazards | setups | route |
|---|---|---|---|---|---|
| **`sm-summing-lever`** | modeled **Gray Cast Iron casting**; organic first-class lever ~120×28×196 | solid pivot cylinder Ø25.4×152.4 (**no bore**); 2× hex knife trunnions (edges = top-vertex ridges) protruding 21.717 each end; 20× #6-32 tapped anchor seats through the 5.08 plate @ 7.0565 pitch (web ~5.06, Ø2.705 tap drill); one #10-24 tap through the Ø19.05×19.05 summation-anchor boss — both purchased spring anchors thread straight in, no nuts | knife-edge ridge **delicate** (the precision line); trunnion slender cantilever → **chatter**; organic 3-pt-arc leaf/rib profiles hard to mill; turning Ø25.4 with cantilevered plates; 20 small through-taps in a 5.08 web → **tap breakage**, use a tapping head | **4–5 from bar** (2 sketch planes + turn) | **CAST or fabricate**, don't hog; knife edge → hardened insert (§6) |
| **`sm-knife-mount`** | rectangular block 24.0×29.6×14.0 at .X (bar/plate); **2 identical** | Ø12.00 +0.03/0 reamed through bore (bearing bore for the trunnion), centre 20.616 BASIC below the top face (`BORE_CY` −5.75 from the knife-edge origin, block top +14.866, clamped to the casting underside); #6-32 UNC-2B bottoming tap in the block top on the bore axis (hanger-screw seat: drill #36 Ø2.705 ×11.20 ±0.47, full thread 9.42 at the general .XX, the drill ≥0.80 past the thread; worst-case 2.02 web over the bore crown, no break-in); 2× Ø3.175 reamed dowel press holes ×9.5 in the block top at ±6.350 from the tap axis (span 12.700 BASIC, the pair ⌖Ø0.13 to the top seat as datum pattern B, the +X hole 5.65 from the +X face and the row 7.0 from the front face; tap ⌖Ø0.10 to the top seat and the pair); walls 3.0 under bore, 6.0 flanks | watch **bore breakout on the 3 mm floor**; hold the #36 drill to 11.20 ±0.47 (the 2.02 worst-case web over the bore crown); otherwise trivial | 1–2 (square block, bore one axis) | **CNC-REPEAT** (×2) or trivial manual. Clamped to the underside of the top-frame casting's integral crossbar (the former separate top-crossbar part is merged into the top-frame) by a #6-32 × 1-1/2 socket head cap screw (MHA-VN-024, McMaster 91251A157) dropped through a Ø7.0 ×6.5 counterbore + Ø4.318 #6 clearance (floor 30.0 above the crossbar underside), 8.10 nominal engagement (6.28..8.90), set with removable medium-strength threadlocker; the two pressed MHA-VN-051 dowels (98381A473, 1/8 × 3/4) slip into a Ø3.24 ±0.03 ×12.0 blind hole and a 3.24 ±0.03 × 4.30 ×12.0 blind slot (reamed width, BASIC 12.700 from and ⌖0.05 to the round hole) in the crossbar underside and key the block against turning |

### Cylinder gear + cam, connecting rod (T1 — the 20 function generators)

| part | stock / form | key features | machinability hazards | setups | route |
|---|---|---|---|---|---|
| **`dt-cylinder-gear`** ×20 | round brass bar ~65; toothed disc OD64.44×3 + integral eccentric cam OD30.6×4.0565 (offset +Y 8.64); total H 7.0565 | Ø9.575 through bore on the Ø9.525 (3/8") arbor — **rides free on arbor, no keyway**; 120T involute 48DP PA20 (2.5D through-cut, patterned → **DXF/2.5D-machinable**); cam = plain eccentric circle (2.5D); **0.4 mm alignment notch** = the +Y co-phased timing datum | cam thin-side wall **1.90 mm**; notch kerf **0.4 mm** (slitting-saw, fragile crests); 3 mm slender disc; **double-sided** (teeth+notch front / cam boss far face) | **≥2** (flip for cam boss) | **CNC-REPEAT** — lathe bore+OD, teeth with a stock 48DP PA20 #2 cutter indexed (see [Cutter plan](#cutter-plan); wire-EDM = outsource), cam offset, notch by slitting saw; **hold the +Y phasing identical on all 20** |
| **`ch-connecting-rod`** ×20 | AISI 1018 plate, 1/4" (6.35) faced to 6.075; 2D outline ~188×40.8; ring and shank 2.200 ±0.127 (symmetric to the fork slot within 0.10) and fork 6.075 ±0.05 all on one mid-plane; black finish | Ø30.8 strap bore (rides Ø30.6 cam, 0.1/side); fork 10 wide, full R5 crown on the pin, 18 long from the crown; slot 2.625 +0.127/0, 14.75 deep from the crown, centred (tines equal within 0.10); Ø1.968 +0.010/0 pin hole reamed through both tines (pin MHA-CH-010 pressed in at assembly, ends dressed flush; user ruling 2026-10-09, PR #1292) | tines **1.725** (1.59 MIN) beside a 2.625 slot — slitting saw or a 3/32 end mill in two passes, hold the 3-place band; both faces stepped (thin 2.200 shank ~150 long faced from 6.35 — chatter/curl); the ream must hold +0.010/0 for the press | **2** (flip to face the second side; slot, drill and ream in the second) | **DXF/2.5D profile** the outline, face both sides to the two levels, slit the fork, drill + ream |

### Cone gears + shaft (T1 — the 48DP PA20 train, tip gears fragile)

| part | stock / form | key features | machinability hazards | setups | route |
|---|---|---|---|---|---|
| **`dt-cone-gear`** ×20 (T006→T120) | round brass bar, extruded disc, face **6.8756 ±0.025** each, OD printed per gear at the AGMA (N + 2)/DP blank, +0/−0.05, capped by the cutter's form (`dt_cone_gear_spec.py`; T006 Ø4.31 +0/−0.02); tip gears T006–T024 harder yellow metal | D-bore matching the land's single +X flat, clocked to the phase-0 tooth: round seat Ø by config (T006/T012 0.79375, T018 3.175, T024 6.350, T030+ 9.525); bore AF +0.010/+0.020 over shaft nominal AF (0.01–0.03 clearance), diametral slip clearance 0.025–0.105; 6–120 involute teeth PA20, tooth thickness ±0.075 (T006 +0/−0.04), 2.5D through-cut | **T006 web 0.64 mm minimum** on the 1/32 in bore (the flat cuts inward from that circle; see [`gear-standard.md`](./gear-standard.md#what-it-costs)); whole gear tiny → difficult workholding, especially forming and gauging the D without damaging the teeth | ≥2 (turn/bore, indexed teeth, plus D-bore finishing) | stock 48DP PA20 range cutter per gear, **indexed**, set up within 0.05 TIR of the finished bore (see [Cutter plan](#cutter-plan)); T006 needs its named custom ground tool, DT6-FORM1; form the bore flat to the AF gauge (filing or broaching is a hobby-shop possibility, not a selected route; EDM or a D-shaped punch needs process/fixture approval). Measure all 20 touching faces as a stack: **137.512 ±0.20** |
| **`dt-cone-gear-shaft`** ×1 | stepped steel bar; integral Ø12.2308 post journal, thrust collar then Ø9.525→6.35→3.175→0.79375 gear lands | turned steps plus **one milled +X D-flat on each gear land**, nominal AF **8.763/5.842/2.921/0.420** respectively, each +0/−0.010; the Ø0.79375 flat continues through the tip end and the MHA-VN-016 stack collar's set screw locks on it. Finish the post journal for 0.05 diametral clearance | slender terminal land needs tailstock support; flat machining adds an indexed milling setup and inspection against the mating D-bores | lathe + at least 1 indexed milling setup | manual lathe **+ steady/follower**, then mill/gauge the co-clocked flats; do not leave a round section under the MHA-VN-016 collar |

### Pivots, bushings, shafts (T1 — the 19-channel stacks)

| part | stock / form | key features | machinability hazards | setups | route |
|---|---|---|---|---|---|
| **`ch-pivot-shaft`** ×1 | plain steel bar Ø6.35×203.2 | solid, no bore/step/thread; 2 end faces | **L/D 32:1** → whip; steady-rest / between-centers | 1 | manual lathe + steady |
| **`ch-fulcrum-shaft`** ×1 | plain steel bar Ø6.35×182 | as pivot-shaft, only shorter | **L/D 29:1** → whip; **same stock as pivot-shaft — don't mix** | 1 | manual lathe + steady |
| **`pivot-bushing`** ×19 | brass, OD Ø10.0×**4.5565** | Ø6.5 through bore (rides Ø6.35, **0.15 mm** clr); stubby L/D 0.46 | **length 4.5565 sets the 7.0565 channel pitch** → parting-length repeatability across all 19 is *the* critical dim | 1 (turn + bore + part) | **CNC-REPEAT** / collet stop for length consistency |
| **`lever-bushing`** ×19 | brass, OD Ø12.0×**4.0565** | Ø6.5 through bore (rides Ø6.35, 0.15 mm clr); twin of pivot-bushing | same drill/ream as pivot-bushing; differs only OD (12 vs 10) + length (4.0565 vs 4.5565) — **don't mix the two sets** | 1 | **CNC-REPEAT** / collet stop |

### Rocker arms + support (T1 — flat profile + cast bracket)

| part | stock / form | key features | machinability hazards | setups | route |
|---|---|---|---|---|---|
| **`ch-rocker-arm`** ×20 | flat steel plate **2.5 mm** thick, ~270×21 | **top edge = R800 concave arc** (the amplitude-bar rides ON it) — it is the **2D OUTLINE of the plate, NOT a concave pocket/face**; bottom edge R816 concentric; Ø6.5 pivot bore + Ø2.0 rod-pin bore, both through the plate | none severe — pivot bore is **inherently square** (drilled through flat stock, one setup); no slot, no internal corner | **1** (all features one plane) | **CNC 2.5D profile** (×20 identical) or bandsaw+template; the R800 is profiled, not form-cut |
| **`fr-rocker-arm-support`** | modeled Gray Cast Iron; drawing permits gray iron casting or low-carbon steel stock; trapezoidal wedge, 6.35 mm shell/web | opposed 165.1 mm pockets with **R6.35** internal corners; through cavity with **R12.7** corners; **4× 5/16 through clearance drills** in the 6.35 mm foot for top-down 1/4-20 hex-head screws; RimChamfer 1.27 | 6.35 mm web/shell; from solid stock, each pocket reaches about 28.6 mm at the wide foot. R6.35 is ordinary contour geometry on a PM-25MV and does not need square-corner EDM; a 1/8″ end mill can finish the radius, but its long reach in 1018 favors roughing with a stiffer cutter first | casting route: foot holes/rim; solid-stock route: **2 opposed pocket setups** + foot drilling | cast body, or rough both pockets from 1018 with a larger cutter and finish the R6.35 corners with a 1/8″ end mill; drill the clearance pattern from the seat face |

---

## Recommended actions (gaps this pass surfaced)

1. **Retain the executable native wall guard for the smallest cone gear.** After a forced T006
   rebuild, `build_dt_cone_gear.py` measures the native floor edges directly, requires the printed MIN
   floor radius (`dt_cone_gear_spec.floor_radius_min_mm`) within 0.002 mm and at least one floor edge per
   tooth, and rejects a non-positive web at the maximum allowed bore; `test_dt_cone_gear_drawing` pins
   the T006 web exception (`WEB_EXCEPTIONS_MM`). Keep both when changing the tooth profile or bore bands.
2. **Decide the `sm-summing-lever` fabrication method** (cast / fabricate / hog) and the **knife-edge
   insert** now — it drives whether this is a 5-setup nightmare or two simple operations, and it is the
   critical interface.
3. ~~**Model the `sm-knife-mount` mounting holes**~~ — RESOLVED (top-frame rederive, 2026-08-02; #6-32 redesign, 2026-10): the
   block is clamped to the top-frame casting's integral crossbar by a #6-32 socket head cap screw threaded
   into a bottoming tap in the block top and keyed by two pressed dowels; the screw, dowels and all their holes are modeled.
4. **Reconcile the `ch-rocker-arm` R800 vs book 812.8 mm** (already a §4 Finding) before it becomes a
   drawing callout — but note the good news from this pass: it's a *profile* dimension, cheap to change.
5. **Consider enlarging the tip cone gears** (T006–T012) — the model already flags them marginal and a
   period build used harder metal. **DP caveat:** enlarging OD at a *fixed tooth count* changes the
   DP/module and **breaks the shared 48DP mesh** — tooth *counts* preserve the ratio, but DP/pitch
   diameter preserves the *mesh* (`dt_cone_gear_spec.py` and `dt_cylinder_gear_spec.py` both read `diametral_pitch` from `gear_train.yaml`; §4
   treats the shared DP/PA as the meshing-domain constraint). So a real enlargement must either re-cut
   the mating **cylinder gear + centre distance** to the same new DP for that pair, or keep DP and accept
   the small size. Not the free change it first looks — the cheaper de-risk is the **harder tip metal**
   the original used.
6. **Reconcile the `sm-knife-mount` material** — `build_sm_knife_mount.py` (`Gray Cast Iron`) contradicts
   `parts/sm-knife-mount.yaml` + §6 (`Brass`); the registry drives the BOM/drawing, so fix the script
   constant to Brass (or decide the part is cast) before a drawing ships a wrong material.

> These are machinability flags, not tolerance rules — the fits/finish/GD&T for the same parts live in
> [`tolerance-gdt-assessment.md`](./tolerance-gdt-assessment.md) §6, and the drawing/CAM outputs that
> carry them to the bench in §11. Those drawings now carry the **full** GD&T vocabulary (runout,
> position, profile, perpendicularity — ASME Y14.5-2018), not a runout-only "lite" subset. The DFM
> consequence: **each geometric callout is itself a machinability + inspection cost** — a tight
> runout or profile constrains the process (form-cut, single-setup, mandrel) and adds an inspection
> step — so a frame is spent only where the error model rewards it (the knife edge, the 20 cams,
> channel consistency), exactly the parts flagged T1 above. Over-calling GD&T is the same trap as
> over-tolerancing: it limits the process and inflates inspection for no functional gain.

## How to get this reviewed (strategy — for future reference)

Nobody reviews a 100+-part reproduction for free, and none should. **Don't review the machine —
review the risk:** the ~10 T1 parts above plus a few go/no-go questions, spread across cheap targeted
steps instead of one big engagement.

**The automated-DFM ladder — necessary, not sufficient, and each tool is blind in a different place:**

- **DFMPro (SW add-in) and Xometry auto-DFM — false-green here (observed).** Both passed *every* SLDPRT
  — yet the model is full of sharp internal corners (every gear-tooth root, the cam notch) a round tool
  cannot cut, plus the thin T006 **root-to-bore web** (0.621 mm in the model they checked). Their rule sets are tuned for
  moulding / sheet / generic 3-axis and don't flag manual-machining hazards. **A green from these
  means little — trust it for nothing on the corners or walls.**
- **Fusion 360 CAM verify/simulate — the one worth banking on, with a known edge.** Because it
  simulates the *actual tool against the actual solid*, it **surfaces the class DFMPro missed**: an
  internal corner smaller than the smallest endmill shows up as **un-cut stock** (you can't program a
  sharp internal corner), and tool-reach / gouge / holder-collision are caught. Banking on Fusion for
  the **majority of tool-access & gouge issues is reasonable** — it's a real simulation, not a
  rule-of-thumb checker.
  - **But its blind spot is exactly where the worst risk lives.** Fusion treats geometry as **rigid**
  and stock as **held**, so it will *not* warn that the **T006 web (0.64 mm minimum)** breaks in
  workholding, the **Ø0.79375 mm slender shaft tip** whips, the **1.90 mm cam wall** is fragile, or that
  a ~4 mm gear can't be gripped. Thin-wall / fragile-feature / fixturing failures are not modelled
  by CAM sim. **A clean Fusion sim is not a substitute for a first cut on the fragile parts.**

**Order that actually de-risks the build:**
1. **Fusion CAM verify** — cheap; catches the tool-access/gouge/reach majority, incl. the sharp corners
   (as uncut stock).
2. **First-article cut** — cut **one** of each fragile/hard part (a T006 gear, a cam-gear, a bushing,
   the thin shaft) and inspect **before** committing to 20×. The only check that catches
   thin-wall/workholding — precisely Fusion's blind spot.
3. Narrow paid consults / outsource-quotes only for whatever 1–2 leave open.

**Inspecting the geometric callouts (what the first-article cut actually measures).** The full-GD&T
frames map to concrete shop checks — this is part of the per-part inspection cost above, not free:
**runout** (gears, cams, journals, wheel) → mandrel + dial gauge rotated per cross-section (a
workflow the audience already knows as "indicating"); **flatness / straightness** (mount seats,
shaft axes) → dial-indicator sweep on jacks / Vee-blocks; **position** of the hole patterns (support
feet, the 20 spring holes) and **profile** (the R800 rocker, cam eccentric, gear-tooth flanks) →
CMM against the basic-dimension grid / nominal curve, since a hand gauge can't hold a profile; any
**angularity** → sine bar. The profile and position checks on the fragile T1 parts are where a CMM
(or an outsourced inspection) earns its keep — budget for it rather than assuming calipers suffice.

**Go/no-go — gear cutters: RESOLVED (stock cutters, one special).** The train moved from the
measured-photo pitch DP 49.82 to standard 48DP PA20 so that stock involute cutters cover every gear
except the T006 cone ([`gear-standard.md`](./gear-standard.md)). The per-part plan is below;
wire-EDM and hobbing stay outsource alternates.

## Cutter plan

Every cut gear uses a stock involute form cutter from the eight-cutter set for its pitch,
indexed on the dividing head, except the T006 cone. Three sets cover the machine: 48DP (cones,
cylinder gears, alignment drum and paper reducer), 24DP (crank pair) and 32DP (feed pinion); the
rack is bought. The cutter numbers follow the Brown & Sharpe
ranges (#1 135 teeth to a rack, #2 55–134, #3 35–54, #4 26–34, #5 21–25, #6 17–20, #7 14–16,
#8 12–13), which date to the period catalogues
([Brown & Sharpe 1904](https://archive.org/details/BrownAndSharpeMachineryAndTools1904Catalogue))
and are still sold today ([C.R.Tools](https://crtoolsuk.com/product/diametrical-pitch-involute-gear-cutters/),
[Newman Tools chart](https://www.newmantools.com/cutters/gear.htm)). Module cutters number the
same ranges in reverse, so order by DP.

Indexing assumes a 40:1 head, the ratio of the shop's Precision Matthews BS-0, so one tooth is
40/N crank turns. The hole circles are the standard Brown & Sharpe plates (15, 16, 17, 18, 19,
20, 21, 23, 27, 29, 31, 33, 37, 39, 41, 43, 47, 49), from
`references/machinerys-handbook/` (printed p. 2008, which also covers differential indexing). The BS-0's own
plates have not been checked against this list; check yours before cutting.

### Cone and cylinder train, 48DP PA20

| part | teeth | cutter | index per tooth (40:1) |
|---|--:|:--:|---|
| `dt-cone-gear` T006 | 6 | special, see below | 6 turns + 10 holes on 15 |
| `dt-cone-gear` T012 | 12 | #8 | 3 turns + 5 on 15 |
| `dt-cone-gear` T018 | 18 | #6 | 2 turns + 4 on 18 |
| `dt-cone-gear` T024 | 24 | #5 | 1 turn + 10 on 15 |
| `dt-cone-gear` T030 | 30 | #4 | 1 turn + 5 on 15 |
| `dt-cone-gear` T036 | 36 | #3 | 1 turn + 2 on 18 |
| `dt-cone-gear` T042 | 42 | #3 | 20 on 21 |
| `dt-cone-gear` T048 | 48 | #3 | 15 on 18 |
| `dt-cone-gear` T054 | 54 | #3 | 20 on 27 |
| `dt-cone-gear` T060 | 60 | #2 | 10 on 15 |
| `dt-cone-gear` T066 | 66 | #2 | 20 on 33 |
| `dt-cone-gear` T072 | 72 | #2 | 10 on 18 |
| `dt-cone-gear` T078 | 78 | #2 | 20 on 39 |
| `dt-cone-gear` T084 | 84 | #2 | 10 on 21 |
| `dt-cone-gear` T090 | 90 | #2 | 8 on 18 |
| `dt-cone-gear` T096 | 96 | #2 | 5/12 turn: no standard circle |
| `dt-cone-gear` T102 | 102 | #2 | 20/51 turn: no standard circle |
| `dt-cone-gear` T108 | 108 | #2 | 10 on 27 |
| `dt-cone-gear` T114 | 114 | #2 | 20/57 turn: no standard circle |
| `dt-cone-gear` T120 | 120 | #2 | 5 on 15 |
| `dt-cylinder-gear` ×20 | 120 | #2 | 5 on 15 |
| `dt-alignment-pinion` | 32 | #4 | 1 turn + 4 on 16 |

T096, T102 and T114 need differential indexing, which takes a universal head with change
gears, or a plate drilled with 12, 51 or 57 holes. Those tooth counts did not change with the
pitch, so this was already true of the old train.

Each gear is modelled as the gap its stock cutter makes: the tooth of the lowest count in the
cutter's range. Each cone is cut at standard depth, so the cutter's pitch line sits on the cone's
pitch circle, and its blank is the AGMA standard outside diameter, (N + 2)/DP, cut down only where
the cutter's form would stop supporting the tip
([`gear-standard.md`](./gear-standard.md#cutter-native-teeth)). The meshes are not conjugate.
They are accepted by closed-form contact-ratio, interference, backlash and root-clearance checks
on the printed limits, plus the SolidWorks assembly interference gate
([`gear-standard.md`](./gear-standard.md#how-the-meshes-are-accepted)). Cut and roll one gear per
cutter before committing a set all the same.

Boston Y48120 is a catalogue brass 48DP PA20 120T spur. Using it as a donor for the cylinder-gear
teeth is possible in principle, but the part is not designed around it.

### T006 special cutter

No range cutter reaches 6 teeth, so T006 needs a tool made in the shop: DT6-FORM1, a custom
ground form tool whose full grind, including the relief that clears the drum tips, is
drawn on its own detail sheet in the MHA-DT-003 package. The root-to-bore web it leaves is
0.64 mm, over the 0.62 mm floor; see [`gear-standard.md`](./gear-standard.md#what-it-costs).

For background on shop-made form cutters, Law's *Gears and Gear Cutting*
(`references/gears-and-gear-cutting/`, ch. 12) forms the cutter profile with a button tool: two
hardened round buttons set at a chosen centre distance. The Eureka device named there is only an
attachment for relieving the cutter. Law's button table covers cutters from a 17-tooth pinion up,
so it does not give a six-tooth form.

### Crossed crank pair, normal 24DP PA20

| part | teeth | form | cutter | index per tooth (40:1) |
|---|--:|---|:--:|---|
| `dt-crank-pinion` | 16 | straight spur | #7 | 2 turns + 10 on 20 |
| `dt-crank-drive-gear` | 64 | right-hand helix 13.0011°, lead 945.862 mm | #2 (virtual 69 teeth) | 10 on 16 |

The 64T is cut with the cutter chosen for its virtual tooth count, N / cos³ of the helix angle,
which lands in the #2 range ([John F's workshop, helical gears](https://johnfsworkshop.org/home/making-other/gears-links/helical-gears-links/making-helical-gears-on-a-vertical-milling-machine/)).
The table is swivelled to the helix angle and the head is geared to the table leadscrew so the
blank turns once per 945.862 mm of travel. That needs a spiral-capable universal dividing head;
indexing alone, even with a DRO, cannot generate the lead. The installed Precision Matthews BS-0
is sold as semi-universal
([BS-0](https://www.precisionmatthews.com/products/dividinghead-bs-0)); the BS-2 is sold as able to
cut spirals ([BS-2](https://www.precisionmatthews.com/products/dividinghead-bs-2)). Change gears
for the lead depend on the head and the table screw: `TODO(cut it first)`.

Set each crank gear up for tooth cutting within 0.05 mm TIR of its finished bore
(`cad/config/tolerances/crank_mesh.yaml`, `tooth_cutting_runout_tir_mm`, read by both gear specs). This is a
setup allowance, not a gear accuracy grade.

### Paper drive

| part | teeth | pitch | cutter | index per tooth (40:1) |
|---|--:|---|:--:|---|
| `pd-rack-pinion` (reducer disc) | 120 | 48DP PA20 | #2, Precise/Penn 10-289-482 | 5 on 15 |
| `pd-transgear-knob-shaft` integral pinion | 12 | 48DP PA20 | #8, TTC 10-289-488 | 3 turns + 5 on 15 |
| `pd-transgear-feed-pinion` | 12 | 32DP PA20 | #8, Precise/Penn 10-289-328 | 3 turns + 5 on 15 |
| `pd-platen-rack` | rack, pitch 2.4936 mm | 32DP PA20 | none: bought as stock rack | none |

The reducer is 12:120 at 48DP, and the two 48DP cutters are the same #2 and #8 sizes the cones
use. Both 12T pinions carry the stock #8 form, and each hub is shaped so the cutter runs out clear.
The rack is bought, not cut: SDP/SI A1B12-Y324, a 48 in brass 32DP 20° rack, 3/16 × 3/16 in
(4.7625 mm) square ([product page](https://shop.sdp-si.com/a-1b12-y324.html),
[D820 catalogue](https://sdp-si.com/D820/PDFS/Gears.pdf)), cut to 269.64 mm and soldered to the
existing backer. Check it against the feed pinion before fitting; the pitch-index limit the model
allows for it is in `cad/config/tolerances/stock_form_quality.yaml` (`rack_pitch_index_deviation_mm`).

The chain is 68 links of ANSI #25, 12:24 from the crank sprocket to the knob sprocket. The
sprockets are made from McMaster 6793K blanks. The transgear arm and its plate are located by two
MHA-VN-054 dowels (McMaster 93600A189, 2 × 6 mm); the screws only clamp.
