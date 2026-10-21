"""Two fillister screws seat MHA-MG-01 on MHA-SM-03's front face.

Pure joint data: no assembly or COM imports enter either part recipe. Machine
seat coordinates are pinned to the live summing installation by the offline
contract and the magnifier assembly. Photo stations: ch30 page002_img01 front
view and ch20 page001_img01, top-right close-up.
"""

from __future__ import annotations

import math

from _hole_spec import DRILL_POINT_H, HoleSpec, blind_cut_dia_mm
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

# The owner approved the inward-only 9.00 receiver rib and the bounded
# thread-cutting requirement below on 2026-10-20. Entry face, both axes and
# the opposite 5.08 rib stay fixed. Native full-thread metadata preserves
# the screw/grip stack; the separate cutting envelope bounds manufacturing.
PLATE_THICKNESS_BAND = 0.05
COUNTERBORE_DEPTH_BAND = 0.05
THREAD_DEPTH_BAND = 0.05  # native metadata only; the drawing prints 4.95 MIN
LINEAR_BAND = 0.51  # PRINTED title-block .XX band, not the unrounded .02 in
# A bounded ordinary band is still necessary: an unlimited MIN depth could
# run the drill beyond any finite rib into the unbacked coefficient plate.
DRILL_DEPTH_DEVIATIONS = (-LINEAR_BAND, LINEAR_BAND)  # (lower, upper), mm
RIB_DEPTH = 9.00
POSITION_BAND = 0.05
DRILLED_DIAMETER_PLUS = 0.10
RIB_DEPTH_BAND = LINEAR_BAND  # the title block's: the rib takes no native band
# Rule-17 floor for the separate pilot and required thread-cutting envelopes.
RECEIVER_WALL_MIN = 2.0
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
THREAD_DEPTH = 4.95
DRILL_DEPTH = 6.50
DRILL_DEPTH_MIN = DRILL_DEPTH + DRILL_DEPTH_DEVIATIONS[0]
DRILL_DEPTH_MAX = DRILL_DEPTH + DRILL_DEPTH_DEVIATIONS[1]
# Manufacturing requirement, NOT a claimed stock-tap specification or physical
# thread model: every thread-cutting removal (including partial thread, lead,
# chamfer, tip, runout and deflection) must fit this cylinder about the ACTUAL
# finished-hole axis, measured from the ACTUAL entry face. Separate pilot
# drilling is excluded and retains its own deeper finite-cone proof.
THREAD_CUTTING_ENVELOPE_DIA_MAX = 2.40
THREAD_CUTTING_ENVELOPE_DEPTH_MAX = 6.00
# An additional conservative proof reserve, not another runout allowance or a
# tighter printed axis tolerance. Runout/deflection are already IN the envelope.
THREAD_CUTTING_PROOF_RESERVE = 0.04
THREAD_CUTTING_AUXILIARY_DEPTH_MAX = THREAD_CUTTING_ENVELOPE_DEPTH_MAX - THREAD_DEPTH
THREAD_CUTTING_LEAD_MARGIN_MIN = (
    THREAD_CUTTING_ENVELOPE_DEPTH_MAX - THREAD_DEPTH - THREAD_DEPTH_BAND
    - 2.0 * SCREW_PITCH
)
TAP_SPEC = HoleSpec(
    "tapped_bottoming",
    SCREW_THREAD,
    end="blind",
    depth_mm=DRILL_DEPTH,
    thread_class="2B",
    overrides_mm={"ThreadDepth": THREAD_DEPTH},
)
TAP_DRILL_DIA = blind_cut_dia_mm(TAP_SPEC)
DRILL_POINT_DEPTH = TAP_DRILL_DIA / 2.0 * DRILL_POINT_H
DRILL_POINT_DEPTH_MAX = (
    (TAP_DRILL_DIA + DRILLED_DIAMETER_PLUS) / 2.0 * DRILL_POINT_H
)
THREAD_RIB_MARGIN_MIN = RIB_DEPTH - RIB_DEPTH_BAND - THREAD_DEPTH - THREAD_DEPTH_BAND
SCREW_TIP_GAP_MIN = THREAD_DEPTH - THREAD_DEPTH_BAND - SCREW_REACH_MAX
TAP_LEAD_MARGIN_MIN = (
    DRILL_DEPTH_MIN - THREAD_DEPTH - THREAD_DEPTH_BAND - 2.0 * SCREW_PITCH
)
DRILL_POINT_RIB_MARGIN = RIB_DEPTH - DRILL_DEPTH - DRILL_POINT_DEPTH
# Lateral pilot drift at its deepest reach (fr_top_frame_spec's 0.3 deg
# realistic wander, restated so this stays a pure leaf module). Thread-cutting
# runout/deflection are already contained by the separate required envelope.
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
COUNTERBORE_END_WALL_MIN = (
    min(SCREW_MACHINE_X) - SIDE_PLATE_MACHINE_X[0]
    - POSITION_BAND - (COUNTERBORE_DIA + DRILLED_DIAMETER_PLUS) / 2.0
)
COUNTERBORE_HEIGHT_WALL_MIN = (
    SIDE_PLATE_HEIGHT - LINEAR_BAND - (SIDE_PLATE_HEIGHT / 2.0 + POSITION_BAND)
    - (COUNTERBORE_DIA + DRILLED_DIAMETER_PLUS) / 2.0
)


