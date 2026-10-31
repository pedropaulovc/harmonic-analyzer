"""Custom MHA-DT-VN-54 stack collar and its stock set screw, mm.

9414T1 was the historical 1/16-inch collar, not a 1/32-inch product. Live
McMaster 1/32-inch collars (6435K234, 6436K236, 6157K64; 2026-10-08) are
clamp-on alternatives, not unavailable products. This custom design preserves
the existing set-screw mechanism and is turned from 3/4-inch steel bar.
Its screw is genuine 94355A213, #2-56 x 5/16-inch 18-8 stainless flat point,
used as supplied: its flat point bears on the shaft's terminal D-flat, and
SCREW_LANDING_MARGIN_MM gates that it can, from printed tolerances only.

The collar axis is +Y, south face y=0, north face y=WIDTH. The radial screw
is on +X, tapped through, at the tap station from the south face.
Default is installed; Collar and SetScrew configurations define the made
collar and the bought screw separately.
Set one COLLAR_FEELER off T006 and lock on the shaft D-flat. The block/cup
still control shaft end play, never the collar. Assembly owns the full
collar/block/plate air stack and moves the tip-end station for this envelope.
"""

from __future__ import annotations

import math

import _config

from _hole_spec import HoleSpec, TAP_DRILL_MM
from _printed_tolerance import printed_band_mm
from cone_shaft_land_bands import (
    RUNNING_DIA_BAND,
    TERMINAL_DIA_MM,
    TERMINAL_DIA_PLACES,
    TERMINAL_FINISHED_DIA_LIMITS_MM,
    TERMINAL_FINISHED_AF_LIMITS_MM,
    TERMINAL_FLAT_AF_MM,
    TERMINAL_FLAT_EDGE_BREAK_MAX,
    TERMINAL_HALF_CHORD_MIN_MM,
    TIP_COLLAR_AXIAL_PLACES,
    TIP_COLLAR_MAX_RADIAL_FLOAT_MM,
    TIP_COLLAR_WIDTH_MM,
    TIP_COLLAR_MIN_RADIAL_FLOAT_MM,
    TIP_COLLAR_WIDTH_BAND_MM,
    TIP_COLLAR_NOSE_LENGTH_MM,
    TIP_COLLAR_TAP_STATION_MM,
    TIP_COLLAR_FREE_EDGE_BREAK_MAX_MM,
)
from gear_seat_fit import seat_bore_band

IN = 25.4
STOCK_DIA = 3.0 * IN / 4.0
BORE_DIA = TERMINAL_DIA_MM
BORE_DIA_BAND = seat_bore_band(RUNNING_DIA_BAND)
# A real saved representative inside the SAME retained finished-bore limits.
# Modelling nominal shaft-size here used to create a concentric zero-clearance
# collar despite its positive printed bore band. Re-centering the dimension
# changes neither finished limit nor the named free-fit class.
BORE_MODEL_DIA_MM = BORE_DIA + sum(BORE_DIA_BAND) / 2.0
BORE_MODEL_DIA_BAND = tuple(value - sum(BORE_DIA_BAND) / 2.0 for value in BORE_DIA_BAND)
BORE_PRINTED_DIA_MM = round(BORE_MODEL_DIA_MM, TERMINAL_DIA_PLACES)
BORE_FINISHED_DIA_LIMITS_MM = (
    BORE_PRINTED_DIA_MM + BORE_MODEL_DIA_BAND[1],
    BORE_PRINTED_DIA_MM + BORE_MODEL_DIA_BAND[0],
)
INSTALLED_BORE_AXIS_OFFSET_MM = (BORE_MODEL_DIA_MM - TERMINAL_DIA_MM) / 2.0
NOSE_DIA = 6.40
NOSE_LENGTH = TIP_COLLAR_NOSE_LENGTH_MM
WIDTH = TIP_COLLAR_WIDTH_MM
WIDTH_BAND_MM = TIP_COLLAR_WIDTH_BAND_MM
TAP_STATION = TIP_COLLAR_TAP_STATION_MM
# The turned shoulder's tool-nose root prints R0.25 MAX: any root from sharp
# up to 0.25 is good, and the collar air stack (dt_tip_collar_air) books 0.25.
SHOULDER_ROOT_RADIUS = 0.25
# The title block's free-edge break: the wall, thread and contact budgets
# book it, but the model leaves the edges sharp (the title block prints it).
EDGE_BREAK = TIP_COLLAR_FREE_EDGE_BREAK_MAX_MM
FLAT_DISTANCE = 7.0
ROUTINE_BAND_MM = printed_band_mm(2)
# Width, nose and tap station: the title block's .XXX (cone_shaft_land_bands).
AXIAL_PLACES = TIP_COLLAR_AXIAL_PLACES
AXIAL_BAND_MM = printed_band_mm(AXIAL_PLACES)
WALL_TARGET_MM = 2.0

