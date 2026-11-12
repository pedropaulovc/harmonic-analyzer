r"""MHA-PD-22 transgear-drive-collar: the brass drive collar on the knob shaft.

PURE DATA, no SolidWorks/COM calls and no ``build_*`` module in its import
closure.  ``build_pd_transgear_drive_collar`` marks and tolerances exactly
``DRAWING_DIMENSIONS`` / ``DRAWING_PRECISION`` on the model and
``draw_pd_transgear_drive_collar`` keeps exactly the same names.

The plain round reamed bore slides over the knob shaft's .191 solid D-core
(#2409: no internal D, no broach).  The drive flat is the crest of the
MHA-PD-VN-70 dowel pressed parallel to the axis into a blind ream on local
-Y; that crest bears on the core's D-flat and carries the torque.  There is
no rear slot or front spring pin.
The existing seat-diameter body is supplied long and its REAR FACE is faced
at assembly until the removable T24 meets the unchanged chain-plane setting,
with that rear face seated directly on the integral gear front F.
The model body length is a REF fitted nominal, not an independently
toleranced length.  The thumbnut clamps pilot -> body -> actual gear
shoulder; it carries no drive torque. The two existing axial MHA-PD-VN-54
dowels still drive the removable wheel, and the pilot is faced to retain its
float under the nut.

Decimal inch (#290): nominals are the exact millimetres of their printed
inch values, except the shared seat interface's (``_sprocket_seat_geometry``)
Ø17.5 seat and 14.0 pin circle, which print rounded (.689, .2756).

The front bore mouth takes the title block's edge break.  The pin hole is
reamed blind from the rear face into the supplied body; its floor station is
from the front face, because the rear face is faced at assembly (and faces
the unhardened pin flush with it).  The rear bore mouth then takes a 45°
break about the bore axis, the pin's crest included, which lifts the crest
off the shaft's root corner at F.  Collar and pin are one permanent pair.

Part frame: the axis is local +Z through the origin (``Axis1``, the bore
axis); +Z is machine +Z (rearward), so the assembly places the part without
rotation.  The origin is the front (seat) face, machine z -154.3 at the
nominal setting: the body runs z = 0..LENGTH, the pilot -PILOT_LENGTH..0,
and the drive-pin holes run along Z at (0, ±PIN_CIRCLE_RADIUS), the flat
pin's at (0, -FLAT_PIN_CENTRE) from z = FLAT_PIN_FLOOR to the rear face.

Named datums: ``Axis1``; ``Front Plane`` (the seat face); planes
``PilotFront`` and ``RearFace``; axes ``DrivePinAxis1`` (+Y),
``DrivePinAxis2`` (-Y) and ``FlatPinAxis`` (the flat pin's, -Y).
"""

from __future__ import annotations

import math
import textwrap

import _config
from _fit_ream_h7 import REAM_H7
from _inch_wall_limits import WALL_FLOOR_MM, WALL_TARGET_MM
from _package_units import drawing_unit
from _printed_tolerance import (
    angular_band_deg,
    drilled_oversize_mm,
    edge_break_chamfer_mm,
    edge_break_radius_mm,
    printed_band_mm,
    printed_deviations,
)
from _sprocket_seat_geometry import (
    DRIVE_PIN_LENGTH_GRADE,
)
from pd_rack_pinion_spec import inch_ceil_mm, inch_floor_mm, inch_text
from pd_vn_transgear_knob_drive_pin_spec import LENGTH as PIN_LENGTH
from pd_vn_transgear_knob_drive_pin_spec import PROUD_RANGE, THINNEST_PLATE
from pd_vn_transgear_collar_flat_pin_spec import DIA_LIMITS_MM as FLAT_PIN_DIA_LIMITS
from pd_vn_transgear_collar_flat_pin_spec import LENGTH as FLAT_PIN_STOCK_LENGTH
from pd_vn_transgear_collar_flat_pin_spec import LENGTH_LIMITS_MM as FLAT_PIN_LENGTH_LIMITS
from pd_vn_transgear_collar_flat_pin_spec import PRESS_HOLE_BAND as FLAT_PIN_HOLE_BAND
from pd_vn_transgear_collar_flat_pin_spec import PRESS_HOLE_DIA as FLAT_PIN_HOLE_DIA
from pd_transgear_knob_shaft_spec import (
    CORE_DIA,
    CORE_DIA_BAND,
    CORE_FLAT_BAND,
    CORE_FLAT_FROM_AXIS,
    CORE_TOTAL_RUNOUT,
    CORE_FRONT_FROM_F,
    CORE_FRONT_FROM_F_PLACES,
    CORE_ACTIVE_LENGTH_MIN,
    FRONT_RELIEF_DIA_MAX,
    FRONT_RELIEF_WIDTH_MAX,
    FRONT_RELIEF_WIDTH_MIN,
    FRONT_RELIEF_TOTAL_RUNOUT,
    FRONT_CORNER_RADIUS_MAX,
    END_FLOAT,
    END_FLOAT_SET_TOL,
    ENGAGEMENT_FLOOR_D,
    TOOTH_SPACE_RUNOUT_TIR_MM,
    THREAD_BLANK_LIMITS,
    gear_bearing_area_lower,
    manufactured_profiles,
    PLAIN_CORE,
    PLAIN_CORE_PLACES,
    RELIEF_DIA_MAX,
    THREAD_MAJOR,
    THREAD_PITCH,
    TEETH as SHAFT_TEETH,
    TIP_STATION,
    TIP_STATION_PLACES,
)
from _sprocket_seat_geometry import BORE_DIA as WHEEL_BORE_DIA
from pd_transgear_removable_spec import CRANK_CONFIG, KNOB_CONFIG
from pd_transgear_removable_spec import UNIT as WHEEL_UNIT
from _sprocket_seat_geometry import (
    DRIVE_PIN_HOLE_BAND,
    DRIVE_PIN_HOLE_DIA,
    DRIVE_PIN_OFFSET_PLACES,
    DRIVE_PIN_OFFSET_TOL,
    DRIVE_PIN_PROUD,
    PLATE,
    PLATE_BAND,
    SEAT_SPIGOT_DIA,
    SEAT_SPIGOT_RIM,
    SPIGOT_DIA_BAND,
)
from _sprocket_seat_geometry import PIN_CIRCLE_RADIUS as _WHEEL_PIN_CIRCLE_RADIUS
from pd_transgear_thumbnut_spec import CSK_DIA as NUT_CSK_DIA
from pd_transgear_thumbnut_spec import FLANGE_DIA as NUT_FLANGE_DIA
from pd_transgear_thumbnut_spec import FLANGE_DIA_PLACES as NUT_FLANGE_DIA_PLACES
from pd_transgear_thumbnut_spec import UNIT as NUT_UNIT
from pd_transgear_knob_shaft_spec import UNIT as SHAFT_UNIT
from pd_transgear_thumbnut_spec import FRONT_THREAD_LOSS as NUT_FRONT_THREAD_LOSS
from pd_transgear_thumbnut_spec import OVERALL_LENGTH as NUT_LENGTH
from pd_transgear_thumbnut_spec import OVERALL_LENGTH_LO as NUT_LENGTH_LO
from pd_transgear_thumbnut_spec import REAR_THREAD_LOSS as NUT_REAR_THREAD_LOSS
from pd_transgear_thumbnut_spec import TAP_MINOR_2B_MIN as NUT_MINOR_MIN

