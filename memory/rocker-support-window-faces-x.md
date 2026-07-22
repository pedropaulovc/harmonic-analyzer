---
name: rocker-support-window-faces-x
description: rocker-arm-support must be turned +90deg about Y in frame.SLDASM so its window faces machine X (book ch30 p008), not Z
metadata:
  type: project
---

The `rocker-arm-support` part (build_rocker_arm_support.py, the single NORTH
upright that replaced `rocker-arm-portal`) is authored with its big windowed
faces normal to its LOCAL Z (the thin 63.5mm axis) and its 177.8mm width along
local X. Placing it at IDENTITY in frame.SLDASM points the window along machine
±Z — WRONG: the window then reads edge-on (a thin tapered wedge) from the +X
side, but book ch30 p008 (the +X side view) shows the windowed square FACE-ON,
exactly like the `rocker-arm-portal` it replaced.

Fix (frame.SLDASM): turn it **+90deg about Y** with `ROT_Y_POS90` (from
`_transforms`; equals `rows_from_euler([0,90,0])`). The turn maps local Z (window
normal) -> machine +X, local X (177.8 width) -> machine Z, local Y -> machine Y.

Placement after the turn (CURRENT): inserted on its exact authored transform
(`place_component(..., ground=False)`, `support_target = [SUPPORT_X,
SUPPORT_SEAT_Y=139.7, 0.0]`, `SUPPORT_ROWS=ROT_Y_POS90`) and pinned with a SINGLE
`lock_mate(Front@support <-> Right@base)` to the fixed base — the frame's
"single-mate strategy" (every rigid member: exact transform + one lock mate on a
DEFAULT plane; `assert_component_placed` is the readback tripwire). The +90 turn
already makes the pose deterministic, so no orientation/seat mate is needed.

**Superseded — the datum-mate design (removed 2026-07-22).** The support used to
be CONSTRAINED BY THREE ORTHOGONAL MATES, one of them
`FootSeat@support <-> DeckTop@base` COINCIDENT (foot bottom on base top), after a
4-approach bake-off for the foot-seat y: (a) `Top<->Top` distance `flip=True`, (b)
`"anti_aligned"` swMateAlign — inverts orientation 180deg, FAILS, (c) physical
face-object coincident — flip-free but ~45s walking the base's faces, (d) WINNER
at the time: named DATUM PLANES on the contact (`FootSeat` offset `-HALF_Y` on the
support, `DeckTop` offset 50.8 on the base), mated coincident, 0.4s. That whole
approach is GONE: exact-transform placement made all three mates redundant, so
`FootSeat`, the base `DeckTop`, and the other members' mate datums (`TopEnd`,
`RingTop`, `Underside`, `MidLength`, lag-screw `ScrewAxis`) were orphaned and
deleted. Lesson retained: signed `create_plane` offset flips the datum side, and a
free-space distance mate (no contact to seat a datum on) still needs `flip=True`.

**Mount caveat (RESOLVED).** The north pivot ball mount originally stayed at z
+101.6 and cantilevered ~12.7 mm past the centred wall edge (88.9). Fixed — NOT by
widening the wall (the user rejected that) — with these changes in
build_channel_assembly.py: (1) the north mount moved south to z +81.5
(`SUPPORT_Z`); (2) pivot-ball-mount's ball+base narrowed Ø19/16 -> **Ø13** so its
z-footprint [75.0, 88.0] both clears the channel-19 amplitude-bar (z 74.1) and
stays inside the wall edge (88.9) — the shared part shrinks all 4 mounts
(user-approved). The pivot SHAFT was also trimmed 228.6 -> **203.2 (8")** and
placed OFF-CENTRE (`PIVOT_SHAFT_Z = -12.7`) so its north end lands at the wall edge
(+88.9) while the south end (-114.3) still reaches the A-frame mount (-111) — the
"north end only" choice (the shaft stays a symmetric part; the assembly offsets
it). Verified: channel + full-assembly interference-free, all gates green.

**Hold-down bolts (added).** The base bolt holes were realigned from the dead
portal pattern to the support FOOT pattern (FootTappedHoles, local X ±60.32 Z
±17.46 -> machine x 55.44/90.36, z ±60.32) and 4× **9/16-12 lag screws** added:
- build_harmonic_base.py `HOLE_XZ` = those 4 machine stations, `HOLE_DIA` 8.2 ->
  **13** clearance, `CBORE_DIA/DEPTH` 15/4.5 -> **23/6.5** on ALL 4 (`CBORE_XZ =
  HOLE_XZ`). Base CoM z went to ~0 (pattern now z-symmetric).
- build_lag_screw.py resized 5/16 -> **9/16-12**: shank Ø7.8 -> **12** (fits the
  Ø12.30376 tap-drill foot hole), head Ø14 -> **22**, len 66 -> 63.
- build_frame_assembly.py grounds 4 lag-screws head-down at the stations
  (`LAG_SCREW_XZ`, `mirror=False`, under-head y 6.5; shank top y 69.5 stays below
  the window at y 76.2). verify.py frame band 7-12 -> **11-16** (measured 13 = 9
  structure + 4 bolts).

The rocker-pivot SHAFT runs along Z; the wall sits at the north end with the
shaft's north end carried at its apex. Related: [[harmonic-analyzer-project]].
