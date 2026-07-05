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
  | `cone-gear` | 20 | involute teeth, 2.5D through-cut → CNC/wire-EDM/indexed |
  | `pivot-bushing` / `lever-bushing` | 19 each | turned spacers whose **length** sets channel pitch — length consistency across the set is the point |
  | `rocker-arm` | 20 | flat R800 profile, one setup — ideal CNC profile part |
  | `connecting-rod` | 20 | flat 2D outline → DXF/2.5D |
  | `knife-mount` | 2 | trivial prismatic block, 2 identical |

- **Casting-vs-bar substitution (4 T1 parts modeled as castings):** `summing-lever`,
  `rocker-arm-support`, `connecting-rod`, and (nominally) `knife-mount` are `Gray Cast Iron` in the
  model. Three are **benign** substitutions — the mount and support cut fine from bar, and the rod is a
  flat 2D profile that cuts trivially from plate (book: "rough-finished", so cosmetically forgiving).
  The **lever does not** — its ribbed/leaf organic form is casting-native and hogging it from solid
  means 4–5 setups around cantilevered plates. Decide **cast, fabricate (weld/silver-solder up from
  simple stock), or accept the multi-setup hog** before you start; the other three are just a stock
  choice, the lever is a real decision.

- **Almost every hole is 2.5D and almost nothing is threaded.** Only `rocker-arm-support` has real
  threads (4× 9/16-12 tapped foot holes). No keyways anywhere — gears are **soldered** to their
  shafts (cone) or ride **free on an arbor** (cylinder). That simplifies the whole build.

---

## Per-part rows

### Summing lever & knife edge (T1 — least forgiving interface)

| part | stock / form | key features | machinability hazards | setups | route |
|---|---|---|---|---|---|
| **`summing-lever`** | modeled **Gray Cast Iron casting**; organic first-class lever ~120×28×196 | solid pivot cylinder Ø25.4×152.4 (**no bore**); 2× hex knife trunnions (edges = top-vertex ridges) protruding 21.717 each end; 20× Ø2.0 spring holes through 5.08 plate @ 7.0565 pitch (web ~5.06); Ø3.0 anchor bore | knife-edge ridge **delicate** (the precision line); trunnion slender cantilever → **chatter**; organic 3-pt-arc leaf/rib profiles hard to mill; turning Ø25.4 with cantilevered plates | **4–5 from bar** (2 sketch planes + turn) | **CAST or fabricate**, don't hog; knife edge → hardened insert (§6) |
| **`knife-mount`** | rectangular block 34×43.77×14 (bar/plate); **2 identical** | Ø25.4 through bore (bearing bore for the trunnion), centre ~27.1 below the top face (`BORE_CY` −12.45 from the knife-edge origin, block top +14.62); walls 4.0 under bore, ~4.3 flanks | watch **bore breakout on the 4 mm floor**; otherwise trivial | 1–2 (square block, bore one axis) | **CNC-REPEAT** (×2) or trivial manual. **Gap:** mount-to-crossbar fastener holes are *not modeled* — add before drawing |

### Cylinder gear + cam, connecting rod (T1 — the 20 function generators)