# #290: the registry row's drawing_unit (in) is this sheet's unit.
UNIT = drawing_unit(
    "parts/pd-transgear-drive-collar", _config.parts("pd-transgear-drive-collar")
)

# The policy's wall floor for a named shortfall (the target's floor).
WALL_FLOOR = WALL_FLOOR_MM

# --- Existing body: fitted rear-face reaction, unchanged wheel-seat station --
# .243 is the authored set length (owner/Main ruling; FR and MG planes key on
# it), not the .244 snap of F - SEAT_FACE_Z (6.1891). The collar is faced to
# fit; the assembly seats the model's rear on F and leaves the 0.0169
# remainder as air at its front (build_pd_paper_drive_assembly
# .KNOB_COLLAR_FRONT_GAP).
SET_NOMINAL = 6.1722  # .243
SEAT_MIN_FROM_F = 3.8862  # .153
SEAT_MAX_FROM_F = 6.8834  # .271
LENGTH = SET_NOMINAL  # REF fitted nominal; never a title-block band
LENGTH_FITTED_MIN = SEAT_MIN_FROM_F
LENGTH_FITTED_MAX = SEAT_MAX_FROM_F
LENGTH_PLACES = 3
BODY_BLANK_LENGTH_MIN = 7.4168  # .292
OD = SEAT_SPIGOT_DIA  # the crank spigot's seat, printed .689
OD_PLACES = 3
# The removables swap between shafts: the crank spigot's maximum keeps the
# #25 plates wrapping a T12 clear of this seat: the shared +.000/-.004.
OD_BAND = SPIGOT_DIA_BAND

# --- Pilot on the front face, through the wheel's bore (ruling 5) ------------
# .39 at the title block's .XX row (Codjiflo, #2148; rule 4): the pilot only
# clears the wheel's drilled bore, and that row serves both limits.  Its
# maximum (.40) keeps radial air in the bore; its minimum (.38) still
# leaves the pilot wall over the .080 target and the thumbnut's seat a wide
# annulus outside its countersink (the checks below).
PILOT_DIA = 9.906  # .39
PILOT_DIA_PLACES = 2
_PILOT_LO, _PILOT_HI = printed_deviations(PILOT_DIA, PILOT_DIA_PLACES, unit=UNIT)
PILOT_DIA_BAND = (_PILOT_HI, _PILOT_LO)  # title-block row, never authored
# R9-70 (N-A): the thumbnut's seat.  The fitter faces the pilot so its front
# face stands PILOT_PROUD_RANGE proud of the wheel's front face (the plate
# measured, the pilot faced to it plus .004 ±.002), so the wheel is free under
# the nut by the same amount.  It is supplied PILOT_BLANK_LENGTH_MIN long and
# the model carries the nominal plate plus the mid proud.
PILOT_PROUD_RANGE = (0.0508, 0.1524)  # .002 .. .006
PILOT_PROUD = sum(PILOT_PROUD_RANGE) / 2.0
PILOT_LENGTH = PLATE + PILOT_PROUD  # nominal fitted
PILOT_LENGTH_PLACES = 3
PILOT_LENGTH_FITTED_MIN = THINNEST_PLATE + min(PILOT_PROUD_RANGE)
PILOT_LENGTH_FITTED_MAX = PLATE + max(PLATE_BAND) + max(PILOT_PROUD_RANGE)
FACING_ALLOWANCE = 0.1016  # .004
PILOT_BLANK_LENGTH_MIN = 3.4036  # .134
if PILOT_BLANK_LENGTH_MIN < PILOT_LENGTH_FITTED_MAX + FACING_ALLOWANCE - 1e-9:
    raise AssertionError("MHA-PD-22 pilot blank leaves no facing allowance")
if not PILOT_LENGTH_FITTED_MIN <= PILOT_LENGTH <= PILOT_LENGTH_FITTED_MAX:
    raise AssertionError("MHA-PD-22's modelled pilot lies outside its fitted band")

# --- Round bore over the D-core (#2409) --------------------------------------
# #290 fit D10: the .192 REAM_H7 bore (.1920-.1925, the .192 reamer) slides
# over the core's .191 SHAFT_H.  No flat is cut in the bore: the MHA-PD-VN-70
# pin's crest (below) is the drive flat.
BORE_DIA = 4.8768  # .192
BORE_DIA_BAND = REAM_H7
BORE_DIA_PLACES = 4
_CORE_R_MIN = (CORE_DIA + min(CORE_DIA_BAND)) / 2.0
_BORE_R_MIN = (BORE_DIA + min(BORE_DIA_BAND)) / 2.0
_BORE_R_MAX = (BORE_DIA + max(BORE_DIA_BAND)) / 2.0
_CORE_FLAT_MIN = CORE_FLAT_FROM_AXIS + min(CORE_FLAT_BAND)
_CORE_FLAT_MAX = CORE_FLAT_FROM_AXIS + max(CORE_FLAT_BAND)
_CORE_FRONT_MIN = CORE_FRONT_FROM_F - printed_band_mm(CORE_FRONT_FROM_F_PLACES, unit=SHAFT_UNIT)
_CORE_FRONT_MAX = CORE_FRONT_FROM_F + printed_band_mm(CORE_FRONT_FROM_F_PLACES, unit=SHAFT_UNIT)
# The front mouth takes the title block's edge break.
BORE_EDGE_BREAK_MAX = max(edge_break_radius_mm(unit=UNIT), edge_break_chamfer_mm(unit=UNIT))
# The rear mouth: a 45° break of radial leg REAR_BREAK about the bore axis,
# cut after the rear is faced at assembly, through the pressed flat pin with
# it (collar and pin are one permanent pair): it lifts the pin's crest corner
# clear of the shaft's root corner at F (rule 21; FLAT_PIN_CREST_CORNER_AIR_MIN).
REAR_BREAK = 0.2032  # .008
REAR_BREAK_TOL = 0.0508  # ±.002
REAR_BREAK_PLACES = 3
REAR_BREAK_LIMITS = (REAR_BREAK - REAR_BREAK_TOL, REAR_BREAK + REAR_BREAK_TOL)
REAR_BREAK_ANGLE_DEG = 45.0  # from the axis, at the title block's angular row
REAR_BREAK_ANGLE_LIMITS = (
    REAR_BREAK_ANGLE_DEG - angular_band_deg(unit=UNIT),
    REAR_BREAK_ANGLE_DEG + angular_band_deg(unit=UNIT),
)
# How far the break runs along the bore from the rear face: widest, steepest.
REAR_BREAK_DEPTH_MAX = max(REAR_BREAK_LIMITS) / math.tan(
    math.radians(min(REAR_BREAK_ANGLE_LIMITS))
)


def rear_break_radius(depth: float, bore_r: float, leg: float, angle_deg: float) -> float:
    """Radius of the rear break's cone ``depth`` in from the rear face: the
    bore edge plus the leg at the face, closing at ``angle_deg`` to the axis."""
    return bore_r + leg - depth * math.tan(math.radians(angle_deg))


