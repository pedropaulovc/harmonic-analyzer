"""Two fillister screws seat MHA-MG-01 on MHA-SM-03's front face.

Pure joint geometry depends on the shared sm_summing_lever_spec geometry;
no assembly or COM imports enter either part recipe. Machine seat coordinates
are pinned to the live summing installation by the offline contract and the
magnifier assembly. Photo stations: ch30 page002_img01 front view and
ch20 page001_img01, top-right close-up.
"""

from __future__ import annotations

import math

from _hole_spec import DRILL_POINT_H, HoleSpec, blind_cut_dia_mm
from _inch_wall_limits import WALL_TARGET_MM
from _printed_tolerance import (
    drilled_oversize_mm,
    edge_break_chamfer_mm,
    printed_band_mm,
    printed_deviations,
)
from mg_magnifying_bracket_spec import DRAWING_PRECISION, FOOT_GRIP_TOL
from mg_lever_thread_joint import NOSE_R
import sm_summing_lever_spec as lever

SCREW_SKU = "91794A078"
SCREW_THREAD = "#2-56"
# Main ruling 2026-10-16, option (i): 18-8 stainless 5/16 with the heads on
# the flange's front face (no counterbore).  The heads were already 18-8
# stainless; brass 90114A #2-56 has no 5/16, and its 3/8 with a 3/16 flange
# kept only a 1.04 shank-shear margin (66.05 vs 68.9 MPa at 50 ksi).
SCREW_LENGTH = 7.9375  # McMaster 91794A078, under-head 5/16 in
SCREW_MAJOR_DIA = 2.1844
SCREW_HEAD_DIA = 3.556
SCREW_HEAD_HEIGHT = 2.1082
SCREW_PITCH = 25.4 / 56.0

BRACKET_ORIGIN = (40.0, 979.7, -173.51)  # threaded nose in the drum's wire lane
LEVER_ORIGIN_X = -15.0
LEVER_FRONT_LOCAL_Z = -76.2
SEAT_PLANE_Z = -73.11241221957347
SIDE_PLATE_THICKNESS = 3.175
SIDE_PLATE_HEIGHT = 2.0 * NOSE_R  # owner: match neck width; no lateral root ledge
SIDE_PLATE_MACHINE_X = (-8.0, 46.25)  # user-approved +5 free end; mounts/neck stay fixed
# Physical acceptance follows the printed rounded size, not the hidden nominal.
SIDE_PLATE_LENGTH_DEVIATIONS = printed_deviations(
    SIDE_PLATE_MACHINE_X[1] - SIDE_PLATE_MACHINE_X[0],
    DRAWING_PRECISION["FlangeProfile"]["FlangeWidth"],
)
SIDE_PLATE_HEIGHT_DEVIATIONS = printed_deviations(
    SIDE_PLATE_HEIGHT, DRAWING_PRECISION["Flange"]["FlangeHeight"],
)
SIDE_PLATE_X = tuple(x - BRACKET_ORIGIN[0] for x in SIDE_PLATE_MACHINE_X)
SIDE_PLATE_Y = (-SIDE_PLATE_HEIGHT / 2.0, SIDE_PLATE_HEIGHT / 2.0)
SIDE_PLATE_FRONT_Z = SEAT_PLANE_Z - SIDE_PLATE_THICKNESS
SIDE_PLATE_Z = (
    SIDE_PLATE_FRONT_Z - BRACKET_ORIGIN[2],
    SEAT_PLANE_Z - BRACKET_ORIGIN[2],
)
SCREW_MACHINE_X = (1.0, 14.7)
# Both mating rows move together; the L body, seat and threaded nose do not.
# Receiver location is measured from the actual coefficient-plate top face.
RECEIVER_ROW_FROM_TOP = 3.25
RECEIVER_ROW_Y = lever.COEFFICIENT_TOP_Y - RECEIVER_ROW_FROM_TOP
SCREW_PITCH_X = SCREW_MACHINE_X[1] - SCREW_MACHINE_X[0]
BRACKET_HOLE_POINTS = tuple(
    (x - BRACKET_ORIGIN[0], RECEIVER_ROW_Y, SIDE_PLATE_Z[0]) for x in SCREW_MACHINE_X
)
LEVER_HOLE_POINTS = tuple(
    (x - LEVER_ORIGIN_X, RECEIVER_ROW_Y, LEVER_FRONT_LOCAL_Z) for x in SCREW_MACHINE_X
)
# A flush head would run this screw past the tap's full thread and bottom it.
# The heads instead bear on the flange's front face, no counterbore, inside a
# head-clearance circle (still named COUNTERBORE_DIA) that keeps their float.
COUNTERBORE_DIA = 3.8  # no counterbore: the head-clearance circle of the wall asserts
COUNTERBORE_DEPTH = 0.0  # no counterbore
CLEARANCE_SPEC = HoleSpec("clearance", "#2", fit="normal")
CLEARANCE_DIA = blind_cut_dia_mm(CLEARANCE_SPEC)
SCREW_POSITIONS = tuple(
    (x, BRACKET_ORIGIN[1] + RECEIVER_ROW_Y, SIDE_PLATE_FRONT_Z) for x in SCREW_MACHINE_X
)
# The heads bear on the flange's front face, wholly proud of it.
GRIP = SIDE_PLATE_THICKNESS
ENGAGEMENT = SCREW_LENGTH - GRIP
HEAD_PROTRUSION = SCREW_HEAD_HEIGHT
# Explicit native 3.175 +/-0.13 preserves the accepted screw-grip interval.
FLANGE_THICKNESS_BAND = FOOT_GRIP_TOL

