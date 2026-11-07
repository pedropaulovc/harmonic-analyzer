r"""Pure-data dimensional contract shared by the pinion lift rod and drawing."""

from __future__ import annotations

import math

import _config
import pinion_rig_layout as _rig
from _fit_shaft_h import SHAFT_H
from _gtol_cylinder import CylinderFace
from _package_units import drawing_unit
from _printed_tolerance import printed_band_mm
from _surface_finish import MACHINED_UM, SurfaceFinishControl
from dt_pinion_cam_geometry import CAM_LEN as _CAM_LEN
from dt_pinion_cam_geometry import SET_SCREW_Z as _CAM_SET_SCREW_Z
from pinion_rig_layout import LIFT_ROD_LEN

UNIT = drawing_unit("parts/dt-pinion-lift-rod", _config.parts("dt-pinion-lift-rod"))
ROD_DIA = 6.35
# Back end flush with the back block, front end the lever hub's seat past the
# front block; ruling (c) moved that block inboard (pinion_rig_layout),
# 202 -> 192.0 (Codex #854), then 197.0 so the hub clears the block at the
# worst fitted stack, both blocks' .XX depth bands included
# (pinion_rig_layout.lift_rod_seat_stack, Codex #837/#854), then 197.5 for
# the deeper E-a blocks (Codex #858), then 197.8 for the drum's end shim
# (Main, #858 ruling 3), then 198.8 for the 11.0 blocks, then 199.5 for the
# 0.45 drum shim, the 6.25 back-collar pin plane and RIG_MARGIN_SPARE past
# the lever seat (Main, #858), then 198.3 once the back collar went on its
# leaf F (user ruling P1-1): the lever throw plane's air to the torque shaft's
# front end now sizes it, not the seat.
ROD_LEN = LIFT_ROD_LEN
# #290: the crown's sphere radius snaps to .19, and the crown height follows
# from it on the 1/4 in diameter (1.19, the old 1.2).
CAP_R = 4.826  # .19
CAP_SAG = CAP_R - math.sqrt(CAP_R**2 - ROD_DIA**2 / 4.0)
ROD_DIA_BAND = SHAFT_H

LEVER_NUMBER = "MHA-DT-16"
PIVOT_BLOCK_NUMBER = "MHA-DT-18"
CAM_NUMBER = "MHA-DT-23"

# --- Set-screw flats: rule-23 retention, owner ruling 2026-11-07 (MHA-DT-00
# rubric sample, PR #2248).  Each MHA-DT-23 cam is
# held on the rod by one staked #2-56 flat-point set screw at a feeler-set
# station (drive torque, reversing); a flat under each screw gives the point
# a seat that cannot walk round the rod (owner question 2, option A).  The
# derivation is the owner sketch's (owner_q2_rule23_sketch.py, panel 2) from
# the rig's own layout, so a rig change moves the flats with it.
#
# The flats are .012 deep, the MHA-CH-04 fulcrum shaft's set-screw flat
# (ch_fulcrum_shaft_spec.FLAT_DEPTH), a precedent, not a shared contract.
FLAT_DEPTH = 0.3048  # .012
FLAT_HEIGHT = ROD_DIA / 2.0 - FLAT_DEPTH  # the flat above the rod axis
ACROSS_FLAT = ROD_DIA - FLAT_DEPTH  # 6.0452 (.238): the printed size
FLAT_LENGTH_PLACES = 2
FLAT_STATION_PLACES = 3
ACROSS_FLAT_PLACES = 3
_IN = 25.4

# The cam's printed grades and its screw, restated: dt_pinion_cam_spec reads
# this module (the rod diameter), so this module cannot import it back.  The
# drawing script, which may import both, proves every value at import time.
# One pitch off the major each side is the screw's 45 deg point (the
# ch_pivot_bracket_spec.SET_SCREW_POINT_DIA convention): the face that seats.
CAM_UNIT = drawing_unit("parts/dt-pinion-cam", _config.parts("dt-pinion-cam"))
CAM_LENGTH_PLACES = 2
CAM_SET_SCREW_Z_PLACES = 2
CAM_SET_SCREW_MAJOR_MAX = 0.086 * _IN
CAM_SET_SCREW_PITCH = _IN / 56.0
SET_SCREW_POINT_DIA = CAM_SET_SCREW_MAJOR_MAX - 2.0 * CAM_SET_SCREW_PITCH

