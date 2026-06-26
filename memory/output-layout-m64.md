---
name: output-layout-m64
description: "M6.4 output.SLDASM final placement table (machine coords) + resolved interference fixes + M6.5 open items"
metadata:
  node_type: memory
  type: project
  originSessionId: 5e824fa0-7bda-4055-8655-aa59ed6f0ef9
---

M6.4 output.SLDASM FINAL placements (2026-06-10, after the 17→8→0
interference campaign). Authoritative source: `cad/scripts/build_output_assembly.py`
constants + `cad/DIMENSIONS.md` ch. 18–24 M6.4 rows. Machine coords: Y up
(base top 50.8), channels along Z, output side −Z. Knife line (15, 990).

- **Summing group (z≈0)**: summing-lever + knife-mount at (15, 990, 0) ID;
  top-crossbar (15, **1010**, 0) — band 1010..1051, 0.5 above the tube top
  1009.5, floats 10.3 proud of the ring band 999.7..1040.7, ends face-flush
  on rail inner faces; boss-hook
  (90.5, 1000, 0); counter-spring (95, **1052.1**, 0) Ry+90 — ring 1012.1,
  0.05 AIR gap above the hook rod top 1016.5 (the hang assert measures
  ring_inner_top − rod_top ∈ (0, 0.5); the original sense was inverted);
  gooseneck (197, 1210, 0); gooseneck-clamp (197, 1040.7, 0).
- **Magnifying**: bracket (−40, 985, −85); lever (−200, 985, −85); clamp at
  lever x −150 Ry+90; thumb screw backed out (tip tangent rod top) Rz−90;
  vertical rod (−150, 990, −91.5) Rz−90; output-fixture (−150, 926, −91.5).
- **Support bars** y 565/440/334, z −133.9 (front face −138.9); column-clamps
  (±197, bar y, −112) Ry+90. Wheel-axle (−53, 565, −138.9) Rx−90; wheel
  (−53, 565, −146.9).
- **Platen**: (−258, 305, −142.9) — slab z −142.9..−138.9, y 305..445;
  platen-rack Rz180 at (41.23, 323.59, −138.9): **RACK_X0 = 15.5 × pitch**
  — the 96T gear's seed gap is centred at +γ/2 so a TOOTH sits at bottom
  dead centre and gaps flank it at ±p/2; 15 × pitch was tip-to-tip (7
  decaying overlaps that LOOKED like insufficient backlash — backlash
  stays 0.3); clips x −250..−240 / +22..+32, z −144.1, Rz+90.
- **Transgear (M6.5 updates)**: a-frame (0, 50.8, −111) — apex REDESIGNED:
  plate trapezoid foot x −115..−45 → apex −87..−59, saddle (full-width
  z ±11.1) at y 228.6 seats the SOUTH PIVOT BALL MOUNT, clevis ears
  ±(8.1..11.1) rise to 248.6 flanking the mount's Ø16 base (a-frame
  doubles as the front rocker support — the south frustum is refuted, see
  [[channel-layout-m63]]); pinion-bar (0, 253.5, −111) trimmed to
  x −58..+178, BOTH ends float (documented simplification); stub
  (0, 253.5, −101.5) Rx−90; rack-pinion (0, 253.5, −137.5) — disc back face
  −134.5; transgear-pinion (0, 253.5, −134); latch Rz−20 at z −122.5;
  knob-shaft at (32.19, 241.78, −76.5) Rx−90 — part shortened to **51.4**
  (shaft −76.5..−127.9, knob to −134.4, 0.1 shy of the rack-pinion disc;
  latch C2C 34.26 < disc r 41.49); chain-sprocket z −81.
- **Pen group**: hanger (−3, 505, −151.5) — guide hole is a VERTICAL
  5.4-square channel cut along Y (first build wrongly tunnelled it along Z);
  rod (−3, 398, −154) → z −154..−149; v-block (−24, 390, −159.5); marker
  vertical at (−13, 368, −151.5), barrel z −155.5..−147.5; **pen-frame**
  (−29, 418, **−143**) rotation **[90, 90, 0]** = Ry90·Rx90 (rows
  [[0,0,−1],[1,0,0],[0,−1,0]]; local→machine (x,y,z)→(y,−z,−x)) — flat on
  the v-block top 408, long axis along X, window x −25..+7 / z −161..−147
  spans marker+rod, near plate edge 0.1 short of the platen front −142.9
  (this forced the part's side rails 5→4: window edge 4 mm from the plate
  edge clears the marker top −147.5); **pen-set-screw** (−38, 413, −154)
  IDENTITY — its own +X axis presses east through the west end-rail hole
  (machine y 413, z −154 = frame local x 11, z 5), tip −18, 1 shy of the
  marker.
- **Loose (reparked by the OD-62.2 re-anchor, commit 2c22311, 2026-06-19 —
  the crank-pedestal shift consumed the old front-edge spots; see
  [[od-62mm-reanchor]])**: measuring-stick now `STICK_POS = (−100, 53.8, 123.5)`
  Rx+90 (moved to the clear back-plate edge); spare T24 now
  `SPARE_GEAR_POS = (−160, 55.8, −15)` Rx−90. (M6.5-era values were
  measuring-stick (−158, 53.8, −133) / spare T24 (−133, 55.8, −80); the
  spare's plan circle r 26 = OD radius, NOT the 20.7 hub radius that botched
  the first move.)
- **Knife-stay strap (M6.5)** — OBSOLETE, the part was later REMOVED (never
  in the real device; see [[knife-stay-removed]]). Kept only as history: its
  rod hook had moved −40 → −10, strap (−10, 1086) → (9.7, 1053), to clear the
  channel levers' spring tabs (overhang 8 past the hole line to x −14.1).
- **M6.5 size trims**: top-crossbar half-z 101 (372→202 long; M6.4 had
  mistakenly used the ring inner X span 186); support-bar 384 (columns
  reach x ±192.6 at the bar z band); magnifying-bracket flange machine
  x −45..−29 (clears the j=0 spring helix at −28.35).
- Other M6.4 part changes: knife-mount bar 35→**31.8** (rides inside the
  lever tube slot ±16; contact bands outside the slot are geometrically
  impossible).

**M6.5 open items**: marker plumb vs the book's ~12° tilt;
cross-subassembly fits (gooseneck vs column
caps). (The knife-stay rod-and-strap was REMOVED — it never existed in the
real device; see [[knife-stay-removed]].) RESOLVED (stale flags): the channel-spring chain is reconciled —
channel.SLDASM's `_assert_plate_threading` gates spring bottom loops
against the summing plate (top 998, 5.1 thick, Ø4.5 holes at x −22.10)
and lever span 177.8 puts spring axes on the hole line; the chain plane
is consistent — both drive-train and output place their sprockets at
SPROCKET_Z0 = −81 (the knob shaft spans −76.5..−127.9, so the sprocket
hub sits on it).

See [[harmonic-analyzer-project]], [[channel-layout-m63]],
[[solidworks-modeling-pitfalls]].
