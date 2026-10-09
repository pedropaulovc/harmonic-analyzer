"""Two fillister screws seat MHA-MG-001 on MHA-SM-003's front face.

Pure joint data: no assembly or COM imports enter either part recipe. Machine
seat coordinates are pinned to the live summing installation by the offline
contract and the magnifier assembly. Photo stations: ch30 page002_img01 front
view and ch20 page001_img01, top-right close-up.
"""

from __future__ import annotations

from _hole_spec import DRILL_POINT_H, HoleSpec, blind_cut_dia_mm

SCREW_SKU = "91794A077"
SCREW_THREAD = "#2-56"
SCREW_LENGTH = 6.35  # McMaster 91794A077, under-head 1/4 in
SCREW_MAJOR_DIA = 2.1844
SCREW_HEAD_DIA = 3.556
SCREW_HEAD_HEIGHT = 2.1082
SCREW_PITCH = 25.4 / 56.0

BRACKET_ORIGIN = (40.0, 979.7, -128.3)
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
# A flush head would put this screw's full thread beyond the 5.08 front rib.
# The shallow counterbore instead leaves a bearing floor and a visible head.
COUNTERBORE_DIA = 3.8
COUNTERBORE_DEPTH = 1.55
CLEARANCE_DIA = blind_cut_dia_mm(HoleSpec("clearance", "#2", fit="normal"))
CLEARANCE_SPEC = HoleSpec(
    "counterbore_fillister",
    "#2",
    fit="normal",
    overrides_mm={
        "HoleDiameter": CLEARANCE_DIA,
        "CounterBoreDiameter": COUNTERBORE_DIA,
        "CounterBoreDepth": COUNTERBORE_DEPTH,
    },
)
SCREW_POSITIONS = tuple(
    (x, BRACKET_ORIGIN[1], SIDE_PLATE_FRONT_Z + COUNTERBORE_DEPTH)
    for x in SCREW_MACHINE_X
)
GRIP = SIDE_PLATE_THICKNESS - COUNTERBORE_DEPTH
ENGAGEMENT = SCREW_LENGTH - GRIP
HEAD_PROTRUSION = SCREW_HEAD_HEIGHT - COUNTERBORE_DEPTH

# Joint-specific native bands authorized by the October 8, 2026 user ruling.
# Default .XX bands cannot retain full thread inside this rib. The modeled
# thread stays in the rib; only the smaller tap drill continues into the plate.
PLATE_THICKNESS_BAND = 0.05
COUNTERBORE_DEPTH_BAND = 0.05
THREAD_DEPTH_BAND = 0.05
DRILL_DEPTH_BAND = 0.10
RIB_DEPTH = 5.08
RIB_DEPTH_BAND = 0.05
LEVER_PLATE_THICKNESS = 5.08
LEVER_PLATE_THICKNESS_BAND = 0.05
RECEIVER_DIMENSION_BANDS = {
    "CoefficientsPlate": {"D1": LEVER_PLATE_THICKNESS_BAND},
    "EdgeRibBack": {"D1": RIB_DEPTH_BAND},  # -Z entry; Front is the opposite rib
}
POSITION_BAND = 0.05
DRILLED_DIAMETER_PLUS = 0.10
LINEAR_BAND = 0.51  # PRINTED title-block .XX band, not the unrounded .02 in
HEAD_FLOAT_MIN = (COUNTERBORE_DIA - SCREW_HEAD_DIA) / 2.0
HEAD_POSITION_MISMATCH_MAX = 2.0 * POSITION_BAND
EDGE_BREAK = 0.25
SCREW_LENGTH_MINUS = 0.76  # conservative stock allowance, not a catalog band
SCREW_TIP_CHAMFER = 0.7 * SCREW_PITCH
GRIP_BAND = PLATE_THICKNESS_BAND + COUNTERBORE_DEPTH_BAND
GRIP_MIN = GRIP - GRIP_BAND
ENGAGEMENT_MIN = (
    ENGAGEMENT - SCREW_LENGTH_MINUS - GRIP_BAND - SCREW_TIP_CHAMFER - EDGE_BREAK
)
SCREW_REACH_MAX = ENGAGEMENT + GRIP_BAND
THREAD_DEPTH = 4.95
DRILL_DEPTH = 6.05
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
    DRILL_DEPTH - DRILL_DEPTH_BAND
    - THREAD_DEPTH - THREAD_DEPTH_BAND - 2.0 * SCREW_PITCH
)
DRILL_POINT_RIB_MARGIN = RIB_DEPTH - DRILL_DEPTH - DRILL_POINT_DEPTH
DRILL_POINT_RIB_MARGIN_MIN = (
    RIB_DEPTH - RIB_DEPTH_BAND - DRILL_DEPTH - DRILL_DEPTH_BAND
    - DRILL_POINT_DEPTH_MAX
)
# The print locates the row from the real lower face, not a derived mid-plane.
# The opposite wall therefore takes the FULL plate-thickness band.
DRILL_LATERAL_WALL_MIN = (
    LEVER_PLATE_THICKNESS - LEVER_PLATE_THICKNESS_BAND
    - (LEVER_PLATE_THICKNESS / 2.0 + POSITION_BAND)
    - (TAP_DRILL_DIA + DRILLED_DIAMETER_PLUS) / 2.0
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
if HEAD_FLOAT_MIN < HEAD_POSITION_MISMATCH_MAX:
    raise AssertionError("magnifying bracket counterbore loses head float")
if min(
    GRIP_MIN, DRILL_LATERAL_WALL_MIN,
    COUNTERBORE_END_WALL_MIN, COUNTERBORE_HEIGHT_WALL_MIN,
) < 1.5:
    raise AssertionError("magnifying bracket joint loses a rule-12 wall")
