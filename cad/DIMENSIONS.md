# Harmonic Analyzer — Dimension Source of Truth

Single source of truth for all part/assembly dimensions used by the reproduction
scripts in `cad/scripts/`. Built in Milestone 1 from the book
`references/albert-michelsons-harmonic-analyzer` (chapters 11–25, one component
each), cross-checked against the legacy `cad/Parts/*.cs` / `cad/kcl-archive/*.kcl`
dimensions.

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

Photo evidence: besides the book, 89 first-party photos of the machine exist in
`photogrammetry/raw/` — indexed per component in `cad/PHOTOS.md`. Use them for
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
| Crank arm length (center-to-center) | ~150 mm | ~5.9 | p.14 photo vs cone-gear 150 mm axial length in frame | scaled | low |
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

## Chapter 12 — Cone Gear Set (pp. 16–21)

| dim | value | (in) | source | method | confidence |
|---|---|---|---|---|---|
| Gear face width | 7 mm | 0.276 | photo callout p.18 | annotated | high |
| Cone set axial length | 150 mm | 5.91 | photo callout p.18 | annotated | high |
| Gear count | 20 | — | text p.16 | stated | high |
| Tooth counts | 6, 12, 18 … 120 (step 6) | — | text p.16 | stated | high |
| Crank→cone reduction | 4:1 (1 crank turn = 1/4 cone turn) | — | text p.16 | stated | high |
| Axial gear pitch | 7.5 mm | 0.295 | 150 mm / 20 gears (leaves 0.5 mm gap at 7 mm face) | derived | med |
| Diametral pitch / module | DP 30 (m = 0.8467 mm) | — | M4 prep, two independent measurements converge (see Appendix C #1 — resolved): p.18 photo tooth pitch 2.69 mm via 7 mm-callout scale; largest-gear OD ≈ 105 ± 5 mm via 150 mm-arrow scale (DP 30 → 103.3). Gives round-inch PDs: largest cone / cylinder gear PD = 120/30 = 4.000", pinion PD = 1.400" | scaled ×2 + period argument | high |
| Pressure angle | 14.5° assumed | — | period-typical; not stated anywhere | derived | low |
| Cone shaft length | ~225 mm | ~8.9 | derived: 150 stack + small-end pinion seat ~15 + bearing post ~35 (p.18 top-down) + large-end pivot journal ~25 | derived | low |
| Cone shaft diameter | stepped: 9.5 (3/8") y 0–152.5, 6.35 (1/4") to 160, 4.76 (3/16") to 167.5, 3.175 (1/8") to 225 (large/pivot end at y 0) | 0.375/0.25/0.1875/0.125 | base dia legacy `parameters.kcl` ShaftDiameter; steps = gear bores (Appendix C #7 resolution): small gears can't clear 3/8", and p.18 shows a visibly thin rod past the smallest gears — `build_cone_gear_shaft.py` | legacy + derived | med |
| Gear bores (configured `BoreDia`) | 9.5 (3/8") T024–T120; 6.35 (1/4") T018; 4.76 (3/16") T012; 3.175 (1/8") T006; no keyway | 0.375/0.25/0.1875/0.125 | Appendix C #7 resolution; 6T wall 0.8 mm matches the thin tip rod (p.18); p.21 macro shows solder blobs fixing the small gears — no keyway evidence anywhere | derived | med |
| Crank-drive gear (dark steel gear at the large end, "This gear engages the crank" p.20) | coarser pitch than DP 30, est. DP 16: ~64T, PD 4" (OD ≈ cone 120T's); mates a ~16T crank pinion (4:1) | — | p.20 annotation + visibly ~1.5–2× coarser teeth than the 120T beside it; tooth counts NOT countable in available photos — est. from the stated 4:1 + round-PD argument (see Appendix C #9) | scaled | low |

Notes: all 20 gears fixed to one shaft, rotate together. Engagement with cylinder
gears is at an oblique angle (partial engagement → distinct wear). The four smallest
gears (6–24T) look yellower — possibly a harder metal. Cone set pivots out of
engagement via a knob (for sine/cosine alignment, ch. 25). A 6-tooth involute gear
is severely undercut at standard proportions — `build_cone_gear.py` (M4) models it
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
| Tooth count | 120 (each gear) | — | derived from gear law k/80 (ch.29) + 4:1 + cone teeth 6k — see ch.6/26/29 section | derived | high |
| Alignment notch depth | 3 mm | 0.118 | text p.22 (also pp. 66–67) | stated | high |
| Gear material | brass (polished) | — | text p.22 | stated | high |
| Axial pitch | 7.5 mm | 0.295 | must match cone-set axial pitch (ch. 12) | derived | med |
| Gear outer diameter | 103.3 mm (4.067") | 4.067 | (120+2)/DP30; PD = 4.000" exactly (module closed — ch. 12 row) | derived | high |
| Cam diameter (integral cam per gear) | 50.8 mm (2.0") | 2.0 | legacy `parameters.kcl`; M2 check: p.25 printed outline measures cam OD ≈ 0.52 × cylinder-gear OD → 0.52 × 103.3 = 53.7 vs legacy 50.8 (5% — within the outline-measurement error); keep the legacy round 2.0" | legacy + scaled ratio | med |
| Cam thickness | 10.2 mm (0.4") | 0.4 | legacy `parameters.kcl` | legacy | med |
| Cam eccentricity | 5.1 mm (0.2") | 0.2 | legacy `parameters.kcl`; sets rocker-arm stroke; p.25 photo shows ≈ 4 mm center offset (within photo error) | legacy | med |
| Cam bore | 9.5 mm (3/8") | 0.375 | legacy `parameters.kcl` | legacy | med |
| Cam keyway | 3.2 × 1.5 mm (1/8" × 0.06") | 0.125 × 0.06 | legacy `parameters.kcl` | legacy | med |
| Cylinder shaft length | ~200 mm | ~7.9 | derived: 150 stack (20 × 7.5 axial pitch) + ~25 bearing journal each end (eight-views 8/8 pedestals) | derived | low |
| Cylinder shaft keyseat | 3.2 wide × 1.5 deep, lower end through stack span | — | mates the cam keyway (row above) | derived | low |

Notes: set is a sandwich — shiny brass gears alternating with black rough-finished
connecting rods. Each rod rides the cam on the gear to its right; cam converts
rotation to near-sinusoidal reciprocation of the rod → rocker arm. Notches aligned
to top = cosine mode; rotated 90° = sine mode (pp. 66–67).

M4 build (`build_cylinder_gear.py`): single non-configured part — 120T involute
ring (cone-gear equation-curve technique, toothed-disc volume reproduces the
cone gear's T120 configuration), integral cam boss (lobe −Y), bore + keyway
(+Y) through gear and cam, alignment notch at +Y. Notch width is unstated in
the book — modeled square (3 mm wide × 3 mm deep, low confidence). The
standalone `eccentric-cam` part (M2 legacy re-author) is superseded by the
integral cam for assembly purposes.

### Connecting rods (ch. 13 pp. 22–25 + ch. 14 p. 29; 20 used)

| dim | value | (in) | source | method | confidence |
|---|---|---|---|---|---|
| Centre distance (cam ring → rocker pin) | ~105 mm | ~4.1 | eight-views 8/8: cylinder shaft axis ~74 mm above base (A-frame 177.8 mm scale), rocker tip just above the A-frame top; visible black rod band ~104 mm agrees | scaled | low |
| Cam ring bore | 51.0 mm | 2.008 | cam OD 50.8 + 0.1 running clearance per side | derived | med |
| Cam ring radial wall | 5 mm (OD 61) | 0.20 | ch.13 photos, strap proportion vs cam | scaled | low |
| Ring / shank / tip-block thickness | 3 / 2.5 / 6 mm | — | sandwich budget (7.5 axial pitch) + p.29 tip blocks ~2.4× the strap | scaled | low |
| Shank width | 8 mm | 0.31 | ch.13 p.23 rod silhouettes vs 7 mm gear face | scaled | low |
| Tip block (flattened upper end) | 10 × 18, Ø2 pin hole centred | — | p.29 stepped blocks at the rocker tips; pin matches the rocker's Ø2 rod hole (ch. 14) | scaled | low |

The p.29 "stepped" tip profile (alternate rods offset to clear adjacent
rockers) is deferred — modeled as a plain block until the channel array
is laid out in M6 (Appendix C #6).

---

## Chapter 14 — Rocker Arms (pp. 26–29)

| dim | value | (in) | source | method | confidence |
|---|---|---|---|---|---|
| Arm plate thickness | 2.5 mm | 0.098 | photo callout p.27 (M2 re-read at 400 dpi; the M1 row misread this as a 12.5 mm "arm width") | annotated | high |
| Arm depth (end-face height) | 16 mm | 0.630 | photo callout p.29 — M2 zoom shows the arrows span the arm's end face vertically (NOT channel pitch) | annotated | high |
| Top-surface curvature radius | = amplitude bar length ≈ 800 mm | ≈ 31.5 | text pp. 26–27 ("equal to the length of amplitude bars" — minimizes nonlinearity) | stated | high |
| Arm count | 20 | — | photos/text | stated | high |
| Arm length | RESOLVED ~170 mm: ~100 mm pivot→rod end + ~70 mm tail | — | eight-views view 5/8 side photo (perspective-corrected; p.29 macro inflates the near end ~4×) + ch.16 half-arm ≈ 80 mm | scaled/derived | low-med |
| Pivot pin hole | Ø3 at the pivot, mid-depth | — | p.27/p.28 dark dots on the strap at the pivot | scaled | low |
| Connecting-rod pin hole | Ø2, 6 mm from the rod end, mid-depth | — | p.29 tip pins | scaled | low |

Notes: concave-upward curved top supports the amplitude bar; knife-edge/pivot
see-saw motion driven by vertical connecting rods from the cams. Labeled "pivot"
point = zero-coefficient position for the amplitude bar. Matte-black finish
(blackened cast/steel). End view p.28 shows the 20-arm array at uniform pitch.
Bottom edge concentric with the top (uniform 16 mm depth, R 816/800 arcs).
The stepped sawtooth blocks at the arm tips (p.29 top) are the connecting
rods' flattened upper ends — they belong to the connecting-rod part.
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
| Bar count | 20 | — | text | stated | high |

Notes: bottom notch rides/slides along the rocker arm for positioning (bar at
pivot = zero coefficient; opposite ends = 180° phase reversal). Chrome-like
finish. Legacy AmplitudeBar.cs survives the audit: both book-verifiable dims
(width, length) confirm it.

## Chapter 16 — Measuring Stick (pp. 34–37)

| dim | value | (in) | source | method | confidence |
|---|---|---|---|---|---|
| Overall length | 200 mm | 7.87 | photo callout pp. 34–35 | annotated | high |
| Division spacing | 8 mm | 0.315 | photo callout pp. 34–35 | annotated | high |
| Scale | 0–10, hand-stamped, uneven | — | text pp. 34–35 (0.5 tick longest; 0.4–0.5 gap < 0.5–0.6 gap) | stated | high |
| Scale span (10 divisions) | 80 mm | 3.15 | 10 × 8 mm | derived | med |
| Body width | ~15 mm | ~0.59 | pp. 34–35 photo proportion vs 200 mm length | scaled | low |
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
| Spring end hooks | bent-wire loops, both ends, extend axially | — | p.41 inset (feature only; modelling deferred to Phase 3 rebuild) | stated | high (feature) |
| Lever count | 20, cast metal, third-class | — | text pp. 38–39 | stated | high |
| Spring count | 20 | — | text pp. 38–39 | stated | high |
| Lever length (pivot→spring hole c2c) | ~240 mm | ~9.4 | p.38 inset vs 320 mm lever-bank width (20 × 16 mm ch.14 pitch); resolved in M2 | scaled | low |
| Lever bar section | ~12.5 wide × 9.5 thick | ~0.49 × 0.37 | width matches ch.14 arm callout; thickness vs spring OD p.39 | scaled | low |
| Lever fulcrum boss | ~Ø19 × 14 long, Ø6 pivot hole | — | p.40 bottom-left close-up | scaled | low |
| Lever tip | Ø3 spring-hook hole, ~8 mm overhang; fork/clip fittings deferred (photogrammetry 195527397) | — | p.39, p.40 | scaled | low |

Notes: each third-class lever pivots at its end (fulcrum), is driven by its
rocker arm/amplitude bar, and pulls one of 20 helical springs attached to the
pivoted summing lever below. Amplitude bar at rocker pivot → lever motionless;
at rocker edge → full amplitude; opposite end → 180° phase flip.

---

## Chapter 18 — Summing Lever (pp. 42–43)

No annotated or stated numeric dimensions in this chapter. Legacy SummingLever.cs
(from summing-lever.kcl) is the numeric source; nothing in the book contradicts it.

| dim | value | (in) | source | method | confidence |
|---|---|---|---|---|---|
| Coefficients plate | 44.5 × 152.4 × 5.1 mm | 1.75 × 6.0 × 0.2 | legacy | legacy | med |
| Pivot cylinder radius | 12.7 mm | 0.5 | legacy | legacy | med |
| Spring attachment holes | 20 × r 0.5 mm, spacing ≈ 6.95 mm | 20 × r 0.02, ≈ 0.274 pitch | legacy (5.2" span / 19) | legacy | med |
| Summation plate height | 76.2 mm | 3.0 | legacy | legacy | med |
| Summation anchor | r 9.5 × h 19.1 mm | r 0.375 × h 0.75 | legacy | legacy | med |
| Rib thickness / height | 5.1 / 12.7 mm | 0.2 / 0.5 | legacy | legacy | med |

Notes (stated, qualitative): cast iron; pivots on a knife-edge fulcrum; the 20
channel springs attach along the wide end; total motion is only a few mm
(magnified downstream by ch. 20–21). Re-scale plate proportions against p.42–43
photos during M2 rebuild.

## Chapter 19 — Counter Spring (pp. 44–45)

No annotated or stated numeric dimensions. No legacy part. M2 revision: the
first-pass ~45 × ~80 mm estimate was wrong — the book calls it "a long spring
[that] towers above the machine" and photogrammetry `195253322` shows the coil
spanning most of the gooseneck's run above the top casting (≈ 40 cm per ch. 6:
147 cm total − 107 cm column).

| dim | value | (in) | source | method | confidence |
|---|---|---|---|---|---|
| Coil body length | ~300 mm | ~11.8 | gooseneck rise (147−107 cm, ch. 6) minus curve; photogrammetry 195253322 + p.45 centre photo | scaled | low |
| Coil OD | ~22 mm | ~0.87 | p.45 top-right close-up: coil slightly narrower than the gooseneck tube (~25 mm) | scaled | low |
| Wire dia | ~2.5 mm | ~0.098 | p.45 close-up: heavy close-wound wire | scaled | low |
| Coil count | ~110 | — | body length / ~2.73 mm pitch (close-wound) | derived | low |
| Adjustment post | square-head screw on adjustable post | — | text pp. 44–45 | stated | high (feature) |

Notes: single large spring balancing the combined pull of the 20 channel springs
on the summing lever; tension adjustable via the square-head screw post.
Re-measure both dims from photos during the M2 build.

## Chapter 20 — Magnifying Lever (pp. 46–49)

No annotated or stated numeric dimensions. No legacy part.

| dim | value | (in) | source | method | confidence |
|---|---|---|---|---|---|
| Magnification | up to 4× (adjustable) | — | text pp. 46–49 | stated | high |
| Rod diameter | ~6 mm | ~0.24 | round brass rod, photo proportion | scaled | low |
| Lever rod length | ~310 mm (300 usable) | ~12.2 | 4× constraint vs summing-lever ~76 mm effective arm (300/76 ≈ 3.9); p.46 inset consistent; resolved in M2 | derived | low |
| Vertical rod | ~Ø5 × 150, domed ends | — | p.46/48 vs lever rod | scaled | low |
| Clamp block | ~20 × 26 × 12; Ø6.2 lever bore, Ø5.2 rod bore (skew, 6.5 off-axis), Ø3 screw hole | — | p.48 close-up | scaled | low |
| Thumb screw | ~Ø10 × 5 reeded head, Ø3 × 12 shank (×2: clamp + output fixture) | — | p.48; knurl/thread deferred to Phase 5 | scaled | low |
| Output fixture | collar ~Ø10 × 8, Ø5.2 bore, Ø3 cross hole | — | p.48 bottom close-up | scaled | low |

Notes: round brass rod lever; magnification set by a reeded (knurled) screw
adjustment that moves the effective fulcrum/attachment point. Geometry
constraint used in M2: output/input arm ratio = 4 at maximum setting (rod
ends domed; both rods revolves with hemispherical caps).

## Chapter 21 — Magnifying Wheel (pp. 50–53)

| dim | value | (in) | source | method | confidence |
|---|---|---|---|---|---|
| Inner hub diameter | 20 mm | 0.787 | photo callout pp. 50–53 (stated in text: "100 mm versus 20 mm") | annotated | high |
| Outer wheel diameter | 100 mm | 3.937 | photo callout pp. 50–53 | annotated | high |
| Magnification | 5× | — | text; consistent: 100/20 = 5 ✓ | stated | high |
| Spoke count | 6 | — | counted on the full-page photo p.51 (and photogrammetry `195607299`); an earlier extraction said 5 — wrong | stated | high |

Notes: wheel body is black-painted cast metal with a bright machined rim
(wire groove on the outer circumference); the inner hub is a grooved brass
drum (wire from magnifying lever wraps the hub, wire to pen mechanism leaves
the outer rim → 5× motion magnification). Six straight spokes. Hex-nut axle on
a horizontal support bar. The two annotated diameters self-validate against
the stated magnification — strongest-sourced part in chapters 18–21.

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

Notes: toothed brass rack along the bottom edge (driven by ch. 23 gearing for
horizontal travel); two brass clips (left/right) retain the recording paper;
gearing can be unlatched from the rack for free repositioning/reset.

## Chapter 23 — Translational Gearing (pp. 56–59)

| dim | value | (in) | source | method | confidence |
|---|---|---|---|---|---|
| Total gear count | 6 | — | text p.56 | stated | high |
| Removable gear set tooth counts | 12 / 18 / 24 (small/medium/large) | — | p.57 diagram captions | annotated | high |
| Rack & pinion | 2 of the 6 gears | — | text | stated | high |
| Chain drive | 2 gears (one at platen front, one on crankshaft) | — | text | stated | high |
| Fixed crank-speed reduction | 2 gears | — | text | stated | high |
| Rack & rack pinion pitch | DP 30 (machine system) | — | M4c keyframe measurement: with the rack pitch taken as DP 30 (2.66 mm), the rack pinion's vertical OD in `v4_transgear_030` measures ≈ 105 mm — matching a 120T DP 30 gear (103.3 mm) to 1.8%; quadrant tooth counts on `v4_transgear_028` give ~30–32/quadrant ≈ 120T | scaled + counted | med |
| Rack pinion | 120T, OD 103.3 mm (4.067"), thin disc ≈ 3 mm face, brass | 4.067 | rows above; thickness from edge-on view `v4_transgear_002` | scaled | med (face: low) |
| Removable gear module | 2.0 mm (≈ DP 12.7) | — | 24T gear OD ≈ 51 mm in `v4_transgear_030` (scale via DP 30 rack pitch) ⟹ m = OD/(N+2) ≈ 1.96; m = 2.0 makes every swap combo's centre distance m(12+24)/2 = 36 mm exactly | scaled | med |
| Removable gear face / bore / pins | ≈ 5 thick; common bore Ø12; 2 × Ø3.5 pin holes on Ø19 BC | — | `v4_transgear_015` (catalog shot) + `v4_transgear_020/025/030` (mounted on the oval-pin stub shaft) | scaled | low |
| Chain sprockets | 17T (both), roller chain ≈ 3/8" pitch, ≈ 4.5 thick, Ø9.525 bore | — | tooth counts from `v4_transgear_012` crops (16–17 counted; modeled equal ⟹ 1:1 chain); pitch from sprocket OD ≈ 56–60 px-scaled mm (17T @ 3/8": PD 51.8) | counted + scaled | low |
| Reduction pinion (coaxial with rack pinion) | est. 24T DP 30, OD ≈ 21 mm measured, face ≈ 6 | — | edge-on views `v4_transgear_002/003/008`: small fine-tooth steel pinion on the rack-pinion shaft | scaled | low |

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

## Chapter 24 — Pen Mechanism (pp. 60–61)

No numeric dimensions; modern reconstruction ("about 100 years younger than any
other part").

| dim | value | (in) | source | method | confidence |
|---|---|---|---|---|---|
| Square brass rod cross-section | ~5 mm | ~0.2 | photo proportion | scaled | low |
| Square rod length | ~120 mm, Ø2 wire hole near top | ~4.7 | p.64 inset; resolved in M2 | scaled | low |
| Frame (stirrup) | ~22 × 40 × 10, 5 mm rails, Ø3 set-screw hole in bottom rail | — | p.64–65 vs 5 mm rod; resolved in M2 | scaled | low |
| V-block | ~32 × 18 × 16; 6 mm 45° top chamfers; 2 × Ø8 vertical bores at x = 11/21; stopped clamp slit 26 long × 4 (y 4–8); Ø2.5 screw hole | — | p.65 close-up | scaled | low |
| Set screw | Ø9 × 5 knurled knob + Ø3 × 15 shank | — | p.64–65; knurl/thread deferred to Phase 5 | scaled | low |

Notes: brass frame holds the marker in a v-block; v-block on a square brass rod
attached to the wire from the magnifying wheel (vertical motion); platen provides
horizontal motion. Small set screw adjusts pen angle to paper to cut friction.
Provenance (ch. 5 Preface): the original pen holder was missing — the one in all
book photos is a modern replacement designed/built by Mike Harland and Tom
Wilson. Model the replacement (it is what the photos document).

## Chapter 25 — Pinion Gear (pp. 66–69)

| dim | value | (in) | source | method | confidence |
|---|---|---|---|---|---|
| Tooth count | 42 | — | counted on the drum end view (engineerguy video 4/4 @ 8:00, frame `v4_pinion_018`): 7 tips per 60° sector × 6; tip-radius ratio to the meshing 120T cylinder gear = 0.36 = 44/122 confirms same DP | counted | high |
| Pitch diameter | 35.56 mm (1.400") | 1.400 | 42 / DP 30 — round-inch PD corroborates both the count and DP 30 | derived | high |
| Outer diameter | 37.25 mm (1.467") | 1.467 | (42+2)/30 | derived | high |
| Drum length | ~150 mm | ~5.9 | spans/engages all 20 cylinder gears at once (p.67 photo: drum ≈ cylinder stack length = 20 × 7.5 axial pitch) | derived | med |
| Material | brass | — | photos | stated | high |

Notes: single pinion — a long toothed drum, engaged via a small ball-handle
lever, meshes the cylinder gear set and turns all 20 cylinder gears as one —
used only during setup to align the 3 mm notches (top = cosine, 90° = sine)
after pivoting the cone set out of engagement. The "small gear" visible on the
lever arm in the p.68–69 photos is the drum's front end face, not a separate
idler (video frame `v4_pinion_018` shows the drum receding behind it).

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
| rocker-arm-support ×3 | none | UNVERIFIED — photo scaling in M2 |
| oscilating-arms | ch.14 re-read: the "12.5 mm width" was a misread (callout is 2.5 mm plate thickness) | SUPERSEDED — re-authored as rocker-arm with corrected dims (`build_rocker_arm.py`) |
| corner-bracket | none — no source either; geometry interrogated live from the SLDPRT (face inventory): base 1.125" × 0.75", height 2.3", plate 0.3" thick, sides tangent-tapered to R0.5" crown (centre 1.8" up), Ø0.4" lug hole, #9 (Ø0.196") foot hole | RE-AUTHORED — `build_corner_bracket.py` reproduces it to 13,035 mm³ (exact volume match) |
| tube-frame | ch.6: frame column height 107 cm — legacy file measured 1016 mm (40"), CONTRADICTS the book | RE-AUTHORED — `build_tube_frame.py` at 1070 mm (book wins), Ø1.375" × 0.12" wall from legacy. Fluted/reeded columns (PHOTOS.md `195108425`, `195123524`) deferred as cosmetic to M4 |

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
3. **Channel pitch** — M2 re-read: the ch. 14 "16 mm" callout measures the
   rocker arm's end-face depth, NOT pitch, so the 16 mm pitch candidate now
   rests only on the top-down fit (base 46 cm → 20 × 16 mm = 320 mm with
   ~70 mm margin per side, plausible vs the lever bank). 7.5 mm axial gear
   pitch (ch. 12 derived) still holds for the gear stack. Confirm 16 mm
   against the end-view photo (p. 28) before the M6 channel array.
4. **Rocker arm working length** — RESOLVED in M2: eight-views view 5/8
   side photo agrees with the ch. 16 derivation (~80 mm working half);
   modeled 100 mm rod side / 70 mm tail (`build_rocker_arm.py`).
5. **Feature mapping of the 16 mm (ch. 14) and 32 mm (ch. 17) callouts** —
   ch. 14 16 mm RESOLVED in M2 = rocker arm end-face depth (see ch. 14
   table). ch. 17 32 mm still to identify when finishing that chapter.
6. **Cylinder-set axial budget** (ch. 13) — needed by M6 channel array.
   The 7.5 mm axial pitch must fit gear face + integral cam + rod ring,
   but the legacy cam thickness (10.2 mm) alone exceeds it. M2 modeled
   the rod ring at 3 mm; re-measure gear face / cam / ring thicknesses
   from ch. 13 macro photos (or photogrammetry `195445871`) and reconcile
   the eccentric-cam part before assembling a channel.
7. **Small cone gears cannot carry the 9.5 mm shaft bore** (ch. 12) —
   **RESOLVED in M4c: configured bore + stepped shaft, no keyway.** At
   DP 30 the 6T gear's OD is 6.77 mm and the 12T root circle is 8.0 mm,
   both smaller than the 9.5 mm cone shaft. Resolution: the cone-gear
   part carries a configured `BoreDia` global — 3/8" (T024–T120), 1/4"
   (T018), 3/16" (T012), 1/8" (T006; 0.8 mm wall matches the visibly
   thin tip rod in p.18) — and the shaft (`build_cone_gear_shaft.py`)
   steps 3/8 → 1/4 → 3/16 → 1/8" at the same stations (ch. 12 rows). No
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
   nor which shafts carry the two 17T sprockets vs the removable 12/18/24
   pair. All six gear parts are authored individually; resolve the shaft
   layout (and re-check the reduction pinion's tooth count against the
   required k/80→platen-speed law) when mating the drive train in M6.
9. **Crank-drive gear pair** (ch. 11/12) — found in M4c: the dark steel
   gear at the cone set's large end ("This gear engages the crank",
   p.20) implements the stated 4:1 crank→cone reduction together with a
   pinion on the crankshaft; neither part is in any legacy source. Teeth
   are visibly ~1.5–2× coarser than the DP 30 train and not countable in
   the available photos. Working estimate (round-PD argument, mirrors
   the DP 30 resolution): DP 16, drive gear 64T (PD 4.000", OD ≈ the
   120T cone gear's, matching p.20), crank pinion 16T (PD 1.000").
   Author both as M4 parts at the estimate; re-measure/ratify when the
   drive train is mated in M6 (the 4:1 ratio itself is book-stated and
   fixed — only DP/tooth-count split is estimated).



