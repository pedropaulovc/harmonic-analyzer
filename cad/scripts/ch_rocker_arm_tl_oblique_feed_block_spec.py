"""TL-32 integral feed block, rail 1; same pivot/carriage interface as TL-22.

Nut holes are drilled to print, never transfer spotted. The nut flange seats
on the -X lug face with its long body proud; all coordinates are block-local.
"""
from __future__ import annotations
import math
import ch_rocker_arm_tl_oblique_pivot_block_spec as pivot
import ch_rocker_arm_tl_oblique_trammel_spec as trammel
import ch_rocker_arm_tl_vn_oblique_leadscrew_spec as lead
from _hole_spec import HoleSpec, TAP_DRILL_MM

PART_NAME = "ch-rocker-arm-tl-oblique-feed-block"
NUMBER = "MHA-CH-06-TL-32"
QUANTITY = 1
BLOCK_X0, BLOCK_X1 = pivot.BLOCK_X0, pivot.BLOCK_X1
BLOCK_LENGTH, BLOCK_WIDTH, BLOCK_HEIGHT = pivot.BLOCK_LENGTH, pivot.BLOCK_WIDTH, pivot.BLOCK_HEIGHT
LUG_X0, LUG_X1 = -9.25, 9.25
LUG_Y0, LUG_Y1 = -68.0, -20.0
LUG_WIDTH, LUG_LENGTH = LUG_X1 - LUG_X0, LUG_Y1 - LUG_Y0
NUT_FACE_X = LUG_X0
NUT_AXIS_Y, NUT_AXIS_Z = -55.0, 12.4
NUT_SPIGOT_DEPTH = 1.5
NUT_SEAT_DIA = 10.5
SCREW_CLEARANCE_DIA = 8.5
NUT_PCD = 16.0
NUT_PATTERN_ANGLE = 45.0
NUT_HOLE_OFFSET = NUT_PCD / (2 * math.sqrt(2))
NUT_HOLES_YZ = tuple((NUT_AXIS_Y + dy * NUT_HOLE_OFFSET, NUT_AXIS_Z + dz * NUT_HOLE_OFFSET)
                     for dy in (-1, 1) for dz in (-1, 1))
SCREW_TAP_DEPTH = 10.0
NUT_TAP_DRILL_DEPTH = 12.0
NUT_TAP_DRILL = TAP_DRILL_MM["#4-40"]
NUT_TAP_SPEC = HoleSpec("tapped", "#4-40", end="blind", depth_mm=NUT_TAP_DRILL_DEPTH,
                        overrides_mm={"ThreadDepth": SCREW_TAP_DEPTH})
NUT_REACH_X = (NUT_FACE_X - lead.NUT_FLANGE_THICK - lead.NUT_BODY_LONG,
               max(LUG_X1, NUT_FACE_X + lead.NUT_BODY_SHORT))
NUT_MACHINE_Z = trammel.CARRIAGE_TOP_Z + NUT_AXIS_Z
DRAWING_VALUES = dict(pivot.DRAWING_VALUES) | {
    "LugWidth": LUG_WIDTH, "LugLength": LUG_LENGTH,
    "LugEndX": -LUG_X0, "LugEndY": -LUG_Y0,
    "NutAxisY": -NUT_AXIS_Y, "NutAxisZ": NUT_AXIS_Z,
    "NutSeatDia": NUT_SEAT_DIA, "NutSeatDepth": NUT_SPIGOT_DEPTH,
    "NutClearanceDia": SCREW_CLEARANCE_DIA,
    **{f"NutTap{i}{axis}": abs(value)
       for i, point in enumerate(NUT_HOLES_YZ, 1)
       for axis, value in zip(("Y", "Z"), point)},
}
DRAWING_DIMENSIONS = dict(pivot.DRAWING_DIMENSIONS) | {
    "LugProfile": ("LugWidth", "LugLength", "LugEndX", "LugEndY"),
    "NutSeatProfile": ("NutAxisZ", "NutAxisY", "NutSeatDia"),
    "NutSeat": ("NutSeatDepth",),
    "NutClearanceProfile": ("NutClearanceDia",),
    "NutPatternReference": tuple(n for i in range(1, 5) for n in (f"NutTap{i}Z", f"NutTap{i}Y")),
}
DRAWING_PRECISION = dict(pivot.DRAWING_PRECISION) | {
    feature: {name: (3 if feature == "NutPatternReference" else 2) for name in DRAWING_DIMENSIONS[feature]}
    for feature in ("LugProfile", "NutSeatProfile", "NutSeat", "NutClearanceProfile", "NutPatternReference")
}
DRAWING_PRECISION_BY_NAME = {
    name: places for dimensions in DRAWING_PRECISION.values()
    for name, places in dimensions.items()
}
CALLOUTS_ABOVE = dict(pivot.CALLOUTS_ABOVE)
CALLOUTS_BELOW = dict(pivot.CALLOUTS_BELOW) | {
    "NutSeatDia": "SPIGOT CLEARANCE: TL-VN-55 NUT",
    "NutClearanceDia": "LEADSCREW CLEARANCE THRU",
}
REFERENCE_SKETCHES = pivot.REFERENCE_SKETCHES + ("NutPatternReference",)
ISOMETRIC_VIEW_NOTE = "RAIL 1 / QTY 1 / INTEGRAL NUT LUG"
# The flange rim remains within the full-height lug.
assert NUT_AXIS_Z - lead.NUT_FLANGE_DIA / 2 >= 0
assert NUT_AXIS_Z + lead.NUT_FLANGE_DIA / 2 <= BLOCK_HEIGHT
assert -NUT_AXIS_Y + lead.NUT_FLANGE_DIA / 2 + 2 <= -LUG_Y0
assert abs(NUT_MACHINE_Z - lead.SCREW_AXIS_Z) < 1e-6
assert NUT_TAP_DRILL_DEPTH + NUT_TAP_DRILL / 2 * 0.60086 < LUG_WIDTH
# Travel-end clearance includes the proud purchased nut, not only the lug.
for _box in lead.KP08_BOXES.values():
    for _station in trammel.CARRIAGE_TRAVEL:
        _lo, _hi = _station + NUT_REACH_X[0], _station + NUT_REACH_X[1]
        assert max(_box[0] - _hi, _lo - _box[1]) >= lead.FEED_GAP