BOM_DESCRIPTION = str(_config.parts("dt-vn-cone-tip-collar")["description"])
MANUFACTURING_DESCRIPTIONS = {
    "Collar": "Turned steel cone tip stack collar",
    "SetScrew": "McMaster 94355A213 flat-point set screw, as supplied",
}

SET_SCREW_SKU = "94355A213"
SET_SCREW_THREAD = "#2-56"
SET_SCREW_MAJOR_DIA = 0.086 * IN
SET_SCREW_PITCH = IN / 56.0
# ASME B1.1 #2-56 pitch-diameter limits: stock external 3A MIN .0728 in,
# receiver internal 2B MAX .0772 in (BBI thread details / Amesweb UNC chart).
SET_SCREW_THREAD_RADIAL_PLAY_MM = (0.0772 - 0.0728) * IN / 2.0
REQUIRED_FULL_ENGAGEMENT_MM = 1.5 * SET_SCREW_MAJOR_DIA
SET_SCREW_LENGTH = 5.0 * IN / 16.0
SET_SCREW_LENGTH_BAND_MM = 0.01 * IN  # ASME B18.3 Table 14 note (11), L <= 0.63 in
SET_SCREW_SOCKET_AF = 0.035 * IN
SET_SCREW_SOCKET_DEPTH = 0.060 * IN  # Table 14 #2 minimum key engagement; not vendor-exact
# Supplier engineering drawing inspected 2026-10-19. Its .313 in label is the
# rounded presentation of the retained exact 5/16 in native length.
# Point diameter/angle and socket depth are ASME envelope assumptions, not
# dimensions published on this supplier drawing.
SET_SCREW_SUPPLIER_PAGE = "https://www.mcmaster.com/94355A213/"
SET_SCREW_SUPPLIER_DRAWING = (
    "https://www.mcmaster.com/mvC/Library/CAD2/20260604/1B55C491/"
    "94355A213_18-8%20Stainless%20Steel%20Flat-Tip%20Set%20ScrewX.GIF"
)
SET_SCREW_SUPPLIER_UNITS = "in"
SET_SCREW_SUPPLIER_PRECISION = 3
SET_SCREW_SUPPLIER_SIZES_MM = {
    "ScrewLength": SET_SCREW_LENGTH,
    "ScrewMajorDia": SET_SCREW_MAJOR_DIA,
    "SocketAF": SET_SCREW_SOCKET_AF,
}
SET_SCREW_SUPPLIER_DIMENSIONS = {
    "SetScrewProfile": {"ScrewLength", "ScrewMajorDia"},
    "SocketAFReference": {"SocketAF"},
}
SET_SCREW_SUPPLIER_TITLE = "\n".join((
    f"McMASTER {SET_SCREW_SKU} FLAT-POINT SET SCREW",
    "AS SUPPLIED - SUPPLIER REFERENCE ONLY",
    "CUSTOM COLLAR MANUFACTURING CONTROLS: SHEET 1",
))
SET_SCREW_END_FACE_MIN_ANGLE_DEG = 30.0  # Table 14 note (1): socket-face chamfer 30..45 deg
SET_SCREW_FACTORY_POINT_MIN_DIA = 0.039 * IN  # Table 14 #2 flat-point P MIN
SET_SCREW_FACTORY_POINT_MIN_ANGLE_DEG = 45.0  # Table 14 note (2), length >= B
# Coordinates in the collar's frame. The loaded collar centre moves toward
# +X; its bore seats on the shaft's -X round back. The screw's point face
# sits on the flat at that displaced position.
SET_SCREW_SEAT_RADIUS = (
    TERMINAL_FLAT_AF_MM - TERMINAL_DIA_MM / 2.0 - INSTALLED_BORE_AXIS_OFFSET_MM
)
SET_SCREW_END_RADIUS = SET_SCREW_SEAT_RADIUS + SET_SCREW_LENGTH
# Drilled and tapped through: no blind depth to hold, and the stock screw
# reaches the D-flat from the mounting flat.
TAP_DRILL_DIA = TAP_DRILL_MM[SET_SCREW_THREAD]
SET_SCREW_HOLE = HoleSpec("tapped", SET_SCREW_THREAD)
# Internal 2B has no standard root MAX. This is an explicit manufacturing
# limit, authored as a native MAX gauge diameter and printed beside the tap,
# so the envelope the wall budget books (WORST_WALLS_MM) is one the sheet
# enforces (Codjiflo review of #2101; the machinist review that asked to
# drop it is waived on this sheet).  Book its rounded PRINTED maximum.
THREAD_ENVELOPE_DIA = math.ceil((
    0.0772 * IN + 0.64951905 * SET_SCREW_PITCH + 0.10
) * 100.0) / 100.0
# The tap is located by its .XXX station from the south face; its centring
# on the bore axis is implied, not dimensioned, so it is booked at .XX. Its
# squareness to the mounting flat is the title block's angle.
TAP_STATION_BAND_MM = AXIAL_BAND_MM
TAP_LATERAL_BAND_MM = ROUTINE_BAND_MM
TAP_ANGLE_RAD = math.radians(float(_config.title_block("angular")["value_deg"]))
# The stock screw rocks in its 3A/2B play over the least full engagement the
# thread gate admits, on top of the tapped hole's own angle.
SET_SCREW_MAX_AXIS_ANGLE_RAD = TAP_ANGLE_RAD + math.atan(
    2.0 * SET_SCREW_THREAD_RADIAL_PLAY_MM / REQUIRED_FULL_ENGAGEMENT_MM
)
# The smallest shop-readable custom body that retains the 2.0 wall target at
# every printed limit.
BODY_RADIUS_REQUIREMENTS_MM = {
    "round bore wall": BORE_FINISHED_DIA_LIMITS_MM[1]/2.0 + 2.0*EDGE_BREAK + WALL_TARGET_MM,
    "tap to flat side rims": math.hypot(
        FLAT_DISTANCE+ROUTINE_BAND_MM,
        WALL_TARGET_MM+THREAD_ENVELOPE_DIA/2.0+EDGE_BREAK+TAP_LATERAL_BAND_MM,
    ),
}
OUTER_DIA = math.ceil((2.0*max(BODY_RADIUS_REQUIREMENTS_MM.values())+ROUTINE_BAND_MM)*100.0)/100.0