def circle_overlap_area(r1: float, r2: float, distance: float) -> float:
    """Area common to two circles whose centres lie ``distance`` apart."""
    if distance >= r1 + r2:
        return 0.0
    if distance <= abs(r1 - r2):
        return math.pi * min(r1, r2) ** 2
    d2, a2, b2 = distance**2, r1**2, r2**2
    return (
        a2 * math.acos((d2 + a2 - b2) / (2.0 * distance * r1))
        + b2 * math.acos((d2 + b2 - a2) / (2.0 * distance * r2))
        - 0.5 * math.sqrt(
            (-distance + r1 + r2)
            * (distance + r1 - r2)
            * (distance - r1 + r2)
            * (distance + r1 + r2)
        )
    )


def cone_cylinder_volume(
    face_r: float, depth: float, cylinder_r: float, distance: float, steps: int = 64
) -> float:
    """Volume common, over ``depth`` in from a face, to a 45° cone narrowing
    from ``face_r`` at that face and a cylinder of ``cylinder_r`` parallel to
    the cone's axis ``distance`` from it (Simpson's rule)."""
    step = depth / steps
    return step / 3.0 * sum(
        (1 if i in (0, steps) else 4 if i % 2 else 2)
        * circle_overlap_area(max(face_r - i * step, 0.0), cylinder_r, distance)
        for i in range(steps + 1)
    )


# The largest radial float of the round bore on the plain core.
ROUND_FIT_FLOAT_MAX = _BORE_R_MAX - _CORE_R_MIN
# The rear mouth seats on F over the shaft's neck and its root corner (the
# neck's largest radius plus its largest corner, .0815): spend both turned
# surfaces' runout and the whole float, no common-axis credit.
_ROOT_CORNER_REACH_MAX = (
    FRONT_RELIEF_DIA_MAX / 2.0 + FRONT_CORNER_RADIUS_MAX
    + (CORE_TOTAL_RUNOUT + FRONT_RELIEF_TOTAL_RUNOUT) / 2.0 + ROUND_FIT_FLOAT_MAX
)
ROOT_CORNER_BORE_AIR_MIN = _BORE_R_MIN - _ROOT_CORNER_REACH_MAX
# The F face lies behind the core's support.  The rear mouth's break ends
# inside the neck and the bore runs on through the shortest pilot past the
# core's front (both asserted below), so the bore bears on the core's whole
# active length.  Bound the bore's axis at both ends of that support, then
# extrapolate to F; spend the core runout at BOTH sections.
BORE_SUPPORT_LENGTH_MIN = CORE_ACTIVE_LENGTH_MIN
BORE_SUPPORT_TO_F_MAX = FRONT_RELIEF_WIDTH_MAX
BORE_AXIS_AT_F_FROM_JOURNAL_MAX = (
    ROUND_FIT_FLOAT_MAX + CORE_TOTAL_RUNOUT / 2.0
) * (1.0 + 2.0 * BORE_SUPPORT_TO_F_MAX / BORE_SUPPORT_LENGTH_MIN)
FRONT_BEARING_INNER_RADIUS_MAX = (
    _BORE_R_MAX + max(REAR_BREAK_LIMITS) + BORE_AXIS_AT_F_FROM_JOURNAL_MAX
    + TOOTH_SPACE_RUNOUT_TIR_MM / 2.0
)
FRONT_BEARING_AREA_MIN = min(
    gear_bearing_area_lower(profile, FRONT_BEARING_INNER_RADIUS_MAX)
    for profile in manufactured_profiles()
)

# --- Drive-pin holes: reamed THROUGH for the MHA-PD-VN-54 press (the crank's twin) -
PIN_CIRCLE_RADIUS = _WHEEL_PIN_CIRCLE_RADIUS  # ±Y
PIN_HOLE_DIA = DRIVE_PIN_HOLE_DIA  # the shared 3/32 press hole
# The shared .0930 REAM_H7 hole and each centre's .2756 +/-.0009, at the
# four places the crank's sheet prints them too.
PIN_HOLE_BAND = DRIVE_PIN_HOLE_BAND  # +.0005/-.0000
PIN_HOLE_PLACES = 4
PIN_OFFSET_TOL = DRIVE_PIN_OFFSET_TOL  # ±.0009 each centre
PIN_OFFSET_PLACES = DRIVE_PIN_OFFSET_PLACES
PIN_HOLE_DEPTH = LENGTH  # through the body