| part | stock / form | key features | machinability hazards | setups | route |
|---|---|---|---|---|---|
| **`cylinder-gear`** ×20 | round brass bar ~63; toothed disc OD62.2×3 + integral eccentric cam OD30.6×3.5 (offset +Y 8.64); total H 6.5 | Ø9.525 (3/8") through bore — **rides free on arbor, no keyway**; 120T involute DP49.82 PA14.5° (2.5D through-cut, patterned → **DXF/2.5D-machinable**); cam = plain eccentric circle (2.5D); **0.4 mm alignment notch** = the +Y co-phased timing datum | cam thin-side wall **1.90 mm**; notch kerf **0.4 mm** (slitting-saw, fragile crests); 3 mm slender disc; **double-sided** (teeth+notch front / cam boss far face) | **≥2** (flip for cam boss) | **CNC-REPEAT** — lathe bore+OD, teeth CNC/wire-EDM/index, cam offset, notch by slitting saw; **hold the +Y phasing identical on all 20** |
| **`connecting-rod`** ×20 | flat plate ~3 mm; 2D outline ~170×40.8; book: "rough-finished" (cosmetically forgiving) | Ø30.8 strap bore (rides Ø30.6 cam, 0.1/side); Ø2.0 pin hole in head | **~1.4 mm** material over the Ø2 pin (fragile crown); reentrant fillets at shoulder roots (fine — it's an outline); 2.5 mm shank | **1** (profile + 2 drills) | **DXF/2.5D profile** the outline + drill 2 bores; leave body rough |

### Cone gears + shaft (T1 — the DP-49.82 train, tip gears fragile)

| part | stock / form | key features | machinability hazards | setups | route |
|---|---|---|---|---|---|
| **`cone-gear`** ×20 (T006→T120) | round brass bar, extruded disc, face 6.5, OD = (N+2)/DP·25.4 at DP 49.82 → **~4.08 (T006) → ~62.2 (T120)** (same DP/OD as the 120T cylinder gear it meshes); tip gears T006–T024 harder yellow metal | 1 central through-bore, **soldered, no key**; bore Ø by config (T006 **0.79**/1/32″, T012 3.18, T018 6.35, T024+ 9.53); 6–120 involute teeth PA14.5°, 2.5D through-cut → **DXF/wire-EDM/2.5D** | **T006 wall 0.49 mm** (headline); all small gears sub-1 mm; T006 whole gear tiny → brutal workholding; sharp internal corner at flank↔base-chord (wire-EDM/broach or accept radius) | ~2 (lathe OD/face/bore; teeth) | **CNC/wire-EDM**; T006 = hardest part — consider **enlarging tip gears** per script note |
| **`cone-gear-shaft`** ×1 | stepped steel bar ~202; steps 3/8→1/4→1/8→1/32″ | 4 turned diameter steps; **no keyseat** (gears soldered) | **Ø0.79×~34 tip journal in steel, 43:1** → whip; long slender overall | 1 (single-axis turn from one end) | manual lathe **+ steady/follower**; light finish on the tip |

### Pivots, bushings, shafts (T1 — the 19-channel stacks)

| part | stock / form | key features | machinability hazards | setups | route |
|---|---|---|---|---|---|
| **`pivot-shaft`** ×1 | plain steel bar Ø6.35×203.2 | solid, no bore/step/thread; 2 end faces | **L/D 32:1** → whip; steady-rest / between-centers | 1 | manual lathe + steady |
| **`fulcrum-shaft`** ×1 | plain steel bar Ø6.35×182 | as pivot-shaft, only shorter | **L/D 29:1** → whip; **same stock as pivot-shaft — don't mix** | 1 | manual lathe + steady |
| **`pivot-bushing`** ×19 | brass, OD Ø10.0×**4.5565** | Ø6.5 through bore (rides Ø6.35, **0.15 mm** clr); stubby L/D 0.46 | **length 4.5565 sets the 7.0565 channel pitch** → parting-length repeatability across all 19 is *the* critical dim | 1 (turn + bore + part) | **CNC-REPEAT** / collet stop for length consistency |
| **`lever-bushing`** ×19 | brass, OD Ø12.0×**4.0565** | Ø6.5 through bore (rides Ø6.35, 0.15 mm clr); twin of pivot-bushing | same drill/ream as pivot-bushing; differs only OD (12 vs 10) + length (4.0565 vs 4.5565) — **don't mix the two sets** | 1 | **CNC-REPEAT** / collet stop |

### Rocker arms + support (T1 — flat profile + cast bracket)

| part | stock / form | key features | machinability hazards | setups | route |
|---|---|---|---|---|---|
| **`rocker-arm`** ×20 | flat steel plate **2.5 mm** thick, ~270×21 | **top edge = R800 concave arc** (the amplitude-bar rides ON it) — it is the **2D OUTLINE of the plate, NOT a concave pocket/face**; bottom edge R816 concentric; Ø6.5 pivot bore + Ø2.0 rod-pin bore, both through the plate | none severe — pivot bore is **inherently square** (drilled through flat stock, one setup); no slot, no internal corner | **1** (all features one plane) | **CNC 2.5D profile** (×20 identical) or bandsaw+template; the R800 is profiled, not form-cut |
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
3. **Model the `knife-mount` mounting holes** — the block is placed on the crossbar but its fastener
   holes aren't in the script, so a generated drawing would omit them.
4. **Reconcile the `rocker-arm` R800 vs book 812.8 mm** (already a §4 Finding) before it becomes a
   drawing callout — but note the good news from this pass: it's a *profile* dimension, cheap to change.
5. **Consider enlarging the tip cone gears** (T006–T012) — the model already flags them marginal and a
   period build used harder metal; a modest bore/OD bump would de-risk the hardest parts with negligible
   kinematic effect (the tooth *counts*, not the diameters, set the ratios).

> These are machinability flags, not tolerance rules — the fits/finish/GD&T for the same parts live in
> [`tolerance-gdt-assessment.md`](./tolerance-gdt-assessment.md) §6, and the drawing/CAM outputs that
> carry them to the bench in §11.
