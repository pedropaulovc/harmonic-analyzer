"""TL-32 integral feed block, rail 1; same pivot/carriage interface as TL-22.

Nut holes are drilled to print, never transfer spotted. The nut flange seats
on the -X lug face with its long body proud; all coordinates are block-local.
The nut face's print locates the nut axis from the lug end and the bottom
face, and the four taps from that axis (``NutPatternReference``), so the
pattern holds to the spigot recess it surrounds.
"""
from __future__ import annotations
import math
import ch_rocker_arm_tl_oblique_pivot_block_spec as pivot
import ch_rocker_arm_tl_oblique_trammel_spec as trammel
import ch_rocker_arm_tl_vn_oblique_leadscrew_spec as lead
from _hole_spec import HoleSpec, TAP_DRILL_MM, THREAD_MAJOR_MM
from _printed_tolerance import printed_band_mm

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
PLAN_DATUM_REFERENCE = pivot.PLAN_DATUM_REFERENCE
DRAWING_VALUES = dict(pivot.DRAWING_VALUES) | {
    "LugWidth": LUG_WIDTH, "PlanLugX": LUG_X0 - BLOCK_X0,
    "PlanOverallY": BLOCK_WIDTH / 2 - LUG_Y0,
    "NutSeatDia": NUT_SEAT_DIA, "NutClearanceDia": SCREW_CLEARANCE_DIA,
    "NutCentreZ": NUT_AXIS_Z, "NutCentreY": NUT_AXIS_Y - LUG_Y0,
    **{f"NutTap{i}{axis}": NUT_HOLE_OFFSET for i in range(1, 5) for axis in ("Z", "Y")},
}
# The four taps print as offsets from the nut axis: rows on the -Z column
# (taps 1 and 3), columns on the +Y row (taps 3 and 4).
NUT_PATTERN_PRINTED = ("NutCentreZ", "NutCentreY", "NutTap3Z", "NutTap4Z", "NutTap1Y", "NutTap3Y")
DRAWING_DIMENSIONS = dict(pivot.DRAWING_DIMENSIONS) | {
    PLAN_DATUM_REFERENCE: pivot.DRAWING_DIMENSIONS[PLAN_DATUM_REFERENCE] + ("PlanLugX", "PlanOverallY"),
    "LugProfile": ("LugWidth",),
    "NutSeatProfile": ("NutSeatDia",),
    "NutClearanceProfile": ("NutClearanceDia",),
    "NutPatternReference": NUT_PATTERN_PRINTED,
}
NUT_PATTERN_PLACES = 3
NUT_SEAT_PLACES = 2
DRAWING_PRECISION = dict(pivot.DRAWING_PRECISION) | {
    feature: {
        name: (3 if name in pivot.THREE_PLACE_DIMENSIONS or name.startswith("NutTap") else 2)
        for name in DRAWING_DIMENSIONS[feature]
    }
    for feature in (PLAN_DATUM_REFERENCE, "LugProfile", "NutSeatProfile", "NutClearanceProfile", "NutPatternReference")
}
DRAWING_PRECISION_BY_NAME = {
    name: places for dimensions in DRAWING_PRECISION.values()
    for name, places in dimensions.items()
}
assert DRAWING_PRECISION_BY_NAME["NutTap3Z"] == NUT_PATTERN_PLACES
assert DRAWING_PRECISION_BY_NAME["NutSeatDia"] == NUT_SEAT_PLACES
# Rule 17 shortfall, stated on the sheet (rule 20): the Ø16 PCD is the bought
# nut's, so a #4-40 major sits 1.33 from the Ø10.50 spigot recess at nominal;
# no recess that still clears the Ø10.2 spigot reaches the 1.5 floor. Worst
# case: the recess at its upper .XX limit, each tap off the axis by its .XXX
# band in both Y and Z.
NUT_TAP_MAJOR = THREAD_MAJOR_MM["#4-40"]
NUT_SEAT_WALL_NOMINAL = NUT_PCD / 2 - NUT_SEAT_DIA / 2 - NUT_TAP_MAJOR / 2
NUT_SEAT_WALL_MIN = (
    NUT_PCD / 2
    - math.hypot(printed_band_mm(NUT_PATTERN_PLACES), printed_band_mm(NUT_PATTERN_PLACES))
    - (NUT_SEAT_DIA + printed_band_mm(NUT_SEAT_PLACES)) / 2
    - NUT_TAP_MAJOR / 2
)
NUT_SEAT_WALL_TEXT = f"WALL {math.floor(NUT_SEAT_WALL_MIN * 100) / 100:.2f} MIN TO 4-40 TAPS"
assert 0.0 < NUT_SEAT_WALL_MIN < NUT_SEAT_WALL_NOMINAL < 1.5
assert NUT_PCD / 2 - lead.NUT_BODY_DIA / 2 - NUT_TAP_MAJOR / 2 < 1.5
CALLOUTS_SUFFIX = dict(pivot.CALLOUTS_SUFFIX) | {
    "NutSeatDia": f" <HOLE-DEPTH> {NUT_SPIGOT_DEPTH:.2f}",
}
CALLOUTS_ABOVE = dict(pivot.CALLOUTS_ABOVE) | {"NutClearanceDia": "DRILL THRU"}
CALLOUTS_BELOW = dict(pivot.CALLOUTS_BELOW) | {
    "NutSeatDia": f"SPIGOT CLEARANCE: TL-VN-55 NUT\n{NUT_SEAT_WALL_TEXT}",
    "NutClearanceDia": "LEADSCREW CLEARANCE",
    "NutCentreZ": "FROM BOTTOM FACE",
}
NUT_FLANGE_MATE_TEXT = "MATCHES TL-VN-55 NUT FLANGE"
REFERENCE_SKETCHES = pivot.REFERENCE_SKETCHES + ("NutPatternReference",)
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