# --- The drive flat: the MHA-PD-VN-70 dowel's crest (#2409) ------------------
# A 1/16 x 3/16 unhardened stainless dowel pressed parallel to the axis into a
# blind .0615 REAM_H7 hole on local -Y (the former D-flat side, so the
# assembly's clocking is unchanged).  The hole is reamed blind from the rear
# face into the supplied body to a full-diameter floor FLAT_PIN_FLOOR behind
# the front (seat) face; the floor prints at two places (.XX, ±.01): over its
# band the drill point stays in the body, the pilot-shoulder wall holds the
# .080 target and the pin keeps its engagement on the core (asserted below),
# so the floor needs no tighter row and no function words.  The pin is
# pressed to that floor and its
# crest, the surface nearest the axis, stands inside the bore over the core's
# D-flat.  Facing the rear to fit faces the pin flush with it, and the rear
# break then cuts its crest corner: collar and pin are one permanent pair
# (rule 16), named so at the pin hole's callout.
FLAT_PIN_NUMBER = "MHA-PD-VN-70"
FLAT_PIN_HOLE_PLACES = 4
# The shop row for a reamed hole's location, no fit route: the crest's
# clearance to the core's flat holds over the whole band (asserted below).
FLAT_PIN_CENTRE = 2.9972  # .118 from the bore axis, along local -Y
FLAT_PIN_CENTRE_TOL = 0.0508  # ±.002
FLAT_PIN_CENTRE_PLACES = 3
FLAT_PIN_FLOOR = 2.032  # .08 behind the front face
FLAT_PIN_FLOOR_PLACES = 2
_FLOOR_LO, _FLOOR_HI = printed_deviations(FLAT_PIN_FLOOR, FLAT_PIN_FLOOR_PLACES, unit=UNIT)
FLAT_PIN_FLOOR_LIMITS = (FLAT_PIN_FLOOR + _FLOOR_LO, FLAT_PIN_FLOOR + _FLOOR_HI)
# The pin as modelled: the catalogue length, faced flush with the model's
# nominal fitted rear face when it would stand past it.
FLAT_PIN_LENGTH = min(FLAT_PIN_STOCK_LENGTH, LENGTH - FLAT_PIN_FLOOR)
_FLAT_PIN_CENTRE_LIMITS = (
    FLAT_PIN_CENTRE - FLAT_PIN_CENTRE_TOL, FLAT_PIN_CENTRE + FLAT_PIN_CENTRE_TOL
)
_FLAT_PIN_R_LIMITS = (min(FLAT_PIN_DIA_LIMITS) / 2.0, max(FLAT_PIN_DIA_LIMITS) / 2.0)
_FLAT_PIN_HOLE_R_MAX = (FLAT_PIN_HOLE_DIA + max(FLAT_PIN_HOLE_BAND)) / 2.0
_FLAT_PIN_HOLE_OUTER_R_MAX = max(_FLAT_PIN_CENTRE_LIMITS) + _FLAT_PIN_HOLE_R_MAX
# The pressed pin sits on the hole's axis: its crest is centre less radius.
FLAT_PIN_CREST_LIMITS = (
    min(_FLAT_PIN_CENTRE_LIMITS) - max(_FLAT_PIN_R_LIMITS),
    max(_FLAT_PIN_CENTRE_LIMITS) - min(_FLAT_PIN_R_LIMITS),
)  # .0847 .. .0888
# Radial air from the crest to the core's flat, the core centred in the bore.
FLAT_PIN_CREST_CLEARANCE = (
    min(FLAT_PIN_CREST_LIMITS) - _CORE_FLAT_MAX,
    max(FLAT_PIN_CREST_LIMITS) - _CORE_FLAT_MIN,
)
# The #8-32 stud's largest blank passes the lowest crest.
STUD_FLAT_PIN_AIR = min(FLAT_PIN_CREST_LIMITS) - max(THREAD_BLANK_LIMITS) / 2.0
# More than half the pin lies in the hole: the bore cannot release it.
FLAT_PIN_RETAINED_MARGIN = min(_FLAT_PIN_CENTRE_LIMITS) - _BORE_R_MAX
# The pin's rear end, deepest floor and longest pin, inside the supplied body
# blank: the rear-face fit faces the pin with the body.
FLAT_PIN_REAR_MAX = max(FLAT_PIN_FLOOR_LIMITS) + max(FLAT_PIN_LENGTH_LIMITS)
FLAT_PIN_BLANK_INSET_MIN = BODY_BLANK_LENGTH_MIN - FLAT_PIN_REAR_MAX
# The reamed hole's 118-degree drill point lies ahead of the full-diameter
# floor; it stays in the body, behind the front face.
FLAT_PIN_DRILL_POINT = _FLAT_PIN_HOLE_R_MAX / math.tan(math.radians(59.0))
FLAT_PIN_DRILL_TIP_MIN = min(FLAT_PIN_FLOOR_LIMITS) - FLAT_PIN_DRILL_POINT
# Within FRONT_CORNER_RADIUS_MAX of F the shaft's root corner reaches
# _ROOT_CORNER_REACH_MAX.  There the rear break has cut the pin's crest back
# to at least its cone's radius at that depth (its smallest leg at its
# steepest angle), so the metal nearest the axis is the larger of the crest
# and that cone.
FLAT_PIN_CREST_CORNER_AIR_MIN = max(
    min(FLAT_PIN_CREST_LIMITS),
    rear_break_radius(
        FRONT_CORNER_RADIUS_MAX,
        _BORE_R_MIN,
        min(REAR_BREAK_LIMITS),
        max(REAR_BREAK_ANGLE_LIMITS),
    ),
) - _ROOT_CORNER_REACH_MAX
# How deep from F the break removes the crest: the cone's widest reach down
# to the lowest crest, at its shallowest angle.  The pin bears on the flat
# only behind it.
FLAT_PIN_CREST_RELIEF_MAX = (
    _BORE_R_MAX + max(REAR_BREAK_LIMITS) - min(FLAT_PIN_CREST_LIMITS)
) / math.tan(math.radians(min(REAR_BREAK_ANGLE_LIMITS)))


def flat_pin_core_engagement(
    body_length: float, floor: float, pin_length: float, core_front: float
) -> float:
    """Axial length of the pressed pin on the shaft's D-core, the collar's
    rear face seated on F ``body_length`` behind its front face: the pin runs
    ``body_length - floor`` forward of F back to its rear end, faced flush
    with the rear face where it would stand past it and its crest relieved by
    the rear break; the core runs from the neck's widest end to
    ``core_front``."""
    pin_front = body_length - floor
    pin_rear = max(pin_front - pin_length, 0.0)
    return min(pin_front, core_front) - max(
        pin_rear, FLAT_PIN_CREST_RELIEF_MAX, FRONT_RELIEF_WIDTH_MAX
    )


# Affine terms under min/max: concave over the box, so its corners bound it.
FLAT_PIN_CORE_ENGAGEMENT_MIN = min(
    flat_pin_core_engagement(length, floor, pin, front)
    for length in (LENGTH_FITTED_MIN, LENGTH_FITTED_MAX)
    for floor in FLAT_PIN_FLOOR_LIMITS
    for pin in FLAT_PIN_LENGTH_LIMITS
    for front in (_CORE_FRONT_MIN, _CORE_FRONT_MAX)
)


def flat_pin_play_deg(centre: float, pin_r: float, core_flat: float) -> float:
    """Turn of the shaft, either way from square, until its flat meets the
    round pin: cos(theta) = (flat + pin radius) / pin centre."""
    return math.degrees(math.acos((core_flat + pin_r) / centre))


# A binding crest leaves no play (the acos below has no root): refuse it here.
if min(FLAT_PIN_CREST_CLEARANCE) <= 0.0:
    raise AssertionError("MHA-PD-22: the flat pin's crest binds on the core's flat")
# Lost motion, stated not gated: the knob is chain-driven and the paper feeds
# one way while the crank turns.  Delegated accept RV-04 in the registry row.
FLAT_PIN_PLAY_DEG = (
    flat_pin_play_deg(min(_FLAT_PIN_CENTRE_LIMITS), max(_FLAT_PIN_R_LIMITS), _CORE_FLAT_MAX),
    flat_pin_play_deg(max(_FLAT_PIN_CENTRE_LIMITS), min(_FLAT_PIN_R_LIMITS), _CORE_FLAT_MIN),
)
# At the widest play the contact still lands on the flat, short of its edge.
FLAT_PIN_CONTACT_EDGE_MARGIN = math.sqrt(_CORE_R_MIN**2 - _CORE_FLAT_MAX**2) - (
    max(_FLAT_PIN_CENTRE_LIMITS) * math.sin(math.radians(max(FLAT_PIN_PLAY_DEG)))
)
# Reversal lost motion at the knob, both ways at the widest play.  The paper
# travel it costs (through 15:150 and the feed pinion on the rack) is RV-04's,
# whose figures the collar tests derive from paper_drive_geom: importing that
# chain here would key this part's build on the paper-drive stock modules.
KNOB_REVERSAL_PLAY_DEG = 2.0 * max(FLAT_PIN_PLAY_DEG)

