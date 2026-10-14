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
from _printed_tolerance import printed_band_mm
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

# --- Drawing contract.  ``build_pd_platen`` marks exactly these dimensions and
# authors their places; ``draw_pd_platen`` keeps exactly their union across its
# views.  Hole sizes ship as native Hole Wizard callouts.  The socket and the
# guide-hole coordinates print once per shared station (the other instances'
# coordinates are sketch relations to these), from the plate's bottom-left
# corner. ---
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "PlateProfile": {"Width", "Height"},
    "Plate": {"Depth"},
    "SocketBossProfile": {"Boss1Dia"},
    "SocketBosses": {"BossH"},
    "Sockets": {"Socket1X", "Socket1Y", "Socket2Y", "Socket3X"},
    "GuideHoles": {
        "Guide1X",
        "Guide2X",
        "Guide3X",
        "Guide4X",
        "Guide5X",
        "Guide1Y",
        "Guide6Y",
    },
}
# Places.  The outline prints .X: the clips and guides locate from the holes,
# not the edges.  The thickness and boss height are the clip-screw thread
# stack (SOCKET_THREAD_ENGAGEMENT), the boss Ø its wall round the tap, and
# every hole coordinate is spent by the fixed-screw float over the clip's and
# the guides' patterns (test_pd_platen_refit): all .XXX.
POSITION_PLACES = 3
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "PlateProfile": {"Width": 1, "Height": 1},
    "Plate": {"Depth": 3},
    "SocketBossProfile": {"Boss1Dia": 3},
    "SocketBosses": {"BossH": 3},
    "Sockets": {name: POSITION_PLACES for name in DRAWING_DIMENSIONS["Sockets"]},
    "GuideHoles": {name: POSITION_PLACES for name in DRAWING_DIMENSIONS["GuideHoles"]},
}
DRAWING_PRECISION_BY_NAME: dict[str, int] = {
    name: places
    for dimensions in DRAWING_PRECISION.values()
    for name, places in dimensions.items()
}
if DRAWING_PRECISION.keys() != DRAWING_DIMENSIONS.keys() or any(
    set(DRAWING_PRECISION[feature]) != names
    for feature, names in DRAWING_DIMENSIONS.items()
):
    raise AssertionError("every marked platen dimension needs authored places")

# The counterbored guide-hole callout's native variables: the loose through
# hole and the head-recess depth at .XXX, the counterbore Ø at .X (the head
# clears it by more than the .X band).
GUIDE_CALLOUT_PRECISION = {"hw-thruholedia": 3, "hw-cbdia": 1, "hw-cbdepth": 3}
# The shallowest printed counterbore still sinks the stock fillister head.
HEAD_RECESS_MIN = (
    round(CBORE_DEPTH, GUIDE_CALLOUT_PRECISION["hw-cbdepth"])
    - printed_band_mm(GUIDE_CALLOUT_PRECISION["hw-cbdepth"])
    - FILLISTER_HEAD_H
)
if HEAD_RECESS_MIN <= 0.0:
    raise AssertionError(
        f"guide-screw heads stand proud at the shallowest counterbore: {HEAD_RECESS_MIN}"
    )

ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:4"
RIGHT_VIEW_NOTE = "ENLARGED RIGHT VIEW SCALE 1:1"
BACK_VIEW_NOTE = "BACK VIEW"
