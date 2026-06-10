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
| Alignment notch depth | 3 mm | 0.118 | text p.22 (also pp. 66–67) | stated | high |
| Gear material | brass (polished) | — | text p.22 | stated | high |
| Axial pitch | 7.5 mm | 0.295 | must match cone-set axial pitch (ch. 12) | derived | med |
| Gear outer diameter | OPEN | — | count teeth + module from ch.12 resolution | — | — |
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