_BORE_MAX = BORE_FINISHED_DIA_LIMITS_MM[1]
_LAND_MIN = TERMINAL_FINISHED_DIA_LIMITS_MM[0]
_FLOAT_MAX = (_BORE_MAX - _LAND_MIN) / 2.0
_FLAT_MAX = TERMINAL_FINISHED_AF_LIMITS_MM[1] - _LAND_MIN / 2.0
_FLAT_MIN = TERMINAL_FINISHED_AF_LIMITS_MM[0] - TERMINAL_FINISHED_DIA_LIMITS_MM[1] / 2.0
# The screw's point face, in the collar frame, across the flat and float.
_POINT_PLANE_MIN = _FLAT_MIN - _FLOAT_MAX
_POINT_PLANE_MAX = _FLAT_MAX + _FLOAT_MAX
# The drilled hole crosses the bore, so the female thread is whole only
# outside the bore and its edge break, less one incomplete pitch.
_FEMALE_FULL_START_MAX = _BORE_MAX / 2.0 + EDGE_BREAK + SET_SCREW_PITCH

# Where the point lands across the flat. Each term is a printed tolerance:
# the tap's centring and angle (the angle swings about the hole's mouth on
# the mounting flat), the screw's thread play carried out to the point, and
# the collar's float on its journal.
_POINT_PROJECTION_MAX = _FEMALE_FULL_START_MAX - _POINT_PLANE_MIN
SCREW_POINT_LATERAL_OFFSETS_MM = {
    "tap centring": TAP_LATERAL_BAND_MM,
    "tap angle": math.tan(TAP_ANGLE_RAD) * (FLAT_DISTANCE + ROUTINE_BAND_MM - _POINT_PLANE_MIN),
    "screw thread play": SET_SCREW_THREAD_RADIAL_PLAY_MM * (
        1.0 + 2.0 * _POINT_PROJECTION_MAX / REQUIRED_FULL_ENGAGEMENT_MM
    ),
    "collar float": _FLOAT_MAX,
}
SCREW_POINT_LATERAL_OFFSET_MM = sum(SCREW_POINT_LATERAL_OFFSETS_MM.values())
# The flat's narrowest face, less its stoned torque corners.
FLAT_FACE_HALF_WIDTH_MIN_MM = TERMINAL_HALF_CHORD_MIN_MM - TERMINAL_FLAT_EDGE_BREAK_MAX
SCREW_POINT_RADIUS_MIN_MM = SET_SCREW_FACTORY_POINT_MIN_DIA / 2.0


