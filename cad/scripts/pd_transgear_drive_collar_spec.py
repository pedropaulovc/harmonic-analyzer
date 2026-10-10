r"""MHA-PD-022 transgear-drive-collar: the brass drive collar on the knob shaft.

PURE DATA, no SolidWorks/COM calls and no ``build_*`` module in its import
closure.  ``build_pd_transgear_drive_collar`` marks and tolerances exactly
``DRAWING_DIMENSIONS`` / ``DRAWING_PRECISION`` on the model and
``draw_pd_transgear_drive_collar`` keeps exactly the same names.

The actual D-bore slides over the knob shaft's Ø4.850 h6 solid D-core.
The D-flat carries torque; there is no rear slot or front spring pin.
The existing Ø17.5 body is supplied long and its REAR FACE is faced at
assembly until the removable T24 meets the unchanged chain-plane setting,
with that rear face seated directly on the integral gear front F.
The model body length is 6.2 REF, not an independently toleranced length.
The thumbnut clamps pilot -> body -> actual gear shoulder; it carries no
drive torque. The two existing axial MHA-VN-038 dowels still drive the
removable wheel, and the pilot is faced to retain its .05-.15 float.

The rear D-entry nominal is the actual shaft corner envelope plus one full
entry-tolerance span. Both legs retain the explicit manufacturing band;
the drawn 45-degree angle also spends the title block's angular grade, with
no favourable credit for intersecting those constraints. The smallest
true-D edge, fitted rear axial span and post-break wall bound the maximum
physical leg, while the neck/corner stack bounds its functional minimum.

Part frame: the axis is local +Z through the origin (``Axis1``, the bore
axis); +Z is machine +Z (rearward), so the assembly places the part without
rotation.  The origin is the front (seat) face, machine z -154.3 at the
nominal setting: the body runs z = 0..LENGTH, the pilot -PILOT_LENGTH..0,
and the drive-pin holes run along Z at (0, ±PIN_CIRCLE_RADIUS).

Named datums: ``Axis1``; ``Front Plane`` (the seat face); planes
``PilotFront`` and ``RearFace``; axes ``DrivePinAxis1`` (+Y)
and ``DrivePinAxis2`` (-Y).
"""

from __future__ import annotations

import math
import textwrap

from _fit_limits import REAM_H7
from _printed_tolerance import (
    angular_band_deg,
    drilled_oversize_mm,
    printed_band_mm,
    printed_deviations,
)
from dt_crankshaft_spec import (
    DRIVE_PIN_HOLE_BAND,
    DRIVE_PIN_LENGTH_GRADE,
    DRIVE_PIN_OFFSET_PLACES,
    DRIVE_PIN_OFFSET_TOL,
    SPIGOT_DIA_BAND,
)
from vn_transgear_knob_drive_pin_spec import LENGTH as PIN_LENGTH
from vn_transgear_knob_drive_pin_spec import PROUD_RANGE, THINNEST_PLATE
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
    TIP_STATION,
    TIP_STATION_PLACES,
)
from pd_transgear_removable_spec import BORE_DIA as WHEEL_BORE_DIA
from pd_transgear_removable_spec import (
    CRANK_CONFIG,
    DRIVE_PIN_HOLE_DIA,
    DRIVE_PIN_PROUD,
    KNOB_CONFIG,
    PLATE,
    PLATE_BAND,
    SEAT_SPIGOT_DIA,
    SEAT_SPIGOT_RIM,
)
from pd_transgear_removable_spec import PIN_CIRCLE_RADIUS as _WHEEL_PIN_CIRCLE_RADIUS
from pd_transgear_thumbnut_spec import CSK_DIA as NUT_CSK_DIA
from pd_transgear_thumbnut_spec import FLANGE_DIA as NUT_FLANGE_DIA
from pd_transgear_thumbnut_spec import FLANGE_DIA_PLACES as NUT_FLANGE_DIA_PLACES
from pd_transgear_thumbnut_spec import FRONT_THREAD_LOSS as NUT_FRONT_THREAD_LOSS
from pd_transgear_thumbnut_spec import OVERALL_LENGTH as NUT_LENGTH
from pd_transgear_thumbnut_spec import OVERALL_LENGTH_LO as NUT_LENGTH_LO
from pd_transgear_thumbnut_spec import REAR_THREAD_LOSS as NUT_REAR_THREAD_LOSS
from pd_transgear_thumbnut_spec import TAP_MINOR_2B_MIN as NUT_MINOR_MIN

# The policy's wall floor for a named shortfall (the 2.0 target's floor).
WALL_FLOOR = 1.5

