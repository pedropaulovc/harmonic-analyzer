"""Two fillister screws seat MHA-MG-001 on MHA-SM-003's front face.

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

# Joint-specific native bands authorized by the October 8, 2026 user ruling
# on the thread and drill depths: the stack below leaves 0.04-0.08 of margin
# at them, so neither can take the title block's .XX band.
# The -Z end rib was 5.08 deep, so the drill's tip ran past it into the 5.08
# plate and held the plate to +/-0.05 for its wall.  Owner ruling 2026-10-16
# (option A; the user's ask timed out and the recommended option was
# auto-selected) deepened the rib to 7.0 at a 0.25 band, so the whole tap
# drill, point and wander stay in the rib.  Machinist review r12 read that
# band as tightening to rescue a wall, with no mate; per the standing user
# preference (move the nominal so the title block holds, coordinator
# 2026-10-16) the rib is 7.3, the least one-place depth whose drill-point
# margin holds at the title block's .XX band, so it takes no native band.
PLATE_THICKNESS_BAND = 0.05
COUNTERBORE_DEPTH_BAND = 0.05
THREAD_DEPTH_BAND = 0.05
# The tap drill's depth is one-sided, +0.10/0 (owner ruling 2026-10-18 on
# machinist review 4b89c4336): its shallowest is the nominal, which holds the
# bottoming tap's lead; its deepest, 6.15, keeps the point in the rib.
DRILL_DEPTH_DEVIATIONS = (0.0, 0.10)  # (lower, upper), mm
RIB_DEPTH = 7.3
POSITION_BAND = 0.05
DRILLED_DIAMETER_PLUS = 0.10
LINEAR_BAND = 0.51  # PRINTED title-block .XX band, not the unrounded .02 in
RIB_DEPTH_BAND = LINEAR_BAND  # the title block's: the rib takes no native band
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
DRILL_DEPTH = 6.05
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
# Lateral drift of the drill at its deepest reach (fr_top_frame_spec's 0.3
# deg realistic wander, restated so the joint stays a pure leaf module): the
# rib walls round the tap are judged with it.
DRILL_WANDER_DEG = 0.3
DRILL_WANDER_MAX = math.tan(math.radians(DRILL_WANDER_DEG)) * (
    DRILL_DEPTH_MAX + DRILL_POINT_DEPTH_MAX
)
# The drill point's floor margin also takes the whole wander, as if it were
# axial (it is lateral: an upper bound, so the 7.3 rib holds even then).
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
if HEAD_FLOAT_MIN < HEAD_POSITION_MISMATCH_MAX:
    raise AssertionError("magnifying bracket counterbore loses head float")
if min(
    GRIP_MIN, COUNTERBORE_END_WALL_MIN, COUNTERBORE_HEIGHT_WALL_MIN,
) < 1.5:
    raise AssertionError("magnifying bracket joint loses a drawing-guidelines.md rule 17 (walls and webs) wall")
