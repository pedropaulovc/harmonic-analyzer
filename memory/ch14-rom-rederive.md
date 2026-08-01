---
name: ch14-rom-rederive
description: 2026-07-02 rocker ROM re-derive — cam ecc 8.64 measured from ch14 end views, lobe flipped +Y, LEVEL rest pose co-solved, template-cam reconciliation, low rod pin + tombstone Y-head
metadata:
  type: project
---

**2026-07-02 (branch `ch14-rom-rederive`, same day as [[ch30-gt-reanchor]]):**
the rocker range of motion was re-derived from the ch14 book photos and the
whole cam→rocker→rod chain re-authored around it.

- **Cam eccentricity is MEASURED now, not scaled: 8.64 mm** (was 3.06 = 0.6022 ×
  legacy 5.08). Least-squares cos fit of the 20 rocker-tip heights in the ch14
  end views gives tip half-amplitude 9.458 mm; scaled down the 139.5 tip lever
  to the 127.37 rod lever → 8.64 (plausible-scale band 8.2–9.1). The 0.6022
  gear-OD rescale was never valid for the throw — the stroke is set by the
  rocker ROM, not the gear module.
- **Lobe points +Y (toward the notch) — the old model was 180° off.** At 0
  cranks (notch up = cos mode) the end views show all 20 tips in a flat LEVEL
  row at the TOP of the stroke: cos reads +1 at home, so the lobe is UP.
  **2026-08-01 clarification (PR #458 user catch): the photographed tips are
  the ROD-SIDE arm ends** — each bright tip sits directly atop its
  matte-black connecting rod in the end views, and the 139.5 tip lever is
  just past the 132.76 rod hole (nowhere near the ~130 tail). So the chain
  reads: lobe UP ⇒ ring at TOP ⇒ ROD SIDE at its highest (= the level rest)
  at cos home, and the working stroke dips the ROD SIDE below level (the
  measured rocker plane angle INCREASES 90→~97.4). The rocker-stop window
  shipped as (82.0, 90.5) — allowing only the mirror-image rod-side-UP swing
  — was this direction INVERTED; a manual UI drag of the rod end downward
  (the real stroke) hit the 0.5° margin instantly. Fixed to (89.5, 98.0)
  with the drag gate now proving both the working swing and the up-side stop.
- **The rest pose is LEVEL and *authored*, not incidental**: `ROD_HOLE_X`
  127.49 → **127.3738**, `ROD_C2C`/`CENTER_DISTANCE` 144.75 → **147.6655**,
  `RING_CENTER` = (54.474, 113.437) are co-solved so arm tilt = rod tilt = 0
  by construction. A fail-loud assert after `_ARC = _arc_geometry()` in
  `build_channel_assembly.py` (|tilt| > 0.02°) trips if any of the three moves
  without re-solving the closure.
- **p.25 "cam outline" reconciliation**: the dashed outline is a teardrop
  **TEMPLATE** cam (base Ø18 offset 3.3, R_tip 20.4) — Michelson's 1898 paper
  closing note says the original machine used cut metal templates. Its base
  offset 3.3 is NOT the throw; its full lift ≈ 14.7 mm agrees with the
  end-view ring travel ~17.3 within the plate's weak scale, and its ring bore
  scales to Ø29.83, independently confirming the Ø30.6 integral cam. **User
  decision**: model whichever produces sinusoidal rocker motion → the circular
  eccentric-and-strap (concentric mate = exact SHM at the ring centre;
  rod-obliquity 2nd harmonic ecc²/(4·C2C) ≈ 0.11 mm ≈ 1.3%, the same order as
  the real machine's "near-sinusoidal"). Template reality lives in
  provenance/docstrings only; a SW tangency-mate follower would simulate worse.
- **Rod pin sits LOW in the rocker strap** (ch14 fan photo, 0.114 mm/px via
  the 16 mm arm-depth callout): new module constant `ROD_HOLE_Y` =
  bottom_arc_y + 5.3 ≈ 15.30 in `build_rocker_arm.py` (pivot stays mid-depth
  8.0), imported-not-copied by the assembly → lever 127.583, β 3.2813°.
- **Rod top is a tombstone Y-head**, not a 10×18 full-depth strap: 10 wide ×
  10.5 tall, R5 crown, pin 2.4 below the crown top, short shoulders into the
  8 mm shank (`HEAD_*` constants in `build_connecting_rod.py`).
- **Downstream ripple** (all solver-driven, only two literals moved):
  `LEVER_EYE_Y` 1063.25 → **1062.5234** (neutral lever tilt −0.002°, guarded by
  `spring:neutral-body-canonical`); pivot-bushing bar clearance tightened —
  contact 262.63 → 261.81, cheeks 5.63 over the axis, Ø10 bushing keeps only
  **0.63 mm** (was 1.45), and the assembly's `bar_bottom − PIVOT_y ≥ 5.5`
  assert now passes by just 0.145 mm. If the pose ever drops further, the
  bushing OD ceiling (~11.25) is the first casualty.

**Why:** the ROM is the machine's output amplitude — every fourier trace
scales with it; a 2.8× understated throw (ecc 3.06) made the whole analyzer a
toy. **How to apply:** treat photo-measured ROM as the anchor for any future
cam/lever rescale; grep for the level-pose closure constants before moving
RING_CENTER, ROD_HOLE_X/Y, or CENTER_DISTANCE (the assert names them).
Supersedes the default-state numbers in [[channel-layout-m63]] and the
127.49/144.75 vertical-rod solve in [[ch30-gt-reanchor]] (the plumb topology
itself stands).