# --- Existing body: fitted rear-face reaction, unchanged wheel-seat station --
SET_NOMINAL = 6.2
SEAT_MIN_FROM_F = 3.870
SEAT_MAX_FROM_F = 6.900
LENGTH = SET_NOMINAL  # REF fitted nominal; never title-block +/- .13
LENGTH_FITTED_MIN = SEAT_MIN_FROM_F
LENGTH_FITTED_MAX = SEAT_MAX_FROM_F
LENGTH_PLACES = 2
BODY_BLANK_LENGTH_MIN = 7.400
OD = SEAT_SPIGOT_DIA  # 17.5, the crank spigot's seat
# The removables swap between shafts: the crank spigot's functional band.
OD_BAND = SPIGOT_DIA_BAND  # (upper, lower) = (0, -0.10)
OD_PLACES = 2

# --- Pilot on the front face, through the wheel's Ø10.3 bore (ruling 5) -------
PILOT_DIA = 10.0
PILOT_DIA_BAND = (0.0, -0.10)
PILOT_DIA_PLACES = 2
# R9-70 (N-A): the thumbnut's seat.  The fitter faces the pilot so its front
# face stands PILOT_PROUD_RANGE proud of the wheel's front face (the plate
# measured, the pilot faced to it plus 0.10 ±0.05), so the wheel is free under
# the nut by the same amount.  The pilot's fitted length is the plate plus
# that: 2.70 + 0.05 = 2.75 .. 2.80 + 0.15 = 2.95; it is supplied
# PILOT_BLANK_LENGTH_MIN long and the model carries the nominal 2.8 + 0.10.
PILOT_PROUD_RANGE = (0.05, 0.15)
PILOT_PROUD = sum(PILOT_PROUD_RANGE) / 2.0  # 0.10
PILOT_LENGTH = PLATE + PILOT_PROUD  # 2.90, nominal fitted
PILOT_LENGTH_PLACES = 2
PILOT_LENGTH_FITTED_MIN = THINNEST_PLATE + min(PILOT_PROUD_RANGE)  # 2.75
PILOT_LENGTH_FITTED_MAX = PLATE + max(PLATE_BAND) + max(PILOT_PROUD_RANGE)  # 2.95
FACING_ALLOWANCE = 0.10
PILOT_BLANK_LENGTH_MIN = 3.40
if PILOT_BLANK_LENGTH_MIN < PILOT_LENGTH_FITTED_MAX + FACING_ALLOWANCE - 1e-9:
    raise AssertionError(
        f"MHA-PD-022 pilot blank {PILOT_BLANK_LENGTH_MIN:.2f} MIN leaves no "
        f"{FACING_ALLOWANCE} facing allowance over the "
        f"{PILOT_LENGTH_FITTED_MAX:.2f} longest fit"
    )
if not PILOT_LENGTH_FITTED_MIN <= PILOT_LENGTH <= PILOT_LENGTH_FITTED_MAX:
    raise AssertionError("MHA-PD-022's modelled pilot lies outside its fitted band")

