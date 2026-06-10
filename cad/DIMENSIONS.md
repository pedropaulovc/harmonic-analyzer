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
| Diametral pitch / module | OPEN | — | count teeth + scale a pitch dia from photo in M4 prep | — | — |
| Pressure angle | 14.5° assumed | — | period-typical; not stated anywhere | derived | low |

Notes: all 20 gears fixed to one shaft, rotate together. Engagement with cylinder
gears is at an oblique angle (partial engagement → distinct wear). The four smallest
gears (6–24T) look yellower — possibly a harder metal. Cone set pivots out of
engagement via a knob (for sine/cosine alignment, ch. 25). A 6-tooth involute gear
is severely undercut at standard proportions — expect a stub/pin-tooth form; resolve
during M4 gear pipeline prototyping.

## Chapter 13 — Cylinder Gear Set (pp. 22–25)

| dim | value | (in) | source | method | confidence |
|---|---|---|---|---|---|
| Gear count | 20, all identical size | — | text p.22 | stated | high |
| Tooth count | 120 (each gear) | — | derived from gear law k/80 (ch.29) + 4:1 + cone teeth 6k — see ch.6/26/29 section | derived | high |
| Alignment notch depth | 3 mm | 0.118 | text p.22 (also pp. 66–67) | stated | high |
| Gear material | brass (polished) | — | text p.22 | stated | high |
| Axial pitch | 7.5 mm | 0.295 | must match cone-set axial pitch (ch. 12) | derived | med |
| Gear outer diameter | 120 × module; module still OPEN | — | scale OD from ch.13 photos (= largest cone gear dia) | — | — |
| Cam diameter (integral cam per gear) | 50.8 mm (2.0") | 2.0 | legacy `parameters.kcl`; cam outline printed p.25 — verify by scaling p.25 outline in M2 | legacy | med |
| Cam thickness | 10.2 mm (0.4") | 0.4 | legacy `parameters.kcl` | legacy | med |
| Cam eccentricity | 5.1 mm (0.2") | 0.2 | legacy `parameters.kcl`; sets rocker-arm stroke | legacy | med |
| Cam bore | 9.5 mm (3/8") | 0.375 | legacy `parameters.kcl` | legacy | med |
| Cam keyway | 3.2 × 1.5 mm (1/8" × 0.06") | 0.125 × 0.06 | legacy `parameters.kcl` | legacy | med |

Notes: set is a sandwich — shiny brass gears alternating with black rough-finished
connecting rods. Each rod rides the cam on the gear to its right; cam converts
rotation to near-sinusoidal reciprocation of the rod → rocker arm. Notches aligned
to top = cosine mode; rotated 90° = sine mode (pp. 66–67).

---

## Chapter 14 — Rocker Arms (pp. 26–29)

| dim | value | (in) | source | method | confidence |
|---|---|---|---|---|---|
| Arm width | 12.5 mm | 0.492 | photo callout p.27 | annotated | high |
| Secondary dim (p.29) | 16 mm | 0.630 | photo callout p.29 — likely channel pitch or arm height; identify exact feature in M2 | annotated | high (value), low (feature mapping) |
| Top-surface curvature radius | = amplitude bar length ≈ 800 mm | ≈ 31.5 | text pp. 26–27 ("equal to the length of amplitude bars" — minimizes nonlinearity) | stated | high |
| Arm count | 20 | — | photos/text | stated | high |
| Arm length | OPEN — see ch. 16 note: half-arm = 10 measuring-stick divisions | — | derive from measuring stick + photo scaling in M2 | — | — |

Notes: concave-upward curved top supports the amplitude bar; knife-edge/pivot
see-saw motion driven by vertical connecting rods from the cams. Labeled "pivot"
point = zero-coefficient position for the amplitude bar. Matte-black finish
(blackened cast/steel). End view p.28 shows the 20-arm array at uniform pitch.

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

Notes: ruled brass gauge (Wm. Gaertner & Co.) with a sliding/locking stop. The
0–10 scale spans "the 10 equal divisions of one half of the rocker arm" → half
rocker-arm working length ≈ 80 mm → rocker-arm working length ≈ 160 mm. This is
the top-down channel-geometry anchor; cross-check against the 16 mm callout in
ch. 14 and photo scaling during M2. Model the nominal 8 mm spacing (not the
hand-stamping error).

## Chapter 17 — Springs and Levers (pp. 38–41)

| dim | value | (in) | source | method | confidence |
|---|---|---|---|---|---|
| Spring dimension (p.40–41 callout) | 32 mm | 1.260 | photo callout — free length or coil OD; identify exact feature in M2 | annotated | high (value), low (feature mapping) |
| Lever count | 20, cast metal, third-class | — | text pp. 38–39 | stated | high |
| Spring count | 20 | — | text pp. 38–39 | stated | high |
| Lever length | OPEN | — | scale from p.40–41 photos vs 32 mm spring callout in M2 | — | — |
| Spring wire dia / coil count | OPEN | — | scale from p.40–41 close-up in M2 | — | — |

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

No annotated or stated numeric dimensions. No legacy part.

| dim | value | (in) | source | method | confidence |
|---|---|---|---|---|---|
| Coil OD | ~45 mm | ~1.77 | "large-diameter" vs channel springs (32 mm callout, ch. 17); photo proportion | scaled | low |
| Free length | ~80 mm | ~3.1 | p.44–45 photo proportion | scaled | low |
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
| Lever length | OPEN | — | scale from p.46–49 photos in M2; arm ratio must give 4× at max setting | — | — |

Notes: round brass rod lever; magnification set by a reeded (knurled) screw
adjustment that moves the effective fulcrum/attachment point. Geometry
constraint for M2: output/input arm ratio = 4 at maximum setting.

## Chapter 21 — Magnifying Wheel (pp. 50–53)

| dim | value | (in) | source | method | confidence |
|---|---|---|---|---|---|
| Inner hub diameter | 20 mm | 0.787 | photo callout pp. 50–53 | annotated | high |
| Outer wheel diameter | 100 mm | 3.937 | photo callout pp. 50–53 | annotated | high |
| Magnification | 5× | — | text; consistent: 100/20 = 5 ✓ | stated | high |
| Spoke count | 5 | — | photos | stated | high |

Notes: brass; inner hub is grooved (wire from magnifying lever wraps the hub,
wire to pen mechanism leaves the outer rim → 5× motion magnification).
Five-spoke wheel. The two annotated diameters self-validate against the stated
magnification — strongest-sourced part in chapters 18–21.

---

## Chapter 22 — Platen (pp. 54–55)

| dim | value | (in) | source | method | confidence |
|---|---|---|---|---|---|
| Front face height | 140 mm | 5.51 | photo callout p.55 | annotated | high |
| Width (travel direction) | ~200 mm | ~7.9 | p.55 front photo proportion vs 140 mm height | scaled | low |
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
| Module / diameters | OPEN | — | resolve with ch. 12/13 gear-pitch question in M4 prep | — | — |

Notes: speed combos — small driving + large driven = slowest platen (smallest
horizontal scale), large+small = fastest, medium+medium = 1:1. Latch disengages
gearing from the platen rack (quick reset; also slackens chain for swapping the
removable gears). Brass gears, central bores.

## Chapter 24 — Pen Mechanism (pp. 60–61)

No numeric dimensions; modern reconstruction ("about 100 years younger than any
other part").

| dim | value | (in) | source | method | confidence |
|---|---|---|---|---|---|
| Square brass rod cross-section | ~5 mm | ~0.2 | photo proportion | scaled | low |
| Frame envelope | OPEN | — | scale from p.60–61 photos in M2 | — | — |

Notes: brass frame holds the marker in a v-block; v-block on a square brass rod
attached to the wire from the magnifying wheel (vertical motion); platen provides
horizontal motion. Small set screw adjusts pen angle to paper to cut friction.
Provenance (ch. 5 Preface): the original pen holder was missing — the one in all
book photos is a modern replacement designed/built by Mike Harland and Tom
Wilson. Model the replacement (it is what the photos document).

## Chapter 25 — Pinion Gear (pp. 66–69)

| dim | value | (in) | source | method | confidence |
|---|---|---|---|---|---|
| Tooth count | OPEN — visible in photos, never stated; count from p.67–69 photos in M4 prep | — | — | — | — |
| Material | brass | — | photos | stated | high |

Notes: single pinion, engaged via a small lever, meshes the cylinder gear set and
turns all 20 cylinder gears as one — used only during setup to align the 3 mm
notches (top = cosine, 90° = sine) after pivoting the cone set out of engagement.
Must span/engage the cylinder set; geometry resolved with the ch. 12/13 module
question.

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
| oscilating-arms | ch.14: width 12.5 mm, curvature R ≈ 800 mm | AUDIT in M2 — check both against part |
| corner-bracket | none | UNVERIFIED |
| tube-frame | ch.6: frame column height 107 cm | AUDIT in M2 — check tube length against 107 cm |

No legacy part contradicts a book annotation. Every part still gets re-authored
as a reproduction script (project requirement); UNVERIFIED parts get their photo
re-measure during their M2 script build.

## Appendix C — Open items (must close before the milestone that needs them)

1. **Gear module + pressure angle** (ch. 12/13/23/25) — needed by M4. Tooth
   counts now fully known (cone 6k, cylinder 120 derived); remaining unknown is
   module only. Plan: scale a cylinder-gear OD from ch.13 photos against the
   7 mm face / 150 mm cone references (cylinder gear PD = largest cone gear PD
   = 120 × module); assume PA 14.5° unless tooth profile photos contradict.
2. **Pinion tooth count** (ch. 25) — count from p.67–69 photos in M4 prep.
3. **Channel pitch** — candidates: 7.5 mm axial gear pitch (ch. 12 derived) vs
   16 mm callout (ch. 14). These may both be real (gears packed tighter than
   rocker arms, connecting rods fan out). Resolve top-down: base is 46 cm wide
   (ch. 6) → 20 channels at 16 mm = 320 mm fits with ~70 mm margin per side;
   confirm against end-view photo (p. 28) before M6 channel array.
4. **Rocker arm working length** — measuring stick implies half-arm ≈ 80 mm
   (ch. 16); reconcile with arm photos in M2.
5. **Feature mapping of the 16 mm (ch. 14) and 32 mm (ch. 17) callouts** —
   identify which feature each annotates when building those parts in M2.