# --- The native features' marked dimensions --------------------------------
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "BodyProfile": {"CollarDia", "CollarLength", "PilotDia", "PilotLength"},
    "BoreProfile": {"BoreDia"},
    "PinHoleProfile": {"PinPosDia", "PinPosY", "PinNegY"},
    "FlatPinProfile": {"FlatPinDia", "FlatPinCentre", "FlatPinFloor"},
    "RearBreakProfile": {"RearBreak"},
}
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "BodyProfile": {
        "CollarDia": OD_PLACES,
        "CollarLength": LENGTH_PLACES,
        "PilotDia": PILOT_DIA_PLACES,
        "PilotLength": PILOT_LENGTH_PLACES,
    },
    "BoreProfile": {"BoreDia": BORE_DIA_PLACES},
    "PinHoleProfile": {
        "PinPosDia": PIN_HOLE_PLACES,
        "PinPosY": PIN_OFFSET_PLACES,
        "PinNegY": PIN_OFFSET_PLACES,
    },
    "FlatPinProfile": {
        "FlatPinDia": FLAT_PIN_HOLE_PLACES,
        "FlatPinCentre": FLAT_PIN_CENTRE_PLACES,
        "FlatPinFloor": FLAT_PIN_FLOOR_PLACES,
    },
    "RearBreakProfile": {"RearBreak": REAR_BREAK_PLACES},
}
if {feature: set(names) for feature, names in DRAWING_PRECISION.items()} != (
    DRAWING_DIMENSIONS
):
    raise AssertionError("every marked MHA-PD-22 dimension needs authored places")
DRAWING_PRECISION_BY_NAME: dict[str, int] = {
    name: places
    for dimensions in DRAWING_PRECISION.values()
    for name, places in dimensions.items()
}

if BODY_BLANK_LENGTH_MIN < LENGTH_FITTED_MAX + FACING_ALLOWANCE - 1e-9:
    raise AssertionError("MHA-PD-22 body blank leaves no rear-facing allowance")
if not LENGTH_FITTED_MIN <= LENGTH <= LENGTH_FITTED_MAX:
    raise AssertionError("MHA-PD-22 model body lies outside its fitted band")


def floor_inch(value: float) -> float:
    """A MIN on the sheet never rounds up past the arithmetic (.XXX)."""
    return inch_floor_mm(value, 3)


# --- Walls (contract §8) ---------------------------------------------------------
_OD_R_MIN = (OD + min(OD_BAND)) / 2.0
_PIN_HOLE_R_MAX = (PIN_HOLE_DIA + max(PIN_HOLE_BAND)) / 2.0
# Drive-pin hole to the seat-diameter rim, nominal and at the printed worst
# case (the smallest body, the farthest-out centre, the largest hole).
DRIVE_PIN_COLLAR_RIM = OD / 2.0 - PIN_CIRCLE_RADIUS - PIN_HOLE_DIA / 2.0
DRIVE_PIN_COLLAR_RIM_WORST = floor_inch(
    _OD_R_MIN - PIN_CIRCLE_RADIUS - PIN_OFFSET_TOL - _PIN_HOLE_R_MAX
)
# The round bore meets the full pilot-wall target.
PILOT_WALL = (PILOT_DIA - BORE_DIA) / 2.0
PILOT_WALL_WORST = floor_inch(
    (PILOT_DIA + min(PILOT_DIA_BAND) - (BORE_DIA + max(BORE_DIA_BAND))) / 2.0
)
# Bore to each retained wheel drive-pin hole.
BORE_PIN_WALL = PIN_CIRCLE_RADIUS - PIN_HOLE_DIA / 2.0 - BORE_DIA / 2.0
BORE_PIN_WALL_WORST = (
    PIN_CIRCLE_RADIUS
    - PIN_OFFSET_TOL
    - _PIN_HOLE_R_MAX
    - (BORE_DIA + max(BORE_DIA_BAND)) / 2.0
)
# The flat-pin hole on local -Y and the -Y drive-pin hole share a radius
# line: the web between them at the worst centres and largest holes.  Under
# the target, over the floor: RV-03 in the registry row, printed as note 2.
FLAT_PIN_WEB_WORST = floor_inch(
    PIN_CIRCLE_RADIUS - PIN_OFFSET_TOL - _PIN_HOLE_R_MAX - _FLAT_PIN_HOLE_OUTER_R_MAX
)
# Flat-pin hole to the body O.D.
FLAT_PIN_OD_WALL_WORST = _OD_R_MIN - _FLAT_PIN_HOLE_OUTER_R_MAX
# The hole lies inside the pilot's footprint; its floor's outer edge meets
# the pilot shoulder (pilot O.D. on the front face) across the shallowest
# floor.  The hole breaking into the bore is the intended crest, not a wall.
_PILOT_R_MIN = (PILOT_DIA + min(PILOT_DIA_BAND)) / 2.0
FLAT_PIN_SHOULDER_WALL_WORST = math.hypot(
    _PILOT_R_MIN - _FLAT_PIN_HOLE_OUTER_R_MAX, min(FLAT_PIN_FLOOR_LIMITS)
)
# The holes run through the body beside the pilot, never into it.
PIN_HOLE_INNER_R_MIN = PIN_CIRCLE_RADIUS - PIN_OFFSET_TOL - _PIN_HOLE_R_MAX
PILOT_R_MAX = (PILOT_DIA + max(PILOT_DIA_BAND)) / 2.0

# --- Fits ------------------------------------------------------------------------
# Diametral sliding clearance of the round bore on the core.
BORE_CORE_CLEARANCE = (
    BORE_DIA + min(BORE_DIA_BAND) - (CORE_DIA + max(CORE_DIA_BAND)),
    BORE_DIA + max(BORE_DIA_BAND) - (CORE_DIA + min(CORE_DIA_BAND)),
)
# Radial air round the pilot in the wheel's drilled bore.
PILOT_BORE_CLEARANCE = (
    (WHEEL_BORE_DIA - (PILOT_DIA + max(PILOT_DIA_BAND))) / 2.0,
    (
        WHEEL_BORE_DIA + drilled_oversize_mm(unit=WHEEL_UNIT)
        - (PILOT_DIA + min(PILOT_DIA_BAND))
    ) / 2.0,
)
# R9-70 (N-A): the thumbnut seats on the pilot's front face, which stands
# PILOT_PROUD_RANGE proud of the wheel's front face: the nut's seat bears on the
# pilot's annulus outside its rear countersink, its flange covers the pilot
# all round, and the wheel is free under it by the proud.
_NUT_FLANGE_LO, _ = printed_deviations(NUT_FLANGE_DIA, NUT_FLANGE_DIA_PLACES, unit=NUT_UNIT)
NUT_PILOT_BEARING_WORST = (PILOT_DIA + min(PILOT_DIA_BAND) - NUT_CSK_DIA) / 2.0
NUT_FLANGE_OVER_PILOT_WORST = (
    NUT_FLANGE_DIA + _NUT_FLANGE_LO - (PILOT_DIA + max(PILOT_DIA_BAND))
) / 2.0
KNOB_FLOAT_RANGE = PILOT_PROUD_RANGE


# --- Drive pins pressed through to a stop (MHA-PD-VN-54) ------------------------------
def pin_hole_meets_wall_floor(collar_length: float, depth: float) -> bool:
    """A pin hole either runs through the collar or leaves ``WALL_FLOOR`` of
    solid behind its floor; a thinner floor is a wall under the policy."""
    return depth >= collar_length or collar_length - depth >= WALL_FLOOR - 1e-9


def pin_rear_inset(collar_length: float, pin_length: float, proud: float) -> float:
    """How far the pressed end of a pin set ``proud`` of the seat face stays
    inside the collar's rear face (negative: it stands out toward the disc)."""
    return collar_length - (pin_length - proud)


