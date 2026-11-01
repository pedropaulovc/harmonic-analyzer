r"""Platen plate nominals (book ch. 22, pp. 54-55).

PURE DATA, no SolidWorks/COM calls and no ``build_*`` module in its import
closure: the plate envelope, the clip-screw receivers and the guide-screw
counterbored through-holes. ``build_pd_platen`` authors the part from these; the
clip, the guide rails and the paper-drive assembly read them here instead of
importing the builder, whose sketch recipe would otherwise ride their cache
keys (#880).

Issue #290: the sheet prints decimal inch (``drawing_unit: in``). Lengths stay
physical millimetres, each the exact decimal of its printed inch value, except
the envelope (width, height, thickness) that _recording_geometry and the pen
hanger read: those keep their millimetre nominals and print rounded, so every
check below is judged at the printed limits (``printed_deviations``).
"""

from __future__ import annotations

import math

import _config
from _hole_spec import CLEARANCE_MM, THREAD_MAJOR_MM, HoleSpec
from _inch_wall_limits import WALL_TARGET_MM
from _package_units import drawing_unit
from _printed_tolerance import inside_corner_radius_mm, printed_deviations
from sh_vn_brass_fillister_screw_spec import HEAD_H as FILLISTER_HEAD_H

UNIT = drawing_unit("parts/pd-platen", _config.parts("pd-platen"))

PLATE_WIDTH = 269.64  # ch30-p002 Pose Studio: 300 * 0.8988 (user fit); prints 10.62
PLATE_HEIGHT = PLATE_WIDTH / 2.0  # user-confirmed front-face H:W = 1:2; prints 5.31
# DIMENSIONS.md ch22: p.55 edge-on photo (low) read ~4; thinned to 3.85
# (R9-68) with the back face, which carries the rack, held on the bar front:
# the front face moves 0.15 rearward to open the disc-to-platen air.
PLATE_THICKNESS = 3.85  # prints .152

# Clip-screw receivers: the stock 92446A077 brass #2-56 slotted pan head
# (pd-vn-platen-clip-screw) sits directly on the clip's flat .032 brass sheet
# (ch22 img03: no raised seat, small heads), and its shank reaches through a
# #2-56 tap through the plate and a boss standing SOCKET_BOSS_H proud of the
# back face at each station, so the thread engages >= 1.5D (drawing-guidelines.md rule 18 (thread engagement)) and the
# screw tip finishes flush with the boss's rear face. These must be through
# taps: no blind receiver here can accept the exact 1/4-in under-head length
# without bottoming. The bosses stand above the top guide rail's band, where
# nothing but the clip-screw tips rides the back.
SOCKET_SPEC = HoleSpec("tapped", "#2-56")
SOCKET_BOSS_DIA = (
    7.112  # .28: wall round the #2-56 major (rule 17, SOCKET_BOSS_WALL_MIN)
)
# 1/4 shank - .032 clip sheet - 3.85 plate: the boss closes the stack so the
# tip finishes flush (a closure on the kept plate thickness, so it prints
# .07 rounded). build_pd_platen_clip asserts it against the live screw and sheet.
SOCKET_BOSS_H = 1.6872
SOCKET_THREAD_ENGAGEMENT = PLATE_THICKNESS + SOCKET_BOSS_H
# Each boss meets the back face in a root round. Nothing seats on that corner
# (only the clip-screw tips ride the back there), so the title block's INSIDE
# CORNERS limit governs it unprinted (machinist review round 2: a tighter
# printed R.020 MAX only narrowed the cutter choice). The model carries a
# round inside that limit; the paper-drive assembly's lock-station sweep grows
# each boss by the limit, not the model's round.
SOCKET_BOSS_FILLET_R = 0.508  # .020, modelled
SOCKET_BOSS_ROOT_R_MAX = inside_corner_radius_mm(unit=UNIT)
if SOCKET_BOSS_FILLET_R > SOCKET_BOSS_ROOT_R_MAX:
    raise AssertionError("modelled boss root round exceeds the title block's limit")