# The receiver continues from the uniform 5.08 mm entry rib into the connected
# 7 mm coefficient plate. Neither usable thread nor the drill point is required
# to stop inside the rib. Ordinary printed depths remain independently bounded.
# #290: the receiver taps and coordinates print on the lever's decimal-inch
# sheet (lever.UNIT); the bracket's own bands (LINEAR_BAND, the drilled
# clearance) stay on its millimetre sheet.  The full-thread and coordinate
# bands are +/-.002 in, the nearest exact inch decimals to the former 0.05 mm.
THREAD_DEPTH_BAND = 0.0508  # native metadata only; the drawing prints .195 MIN
LINEAR_BAND = printed_band_mm(2)  # PRINTED title-block .XX band, not the unrounded .02 in
POSITION_BAND = 0.0508
DRILLED_DIAMETER_PLUS = drilled_oversize_mm()
# The lever sheet prints the receiver tap drill's diameter at three places
# (its drilled-hole row sizes the pilot) but the routine tap-drill depth at
# two (rule 3: .26 +/-.01; no function asks for more, rule 4).  The depth's
# acceptance follows its printed rounded value.
RECEIVER_HOLE_PLACES = 3
RECEIVER_DRILL_DEPTH_PLACES = 2
RECEIVER_DRILLED_DIAMETER_PLUS = drilled_oversize_mm(unit=lever.UNIT)
DRILL_DEPTH_BAND = printed_band_mm(RECEIVER_DRILL_DEPTH_PLACES, unit=lever.UNIT)
# Engineering floor for the printed pilot, not the finished thread cavity:
# the lever's rule-17 wall target on its inch sheet.
RECEIVER_PILOT_WALL_MIN = WALL_TARGET_MM
HEAD_FLOAT_MIN = (COUNTERBORE_DIA - SCREW_HEAD_DIA) / 2.0
HEAD_POSITION_MISMATCH_MAX = 2.0 * POSITION_BAND
EDGE_BREAK = edge_break_chamfer_mm()
SCREW_LENGTH_MINUS = 0.76  # conservative stock allowance, not a catalog band
SCREW_TIP_CHAMFER = 0.7 * SCREW_PITCH
GRIP_BAND = FLANGE_THICKNESS_BAND
GRIP_MIN = GRIP - GRIP_BAND
ENGAGEMENT_MIN = (
    ENGAGEMENT - SCREW_LENGTH_MINUS - GRIP_BAND - SCREW_TIP_CHAMFER - EDGE_BREAK
)
SCREW_REACH_MAX = ENGAGEMENT + GRIP_BAND
THREAD_DEPTH = 4.95
DRILL_DEPTH = 6.604  # .26 in, on its printed grid (rule 3)
DRILL_DEPTH_DEVIATIONS = printed_deviations(  # (lower, upper), mm
    DRILL_DEPTH, RECEIVER_DRILL_DEPTH_PLACES, unit=lever.UNIT,
)
DRILL_DEPTH_MIN = DRILL_DEPTH + DRILL_DEPTH_DEVIATIONS[0]
DRILL_DEPTH_MAX = DRILL_DEPTH + DRILL_DEPTH_DEVIATIONS[1]
TAP_SPEC = HoleSpec(
    "tapped_bottoming",
    SCREW_THREAD,
    end="blind",
    depth_mm=DRILL_DEPTH,
    thread_class="2B",
    overrides_mm={"ThreadDepth": THREAD_DEPTH},
)
TAP_DRILL_DIA = blind_cut_dia_mm(TAP_SPEC)


