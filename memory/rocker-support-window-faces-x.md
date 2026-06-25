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
`_transforms`; equals `rows_from_euler([0,90,0])`), via a grounded
`place_component(..., ground=True, mirror=False)` — supports are grounded
structure by convention, like the nameplate. The turn maps local Z (window
normal) -> machine +X, local X (177.8 width) -> machine Z, local Y -> machine Y.

Placement after the turn: `SUPPORT_X=72.9` (pivot x), `SUPPORT_SEAT_Y=139.7`
(origin at casting centre, foot on base top 50.8), `SUPPORT_Z = 101.6 + 8.9 -
88.9 = 21.6`. The 177.8-deep (+/-88.9) wall is centred AS FAR AS the north pivot
ball mount allows: that mount sits at z +101.6 and is 17.8 deep (z 92.7..110.5),
so the wall's north face is set flush with the mount's north edge (z 110.5),
Zc = 110.5 - 88.9 = 21.6 -- any more centred and the mount overhangs the wall.
The window centre then reads +21.6 (vs base half-depth 133.35), nearly centred
in the side views (user wanted it centred), matching the book's slight north
offset; apex y 228.6 carries the mount, south face -67.3. Do NOT push to z=0:
that floats the ball mount 12.7+ mm past the wall's north edge -- unsupported.
Verified: +X/-X side renders show the window nearly centred + face-on matching
the book; front render shows the tapered wedge edge-on (like the portal); part
renders green (Gray Cast Iron + CASTING_GREEN); no interference, fully
constrained.

The rocker-pivot SHAFT runs along Z (build_channel_assembly.py line ~9:
"rocker bank ... along Z"); the wall sits at the north end with the shaft's
north end carried at its apex. Related: [[harmonic-analyzer-project-decisions]].