# Each cam's screw station, from the rod's back rim (the crown rim, ROD_LEN
# from the flat front end), which the rig sets flush with the back block's
# outer face: the front cam's front face stands its leaf (pinion_rig_fitup
# FRONT_COLLAR_LEAF, the front block feeler) off the front block's inner
# face, the back cam's back face leaf F off the back block's.
_RIM_Z = _rig.BACK_BLOCK_OUTER_Z
if abs(_rig.LIFT_ROD_Z0 + ROD_LEN - _RIM_Z) > 1e-9:
    raise AssertionError("the lift rod's back rim is not flush with the back block")
_CAM_FRONT_FACE_Z = {
    "front": _rig.FRONT_BLOCK_Z0 + _rig.BLOCK_DEPTH + _rig.FRONT_BLOCK_FEELER,
    "back": _rig.BACK_BLOCK_Z0 - _rig.BACK_COLLAR_LEAF_F - _CAM_LEN,
}
SCREW_FROM_RIM = {
    key: _RIM_Z - (face + _CAM_SET_SCREW_Z) for key, face in _CAM_FRONT_FACE_Z.items()
}
# Where each screw can land about that station: every band and set error in
# the chain from the rim-flush rod to the cam's tap (the sketch's terms).
_BLOCK_XX = printed_band_mm(_rig.BLOCK_DEPTH_PLACES, unit=_rig.BLOCK_UNIT)
_STRAP_XX = printed_band_mm(_rig.STRAP_T_PLACES, unit=_rig.STRAP_UNIT)
_CAM_LEN_XX = printed_band_mm(CAM_LENGTH_PLACES, unit=CAM_UNIT)
_CAM_STATION_XX = printed_band_mm(CAM_SET_SCREW_Z_PLACES, unit=CAM_UNIT)
SCREW_STATION_TERMS: dict[str, dict[str, float]] = {
    "front": {
        "back MHA-DT-18 depth": _BLOCK_XX,
        "2X MHA-DT-14 thickness": 2.0 * _STRAP_XX,
        "MHA-DT-01 drum length": _rig.DRUM_LEN_BAND,
        "drum end shim set error": _rig.DRUM_END_SHIM_SET_ERROR,
        "front block feeler band": _rig.FRONT_BLOCK_FEELER_BAND,
        "front cam leaf set error": _rig.FEELER_SET_ERROR,
        "MHA-DT-23 tap station": _CAM_STATION_XX,
        "rod rim flush set": _rig.FLUSH_SET_ERROR,
    },
    "back": {
        "back MHA-DT-18 depth": _BLOCK_XX,
        "back cam leaf F set error": _rig.FEELER_SET_ERROR,
        "MHA-DT-23 length": _CAM_LEN_XX,
        "MHA-DT-23 tap station": _CAM_STATION_XX,
        "rod rim flush set": _rig.FLUSH_SET_ERROR,
    },
}
SCREW_HALF_RANGE = {key: sum(terms.values()) for key, terms in SCREW_STATION_TERMS.items()}
# Each flat covers its whole range plus the screw's major, up to the .XX grid;
# its rim-side edge, the printed station, sits on the .XXX grid round the
# nominal tap station.  Centres follow from the two.
_LENGTH_GRID = _IN / 10**FLAT_LENGTH_PLACES
_STATION_GRID = _IN / 10**FLAT_STATION_PLACES
FLAT_LEN = {
    key: round(
        math.ceil((2.0 * half + CAM_SET_SCREW_MAJOR_MAX) / _LENGTH_GRID - 1e-9)
        * _LENGTH_GRID,
        9,
    )
    for key, half in SCREW_HALF_RANGE.items()
}
FLAT_EDGE_FROM_RIM = {
    key: round(round((SCREW_FROM_RIM[key] - FLAT_LEN[key] / 2.0) / _STATION_GRID) * _STATION_GRID, 9)
    for key in FLAT_LEN
}
FLAT_FROM_RIM = {key: FLAT_EDGE_FROM_RIM[key] + FLAT_LEN[key] / 2.0 for key in FLAT_LEN}
FRONT_FLAT_LEN = FLAT_LEN["front"]  # 5.588 (.22)
BACK_FLAT_LEN = FLAT_LEN["back"]  # 4.318 (.17)
FRONT_FLAT_EDGE_FROM_RIM = FLAT_EDGE_FROM_RIM["front"]  # 166.268 (6.546), printed
BACK_FLAT_EDGE_FROM_RIM = FLAT_EDGE_FROM_RIM["back"]  # 14.808 (.583), printed
FRONT_FLAT_FROM_RIM = FLAT_FROM_RIM["front"]  # 169.062 (6.656), centre
BACK_FLAT_FROM_RIM = FLAT_FROM_RIM["back"]  # 16.967 (.668), centre