# Shortest fitted body, longest dowel, lowest allowed proud.
PIN_REAR_INSET = pin_rear_inset(LENGTH, PIN_LENGTH, DRIVE_PIN_PROUD)
PIN_REAR_INSET_WORST = pin_rear_inset(
    LENGTH_FITTED_MIN, PIN_LENGTH + DRIVE_PIN_LENGTH_GRADE, min(PROUD_RANGE)
)

# The mating parts, named at the callouts they serve (drawing-guidelines.md
# rule 4): the shaft, the pressed dowels and the removable sprocket.
SHAFT_NUMBER = "MHA-PD-08"
SHAFT_NAME = "KNOB SHAFT"
SHAFT_SEAT_FACE = f"{SHAFT_NUMBER} {SHAFT_TEETH}T FRONT FACE"
DOWEL_NUMBER = "MHA-PD-VN-54"
SPROCKET_NUMBER = "MHA-PD-09"

# --- Fitted axial reaction -------------------------------------------------
# With the rear face seated on the actual gear shoulder, body length IS the
# front wheel seat's distance from F. No front pin or unreacted axial gap.
BODY_REAR_FACE_FROM_F = 0.0
BODY_LENGTH_CALLOUT = (
    f"FITTED {inch_text(LENGTH_FITTED_MIN, 3)}-{inch_text(LENGTH_FITTED_MAX, 3)}\n"
    f"REAR FACE TO FIT, SEATED ON {SHAFT_SEAT_FACE}"
)
BODY_FACE_PHRASE = (
    f"FACE THE COLLAR REAR WITH THE REAR FACE SEATED ON THE {SHAFT_SEAT_FACE} "
    "UNTIL THE KNOB-WHEEL FRONT MEETS THE CHAIN SETTING"
)

for _ok, _what in (
    (
        math.isclose(DRIVE_PIN_COLLAR_RIM, SEAT_SPIGOT_RIM, abs_tol=1e-9),
        "the collar rim is not the seat interface's rim",
    ),
    (DRIVE_PIN_COLLAR_RIM_WORST > 0.0, "the drive-pin holes break out of the rim"),
    (PILOT_WALL_WORST >= WALL_FLOOR, "pilot wall under the floor"),
    (STUD_FLAT_PIN_AIR > 0.0, "the round stud cannot pass the flat pin's crest"),
    (FLAT_PIN_RETAINED_MARGIN > 0.0, "the bore releases the flat pin"),
    (FLAT_PIN_BLANK_INSET_MIN >= 0.0, "the flat pin stands out of the supplied body"),
    (FLAT_PIN_DRILL_TIP_MIN > 0.0, "the flat-pin hole's drill point leaves the body"),
    (FLAT_PIN_CORE_ENGAGEMENT_MIN > 0.0, "the flat pin misses the shaft's D-core"),
    (FLAT_PIN_CONTACT_EDGE_MARGIN > 0.0, "the flat pin drives on the flat's edge"),
    (FLAT_PIN_WEB_WORST >= WALL_FLOOR, "flat-pin hole to drive-pin hole under the floor"),
    (FLAT_PIN_OD_WALL_WORST >= WALL_TARGET_MM, "flat-pin hole to the O.D. under the target"),
    (
        FLAT_PIN_SHOULDER_WALL_WORST >= WALL_TARGET_MM,
        "flat-pin hole floor to the pilot shoulder under the target",
    ),
    (FRONT_BEARING_AREA_MIN > 0.0, "the collar rear face has no actual gear support"),
    (ROOT_CORNER_BORE_AIR_MIN > 0.0, "the rear bore mouth does not clear the root corner"),
    (
        REAR_BREAK_DEPTH_MAX <= FRONT_RELIEF_WIDTH_MIN,
        "the rear mouth's break shortens the bore's support on the core",
    ),
    (
        FLAT_PIN_CREST_CORNER_AIR_MIN > 0.0,
        "the flat pin's crest rides the shaft's root corner at F",
    ),
    (
        LENGTH_FITTED_MIN + PILOT_LENGTH_FITTED_MIN - BORE_EDGE_BREAK_MAX >= _CORE_FRONT_MAX,
        "the bore ends short of the core's front",
    ),
    (BORE_PIN_WALL_WORST >= WALL_FLOOR, "bore to drive-pin hole under the floor"),
    (PIN_HOLE_INNER_R_MIN > PILOT_R_MAX, "the drive-pin holes break into the pilot"),
    (min(BORE_CORE_CLEARANCE) > 0.0, "the bore binds on the plain core"),
    (min(PILOT_BORE_CLEARANCE) > 0.0, "the pilot binds in the wheel bore"),
    (NUT_PILOT_BEARING_WORST > 0.0, "the thumbnut's countersink swallows the pilot"),
    (
        NUT_FLANGE_OVER_PILOT_WORST > 0.0,
        "the thumbnut's flange no longer covers the pilot",
    ),
    (min(KNOB_FLOAT_RANGE) > 0.0, "the pilot no longer stands proud of the knob wheel"),
    (
        pin_hole_meets_wall_floor(LENGTH, PIN_HOLE_DEPTH),
        "a blind drive-pin hole leaves a floor under the wall floor",
    ),
    (PIN_REAR_INSET_WORST >= 0.0, "a pressed drive pin stands out of the rear face"),
    (BODY_REAR_FACE_FROM_F == 0.0, "the collar has no axial reaction at the pinion front face"),
):
    if not _ok:
        raise AssertionError(f"MHA-PD-22: {_what}")

# drawing-guidelines.md rule 4 (name the mate): every tight band names its
# mate and fit at its own callout; the native bands print the limits and the
# fit's range follows as REF.  The bore's rows: the process and its mate,
# then its clearance.
BORE_CALLOUT = (
    f"REAM THRU, SLIDING FIT\nON {SHAFT_NUMBER} D-CORE\n"
    f"(CLEARANCE {inch_text(inch_floor_mm(BORE_CORE_CLEARANCE[0], 4), 4)}-"
    f"{inch_text(inch_ceil_mm(BORE_CORE_CLEARANCE[1], 4), 4)})"
)
# The flat pin's press ream.  Its process reads on one line over the size:
# BLIND, to the floor the .XX station dimension places, which controls.  The
# size carries the depth as a REF from the section's (nominal fitted) rear
# face (rule 26: a depth is never left to the view; REF because the rear is
# faced to fit after reaming).  Under the size, two lines of words (rule 7):
# its pin, pressed for good so collar and pin are one permanent pair (rule
# 16), and why its location is tight (rule 4): the crest drives the shaft.
# An above-callout prints only on one line.
FLAT_PIN_HOLE_DEPTH_REF = LENGTH - FLAT_PIN_FLOOR
FLAT_PIN_HOLE_SUFFIX = f" <HOLE-DEPTH> ({inch_text(FLAT_PIN_HOLE_DEPTH_REF, 3)})"
FLAT_PIN_HOLE_CALLOUT_ABOVE = "BLIND REAM, PRESS FIT"
FLAT_PIN_HOLE_CALLOUT = f"PERMANENT PIN {FLAT_PIN_NUMBER}\nCREST DRIVES {SHAFT_NUMBER}"
# The rear break prints its leg and angle on one line, then the mate it
# clears (rule 4) on two short rows under it; the clearance is the spec's
# assertion (FLAT_PIN_CREST_CORNER_AIR_MIN).
REAR_BREAK_SUFFIX = f" X {REAR_BREAK_ANGLE_DEG:g}°"
REAR_BREAK_CALLOUT = f"CLEARS {SHAFT_NUMBER}\nROOT CORNER"
# The overall, pilot front face to rear face, prints as a .XX reference.
OVERALL_LENGTH = LENGTH + PILOT_LENGTH
DRAWING_REFERENCE_PRECISION = 2
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW\nSCALE 2:1"

