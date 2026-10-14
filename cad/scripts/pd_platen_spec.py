r"""Platen plate nominals (book ch. 22, pp. 54-55).

PURE DATA, no SolidWorks/COM calls and no ``build_*`` module in its import
closure: the plate envelope, the clip-screw receivers and the guide-screw
counterbored through-holes. ``build_pd_platen`` authors the part from these; the
clip, the guide rails and the paper-drive assembly read them here instead of
importing the builder, whose sketch recipe would otherwise ride their cache
keys (#880).
"""

from __future__ import annotations

from _hole_spec import CLEARANCE_MM, HoleSpec
from vn_fillister_screw_spec import HEAD_H as FILLISTER_HEAD_H

PLATE_WIDTH = 269.64  # ch30-p002 Pose Studio: 300 * 0.8988 (user fit)
PLATE_HEIGHT = PLATE_WIDTH / 2.0  # user-confirmed front-face H:W = 1:2
# DIMENSIONS.md ch22: p.55 edge-on photo (low) read ~4; thinned to 3.85
# (R9-68) with the back face, which carries the rack, held on the bar front:
# the front face moves 0.15 rearward to open the disc-to-platen air.
PLATE_THICKNESS = 3.85

# Clip-screw receivers: the stock 90114A124 brass #2-56 fillister head
# (vn-platen-clip-screw) sits directly on the clip's flat 0.8 brass sheet
# (ch22 img03: no raised seat, small heads), and its shank reaches through a
# #2-56 tap through the plate and a Ø7 boss standing SOCKET_BOSS_H proud of the
# back face at each station, so the thread engages >= 1.5D (drawing-guidelines.md rule 18 (thread engagement)) and the
# screw tip finishes flush with the boss's rear face. These must be through
# taps: no blind receiver here can accept the exact 6.35-mm under-head length
# without bottoming. The bosses stand above the top guide rail's band, where
# nothing but the clip-screw tips rides the back.
SOCKET_SPEC = HoleSpec("tapped", "#2-56")
SOCKET_BOSS_DIA = 7.0  # 2.41 wall around the #2-56 major (drawing-guidelines.md rule 17 (walls and webs): 2.0)
# 6.35 shank - 0.8 clip sheet - 3.85 plate: 5.55 engaged (2.54D), tip flush.
# build_pd_platen_clip asserts the closure against the live screw and sheet.
SOCKET_BOSS_H = 1.70
SOCKET_THREAD_ENGAGEMENT = PLATE_THICKNESS + SOCKET_BOSS_H
SOCKET_XY = (
    (5.3928, 58.5104), (5.3928, 127.6296),
    (264.2472, 58.5104), (264.2472, 127.6296),
)

# Guide-screw through-holes: 2 rows of 5 (heads on the front face, shanks
# into the guide rails on the back). ONE counterbored #4 fillister Hole
# Wizard feature; the artefact counterbore dims are preserved as overrides.
# #4 LOOSE through (user ruling 2026-10-14, rule-21 float stack): the screws
# are fixed in the guides' taps, so each hole's float over the shank must hold
# the guide's tap position and this plate's own .XXX hole coordinates
# (test_pd_platen_refit); the artefact Ø3.0 floated 0.155 against 0.20.
GUIDE_HOLE_FIT = "loose"
GUIDE_HOLE_DIA = CLEARANCE_MM[("#4", GUIDE_HOLE_FIT)]  # 3.658
GUIDE_HOLE_X = (26.964, 80.892, 134.82, 188.748, 242.676)
GUIDE_HOLE_Y = (13.0, 47.0)  # bottom / top rail centrelines (machine 318 / 352)
GUIDE_HOLE_XY = tuple((x, y) for y in GUIDE_HOLE_Y for x in GUIDE_HOLE_X)

# Front-face counterbores recess the stock 4.6482 x 2.7178 fillister heads
# exactly 0.2 below the front face so the recording paper lies flat.
# The Ø6.5 artefact override remains ample for the smaller stock head.
HEAD_RECESS = 0.2
CBORE_DIA = 6.5
CBORE_DEPTH = FILLISTER_HEAD_H + HEAD_RECESS