def receiver_pilot_radius_max() -> float:
    """The larger native/printed pilot radius plus its drilled-hole row: the
    radius for every point/wander/material budget."""
    printed_over = printed_deviations(
        TAP_DRILL_DIA, RECEIVER_HOLE_PLACES, (0.0, 0.0), unit=lever.UNIT,
    )[1]
    return (
        TAP_DRILL_DIA + max(0.0, printed_over) + RECEIVER_DRILLED_DIAMETER_PLUS
    ) / 2.0


RECEIVER_PILOT_RADIUS_MAX = receiver_pilot_radius_max()
DRILL_POINT_DEPTH = TAP_DRILL_DIA / 2.0 * DRILL_POINT_H
DRILL_POINT_DEPTH_MAX = RECEIVER_PILOT_RADIUS_MAX * DRILL_POINT_H
SCREW_TIP_GAP_MIN = THREAD_DEPTH - THREAD_DEPTH_BAND - SCREW_REACH_MAX
TAP_LEAD_MARGIN_MIN = (
    DRILL_DEPTH_MIN - THREAD_DEPTH - THREAD_DEPTH_BAND - 2.0 * SCREW_PITCH
)
# Lateral pilot drift at its deepest reach (fr_top_frame_spec's 0.3 deg
# realistic wander, kept local to avoid adding that spec to the shared pure
# geometry dependency).
DRILL_WANDER_DEG = 0.3
DRILL_WANDER_MAX = math.tan(math.radians(DRILL_WANDER_DEG)) * (
    DRILL_DEPTH_MAX + DRILL_POINT_DEPTH_MAX
)
COUNTERBORE_END_WALL_MIN = min(
    min(SCREW_MACHINE_X) - SIDE_PLATE_MACHINE_X[0] - POSITION_BAND,
    SIDE_PLATE_MACHINE_X[1] - SIDE_PLATE_MACHINE_X[0]
    + SIDE_PLATE_LENGTH_DEVIATIONS[0]
    - (max(SCREW_MACHINE_X) - SIDE_PLATE_MACHINE_X[0]) - POSITION_BAND,
) - (COUNTERBORE_DIA + DRILLED_DIAMETER_PLUS) / 2.0
# Charge BOTH real flange edges: the relocated row is no longer centred.
COUNTERBORE_HEIGHT_WALL_MIN = min(
    min(
        SIDE_PLATE_HEIGHT + SIDE_PLATE_HEIGHT_DEVIATIONS[0]
        - (y - SIDE_PLATE_Y[0]) - POSITION_BAND,
        y - SIDE_PLATE_Y[0] - POSITION_BAND,
    )
    - (COUNTERBORE_DIA + DRILLED_DIAMETER_PLUS) / 2.0
    for _x, y, _z in BRACKET_HOLE_POINTS
)
# The actual clearance hole follows the printed DRILLED HOLES +0.10/0 row.
# Keep this distinct from the larger conservative screw-head clearance circle.
CLEARANCE_HOLE_RADIUS_MAX = (
    round(CLEARANCE_DIA, 2) + DRILLED_DIAMETER_PLUS
) / 2.0
CLEARANCE_HOLE_HEIGHT_WALL_MIN = min(
    min(
        SIDE_PLATE_HEIGHT + SIDE_PLATE_HEIGHT_DEVIATIONS[0]
        - (y - SIDE_PLATE_Y[0]) - POSITION_BAND,
        y - SIDE_PLATE_Y[0] - POSITION_BAND,
    ) - CLEARANCE_HOLE_RADIUS_MAX
    for _x, y, _z in BRACKET_HOLE_POINTS
)



