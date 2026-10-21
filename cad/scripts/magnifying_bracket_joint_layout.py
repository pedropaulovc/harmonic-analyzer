"""Two fillister screws seat MHA-MG-01 on MHA-SM-03's front face.

Pure joint data: no assembly or COM imports enter either part recipe. Machine
seat coordinates are pinned to the live summing installation by the offline
contract and the magnifier assembly. Photo stations: ch30 page002_img01 front
view and ch20 page001_img01, top-right close-up.
"""

from __future__ import annotations

import math

from _hole_spec import DRILL_POINT_H, HoleSpec, blind_cut_dia_mm

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

BRACKET_ORIGIN = (40.0, 979.7, -173.51)  # A1: the collar in the drum's wire lane (#1559)
LEVER_ORIGIN_X = -15.0
LEVER_FRONT_LOCAL_Z = -76.2
SEAT_PLANE_Z = -73.11241221957347
SIDE_PLATE_THICKNESS = 3.175
SIDE_PLATE_HEIGHT = 12.7
SIDE_PLATE_MACHINE_X = (-3.0, 45.0)
SIDE_PLATE_X = tuple(x - BRACKET_ORIGIN[0] for x in SIDE_PLATE_MACHINE_X)
SIDE_PLATE_Y = (-SIDE_PLATE_HEIGHT / 2.0, SIDE_PLATE_HEIGHT / 2.0)
SIDE_PLATE_FRONT_Z = SEAT_PLANE_Z - SIDE_PLATE_THICKNESS
SIDE_PLATE_Z = (
    SIDE_PLATE_FRONT_Z - BRACKET_ORIGIN[2],
    SEAT_PLANE_Z - BRACKET_ORIGIN[2],
)
SCREW_MACHINE_X = (1.0, 14.7)
SCREW_PITCH_X = SCREW_MACHINE_X[1] - SCREW_MACHINE_X[0]
BRACKET_HOLE_POINTS = tuple(
    (x - BRACKET_ORIGIN[0], 0.0, SIDE_PLATE_Z[0]) for x in SCREW_MACHINE_X
)
LEVER_HOLE_POINTS = tuple(
    (x - LEVER_ORIGIN_X, 0.0, LEVER_FRONT_LOCAL_Z) for x in SCREW_MACHINE_X
)
# A flush head would run this screw past the tap's full thread and bottom it.
# The heads instead bear on the flange's front face, no counterbore, inside a
# head-clearance circle (still named COUNTERBORE_DIA) that keeps their float.
COUNTERBORE_DIA = 3.8  # no counterbore: the head-clearance circle of the wall asserts
COUNTERBORE_DEPTH = 0.0  # no counterbore
CLEARANCE_SPEC = HoleSpec("clearance", "#2", fit="normal")
CLEARANCE_DIA = blind_cut_dia_mm(CLEARANCE_SPEC)
SCREW_POSITIONS = tuple(
    (x, BRACKET_ORIGIN[1], SIDE_PLATE_FRONT_Z) for x in SCREW_MACHINE_X
)
# The heads bear on the flange's front face, wholly proud of it.
GRIP = SIDE_PLATE_THICKNESS
ENGAGEMENT = SCREW_LENGTH - GRIP
HEAD_PROTRUSION = SCREW_HEAD_HEIGHT
# The flange prints 3.175 unbanded: the title block's .XXX band holds the grip.
FLANGE_THICKNESS_BAND = 0.13