# --- True D-bore: curved H7 envelope plus a separately banded flat -----------
BORE_DIA = CORE_DIA + 0.010
BORE_DIA_BAND = REAM_H7
BORE_DIA_PLACES = 3
# Actual model midpoint, not a basic flat outside its positive band. Moved in
# 0.025 with the knob core radius (4.900 -> 4.850, 0.05 tooth-space TIR).
FLAT_LIMITS = (2.145, 2.160)
FLAT_TO_AXIS = sum(FLAT_LIMITS) / 2.0
FLAT_BAND = (FLAT_LIMITS[1] - FLAT_TO_AXIS, FLAT_LIMITS[0] - FLAT_TO_AXIS)
FLAT_TOL_TYPE = 3  # native LIMIT, three-place 2.145..2.160
FLAT_PLACES = 3
FLAT_CLEARANCE = (
    FLAT_TO_AXIS + min(FLAT_BAND) - (CORE_FLAT_FROM_AXIS + max(CORE_FLAT_BAND)),
    FLAT_TO_AXIS + max(FLAT_BAND) - (CORE_FLAT_FROM_AXIS + min(CORE_FLAT_BAND)),
)
_CORE_R_MIN = (CORE_DIA + min(CORE_DIA_BAND)) / 2.0
_BORE_R_MAX = (BORE_DIA + max(BORE_DIA_BAND)) / 2.0
_CORE_FLAT_MIN = CORE_FLAT_FROM_AXIS + min(CORE_FLAT_BAND)
# Every direction sees >=flatMIN support on the core's retained major arc.
# The largest permitted centre translation therefore satisfies
# coreRMIN² + float² + 2*flatMIN*float <= boreRMAX².
D_CENTRE_FLOAT_MAX = math.sqrt(
    _CORE_FLAT_MIN**2 + _BORE_R_MAX**2 - _CORE_R_MIN**2
) - _CORE_FLAT_MIN
STUD_D_BORE_AIR = min(
    BORE_DIA + min(BORE_DIA_BAND),
    2.0 * (FLAT_TO_AXIS + min(FLAT_BAND)),
) / 2.0 - max(THREAD_BLANK_LIMITS) / 2.0
# Keep one full manufacturing-tolerance span beyond the actual shaft corner
# envelope, without spending favourable neck/bore air to shrink the entry.
# This derives the inherited .200 nominal / .150.. .250 controlled size
# from the mating geometry; its explicit band and three-place PMI are unchanged.
BORE_ENTRY_BREAK_BAND = (0.050, -0.050)
BORE_ENTRY_BREAK_PLACES = 3
BORE_ENTRY_BREAK = round(
    FRONT_CORNER_RADIUS_MAX
    + max(BORE_ENTRY_BREAK_BAND) - min(BORE_ENTRY_BREAK_BAND),
    BORE_ENTRY_BREAK_PLACES,
)
BORE_ENTRY_BREAK_MIN = BORE_ENTRY_BREAK + min(BORE_ENTRY_BREAK_BAND)
BORE_ENTRY_BREAK_MAX = BORE_ENTRY_BREAK + max(BORE_ENTRY_BREAK_BAND)
BORE_ENTRY_BREAK_ANGLE_DEG = 45.0
BORE_ENTRY_BREAK_ANGLE_BAND_DEG = angular_band_deg()
BORE_ENTRY_BREAK_ANGLE_LIMITS = (
    BORE_ENTRY_BREAK_ANGLE_DEG - BORE_ENTRY_BREAK_ANGLE_BAND_DEG,
    BORE_ENTRY_BREAK_ANGLE_DEG + BORE_ENTRY_BREAK_ANGLE_BAND_DEG,
)
if not 0.0 < min(BORE_ENTRY_BREAK_ANGLE_LIMITS) < max(BORE_ENTRY_BREAK_ANGLE_LIMITS) < 90.0:
    raise AssertionError("MHA-PD-022 rear D-entry angle band must remain acute")
# At the authored 90-degree rear face/wall junction, the second leg is
# width*tan(angle). Both width and angle increase it monotonically. Spend
# every independent printed corner even though BOTH LEGS constrains the
# accepted intersection more tightly: no nominal-45 or favourable-leg credit.
BORE_ENTRY_BREAK_LEG_MIN = min(
    BORE_ENTRY_BREAK_MIN,
    BORE_ENTRY_BREAK_MIN * math.tan(math.radians(min(BORE_ENTRY_BREAK_ANGLE_LIMITS))),
)
BORE_ENTRY_BREAK_LEG_MAX = max(
    BORE_ENTRY_BREAK_MAX,
    BORE_ENTRY_BREAK_MAX * math.tan(math.radians(max(BORE_ENTRY_BREAK_ANGLE_LIMITS))),
)
BORE_ENTRY_BREAK_CALLOUT = (
    f"X {BORE_ENTRY_BREAK_ANGLE_DEG:g} DEG\nBOTH D EDGES; BOTH LEGS"
)
# Spend both turned-surface axes independently; no perfect common-axis credit.
NECK_D_BORE_AIR_MIN = (
    FLAT_TO_AXIS + min(FLAT_BAND) - FRONT_RELIEF_DIA_MAX / 2.0
    - (CORE_TOTAL_RUNOUT + FRONT_RELIEF_TOTAL_RUNOUT) / 2.0 - D_CENTRE_FLOAT_MAX
)
# Under drive use the actual minimum core-flat plane, with NO favourable
# bore-float credit. This is why the neck is4.000, not the old4.050 proposal.
NECK_TORQUE_FLAT_AIR_MIN = (
    _CORE_FLAT_MIN - FRONT_RELIEF_DIA_MAX / 2.0
    - (CORE_TOTAL_RUNOUT + FRONT_RELIEF_TOTAL_RUNOUT) / 2.0
)
BORE_ENTRY_BREAK_REQUIRED_MIN = max(
    0.0,
    FRONT_CORNER_RADIUS_MAX
    - min(NECK_D_BORE_AIR_MIN, NECK_TORQUE_FLAT_AIR_MIN),
)
# Over0..R the entry-clearance minus quarter-circle is concave, so its
# minimum is at an end. Spend the smaller physical leg at every printed corner.
NECK_CORNER_D_BORE_AIR_MIN = (
    min(NECK_D_BORE_AIR_MIN, NECK_TORQUE_FLAT_AIR_MIN)
    + BORE_ENTRY_BREAK_LEG_MIN - FRONT_CORNER_RADIUS_MAX
)
D_DRIVE_WIDTH_MIN = 2.0 * math.sqrt(
    _CORE_R_MIN**2 - (CORE_FLAT_FROM_AXIS + max(CORE_FLAT_BAND))**2
)
D_DRIVE_AREA_MIN = (
    (D_DRIVE_WIDTH_MIN - 2.0 * BORE_ENTRY_BREAK_LEG_MAX)
    * (CORE_ACTIVE_LENGTH_MIN - 2.0 * BORE_ENTRY_BREAK_LEG_MAX)
)
# The F face lies beyond the active D support. Bound a straight bore's axis
# at both unbroken support sections, then extrapolate to F; spend the actual
# core/journal runout at BOTH sections, not only a favourable common axis.
D_SUPPORT_LENGTH_MIN = CORE_ACTIVE_LENGTH_MIN - 2.0 * BORE_ENTRY_BREAK_LEG_MAX
D_SUPPORT_TO_F_MAX = FRONT_RELIEF_WIDTH_MAX + BORE_ENTRY_BREAK_LEG_MAX
D_AXIS_AT_F_FROM_JOURNAL_MAX = (
    D_CENTRE_FLOAT_MAX + CORE_TOTAL_RUNOUT / 2.0
) * (1.0 + 2.0 * D_SUPPORT_TO_F_MAX / D_SUPPORT_LENGTH_MIN)
FRONT_BEARING_INNER_RADIUS_MAX = (
    _BORE_R_MAX + BORE_ENTRY_BREAK_LEG_MAX + D_AXIS_AT_F_FROM_JOURNAL_MAX
    + TOOTH_SPACE_RUNOUT_TIR_MM / 2.0
)
FRONT_BEARING_AREA_MIN = min(
    gear_bearing_area_lower(profile, FRONT_BEARING_INNER_RADIUS_MAX)
    for profile in manufactured_profiles()
)