def receiver_step_wall_margin(
    rib_depth_min: float,
    floor_from_axis_min: float,
    cylinder_depth_max: float,
    radius_max: float,
    point_height_ratio: float,
    wander_max: float,
) -> float:
    """Finite drill/thread envelope to the sharp inward rib-to-plate step.

    Work in an axial/radial section through the nearest plate face. The
    excluded quadrant starts at (rib_depth_min, floor_from_axis_min); treating
    it as infinite in X can only REMOVE material from the real rib/plate
    union. Ignoring the concave R1 root similarly gives a lower wall bound.
    The full cylinder's nearest point is its last shoulder. On the finite
    cone, radial contraction u spans [0, radius_max] and advances axially by
    k*u, where k is the point height/radius. Projection of the sharp corner
    onto that segment gives the clamped minimum below. A zero k models a
    flat-ended bounding cylinder, including all partial thread/tip removal.
    No infinite-cone or always-shoulder shortcut survives a changed envelope.

    The premises require the full cylinder behind the step and inside the
    plate face; fail closed rather than applying this section proof after
    either premise changes. Subtracting the entire deepest wander once is a
    conservative Euclidean perturbation bound, not a second axial allowance.
    """
    values = (
        rib_depth_min, floor_from_axis_min, cylinder_depth_max, radius_max,
        point_height_ratio, wander_max,
    )
    if (
        not all(math.isfinite(value) for value in values)
        or not rib_depth_min >= cylinder_depth_max >= 0.0
        or not floor_from_axis_min >= radius_max >= 0.0
        or point_height_ratio < 0.0
        or wander_max < 0.0
    ):
        raise ValueError("receiver step-wall geometry violates finite-envelope premises")
    a = rib_depth_min - cylinder_depth_max
    b = floor_from_axis_min - radius_max
    k = point_height_ratio
    u = min(radius_max, max(0.0, (k * a - b) / (1.0 + k * k)))
    return math.hypot(a - k * u, b + u) - wander_max


def receiver_pilot_step_wall_budget() -> float:
    """Printed PILOT-only step wall; independent of thread-cutting limits.

    The row is dimensioned from the ACTUAL top face: its top-position shift
    cancels, while thickness and row-location bands remain independent.
    Charge either plate face, the shortest printed rib, deepest printed drill
    and pilot rounded to .XX (1.78, not native 1.778), plus the drill allowance.
    Include the larger native pilot if rounding would otherwise shrink it.
    Thread cutting is bounded independently by its manufacturing requirement.
    """
    radius = (
        max(TAP_DRILL_DIA, round(TAP_DRILL_DIA, 2)) + DRILLED_DIAMETER_PLUS
    ) / 2.0
    wander = math.tan(math.radians(DRILL_WANDER_DEG)) * (
        DRILL_DEPTH_MAX + radius * DRILL_POINT_H
    )
    return min(
        receiver_step_wall_margin(
            RIB_DEPTH - RIB_DEPTH_BAND,
            min(
                lever.COEFFICIENT_TOP_Y - y - POSITION_BAND,
                lever.COEFFICIENT_T - LINEAR_BAND
                - (lever.COEFFICIENT_TOP_Y - y) - POSITION_BAND,
            ),
            DRILL_DEPTH_MAX, radius, DRILL_POINT_H, wander,
        )
        for _x, y, _z in LEVER_HOLE_POINTS
    )


