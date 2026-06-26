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

Placement after the turn: inserted on-solution (`place_component(...,
ground=False, mirror=False)`) then **CONSTRAINED BY THREE ORTHOGONAL MATES**
against the base (NOT grounded — the user wanted the centring done by a mate, not
a hand-tuned constant). Two of the three are flip-free COINCIDENT mates:

* `Front@support <-> Right@base` **distance** `SUPPORT_X=72.9` (pivot x), `flip=True`;
* `FootSeat@support <-> DeckTop@base` **COINCIDENT** — physical foot seat (foot
  bottom on base top, y 50.8), named datum on each part;
* `Right@support <-> Front@base` **COINCIDENT** — centres the 177.8-wide
  (+/-88.9) wall on the base z-axis (z 0) by symmetry plane, no z offset.

After the +90 turn the part's Front plane (local-Z normal) faces machine X, its
Right plane (local-X normal) faces machine Z, Top plane stays on machine Y. Seed
insert on-solution (z 0, foot at base top) so both coincident mates lock their
DOF without moving and solve clean (flip-free).

**Mate-side lesson (4 approaches tried for the foot seat y):** on a +90-turned
part the orientation-preserving sense ("aligned") puts the origin on the FAR
side, so a naive plane-distance mate lands there and the verify-and-flip recovery
deletes + re-adds it — the part visibly JUMPS. (a) `Top@support<->Top@base`
distance `flip=True` lands it in one solve but still uses the flip knob. (b) An
`"anti_aligned"` swMateAlign reaches the near side WITHOUT flip but inverts the
part ORIENTATION 180deg (foot up, window -X — rotation assert drift 2.0, FAILS):
alignment is the WRONG knob, it also rotates. (c) A physical coincident of the
foot/base-top FACE OBJECTS (selected by normal, `IComponent2.GetCorrespondingEntity`)
is flip-free but walking the base's HUNDREDS of faces to find the deck costs ~45s.
(d) **WINNER — named DATUM PLANES on the contact**, mated coincident: flip-free,
0.4s, robust (no coordinate pick, no face walk), no adapter code. Added
`FootSeat` to the support (`create_plane` offset `-HALF_Y` from Top Plane = the
foot face) and `DeckTop` to the base (offset `BOTTOM_THICKNESS+TOP_THICKNESS=50.8`
= the top face); `create_plane` offset is SIGNED (neg flips the side), Top Plane
normal is +Y. The pivot-x DISTANCE mate (a) still needs `flip=True` — a free-space
offset has no contact to seat a datum on, so its side selector is unavoidable.

Verified: frame builds fully-defined (status 3, not fixed), support lands in one
solve (no moved/flipped/delete lines), foot seat 0.4s, no interference, healthy.

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
shaft's north end carried at its apex. Related: [[harmonic-analyzer-project-decisions]].