# --- Drive-pin holes: reamed THROUGH for the MHA-VN-038 press (the crank's twin) -
PIN_CIRCLE_RADIUS = _WHEEL_PIN_CIRCLE_RADIUS  # 7.0, ±Y
PIN_HOLE_DIA = DRIVE_PIN_HOLE_DIA  # 2.38
PIN_HOLE_BAND = DRIVE_PIN_HOLE_BAND  # (0, -0.010)
PIN_HOLE_PLACES = 3
PIN_OFFSET_TOL = DRIVE_PIN_OFFSET_TOL  # ±0.025 each centre
PIN_OFFSET_PLACES = DRIVE_PIN_OFFSET_PLACES
PIN_HOLE_DEPTH = LENGTH  # through the body

# --- Native D construction and the existing drive-hole carriers ------------
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "BodyProfile": {"CollarDia", "CollarLength", "PilotDia", "PilotLength"},
    "BoreProfile": {"BoreDia", "FlatToAxis"},
    "RearBoreChamfer": {"BoreEntryBreak"},
    "PinHoleProfile": {"PinPosDia", "PinPosY", "PinNegY"},
}
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "BodyProfile": {
        "CollarDia": OD_PLACES,
        "CollarLength": LENGTH_PLACES,
        "PilotDia": PILOT_DIA_PLACES,
        "PilotLength": PILOT_LENGTH_PLACES,
    },
    "BoreProfile": {"BoreDia": BORE_DIA_PLACES, "FlatToAxis": FLAT_PLACES},
    "RearBoreChamfer": {"BoreEntryBreak": BORE_ENTRY_BREAK_PLACES},
    "PinHoleProfile": {
        "PinPosDia": PIN_HOLE_PLACES,
        "PinPosY": PIN_OFFSET_PLACES,
        "PinNegY": PIN_OFFSET_PLACES,
    },
}
if {feature: set(names) for feature, names in DRAWING_PRECISION.items()} != (
    DRAWING_DIMENSIONS
):
    raise AssertionError("every marked MHA-PD-022 dimension needs authored places")
DRAWING_PRECISION_BY_NAME: dict[str, int] = {
    name: places
    for dimensions in DRAWING_PRECISION.values()
    for name, places in dimensions.items()
}

if BODY_BLANK_LENGTH_MIN < LENGTH_FITTED_MAX + FACING_ALLOWANCE - 1e-9:
    raise AssertionError("MHA-PD-022 body blank leaves no rear-facing allowance")
if not LENGTH_FITTED_MIN <= LENGTH <= LENGTH_FITTED_MAX:
    raise AssertionError("MHA-PD-022 model body lies outside its fitted band")


def floor_2(value: float) -> float:
    """A MIN on the sheet never rounds up past the arithmetic."""
    return math.floor(value * 100.0 + 1e-9) / 100.0


