r"""Platen plate nominals (book ch. 22, pp. 54-55).

PURE DATA, no SolidWorks/COM calls and no ``build_*`` module in its import
closure: the plate envelope, the clip-screw receivers and the guide-screw
counterbored through-holes. ``build_pd_platen`` authors the part from these; the
clip, the guide rails and the paper-drive assembly read them here instead of
importing the builder, whose sketch recipe would otherwise ride their cache
keys (#880).
"""

from __future__ import annotations

from _hole_spec import CLEARANCE_MM, THREAD_MAJOR_MM, HoleSpec
from _printed_tolerance import printed_band_mm
from vn_fillister_screw_spec import HEAD_H as FILLISTER_HEAD_H

PLATE_WIDTH = 269.64  # ch30-p002 Pose Studio: 300 * 0.8988 (user fit)
PLATE_HEIGHT = PLATE_WIDTH / 2.0  # user-confirmed front-face H:W = 1:2
# DIMENSIONS.md ch22: p.55 edge-on photo (low) read ~4; thinned to 3.85
# (R9-68) with the back face, which carries the rack, held on the bar front:
# the front face moves 0.15 rearward to open the disc-to-platen air.
PLATE_THICKNESS = 3.85

# Clip-screw receivers: the stock 92446A077 brass #2-56 slotted pan head
# (vn-platen-clip-screw) sits directly on the clip's flat 0.8 brass sheet
# (ch22 img03: no raised seat, small heads), and its shank reaches through a
# #2-56 tap through the plate and a Ø7 boss standing SOCKET_BOSS_H proud of the
# back face at each station, so the thread engages >= 1.5D (drawing-guidelines.md rule 18 (thread engagement)) and the
# screw tip finishes flush with the boss's rear face. These must be through
# taps: no blind receiver here can accept the exact 6.35-mm under-head length
# without bottoming. The bosses stand above the top guide rail's band, where
# nothing but the clip-screw tips rides the back.
SOCKET_SPEC = HoleSpec("tapped", "#2-56")
SOCKET_BOSS_DIA = 7.0  # wall round the #2-56 major (drawing-guidelines.md rule 17 (walls and webs): 2.0)
# 6.35 shank - 0.8 clip sheet - 3.85 plate: 5.55 engaged (2.54D), tip flush.
# build_pd_platen_clip asserts the closure against the live screw and sheet.
SOCKET_BOSS_H = 1.70
SOCKET_THREAD_ENGAGEMENT = PLATE_THICKNESS + SOCKET_BOSS_H
# Each boss meets the back face in a root round up to the tool-nose radius
# the print allows (r7 review: a bare corner left the root unstated).  It
# prints as the single limit "4X R0.5 MAX"; swTolMAX prints the nominal, so
# the model carries the limit (pn_pen_rod_spec's shoulder root).  The round
# stands 0.5 out from the boss on the back face, where nothing rides
# (build_pd_paper_drive_assembly's lock-station sweep grows each boss by it).
SOCKET_BOSS_FILLET_R = 0.5
# (upper, lower) deviations: the nominal IS the limit, down to sharp.
SOCKET_BOSS_FILLET_BAND = (0.0, -SOCKET_BOSS_FILLET_R)
SOCKET_BOSS_FILLET_TOL_TYPE = 6  # swTolType_e.swTolMAX: prints "4X R0.5 MAX"
# Each socket's distance in from its side edge, on both sides.  The widened
# clip screw rail (user ruling 2026-10-14) puts the clip's inboard edge at
# SOCKET_X - HOLE_Y + CLIP_WIDTH; with the recording paper's 14.6 left inset
# (paper_drive_geom) the photographed 5.3928 left that edge 1.15 off the
# paper.  This is the largest 0.1-grid station that holds the 2.0 nominal
# clip-to-paper gap (test_pd_platen_refit asserts the gap, the grid optimum
# and the worst-case tap ligament, clip and plate edges).
SOCKET_X = 4.5
SOCKET_XY = (
    (SOCKET_X, 58.5104),
    (SOCKET_X, 127.6296),
    (PLATE_WIDTH - SOCKET_X, 58.5104),
    (PLATE_WIDTH - SOCKET_X, 127.6296),
)
# The one printed root round: the upper boss nearest the right view's eye
# (+X), whose root silhouette that view shows; the other three are a second
# feature on the same global.
SOCKET_BOSS_FILLET_PRINTED_XY = SOCKET_XY[3]

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

