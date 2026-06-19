# Harmonic Analyzer — Dimension Source of Truth

Single source of truth for all part/assembly dimensions used by the reproduction
scripts in `cad/scripts/`. Built in Milestone 1 from the book
`references/albert-michelsons-harmonic-analyzer` (chapters 11–25, one component
each), cross-checked against the legacy `cad/Parts/*.cs` / `cad/kcl-archive/*.kcl`
dimensions.

> **This file is GENERATED from `cad/config/dimensions.yaml` — do not edit it
> directly.** The dimension tables live there as structured rows and the
> narrative as `prose` properties; `cad/scripts/gen_dimensions.py` renders this
> view (`--check` gates that the two never drift). The build *inputs* the scripts
> actually read (tooth counts, pitches, fits, the cone incline) live in the
> sibling `machine.yaml` / `channels.yaml` / `tolerances.yaml`; `verify.py`
> cross-checks those against the dimension rows here. Confidence ladder:
> annotated → stated → scaled → legacy → derived.

## Source hierarchy (authoritative → weakest)

1. **annotated** — dimension callouts printed on the book's photos. AUTHORITATIVE.
2. **stated** — dimensions written in the chapter body text. AUTHORITATIVE.
3. **scaled** — proportional scaling from an annotated/stated reference in the same
   photo (reference and method recorded per row; re-measure during M2 part builds).
4. **legacy** — `cad/Parts/*.cs` / `cad/kcl-archive/*.kcl` constants, themselves
   derived from the book earlier and POSSIBLY WRONG. Cross-check/tiebreaker only;
   wherever legacy contradicts a book annotation, the book wins (discrepancy logged).
5. **derived** — computed from other rows (formula recorded).

Confidence: **high** (annotated/stated, or legacy confirmed by book), **med**
(scaled with a good reference, or uncontradicted legacy), **low** (rough estimate,
must be re-measured against photos during the M2 build of that part).

**A derived row is NEVER high.** A value computed from other rows inherits one
step below its strongest cited input: derived from high → **med**, derived from
med → **low** (derived from low stays low). The cited inputs and formula are
recorded per row so the cascade is auditable.

Photo evidence: besides the book, 89 first-party photos of the machine exist in
`photogrammetry/raw/` — indexed per component in `photogrammetry/raw/README.md`. Use them for
detail inspection (fasteners, cross-sections, routing) and secondary scaling
(the 100 × 55 mm nameplate appears in-frame with the gear stack).

Units: original units as found; inches in parentheses (book annotations are metric;
legacy code is inches).

---

## Chapter 6 — Introduction: overall machine dimensions (p. 3)

The last page of the Introduction is a dedicated "Dimensions" photo with callouts
— the authoritative envelope for the whole assembly.

| dim | value | (in) | source | method | confidence |
|---|---|---|---|---|---|
| Total height (incl. curved counter-spring rod arching over top) | 147 cm | 57.9 | photo callout p.3 | annotated | high |
| Frame column height | 107 cm | 42.1 | photo callout p.3 | annotated | high |
| Base length | 46 cm | 18.1 | photo callout p.3 | annotated | high |
| Base depth | 28 cm | 11.0 | photo callout p.3 | annotated | high |
| Weight | 69 kg | 152 lb | photo callout p.3 | annotated | high |

Cross-validation: base 46 × 28 cm = 18.1" × 11.0" **confirms** legacy
HarmonicBase.cs bottom plate 18.0" × 11.0" (within rounding of the cm callouts).
Frame column 107 cm is the top-down anchor for tube-frame length; 147 − 107 =
40 cm of counter-spring rod arc above the frame.

## Chapter 26/29/8/9 — System-level facts (gear law, scale references)

| fact | value | source | method | confidence |
|---|---|---|---|---|
| Gear law | cylinder gear k turns k/80 rev per crank turn (k = 1…20) | ch.29 photo caption p.99 | annotated | high |
| Sample spacing | Δ = π/20 per 2 crank turns; 20 arms uniformly subdivide [0, π] | ch.29 p.99 | annotated | high |
| Cylinder gear speed ratio | gear n spins n× gear 1 | ch.8 p.7 | stated | high |
| Nameplate | 100 × 55 mm, brass, 4 corner screws, on base near platen | ch.26 text p.70 | stated | high |
| Maker / date | Wm. Gaertner & Co., Chicago; built 1896–1923 (likely 1901–09) | ch.26 | stated | high |

The nameplate's 100 mm width nearly fills the p.71 photo and appears in situ on
the base in the p.70 photo — best photogrammetric ruler for the base/platen region.

**Derived: cylinder gear tooth count = 120.** Cone does 1/4 rev per crank turn
(ch.12); cone gear k has 6k teeth (ch.12); cylinder gear k rate = (1/4)·(6k/T) rev
per crank = k/80 (ch.29) ⟹ T = 120 for all cylinder gears. Consequence: each
cylinder gear has the same tooth count (and pitch diameter) as the largest cone
gear — visually checkable against ch.13 photos. Confidence: high (pure arithmetic
from three high-confidence facts).

Chapters scanned with no dimensional content: 01–05, 07, 10, 27, 31. Ch.28
(Michelson & Stratton 1898 paper, 80-element machine) gives no absolute
dimensions; transferable facts: cone tooth counts proportional 1:2:…:n; sine⇄cosine
shift = 90° quarter-turn of all eccentrics via one long pinion engaging all at once
(matches ch.25); spring-summation balance y = Σx / [n(l/L + a/b)] with design rule
"l/L and a/b as small as possible"; accuracy benchmark 0.65–0.7% of largest term.

---

## Chapter 11 — Crank (pp. 12–15)

No annotated or stated numeric dimensions in this chapter.

