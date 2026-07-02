---
name: channel-layout-m63
description: "M6.3 resolved channel geometry — rocker seesaw pivot (−72.9, 253.8), bars up the spine, lever bank at (−199.9, 1065.9), legacy gate refuted"
metadata: 
  node_type: memory
  type: project
  originSessionId: 5e824fa0-7bda-4055-8655-aa59ed6f0ef9
---

M6.3 channel layout resolution (2026-06-10), authoritative in
cad/DIMENSIONS.md ("Rocker pivot & supports layout" + "Channel & top-frame
layout" tables):

- **Rocker arms are mid-pivot seesaws**: ±88 about the pivot, connecting-rod
  pin Ø2 at +25.4 (1") on the +X side, pivot hole Ø6.5. The old read (rods at
  the arm tips, ROD_SPAN 100/TAIL 70) was wrong — the p.29 "stepped tip
  blocks" are amplitude-bar notched feet.
- **Pivot shaft** Ø6.35×228.6 along Z at (x,y) = (−72.9, 253.8) =
  (arbor −47.5 − 25.4, drive 126.8 + 127). Connecting rod c2c = 127 (5"),
  not 105. Ball mounts (ball centre 25.2 above seat) on support apexes.
- **Support (M6.5: ONE, north only)**: solid tapered frustum 88.9×63.5 →
  20×16.9, 177.8 tall, at (−72.9, +101.6). The calibrated v3 side view
  (6.124 px/mm, z0 x_img 1744.5, ybase 6569) REFUTES the south instance;
  the south pivot ball mount (z −111) seats on the transgear A-FRAME's
  saddle (y 228.6) between clevis ears (see [[output-layout-m64]]). The
  frustum's east-flank boss (Ø20 at local (+25.4, 76), face machine z
  74.1, Ø9.7 through-bore) clamps the cylinder-arbor north end — only ONE
  arbor pedestal (south, z −92). The legacy windowed-square-frame
  rocker-arm-support (184 wide) is fiction.
- **Fulcrum shaft is its own part** (`fulcrum-shaft`, Ø6.35×182): the
  228.6 pivot-shaft length put the tips inside the west columns at
  (−197, ±112). Pivot shaft (rocker bank) stays 228.6.
- **Amplitude bars run UP** (812.8) to 20 top levers: levers span
  x −199.9..−22.1 (177.8 long, NOT 254 c2c) — fulcrum shaft at
  (−199.9, 1065.9) on the top-frame west rail (west column line), bar pin
  at −72.9 (127 from the fulcrum), spring tab at −22.1; section 9.5×3.0
  (12.5 width violated the 7.06 pitch); same ball-mount + bushing design
  as the rocker bank. Anything east of x −22.1 at the lever level is
  lever-free (M6.4 clearance checks relied on this).
- **Top frame** (new part): green ring clamping the 4 columns at
  y ≈ 1000–1040.7; columns continue above it.
- **Default state (exact solve, build_channel_assembly.solve_default_state)**
  *(SUPERSEDED 2026-07-02 by [[ch14-rom-rederive]]: ecc 8.64 lobe-UP, arms rest
  LEVEL, rod pin low at +127.37 — the numbers below are the M6.3-era record)*:
  drive-train locks cylinder gears at Rz(+1.5°) (half T120 tooth pitch —
  tooth faces the cone mesh), so the cam centres sit at (−47.367, 121.721)
  = arbor + 5.08·(sin1.5°, −cos1.5°) — M6.5: assuming the unrotated centre
  (−47.5, 121.72) dug every rod ring 0.033 into its cam (20 × 2.40 mm³ at
  top level). Rod rings concentric there; rod-pin = r25.4 about pivot ∩
  r127 about ring centre, +X branch (−48.01, 248.72) → arms −11.54°, rods
  Rz +0.29°; bar foot contact
  262.63 (bar −X edge on the tilted-arm R800 arc), bar bottom 260.25, top pin
  1066.70 → levers +0.36°; spring holes (54.10, 1067.50). Cams are INTEGRAL
  to cylinder gears (already in drive-train.SLDASM); standalone eccentric-cam
  part superseded.
- **Geometric refutations**: pivot bushings Ø10 (not the p.27 Ø25.4 read —
  bar foot passes 6.45 above the shaft axis at d=0, OD ceiling ~12.9); lever
  ball mounts at z ±85 (not ±101.6 — Ø16 base must clear the top-frame Ø35
  boss bores at z 112); lever spring hole Ø4 (not the Ø3 photo read — the
  spring's r2.75 Ø1-wire eye can't thread a Ø3 hole in the 3.0 plate; eye
  drop 3.37 gives ~0.3 margins, toroid solve in _assert_spring_threading).
- Eight-views calibrations: front p1: 6.02 px/mm, x0_img 1634, base-top
  y_img 6580. Back p5: ~6.143 px/mm, x0 1647, base-top y_img ~6551, x
  MIRRORED. Side v3 (90°, camera WEST, −z at left; M6.5): 6.124 px/mm,
  z0 at x_img 1744.5, ybase-img 6569. Perspective model: scale ratio ≈
  D/(D+depth), D≈977 from the near base edge (crank pedestal at x +122.3
  reads at ratio 0.736 in v3 — beware misattributing far-side objects).
  Grid tool: references/…/ch30_images/make_machine_grid.py.
- Summing lever (M6.4): first-class, knife edge ≈ +69, plate takes 20
  springs from lever tips (+54.1), counter spring at +84 rising to a
  chrome U-loop; magnifying wheel at (−55, 565).
- **Channel-spring chain (RESOLVED in M6.4)**: the installed-spring part
  spans lever tab (spring hole ~1067.5) down through the summing plate
  (top 998, Ø4.5 holes at x −22.10, z z_j−1.95);
  `build_channel_assembly._assert_plate_threading` gates the fit. The
  earlier "plate level y 1027.6" claim was wrong (see
  [[output-layout-m64]]).

Related: [[harmonic-analyzer-project]]