# Worst case of the printed bands (inch title block) and the rig's set
# errors together: the screw's point lies wholly on its flat.
_LENGTH_BAND = printed_band_mm(FLAT_LENGTH_PLACES, unit=UNIT)
_STATION_BAND = printed_band_mm(FLAT_STATION_PLACES, unit=UNIT)
_ACROSS_FLAT_BAND = printed_band_mm(ACROSS_FLAT_PLACES, unit=UNIT)
_POINT_R = SET_SCREW_POINT_DIA / 2.0
SCREW_POINT_ON_FLAT_MARGIN_MM = min(
    min(
        SCREW_FROM_RIM[key] - SCREW_HALF_RANGE[key] - _POINT_R
        - (FLAT_EDGE_FROM_RIM[key] + _STATION_BAND),
        FLAT_EDGE_FROM_RIM[key] - _STATION_BAND + FLAT_LEN[key] - _LENGTH_BAND
        - (SCREW_FROM_RIM[key] + SCREW_HALF_RANGE[key] + _POINT_R),
    )
    for key in FLAT_LEN
)
if SCREW_POINT_ON_FLAT_MARGIN_MM <= 0.0:
    raise AssertionError(
        f"a cam's set-screw point can run off its flat ({SCREW_POINT_ON_FLAT_MARGIN_MM:.3f})"
    )
# The shallowest flat (least rod, largest AcrossFlat) still seats the point.
_ROD_R_MIN = (ROD_DIA + ROD_DIA_BAND[1]) / 2.0
_FLAT_DEPTH_MIN = 2.0 * _ROD_R_MIN - (ACROSS_FLAT + _ACROSS_FLAT_BAND)
FLAT_CHORD_MIN = 2.0 * math.sqrt(2.0 * _ROD_R_MIN * _FLAT_DEPTH_MIN - _FLAT_DEPTH_MIN**2)
if FLAT_CHORD_MIN <= SET_SCREW_POINT_DIA:
    raise AssertionError(
        f"shallowest flat is {FLAT_CHORD_MIN:.3f} wide, under the screw's "
        f"{SET_SCREW_POINT_DIA:.3f} point"
    )
if not 0.0 < BACK_FLAT_EDGE_FROM_RIM - _STATION_BAND:
    raise AssertionError("the back set-screw flat runs onto the crown")
# For the record, not gated (the owner sketch's option A accepts both): at
# the worst case, how far each flat stays inside its cam's hub (negative: its
# end shows past the hub face) and clear of the nearer MHA-DT-18 bore face
# (negative: it runs under that bore's mouth).  The hub faces move with the
# blocks' chain plus the cam's leaf and length; the screw sits SET_SCREW_Z
# behind the cam's front face.
_BLOCK_FACE_SHIFT = {
    "front": sum(
        value
        for name, value in SCREW_STATION_TERMS["front"].items()
        if "leaf" not in name and "station" not in name
    ),
    "back": _BLOCK_XX + _rig.FLUSH_SET_ERROR,
}
_HUB_FACE_SHIFT = {  # (front face, back face)
    "front": (
        _BLOCK_FACE_SHIFT["front"] + _rig.FEELER_SET_ERROR,
        _BLOCK_FACE_SHIFT["front"] + _rig.FEELER_SET_ERROR + _CAM_LEN_XX,
    ),
    "back": (
        _BLOCK_FACE_SHIFT["back"] + _rig.FEELER_SET_ERROR + _CAM_LEN_XX,
        _BLOCK_FACE_SHIFT["back"] + _rig.FEELER_SET_ERROR,
    ),
}
FLAT_HUB_COVER_MM = {
    key: min(
        SCREW_FROM_RIM[key] + _CAM_SET_SCREW_Z - _HUB_FACE_SHIFT[key][0]
        - (FLAT_EDGE_FROM_RIM[key] + _STATION_BAND + FLAT_LEN[key] + _LENGTH_BAND),
        FLAT_EDGE_FROM_RIM[key] - _STATION_BAND
        - (SCREW_FROM_RIM[key] - (_CAM_LEN - _CAM_SET_SCREW_Z) + _HUB_FACE_SHIFT[key][1]),
    )
    for key in FLAT_LEN
}
FLAT_TO_BLOCK_MM = {
    "front": _RIM_Z - (_rig.FRONT_BLOCK_Z0 + _rig.BLOCK_DEPTH) - _BLOCK_FACE_SHIFT["front"]
    - (FRONT_FLAT_EDGE_FROM_RIM + _STATION_BAND + FRONT_FLAT_LEN + _LENGTH_BAND),
    "back": BACK_FLAT_EDGE_FROM_RIM - _STATION_BAND
    - (_RIM_Z - _rig.BACK_BLOCK_Z0) - _BLOCK_FACE_SHIFT["back"],
}