# Rear-face fit and pilot fit are actual assembly operations; the supplied
# body/pilot are deliberately long. The assembly prints these same phrases.
# The knob-wheel front face is set FIT_UP_OFFSET_TARGET forward of the crank
# wheel's front face, within FIT_UP_OFFSET_SET_TOL at setting (§13.2 procedure (4)).
# The band is read with a straightedge across both wheels and feelers, and a
# miss costs a facing cut or a new collar, so it takes what the chain plane's
# budget leaves (#2420): the re-check's band is the largest .001 band
# Tsubaki's ±1 admits in service (pd_paper_drive_assembly_steps
# .OFFSET_ACCEPT_TOL, .009), and the setting keeps the former .002 inside it
# for the refit between the two readings: .009 - .002 = .007.
FIT_UP_OFFSET_TARGET = 0.0508  # .002
FIT_UP_OFFSET_SET_TOL = 0.1778  # .007
FIT_UP_OFFSET_SET_TEXT = (
    f"{inch_text(FIT_UP_OFFSET_TARGET, 3)} \u00b1{inch_text(FIT_UP_OFFSET_SET_TOL, 3)}"
)
# Procedure (7): a stud end standing proud of the thumbnut's rim is cut this
# far below the rim and re-chamfered 45 degrees to the thread minor (the
# MHA-PD-08 tip form).
STUD_CUT_BELOW_RIM = (0.254, 1.016)  # .010 .. .040
STUD_RECHAMFER_DEG = 45
STUD_CUT_PHRASE = (
    f"CUT {inch_text(STUD_CUT_BELOW_RIM[0], 3)} TO {inch_text(STUD_CUT_BELOW_RIM[1], 3)}"
    f" BELOW THE RIM, RE-CHAMFER {STUD_RECHAMFER_DEG}\u00b0 TO THE MINOR"
)

# --- The thumbnut on the stud over the whole setting (R9-53, contract §7) ------
# The fitter may leave the knob-wheel seat anywhere from the rearward stop (the
# collar's rear face on F, seat = the collar length) to SEAT_MAX_FROM_F.  The
# nut seats on the pilot's faced front face (R9-70), the fitted pilot length
# in front of the seat.
_TIP_STATION_MIN = TIP_STATION - printed_band_mm(TIP_STATION_PLACES, unit=SHAFT_UNIT)
_PLAIN_CORE_MAX = PLAIN_CORE + printed_band_mm(PLAIN_CORE_PLACES, unit=SHAFT_UNIT)
NUT_LENGTH_MIN = NUT_LENGTH + NUT_LENGTH_LO


def thumbnut_engagement(seat_from_f: float) -> float:
    """Full stud thread inside the nut's full thread, the knob-wheel seat
    ``seat_from_f`` in front of F, at the printed worst case: forward, the
    shortest stud tip (or the deepest cut below the shortest nut's rim) less
    one pitch for its chamfer, inside the rim's countersink, the nut on the
    shortest fitted pilot; rearward, the nut's seat countersink on the longest
    fitted pilot or the stud's full-thread end, whichever lies further
    forward.  Each countersink's loss is counted from the tap drill (R9-63)."""
    rim = seat_from_f + PILOT_LENGTH_FITTED_MIN + NUT_LENGTH_MIN
    tip = min(_TIP_STATION_MIN, rim - STUD_CUT_BELOW_RIM[1])
    front = min(tip - THREAD_PITCH, rim - NUT_FRONT_THREAD_LOSS)
    rear = max(
        seat_from_f + PILOT_LENGTH_FITTED_MAX + NUT_REAR_THREAD_LOSS, _PLAIN_CORE_MAX
    )
    return front - rear


# Engagement is concave over the accepted fitted seat interval. Charge both
# ends rather than replace a fitted length with an independent +/- band.
THUMBNUT_ENGAGEMENT_WORST = min(
    thumbnut_engagement(seat) for seat in (LENGTH_FITTED_MIN, LENGTH_FITTED_MAX)
)
if THUMBNUT_ENGAGEMENT_WORST < ENGAGEMENT_FLOOR_D * THREAD_MAJOR - 1e-9:
    raise AssertionError(
        f"MHA-PD-13 thumbnut / MHA-PD-08 stud: {THUMBNUT_ENGAGEMENT_WORST:.3f} of full "
        f"thread ({THUMBNUT_ENGAGEMENT_WORST / THREAD_MAJOR:.2f} D) at the worst "
        f"setting, under {ENGAGEMENT_FLOOR_D} D"
    )
# At the rearward stop the nut's seat stands in front of the core's step, so
# its thread runs only on full thread or over the relief, never onto the core
# or incomplete thread at the tool's exit.
NUT_CORE_STEP_AIR = LENGTH_FITTED_MIN + PILOT_LENGTH_FITTED_MIN - _CORE_FRONT_MAX
if NUT_CORE_STEP_AIR <= 0.0:
    raise AssertionError(
        f"MHA-PD-13 thumbnut / MHA-PD-08 core step: at the rearward stop the nut "
        f"seat {LENGTH_FITTED_MIN + PILOT_LENGTH_FITTED_MIN:.3f} reaches the core step "
        f"{_CORE_FRONT_MAX:.3f} ({NUT_CORE_STEP_AIR:+.3f})"
    )
# The actual #8-32 nut minor clears the relief at both printed corners.
NUT_RELIEF_RADIAL_AIR = (NUT_MINOR_MIN - RELIEF_DIA_MAX) / 2.0
if NUT_RELIEF_RADIAL_AIR <= 0.0:
    raise AssertionError(
        f"MHA-PD-13 thumbnut / MHA-PD-08 thread relief: the nut's 2B minor "
        f"Ø{NUT_MINOR_MIN:.3f} reaches the relief Ø{RELIEF_DIA_MAX:.3f}"
    )