| dim | value | (in) | source | method | confidence |
|---|---|---|---|---|---|
| Crank arm length (center-to-center) | ~66 mm | ~2.6 | REDERIVED from the ch30 eight-views (angle 90 side view): crankshaft axis to handle-pivot axis, scaled to the 280 mm base depth (ch6, annotated). The crank hangs straight DOWN (the handle reads "down" in all eight roll views, so the arm is on the views' vertical rotation axis), putting the handle ~10 mm above the base top. SUPERSEDES the former ~150 (cone-axial scaled, low), which was >2x too long — a down-pointing 150 arm would drop the handle below the table | scaled | med |
| Handle length | ~90 mm | ~3.5 | p.12 photo, proportion of arm length | scaled | low |
| Handle diameter | ~22 mm | ~0.87 | p.12 photo, proportion of arm length | scaled | low |
| Crank arm width | ~16 mm | ~0.63 | p.12 photo | scaled | low |
| Crankshaft diameter | 9.5 mm (3/8") | 0.375 | legacy `parameters.kcl` ShaftDiameter; uncontradicted | legacy | med |
| Arm thickness | ~8 mm | ~0.31 | p.12 photo, ~half the arm width | scaled | low |
| Square-end overhang past pivot | ~10 mm | ~0.39 | p.12 photo | scaled | low |
| Handle pivot bore | ~6 mm | ~0.24 | p.12 photo, proportion of handle dia | scaled | low |
| Fiducial dimple | ~Ø8 × 0.5 deep | — | p.15 photo | scaled | low |
| Tapered-pin cross-hole | ~Ø5 mm | ~0.20 | p.14 photo, pin small end | scaled | low |
| Crankshaft length | ~120 mm | ~4.7 | derived: crank seat (~30, incl. 10 overhang) + green pedestal bearing (~60, eight-views 8/8) + sprocket/drive-pinion seats (~30) | derived | low |

Construction (stated): wooden handle stained black, rotates on a pivot; metal crank
arm with fiducial indentations for alignment; tapered pin affixes crank to shaft
(removable — crankshaft gear is changeable); small chain eyelet (chain lost).

Rest pose (ch30 eight-views): the crank arm hangs straight down (−Y), the handle
pivot ~66 mm below the crankshaft axis with the grip axis parallel to the shaft —
modeled in `build_drive_train_assembly.py` as a −90° arm rotation about the crank
axis with the handle relocated below the crankshaft.

## Chapter 12 — Cone Gear Set (pp. 16–21)

| dim | value | (in) | source | method | confidence |
|---|---|---|---|---|---|
| Gear face width | 7 mm | 0.276 | photo callout p.18 — the annotated 7/7.5/150 trio is mutually inconsistent with the frame-locked drum grid; the build trims the as-built face to clear the seat pitch (a model detail, see build_cone_gear.py) | annotated | high |
| Cone set axial length | 150 mm | 5.91 | photo callout p.18; with the finer DP 49.82 module the gear stack shrank to 19 × 6.889 + 6.5 ≈ 137.4 mm (+ 64T face 10 + air) — the 150 arrow no longer matches cleanly and is flagged (the annotated 7/7.5/150 trio was already inconsistent with the drum grid) | annotated | high |
| Gear count | 20 | — | text p.16 | stated | high |
| Tooth counts | 6, 12, 18 … 120 (step 6) | — | text p.16 | stated | high |
| Crank→cone reduction | 4:1 (1 crank turn = 1/4 cone turn) | — | text p.16 | stated | high |
| Axial gear pitch | 7.2204 mm | 0.284 | along the cone axis (= machine.yaml drum_seat_nominal); RE-TUNED from 7.5 so its Z-projection stays 7.0565 = the frame-locked drum grid (gates, channels — Appendix C #3) when the module shrank to DP 49.82. The along-shaft seat pitch is now 6.889 (clears the shallower 12.52° incline) — a model detail. | derived | low |
| Diametral pitch / module | DP 49.82 (m = 0.5098 mm) | — | ANCHORED on the measured cylinder-gear OD = 62.2 mm (ch13, scaled p.25 bottom-left vs the back-view gear brackets, LOW): m = 62.2/(120+2) = 0.5098, DP = 25.4/m = 49.82, so largest cone / cylinder PD = 120·m = 61.18 mm. The cone T120 shares this module (it meshes the cylinder set). SUPERSEDES the former DP 30 round-inch derivation (p.18 tooth pitch 2.69 mm + 150 mm-arrow OD ≈ 105 → DP 30 → OD 103.3), which the 62.2 reading REFUTES — the p.18 scalings and the round-inch PD do not survive (logged discrepancy, user-directed 2026-06-18) | derived from the ch13 OD scaling (low) | low |
| Pressure angle | 14.5° assumed | — | period-typical; not stated anywhere | derived | low |
| Cone shaft length | 190 mm | 7.5 | M6.7: pivot journal 25 + stack 19 × 6.889 + 6.5 ≈ 137.4 + thin-tip journal through the knob post at station 177 (length kept 190; the stack lengthened slightly with the shallower incline) | derived | low |
| Cone shaft diameter | stepped: 9.5 (3/8") z 0–141.9, 6.35 (1/4") to 148.8, 3.18 (1/8") to 155.7, 0.79 (1/32") to 190 (large/pivot end at z 0) | 0.375/0.25/0.125/0.03125 | big-end dia kept 3/8" (pivot-post bearing). At DP 49.82 the tip gears are tiny (T006 OD 4.08, root r 0.89), so the shaft steps down MUCH further than the old DP 30 shaft: each step lands in the ~0.39 mm air gap between faces (seats at 28.25 + 6.889j ± 3.25). The 1/32" (0.79 mm) tip journal carrying T006 is mechanically marginal — flagged, follows from the 62.2 OD anchor (low) — `build_cone_gear_shaft.py` | legacy + derived | low |
| Gear bores (configured `BoreDia`) | snug on the stepped shaft (M6.7 perpendicular seats) AND inside each gear's root circle: 9.5 (3/8") T024–T120; 6.35 (1/4") T018; 3.18 (1/8") T012; 0.79 (1/32") T006; no keyway | — | Appendix C #7: bore = shaft section at the seat (perpendicular gears need no ellipse margin). At the finer module the T012 bore drops to 1/8" (root r 2.42) and T006 to 1/32" (root r 0.89 — marginal 0.49 mm wall); p.21 macro shows solder blobs fixing the small gears — no keyway evidence anywhere | derived | low |
| Crank-drive gear (dark steel gear at the large end, "This gear engages the crank" p.20) | coarser pitch than the train, est. DP 26.57 (= DP_TRAIN·64/120): ~64T, PD 61.18 mm (OD ≈ 63.1 mm ≈ the cone 120T's 62.2 — visual match RESTORED); mates a ~16T crank pinion (4:1, PD 15.3, OD 17.2) | — | p.20 annotation + visibly coarser teeth than the 120T beside it. Re-anchored with the 62.2 OD: the crank-drive DP was rescaled to 26.57 so the 64T pitch radius again equals the cone big-end's (the book's "OD ≈ cone 120T" cross-check holds, and the 64T stays ~1.9× coarser than the train DP 49.82). Tooth counts NOT countable in photos — split est. from the stated 4:1 + the OD-match argument (Appendix C #9) | scaled | low |

Notes: all 20 gears fixed to one shaft, rotate together. Engagement with cylinder
gears is at an oblique angle (partial engagement → distinct wear). The four smallest
gears (T006–T024, the cone tip) look "slightly more yellow … a different, perhaps
harder metal" (p.21). Period-accurate reading: a harder high-zinc yellow metal —
Muntz metal (60/40 Cu-Zn) or manganese bronze, both more golden and markedly harder
than the ~70/30 alpha brass of the larger gears — cut from drawn rod on a wheel-
cutting / dividing engine and soldered to the shaft (the p.21 solder blobs), chosen
because the finest teeth wear/break most. Modeled as the `muntz_yellow` appearance on
those four configs (materials.yaml, applied in the Phase 3 rebuild). Cone set pivots
out of engagement via a knob (for sine/cosine alignment, ch. 25). A 6-tooth involute
gear is severely undercut at standard proportions — `build_cone_gear.py` (M4) models it
stub-form (gap floor at the base-circle chord, no trochoid root), validated against
an analytic profile integral to ≤ 0.015% per configuration. All 20 tooth counts are
configurations T006..T120 of the single parametric part `cone-gear.SLDPRT`
(equation-driven involutes from ToothCount/DP/PA globals) with a configured bore
(`BoreDia` global per configuration, no keyway — Appendix C #7 resolved; the
mating shaft steps down accordingly, see the shaft rows). The dark coarse-tooth
steel gear beside the 120T ("This gear engages the crank", p.20) is a separate
drive component — Appendix C #9.

## Chapter 13 — Cylinder Gear Set (pp. 22–25)

| dim | value | (in) | source | method | confidence |
|---|---|---|---|---|---|
| Gear count | 20, all identical size | — | text p.22 | stated | high |
| Tooth count | 120 (each gear) | — | derived from gear law k/80 (ch.29) + 4:1 + cone teeth 6k — see ch.6/26/29 section | derived | med |
| Alignment notch depth | 3 mm | 0.118 | text p.22 (also pp. 66–67) | stated | high |
| Gear material | brass (polished) | — | text p.22 | stated | high |
| Axial pitch (z) | 7.0568 mm | 0.278 | frame-locked drum grid = the cone-set 7.5 annotation's Z-projection (Appendix C #3); M6 cross-check: rocker-arm end-view pitch measures ≈ 7.5 within photo error (ch. 14 note) | derived | med |
| Gear face width | 3.0 mm | 0.118 | M6 (Appendix C #6): p.22 stack macro face/pitch = 190/497 px ≈ 0.38 × 7.5 axial pitch ≈ 2.9, rounded 3.0 (the ch. 12 "7 mm" callout is the CONE gear face; the cylinder sandwich must also fit cam + rod ring) | scaled | med |
| Gear outer diameter | 62.2 mm (2.449") | 2.449 | scaled p.25 bottom-left picture against the gear-bracket sizes on the full-device back view (user, 2026-06-18). This is now the ANCHOR for the whole train module: DP = (120+2)·25.4/62.2 = 49.82, m = 0.5098 (ch. 12 row). REFUTES the former (120+2)/DP30 = 103.3 / round-inch-PD derivation. | scaled | low |
| Cam diameter (integral cam per gear) | 30.6 mm | 1.205 | SCALED 0.6022 with the gear OD (50.8 → 30.6, user-directed 2026-06-18): at the finer module the eccentric lobe (OD/2 + ecc) must clear the new tooth-root circle (root r ≈ 29.95). Cam OD is only a bearing surface, so scaling it is functionally harmless | scaled | low |
| Cam thickness | 3.5 mm | 0.138 | M6 (Appendix C #6): rides the inter-face gap in the UNCHANGED 7.0565 channel pitch (axial budget unaffected by the module change); REFUTES legacy 10.2 (0.4"), which alone exceeds the axial pitch | derived | med |
| Cam eccentricity | 3.06 mm | 0.120 | SCALED 0.6022 with the gear (5.08 → 3.06, user-directed 2026-06-18); the rocker-arm stroke shrinks proportionally (accepted). Was legacy 0.2" at the old module | scaled | low |
| Cam bore | 9.5 mm (3/8") | 0.375 | legacy `parameters.kcl`; plain bore, NO keyway (M6.2 refutation below) | legacy | med |
| Cylinder arbor length | ~200 mm | ~7.9 | derived: 134 stack (20 × 7.06 Z-pitch) + journal/clamp each end (eight-views 8/8 pedestals) | derived | low |

Notes: set is a sandwich — shiny brass gears alternating with black rough-finished
connecting rods. Each rod rides the cam on the gear to its right; cam converts
rotation to near-sinusoidal reciprocation of the rod → rocker arm. Notches aligned
to top = cosine mode; rotated 90° = sine mode (pp. 66–67).

M4 build (`build_cylinder_gear.py`): single non-configured part — 120T involute
ring (cone-gear equation-curve technique, toothed-disc volume reproduces the
cone gear's T120 configuration), integral cam boss (lobe −Y), plain bore
through gear and cam, alignment notch at +Y. Notch width is unstated in
the book — modeled square (3 mm wide × 3 mm deep, low confidence). The
standalone `eccentric-cam` part (M2 legacy re-author) is superseded by the
integral cam for assembly purposes.

**M6.2 keyway refutation (kinematic proof):** cylinder gear k turns k/80
rev per crank (ch. 29 gear law) — every gear at a DIFFERENT speed — so the
gears cannot be keyed to a common rotating shaft. The cylinder shaft is a
stationary arbor; gears spin freely on plain bores. This also explains the
ch. 25 setup pinion (turns all 20 gears as one only after the cone pivots
out of engagement). The legacy `parameters.kcl` cam keyway (3.2 × 1.5) and
matching shaft keyseat were legacy fiction — both removed in M6.2
(`build_cylinder_gear.py`, `build_cylinder_gear_shaft.py`).

### Drive-train layout (M6.2, eight-views 0°/90° + ch. 12 p.18 top-down)

Assembly frame: X = machine length (+ right when viewed from the front),
Y up from base top face (absolute Y = value + 50.8), Z = depth (− front).
Scales: front view bottom plate 2750 px / 457 mm = 6.02 px/mm; landmarks
converted from 400 dpi eight-views extractions (`ch30_images/`).
Eight-views calibrations (make_machine_grid.py): front p1 6.02 px/mm,
x0_img 1634, base-top y_img 6580; back p5 6.143 px/mm, x0 1647, ybase
6551, x mirrored (--xflip); side v3 (90°, camera WEST, −z left, M6.5)
6.124 px/mm, z0 at x_img 1744.5, ybase 6569. Perspective: scale ratio ≈
D/(D + depth), D ≈ 977 from the near base edge — far objects compress
toward the horizon (e.g. the crank pedestal at x +122.3 reads at ratio
0.736 in v3).

| item | value | source | confidence |
|---|---|---|---|
| Drive height (cylinder arbor AND cone big-end axis) | y = 76 above base top | crank-arm pivot + cone big-end brass blob, front view; side-view cone midline near-level confirms equal heights | med |
| Mesh offset direction | horizontal (plan), cone beside drum | ch. 12 p.18 top-down: cone converges on the drum toward the small end; side view cone midline ≈ level | high |
| Cone plan incline | 12.5188° = arcsin(1.5295/7.0565), converging +X→−X toward the drum | M6.7 exact-tracking mesh condition (appendix C #3): the radius step (now 1.5295 at DP 49.82) tracks per DRUM z-pitch 7.0565, which is held fixed by re-tuning the cone drum-seat to 7.2204 (machine.yaml) so the channel grid does not move. Shallower than the old 21.0976° because the finer module shrinks the per-gear radius step (was arcsin(2.54/7.0568)) | low |
| Cone mesh grid (X_PITCH) | every cone gear's pitch section crosses x = −16.01 at the contact azimuth: X_PITCH = drum tip x −16.40 + addendum·sec 12.52° − mid-face penetration 0.137 | M6.7 oblique partial engagement (book ch. 12 "partial engagement, distinct wear"): the contact tooth crosses the 3 mm drum face obliquely. The grid shifted ~20 mm inboard from the old +4.49 because the drum radius shrank with the module (tip x 51.65→31.10). FLAG: working depth is now only 1.02 mm (vs 1.69 at DP 30), so the 0.55 edge slack (tolerances.yaml) is large relative to it — the cone/drum mesh penetration needs re-tuning in the Phase 3 rebuild | low |
| Cone big-end (T120) gear centre | (x, z) = (+13.86, −60.47) = (X_PITCH + 30.59 cos i, drum plane −67.1 + 30.59 sin i) | M6.7: a perpendicular gear's contact tooth sits r·sin i along-shaft south of its centre, so each centre rides r_j·sin i NORTH of its drum plane. The +55 ± 5 photo blob NO LONGER agrees in x (the smaller cone pulled the big-end inboard to +13.9) — flagged consequence of the 62.2 anchor | low |
| 64T drive gear | perpendicular on the 3/8" pivot journal at shaft station 19.9, centre (x, z) = (+15.66, −68.62), 0.1 air to the T120 south face | p.20 (directly beside the 120T); rescaled to DP 26.57 (r 30.59 = cone T120), its contact tooth (toward the crank) sits 30.59·sin i = 6.63 north of centre at z = −61.99 | low |
| Cone gear j (j = 0 big … 19 small) | shaft seat station 28.25 + 6.889j; centre x_j = −16.01 + (30.59 − 1.5295j)·cos i, z_j = −67.1 + 7.0565j + (30.59 − 1.5295j)·sin i, y = 76; ALL 20 perpendicular to the shaft (true cone, p.18) | M6.7 exact tracking: the 20 mesh-derived centres are collinear iff sin i = 1.5295/7.0565 (asserted in `build_drive_train_assembly.py`); elegance check: tan(cone half-angle) = 1.5295/6.889 = tan i, so the drum-side generator runs parallel to the drum axis — the p.18 seam | low |
| Cylinder arbor (stationary) | x = −47.5 (frame-locked: rocker-support boss bore + arbor pedestal), y = 76, along Z | the cone grid is derived FROM the drum (X_PITCH + exact tracking); the book's "oblique partial engagement, distinct wear" (ch. 12) is now modeled literally (M6.7). Vertical connecting rods reach rocker tips only for x_cyl ≥ −100 ✓ | med |
| Cylinder gear j | z_j = −67.1 + 7.0568j (cone gear j's contact tooth lands in this plane; the cone CENTRES sit r_j·sin i north of it) | mesh plane alignment | high |
| Crankshaft | along Z at (x, y) = (+55.38, 76) = 64T contact x (15.66 + 30.59 cos i) + 38.24 DP 26.57 centre distance (R64 30.59 + R16 7.65) + oblique backoff (pinion centred on the 64T contact-tooth plane z −61.99) | FLAG: the front-view pedestal at +122 ± 3 NO LONGER matches the derived +55.4 — rescaling the whole drive train (cone + crank-drive) with the 62.2 anchor pulled the crank ~67 mm inboard. This is a new discrepancy from the 62.2 OD anchor: either the crank pedestal photo position or the 62.2 reading is wrong (appendix C #9 distance no longer ratifies) | low |
| Chain run | crank sprocket (+80, 76, the inboard-shifted crank) up to the translational-gearing sprocket at the third A-frame apex (x ≈ −7 ≈ 0, centered) | front view; transgear disc center measured x = −7 (the crank-end of the chain moved inboard with the crankshaft — see the crankshaft flag) | low |
| Cone pivot | at the big end, front (black bracket, p.18 "pivot" label); small end carried by the green knob post — swing is horizontal (out of mesh) | p.18 + ch. 12 notes | high |

### Drive supports (M6.2, photo-estimated)

| part | dims | position (x, z), bore y = 76 | source | confidence |
|---|---|---|---|---|
| `crank-pedestal` | green cylinder Ø46 × 110 tall, Ø9.5 bore along Z | (+118.00, −108.6) | front view: centre +123 ± 3 (M6.7 mesh-derived x within 1.3σ — crankshaft row), Ø 278 px / 6.02 px/mm, top ~110 above base top; z: standing inside the base front edge (−133.35), shaft stations in front | low/med |
| `arbor-pedestal` ×1 (M6.5, M6.9 trim) | green block 24 × 16 × 85, Ø9.5 clamp bore along Z | (−47.5, −90.5) south only (M6.9: 92 → 90.5, block front face −98.5 clears the thickened a-frame plate back face −99 by 0.5) — arbor 196 long spans z ±98 (M6.9: 200 → 196, 1.0 clear of the plate), stack ends ±70.6; the NORTH end clamps into the rocker-support frustum's east-flank boss bore (Ø9.7 at local (+25.4, 76) = machine (−47.5, 126.8), boss Ø20 face at z 74.1) — calibrated v3 side view shows no north pedestal, the arbor disappears into the frustum flank | function-driven; v3 side view (6.124 px/mm) | low/med |
| `cone-pivot-post` | black steel block 25 × 20 × 85, Ø9.5 journal bore (rotated 21.1° in plan with the cone axis) | (+62.4, −76.1) = shaft station −1 from the pivot end: the shaft engages the first 9 mm of the bore and ends inside (blind-bearing look — p.18 shows the shaft end disappearing into the bracket); the rotated block's z-reach 13.83 stops 1.0 clear of the perpendicular 64T's south face | p.18 "pivot" bracket; journal length from the cone-shaft row (~25) | low |
| `cone-knob-post` | green round post Ø32 × 80, upward-open U-slot 3.5 wide, floor at 74.4 (resting 1/8" tip centre 76) | (−1.7, +90.0) = shaft station 177 from the pivot end (thin-tip journal) | p.18 top-down: green post Ø ~72 px / 2.23 px/mm (largest-cone-gear-OD scale); view 5/8 ball-knob at x ≈ −20 ± 15 agrees within error | low |

### Connecting rods (ch. 13 pp. 22–25 + ch. 14 p. 29; 20 used)

| dim | value | (in) | source | method | confidence |
|---|---|---|---|---|---|
| Centre distance (cam ring → rocker pin) | 127.0 mm (5") | 5.0 | M6.3: rocker pivot axis y = 253.8 (apex ball mounts, front + back eight-views) minus drive height y = 126.8 = exactly 5" with the arm level; supersedes the earlier ~105 scaling (which used the wrong "rocker tip" attachment reading) | derived | med |
| Cam ring bore | 30.8 mm | 1.213 | cam OD 30.6 (scaled 0.6022) + 0.1 running clearance per side | derived | low |
| Cam ring radial wall | 5 mm (OD 40.8) | 0.20 | ch.13 photos, strap proportion vs cam; wall kept 5 mm (structural), so OD drops to 40.8 with the smaller bore | scaled | low |
| Ring / shank / tip-strap thickness | 3 / 2.5 / 2.5 mm | — | sandwich budget (7.5 axial pitch); tip strap = arm thickness so the pin joint is strap-beside-arm inside the 7.06 channel pitch (M6.3 — the "thick tip blocks" read of p.29 was wrong, see ch. 14 note) | scaled/derived | med |
| Shank width | 8 mm | 0.31 | ch.13 p.23 rod silhouettes vs 7 mm gear face | scaled | low |
| Tip strap (flattened upper end) | 10 × 18, Ø2 pin hole centred | — | pin matches the rocker's Ø2 rod-pin hole at +25.4 from the pivot (ch. 14) | scaled | low |

M6.3 re-read of p.29: the stepped sawtooth blocks at the rocker-arm tips
are the AMPLITUDE BARS' notched feet parked near the arm ends (ch. 15
"slide along its rocker arm … can slide completely off"), NOT the rod
tops. The rods attach near the pivot (rod pin +25.4 from the pivot, see
ch. 14 layout) and are plain thin straps at the top.

---

## Chapter 14 — Rocker Arms (pp. 26–29)

| dim | value | (in) | source | method | confidence |
|---|---|---|---|---|---|
| Arm plate thickness | 2.5 mm | 0.098 | photo callout p.27 (M2 re-read at 400 dpi; the M1 row misread this as a 12.5 mm "arm width") | annotated | high |
| Arm depth (end-face height) | 16 mm | 0.630 | photo callout p.29 — M2 zoom shows the arrows span the arm's end face vertically (NOT channel pitch) | annotated | high |
| Top-surface curvature radius | = amplitude bar length ≈ 800 mm | ≈ 31.5 | text pp. 26–27 ("equal to the length of amplitude bars" — minimizes nonlinearity) | stated | high |
| Arm count | 20 | — | photos/text | stated | high |
| Arm length | symmetric ±88 mm about the pivot (176 total) | ~6.9 | M6.3: ch. 15 text — positive amplitudes one side of the pivot, negative the OPPOSITE side, both up to the 80 mm measuring-stick span (+8 mm notch margin); supersedes the M2 100/70 asymmetric read | derived | med |
| Rod-pin hole | Ø2 at +25.4 (1") from the pivot, rod side, mid-depth | 1.0 | M6.3 closure: vertical connecting rods hang at the cylinder-arbor x = −47.5; pivot ball measured x ≈ −66 (back view, base-edge calibration) … −81 (front view) → designer value 1" lever arm, pivot at −72.9 | derived | med |
| Pivot pin hole | Ø6.5 (rides the Ø6.35 pivot shaft), mid-depth | 0.256 | function-driven (common pivot shaft, see layout below); the M2 "Ø3 dark dots" read was the rod-pin holes | derived | low |

### Rocker pivot & supports layout (M6.3, ch. 14 + ch. 30 front/back views)

| item | value | source | confidence |
|---|---|---|---|
| Pivot shaft | Ø6.35 × 228.6 (9") along Z at (x, y) = (−72.9, 253.8) | x = arbor −47.5 − 25.4 rod-lever; y = drive 126.8 + 127 rod (arm level at cam mid-stroke); ball x photo-measured −66…−81, ball y 252–255 in both 0°/180° views ✓ | med (x, y derived; dia low) |
| Support casting ×1 (M6.5, depth re-read M6.9) | solid tapered frustum, base 88.9 × 40 → top 20 × 20, 177.8 tall (7"), green; east-flank boss Ø20 at local (+25.4, 76) protruding to local z −27.5 (machine z 74.1), Ø9.7 through-bore along Z clamping the cylinder-arbor north end | front view: triangle base spans x −130…−44 (≈86), apex at −81 ± 6. M6.9 REINSTATES the windowed-frame reading M6.3/M6.5 refuted: ch30 p008 (+x side, brightened) plainly shows the legacy windowed portal frame (~184 wide, ~127 window) — this frustum is its NORTH upright, the transgear A-frame its SOUTH upright, joined by top/foot rails (modeled on the a-frame part, ch. 23 row); the old refutation came from the −x side view where the cone/drum hides the frame. The p008 uprights read ~28–40 deep and near-uniform → side depth 40 → 20 (supersedes the legacy 63.5 → 16.9 strong taper). M6.5's refutation of a second free-standing SOUTH frustum stands (the calibrated v3 side view shows ONE frustum at the back, z +69..+134 footprint; the south ball is gripped by the A-frame clevis) | photo + legacy height | med |
| Support position | apex centred (x, z) = (−72.9, +101.6), feet on the base top | north (back) only; z anchored by the north pivot ball at +101.6 (the old "outer face flush with the top plate edge" rationale died with the 63.5 base depth); apex top at y = 228.6 | med |
| Hold-down lag screws ×2 (M6.10) | round head Ø14 × 4 + Ø7.8 × 66 shank, axis +Y at machine (x, z) = (72.9 ± 31.75, 101.6) — UP through the base from below: heads recessed in the underside's Ø15 × 4.5 counterbores (y 0.5..4.5), shanks through the base's Ø8.2 through-holes into the frustum's Ø7.94 × 25 sockets (tips y 70.5, 5.3 short of the socket bottoms) | the support's 63.5 mounting-hole pitch (`build_rocker_arm_support.py`); placed in frame.SLDASM (`build_lag_screw.py`) | low |
| Ball mounts ×2 | clevis + Ø19 ball, ball centre 25.2 above its seat; Ø6.5 shaft cross-bore | apex/saddle top 228.6 + 25.2 = 253.8 = pivot axis ✓; north mount on the frustum apex (z +101.6), south mount on the A-frame saddle between its clevis ears (z −111, M6.5); same style at the lever rail (ch. 17) | scaled | low |
| Pivot spacer bushings ×19 | Ø10 OD × 4.5565 long × Ø6.5 bore (pitch 7.0565 − arm 2.5) | M6.3 geometric ceiling: at d = 0 the bar-foot cheeks pass 6.45 above the shaft axis (contact 262.63 − notch 2.381 − axis 253.8), so OD < ~12.9 — REFUTES the p.27 "Ø~25 barrel" read (those barrels are something else); Ø10 keeps 1.45 clearance | derived | med (OD low) |
| Arm stations | arm mid-plane z = z_j + 0.8 (rod strap at z_j + 3.3 sits beside the arm) | cam/ring z budget, ch. 13 sandwich | derived | med |

Notes: concave-upward curved top supports the amplitude bar (R = bar
length, minimizing the bar-tilt cosine error — the bar-top pin height is
invariant within 0.1 mm across the ±11.6° arm swing). Pivot = zero-
coefficient position for the amplitude bar. Matte-black finish. End view
p.28 shows the 20-arm array at uniform pitch. Bottom edge concentric with
the top (uniform 16 mm depth, R 816/800 arcs). Canonical rest state
(cylinder-gear notches at +Y = cosine alignment, integral cam lobes −Y):
arms tilt −11.6° (rod side down), rods tilt 0.18°.
Re-authored as `cad/scripts/build_rocker_arm.py` (supersedes the legacy
`oscilating-arms` part, which had no surviving source).

## Chapter 15 — Amplitude Bars (pp. 30–33)

| dim | value | (in) | source | method | confidence |
|---|---|---|---|---|---|
| Bar width | 6.35 mm | 0.250 | photo callout pp. 32–33 — exactly matches legacy BarWidth 0.25" | annotated | high |
| Bar length | ~800 mm ("about 80 cm") | ~31.5 | text pp. 30–31 — legacy BarLength 32.0" (813 mm) consistent | stated | high |
| Bar depth (cross-section) | 6.35 mm | 0.250 | legacy BarDepth, square section consistent with photos | legacy | med |
| Bottom notch width | 3.2 mm | 0.125 | legacy BottomNotchWidth (notch existence stated pp. 30–31) | legacy | med |
| Bottom notch height | 2.4 mm | 0.094 | legacy BottomNotchHeight (3/32") | legacy | med |
| Top notch width | 3.2 mm | 0.125 | legacy TopNotchWidth | legacy | med |
| Top notch height | 12.7 mm | 0.5 | legacy TopNotchHeight | legacy | med |
| Top pin hole | Ø2 through the top-notch cheeks, 6.35 below the top end | — | M6.3: p.39 shows the bar pinned to its top lever; the 3.2 top slot straddles the 3.0-thick lever with a Ø2 cross pin (matches the lever's bar-pin hole at 127 from its fulcrum, ch. 17) | derived | low |
| Bar count | 20 | — | text | stated | high |

Notes: bottom notch rides/slides along the rocker arm for positioning (bar at
pivot = zero coefficient; opposite ends = 180° phase reversal). Chrome-like
finish. Legacy AmplitudeBar.cs survives the audit: both book-verifiable dims
(width, length) confirm it. M6.3: the bars run UP the spine from the rocker
arms to the top levers (text pp. 30–31) — top pin FIXED on the lever at
x = −72.9 (above the rocker pivot), foot slides ±80 along the arm, the bar
tilting up to ±5.6° (the "nonlinearity ameliorated" by the 813 length).
Default assembly state: all bars at the pivot (d = 0, all coefficients
zero), exactly vertical, foot notch on the arm top edge at y ≈ 261.8,
top at ≈ 1072.3, pin at ≈ 1065.9.

## Chapter 16 — Measuring Stick (pp. 34–37)

| dim | value | (in) | source | method | confidence |
|---|---|---|---|---|---|
| Overall length | 200 mm | 7.87 | photo callout pp. 34–35 | annotated | high |
| Stick width | 8 mm | 0.315 | photo callout pp. 34–35 | annotated | high |
| Scale | 0–10, hand-stamped — 10 equal divisions of one half of the rocker arm | — | text p. 34 | stated | high |
| Scale span (10 divisions) | 80 mm | 3.15 | one half of the rocker-arm working length (p.34; ch.14 → ~160 mm) | derived | med |
| Body thickness | ~3 mm | ~0.12 | pp. 34–35 photo proportion | scaled | low |

Notes: ruled brass gauge (Wm. Gaertner & Co.) with a sliding/locking stop. The
0–10 scale spans "the 10 equal divisions of one half of the rocker arm" → half
rocker-arm working length ≈ 80 mm → rocker-arm working length ≈ 160 mm. This is
the top-down channel-geometry anchor; cross-check against the 16 mm callout in
ch. 14 and photo scaling during M2. Model the nominal 8 mm spacing (not the
hand-stamping error).

## Chapter 17 — Springs and Levers (pp. 38–41)

| dim | value | (in) | source | method | confidence |
|---|---|---|---|---|---|
| Spring coil body length | 32 mm | 1.260 | p.41 inset callout — dimension line spans the coiled body (excludes end hooks); resolved during M2 build | annotated | high |
| Spring coil OD | ~6.5 mm | ~0.256 | p.41 inset proportion vs 32 mm body (body/OD ≈ 4.9) | scaled | low |
| Spring wire dia | ~1.0 mm | ~0.039 | p.41 inset: close-wound, coils just distinguishable | scaled | low |
| Spring coil count | ~28 | — | body length / ~1.14 mm pitch (close-wound) | derived | low |
| Spring end hooks | bent-wire loops, both ends, extend axially | — | p.41 inset; M4: modelled as axial lead (2× wire dia) + 270° loop at coil mean radius, both springs (`_common.add_spring_end_hooks`) | stated | high (feature), loop geometry estimated (low) |
| Lever count | 20, cast metal, third-class | — | text pp. 38–39 | stated | high |
| Spring count | 20 | — | text pp. 38–39 | stated | high |
| Lever length (fulcrum→spring hole c2c) | 177.8 mm (7") | 7.0 | M6.4: the 254 "clean 2:1" guess (and the M2 ~240 scaling) is photo-REFUTED — calibrated ch. 30 front view: the lever bank ends at x ≈ −30, the summing-lever plate (pivot bolt read x ≈ +13..17, plate 44.45 wide) sits directly under the tab line, and the 32 mm springs can only bridge tab → plate at x ≈ −22; p.39 shows the bar pin ~5 bar-heights from the tip (50.8/9.5 ✓, 127/9.5 ✗). Bar pin stays at 127 (bar line −72.9, high) → motion ratio 1.4 | derived | med |
| Bar-pin hole | Ø2 at 127 (5") from the fulcrum, mid-height | 5.0 | amplitude-bar top pin (ch. 15); bar line x = −72.9 | derived | med |
| Lever bar section | 9.5 tall × 3.0 thick | 0.37 × 0.118 | M6.3: 20 levers at the 7.06 channel pitch on a common shaft cap the thickness (the M2 12.5 "width" violated the pitch); 3.0 lets the bar's 3.2 top slot straddle the lever | derived | med |
| Lever fulcrum | Ø6.5 pivot hole at 0; common Ø6.35 × 182 shaft (`fulcrum-shaft`, M6.5 — shortened from 228.6: tips ±91 clear the west columns' Ø34.925 surfaces at (−197, ±112), where 228.6 tips overlapped them by 0.09 mm) along Z at (x, y) = (−199.9, 1065.9), 2 ball mounts (same part as the rocker pivot's) on the top-frame west rail at z ±85; Ø12 × 4.0565 spacer bushings ×19 | — | p.40 bottom-left clevis+ball = the shaft END mount (mirror of the rocker pivot design); rail top = 1065.9 − 25.2 = 1040.7 | derived | low-med |
| Lever tip | bar steps to a 6.0-tall centred tab at x 169 (p.39/p.41), rounded r3 tip, Ø4 spring-hook hole at 177.8, 8 mm overhang; fork/clip fittings deferred (photogrammetry 195527397) | — | p.39, p.40; the Ø3 photo read is infeasible — the spring's r 2.75 Ø1-wire eye threading the 3.0 plate needs eye-drop margins |√(ρ²−1.5²)−D| ≤ hole_r − 0.1 at ρ = 2.25/3.25, best ~0.05 through Ø3, ~0.3 through Ø4 (M6.3 toroid solve) | scaled→derived | med |

Notes: each third-class lever pivots at its end (fulcrum), is driven by its
rocker arm/amplitude bar pinned at mid-length, and pulls one of 20 helical
springs attached to the pivoted summing lever below. Amplitude bar at rocker
pivot → lever motionless; at rocker edge → full amplitude; opposite end →
180° phase flip. M6.3 closure: fulcrum height 1065.9 = bar-top pin height
(levers level in the d = 0 default state) — consistent with the 1070
columns + top frame + 25.2 ball mounts within photo error (ball measured
(−205, 1078) on the tilted museum machine). Spring row hangs at
x = +54.1 (lever tips), z = lever stations; lower ends reach the summing
lever (ch. 18, M6.4).

### Channel & top-frame layout (M6.3, eight-views 0°/180° + ch. 14–18)

Machine coords as in "Drive-train layout". Channel j (j = 0 back … 19
front): cylinder gear at z_j = −67.1 + 7.0565 j; integral cam + rod ring
plane at z_j + 3.3; rocker arm / amplitude bar / top lever mid-planes at
z_j + 0.8.

| item | position / value | source | confidence |
|---|---|---|---|
| Rocker pivot shaft | Ø6.35 × 228.6 along Z at (−72.9, 253.8) | ch. 14 layout table | med |
| Top-lever fulcrum shaft | Ø6.35 × 182 (`fulcrum-shaft`) along Z at (−199.9, 1065.9) — M6.5: 228.6 tips fell inside the west columns | ch. 17 rows | med |
| Top frame (NEW part) | green cast rectangular ring around the 4 columns: rails 22 wide × 41 tall (y 999.7…1040.7, top = lever ball-mount seat 1065.9 − 25.2), corner bosses Ø48 bored Ø35 (column Ø34.925) at (±197, ±112); clamps the columns 80 below their tops (1120.8 − 1040.7) | eight-views: green ring at y ≈ 1010–1055 in all views, columns continue above it to caps ≈ 1090–1120 | med |
| Ball mounts ×4 | rocker pair at seats y 228.6: north on the support apex (z +101.6), south on the A-frame saddle (z −111, M6.5); lever pair on the top-frame west rail (seat y 1040.7) at z ±85 — any further out the Ø16 base overhangs the Ø35 boss bores (need √(2.9² + dz²) ≥ 17.5 + 8 → dz ≥ 25.3 from the boss at z 112) | ch. 14 / ch. 17; lever z from boss-bore clearance | med |
| Amplitude bars (default) | vertical, slot centred on the pivot x = −72.9 (d = 0, bar rotated 90° about its long axis: slot/pin across Z); foot roof on the tilted arm's top edge at 262.63 (contact at the bar −X edge, arc max), bar bottom 260.25, top 1073.05, top pin 1066.70 | ch. 15 notes + M6.3 assembly solve | med |
| Springs (default) | hanging free from lever tab holes (−22.10, 1067.02), rotated 90° about Y so the eye ring (r 2.75, plane ⊥ lever face) threads the Ø4 hole; eye centre 3.37 below the hole (torus-swept worst cases at the slab faces: upper branch inside the hole void with 0.31 margin, lower branch clears the tab underside by 2.05); body 32 + hooks (eye centre at spring local y 34 = body 32 + lead 2.0); lower hook centre lands at y 1027.6 = summing-plate level — the 32 mm spring length closes the lever→plate chain only with the 177.8 lever (M6.4) | ch. 17/18 + M6.4 threading solve | med |
| Default mechanism state | gear notches near +Y with the drive-train's +1.5° tooth-phase rotation (a T120 tooth faces the cone mesh) → cam centres at (−47.367, 121.721) = arbor + 5.08·(sin 1.5°, −cos 1.5°) → rod rings concentric on the cams there (M6.5 — assuming the unrotated centre (−47.5, 121.72) dug every ring 0.033 into its cam: 20 × 2.40 mm³) → arms tilted −11.54° (pin solve → pin (−48.01, 248.72)), rods leaning Rz +0.29°, levers +0.36° (bar-pin chain vs fulcrum 1065.9) | ch. 13 notes + ch. 25 + M6.3 solve, M6.5 phase fix | derived |

The measuring stick (ch. 16) is a loose hand tool — excluded from the
assemblies.

---

## Chapter 18 — Summing Lever (pp. 42–43)

No annotated or stated numeric dimensions in this chapter. The lever follows the
SummingLever.cs shape: a solid pivot cylinder, edge ribs, a tapering summation
tongue, an anchor eye, and a middle rib. Two hexagonal knife-edge trunnions
protrude beyond the body ends, vertex-up, their top vertex ridge forming the
knife edge the first-class lever hangs/rocks on; the stubs rest on bearing
supports standing on the top plate (ch30-p003 — not yet modeled). Lever-local
coords: origin on the pivot axis (cylinder centreline); the knife edge (rock
axis) is the hex top ridge, just above it. The 20 spring holes use the channel
registration. The build is authored x-negated so the hole plate lands on the
channel arm and the anchor eye on the counter-spring arm.

| dim | value | (in) | source | method | confidence |
|---|---|---|---|---|---|
| Pivot cylinder | Ø25.4 (1.0") OD × 152.4 long (z ±76.2), solid (no bore); mid-plane on the pivot axis | 1.0 | SummingLever.cs + p.42–43 close-ups | legacy | med |
| Hex knife-edge trunnions ×2 | vertex-up hex 8.653 wide (x) × 10.268 tall (y, vertex-to-vertex) × 21.717 deep (z), one PROTRUDING beyond each body end (z 76.2..97.92); top vertex ridge = knife edge = rock axis (≈5.1 above the cylinder centreline); rest on top-plate bearing supports (not yet modeled) | — | measured (user, ch18) | measured | med |
| Coefficients plate | x −60..−10 (machine −45..+5), top y 8, 5.1 thick, z ±76.2 | — | calibrated p1; thickness/length legacy (uncontradicted) | scaled + legacy | med |
| Spring holes | 20 × Ø4.5 at x −37.10 (machine x −22.10 = channel-lever tab line), z = z_j − 1.95 | — | derived: installed-spring eye reach √(3.25²−2.55²) = 2.0 through the 5.1 plate; z offset puts the hole under the helix lead | derived | med |
| Web + boss | twin ribs 3 wide, y 2..12, x 9..80, z taper ±17.18 → ±4.27; boss Ø14 × 12 at x 80 (machine 95) | — | p.43 plan | scaled | low |
| Hook hole | Ø3 vertical in the boss top at x 75.5 (machine 90.5) | — | derived: boss-hook shank seat (real joint ≈ 2.6 tap drill + M3 — modeled at shank size for a zero-volume fit) | derived | low |
| Knife mount | 8-square hardened bar set diamond-wise (edge up), 31.8 long — rides inside the lever tube's slot tunnel (z ±15.9 vs slot ±16; contact bands outside the slot are geometrically impossible — the diamond flanks clash with the tube lower wall); brass block 24 × 28 × 24 below; Ø8 stud through the tube slot rising to machine y 1065 | — | p.42/43 (square-head bolt + stirrup strap collapsed to block + stud — simplification) | scaled | low |
| Top crossbar | 22 × 41 rail section (ch. 6), 202 long along Z (M6.5 — the M6.4 372 mistakenly used the ring's inner X half-span 186; the bar spans the ring WINDOW along Z, inner faces at z ±101), Ø8.2 stud hole at centre; bottom face machine y 1010 (0.5 above the summing-lever tube top 1009.5) — the bar floats 10.3 proud of the top-frame ring band (999.7..1040.7), ends face-flush against the north/south rail inner faces over y 1010..1040.7 | — | ch. 30 views + top-frame ring inner span | scaled + derived | med |
| Knife stay | Ø3 rod along X at machine (0, 1086), x −197..+20; 8 × 2 strap from the rod at x −10 down to the knife-mount stud west flank at (9.7, 1053) (end corner 0.44 clear of the stud face, low corner 1.5 above the raised crossbar top 1051) | — | p.42–43; M6.4 reroute: a drop to the knife block crosses the summing-plate band; M6.5 reroute: the lever spring tabs overhang to x −14.1 (tab tops ~1070.1), so the hook moved −40 → −10 to keep the whole strap east of the tab tips | scaled + derived | low |
| Boss hook | Ø3 J-hook: shank +Y in the boss hole, rise 12, elbow R 3, arm +X 3.5 — rod top machine y 1015, tip x 97 | — | p.43/45 (hook + chrome link ring collapsed to one hook; the spring's own loop is the ring) | derived | low |

Notes (stated, qualitative): cast iron; pivots on a knife-edge fulcrum; the 20
channel springs attach along the wide end; total motion is only a few mm
(magnified downstream by ch. 20–21).

## Chapter 19 — Counter Spring (pp. 44–45)

No annotated or stated numeric dimensions. No legacy part. M6.4 REVISION: the
M2 "~300 × Ø22, wire ~2.5" read came from the cut-off p1 front page (the
spring exits the page top). Recalibrated against the ch. 19 full-machine photo
(gooseneck scale 0.515 px/mm) and the p3 90° page.

| dim | value | (in) | source | method | confidence |
|---|---|---|---|---|---|
| Coil body length | 315 mm | 12.4 | ch. 19 full-machine photo, gooseneck-scaled (supersedes the ~300 M2 read) | scaled | low |
| Coil OD | 12.5 mm | 0.49 | vs the Ø16 gooseneck tube in the same frame (supersedes ~22) | scaled | low |
| Wire dia | 1.8 mm | 0.071 | close-wound dark coil, no light through (supersedes ~2.5) | scaled | low |
| Coil count | 165 | — | close-wound: pitch 1.91 leaves a 0.11 sweep-merge gap | derived | low |
| Bottom lead | straight 40 mm drop, coil bottom → ring that hangs on the boss hook (ring centre machine y 1012, rod top 1015) | — | M6.4 hang solve (`build_output_assembly.py`: ring inner top 1016.45 vs rod top 1016.5) | derived | low |
| Adjustment post | square-head screw on adjustable post | — | text pp. 44–45 | stated | high (feature) |
| Gooseneck | Ø16 chrome tube: vertical leg machine x 197 (east column line), y 1041..1390; 180° bend R 51; tip leg x 95 — plumb above the boss hook — ending y 1378; lug + Ø4 X-pin at y 1373 carries the spring's top loop | — | ch. 19 photo 0.515 px/mm + p3 90° page; the tip "slotted screw" modeled as lug + pin (simplification) | scaled + derived | med |
| Gooseneck clamp | green cast block 30 × 29 × 24 at machine (197, 1040.7, 0) on the east rail end; Ø16.5 vertical bore; square-head pinch screw (10 × 10 × 6 head, Ø5 shank stopped at the bore wall) | — | p.45: "a square-head screw pinches the post in its socket" | scaled | low |

Notes: single large spring balancing the combined pull of the 20 channel
springs. Hang chain (machine y): boss hook rod 1015 → bottom ring 1012 →
coil 1052..1367 → top loop 1370.6 → gooseneck pin 1373. Tension is set by
sliding the tube in the clamp bore (tube bottom stops 0.3 above the rail
top at 1040.7).

## Chapter 20 — Magnifying Lever (pp. 46–49)

No annotated or stated numeric dimensions. No legacy part.

| dim | value | (in) | source | method | confidence |
|---|---|---|---|---|---|
| Magnification | up to 4× (adjustable) | — | text pp. 46–49 | stated | high |
| Rod diameter | ~6 mm | ~0.24 | round brass rod, photo proportion | scaled | low |
| Lever rod length | 165 mm | 6.5 | calibrated ch. 30 front view (p1): rod spans x ≈ −200..−35 at y ≈ 982. M6.4: REFUTES the M2 "~310 from the 4× constraint" — the p.46/48 insets show the CLAMP sliding along the rod (magnification = clamp-radius ratio), not a 310 rod | scaled | med |
| Vertical rod | ~Ø5 × 150, domed ends | — | p.46/48 vs lever rod | scaled | low |
| Clamp block | ~20 × 26 × 12; Ø6.2 lever bore, Ø5.2 rod bore (skew, 6.5 off-axis), Ø3 screw hole | — | p.48 close-up | scaled | low |
| Thumb screw | ~Ø10 × 5 reeded head, Ø3 × 12 shank (×2: clamp + output fixture) | — | p.48; M4: head reeded (24 × Ø1 grooves), cosmetic M3 thread on shank | scaled | low |
| Output fixture | collar ~Ø10 × 8, Ø5.2 bore, Ø3 cross hole | — | p.48 bottom close-up | scaled | low |
| Mounting bracket | collar Ø12 × 10 (bore Ø6.2) at machine (+40, 985, −85) (post-mirror, M6.8), axis along X; arm 10 wide reaching +Z to −70; 16 × 4 flange (machine x +29..+45, M6.5 — trimmed from 40 long: the end stops 0.65 off the j = 0 channel-spring helix at x +28.35) under the plate's front edge (top touches the plate bottom 992.9) | — | p.47 close-up | scaled | low |
| Bracket flange screws ×2 (M6.10) | fillister Ø5.5 × 2.2 head + Ø2.9 × 4 shank, UP (Rx −90) through Ø3.2 flange holes on the z −67 line (machine x +33/+41, inset 4 from the flange ends): shanks fill the flange band 988.9..992.9, tips flush with the plate bottom (engagement into the summing-lever plate not modeled); heads in free air below, 0.25 off the arm face (z −70), 1.9 off spring j = 0 | — | p.47 close-up (screw heads visible under the flange) | scaled + derived | low |

Notes: round brass rod lever; magnification set by a reeded (knurled) screw
adjustment that moves the effective fulcrum/attachment point. Geometry
constraint used in M2: output/input arm ratio = 4 at maximum setting (rod
ends domed; both rods revolves with hemispherical caps). M6.4 placement:
lever rod axis machine y 985 / z −85; clamp block at x −150; vertical rod
at z −91.5 (the clamp's skew bore, 6.5 off the lever axis), top y 990,
fixture at y 926; clamp thumb screw modeled BACKED OUT (head tangent above
the rod it pinches — seated it would overlap); the fixture's screw is
omitted at assembly level.

## Chapter 21 — Magnifying Wheel (pp. 50–53)

| dim | value | (in) | source | method | confidence |
|---|---|---|---|---|---|
| Inner hub diameter | 20 mm | 0.787 | photo callout pp. 50–53 (stated in text: "100 mm versus 20 mm") | annotated | high |
| Outer wheel diameter | 100 mm | 3.937 | photo callout pp. 50–53 | annotated | high |
| Magnification | 5× | — | text; consistent: 100/20 = 5 ✓ | stated | high |
| Spoke count | 6 | — | counted on the full-page photo p.51 (and photogrammetry `195607299`); an earlier extraction said 5 — wrong | stated | high |
| Wheel axle (M6.4) | flange Ø35 × 3 seated on the bar front face; Ø5 stud × 14 the wheel bore rides; Ø9 × 4 retaining collar (photo's washer + hex nut collapsed to a collar — simplification) | — | p.50–51 | scaled | low |
| Support bar (×3, M6.4) | 10-square steel, 384 long (M6.5 — trimmed from 400: at the bar's z band −138.9..−128.9 the Ø34.925 column surfaces reach x ±192.6, so ends at ±192 stay just inside); wheel bar y 565, platen top rail y 440, bottom rail y 334 — all on the column-clamp axis z −133.9 (front face −138.9) | — | M6.4 layout; p3 90° view: bars run tangent IN FRONT of the columns (z −112) | derived | low |
| Column clamp (×5, M6.4; count M6.8 — the half-width wheel bar takes ONE clamp) | green cast collar Ø48 × 16, bore Ø35.2 sliding on the Ø35 column; open channel across the front face (10.2 wide, floor 5.1 below bar centre) at column-to-bar offset 21.9; Ø3.2 radial pinch-screw hole through the back wall (M6.10) | — | p.50–55 | scaled + derived | low |
| Pinch screws ×5 (M6.10) | Ø6 × 2.5 head + Ø2.9 × 6.2 shank in each clamp's back-wall hole, BACKED OUT (a seated screw would overlap the column it pinches): heads on the clamp back faces (z −88..−85.5), shank tips at z −94.2 — 0.2 inside the hole, 0.3 off the column surface | — | p.50–55 (screw heads on the clamp backs) | scaled + derived | low |

Notes: wheel body is black-painted cast metal with a bright machined rim
(wire groove on the outer circumference); the inner hub is a grooved brass
drum (wire from magnifying lever wraps the hub, wire to pen mechanism leaves
the outer rim → 5× motion magnification). Six straight spokes. Hex-nut axle on
a horizontal support bar. The two annotated diameters self-validate against
the stated magnification — strongest-sourced part in chapters 18–21.
M6.4 placement: wheel at machine x −53 on the y-565 bar, wheel mid-plane
z −146.9 (axle flange on the bar front −138.9).

---

## Chapter 22 — Platen (pp. 54–55)

| dim | value | (in) | source | method | confidence |
|---|---|---|---|---|---|
| Front face height | 140 mm | 5.51 | photo callout p.55 | annotated | high |
| Width (travel direction) | ~300 mm | ~11.8 | p.55 front photo aspect ≈ 2.15:1 vs 140 mm; p.54 inset vs 460 mm frame agrees. M2 revision: supersedes earlier ~200 estimate | scaled | low |
| Plate thickness | ~4 mm | ~0.16 | p.55 top edge-on photo | scaled | low |
| Rack bar | ~300 × 30 × 6, brass | — | p.55 back-side photo; M4c: teeth cut at DP 30 / PA 14.5° (ch. 23 measurement), 112 gaps at p = 2.660 mm, crest at bar top, pitch line addendum (0.847) below it — `build_platen_rack.py`; mounting holes deferred to M6 (Appendix C #8) | scaled | low |
| Paper clip strips (×2) | ~125 × 10 × 1.2, Ø3 end-screw holes | — | p.55 front photo vs 140 mm | scaled | low |
| Material | heavy brass (darkened) | — | text | stated | high |
| Platen position (M6.4) | plate x −258..+42, y 305..445, front face z −142.9 (back face on the rail fronts at −138.9); carried by the y-440 / y-334 support bars | — | M6.4 layout: bottom rail raised 318 → 334 so the rack clears the column-clamp collars; top rail 460 → 440 to sit under the plate top 445 | derived | low |
| Paper clips position (M6.4) | two vertical strips on the paper face (z −144.1), rising from y 312: left at x −250..−240, right at x +22..+32 — shifted east of the pen v-block's x band (−24..8) | — | M6.4 layout | derived | low |
| Clip screws ×4 + platen sockets (M6.10) | brass fillister Ø5.5 × 2.2 head + Ø2.9 × 4 shank through each clip's own Ø3 end holes (machine x +245 / −27, y 320/429) into Ø3 × 3.5 blind sockets in the platen front face (shanks 2.8 into the plate, 0.7 short); under-head faces on the clip fronts (z −144.1); slots below render resolution — omitted | — | p.55 front photo (clip end screws) | scaled + derived | low |

Notes: toothed brass rack along the bottom edge (driven by ch. 23 gearing for
horizontal travel); two brass clips (left/right) retain the recording paper;
gearing can be unlatched from the rack for free repositioning/reset.
M6.4 rack mesh: rack mounted teeth-down (Rz 180) at y 323.59 = pinion axis
253.5 + PD r 40.64 + 0.3 backlash + pitch-line offset; rack x0 = 15.5 × pitch
(2.660) ≈ 41.23 — the gear's seed gap is centred at +γ/2 (flanks cross the
pitch circle at ±π/(2N) of the gap centreline), so a TOOTH sits at bottom
dead centre and the gaps flank it at ±p/2: rack teeth land on those gaps
(15 × pitch was tip-to-tip — 7 decaying overlaps, NOT a backlash problem).

## Chapter 23 — Translational Gearing (pp. 56–59)

| dim | value | (in) | source | method | confidence |
|---|---|---|---|---|---|
| Total gear count | 6 | — | text p.56 | stated | high |
| Removable gear set tooth counts | 12 / 18 / 24 (small/medium/large) | — | p.57 diagram captions | annotated | high |
| Rack & pinion | 2 of the 6 gears | — | text | stated | high |
| Chain drive | 2 gears (one at platen front, one on crankshaft) | — | text | stated | high |
| Fixed crank-speed reduction | 2 gears | — | text | stated | high |
| Rack & rack pinion pitch | DP 30 (machine system) | — | M4c keyframe measurement: rack pitch 2.66 mm; the DP 30 conclusion stands, but the M4c 120T/OD-105 read of the keyframes is superseded — see the rack-pinion row | scaled + counted | med |
| Rack pinion | 96T DP 30: PD 81.28, OD 82.97, ~3 mm face, Ø9.525 (3/8") bore, brass | 3.266 OD | M6.4: REFUTES the M4c "120T, OD 103.3" keyframe read — the calibrated ch. 30 front view (p1, 6.02 px/mm) shows OD ≈ 83 centred on the pinion-bar stud at (0, 253.5) | scaled | med (face: low) |
| Removable gear module | 2.0 mm (≈ DP 12.7) | — | 24T gear OD ≈ 51 mm in `v4_transgear_030` (scale via DP 30 rack pitch) ⟹ m = OD/(N+2) ≈ 1.96; m = 2.0 makes every swap combo's centre distance m(12+24)/2 = 36 mm exactly | scaled | med |
| Removable gear face / bore / pins | ≈ 5 thick; common bore Ø12; 2 × Ø3.5 pin holes on Ø19 BC | — | `v4_transgear_015` (catalog shot) + `v4_transgear_020/025/030` (mounted on the oval-pin stub shaft) | scaled | low |
| Chain wheels | the two MOUNTED removable gears themselves (knob shaft T24, crankshaft T12): the bead chain rides their m2 teeth — that is how gear swaps change the platen ratio, and why the latch slackens the chain | — | M6.8 supersedes the M4c "17T sprockets both ends": ch. 23 text + `v4_transgear_002/008/012` (chain visibly wraps the removable's coarse teeth); ch30 p002 full-res: upper wrap tips Ø ≈ 53.6 ≈ T24 OD 52 at post-mirror (−65, ~248); crank wheel small ≈ Ø30 (`v2_gears_010`) ≈ T12 OD 28. `chain-sprocket.SLDPRT` retired from the assemblies | counted + scaled | med |
| Drive chain (bead-chain rework) | ball-chain #13 stand-in: 63 × Ø4.8 spheres (`chain-bead`) at exact-closure pitch 6.387 (nominal 6.35 = 1/4") along the 402.4 closed centreline loop — two wrap arcs floating 0.41 + 2.5 outside the mounted removables' tip circles (knob T24 r 28.91 about post-mirror (−65, 241.78); crank T12 r 16.91 about (−118, 126.8)), the taut common external tangent on the pinion-bar side, and a slack arc (r 171.8) sagging 14 below the straight tangent (SAG trimmed 18 → 14: outer reach clears the cone-pivot-post top by 0.95); bead centres on the chain mid-plane z −81.05 (splits the T24/T12 wrap mid-planes; the real chain bridges the 4.35 z offset with a ~1.7° skew); connecting wire not modeled (flexible); realised as a SolidWorks chain component pattern over the `_chain.py` path sketch — replaces the rigid flat-band stand-in (5 × 4.5 section, same centreline) | — | ch30 p002/p005/p006 (taut run + visibly drooping slack run; p006 droop crop read 18) + ch. 23 text | scaled + derived | low/med |
| Reduction pinion (coaxial with rack pinion) | est. 24T DP 30, OD ≈ 21 mm measured, face ≈ 6 | — | edge-on views `v4_transgear_002/003/008`: small fine-tooth steel pinion on the rack-pinion shaft | scaled | low |
| Pinion bar (M6.5) | 12-square steel, x −58 → +178 at machine y 253.5 (M6.5 trim from −95..+197: west end clears the A-frame clevis ears/ball at x −59, east end clears the SE column tangent 179.54); Ø9.6 stud bore along Z at x 0 (9.525 stud + slip clearance); both ends FLOAT (documented simplification — the real machine likely straps the bar to the a-frame and column) | — | ch. 30 views + M6.5 layout | scaled + derived | low/med |
| A-frame (M6.5, re-thicknessed + rails M6.9) | green cast stand on the base front-west, doubles as the FRONT rocker support — the SOUTH upright of the rocker-support portal frame (ch30 p008): tapered plate 18.5 thick (machine z −117.5..−99.0 — photo reads ~28-30 but the band is pinned by the parked measuring stick at z ≤ −118 and the ch25 handle plane at z ≥ −98), foot x −115..−45 on the base top (y 50.8), apex x −87..−59 at the ball-seat saddle y 228.6 (machine); full-width saddle z ±11.1 over the last 19.8 of rise; clevis ears (z ±(8.1..11.1), 20 tall, tops machine 248.6) flank the south pivot-ball mount's Ø16 base (gap 16.2; ball r 9.5 centre 253.8 clears the ear inner faces; pivot shaft bottom 250.65 clears ear tops by 2.05); carries the portal-frame rails to the north frustum (faces −0.25): TOP RAIL 20 (machine x +62.9..+82.9) × 16 (y machine 212.6..228.6 = photo window top) to machine z +90.45, FOOT RAIL 30 (machine x +59.75..+89.75 — west face 0.25 east of the arbor-pedestal block) × 20 on the base top to machine z +81.35, bolted down by two hex bolts (M6.10): AF 12.7 × 5.5 heads + Ø7.8 × 32 shanks at machine (74.75, z −54/+36) through the rail's Ø8.2 holes, 12 into the base's through-holes (head corner 2.64 clear of the cylinder train's 120T tips); the part is authored MACHINE-handed (MIRROR_PLANE "x0", M6.9 — the one-sided rails killed the local-z symmetry the old "z" entry used); the real machine casts uprights + rails in one piece (split documented) | — | ch. 14 pp. 26–29 + ch. 30 front view: clevis grips the pivot ball at (−72, 252) — M6.5 apex crop; ch30 p008 (brightened) shows the full windowed frame; the M6.4 "ears grip the pinion bar" read is REFUTED (bar now floats) | scaled | med |
| Transgear stud (M6.4) | Ø9.525 (3/8") × 36 plug in the pinion-bar bore, axis −Z from z −101.5; Ø14 × 4 retaining collar at the front end (z −141.5) | — | derived: carries rack pinion (z −137.5), fixed pinion (z −134) and latch big hub (z −122.5); end hardware collapsed to a collar | derived | low |
| Latch arm (M6.8) | tapered link, 4.5 thick: big hub Ø22 / small hub Ø16, both bores Ø9.6; centre distance 66.05 = ch30 REST state, stud (0, 253.5) → parked knob shaft (pre-mirror +65, 241.78); assembled at −10.22° below +X (knob shaft clears the pinion-bar underside 247.5 by 0.96) | — | ch30 p002 full-res wrap centre (−65, ~248 post-mirror, ±3 chain-plane parallax; y clamped under the bar) — supersedes the M6.4 mesh-derived 34.26/−20°, which is the ENGAGED-state c2c (see Appendix C #8) | scaled + derived | med |
| Knob shaft (M6.8) | Ø9.525 × 58.0 through the latch small hub at (65.0, 241.78), spanning machine z −76.5 (chain end) → −134.5; carries the mounted T24 removable chain-wrapped at z −81.5..−76.5 and the fine 24T pinion at −134..−128; Ø20 × 6.5 brass thumb knob ending at −141.0, level with the stub collar band | — | `v4_transgear_008/020` + ch. 23 topology (M6.8) | scaled + derived | low/med |

Notes: speed combos — small driving + large driven = slowest platen (smallest
horizontal scale), large+small = fastest, medium+medium = 1:1. Latch disengages
gearing from the platen rack (quick reset; also slackens chain for swapping the
removable gears). Brass gears, central bores.

M4c note: the fixed-reduction pair's exact topology (what the coaxial DP 30
pinion meshes, and which shafts carry the two sprockets vs the removable pair)
is not fully resolvable from the available frames — logged as Appendix C #8,
to be settled when mating the drive train in M6. Parts authored now:
`transgear-removable` (one part, T12/T18/T24 configurations), `rack-pinion`,
`platen-rack`, `chain-sprocket`, `transgear-pinion`.

M6.8 notes (Appendix C #8 topology resolution): the six gears are (1) the
96T DP 30 rack-pinion disc on the stud, meshing (2) the platen rack above;
(3) the fine 24T DP 30 pinion on the KNOB SHAFT front (z −134..−128),
which meshes the disc only when the latch swings it in; (4) the T24
removable on the knob shaft at the chain plane and (5) the T12 removable
on the crankshaft — the bead chain wraps the removables' own m2 teeth (no
separate sprockets); (6) is the spare removable (T18) lying loose on the
base (machine (−133, 55.8, −80), M6.5 clearances). The ch30 plates show
the DISENGAGED rest state — latch parked at c2c 66.05, the T24's tips
overlapping the disc rim in XY projection only (chain plane is ~56 north
of the disc plane). The mixed-pitch jam note (m2 vs DP 30) still bars any
literal removable-on-pinion mesh; it never happens in the resolved
topology. The measuring stick (ch. 16, hand tool) lies flat on the base at
(−158, 53.8, −133), graduations up (M6.5 — the M6.4 spot (−175, .., −135)
ran it through the SW corner bracket's plate + foot).

## Chapter 24 — Pen Mechanism (pp. 60–61)

No numeric dimensions; modern reconstruction ("about 100 years younger than any
other part").

| dim | value | (in) | source | method | confidence |
|---|---|---|---|---|---|
| Square brass rod cross-section | ~5 mm | ~0.2 | photo proportion | scaled | low |
| Square rod length | ~120 mm, Ø2 wire hole near top | ~4.7 | p.64 inset; resolved in M2 | scaled | low |
| Frame (stirrup) | ~22 × 40 × 10; side rails 4 (long sides), end rails 5; Ø3 set-screw hole in one end rail | — | p.64–65 vs 5 mm rod; resolved in M2; M6.4: side rails thinned 5 → 4 (read thinner in the photo; the 14-wide window must clear the marker barrel at the platen side) | scaled | low |
| V-block | ~32 × 18 × 16; 6 mm 45° top chamfers; 2 × Ø8 vertical bores at x = 11/21; stopped clamp slit 26 long × 4 (y 4–8); Ø2.5 screw hole | — | p.65 close-up | scaled | low |
| Set screw | Ø9 × 5 knurled knob + Ø3 × 15 shank | — | p.64–65; M4: knob reeded (22 × Ø1 grooves), cosmetic M3 thread on shank | scaled | low |
| Pen hanger (M6.4) | black strap (3 thick, tapering 16 → 10 wide) flat on the wheel-bar front face (z −138.9), descending from the bar band (y 560..570) to a 12 × 12 guide block (z −155.5..−138.9) with a 5.4-square VERTICAL channel (cut along Y) the pen rod slides in | — | p.60–63 | scaled + derived | low |
| Hanger screw ×1 (M6.10) | AF-7 hex head × 2.5 + Ø3.5 × 12.5 shank at machine (−5.5, 565), driven from BEHIND the bar (the wheel rim back face passes 1.0 in front of the strap — no front-side head fits): head on the bar back face (z −128.9), shank through the bar's Ø3.8 hole + the strap's Ø3.6 hole, tip 0.5 behind the strap front face (−141.9); hole 0.6 off the bar's free-end face (machine −8) | — | p.60–63 (the strap is bolted to the bar) | scaled + derived | low |
| Pen marker (M6.4) | Ø8 brass barrel, 12-tall conical tip, 60 overall; collar/ferrule detail omitted | — | p.60–63 | scaled | low |

Notes: brass frame holds the marker in a v-block; v-block on a square brass rod
attached to the wire from the magnifying wheel (vertical motion); platen provides
horizontal motion. Small set screw adjusts pen angle to paper to cut friction.
Provenance (ch. 5 Preface): the original pen holder was missing — the one in all
book photos is a modern replacement designed/built by Mike Harland and Tom
Wilson. Model the replacement (it is what the photos document).

M6.4 pen layout (machine coords): pen rod vertical at x −3, z −151.5 band
(rod z −154..−149), y 398..518, Ø2 wire hole at y 513 just above the hanger
block top (511); v-block at (−24, 390, −159.5) — rod bore (local x 21) on
the rod axis; marker VERTICAL in the x −13 bore, tip at y 368, i.e. 8.6 off
the paper plane — the book's ~12° tilt would cut the v-block's vertical
bores, so the marker stands plumb (documented deviation, settle in M6.5);
pen frame flat on the v-block top (y 408), long axis along X (Ry+90·Rx+90 at
(−29, 418, −143)): window machine x −25..+7, z −161..−147 spans marker +
rod, the plate's near edge stops 0.1 short of the platen front face −142.9;
set screw along +X at (−38, 413, −154) — knob x −38..−33, shank threading
the west end rail (x −29..−24), tip at −18, 1 shy of the marker barrel.

## Chapter 25 — Pinion Gear (pp. 66–69)

| dim | value | (in) | source | method | confidence |
|---|---|---|---|---|---|
| Tooth count | 42 | — | counted on the drum end view (engineerguy video 4/4 @ 8:00, frame `v4_pinion_018`): 7 tips per 60° sector × 6; tip-radius ratio to the meshing 120T cylinder gear = 0.36 = 44/122 confirms same DP | counted | high |
| Pitch diameter | 35.56 mm (1.400") | 1.400 | 42 / DP 30 — round-inch PD corroborates both the count and DP 30 | derived | med |
| Outer diameter | 37.25 mm (1.467") | 1.467 | (42+2)/30 | derived | med |
| Drum length | ~150 mm | ~5.9 | spans/engages all 20 cylinder gears at once (p.67 photo: drum ≈ cylinder stack length = 20 × 7.5 axial pitch) | derived | med |
| Material | brass | — | photos | stated | high |

Notes: single pinion — a long toothed drum, engaged via a small ball-handle
lever, meshes the cylinder gear set and turns all 20 cylinder gears as one —
used only during setup to align the 3 mm notches (top = cosine, 90° = sine)
after pivoting the cone set out of engagement. The "small gear" visible on the
lever arm in the p.68–69 photos is the drum's front end face, not a separate
idler (video frame `v4_pinion_018` shows the drum receding behind it).

### Alignment-pinion layout — REMOVED 2026-06-18, pending rework

The alignment pinion (the 42T zeroing drum + its swing straps, pivot
blocks, torque shaft, lift rod, lever and handle) has been DROPPED from
`build_drive_train_assembly.py`. At the re-anchored OD 62.2 / DP 49.82 the
Ø22.4 mm pinion drum no longer fits the machine: a single rigid drum
spanning the cylinder set (z −75..+68) sits at one x for its whole length,
and the channel between the rocker-support frustum (east face x −28.45) and
the rescaled 64T (tip west edge x −15.89, where the 64T crosses the drum
face) is only 12.56 mm wide — a ~9.9 mm shortfall that no position or pivot
topology can resolve. This is the sixth geometric impossibility the 62.2
eyeball reading forces (after the cam-through-roots, the 0.79 mm T006 tip
journal, the 67 mm crank-pedestal shift, the impossible disengage pose, and
the pivot-block straddle). The mechanism is to be re-solved once the gear
OD is confirmed; the retired DP-30 layout it replaced is in git history.


---

## Appendix A — Legacy constants (cross-check only; POSSIBLY WRONG)

Mined from `cad/Parts/*.cs` (each translated from `cad/kcl-archive/*.kcl`). Full
audit detail in the M1 extraction; key values referenced by the chapter tables:

- **AmplitudeBar.cs**: length 32.0", section 0.25" × 0.25", bottom notch
  0.125" × 3/32", top notch 0.125" × 0.5" — **CONFIRMED** by ch. 15 (6.35 mm
  width annotated, ~80 cm length stated).
- **EccentricCam.cs**: Ø2.0" × 0.4" thick, bore 0.375", keyway 0.125" × 0.06",
  eccentricity 0.2" — uncontradicted; verify against the cam outline printed on
  book p. 25 during M2.
- **HarmonicBase.cs**: bottom plate 18.0 × 11.0 × 0.5", top plate
  17.5 × 10.5 × 1.5", fillets 0.125"/0.0625" — footprint **CONFIRMED** by the
  ch. 6 base callouts (46 × 28 cm = 18.1" × 11.0"); plate thicknesses still
  photo-verify in M2.
- **RockerArmSupport.cs**: 7.00" tall × 7.25" wide A-frame, trapezoid depth
  2.50"→0.667", wall 0.25", 5.00" sq window (r 0.625" corners), mounting holes
  Ø5/16" — no book numerics; verify by photo scaling in M2.
- **SummingLever.cs**: see ch. 18 table (carried as primary numeric source there).

## Appendix B — Audit of 10 existing SLDPRT parts

| part | book-verifiable dims | verdict |
|---|---|---|
| amplitude-bar | width 6.35 mm ✓, length ~80 cm ✓ | PASS — re-author script with same dims |
| eccentric-cam | none annotated; cam outline p.25 available | UNVERIFIED — scale p.25 outline in M2 |
| harmonic-base | ch.6: base 46 × 28 cm ✓ (= 18.1" × 11.0") | PASS (footprint) — thicknesses photo-verify in M2 |
| summing-lever | none | UNVERIFIED — p.42–43 proportion check in M2 |
| rocker-arm-support ×3 | none | M6.3 refuted the legacy windowed square frame (184 wide); M6.9 PARTIALLY REINSTATES it — ch30 p008 (brightened) shows exactly that frame: north frustum + A-frame south upright + top/foot rails (ch. 14 layout table). The ×3 count stays refuted (ONE frame: two uprights; the legacy third instance at x ≈ 0 under the transgear is the pinion-bar/stud's job in this model); re-authored |
| oscilating-arms | ch.14 re-read: the "12.5 mm width" was a misread (callout is 2.5 mm plate thickness) | SUPERSEDED — re-authored as rocker-arm with corrected dims (`build_rocker_arm.py`) |
| corner-bracket | none — no source either; geometry interrogated live from the SLDPRT (face inventory): base 1.125" × 0.75", height 2.3", plate 0.3" thick, sides tangent-tapered to R0.5" crown (centre 1.8" up), Ø0.4" lug hole, #9 (Ø0.196") foot hole | RE-AUTHORED — `build_corner_bracket.py` reproduces it to 13,035 mm³ (exact volume match) |
| tube-frame | ch.6: frame column height 107 cm — legacy file measured 1016 mm (40"), CONTRADICTS the book | RE-AUTHORED — `build_tube_frame.py` at 1070 mm (book wins), Ø1.375" × 0.12" wall from legacy. M4: fluted/reeded per the photo index `195108425`/`195123524` — 16 × Ø3 mm full-length grooves, 1.5 mm deep (count/size photo-estimated, low) |

No legacy part contradicts a book annotation. Every part still gets re-authored
as a reproduction script (project requirement); UNVERIFIED parts get their photo
re-measure during their M2 script build.

## Appendix C — Open items (must close before the milestone that needs them)

1. **Gear module + pressure angle** (ch. 12/13/25) — **RESOLVED in M4 prep:
   DP 30 (m = 0.8467 mm), PA 14.5° (assumed, unchanged).** Two independent
   measurements converge: (a) p.18 macro (`12_…/page002_img07`, 7 mm-callout
   scale 16.57 px/mm): rim silhouette striations at 22.3 px are the interleaved
   near/far tooth serrations (half-pitch — the steel drive gear's visibly
   coarser teeth in `page002_img02` corroborate), so p = 44.6 px = 2.69 mm vs
   DP 30's 2.66 mm; (b) p.18 cone view (`page002_img04`, 150 mm-arrow scale
   ≈ 4.83 px/mm): largest cone gear OD ≈ 105 ± 5 mm vs DP 30's 103.3 mm
   (m = 0.8 → 97.6 marginal, m = 1.0 → 122 excluded). Clincher: DP 30 makes
   every key PD a round inch value — largest cone / cylinder gear 4.000",
   pinion 1.400". The photogrammetry cross-check (`195445871`) was abandoned:
   through-glass color cast + parallax made the nameplate unusable.
   NOTE: ch. 23 translational gearing looks coarser than DP 30 in the video
   frames (`v4_transgear_*`) — its module is a separate question, measure when
   authoring those parts.
2. **Pinion tooth count** (ch. 25) — **RESOLVED in M4 prep: 42 teeth**
   (counted on engineerguy video 4/4 frame `v4_pinion_018`; see ch. 25
   section). Video stills live in `references/engineerguy-youtube/`
   (see its README to re-fetch the videos; mp4/stills not committed).
3. **Channel pitch** — **RESOLVED in M6: 7.5 mm along the cone axis,
   7.06 mm projected on the machine depth (Z)**, uniform with the gear
   stack (vertical connecting rods, no splay). Measured on all four p.28
   end-view strips (400 dpi extraction): arm-end tip pitch ≈ 60 px vs tip
   width ≈ 20 px = the 2.5 mm arm plate (annotated p.27) → pitch ≈ 3.0 ×
   2.5 = 7.5 mm. Self-consistent: 20 ends × 60 px ≈ 1140 px of the 1512 px
   strip. The 16 mm candidate is refuted.
   Z-projection refinement (M6.7 supersedes the M6.2/M6.6 readings):
   the 7.5 annotation's Z-projection 7.5 × cos(arcsin(2.54/7.5)) =
   7.0568 mm is the FRAME-LOCKED drum/channel grid — stack spans
   19 × 7.0568 ≈ 134.1 mm, ~2.8 mm air per side inside the gates'
   139.7 mm clear span (inner faces at Z = ±69.85). The cone-shaft
   incline then follows from exact tracking of perpendicular-seated
   gears (true cone, p.18): a gear square to the shaft contacts the
   parallel-axis drum via the tooth at the drum-facing azimuth, which
   sits r·sin θ along-shaft south of the gear centre, so the 20 mesh
   centres are collinear iff the radius step tracks per DRUM pitch:
   7.0568 sin θ = 2.54 → θ = arcsin(2.54/7.0568) = 21.0976° (the
   earlier arcsin(2.54/7.5) = 19.8° put the tracking on the wrong leg
   of the triangle — 0.44 mm/station z-drift, "most gears not
   meshing"; atan = 18.7° was doubly wrong). Along-shaft seat pitch
   7.0568 × cos θ = 6.5839 (forces the 6.5 face, ch. 12 rows). The
   incline lies in the HORIZONTAL plane: the cone sits beside the drum
   at the same height and converges on it toward the small end (ch. 12
   p.18 top-down photo; the eight-views side view shows the cone
   midline near-level) — see "Drive-train layout" in the ch. 13
   section. Cross-check: tan(cone half-angle) = 2.54/6.5839 = tan θ,
   so the cone's drum-side generator runs parallel to the drum axis —
   exactly the p.18 seam.
4. **Rocker arm working length** — RE-RESOLVED in M6.3 (supersedes the
   M2 100/70 model): symmetric ±88 about the pivot, rod pin at +25.4 —
   see the ch. 14 "Rocker pivot & supports layout" table. The M2 read
   put the connecting rods at the arm tips; ch. 15's "positive one side,
   negative the opposite side" plus the vertical-rod/arbor-x closure
   refutes that.
5. **Feature mapping of the 16 mm (ch. 14) and 32 mm (ch. 17) callouts** —
   ch. 14 16 mm RESOLVED in M2 = rocker arm end-face depth (see ch. 14
   table). ch. 17 32 mm RESOLVED in M2 = spring coil body length (ch. 17
   table, annotated high).
6. **Cylinder-set axial budget** (ch. 13) — **RESOLVED in M6**: p.22
   stack macro (400 dpi) measures gear face / axial pitch = 190/497 px
   ≈ 0.38 → face 3.0 mm; budget per 7.5 mm channel = face 3.0 + cam 3.5
   (0.5 air per side in the 4.5 gap) with the 3.0 rod ring riding the cam
   (0.25 axial clearance per side). Legacy 10.2 cam thickness refuted;
   `build_cylinder_gear.py` updated (face 7 → 3, cam 10.16 → 3.5). The
   ch. 12 "7 mm" face callout applies to the CONE gears, trimmed to 6.5
   in M6.7 by the 6.584 exact-tracking seat pitch (ch. 12 face row).
7. **Small cone gears cannot carry the 9.5 mm shaft bore** (ch. 12) —
   **RESOLVED in M4c: configured bore + stepped shaft, no keyway.** At
   DP 30 the 6T gear's OD is 6.77 mm and the 12T root circle is 8.0 mm,
   both smaller than the 9.5 mm cone shaft. Resolution: the cone-gear
   part carries a configured `BoreDia` global computed by `bore_dia_in`
   (snug on the shaft section at the seat: 3/8" T024–T120, 1/4" T018,
   3/16" T012, 1/8" T006 — M6.7 perpendicular seats need no ellipse
   margin) and the shaft (`build_cone_gear_shaft.py`)
   steps 3/8 → 1/4 → 3/16 → 1/8" at stations 136.88/143.47/150.05
   (each in the 0.08 air gap between gear faces, ch. 12 rows). No
   keyway anywhere: the book never shows the attachment and the p.21
   macro shows solder blobs at the small gears, so gears are modeled
   plain-bored (key/solder hardware out of scope). Implementation note:
   the configured bore forced the gear blank from a revolve to an
   extruded disc — on SW 2026 a dimension-driven cut through a revolved
   body freezes at its creation-time size (skill learning
   `cut-on-revolved-body-freezes-at-creation-size.md`).
8. **Translational gearing fixed-reduction topology** (ch. 23) — found in
   M4c keyframe measurement: a small fine-tooth steel pinion (≈ Ø21 mm,
   est. 24T DP 30) rides coaxially with the 120T rack pinion
   (`v4_transgear_002/003/008`), but the frames do not show what it meshes,
   nor which shafts carry the two chain wheels vs the removable 12/18/24
   pair.
   **M6.8 topology resolution** (ch. 23 PDF + `v4_transgear_002/008/012`
   + ch30 p002 full-res): the stud carries the 96T disc + latch big hub;
   the KNOB SHAFT (latch small hub) carries the fine 24T pinion — it is
   NOT coaxial with the disc; the M4c read conflated the two shafts —
   plus a chain-wrapped removable; the crankshaft carries the second
   chain-wrapped removable. The bead chain rides the removables' m2
   teeth directly (no separate sprockets), which is how gear swaps
   change the platen ratio and why the latch slackens the chain.
   **Open kinematic riddle:** a rigid latch arm pivoting on the stud has
   ONE c2c, but engaged mesh needs 51.0 (96T PD 81.28 + 24T PD 20.32 +
   0.4)/2 while the ch30 rest pose measures 66.05 — the real pivot or a
   slotted arm must provide the travel; not resolvable from available
   photos. Modeled: the rest state exactly (latch at c2c 66.05, −10.22°),
   engagement left conceptual.
9. **Crank-drive gear pair** (ch. 11/12) — found in M4c: the dark steel
   gear at the cone set's large end ("This gear engages the crank",
   p.20) implements the stated 4:1 crank→cone reduction together with a
   pinion on the crankshaft; neither part is in any legacy source. Teeth
   are visibly ~1.5–2× coarser than the train and not countable in the
   available photos. Estimate, RE-ANCHORED with the OD 62.2 train: DP
   26.57 (= DP_TRAIN·64/120), drive gear 64T (PD 61.18 mm, OD ≈ 63.1 ≈
   the 120T cone gear's 62.2 — the p.20 "OD ≈ cone 120T" match holds),
   crank pinion 16T (PD 15.3). The 4:1 ratio is book-stated and fixed;
   only the DP/tooth split is estimated.
   **M6.2 ratification (now BROKEN by the 62.2 anchor):** the rescaled
   64T+16T centre distance is 38.24 mm, no longer the 63.5 that matched
   the measured 67 ± 5 mm crank-to-cone distance. The whole drive train
   shrank with the 62.2 OD, pulling the crank ~67 mm inboard (pedestal
   derived +55 vs photo +122) — flagged with the crankshaft row. Either
   the crank-distance photo or the 62.2 reading is wrong.
10. **Alignment-pinion mechanism removed** (ch. 25) — 2026-06-18. At the
   re-anchored OD 62.2 / DP 49.82 the Ø22.4 mm pinion drum cannot thread
   the 12.56 mm channel between the rocker-support frustum (x −28.45) and
   the rescaled 64T (tip west edge x −15.89): a ~9.9 mm shortfall no
   position or pivot topology can resolve (the drum is one rigid cylinder
   at a single x for its whole z-length). The drum + straps + blocks +
   torque shaft + lift rod + lever + handle were dropped from
   `build_drive_train_assembly.py` pending a rework once the gear OD is
   confirmed. The retired DP-30 layout (and the former entries #10/#11 on
   the 0.28 mm face shave and the parked lift-rod cam pins) are in git
   history. See the "Alignment-pinion layout — REMOVED" section above.