# Clocking.  The flats are the rod's angular datum: the cams are set and
# staked on them (MHA-DT-00 step cam-collars-set) BEFORE the MHA-DT-30 pin
# hole is match-drilled through the lever hub (step lever-pin-set), so the
# hole's clocking to the flats is made at assembly and this sheet prints
# none.  The model still carries the assembly's relation, so each screw bears
# square on its flat in MHA-DT-00: the assembly phases the rod to the lever
# (build_dt_drive_train_assembly LIFT_ROD_ROWS = rot_z_rows(LEVER_TILT_DEG))
# and keeps the cams' rows the identity (PINION_CAM_ROWS), heavy side and tap
# straight down (build_dt_pinion_cam: the tap enters at cam-local -Y).  With
# Transform2 rows (world = local @ rows, rows orthonormal) the screw axis in
# the rod's frame is rows @ world: the flat's outward normal.  The test pins
# ROD_PHASE_DEG and both axes to the assembly and cam recipes.
ROD_PHASE_DEG = 10.0  # build_dt_drive_train_assembly.LEVER_TILT_DEG
CAM_SET_SCREW_AXIS_LOCAL = (0.0, -1.0, 0.0)
_PHASE = math.radians(ROD_PHASE_DEG)
_ROD_ROWS = (
    (math.cos(_PHASE), math.sin(_PHASE), 0.0),
    (-math.sin(_PHASE), math.cos(_PHASE), 0.0),
    (0.0, 0.0, 1.0),
)
FLAT_NORMAL_LOCAL = tuple(
    round(sum(r * w for r, w in zip(row, CAM_SET_SCREW_AXIS_LOCAL, strict=True)), 12)
    for row in _ROD_ROWS
)  # (-sin 10, -cos 10, 0)
# Signed about the rod's +Z from local +X, the modelled pin hole's axis.
FLAT_NORMAL_FROM_PIN_AXIS_DEG = math.degrees(
    math.atan2(FLAT_NORMAL_LOCAL[1], FLAT_NORMAL_LOCAL[0])
)  # -100.0
# The flats' sketch plane holds the rod axis and the normal; the named view
# looks square at it, flats up, crown end left as on the side view.
FLAT_PLANE = "FlatPlane"
FLATS_VIEW = "SET SCREW FLATS"

# drawing-guidelines.md rule 6 (roughness symbols only where a surface runs, slides or locates): the rod turns in the pivot blocks' west bores -- the one running
# surface on the part.
SURFACE_FINISHES = (
    SurfaceFinishControl(
        "bearing", MACHINED_UM, CylinderFace(ROD_DIA), display_unit=UNIT
    ),
)

