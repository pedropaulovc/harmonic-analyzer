"""Custom MHA-VN-016 stack collar and its reworked stock set screw, mm.

9414T1 was the historical 1/16-inch collar, not a 1/32-inch product. Live
McMaster 1/32-inch collars (6435K234, 6436K236, 6157K64; 2026-10-08) are
clamp-on alternatives, not unavailable products. This custom design preserves
the existing set-screw mechanism and is turned from 3/4-inch steel bar.
Its screw is genuine 94355A213, #2-56 x
5/16-inch 18-8 stainless, with the flat tip ground to the native dog geometry.
The supplier specifies the 0.035-inch hex, but not its depth or edge breaks.
The model uses ASME's minimum key engagement and leaves every edge sharp;
those retained stock details are not rework dimensions on this print.

The collar axis is +Y, south face y=0, north face y=WIDTH. The radial screw
is on +X at the BASIC tap station from datum B with model-owned position PMI.
Default is installed; Collar and SetScrew configurations define the two
manufacturing components separately.
Set one COLLAR_FEELER off T006 and lock on the shaft D-flat. The block/cup
still control shaft end play, never the collar. Assembly owns the full
collar/block/plate air stack and moves the tip-end station for this envelope.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import _config

from _gtol_spec import CylinderFace, GeometricControl, PartDatum, PlanarFace
from _hole_spec import DRILL_POINT_H, HoleSpec, TAP_DRILL_MM
from _printed_tolerance import printed_band_mm
from cone_shaft_land_bands import (
    RUNNING_DIA_BAND,
    TERMINAL_DIA_MM,
    TERMINAL_DIA_PLACES,
    TERMINAL_FINISHED_DIA_LIMITS_MM,
    TERMINAL_FINISHED_AF_LIMITS_MM,
    TERMINAL_FLAT_AF_MM,
    TERMINAL_HALF_CHORD_MIN_MM,
    TIP_COLLAR_MAX_RADIAL_FLOAT_MM,
    TIP_COLLAR_WIDTH_MM,
    TIP_COLLAR_MIN_RADIAL_FLOAT_MM,
    TIP_COLLAR_WIDTH_BAND_MM,
    TIP_COLLAR_NOSE_LENGTH_MM,
    TIP_COLLAR_TAP_STATION_MM,
    TIP_COLLAR_FREE_EDGE_BREAK_MAX_MM,
    TIP_COLLAR_INSTALLED_COCK_ANGLE_RAD,
    TIP_COLLAR_BACK_ARC_REACTION_ANGLE_RAD,
    TIP_COLLAR_MIN_CONTACT_SPAN_MM,
    TIP_SCREW_TO_JOURNAL_MAX_AXIS_ANGLE_RAD,
    TIP_SCREW_DOG_AXIAL_PROJECTION_MM,
    TIP_SCREW_DOG_AXIS_OFFSET_MM,
    TIP_SCREW_DOG_DIA_BAND,
    TIP_SCREW_DOG_DIA_MM,
    TIP_SCREW_DOG_LENGTH_MM,
    TIP_SCREW_DOG_TOTAL_RUNOUT_MM,
    TIP_SCREW_DOG_PROJECTED_RADIUS_MM,
    TERMINAL_FLAT_EDGE_BREAK_MAX,
    TIP_SCREW_MAJOR_AXIAL_PROJECTION_MM,
    TIP_SCREW_MAJOR_DIA_MM,
    TIP_SCREW_MAX_AXIS_ANGLE_RAD,
    TIP_SCREW_PITCH_MM,
    TIP_SCREW_POSITION_DIA_MM,
    TIP_SCREW_REQUIRED_FULL_ENGAGEMENT_MM,
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
SHOULDER_ROOT_RADIUS = 0.25
SHOULDER_ROOT_BAND = (0.0, -SHOULDER_ROOT_RADIUS)
# The title block's free-edge break: the wall, thread and contact budgets
# book it, but the model leaves the edges sharp (the title block prints it).
EDGE_BREAK = TIP_COLLAR_FREE_EDGE_BREAK_MAX_MM
FLAT_DISTANCE = 7.0
ROUTINE_BAND_MM = printed_band_mm(2)
WALL_TARGET_MM = 2.0
WALL_FLOOR_MM = 1.5

BOM_DESCRIPTION = str(_config.parts("vn-cone-tip-collar")["description"])
MANUFACTURING_DESCRIPTIONS = {
    "Collar": "Turned steel cone tip stack collar",
    "SetScrew": "Ground-dog rework of supplied McMaster 94355A213 set screw",
}

SET_SCREW_SKU = "94355A213"
SET_SCREW_THREAD = "#2-56"
SET_SCREW_MAJOR_DIA = TIP_SCREW_MAJOR_DIA_MM
SET_SCREW_PITCH = TIP_SCREW_PITCH_MM
SET_SCREW_LENGTH = 5.0 * IN / 16.0
SET_SCREW_LENGTH_BAND_MM = 0.01 * IN  # ASME B18.3 Table 14 note (11), L <= 0.63 in
SET_SCREW_SOCKET_AF = 0.035 * IN
SET_SCREW_SOCKET_DEPTH = 0.060 * IN  # Table 14 #2 minimum key engagement; not vendor-exact
SET_SCREW_END_FACE_MIN_ANGLE_DEG = 30.0  # Table 14 note (1): socket-face chamfer 30..45 deg
SET_SCREW_FACTORY_POINT_MIN_DIA = 0.039 * IN  # Table 14 #2 flat-point P MIN
SET_SCREW_FACTORY_POINT_MIN_ANGLE_DEG = 45.0  # Table 14 note (2), length >= B
DOG_DIA = TIP_SCREW_DOG_DIA_MM
DOG_DIA_BAND = TIP_SCREW_DOG_DIA_BAND
DOG_LENGTH = TIP_SCREW_DOG_LENGTH_MM
# The title block's R0.25 exceeds the Ø0.20 dog's radius and would remove its
# ground face; 0.02 keeps Ø0.15 of face at the dog's least Ø0.19. Printed
# above the dog Ø, on one line (SolidWorks prints no above-callout line
# break); the model's dog edge stays sharp.
DOG_EDGE_BREAK = 0.02
DOG_EDGE_CALLOUT = f"STONE DOG EDGE {DOG_EDGE_BREAK:.2f} MAX"
# Coordinates in the collar's frame. The loaded collar centre moves toward
# +X; its bore seats on the shaft's retained -X BACK arc. The dog consequently
# advances by that nonzero displacement rather than hovering above the flat.
SET_SCREW_SEAT_RADIUS = (
    TERMINAL_FLAT_AF_MM - TERMINAL_DIA_MM / 2.0 - INSTALLED_BORE_AXIS_OFFSET_MM
)
SET_SCREW_END_RADIUS = SET_SCREW_SEAT_RADIUS + SET_SCREW_LENGTH
TAP_DRILL_DEPTH = 7.6
TAP_FULL_DEPTH = 6.8
TAP_DRILL_DIA = TAP_DRILL_MM[SET_SCREW_THREAD]
TAP_DEPTH_PRECISION = 2
SET_SCREW_HOLE = HoleSpec(
    "tapped", SET_SCREW_THREAD, end="blind", depth_mm=TAP_DRILL_DEPTH,
    overrides_mm={"ThreadDepth": TAP_FULL_DEPTH},
)
# Internal 2B has no standard root MAX. This is an explicit manufacturing
# limit, authored as a native MAX gauge diameter and printed beside the tap.
# Book its rounded PRINTED maximum, not an invented ASME major maximum.
THREAD_ENVELOPE_DIA = math.ceil((
    0.0772 * IN + 0.64951905 * SET_SCREW_PITCH + 0.10
) * 100.0) / 100.0
TAP_POSITION_DIA_MM = TIP_SCREW_POSITION_DIA_MM
TAP_POSITION_RADIUS_MM = TAP_POSITION_DIA_MM / 2.0
# The smallest shop-readable custom body that retains the SAME 2.0 wall
# target at every full printed/process limit. No band/floor/tap/flat change:
# removing excess outside material buys real all-state air, not a fake tight
# shaft-motion inspection or a new thrust boss/operating mechanism.
BODY_RADIUS_REQUIREMENTS_MM = {
    "round bore wall": BORE_FINISHED_DIA_LIMITS_MM[1]/2.0 + 2.0*EDGE_BREAK + WALL_TARGET_MM,
    "tap to flat side rims": math.hypot(
        FLAT_DISTANCE+ROUTINE_BAND_MM,
        WALL_TARGET_MM+THREAD_ENVELOPE_DIA/2.0+EDGE_BREAK+TAP_POSITION_RADIUS_MM,
    ),
    "blind drill to opposite OD": (
        WALL_TARGET_MM-FLAT_DISTANCE+ROUTINE_BAND_MM
        + TAP_DRILL_DEPTH+ROUTINE_BAND_MM
        + TAP_DRILL_DIA/2.0*DRILL_POINT_H+TAP_POSITION_RADIUS_MM
    ),
}
OUTER_DIA = math.ceil((2.0*max(BODY_RADIUS_REQUIREMENTS_MM.values())+ROUTINE_BAND_MM)*100.0)/100.0
COLLAR_DATUMS = (
    PartDatum("A", CylinderFace(BORE_MODEL_DIA_MM, contains_y_mm=1.0, tolerance_mm=0.01)),
    PartDatum("B", PlanarFace((0.0, -1.0, 0.0), 0.0)),
    PartDatum("C", PlanarFace((1.0, 0.0, 0.0), FLAT_DISTANCE)),
)
COLLAR_CONTROLS = (
    GeometricControl(
        "radial_tap_position", "position", f"{TAP_POSITION_DIA_MM:.2f}",
        CylinderFace(TAP_DRILL_DIA, contains_x_mm=3.5, tolerance_mm=0.01),
        datums=("A", "B", "C"), tolerance_zone="diametral",
    ),
)
SCREW_DATUMS = (
    PartDatum("D", CylinderFace(
        SET_SCREW_MAJOR_DIA, contains_x_mm=SET_SCREW_SEAT_RADIUS + DOG_LENGTH + 1.0,
        tolerance_mm=0.01,
    )),
)
SCREW_CONTROLS = (
    GeometricControl(
        "ground_dog_runout", "total_runout", f"{TIP_SCREW_DOG_TOTAL_RUNOUT_MM:.2f}",
        CylinderFace(DOG_DIA, contains_x_mm=SET_SCREW_SEAT_RADIUS + DOG_LENGTH / 2.0,
                     tolerance_mm=0.005),
        datums=("D",),
    ),
)
PART_DATUMS = COLLAR_DATUMS + SCREW_DATUMS
GEOMETRIC_CONTROLS = COLLAR_CONTROLS + SCREW_CONTROLS

_BORE_MAX = BORE_FINISHED_DIA_LIMITS_MM[1]
_LAND_MIN = TERMINAL_FINISHED_DIA_LIMITS_MM[0]
_FLOAT_MAX = (_BORE_MAX - _LAND_MIN) / 2.0
_FLAT_MAX = TERMINAL_FINISHED_AF_LIMITS_MM[1] - _LAND_MIN / 2.0
_FLAT_MIN = TERMINAL_FINISHED_AF_LIMITS_MM[0] - TERMINAL_FINISHED_DIA_LIMITS_MM[1] / 2.0
DOG_SIDE_MARGIN_MM = (
    TERMINAL_HALF_CHORD_MIN_MM - TIP_SCREW_DOG_PROJECTED_RADIUS_MM
    - _FLOAT_MAX - TIP_SCREW_DOG_AXIS_OFFSET_MM - TERMINAL_FLAT_EDGE_BREAK_MAX
)
FREE_D_JOURNAL_OFFSET_MAX_MM = math.sqrt(
    (_BORE_MAX / 2.0)**2 - (_LAND_MIN / 2.0)**2
)
NATIVE_CONTACT_RESOLUTION_MM = 1e-5  # metrology roundoff, not a printed fit grade.


@dataclass(frozen=True)
class BackArcWitness:
    """Finite native face points in the SHAFT frame: +X flat, +Y north."""

    shaft_point_mm: tuple[float, float, float]
    bore_point_mm: tuple[float, float, float]
    bore_axis_origin_mm: tuple[float, float, float]
    bore_axis_unit: tuple[float, float, float]
    shaft_radius_mm: float
    bore_radius_mm: float


def _vector(values, label):
    if values is None or len(values) != 3:
        raise ValueError(f"{label} requires three actual coordinates")
    result = tuple(float(value) for value in values)
    if not all(math.isfinite(value) for value in result):
        raise ValueError(f"{label} is non-finite")
    return result


def _dot(a, b):
    return sum(x * y for x, y in zip(a, b, strict=True))


def validate_installed_clamp_pose(
    *, back_arc_witnesses, dog_tip_centre_mm, dog_axis_to_socket,
    dog_radius_mm, flat_offset_mm, flat_half_chord_mm, flat_axial_limits_mm,
):
    """Signed two-ended static clamp and WHOLE dog law, never a free-D fit.

    ``BackArcWitness`` points must come from the actual finite native faces,
    not infinite cylinder equations. All coordinates use the shaft frame.
    The screw's axis points from dog to socket; its reaction on the collar is
    +X, so the bore reaction is on the retained -X arc. Two contact residuals
    alone cannot authorize the loaded law: size, sign, finite span, reaction,
    and complete dog projection are independently required.
    """
    if back_arc_witnesses is None or len(back_arc_witnesses) != 2:
        raise ValueError("installed collar requires both actual back-arc contact witnesses")
    dog = _vector(dog_tip_centre_mm, "dog tip centre")
    force = _vector(dog_axis_to_socket, "dog axis to socket")
    limits = tuple(float(value) for value in flat_axial_limits_mm)
    scalars = (dog_radius_mm, flat_offset_mm, flat_half_chord_mm, *limits)
    if (len(limits) != 2 or not all(math.isfinite(value) for value in scalars)
            or dog_radius_mm <= 0.0 or flat_half_chord_mm <= 0.0 or limits[1] <= limits[0]):
        raise ValueError("whole dog requires finite positive manufactured flat/point geometry")
    if abs(_dot(force, force) - 1.0) > 1e-9 or force[0] < math.cos(
        TIP_SCREW_TO_JOURNAL_MAX_AXIS_ANGLE_RAD
    ) - 1e-12:
        raise ValueError("installed dog load is missing or points away from the retained BACK arc")
    if not (DOG_DIA + DOG_DIA_BAND[1])/2.0-1e-9 <= dog_radius_mm <= (DOG_DIA + DOG_DIA_BAND[0])/2.0+1e-9:
        raise ValueError("actual complete dog leaves its retained ground-diameter limits")
    stations, offsets, residuals = [], [], []
    for witness in back_arc_witnesses:
        if not isinstance(witness, BackArcWitness):
            raise ValueError("loaded fit requires actual finite back-arc witnesses")
        point = _vector(witness.shaft_point_mm, "shaft back-arc point")
        bore_point = _vector(witness.bore_point_mm, "bore back-arc point")
        origin = _vector(witness.bore_axis_origin_mm, "bore axis origin")
        axis = _vector(witness.bore_axis_unit, "bore axis")
        radii = (witness.shaft_radius_mm, witness.bore_radius_mm)
        if (not all(math.isfinite(value) and value > 0.0 for value in radii)
                or abs(_dot(axis, axis) - 1.0) > 1e-9 or axis[1] <= 0.0):
            raise ValueError("back-arc witness has invalid actual cylinder sizes/axis")
        if (not TERMINAL_FINISHED_DIA_LIMITS_MM[0]/2.0-1e-9 <= witness.shaft_radius_mm <= TERMINAL_FINISHED_DIA_LIMITS_MM[1]/2.0+1e-9
                or not BORE_FINISHED_DIA_LIMITS_MM[0]/2.0-1e-9 <= witness.bore_radius_mm <= BORE_FINISHED_DIA_LIMITS_MM[1]/2.0+1e-9):
            raise ValueError("actual shaft/bore radii leave their retained finished limits")
        actual_af = flat_offset_mm + witness.shaft_radius_mm
        if not TERMINAL_FINISHED_AF_LIMITS_MM[0]-1e-9 <= actual_af <= TERMINAL_FINISHED_AF_LIMITS_MM[1]+1e-9:
            raise ValueError("actual dog contact leaves the retained terminal AF band")
        if flat_half_chord_mm > math.sqrt(witness.shaft_radius_mm**2-flat_offset_mm**2)+NATIVE_CONTACT_RESOLUTION_MM:
            raise ValueError("claimed whole-dog half chord exceeds the actual retained D circle")
        gap = witness.bore_radius_mm - witness.shaft_radius_mm
        if not TIP_COLLAR_MIN_RADIAL_FLOAT_MM - 1e-9 <= gap <= TIP_COLLAR_MAX_RADIAL_FLOAT_MM + 1e-9:
            raise ValueError("actual collar/shaft size leaves the retained ROUND free-fit class")
        radial = math.hypot(point[0], point[2])
        if (abs(radial - witness.shaft_radius_mm) > NATIVE_CONTACT_RESOLUTION_MM
                or point[0] >= 0.0
                or -point[0] / radial < math.cos(TIP_COLLAR_BACK_ARC_REACTION_ANGLE_RAD) - 1e-9):
            raise ValueError("contact is not on the signed retained round BACK arc")
        delta = tuple(bore_point[k] - origin[k] for k in range(3))
        along = _dot(delta, axis)
        bore_radial = tuple(delta[k] - along * axis[k] for k in range(3))
        if abs(math.sqrt(_dot(bore_radial, bore_radial)) - witness.bore_radius_mm) > NATIVE_CONTACT_RESOLUTION_MM:
            raise ValueError("back-arc contact is not on the actual cylindrical bore")
        residual = math.sqrt(sum((point[k] - bore_point[k])**2 for k in range(3)))
        if residual > NATIVE_CONTACT_RESOLUTION_MM:
            raise ValueError("installed collar is not seated at both finite bore ends")
        intercept = (point[1] - origin[1]) / axis[1]
        centre = tuple(origin[k] + intercept * axis[k] for k in range(3))
        offset = (centre[0], centre[2])
        magnitude = math.hypot(*offset)
        if (offset[0] <= 0.0 or magnitude > TIP_COLLAR_MAX_RADIAL_FLOAT_MM + NATIVE_CONTACT_RESOLUTION_MM
                or offset[0] / magnitude < math.cos(TIP_COLLAR_BACK_ARC_REACTION_ANGLE_RAD) - 1e-9):
            raise ValueError("loaded collar is concentric or seats toward the removed D-flat")
        stations.append(point[1])
        offsets.append(offset)
        residuals.append(residual)
    south, north = stations
    span = north - south
    if span < TIP_COLLAR_MIN_CONTACT_SPAN_MM*math.cos(TIP_COLLAR_INSTALLED_COCK_ANGLE_RAD) - NATIVE_CONTACT_RESOLUTION_MM:
        raise ValueError("loaded collar witnesses do not bracket the full retained bearing span")
    cock = math.atan(math.dist(offsets[0], offsets[1]) / span)
    if cock > TIP_COLLAR_INSTALLED_COCK_ANGLE_RAD + 1e-9:
        raise ValueError("actual two-end loaded collar cock exceeds its source law")
    # Signed beam statics, normalized by the positive transverse clamp force.
    # Axial force couples through the actual dog-point lever; neither end may
    # change sign. Axial friction retention remains the existing joint class.
    location = dog[1] - south
    # BACK-arc axial reaction is not at x=0. For either possible distribution
    # of its axial reaction across the two ends, retain the worst signed
    # dog-to-actual-contact lever. Both extreme allocations must seat.
    reactions = tuple(
        (location * force[0] - (dog[0] - witness.shaft_point_mm[0]) * force[1]) / (span * force[0])
        for witness in back_arc_witnesses
    )
    north_reaction = min(reactions)
    south_reaction = 1.0 - max(reactions)
    if min(south_reaction, north_reaction) <= 0.0:
        raise ValueError("dog force cannot positively seat both finite BACK-arc ends")
    projected = dog_radius_mm / force[0]
    tip_plane_residual = abs(dog[0] - flat_offset_mm) - dog_radius_mm * math.sqrt(
        max(0.0, 1.0 - force[0]**2)
    )
    side_margin = flat_half_chord_mm - TERMINAL_FLAT_EDGE_BREAK_MAX - abs(dog[2]) - projected
    end_margin = min(dog[1] - limits[0], limits[1] - dog[1]) - projected
    if tip_plane_residual > NATIVE_CONTACT_RESOLUTION_MM or min(side_margin, end_margin) <= 0.0:
        raise ValueError("actual WHOLE dog misses the finite unbroken terminal flat")
    return {
        "loaded_radial_float_mm": TIP_COLLAR_MAX_RADIAL_FLOAT_MM,
        "loaded_cock_angle_rad": cock,
        "back_arc_residuals_mm": tuple(residuals),
        "back_arc_offsets_mm": tuple(offsets),
        "positive_end_reactions": (south_reaction, north_reaction),
        "whole_dog_side_margin_mm": side_margin,
        "whole_dog_end_margin_mm": end_margin,
        "loose_d_journal_offset_mm": FREE_D_JOURNAL_OFFSET_MAX_MM,
    }


_OD_MIN_R = (OUTER_DIA - ROUTINE_BAND_MM) / 2.0
_THREAD_R = THREAD_ENVELOPE_DIA / 2.0
WORST_WALLS_MM = {
    "bore to round OD": _OD_MIN_R - _BORE_MAX / 2.0 - 2.0 * EDGE_BREAK,
    "nose bore to round OD": (NOSE_DIA - ROUTINE_BAND_MM) / 2.0
        - _BORE_MAX / 2.0 - 2.0 * EDGE_BREAK,
    "bore to mounting flat": FLAT_DISTANCE - ROUTINE_BAND_MM - _BORE_MAX / 2.0
        - 2.0 * EDGE_BREAK,
    # BASIC is from the south datum, not half the actual loose width.
    # Both the shoulder and north face move independently on their .XX bands.
    "tap to south shoulder": TAP_STATION - NOSE_LENGTH - ROUTINE_BAND_MM
        - _THREAD_R - EDGE_BREAK - TAP_POSITION_RADIUS_MM,
    "tap to north face": WIDTH - WIDTH_BAND_MM - TAP_STATION
        - _THREAD_R - EDGE_BREAK - TAP_POSITION_RADIUS_MM,
    "tap to flat side rims": math.sqrt(_OD_MIN_R**2 - (FLAT_DISTANCE + ROUTINE_BAND_MM)**2)
        - _THREAD_R - EDGE_BREAK - TAP_POSITION_RADIUS_MM,
    "blind drill to opposite OD": _OD_MIN_R + FLAT_DISTANCE - ROUTINE_BAND_MM
        - TAP_DRILL_DEPTH - ROUTINE_BAND_MM
        - TAP_DRILL_DIA / 2.0 * DRILL_POINT_H - TAP_POSITION_RADIUS_MM,
}
# Full male and female thread overlap, not nominal wall thickness. One pitch
# at each thread end and the receiver's mouth break are deducted separately.
_MALE_FULL_START_MAX = (
    _FLAT_MAX + _FLOAT_MAX + DOG_LENGTH + ROUTINE_BAND_MM + SET_SCREW_PITCH
    + TIP_SCREW_MAJOR_AXIAL_PROJECTION_MM + TIP_SCREW_DOG_AXIAL_PROJECTION_MM
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
    * (1.0 - math.cos(TIP_SCREW_MAX_AXIS_ANGLE_RAD))
    + TIP_SCREW_MAJOR_AXIAL_PROJECTION_MM
)
_STOCK_POINT_CHAMFER_MAX_MM = (
    (SET_SCREW_MAJOR_DIA - SET_SCREW_FACTORY_POINT_MIN_DIA) / 2.0
    / math.tan(math.radians(SET_SCREW_FACTORY_POINT_MIN_ANGLE_DEG))
)
_MALE_FULL_END_MIN = (
    _FLAT_MIN - _FLOAT_MAX + SET_SCREW_LENGTH - SET_SCREW_LENGTH_BAND_MM
    - _STOCK_FACE_CHAMFER_MAX - SET_SCREW_PITCH
    - _STOCK_AXIAL_PROJECTION_LOSS_MM
)
_FEMALE_FULL_END_MIN = FLAT_DISTANCE - ROUTINE_BAND_MM - EDGE_BREAK - SET_SCREW_PITCH
_FEMALE_FULL_START_MAX = (
    FLAT_DISTANCE + ROUTINE_BAND_MM - TAP_FULL_DEPTH + ROUTINE_BAND_MM
    + SET_SCREW_PITCH
)
WORST_FULL_ENGAGEMENT_MM = min(_FEMALE_FULL_END_MIN, _MALE_FULL_END_MIN) - max(
    _MALE_FULL_START_MAX, _FEMALE_FULL_START_MAX,
)
REQUIRED_FULL_ENGAGEMENT_MM = TIP_SCREW_REQUIRED_FULL_ENGAGEMENT_MM
WORST_SOCKET_ACCESS_MM = (
    _FLAT_MIN - _FLOAT_MAX + SET_SCREW_LENGTH - SET_SCREW_LENGTH_BAND_MM
    - FLAT_DISTANCE - ROUTINE_BAND_MM
    - _STOCK_AXIAL_PROJECTION_LOSS_MM
)
ROTATING_ENVELOPE_RADIUS_MM = max(
    (OUTER_DIA + ROUTINE_BAND_MM) / 2.0,
    math.hypot(
        _FLAT_MAX + _FLOAT_MAX + SET_SCREW_LENGTH + SET_SCREW_LENGTH_BAND_MM,
        SET_SCREW_MAJOR_DIA / 2.0 + TIP_SCREW_POSITION_DIA_MM / 2.0
        + SET_SCREW_LENGTH * math.sin(TIP_SCREW_MAX_AXIS_ANGLE_RAD),
    ),
)
if min(WORST_WALLS_MM.values()) < WALL_TARGET_MM:
    raise AssertionError(f"custom collar misses the wall target: {WORST_WALLS_MM}")
if WORST_FULL_ENGAGEMENT_MM < REQUIRED_FULL_ENGAGEMENT_MM:
    raise AssertionError("custom collar set screw has less than 1.5D full thread")
if abs(_FLOAT_MAX - TIP_COLLAR_MAX_RADIAL_FLOAT_MM) > 1e-12:
    raise AssertionError("collar bore and authoritative journal retention fit diverged")
if DOG_LENGTH - ROUTINE_BAND_MM < _STOCK_POINT_CHAMFER_MAX_MM:
    raise AssertionError("ground dog shoulder would require adding material to the factory point")
if DOG_SIDE_MARGIN_MM <= 0.0 or WORST_SOCKET_ACCESS_MM <= 0.0:
    raise AssertionError("complete dog fit/position budget fails or socket is buried")

DRAWING_NOTES = "\n".join((
    "COLLAR: 3/4 STEEL BAR STOCK OK.",
    "SUPPLY MCMASTER 94355A213; RETAIN STOCK THREAD AND HEX.",
    "GROUND DOG TIP; BREAK TIP EDGE ONLY AS DIMENSIONED.",
    "DATUM D: RETAINED STOCK THREAD AXIS.",
))
INSTALLATION_NOTES = "\n".join((
    "SET ASSEMBLY FEELER OFF T006 THRUST FACE.",
    "SEAT BOTH ENDS ON JOURNAL ROUND BACK ARC.",
    "SNUG DOG ON D-FLAT, THEN REMOVE LEAF.",
    "DO NOT SWING OR RUN WITH COLLAR LOOSE.",
))
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 2:1"
RADIAL_TAP_VIEW_SCALE = (2, 1)
BORE_VIEW_SCALE = (40, 1)
BORE_VIEW_NOTE = f"BORE VIEW SCALE {BORE_VIEW_SCALE[0]}:{BORE_VIEW_SCALE[1]}"
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
    "SetScrewProfile": {"DogDia", "DogLength"},
}
DRAWING_PRECISION = {
    "RingProfile": {"NoseDia": 2, "BoreDia": TERMINAL_DIA_PLACES},
    "BodyProfile": {"CollarDia": 2, "NoseLength": 2},
    "ShoulderRoot": {"ShoulderRadius": 2},
    "Ring": {"CollarWidth": 2},
    "MountFlatProfile": {"FlatDistance": 2},
    "SetScrewTap": {"TapStation": 2},
    "TapRootGauge": {"TapRootLimit": 2},
    "SetScrewProfile": {"DogDia": 2, "DogLength": 2},
}
DRAWING_PRECISION_BY_NAME = {
    name: places for names in DRAWING_PRECISION.values() for name, places in names.items()
}