# --- Walls (contract §8) ---------------------------------------------------------
_OD_R_MIN = (OD + min(OD_BAND)) / 2.0  # 8.70
_PIN_HOLE_R_MAX = (PIN_HOLE_DIA + max(PIN_HOLE_BAND)) / 2.0  # 1.19
# Drive-pin hole to the Ø17.5 rim: 8.75 - 7.0 - 1.19 = 0.56 nominal;
# 8.70 - 7.025 - 1.19 = 0.485 worst, printed 0.48.
DRIVE_PIN_COLLAR_RIM = OD / 2.0 - PIN_CIRCLE_RADIUS - PIN_HOLE_DIA / 2.0
DRIVE_PIN_COLLAR_RIM_WORST = floor_2(
    _OD_R_MIN - PIN_CIRCLE_RADIUS - PIN_OFFSET_TOL - _PIN_HOLE_R_MAX
)
# The smaller D-bore now meets the full 2 mm pilot-wall target.
PILOT_WALL = (PILOT_DIA - BORE_DIA) / 2.0
PILOT_WALL_WORST = floor_2(
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
# The entry is on the BODY rear, not the smaller pilot front. Spend the
# largest radial leg against both pin holes and the outer body envelope.
BORE_ENTRY_WALL_MIN = min(BORE_PIN_WALL_WORST, _OD_R_MIN - _BORE_R_MAX)
BORE_ENTRY_WALL_WORST = BORE_ENTRY_WALL_MIN - BORE_ENTRY_BREAK_LEG_MAX
# These are the actual opening's flat chord and retained major arc, not a
# full-circle proxy. The chord decreases with flat offset and increases with
# bore radius; the major arc increases with both. Their independent worst
# corners therefore bound every accepted D profile.
_BORE_R_MIN = (BORE_DIA + min(BORE_DIA_BAND)) / 2.0
BORE_ENTRY_FLAT_EDGE_MIN = 2.0 * math.sqrt(
    _BORE_R_MIN**2 - max(FLAT_LIMITS)**2
)
BORE_ENTRY_ARC_EDGE_MIN = 2.0 * _BORE_R_MIN * (
    math.pi - math.acos(min(FLAT_LIMITS) / _BORE_R_MIN)
)
BORE_ENTRY_PROFILE_EDGE_MIN = min(BORE_ENTRY_FLAT_EDGE_MIN, BORE_ENTRY_ARC_EDGE_MIN)
# Bound even unequal as-made setbacks: a flat at its largest outward break
# must stay inside the smallest arc envelope even if that arc has no setback
# at the same axial section. This protects the whole D, not just its mid-arc.
BORE_ENTRY_PROFILE_DEPTH_MIN = _BORE_R_MIN - max(FLAT_LIMITS)
# Stop before the nearest axial body/pilot shoulder even though the D bore
# itself continues through the pilot. Use the shortest actual fitted body.
BORE_ENTRY_AXIAL_SPAN_MIN = LENGTH_FITTED_MIN
# Reserve two end legs on the profile/core edges and preserve the wall floor.
# Actual gear-front bearing area and axis-extrapolation guards remain separate;
# this is a geometric ceiling, not permission to enlarge the functional break.
BORE_ENTRY_BREAK_GEOMETRY_MAX = min(
    BORE_ENTRY_PROFILE_EDGE_MIN / 2.0,
    BORE_ENTRY_PROFILE_DEPTH_MIN,
    BORE_ENTRY_AXIAL_SPAN_MIN,
    BORE_ENTRY_WALL_MIN - WALL_FLOOR,
    D_DRIVE_WIDTH_MIN / 2.0,
    CORE_ACTIVE_LENGTH_MIN / 2.0,
)
# The holes run through the body beside the pilot, never into it.
PIN_HOLE_INNER_R_MIN = PIN_CIRCLE_RADIUS - PIN_OFFSET_TOL - _PIN_HOLE_R_MAX  # 5.785
PILOT_R_MAX = (PILOT_DIA + max(PILOT_DIA_BAND)) / 2.0  # 5.0

# --- Fits ------------------------------------------------------------------------
# Diametral sliding clearance of the curved portion of the true D interface.
BORE_CORE_CLEARANCE = (
    BORE_DIA + min(BORE_DIA_BAND) - (CORE_DIA + max(CORE_DIA_BAND)),
    BORE_DIA + max(BORE_DIA_BAND) - (CORE_DIA + min(CORE_DIA_BAND)),
)
# Radial air round the pilot in the wheel's drilled Ø10.3 bore: 0.15 .. 0.25.
PILOT_BORE_CLEARANCE = (
    (WHEEL_BORE_DIA - (PILOT_DIA + max(PILOT_DIA_BAND))) / 2.0,
    (WHEEL_BORE_DIA + drilled_oversize_mm() - (PILOT_DIA + min(PILOT_DIA_BAND))) / 2.0,
)
# R9-70 (N-A): the thumbnut seats on the pilot's front face, which stands
# PILOT_PROUD_RANGE proud of the wheel's front face: the nut's seat bears on the
# pilot's annulus outside its rear countersink, (9.90 - 6.75) / 2 = 1.575 at
# worst case, its flange covers the pilot all round, and the wheel is free
# under it by the proud.
_NUT_FLANGE_LO, _ = printed_deviations(NUT_FLANGE_DIA, NUT_FLANGE_DIA_PLACES)
NUT_PILOT_BEARING_WORST = (PILOT_DIA + min(PILOT_DIA_BAND) - NUT_CSK_DIA) / 2.0
NUT_FLANGE_OVER_PILOT_WORST = (
    NUT_FLANGE_DIA + _NUT_FLANGE_LO - (PILOT_DIA + max(PILOT_DIA_BAND))
) / 2.0
KNOB_FLOAT_RANGE = PILOT_PROUD_RANGE


# --- Drive pins pressed through to a stop (MHA-VN-038) ------------------------------
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

# --- Fitted axial reaction -------------------------------------------------
# With the rear face seated on the actual gear shoulder, body length IS the
# front wheel seat's distance from F. No front pin or unreacted axial gap.
BODY_REAR_FACE_FROM_F = 0.0
BODY_LENGTH_CALLOUT = (
    f"FITTED {LENGTH_FITTED_MIN:.3f}-{LENGTH_FITTED_MAX:.3f}\n"
    "REAR FACE TO FIT, SEATED ON GEAR FRONT F"
)
BODY_FACE_PHRASE = (
    "FACE THE COLLAR REAR WITH THE REAR FACE SEATED ON GEAR FRONT F "
    "UNTIL THE KNOB-WHEEL FRONT MEETS THE CHAIN SETTING"
)

for _ok, _what in (
    (
        math.isclose(DRIVE_PIN_COLLAR_RIM, SEAT_SPIGOT_RIM, abs_tol=1e-9),
        "the collar rim is not the seat interface's rim",
    ),
    (DRIVE_PIN_COLLAR_RIM_WORST > 0.0, "the drive-pin holes break out of the rim"),
    (PILOT_WALL_WORST >= WALL_FLOOR, "pilot wall under the floor"),
    (min(FLAT_CLEARANCE) > 0.0, "the D-flat binds on the solid core"),
    (STUD_D_BORE_AIR > 0.0, "the round stud cannot pass the actual D-bore"),
    (FRONT_BEARING_AREA_MIN > 0.0, "the collar rear face has no actual gear support"),
    (NECK_D_BORE_AIR_MIN > 0.0, "the front neck enters the D-bore flat"),
    (NECK_TORQUE_FLAT_AIR_MIN > 0.0, "the front neck enters the torqued core-flat plane"),
    (NECK_CORNER_D_BORE_AIR_MIN > 0.0, "the D entry cannot clear a neck corner"),
    (
        BORE_ENTRY_BREAK_LEG_MIN > BORE_ENTRY_BREAK_REQUIRED_MIN,
        "the smallest entry leg does not exceed the functional corner envelope",
    ),
    (
        BORE_ENTRY_BREAK_LEG_MAX < BORE_ENTRY_BREAK_GEOMETRY_MAX,
        "the largest entry leg consumes an adjacent edge, axial span or wall",
    ),
    (BORE_ENTRY_WALL_WORST >= WALL_FLOOR, "rear D entry to pin hole or rim under the floor"),
    (D_DRIVE_AREA_MIN > 0.0, "the shortened D-core has no usable drive face"),
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
    (BODY_REAR_FACE_FROM_F == 0.0, "the collar has no axial reaction at gear front F"),
):
    if not _ok:
        raise AssertionError(f"MHA-PD-022: {_what}")

# Policy rule 6: the callout states the requirement, not a method; the
# native +0.012/0.000 band already prints the curved portion's H7.
BORE_CALLOUT = "TRUE D THRU"
# The view shows the flat's side; the matched fit is the requirement.
FLAT_ORIENTATION = "MATCH SHAFT D"
PIN_HOLE_CALLOUT = "2X REAM THROUGH"
# The overall, pilot front face to rear face, prints as a .X reference.
OVERALL_LENGTH = LENGTH + PILOT_LENGTH
DRAWING_REFERENCE_PRECISION = 1
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW\nSCALE 2:1"

# Rear-face fit and pilot fit are actual assembly operations; the supplied
# body/pilot are deliberately long. The assembly prints these same phrases.
# The knob-wheel front face is set FIT_UP_OFFSET_TARGET forward of the crank
# wheel's front face, within FIT_UP_OFFSET_SET_TOL at setting (§13.2 procedure (4)).
FIT_UP_OFFSET_TARGET = 0.05
FIT_UP_OFFSET_SET_TOL = 0.05
FIT_UP_OFFSET_SET_TEXT = f"{FIT_UP_OFFSET_TARGET:.2f} \u00b1{FIT_UP_OFFSET_SET_TOL:.2f}"
# Procedure (7): a stud end standing proud of the thumbnut's rim is cut this
# far below the rim and re-chamfered 45 degrees to the thread minor (the
# MHA-PD-008 tip form).
STUD_CUT_BELOW_RIM = (0.3, 1.0)
STUD_RECHAMFER_DEG = 45
STUD_CUT_PHRASE = (
    f"CUT {STUD_CUT_BELOW_RIM[0]:.1f} TO {STUD_CUT_BELOW_RIM[1]:.1f} BELOW THE "
    f"RIM, RE-CHAMFER {STUD_RECHAMFER_DEG}\u00b0 TO THE MINOR"
)

# --- The thumbnut on the stud over the whole setting (R9-53, contract §7) ------
# The fitter may leave the knob-wheel seat anywhere from the rearward stop (the
# collar's rear face on F, seat = the collar length) to SEAT_MAX_FROM_F.  The
# nut seats on the pilot's faced front face (R9-70), the fitted pilot length
# in front of the seat.
_TIP_STATION_MIN = TIP_STATION - printed_band_mm(TIP_STATION_PLACES)  # 23.39
_PLAIN_CORE_MAX = PLAIN_CORE + printed_band_mm(PLAIN_CORE_PLACES)  # 7.63
_CORE_FRONT_MAX = CORE_FRONT_FROM_F + printed_band_mm(CORE_FRONT_FROM_F_PLACES)
NUT_LENGTH_MIN = NUT_LENGTH + NUT_LENGTH_LO  # 15.3


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
        f"MHA-PD-013 thumbnut / MHA-PD-008 stud: {THUMBNUT_ENGAGEMENT_WORST:.3f} of full "
        f"thread ({THUMBNUT_ENGAGEMENT_WORST / THREAD_MAJOR:.2f} D) at the worst "
        f"setting, under {ENGAGEMENT_FLOOR_D} D"
    )