def screw_landing_margin_mm(lateral_offset_mm: float) -> float:
    """Overlap criterion: the stock flat point's face must overlap the D-flat's
    face at its least width.

    The round falls away below the flat's plane on both sides, so a flat point
    square to the flat can bear only on the flat: any overlap lands it there.
    Positive is the overlap width left at the given lateral offset of the
    screw axis from the flat's centre line.
    """
    return FLAT_FACE_HALF_WIDTH_MIN_MM + SCREW_POINT_RADIUS_MIN_MM - lateral_offset_mm


SCREW_LANDING_MARGIN_MM = screw_landing_margin_mm(SCREW_POINT_LATERAL_OFFSET_MM)
# For information only, not gated: the point's centre against the flat face.
SCREW_POINT_CENTRE_MARGIN_MM = FLAT_FACE_HALF_WIDTH_MIN_MM - SCREW_POINT_LATERAL_OFFSET_MM

_OD_MIN_R = (OUTER_DIA - ROUTINE_BAND_MM) / 2.0
_OD_MAX_R = (OUTER_DIA + ROUTINE_BAND_MM) / 2.0
_THREAD_R = THREAD_ENVELOPE_DIA / 2.0
# The through hole's angle carries its far exit this far along the axis.
_TAP_AXIAL_DRIFT_MAX = math.tan(TAP_ANGLE_RAD) * (FLAT_DISTANCE + ROUTINE_BAND_MM + _OD_MAX_R)
WORST_WALLS_MM = {
    "bore to round OD": _OD_MIN_R - _BORE_MAX / 2.0 - 2.0 * EDGE_BREAK,
    "nose bore to round OD": (NOSE_DIA - ROUTINE_BAND_MM) / 2.0
        - _BORE_MAX / 2.0 - 2.0 * EDGE_BREAK,
    "bore to mounting flat": FLAT_DISTANCE - ROUTINE_BAND_MM - _BORE_MAX / 2.0
        - 2.0 * EDGE_BREAK,
    # The station is from the south face; the shoulder and north face move
    # independently on their own bands.
    "tap to south shoulder": TAP_STATION - TAP_STATION_BAND_MM - NOSE_LENGTH - AXIAL_BAND_MM
        - _THREAD_R - EDGE_BREAK - _TAP_AXIAL_DRIFT_MAX,
    "tap to north face": WIDTH - WIDTH_BAND_MM - TAP_STATION - TAP_STATION_BAND_MM
        - _THREAD_R - EDGE_BREAK - _TAP_AXIAL_DRIFT_MAX,
    "tap to flat side rims": math.sqrt(_OD_MIN_R**2 - (FLAT_DISTANCE + ROUTINE_BAND_MM)**2)
        - _THREAD_R - EDGE_BREAK - TAP_LATERAL_BAND_MM,
}
# Full male and female thread overlap, not nominal wall thickness. One pitch
# at each thread end and the receiver's mouth break are deducted separately.
_SCREW_TILT_PROJECTION_MM = SET_SCREW_MAJOR_DIA / 2.0 * math.sin(SET_SCREW_MAX_AXIS_ANGLE_RAD)
_STOCK_POINT_CHAMFER_MAX_MM = (
    (SET_SCREW_MAJOR_DIA - SET_SCREW_FACTORY_POINT_MIN_DIA) / 2.0
    / math.tan(math.radians(SET_SCREW_FACTORY_POINT_MIN_ANGLE_DEG))
)
_MALE_FULL_START_MAX = (
    _POINT_PLANE_MAX + 2.0 * _SCREW_TILT_PROJECTION_MM + _STOCK_POINT_CHAMFER_MAX_MM
    + SET_SCREW_PITCH
)
# The supplied socket-end face must exist outside the hex; at the smallest
# permitted chamfer angle its axial loss cannot exceed this radial envelope.
# This bounds the other male thread end; the model leaves the factory
# chamfer out.
_STOCK_FACE_CHAMFER_MAX = (
    (SET_SCREW_MAJOR_DIA - SET_SCREW_SOCKET_AF) / 2.0
    / math.tan(math.radians(SET_SCREW_END_FACE_MIN_ANGLE_DEG))
)
_STOCK_AXIAL_PROJECTION_LOSS_MM = (
    (SET_SCREW_LENGTH + SET_SCREW_LENGTH_BAND_MM)
    * (1.0 - math.cos(SET_SCREW_MAX_AXIS_ANGLE_RAD))
    + _SCREW_TILT_PROJECTION_MM
)
_MALE_FULL_END_MIN = (
    _POINT_PLANE_MIN + SET_SCREW_LENGTH - SET_SCREW_LENGTH_BAND_MM
    - _STOCK_FACE_CHAMFER_MAX - SET_SCREW_PITCH
    - _STOCK_AXIAL_PROJECTION_LOSS_MM
)
_FEMALE_FULL_END_MIN = FLAT_DISTANCE - ROUTINE_BAND_MM - EDGE_BREAK - SET_SCREW_PITCH
WORST_FULL_ENGAGEMENT_MM = min(_FEMALE_FULL_END_MIN, _MALE_FULL_END_MIN) - max(
    _MALE_FULL_START_MAX, _FEMALE_FULL_START_MAX,
)
WORST_SOCKET_ACCESS_MM = (
    _POINT_PLANE_MIN + SET_SCREW_LENGTH - SET_SCREW_LENGTH_BAND_MM
    - FLAT_DISTANCE - ROUTINE_BAND_MM
    - _STOCK_AXIAL_PROJECTION_LOSS_MM
)
ROTATING_ENVELOPE_RADIUS_MM = max(
    _OD_MAX_R,
    math.hypot(
        _POINT_PLANE_MAX + SET_SCREW_LENGTH + SET_SCREW_LENGTH_BAND_MM,
        SET_SCREW_MAJOR_DIA / 2.0 + TAP_LATERAL_BAND_MM
        + SET_SCREW_LENGTH * math.sin(SET_SCREW_MAX_AXIS_ANGLE_RAD),
    ),
)
if min(WORST_WALLS_MM.values()) < WALL_TARGET_MM:
    raise AssertionError(f"custom collar misses the wall target: {WORST_WALLS_MM}")
