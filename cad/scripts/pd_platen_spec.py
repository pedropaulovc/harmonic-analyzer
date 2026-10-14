r"""Platen plate nominals (book ch. 22, pp. 54-55).

PURE DATA, no SolidWorks/COM calls and no ``build_*`` module in its import
closure: the plate envelope, the clip-screw receivers and the guide-screw
counterbored through-holes. ``build_pd_platen`` authors the part from these; the
clip, the guide rails and the paper-drive assembly read them here instead of
importing the builder, whose sketch recipe would otherwise ride their cache
keys (#880).
"""

from __future__ import annotations

from _hole_spec import HoleSpec
from _inch import inch
from vn_fillister_screw_spec import HEAD_H as FILLISTER_HEAD_H

# ch30-p002 Pose Studio: 300 * 0.8988 = 269.64 (user fit), snapped to 10-5/8.
PLATE_WIDTH = inch(10 + 5 / 8)
PLATE_HEIGHT = PLATE_WIDTH / 2.0  # user-confirmed front-face H:W = 1:2: 5-5/16
# DIMENSIONS.md ch22: p.55 edge-on photo (low) read ~4; thinned to 3.85
# (R9-68) with the back face, which carries the rack, held on the bar front.
# All-inch: 1/8 brass plate, which also offsets the 3/8 bar's 0.525 forward
# step of the bar front (disc-to-platen air).
PLATE_THICKNESS = inch(1, 8)

# Clip-screw receivers: the stock 90114A124 brass #2-56 fillister head
# (vn-platen-clip-screw) sits directly on the clip's flat .032 brass sheet
# (ch22 img03: no raised seat, small heads), and its shank reaches through a
# #2-56 tap through the plate and a Ø1/4 boss standing SOCKET_BOSS_H proud of the
# back face at each station, so the thread engages >= 1.5D (drawing-guidelines.md rule 18 (thread engagement)) and the
# screw tip finishes flush with the boss's rear face. These must be through
# taps: no blind receiver here can accept the exact 1/4-in under-head length
# without bottoming. The bosses stand above the top guide rail's band, where
# nothing but the clip-screw tips rides the back.
SOCKET_SPEC = HoleSpec("tapped", "#2-56")
SOCKET_BOSS_DIA = inch(1, 4)  # 2.08 wall around the #2-56 major (drawing-guidelines.md rule 17 (walls and webs): 2.0)
# Derived closure, tip flush: 1/4 shank - .032 clip sheet - 1/8 plate = .0930
# (2.3622). build_pd_platen_clip asserts the closure against the live screw
# and sheet.
SOCKET_BOSS_H = inch(1, 4) - inch(0.032) - PLATE_THICKNESS
SOCKET_THREAD_ENGAGEMENT = PLATE_THICKNESS + SOCKET_BOSS_H
# x 3/16 in from each side edge; y on the clips' end holes (5-5/16 plate,
# 3-5/16 clip, 5/16 hole inset): 2-5/16 and 5.
SOCKET_X = (inch(3, 16), PLATE_WIDTH - inch(3, 16))
SOCKET_Y = (inch(2 + 5 / 16), inch(5))
SOCKET_XY = tuple((x, y) for x in SOCKET_X for y in SOCKET_Y)

# Guide-screw through-holes: 2 rows of 5 (heads on the front face, shanks
# into the guide rails on the back). ONE counterbored #4 fillister Hole
# Wizard feature; the through/cbore dims are explicit overrides.
GUIDE_HOLE_DIA = inch(1, 8)  # 1/8 drill through Ø (override); #4 fillister shank passes
# 1/10, 3/10 .. 9/10 of the 10-5/8 width: exact sixteenths.
GUIDE_HOLE_X = (
    inch(1 + 1 / 16),
    inch(3 + 3 / 16),
    inch(5 + 5 / 16),
    inch(7 + 7 / 16),
    inch(9 + 9 / 16),
)
# Bottom / top rail centrelines. 1-11/32 apart: the 1-1/8 support bar
# (pd_support_bar_spec.BAR_HEIGHT) + one 3/16 rail + a 1/32 running
# clearance over the bottom rail (the paper-drive assembly closes the stack).
GUIDE_HOLE_Y = (inch(1, 2), inch(1 + 27 / 32))
GUIDE_HOLE_XY = tuple((x, y) for y in GUIDE_HOLE_Y for x in GUIDE_HOLE_X)

# Front-face counterbores recess the stock 4.6482 x 2.7178 fillister heads
# exactly 0.2 below the front face so the recording paper lies flat (a
# sub-1/32 head clearance, left in mm). Ø1/4 clears the stock head; on the
# 1/8 plate the counterbore floor under the head is only 0.257 thick.
HEAD_RECESS = 0.2
CBORE_DIA = inch(1, 4)
CBORE_DEPTH = FILLISTER_HEAD_H + HEAD_RECESS