# Counterbore floor: the plate left under each guide-screw head.  USER-ACCEPTED
# rule-17 exception (2026-10-14): 0.93 nominal and CBORE_FLOOR_MIN (0.67) at
# the printed worst case, under the 1.5 floor.  The plate is brass and the #4
# guide screws are hand-tight: the floor's shear ring under the head
# (pi x 3.658 x 0.67, about 7.7 mm^2) carries only that clamp.  The sheet prints
# the floor as a reference dimension in section A-A, a partial section through
# the top row's middle hole (r4 asked for a cut, not hidden lines): the hidden
# CboreFloorReference sketch lies in the cutting plane (CBORE_SECTION_PLANE,
# x = CBORE_SECTION_X), mid-annulus below that hole.  The value stands left
# of its extension lines, so they run clear of its text (r5).
# test_pd_platen_drawing
# pins the worst case at or above the accepted value, so no later change can
# thin it further.
CBORE_FLOOR = PLATE_THICKNESS - CBORE_DEPTH
CBORE_FLOOR_ACCEPTED_MIN = 0.67
CBORE_SECTION_X = GUIDE_HOLE_X[2]
CBORE_SECTION_HOLE_Y = GUIDE_HOLE_Y[1]
CBORE_SECTION_PLANE = "CboreSectionPlane"
CBORE_FLOOR_REFERENCE_Y = CBORE_SECTION_HOLE_Y - (GUIDE_HOLE_DIA + CBORE_DIA) / 4.0

# --- Drawing contract.  ``build_pd_platen`` marks exactly these dimensions and
# authors their places; ``draw_pd_platen`` keeps exactly their union across its
# views.  Hole sizes ship as native Hole Wizard callouts.  The socket and the
# guide-hole coordinates print once per shared station (the other instances'
# coordinates are sketch relations to these), from the plate's bottom-left
# corner. ---
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "PlateProfile": {"Width", "Height"},
    "Plate": {"Depth"},
    "SocketBossProfile": {"Boss2Dia"},
    "SocketBosses": {"BossH"},
    "SocketBossFillet": {"BossFilletR"},
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
    "CboreFloorReference": {"CboreFloor"},
}
# Places.  The outline prints .X: the clips and guides locate from the holes,
# not the edges.  The thickness prints .XXX: it is spent by the paper-drive
# assembly's disc-to-platen air budget (the back face rides the bar, so the
# thickness sets the front face).  The boss Ø and height print .X: the boss
# keeps its wall round the tap (SOCKET_BOSS_WALL_MIN) and the clip-screw
# engagement through plate and boss stays far above 1.5D at that band; the
# root round prints its single limit (no band to spend) at .X.  Every
# hole coordinate is spent by the fixed-screw float over the clip's and the
# guides' patterns (test_pd_platen_refit): all .XXX.  The counterbore floor is
# a reference dimension.
POSITION_PLACES = 3
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "PlateProfile": {"Width": 1, "Height": 1},
    "Plate": {"Depth": 3},
    "SocketBossProfile": {"Boss2Dia": 1},
    "SocketBosses": {"BossH": 1},
    "SocketBossFillet": {"BossFilletR": 1},
    "Sockets": {name: POSITION_PLACES for name in DRAWING_DIMENSIONS["Sockets"]},
    "GuideHoles": {name: POSITION_PLACES for name in DRAWING_DIMENSIONS["GuideHoles"]},
    "CboreFloorReference": {"CboreFloor": 2},
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
# hole DRILLED at .XX, the head-recess depth at .XXX (the head sits sub-flush
# below the paper face), the counterbore Ø at .X (the head clears it by more
# than the .X band).
GUIDE_CALLOUT_PRECISION = {"hw-thruholedia": 2, "hw-cbdia": 1, "hw-cbdepth": 3}
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
# The thinnest printed plate under the deepest printed counterbore.
CBORE_FLOOR_MIN = (
    round(PLATE_THICKNESS, DRAWING_PRECISION_BY_NAME["Depth"])
    - printed_band_mm(DRAWING_PRECISION_BY_NAME["Depth"])
    - round(CBORE_DEPTH, GUIDE_CALLOUT_PRECISION["hw-cbdepth"])
    - printed_band_mm(GUIDE_CALLOUT_PRECISION["hw-cbdepth"])
)
if CBORE_FLOOR_MIN < CBORE_FLOOR_ACCEPTED_MIN:
    raise AssertionError(
        f"counterbore floor {CBORE_FLOOR_MIN:.3f} is thinner than the user-accepted "
        f"{CBORE_FLOOR_ACCEPTED_MIN}"
    )
# The floor's reference dimension states that worst case as plain fact at the
# callout (Main's ruling, option A).
CBORE_FLOOR_CALLOUT = f"C'BORE FLOOR\n{CBORE_FLOOR_MIN:.2f} MIN WORST CASE"
# The smallest printed boss round the #2-56 major, concentric with its tap.
SOCKET_BOSS_WALL_MIN = (
    SOCKET_BOSS_DIA - printed_band_mm(DRAWING_PRECISION_BY_NAME["Boss2Dia"])
) / 2.0 - THREAD_MAJOR_MM[SOCKET_SPEC.size] / 2.0
if SOCKET_BOSS_WALL_MIN < 2.0:
    raise AssertionError(
        f"socket boss wall {SOCKET_BOSS_WALL_MIN:.3f} under the rule-17 2.0 target"
    )

ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:4"
# The right view shows no hidden lines (r4): section A-A draws the counterbore
# the floor reference measures.
RIGHT_VIEW_NOTE = "ENLARGED RIGHT VIEW SCALE 1:1"
