---
name: physical-build-intent
description: The model is destined for a real physical build once validated — manual mill+lathe primary, PM-30MV CNC for repetitive parts, period brass+steel
metadata:
  type: project
---

The harmonic-analyzer model is not display-only: the user (Pedro) intends to **physically machine
the entire machine** in **period brass + steel** once the model is ready and validated. This makes
DFM/DFA and the tolerance/fits work load-bearing, not academic.

Toolchain (as of 2026-07-04):
- **Primary: manual machining** — manual mill + lathe with DROs (one-off parts).
- **PM-30MV — CNC** (not manual) — available for **repetitive work**: the 20 cams, 19 spacer
  bushings, the 20-pair cone/cylinder gear train, i.e. the high-count parts where channel-to-channel
  consistency is hardest to hold by hand.
- Casting: wanted (period brass/iron blanks) but unlikely due to time.
- **CAM tool = Fusion 360** (Autodesk Makers/personal SKU, bundles CAM). External tool — so
  SOLIDWORKS CAM availability is moot. Primary feed is **STEP** (the 3D solid, already emitted by
  `SaveAs3` in `export_models.py`/`cut_release.py`) → Fusion → G-code. **STEP is the CAM feed, not
  DXF**; DXF is a narrow 2D niche (flat parts, 2.5D cam/gear-tooth profiles, inspection overlays).
  CAM cuts nominal → the toleranced 2D print (§8) carries fits/finish, not the STEP.

**Doc state (resolved 2026-07-04):** [[tolerance-gdt-assessment]] `docs/tolerance-gdt-assessment.md`
§11 and `docs/tolerance-policy.md` "Scope of manufacturing outputs" were revised to match this
toolchain: **CAM = IN SCOPE** (deferred until the nominal model is frozen/validated; targets the
20 cams / 19 spacers / gear train) and **DXF = IN SCOPE** as CNC 2.5D-profile input (was "optional
exhibit"). Manual mill+lathe stay primary for one-off parts. The prior "no CNC / manual-only"
assumption is corrected in-doc. The §4 "numbers don't close" Findings (fit-class vs linear-grade
mismatch, Ø6.5/6.35 pivot clearance, R800 vs 812.8 rocker radius) are the validate-before-cutting-
metal gate and must close before CAM authoring.

**How to apply:** treat tolerances/fits/surface-finish as real manufacturing outputs (see
`docs/tolerance-policy.md`), not render metadata; when scoping drawings/DXF/CAM, remember CNC exists
for repeat parts. Fidelity-to-original constrains DFA part-count reduction (don't consolidate away
period brackets/screws).

**Real-build findings (2026-07-04, from `docs/machining-dfm.md` "How to get this reviewed"):**
- **Automated DFM false-greens on this machine.** DFMPro (SW add-in) AND Xometry's auto-DFM both
  passed every SLDPRT — but miss the real hazards (sharp internal corners at every gear-tooth root +
  the cam notch; sub-mm walls like T006 0.49mm). Don't trust an automated-DFM green here.
- **Fusion 360 CAM verify is the primary automated check the user banks on.** It simulates the real
  tool vs the real solid, so it DOES surface sharp internal corners (as un-cut stock) + reach/gouge/
  collision — the class DFMPro misses. Blind spot: rigid geometry + held stock, so it will NOT catch
  thin-wall breakage / slender-shaft whip / tiny-part workholding (T006 0.49mm wall, Ø0.79×34mm shaft,
  1.90mm cam wall) → those need a first-article cut, not a clean sim.
- **Gear cutters for DP 49.82 don't exist commercially** (searched). Plan: **self-made form cutters
  via the Eureka method** (`references/gears-and-gear-cutting/` ch. 12), teeth cut indexed on a
  dividing head. Wire-EDM/hobbing are outsource alternates only (the shop has no 2D cutters).