# At the rearward stop the nut's seat stands in front of the core's step, so
# its thread runs only on full thread or over the relief, never onto the core
# or a die run-out: 3.87 + 2.75 - 5.38 = 1.24.
NUT_CORE_STEP_AIR = LENGTH_FITTED_MIN + PILOT_LENGTH_FITTED_MIN - _CORE_FRONT_MAX
if NUT_CORE_STEP_AIR <= 0.0:
    raise AssertionError(
        f"MHA-PD-013 thumbnut / MHA-PD-008 core step: at the rearward stop the nut "
        f"seat {LENGTH_FITTED_MIN + PILOT_LENGTH_FITTED_MIN:.3f} reaches the core step "
        f"{_CORE_FRONT_MAX:.3f} ({NUT_CORE_STEP_AIR:+.3f})"
    )
# The actual #8-32 nut minor clears the relief at both printed corners.
NUT_RELIEF_RADIAL_AIR = (NUT_MINOR_MIN - RELIEF_DIA_MAX) / 2.0
if NUT_RELIEF_RADIAL_AIR <= 0.0:
    raise AssertionError(
        f"MHA-PD-013 thumbnut / MHA-PD-008 thread relief: the nut's 2B minor "
        f"Ø{NUT_MINOR_MIN:.3f} reaches the relief Ø{RELIEF_DIA_MAX:.3f}"
    )