# Owner selected 2026-10-20: preserve the existing rib profiles and extend only
# the -Z receiver inward to 9.40 +/-0.51, retaining its front entry and both
# hole axes. The opposite end rib remains 5.08 deep. This geometry is retained,
# but the selection relied on a thread-root bound that 2B does not establish;
# production wall approval remains pending the owner's tap/process decision.
# The unchanged cylindrical drill takes the ordinary title-block .XX band,
# including two pitches of tap lead, its whole point, and drill wander.
PLATE_THICKNESS_BAND = 0.05
COUNTERBORE_DEPTH_BAND = 0.05
THREAD_DEPTH_BAND = 0.05
LINEAR_BAND = 0.51  # PRINTED title-block .XX band, not the unrounded .02 in
# A bounded ordinary band is still necessary: an unlimited MIN depth could
# run the drill beyond any finite rib into the unbacked 5.08 plate.
DRILL_DEPTH_DEVIATIONS = (-LINEAR_BAND, LINEAR_BAND)  # (lower, upper), mm
RIB_DEPTH = 9.4
POSITION_BAND = 0.05
DRILLED_DIAMETER_PLUS = 0.10
RIB_DEPTH_BAND = LINEAR_BAND  # the title block's: the rib takes no native band
LEVER_PLATE_THICKNESS = 5.08
LEVER_PLATE_THICKNESS_BAND = LINEAR_BAND
RECEIVER_ROW_FROM_TOP = 2.54
RECEIVER_ROW_BAND = POSITION_BAND
LOCAL_WALL_HARD_FLOOR = 1.5
RECEIVER_NOTCH_WALL_REQUIRED = 2.0
HEAD_FLOAT_MIN = (COUNTERBORE_DIA - SCREW_HEAD_DIA) / 2.0
HEAD_POSITION_MISMATCH_MAX = 2.0 * POSITION_BAND
EDGE_BREAK = 0.25
SCREW_LENGTH_MINUS = 0.76  # conservative stock allowance, not a catalog band
SCREW_TIP_CHAMFER = 0.7 * SCREW_PITCH
GRIP_BAND = FLANGE_THICKNESS_BAND
GRIP_MIN = GRIP - GRIP_BAND
ENGAGEMENT_MIN = (
    ENGAGEMENT - SCREW_LENGTH_MINUS - GRIP_BAND - SCREW_TIP_CHAMFER - EDGE_BREAK
)
SCREW_REACH_MAX = ENGAGEMENT + GRIP_BAND
# Native full-thread geometry only: the printed MIN is not an upper bound on
# the physical axial extent of the actual thread.
THREAD_DEPTH = 4.95
DRILL_DEPTH = 6.50
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
# The native drill stays 1.778; its printed diameter governs worst-case stock.
TAP_DRILL_PRINTED_DIA = 1.78
TAP_DRILL_RADIUS_MAX = (TAP_DRILL_PRINTED_DIA + DRILLED_DIAMETER_PLUS) / 2.0
DRILL_POINT_DEPTH = TAP_DRILL_DIA / 2.0 * DRILL_POINT_H
DRILL_POINT_DEPTH_MAX = TAP_DRILL_RADIUS_MAX * DRILL_POINT_H
THREAD_RIB_MARGIN_MIN = RIB_DEPTH - RIB_DEPTH_BAND - THREAD_DEPTH - THREAD_DEPTH_BAND
SCREW_TIP_GAP_MIN = THREAD_DEPTH - THREAD_DEPTH_BAND - SCREW_REACH_MAX
TAP_LEAD_MARGIN_MIN = (
    DRILL_DEPTH_MIN - THREAD_DEPTH - THREAD_DEPTH_BAND - 2.0 * SCREW_PITCH
)
DRILL_POINT_RIB_MARGIN = RIB_DEPTH - DRILL_DEPTH - DRILL_POINT_DEPTH
# Lateral drift of the drill at its deepest reach (fr_top_frame_spec's 0.3
# deg realistic wander, restated so the joint stays a pure leaf module): the
# rib walls round the tap are judged with it.
DRILL_WANDER_DEG = 0.3
DRILL_WANDER_MAX = math.tan(math.radians(DRILL_WANDER_DEG)) * (
    DRILL_DEPTH_MAX + DRILL_POINT_DEPTH_MAX
)
# Axial point containment also charges the whole lateral wander as axial.
# This conservative margin keeps the point in the rib; it is not a bottom
# wall thickness, since the plate continues beyond the rib.
DRILL_POINT_RIB_MARGIN_MIN = (
    RIB_DEPTH - RIB_DEPTH_BAND - DRILL_DEPTH_MAX
    - DRILL_POINT_DEPTH_MAX - DRILL_WANDER_MAX
)

# Plate thickness and the top-referenced row are correlated: y_axis=P/2-H,
# y_bottom=-P/2, hence the underside distance is P-H, not P/2-H or a second
# half-thickness deduction. Both the receiver and drill share the entry face,
# so whole-part axial translation cancels from their local depth difference.
RECEIVER_LOWER_NOTCH_HEIGHT_MIN = (
    LEVER_PLATE_THICKNESS - LEVER_PLATE_THICKNESS_BAND
    - RECEIVER_ROW_FROM_TOP - RECEIVER_ROW_BAND
)
RECEIVER_UPPER_NOTCH_HEIGHT_MIN = RECEIVER_ROW_FROM_TOP - RECEIVER_ROW_BAND
RECEIVER_NOTCH_HEIGHT_MIN = min(
    RECEIVER_LOWER_NOTCH_HEIGHT_MIN, RECEIVER_UPPER_NOTCH_HEIGHT_MIN,
)
RECEIVER_NOTCH_AXIAL_GAP_MIN = RIB_DEPTH - RIB_DEPTH_BAND - DRILL_DEPTH_MAX


def cylindrical_notch_distance(
    axial_gap: float, axis_to_notch: float, radius: float,
) -> float:
    """Distance from a full cylinder to the external rib-cap/plate-face notch."""
    return math.hypot(max(axial_gap, 0.0), max(axis_to_notch - radius, 0.0))