# Each socket's distance in from its side edge, on both sides: the clip's
# hole row (.145 from its outer edge, build_pd_platen_clip) plus .025, so the
# clip's outer edge stays on the plate at the printed worst case and its
# inboard edge stays 2.0 off the recording paper's 14.6 left inset
# (test_pd_platen_refit asserts both and the tap's edge ligament).
SOCKET_X = 4.318  # .170
# The two rows are the clip's hole stations with its top end flush with the
# plate's top edge: PLATE_HEIGHT - CLIP_LENGTH + HOLE_INSET and
# PLATE_HEIGHT - HOLE_INSET (3.29 clip, .283 inset). The kept plate height
# makes them closures, printed .XXX rounded (2.301, 5.025).
SOCKET_XY = (
    (SOCKET_X, 58.4422),
    (SOCKET_X, 127.6318),
    (PLATE_WIDTH - SOCKET_X, 58.4422),
    (PLATE_WIDTH - SOCKET_X, 127.6318),
)

# Guide-screw through-holes: 2 rows of 5 (heads on the front face, shanks
# into the guide rails on the back). ONE counterbored #4 fillister Hole
# Wizard feature; the artefact counterbore dims are preserved as overrides.
# #4 LOOSE through (user ruling 2026-10-14, rule-21 float stack): the screws
# are fixed in the guides' taps, so each hole's float over the shank must hold
# the guide's tap position and this plate's own .XXX hole coordinates
# (test_pd_platen_refit); the artefact Ø3.0 floated 0.155 against 0.20.
GUIDE_HOLE_FIT = "loose"
GUIDE_HOLE_DIA = CLEARANCE_MM[("#4", GUIDE_HOLE_FIT)]  # 3.658 (.144)
# A tenth, three tenths ... of the width, on the .001 grid; the guide rails
# (pd_platen_guide) read the same stations.
GUIDE_HOLE_X = (
    26.9748,  # 1.062
    80.899,  # 3.185
    134.8232,  # 5.308
    188.7474,  # 7.431
    242.6716,  # 9.554
)
# Bottom / top rail tap rows: the assembly's fixed rail seats (machine 283.734
# / 317.734) plus the rails' .140 tap row (pd_platen_guide_spec.TAP_Y, owner
# ruling 2026-11-01, B2), less the platen bottom (273.234); they keep those
# millimetres and print .553 / 1.892.
GUIDE_HOLE_Y = (14.056, 48.056)
GUIDE_HOLE_XY = tuple((x, y) for y in GUIDE_HOLE_Y for x in GUIDE_HOLE_X)

# Front-face counterbores recess the stock .183 x .107 fillister heads
# exactly .008 below the front face so the recording paper lies flat.
# The Ø.26 counterbore remains ample for the stock head.
HEAD_RECESS = 0.2032  # .008
CBORE_DIA = 6.604  # .26
CBORE_DEPTH = FILLISTER_HEAD_H + HEAD_RECESS  # .115