# --- The chain plane in service (contract §13.2, R9-2 / R9-17) ----------------
# Tsubaki's ±1 sprocket offset at every printed corner, floats included.  The
# contract's enumeration sets the pair (knob against crank, mid-planes) at
# CHAIN_SET_RANGE; in service the crank shaft's end play and the knob's end
# float move the knob wheel forward. R9-70 adds the wheel's own float under the
# thumbnut, forward only (the collar body is its rear stop), and K-1 sets the
# knob's end float on a feeler at fit-up, so it no longer carries the
# journal, ring and hub-to-boss bands (contract: 0..0.35).  R9-71: the
# MHA-VN-049 spring holds the arm on the MHA-PD-020 spacer, which is pressed on the
# MHA-VN-041 shoulder, so the hanger has no end play and its tilt is fixed in
# the bar's frame, where the fit-up reads it:
# -0.3103 - 0.25 - 0.25 - 0.15 = -0.9603 .. +0.05.
CHAIN_OFFSET_LIMIT = 1.0
CHAIN_SET_RANGE = (-0.3103, 0.05)
CRANK_END_PLAY_MAX = 0.25
HANGER_AXIAL_PLAY_MAX = 0.0
KNOB_END_FLOAT_MAX = END_FLOAT + END_FLOAT_SET_TOL  # 0.25
CHAIN_OFFSET_IN_SERVICE = (
    CHAIN_SET_RANGE[0] - CRANK_END_PLAY_MAX - KNOB_END_FLOAT_MAX - max(KNOB_FLOAT_RANGE),
    CHAIN_SET_RANGE[1] + HANGER_AXIAL_PLAY_MAX,
)
CHAIN_OFFSET_MARGIN = CHAIN_OFFSET_LIMIT - max(map(abs, CHAIN_OFFSET_IN_SERVICE))
if CHAIN_OFFSET_MARGIN < 0.0:
    raise AssertionError(
        f"chain plane in service {CHAIN_OFFSET_IN_SERVICE[0]:+.4f}.."
        f"{CHAIN_OFFSET_IN_SERVICE[1]:+.4f} leaves Tsubaki's "
        f"±{CHAIN_OFFSET_LIMIT} ({CHAIN_OFFSET_MARGIN:+.4f})"
    )

