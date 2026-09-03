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
  1. **`cone-gear` T006** — root-to-bore wall **0.49 mm** on a **~4.08 mm OD / Ø0.79 mm bore** gear.
     The single hardest part in the machine. (The build script's header comment saying "0.8 mm" is
     **stale** — the executable `bore_dia_in` gives 0.49 mm. Every small cone gear is sub-1 mm:
     T012 0.83, T018 0.78, T024 0.71.) **No executable guard enforces this** — it lives only in a
     comment. Period mitigation: the tip gears were a harder yellow metal. The script itself notes "a
     real builder would keep the tip gears larger" — a legitimate DFM deviation to consider.
  2. **`summing-lever` knife edge** — the sharp top-vertex ridge of a hex trunnion that protrudes
     **21.717 mm unsupported** past each end of a casting-shaped organic lever. Delicate (nicks/rounds)
     *and* fixturing-hostile from bar. Per §6 the edge should be a **separate hardened tool-steel
     insert**, not this parent — which also removes it from this part's machining hazard.
  3. **`cone-gear-shaft` tip** — a **Ø0.79 mm × ~34 mm journal in steel** (43:1 slenderness). Whip
     city; needs a follower/steady and a very light finishing cut, or enlarge per the T006 note above.

- **The CNC repeat families (make N identical on the PM-30MV — this is where CNC earns its keep):**
  | family | qty | why CNC |
  |---|---|---|
  | `cylinder-gear` (+ integral cam) | 20 | 120 teeth + eccentric cam + 0.4 mm index notch, all co-phased +Y — hand-repeating 20× scatters the phase |
  | `cone-gear` | 20 | involute teeth cut with a **self-made Eureka-generated form cutter** (cutters for these DP/tooth-counts don't exist — see "How to get this reviewed"), indexed on a dividing head; wire-EDM = outsource alt |
  | `rocker-arm` | 20 | repeated R800/R816 strap profile plus the same integral Ø10 × 7.0565 pivot hub and reduced 5 mm rod tongue; CNC preserves the hub/bores/profile relationship across multi-level setups |
  | `connecting-rod` | 20 | repeated gray-iron ring/shank/offset-clevis casting; fixture from the ring datum to machine the strap bore, then drill the two clevis-cheek openings coaxially and preserve every local-Z envelope |
  | `clevis-pin` | 20 | Ø1.8 × 4.9 shank and Ø3.0 × 0.6 head turned identically from Ø3 stock |
  | `knife-mount` | 2 | trivial prismatic block, 2 identical |

- **Casting-vs-bar substitution (3 T1 parts are castings in the registry):** `summing-lever`,
  `rocker-arm-support`, and `connecting-rod` carry `material: Gray Cast Iron` in
  `cad/config/parts/*.yaml`. The support remains the benign substitution: its
  relieved shell can be machined from bar. The rod is **not** a flat-plate
  substitute: its 3.0 ring, 1.0 centred shank, offset neck/web, and 4.9 clevis
  occupy multiple Z levels. Cutting it from solid requires repeatable ring-datum
  fixturing and multiple setups; fabricating the offset clevis requires controlled
  joining. The lever is still the hardest casting-native part because its ribbed/
  leaf organic form means 4–5 setups around cantilevered plates. Decide **cast,
  fabricate, or accept the multi-setup hog** for both rod and lever before stock
  is ordered; only the support is merely a stock choice.
  - **`knife-mount` is a material *conflict*, not a settled casting:** its registry
    (`parts/knife-mount.yaml`) and assessment §6 say **Brass**, but `build_knife_mount.py` hardcodes
    `MATERIAL = "Gray Cast Iron"`. The registry value is what stamps the BOM/drawing custom property, so
    the intended stock is a **brass bar block** (trivial) — the script constant looks stale. Reconcile
    before it reaches a drawing (gap below).

- **Almost every hole is 2.5D and almost nothing is threaded.** Only `rocker-arm-support` has real
  threads (4× 9/16-12 tapped foot holes). No keyways anywhere — gears are **soldered** to their
  shafts (cone) or ride **free on an arbor** (cylinder). That simplifies the whole build.

---

## Per-part rows

### Summing lever & knife edge (T1 — least forgiving interface)

| part | stock / form | key features | machinability hazards | setups | route |
|---|---|---|---|---|---|
| **`summing-lever`** | modeled **Gray Cast Iron casting**; organic first-class lever ~120×28×196 | solid pivot cylinder Ø25.4×152.4 (**no bore**); 2× hex knife trunnions (edges = top-vertex ridges) protruding 21.717 each end; 20× Ø2.0 spring holes through 5.08 plate @ 7.0565 pitch (web ~5.06); Ø3.0 anchor bore | knife-edge ridge **delicate** (the precision line); trunnion slender cantilever → **chatter**; organic 3-pt-arc leaf/rib profiles hard to mill; turning Ø25.4 with cantilevered plates | **4–5 from bar** (2 sketch planes + turn) | **CAST or fabricate**, don't hog; knife edge → hardened insert (§6) |
| **`knife-mount`** | rectangular block 34×43.77×14 (bar/plate); **2 identical** | Ø25.4 through bore (bearing bore for the trunnion), centre ~27.1 below the top face (`BORE_CY` −12.45 from the knife-edge origin, block top +14.62); tapped 1/2-13 blind hole ×12 in the block top (hanger-stud seat); walls 4.0 under bore, ~4.3 flanks | watch **bore breakout on the 4 mm floor**; otherwise trivial | 1–2 (square block, bore one axis) | **CNC-REPEAT** (×2) or trivial manual. Hangs from the top-frame casting's integral crossbar (the former separate top-crossbar part is merged into the top-frame) via a 1/2-13 knife-hanger stud |

### Cylinder gear + cam, connecting rod + clevis pin (T1 — the 20 function generators)

| part | stock / form | key features | machinability hazards | setups | route |
|---|---|---|---|---|---|
| **`cylinder-gear`** ×20 | round brass bar ~63; toothed disc OD62.2×3 + integral eccentric cam OD30.6×3.5 (offset +Y 8.64); total H 6.5 | Ø9.525 (3/8") through bore — **rides free on arbor, no keyway**; 120T involute DP49.82 PA14.5° (2.5D through-cut, patterned → **DXF/2.5D-machinable**); cam = plain eccentric circle (2.5D); **0.4 mm alignment notch** = the +Y co-phased timing datum | cam thin-side wall **1.90 mm**; notch kerf **0.4 mm** (slitting-saw, fragile crests); 3 mm slender disc; **double-sided** (teeth+notch front / cam boss far face) | **≥2** (flip for cam boss) | **CNC-REPEAT** — lathe bore+OD, teeth with a self-made form cutter indexed (wire-EDM = outsource), cam offset, notch by slitting saw; **hold the +Y phasing identical on all 20** |
| **`connecting-rod`** ×20 | gray-iron multi-level blank: ring 3.0 thick, centred flat shank 1.0 thick, and offset 4.9-wide clevis; ~170×40.8 envelope; book: "rough-finished" | Ø30.8 strap bore (rides Ø30.6 cam, 0.1/side); 8×12 D-cheeks, each 1.0 thick, about a 2.9 slot; #47 Ø1.994 hole through both cheeks; 2-high U-web plus offset neck | **not a flat 2D plate**: the multiple local-Z levels must close as one solid; 1.0 shank/cheeks need support; preserve 0.0565 adjacent-station shank-to-clevis clearance | **≥2** (ring/shank datum, then offset web/neck/cheeks; machine the strap bore separately and drill the two clevis-cheek openings coaxially) | **CAST + MACHINE** — rough-cast the stepped ring/shank/clevis form, machine strap bore and #47 clevis hole; fixture from the ring datum and verify every Z envelope |
| **`clevis-pin` MHA-018** ×20 | AISI 1018 cold-finished steel, turned from Ø3 stock; Ø1.8 shank × 4.9 grip with Ø3.0 × 0.6 flat head | shank clears the Ø1.994 #47 rod/rocker holes; grip closes on the 4.9 clevis outside faces; bright head seats on the near visible cheek | slender Ø1.8 shank and 0.6 head demand a sharp tool and light part-off cut; burrs would obstruct the running joint | **1** (turn shank/head and part off; deburr) | **LATHE-REPEAT ×20** — turn from Ø3 bar, part to head thickness, deburr without shortening the grip, polish bright, and oil |

### Cone gears + shaft (T1 — the DP-49.82 train, tip gears fragile)

| part | stock / form | key features | machinability hazards | setups | route |
|---|---|---|---|---|---|
| **`cone-gear`** ×20 (T006→T120) | round brass bar, extruded disc, face 6.5, OD = (N+2)/DP·25.4 at DP 49.82 → **~4.08 (T006) → ~62.2 (T120)** (same DP/OD as the 120T cylinder gear it meshes); tip gears T006–T024 harder yellow metal | 1 central through-bore, **soldered, no key**; bore Ø by config (T006 **0.79**/1/32″, T012 3.18, T018 6.35, T024+ 9.53); 6–120 involute teeth PA14.5°, 2.5D through-cut (DXF profile) | **T006 wall 0.49 mm** (headline); all small gears sub-1 mm; T006 whole gear tiny → brutal workholding; sharp internal corner at flank↔base-chord (wire-EDM/broach = outsource, or accept a corner radius) | ~2 (lathe OD/face/bore; teeth) | **self-made Eureka form cutter, indexed** (in-house; wire-EDM = outsource); T006 = hardest part — on enlarging tip gears see gap #5 (DP caveat) |
| **`cone-gear-shaft`** ×1 | stepped steel bar ~252; integral Ø12.2308 post journal then 3/8→1/4→1/8→1/32″ | 5 turned diameter steps; **no keyseat** (gears soldered); finish the Ø12.2308 journal for 0.05 diametral clearance in the v2 post bore | **Ø0.79×~34 tip journal in steel, 43:1** → whip; long slender overall | 1 (single-axis turn from one end) | manual lathe **+ steady/follower**; light finish on both bearing journals |

### Pivot and fulcrum shafts (T1 — full channel stack)

| part | stock / form | key features | machinability hazards | setups | route |
|---|---|---|---|---|---|
| **`pivot-shaft`** ×1 | plain steel bar Ø6.35×203.2 | solid, no bore/step/thread; 2 end faces | **L/D 32:1** → whip; steady-rest / between-centers | 1 | manual lathe + steady |
| **`fulcrum-shaft`** ×1 | plain steel bar Ø6.35×182 | as pivot-shaft, only shorter | **L/D 29:1** → whip; **same stock as pivot-shaft — don't mix** | 1 | manual lathe + steady |

### Rocker arms + support (T1 — multi-level arm + cast bracket)

| part | stock / form | key features | machinability hazards | setups | route |
|---|---|---|---|---|---|
| **`rocker-arm`** ×20 | AISI 1018 steel multi-level blank: 2.5-thick strap with integral Ø10 pivot hub spanning 7.0565; ~270×21 profile | top R800 concave and bottom R816 arcs; Ø6.5 pivot bore through the hub; rod end steps at a square shoulder to a 5 mm-deep tongue with Ø1.994 #47 pin hole; full-depth tail remains | **not one plane**: face both sides while leaving the hub concentric with the pivot bore; support the 2.5 web during second-side work; preserve the square tongue shoulder and thin reduced tip | **≥3** (face/pocket first side, flip on a hub/bore datum for second side, then profile; machine the pivot bore and #47 rod hole from the hub datum) | **CNC MULTI-LEVEL REPEAT ×20** — start from ≥7.0565 steel plate/bar, machine both broad faces to leave the integral hub around the 2.5 strap, then profile R800/R816 and the stepped 5 mm tongue; drill/ream the pivot and #47 holes from the hub datum |
| **`rocker-arm-support`** | modeled **Gray Cast Iron casting**, trapezoidal wedge, 6.35 mm shell walls | square window/cavity cuts with **R12.7-relieved** internal corners; **4× 9/16-12 tapped foot holes** (tap drill Ø12.30, through-next); RimChamfer 1.27 | square internal corners already relieved to R12.7 — cannot be cut sharper; thin 6.35 shell | foot-hole drilling = **1 setup** normal to the seat face | **cast** body + machine foot holes/rim |

---

## Recommended actions (gaps this pass surfaced)

1. **Add an executable wall guard for the small cone gears.** The 0.49 mm T006 wall (and 0.71–0.83
   for T012/T018/T024) exist only as comments — `build_cone_gear.py` has *no* assert enforcing them,
   and the header comment (0.8 mm) is stale. Add a `min-wall ≥ …` check so a future bore/OD edit can't
   silently drive it negative, and delete the stale 0.8 mm comment.
2. **Decide the `summing-lever` fabrication method** (cast / fabricate / hog) and the **knife-edge
   insert** now — it drives whether this is a 5-setup nightmare or two simple operations, and it is the
   critical interface.
3. ~~**Model the `knife-mount` mounting holes**~~ — RESOLVED (top-frame rederive, 2026-08-02): the
   block hangs from the top-frame casting's integral crossbar via a 1/2-13 hanger stud threaded
   into a tapped hole in the block top; both the stud and the tapped hole are modeled.
4. **Reconcile the `rocker-arm` R800 vs book 812.8 mm** (already a §4 Finding) before it becomes a
   drawing callout. Treat any radius decision as shared mechanism geometry: update the rocker arc
   source, pose inputs, J5 foot-on-arc coupling, and analytic radius check, then rebuild and revalidate
   the channel assembly. The integral hub and stepped 5 mm tongue keep either physical route multi-level.
5. **Consider enlarging the tip cone gears** (T006–T012) — the model already flags them marginal and a
   period build used harder metal. **DP caveat:** enlarging OD at a *fixed tooth count* changes the
   DP/module and **breaks the shared DP-49.82 mesh** — tooth *counts* preserve the ratio, but DP/pitch
   diameter preserves the *mesh* (`build_cylinder_gear.py` imports `DP` from `build_cone_gear.py`; §4
   treats the shared DP/PA as the meshing-domain constraint). So a real enlargement must either re-cut
   the mating **cylinder gear + centre distance** to the same new DP for that pair, or keep DP and accept
   the small size. Not the free change it first looks — the cheaper de-risk is the **harder tip metal**
   the original used.
6. **Reconcile the `knife-mount` material** — `build_knife_mount.py` (`Gray Cast Iron`) contradicts
   `parts/knife-mount.yaml` + §6 (`Brass`); the registry drives the BOM/drawing, so fix the script
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
  cannot cut, and sub-mm walls (T006 **0.49 mm**). Their rule sets are tuned for moulding / sheet /
  generic 3-axis and don't flag manual-machining hazards. **A green from these means little — trust it
  for nothing on the corners or walls.**
- **Fusion 360 CAM verify/simulate — the one worth banking on, with a known edge.** Because it
  simulates the *actual tool against the actual solid*, it **surfaces the class DFMPro missed**: an
  internal corner smaller than the smallest endmill shows up as **un-cut stock** (you can't program a
  sharp internal corner), and tool-reach / gouge / holder-collision are caught. Banking on Fusion for
  the **majority of tool-access & gouge issues is reasonable** — it's a real simulation, not a
  rule-of-thumb checker.
  - **But its blind spot is exactly where the worst risk lives.** Fusion treats geometry as **rigid**
    and stock as **held**, so it will *not* warn that the **T006 0.49 mm wall** breaks in workholding,
    the **Ø0.79 × 34 mm shaft** whips, the **1.90 mm cam wall** is fragile, or that a ~4 mm gear can't be
    gripped. Thin-wall / fragile-feature / fixturing failures are not modelled by CAM sim. **A clean
    Fusion sim is not a substitute for a first cut on the fragile parts.**

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

**Go/no-go — gear cutters: RESOLVED (they don't exist).** Off-the-shelf involute cutters for the
cone/cylinder train's **DP 49.82** at these tooth counts do not exist (searched exhaustively). **Plan:
generate self-made form cutters via the Eureka method** ([`references/gears-and-gear-cutting/`](../references/gears-and-gear-cutting/gears-and-gear-cutting.pdf)
ch. 12), then cut the teeth indexed on a dividing head — the in-house gear path referenced in the
routing tables above; wire-EDM / hobbing stay outsource alternates.