def receiver_material_wall_margin(
    rib_depth_min: float,
    face_from_axis_min: float,
    cylinder_depth_max: float,
    radius_max: float,
    point_height_ratio: float,
    wander_max: float,
) -> float:
    """Pilot cylinder/cone to the connected plate/rib's inward transition.

    In an axial/radial section the excluded quadrant begins at
    (rib_depth_min, face_from_axis_min). The finite rib extends to that depth;
    the plate continues underneath it. Omitting the concave root can only
    remove material. Once the cylinder reaches beyond the rib, the nearest
    boundary is the actual plate plane, NOT an invented rib end wall.

    Otherwise minimize distance to the excluded quadrant along the finite cone.
    Its radius contracts by u while its depth advances by point_height_ratio*u.
    Endpoints, the two quadrant boundaries and the unconstrained perpendicular
    foot cover every piece of this convex, piecewise-quadratic distance.
    Subtract the entire deepest drill wander once as a Euclidean displacement.
    This is a pilot-only material screen, not a finished-thread or strength proof.
    """
    values = (
        rib_depth_min, face_from_axis_min, cylinder_depth_max, radius_max,
        point_height_ratio, wander_max,
    )
    if not all(math.isfinite(value) and value >= 0.0 for value in values):
        raise ValueError("receiver material geometry requires finite nonnegative inputs")
    a = rib_depth_min - cylinder_depth_max
    b = face_from_axis_min - radius_max
    if a <= 0.0:
        return b - wander_max
    k = point_height_ratio
    candidates = [0.0, radius_max, (k * a - b) / (1.0 + k * k), -b]
    if k:
        candidates.append(a / k)
    return min(
        math.hypot(max(a - k * u, 0.0), max(b + u, 0.0))
        for candidate in candidates
        for u in (min(radius_max, max(0.0, candidate)),)
    ) - wander_max


def receiver_pilot_material_wall_budget() -> float:
    """Worst pilot wall through the actual connected plate/rib material.

    The row is from the ACTUAL top, so a rigid top-position shift cancels.
    Thickness and row-location bands remain independent. The sharp transition
    excludes the root fillet; the plate's free edge and opposite end are also
    real boundaries. Rib, plate thickness and plate length take the lever
    sheet's printed limits (``lever.*_DEVIATIONS``).
    The entry plane is intentionally open: depths start at that actual face.
    Longitudinal rib flank walls are screened separately by the pure profile.
    No internal-major limit, cavity envelope or tighter depth band is assumed.
    """
    radius = receiver_pilot_radius_max()
    point_depth = radius * DRILL_POINT_H
    wander = math.tan(math.radians(DRILL_WANDER_DEG)) * (
        DRILL_DEPTH_MAX + point_depth
    )
    return min(
        min(
            *(
                receiver_material_wall_margin(
                    lever.RIB_T + lever.RIB_T_DEVIATIONS[0], face, DRILL_DEPTH_MAX,
                    radius, DRILL_POINT_H, wander,
                )
                for face in (
                    lever.COEFFICIENT_TOP_Y - y - POSITION_BAND,
                    lever.COEFFICIENT_T + lever.COEFFICIENT_T_DEVIATIONS[0]
                    - (lever.COEFFICIENT_TOP_Y - y) - POSITION_BAND,
                )
            ),
            lever.PLATE_W - x - POSITION_BAND - radius - wander,
            lever.PLATE_L + lever.PLATE_L_DEVIATIONS[0]
            - DRILL_DEPTH_MAX - point_depth - wander,
        )
        for x, y, _z in LEVER_HOLE_POINTS
    )


if ENGAGEMENT_MIN < 1.5 * SCREW_MAJOR_DIA:
    raise AssertionError("magnifying bracket screw loses 1.5D full engagement")
if SCREW_TIP_GAP_MIN <= 0.0:
    raise AssertionError("magnifying bracket screw bottoms in its full-thread seat")
if TAP_LEAD_MARGIN_MIN < 0.0:
    raise AssertionError("magnifying bracket tap drill loses bottoming-tap lead design allowance")
if HEAD_FLOAT_MIN < HEAD_POSITION_MISMATCH_MAX:
    raise AssertionError("magnifying bracket counterbore loses head float")
if min(
    GRIP_MIN, COUNTERBORE_END_WALL_MIN, COUNTERBORE_HEIGHT_WALL_MIN,
    CLEARANCE_HOLE_HEIGHT_WALL_MIN,
) < 1.5:
    raise AssertionError("magnifying bracket joint loses a drawing-guidelines.md rule 17 (walls and webs) wall")

RECEIVER_PILOT_MATERIAL_WALL_MIN = receiver_pilot_material_wall_budget()
if RECEIVER_PILOT_MATERIAL_WALL_MIN < RECEIVER_PILOT_WALL_MIN:
    raise AssertionError(
        f"magnifying bracket receiver pilot material wall {RECEIVER_PILOT_MATERIAL_WALL_MIN:.6f} mm "
        f"is below the {RECEIVER_PILOT_WALL_MIN:g} mm pilot floor"
    )