def cone_notch_closest_advance(
    axial_gap: float, axis_to_notch: float, radius: float,
) -> float:
    """Closest cone advance from its shoulder, clamped to shoulder and tip."""
    radial_gap = axis_to_notch - radius
    slope = 1.0 / DRILL_POINT_H
    return min(
        max((axial_gap - slope * radial_gap) / (1.0 + slope**2), 0.0),
        radius * DRILL_POINT_H,
    )


def drill_notch_distance(
    axial_gap: float, axis_to_notch: float, radius: float,
) -> float:
    """Closest cylinder/cone distance to the sharp external notch, before wander.

    The notch comprises the plate-face ray beyond the receiver and the rear-cap
    ray outside the plate. It is not an underside plane inside the rib. Positive
    gaps put its nearest point at the corner; clamping also covers overlap with
    either ray. No credit is taken for an unspecified concave root radius.
    """
    advance = cone_notch_closest_advance(axial_gap, axis_to_notch, radius)
    cone_distance = math.hypot(
        max(axial_gap - advance, 0.0),
        max(axis_to_notch - radius + advance / DRILL_POINT_H, 0.0),
    )
    return min(
        cylindrical_notch_distance(axial_gap, axis_to_notch, radius),
        cone_distance,
    )


# Deduct the entire displacement budget once, in any direction. A lateral-only
# axis shift is a different model and must not be deducted a second time.
RECEIVER_DRILL_NOTCH_WALL_MIN = drill_notch_distance(
    RECEIVER_NOTCH_AXIAL_GAP_MIN, RECEIVER_NOTCH_HEIGHT_MIN, TAP_DRILL_RADIUS_MAX,
) - DRILL_WANDER_MAX
# Conditional analysis at the BASIC major diameter SCREW_MAJOR_DIA, over the
# entire bounded drill cylinder, not a minimum wall for the actual thread.
# ASME B1.1-2003 §§5.5/8.3.2 leaves the maximum INTERNAL major diameter
# unspecified (established by the unworn tool crest); basic is its minimum.
# Primary source: https://fpg-co.com/Standards/ASME%20B1.1%202008.pdf
# This result applies only IF the actual internal root diameter is no greater
# than basic major AND its actual axial extent stays within that cylinder.
# Neither printed 2B nor thread-depth MIN guarantees these conditions. It is
# not a lower bound on actual internal-root wall and is not a pass condition;
# a qualified off-the-shelf tap/process remains an owner decision.
CONDITIONAL_BASIC_MAJOR_NOTCH_WALL = cylindrical_notch_distance(
    RECEIVER_NOTCH_AXIAL_GAP_MIN, RECEIVER_NOTCH_HEIGHT_MIN, SCREW_MAJOR_DIA / 2.0,
) - DRILL_WANDER_MAX

COUNTERBORE_END_WALL_MIN = (
    min(SCREW_MACHINE_X) - SIDE_PLATE_MACHINE_X[0]
    - POSITION_BAND - (COUNTERBORE_DIA + DRILLED_DIAMETER_PLUS) / 2.0
)
COUNTERBORE_HEIGHT_WALL_MIN = (
    SIDE_PLATE_HEIGHT - LINEAR_BAND - (SIDE_PLATE_HEIGHT / 2.0 + POSITION_BAND)
    - (COUNTERBORE_DIA + DRILLED_DIAMETER_PLUS) / 2.0
)

if ENGAGEMENT_MIN < 1.5 * SCREW_MAJOR_DIA:
    raise AssertionError("magnifying bracket screw loses 1.5D full engagement")
if SCREW_TIP_GAP_MIN <= 0.0:
    raise AssertionError("magnifying bracket screw bottoms in its full-thread seat")
if THREAD_RIB_MARGIN_MIN < 0.0:
    raise AssertionError("magnifying bracket full thread runs beyond the front rib")
if TAP_LEAD_MARGIN_MIN < 0.0:
    raise AssertionError("magnifying bracket tap drill loses bottoming-tap lead")
if DRILL_POINT_RIB_MARGIN_MIN < 0.0:
    raise AssertionError("magnifying bracket tap drill breaks out of the front rib")
if RECEIVER_DRILL_NOTCH_WALL_MIN < LOCAL_WALL_HARD_FLOOR:
    raise AssertionError("magnifying bracket receiver notch loses 1.5 mm hard-floor wall")
if RECEIVER_DRILL_NOTCH_WALL_MIN < RECEIVER_NOTCH_WALL_REQUIRED:
    raise AssertionError("magnifying bracket receiver notch loses approved 2.0 mm wall")
if HEAD_FLOAT_MIN < HEAD_POSITION_MISMATCH_MAX:
    raise AssertionError("magnifying bracket counterbore loses head float")
if min(
    GRIP_MIN, COUNTERBORE_END_WALL_MIN, COUNTERBORE_HEIGHT_WALL_MIN,
) < LOCAL_WALL_HARD_FLOOR:
    raise AssertionError("magnifying bracket joint loses a drawing-guidelines.md rule 17 (walls and webs) wall")