# --- The chain plane in service (contract §13.2, R9-2 / R9-17) ----------------
# Tsubaki's ±1 sprocket offset at every printed corner, floats included.  The
# fit-up reads the pair (knob against crank) on the front faces, the knob
# wheel held back on its seat, within a band about FIT_UP_OFFSET_TARGET; the
# mid-planes lie half the MHA-PD-09 plate band either way of the faces.  In
# service the crank shaft's end play and the knob's end float move the knob
# wheel forward. R9-70 adds the wheel's own float under the thumbnut, forward
# only (the collar body is its rear stop), and K-1 sets the knob's end float
# on a feeler at fit-up, so it no longer carries the journal, ring and
# hub-to-boss bands (contract: 0..0.35).  R9-71: the MHA-PD-VN-63 spring holds
# the arm on the MHA-PD-20 spacer, which is pressed on the MHA-PD-VN-57
# shoulder, so the hanger has no end play and its tilt is fixed in the bar's
# frame, where the fit-up reads it.  The setting (CHAIN_SET_RANGE) and the
# re-check (pd_paper_drive_assembly_steps) both pass through
# chain_offset_in_service, so the two cannot drift apart.  #2420: the set
# range was the contract's enumerated -0.3103..+0.05 (R9-70, before
# fe4188eb5a held the wheel back on its seat for both readings); its forward
# excess over the .05 ±.05 mm band's mid-planes (-0.15) is about the wheel's
# 0.15 float under the nut, which a floated reading set into the pair and
# the held-back reading now pays once, in service, below.
# Setting .002 ±.007: -0.2786 - 0.25 - 0.254 - 0.1524 = -0.935 .. +0.177.
CHAIN_OFFSET_LIMIT = 1.0
CRANK_END_PLAY_MAX = 0.25
HANGER_AXIAL_PLAY_MAX = 0.0
KNOB_END_FLOAT_MAX = END_FLOAT + END_FLOAT_SET_TOL  # 0.25
_HALF_PLATE_SPREAD = (max(PLATE_BAND) - min(PLATE_BAND)) / 2.0


def chain_pair_range(face_tol: float) -> tuple[float, float]:
    """Knob-wheel mid-plane against the crank wheel's (forward is minus),
    for front faces read held back within ``face_tol`` of the target."""
    return (
        -(FIT_UP_OFFSET_TARGET + face_tol) - _HALF_PLATE_SPREAD,
        face_tol - FIT_UP_OFFSET_TARGET + _HALF_PLATE_SPREAD,
    )


def chain_offset_in_service(face_tol: float) -> tuple[float, float]:
    """The pair read within ``face_tol``, then every service float."""
    low, high = chain_pair_range(face_tol)
    return (
        low - CRANK_END_PLAY_MAX - KNOB_END_FLOAT_MAX - max(KNOB_FLOAT_RANGE),
        high + HANGER_AXIAL_PLAY_MAX,
    )


CHAIN_SET_RANGE = chain_pair_range(FIT_UP_OFFSET_SET_TOL)
CHAIN_OFFSET_IN_SERVICE = chain_offset_in_service(FIT_UP_OFFSET_SET_TOL)
CHAIN_OFFSET_MARGIN = CHAIN_OFFSET_LIMIT - max(map(abs, CHAIN_OFFSET_IN_SERVICE))
if CHAIN_OFFSET_MARGIN < 0.0:
    raise AssertionError(
        f"chain plane in service {CHAIN_OFFSET_IN_SERVICE[0]:+.4f}.."
        f"{CHAIN_OFFSET_IN_SERVICE[1]:+.4f} leaves Tsubaki's "
        f"±{CHAIN_OFFSET_LIMIT} ({CHAIN_OFFSET_MARGIN:+.4f})"
    )

# Physical spatial acceptance, not the cluster's analytic plane fit window.
COLLAR_DISC_AIR_MIN = 0.1016  # .004
COLLAR_DISC_AIR_PHRASE = (
    "PUSH THE DISC AND COLLAR TOWARD EACH OTHER AND TURN THE DISC ONE FULL "
    f"TURN: COLLAR TO DISC AIR {inch_text(COLLAR_DISC_AIR_MIN, 3)} MIN AT THE OVERLAP"
)

# The pilot's length: faced at assembly, its requirement printed with the
# dimension (limits rounded inward); the sheet appends the step that sets it.
PILOT_LENGTH_CALLOUT = (
    f"FACED TO {inch_text(inch_ceil_mm(PILOT_LENGTH_FITTED_MIN, 3), 3)}-"
    f"{inch_text(inch_floor_mm(PILOT_LENGTH_FITTED_MAX, 3), 3)}"
)
# The sheet's numbered fitted-length notes: supply length, then the
# requirement; the sheet appends the step that sets each.
PILOT_SUPPLY_NOTE = (
    f"PILOT: SUPPLY {inch_text(PILOT_BLANK_LENGTH_MIN, 3)} MIN; {PILOT_LENGTH_CALLOUT}"
)
BODY_SUPPLY_NOTE = (
    f"BODY: SUPPLY {inch_text(BODY_BLANK_LENGTH_MIN, 3)} MIN; "
    f"{BODY_LENGTH_CALLOUT.replace(chr(10), ', ')}"
)
PILOT_PROUD_TEXT = (
    f"{inch_text(PILOT_PROUD_RANGE[0], 3)} TO {inch_text(PILOT_PROUD_RANGE[1], 3)}"
)
# The widest line the sheet's notes block holds (its layout test).
FIT_UP_NOTE_WIDTH = 66
FIT_UP_NOTE = "\n".join(
    textwrap.wrap(
        f"SUPPLY THE BODY {inch_text(BODY_BLANK_LENGTH_MIN, 3)} MIN LONG AND PILOT "
        f"{inch_text(PILOT_BLANK_LENGTH_MIN, 3)} MIN LONG. AT ASSEMBLY FACE THE PILOT "
        f"{PILOT_PROUD_TEXT} PROUD OF THE {KNOB_CONFIG} FRONT FACE. "
        f"{BODY_FACE_PHRASE}: SET THE {KNOB_CONFIG} FRONT FACE "
        f"{FIT_UP_OFFSET_SET_TEXT} FORWARD OF THE {CRANK_CONFIG} FRONT FACE "
        "WITH THE ARM AND CRANK SHAFT PULLED FORWARD AND KNOB SHAFT PUSHED REARWARD. "
        "START LONG AND FACE THE REAR TO MOVE THE WHEEL REARWARD; KEEP THE REAR "
        f"FACE ON THE {SHAFT_SEAT_FACE}. FITTED BODY "
        f"{inch_text(LENGTH_FITTED_MIN, 3)}-{inch_text(LENGTH_FITTED_MAX, 3)}. "
        f"THE THUMBNUT SEATS ON THE PILOT, THE {KNOB_CONFIG} FREE UNDER IT. "
        f"STUD END PROUD OF THE THUMBNUT RIM: {STUD_CUT_PHRASE}.",
        width=FIT_UP_NOTE_WIDTH,
        break_on_hyphens=False,
    )
)

# The external drive-pin rim shortfall, note 1: owner-ruled permanent minor
# exception RV-01 in cad/config/parts/pd-transgear-drive-collar.yaml (shared
# #25 sprocket-seat geometry, #2141).  The flat-pin hole to drive-pin hole
# web, note 2: delegated minor exception RV-03 there (#2409).  The bore's fit
# prints at its own callout (BORE_CALLOUT).  The drawing appends the two
# fitted lengths as notes 3 and 4 with their assembly steps
# (draw_pd_transgear_drive_collar.FIT_NOTES).
DRAWING_NOTES = (
    f"1. DRIVE-PIN HOLE TO COLLAR RIM {inch_text(DRIVE_PIN_COLLAR_RIM_WORST, 3)} MIN.\n"
    f"2. {FLAT_PIN_NUMBER} PIN HOLE TO DRIVE-PIN HOLE "
    f"{inch_text(FLAT_PIN_WEB_WORST, 3)} MIN."
)