def receiver_thread_cutting_step_wall_budget() -> float:
    """Wall guaranteed for a process conforming to the full cutting envelope.

    The entire removal cylinder, not merely usable/full threads, ends at the
    required maximum reach from the actual entry. Position bands are already
    charged in each actual-top/thickness floor. Runout and deflection are
    included in the required diameter, not added again as drill wander.
    Subtract the independent conservative proof reserve once; it neither
    changes the drawing's hole-position tolerance nor qualifies a tool.
    """
    return min(
        receiver_step_wall_margin(
            RIB_DEPTH - RIB_DEPTH_BAND,
            min(
                lever.COEFFICIENT_TOP_Y - y - POSITION_BAND,
                lever.COEFFICIENT_T - LINEAR_BAND
                - (lever.COEFFICIENT_TOP_Y - y) - POSITION_BAND,
            ),
            THREAD_CUTTING_ENVELOPE_DEPTH_MAX,
            THREAD_CUTTING_ENVELOPE_DIA_MAX / 2.0,
            0.0, THREAD_CUTTING_PROOF_RESERVE,
        )
        for _x, y, _z in LEVER_HOLE_POINTS
    )

if ENGAGEMENT_MIN < 1.5 * SCREW_MAJOR_DIA:
    raise AssertionError("magnifying bracket screw loses 1.5D full engagement")
if SCREW_TIP_GAP_MIN <= 0.0:
    raise AssertionError("magnifying bracket screw bottoms in its full-thread seat")
if THREAD_RIB_MARGIN_MIN < 0.0:
    raise AssertionError("magnifying bracket modeled full thread runs beyond the front rib")
if TAP_LEAD_MARGIN_MIN < 0.0:
    raise AssertionError("magnifying bracket tap drill loses bottoming-tap lead design allowance")
if THREAD_CUTTING_LEAD_MARGIN_MIN < 0.0:
    raise AssertionError("magnifying bracket thread-cutting envelope loses axial lead budget")
if THREAD_CUTTING_ENVELOPE_DIA_MAX < SCREW_MAJOR_DIA:
    raise AssertionError("magnifying bracket thread-cutting envelope cannot contain nominal thread")
if DRILL_POINT_RIB_MARGIN_MIN < 0.0:
    raise AssertionError("magnifying bracket tap drill breaks out of the front rib")
if HEAD_FLOAT_MIN < HEAD_POSITION_MISMATCH_MAX:
    raise AssertionError("magnifying bracket counterbore loses head float")
if min(
    GRIP_MIN, COUNTERBORE_END_WALL_MIN, COUNTERBORE_HEIGHT_WALL_MIN,
) < 1.5:
    raise AssertionError("magnifying bracket joint loses a drawing-guidelines.md rule 17 (walls and webs) wall")

RECEIVER_PILOT_STEP_WALL_MIN = receiver_pilot_step_wall_budget()
if RECEIVER_PILOT_STEP_WALL_MIN < RECEIVER_WALL_MIN:
    raise AssertionError(
        f"magnifying bracket receiver pilot step wall {RECEIVER_PILOT_STEP_WALL_MIN:.6f} mm "
        f"is below the {RECEIVER_WALL_MIN:g} mm pilot floor"
    )
RECEIVER_THREAD_CUTTING_STEP_WALL_MIN = receiver_thread_cutting_step_wall_budget()
if RECEIVER_THREAD_CUTTING_STEP_WALL_MIN < RECEIVER_WALL_MIN:
    raise AssertionError(
        "magnifying bracket receiver thread-cutting step wall "
        f"{RECEIVER_THREAD_CUTTING_STEP_WALL_MIN:.6f} mm "
        f"is below the {RECEIVER_WALL_MIN:g} mm requirement floor"
    )