# Physical spatial acceptance, not the cluster's analytic plane fit window.
COLLAR_DISC_AIR_MIN = 0.10
COLLAR_DISC_AIR_PHRASE = (
    "PUSH THE DISC AND COLLAR TOWARD EACH OTHER AND TURN THE DISC ONE FULL "
    f"TURN: COLLAR TO DISC AIR {COLLAR_DISC_AIR_MIN:.2f} MIN AT THE OVERLAP"
)

# The pilot's length: faced at assembly, its requirement printed with the
# dimension; the sheet appends the step that sets it.
PILOT_LENGTH_CALLOUT = (
    f"SET AT ASSEMBLY {PILOT_LENGTH_FITTED_MIN:.2f}-{PILOT_LENGTH_FITTED_MAX:.2f}"
    "\nFACED TO FIT"
)
# The sheet's numbered fitted-length notes: supply length, then the
# requirement; the sheet appends the step that sets each.
PILOT_SUPPLY_NOTE = (
    f"PILOT: SUPPLY {PILOT_BLANK_LENGTH_MIN:.2f} MIN; "
    f"{PILOT_LENGTH_CALLOUT.replace(chr(10), ', ')}"
)
BODY_SUPPLY_NOTE = (
    f"BODY: SUPPLY {BODY_BLANK_LENGTH_MIN:.3f} MIN; "
    f"{BODY_LENGTH_CALLOUT.replace(chr(10), ', ')}"
)
PILOT_PROUD_TEXT = f"{PILOT_PROUD_RANGE[0]:.2f} TO {PILOT_PROUD_RANGE[1]:.2f}"
# The widest line the sheet's notes block holds (its layout test).
FIT_UP_NOTE_WIDTH = 66
FIT_UP_NOTE = "\n".join(
    textwrap.wrap(
        f"SUPPLY THE BODY {BODY_BLANK_LENGTH_MIN:.3f} MIN LONG AND PILOT "
        f"{PILOT_BLANK_LENGTH_MIN:.2f} MIN LONG. AT ASSEMBLY FACE THE PILOT "
        f"{PILOT_PROUD_TEXT} PROUD OF THE {KNOB_CONFIG} FRONT FACE. "
        f"{BODY_FACE_PHRASE}: SET THE {KNOB_CONFIG} FRONT FACE "
        f"{FIT_UP_OFFSET_SET_TEXT} FORWARD OF THE {CRANK_CONFIG} FRONT FACE "
        "WITH THE ARM AND CRANK SHAFT PULLED FORWARD AND KNOB SHAFT PUSHED REARWARD. "
        "START LONG AND FACE THE REAR TO MOVE THE WHEEL REARWARD; KEEP THE REAR "
        f"FACE ON F. FITTED BODY {LENGTH_FITTED_MIN:.3f}-{LENGTH_FITTED_MAX:.3f}. "
        f"THE THUMBNUT SEATS ON THE PILOT, THE {KNOB_CONFIG} FREE UNDER IT. "
        f"STUD END PROUD OF THE THUMBNUT RIM: {STUD_CUT_PHRASE}.",
        width=FIT_UP_NOTE_WIDTH,
        break_on_hyphens=False,
    )
)

# Existing named external drive-pin rim exception only. The pilot now meets
# the target and the obsolete slotted-floor exception no longer exists. The
# drawing numbers these 1 and 2 and appends the two fitted lengths as notes 3
# and 4 with their assembly steps (draw_pd_transgear_drive_collar.FIT_NOTES).
DRAWING_NOTES = "\n".join(
    (
        f"1. DRIVE-PIN HOLE TO COLLAR RIM {DRIVE_PIN_COLLAR_RIM_WORST:.2f} MIN.",
        "2. TRUE D-BORE; CONTROLLED REAR ENTRY BREAK CLEARS SHAFT F CORNERS.",
    )
)