# One revolved half-profile carries the rod's size, body length, crown and
# overall, so all four print on the side view, as the part sits in the lathe
# (drawing-guidelines.md rule 11 (turned parts read like the lathe)).
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "RodProfile": {"RodDia", "RodBody", "CapR", "RodOverall"},
    # U36: the MHA-DT-30 pin hole, located from the flat front end face -- the
    # part origin sits on that face, so the circle's own anchor IS the
    # front-end baseline (drawing-guidelines.md rule 10 (dimension from a real feature)).
    "PinHoleProfile": {"PinHoleDia", "PinHoleZ"},
    # The set-screw flats' sketch (FLAT_PLANE) carries both lengths, both
    # rim-side edges off the crown rim -- the datum the rig sets flush with
    # the back block, so the stations read straight against the cams'
    # feeler-set screws -- and the one across-flat size both flats share.
    "FlatProfile": {
        "FrontFlatLen",
        "BackFlatLen",
        "FrontFlatFromRim",
        "BackFlatFromRim",
        "AcrossFlat",
    },
}
# The overall (front face to crown apex) prints in parentheses: the body
# length to the crown rim is the controlling size, because the rig's worst
# fitted stack (pinion_rig_layout) reads its .XX band (machinist review r1:
# the body length alone read like an overall that was not one, rule 10).
DRAWING_REFERENCE_DIMENSIONS = frozenset({"RodOverall"})

# Decimal places ARE the tolerance statement (drawing-simplicity-policy.md `How the repository implements the guidelines`); the part authors
# them and the drawing reads them back.  Four on the banded bearing diameter;
# three on the drilled pin hole, which takes the title block's DRILLED HOLES
# row (.064, +.004/0); two on the length the rig's stacks read, the crown, the
# reference overall and the pin station, which the lever's mid-engagement
# sets at assembly.  The flats: two on their lengths, three on their stations
# and the across-flat size, the grades SCREW_POINT_ON_FLAT_MARGIN_MM and
# FLAT_CHORD_MIN are proved at (.XX stations let the back cam's point run off
# its flat).
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "RodProfile": {"RodDia": 4, "RodBody": 2, "CapR": 2, "RodOverall": 2},
    "PinHoleProfile": {"PinHoleDia": 3, "PinHoleZ": 2},
    "FlatProfile": {
        "FrontFlatLen": FLAT_LENGTH_PLACES,
        "BackFlatLen": FLAT_LENGTH_PLACES,
        "FrontFlatFromRim": FLAT_STATION_PLACES,
        "BackFlatFromRim": FLAT_STATION_PLACES,
        "AcrossFlat": ACROSS_FLAT_PLACES,
    },
}
_PRECISION_NAMES = [
    (feature, name) for feature, names in DRAWING_PRECISION.items() for name in names
]
DRAWING_PRECISION_BY_NAME: dict[str, int] = {
    name: DRAWING_PRECISION[feature][name] for feature, name in _PRECISION_NAMES
}
if len(DRAWING_PRECISION_BY_NAME) != len(_PRECISION_NAMES):
    raise AssertionError("DRAWING_PRECISION repeats a dimension name across features")
if set(DRAWING_PRECISION_BY_NAME) != set().union(*DRAWING_DIMENSIONS.values()):
    raise AssertionError("every marked dimension must state its decimal places")

# drawing-guidelines.md rule 4 (tighten only for function, and name the mate):
# the h band rides the diameter because the rod turns in the two MHA-DT-18
# blocks' reamed lift bores (+.0015/+.0010 slide band); ground 1/4 in shafting
# already holds it, so the stock is good enough as supplied (machinist review
# r1: the band and Ra named no mate).
ROD_DIA_CALLOUT = "\n".join(
    (
        f"RUNNING FIT IN {PIVOT_BLOCK_NUMBER} LIFT BORES,",
        "1/4 IN GROUND STOCK OK",
    )
)

# drawing-guidelines.md rule 7 (notes: few, flagged, never a method): the matched fit rides the pin hole's own callout, as the hole
# specification only; the drive and peen are
# dt_pinion_lever_pin_spec.ASSEMBLY_STEP (LEVER PIN SET).  The sheet carries
# no general notes: the SR view defines the crown (machinist review r1).
PIN_HOLE_CALLOUT = "\n".join(
    (
        "MATCH-DRILL THRU AT ASSEMBLY",
        f"IN {LEVER_NUMBER} HUB",
    )
)
# drawing-guidelines.md rule 4: the three-place flat sizes name the mate, and
# one AcrossFlat governs both flats in one plane.  One line under the value
# (rule 7, round-6 review #2): VIEW B shows the flats in line on one side, and
# the stations' extension lines land on the crown rim, so no words say either.
ACROSS_FLAT_CALLOUT = f"SET SCREW FLATS FOR 2X {CAM_NUMBER}"
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:2"