if WORST_FULL_ENGAGEMENT_MM < REQUIRED_FULL_ENGAGEMENT_MM:
    raise AssertionError("custom collar set screw has less than 1.5D full thread")
# The sheet prints the bore and land at TERMINAL_DIA_PLACES, so their printed
# limits may sit up to half a printed digit off the class (the inch class
# lands off the mm grid); a real divergence is larger than that.
_PRINT_GRID_TOL_MM = 0.5 * 10**-TERMINAL_DIA_PLACES
if abs(_FLOAT_MAX - TIP_COLLAR_MAX_RADIAL_FLOAT_MM) > _PRINT_GRID_TOL_MM / 2.0:
    raise AssertionError("collar bore and authoritative journal retention fit diverged")
if SCREW_LANDING_MARGIN_MM <= 0.0:
    raise AssertionError(
        f"stock screw point can miss the D-flat: overlap {SCREW_LANDING_MARGIN_MM:.3f} "
        f"at lateral offsets {SCREW_POINT_LATERAL_OFFSETS_MM}"
    )
if WORST_SOCKET_ACCESS_MM <= 0.0:
    raise AssertionError("stock screw socket is buried below the mounting flat")

# Supply size only: the turned Ø17.48 body is the dimensioned OD.
DRAWING_NOTES = "SUPPLY 3/4 ROUND BAR."
# INSTALLATION_NOTES is the bore's fit statement, printed in its REAM callout
# (rule 4: a tight band names its mate at its callout), not as a sheet note:
# the land's finished limits are the shaft drawing's, and the clearance is the
# authoritative float pair (cone_shaft_land_bands.TIP_COLLAR_MIN/MAX_RADIAL_FLOAT_MM)
# on diameter. Setting the collar is MHA-DT-00 step 3 (draw_dt_drive_train_assembly).
JOURNAL_PART_NUMBER = str(_config.parts("dt-cone-gear-shaft")["number"])
JOURNAL_CLEARANCE_MM = (
    BORE_FINISHED_DIA_LIMITS_MM[0] - TERMINAL_FINISHED_DIA_LIMITS_MM[1],
    BORE_FINISHED_DIA_LIMITS_MM[1] - TERMINAL_FINISHED_DIA_LIMITS_MM[0],
)
if abs(JOURNAL_CLEARANCE_MM[0] - 2.0 * TIP_COLLAR_MIN_RADIAL_FLOAT_MM) > _PRINT_GRID_TOL_MM or abs(
    JOURNAL_CLEARANCE_MM[1] - 2.0 * TIP_COLLAR_MAX_RADIAL_FLOAT_MM
) > _PRINT_GRID_TOL_MM:
    raise AssertionError("printed collar journal clearance diverged from the retention float")