# Counterbore floor: the plate left under each guide-screw head.  USER-ACCEPTED
# rule-17 exception (2026-10-14, pd-platen RV-02): .037 nominal and
# CBORE_FLOOR_MIN (.027) at the printed worst case, under the .060 floor.  The
# plate is brass and the #4 guide screws are hand-tight: the floor's shear
# ring under the head (pi x .144 x .027, about 7.9 mm^2) carries only that
# clamp.  The sheet prints
# the floor as a reference dimension in section A-A, a partial section through
# the top row's middle hole (r4 asked for a cut, not hidden lines): the hidden
# CboreFloorReference sketch lies in the cutting plane (CBORE_SECTION_PLANE,
# x = CBORE_SECTION_X), mid-annulus below that hole.  The value stands left
# of its extension lines, so they run clear of its text (r5).
# The worst case may never fall below the accepted 0.67 mm.
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
# Places.  The outline prints .XX: the right-hand sockets locate from the left
# edge, so the width's band reaches their edge ligament.  The thickness prints
# .XXX: it is spent by the paper-drive assembly's disc-to-platen air budget
# (the back face rides the bar, so the thickness sets the front face).  The
# boss Ø prints .XX (its wall round the tap, SOCKET_BOSS_WALL_MIN), its height
# .XX (no mate: the flush tip is nominal and the engagement minimum reads the
# shortest screw, not the boss); its root round is the title block's.
# Every hole coordinate is spent by the fixed-screw float over the clip's and
# the guides' patterns (test_pd_platen_refit): all .XXX.  The counterbore
# floor is a reference dimension.
POSITION_PLACES = 3
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "PlateProfile": {"Width": 2, "Height": 2},
    "Plate": {"Depth": 3},
    "SocketBossProfile": {"Boss2Dia": 2},
    "SocketBosses": {"BossH": 2},
    "Sockets": {name: POSITION_PLACES for name in DRAWING_DIMENSIONS["Sockets"]},
    "GuideHoles": {name: POSITION_PLACES for name in DRAWING_DIMENSIONS["GuideHoles"]},
    "CboreFloorReference": {"CboreFloor": 3},
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
# hole DRILLED at a three-place inch size, the head-recess depth at .XXX (the
# head sits sub-flush below the paper face), the counterbore Ø at .XX (the
# head clears it by more than the .XX band).
GUIDE_CALLOUT_PRECISION = {"hw-thruholedia": 3, "hw-cbdia": 2, "hw-cbdepth": 3}
_CBORE_DEPTH_LOWER, _CBORE_DEPTH_UPPER = printed_deviations(
    CBORE_DEPTH, GUIDE_CALLOUT_PRECISION["hw-cbdepth"], unit=UNIT
)
_THICKNESS_LOWER, _THICKNESS_UPPER = printed_deviations(
    PLATE_THICKNESS, DRAWING_PRECISION_BY_NAME["Depth"], unit=UNIT
)
# The shallowest printed counterbore still sinks the stock fillister head.
HEAD_RECESS_MIN = CBORE_DEPTH + _CBORE_DEPTH_LOWER - FILLISTER_HEAD_H
if HEAD_RECESS_MIN <= 0.0:
    raise AssertionError(
        f"guide-screw heads stand proud at the shallowest counterbore: {HEAD_RECESS_MIN}"
    )
# The thinnest printed plate under the deepest printed counterbore.
CBORE_FLOOR_MIN = (
    PLATE_THICKNESS + _THICKNESS_LOWER - (CBORE_DEPTH + _CBORE_DEPTH_UPPER)
)
if CBORE_FLOOR_MIN < CBORE_FLOOR_ACCEPTED_MIN:
    raise AssertionError(
        f"counterbore floor {CBORE_FLOOR_MIN:.3f} is thinner than the user-accepted "
        f"{CBORE_FLOOR_ACCEPTED_MIN}"
    )
# The floor's reference dimension states that worst case as plain fact at the
# callout (Main's ruling, option A), floored to .XXX so it never overstates it.
_FLOOR_MIN_IN = math.floor(CBORE_FLOOR_MIN / 25.4 * 1000.0 + 1e-9) / 1000.0
CBORE_FLOOR_CALLOUT = (
    f"C'BORE FLOOR\n{f'{_FLOOR_MIN_IN:.3f}'.lstrip('0')} MIN WORST CASE"
)
# The smallest printed boss round the #2-56 major, concentric with its tap.
SOCKET_BOSS_WALL_MIN = (
    SOCKET_BOSS_DIA
    + printed_deviations(
        SOCKET_BOSS_DIA, DRAWING_PRECISION_BY_NAME["Boss2Dia"], unit=UNIT
    )[0]
) / 2.0 - THREAD_MAJOR_MM[SOCKET_SPEC.size] / 2.0
if SOCKET_BOSS_WALL_MIN < WALL_TARGET_MM:
    raise AssertionError(
        f"socket boss wall {SOCKET_BOSS_WALL_MIN:.3f} under the rule-17 .080 target"
    )

ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:4"
# The right view shows no hidden lines (r4): section A-A draws the counterbore
# the floor reference measures.
RIGHT_VIEW_NOTE = "ENLARGED RIGHT VIEW SCALE 1:1"