INSTALLATION_NOTES = "\n".join((
    f"FITS {JOURNAL_PART_NUMBER} TERMINAL JOURNAL \u00d8"
    f"{TERMINAL_FINISHED_DIA_LIMITS_MM[0]:.4f} TO {TERMINAL_FINISHED_DIA_LIMITS_MM[1]:.4f};",
    f"DIAMETRAL CLEARANCE {JOURNAL_CLEARANCE_MM[0]:.4f} TO {JOURNAL_CLEARANCE_MM[1]:.4f}.",
))
BORE_CALLOUT = f"REAM THRU\n{INSTALLATION_NOTES}"
# The .XXX width, nose length and tap station hold the tapped hole's walls to
# the shoulder and the north face (WORST_WALLS_MM; at .XX they fall below the
# wall floor). Each callout states that function, without numbers (rules 3, 4).
AXIAL_FUNCTION_CALLOUTS = {
    "NoseLength": "SHOULDER CLEAR OF TAP",
    "CollarWidth": "FACE CLEAR OF TAP",
    "TapStation": "TAP CLEAR OF FACES",
}
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 2:1"
RADIAL_TAP_VIEW_SCALE = (2, 1)
BORE_VIEW_SCALE = (40, 1)
BORE_VIEW_NOTE = f"END VIEW BORE SCALE {BORE_VIEW_SCALE[0]}:{BORE_VIEW_SCALE[1]}"
RADIAL_TAP_VIEW_NOTE = (
    f"RADIAL TAP VIEW SCALE {RADIAL_TAP_VIEW_SCALE[0]}:{RADIAL_TAP_VIEW_SCALE[1]}"
)
DRAWING_DIMENSIONS = {
    "RingProfile": {"NoseDia", "BoreDia"},
    "BodyProfile": {"CollarDia", "NoseLength"},
    "Ring": {"CollarWidth"},
    "ShoulderRoot": {"ShoulderRadius"},
    "MountFlatProfile": {"FlatDistance"},
    "SetScrewTap": {"TapStation"},
    "TapRootGauge": {"TapRootLimit"},
}
DRAWING_PRECISION = {
    "RingProfile": {"NoseDia": 2, "BoreDia": TERMINAL_DIA_PLACES},
    "BodyProfile": {"CollarDia": 2, "NoseLength": AXIAL_PLACES},
    "ShoulderRoot": {"ShoulderRadius": 2},
    "Ring": {"CollarWidth": AXIAL_PLACES},
    "MountFlatProfile": {"FlatDistance": 2},
    "SetScrewTap": {"TapStation": AXIAL_PLACES},
    "TapRootGauge": {"TapRootLimit": 2},
}
DRAWING_PRECISION_BY_NAME = {
    name: places for names in DRAWING_PRECISION.values() for name, places in names.items()
}
