"""TL-22: one plain shoulder-screw block on rail 2.

Frame: carriage-pattern centre, bottom Z0; +X away from spindle. New
6061 1 x 3-1/2 inch stock is shared with TL-32. No cartridge hardware.
The print locates every X from the -X (left) edge, never from the frame
centre: ``PLAN_DATUM_REFERENCE`` carries those ordinates.
"""
from __future__ import annotations

import math
import ch_rocker_arm_tl_vn_oblique_pivot_screw_spec as pivot_screw
from _fit_deviations import deviations
from _hole_spec import HoleSpec
from _printed_tolerance import printed_band_mm

PART_NAME = "ch-rocker-arm-tl-oblique-pivot-block"
NUMBER = "MHA-CH-06-TL-22"
QUANTITY = 1
BLOCK_X0, BLOCK_X1 = -42.0, 20.0
BLOCK_LENGTH = BLOCK_X1 - BLOCK_X0
BLOCK_WIDTH, BLOCK_HEIGHT = 40.0, 24.3
STOCK_THICKNESS, STOCK_WIDTH = 25.4, 88.9
BORE_X, BORE_Y = -32.0, 0.0
# The TL-VN-77 shoulder bottoms on the seat floor, so the 3-place depth sets
# how high the screw stands, hence the head-to-carrier gap the assembly's
# shim selection then trims (jig assembly ``PIVOT_RUNNING_GAP``).
BORE_DIA, BORE_DEPTH = 10.0, 7.65
BORE_BAND = (0.015, 0.0)  # H7; locating seat for TL-VN-77 shoulder
_bore_lower, _bore_upper = deviations(BORE_BAND)
_shoulder_lower, _shoulder_upper = deviations(pivot_screw.SHOULDER_DIA_BAND)
BORE_LIMITS = (BORE_DIA + _bore_lower, BORE_DIA + _bore_upper)
PIVOT_LOCATING_CLEARANCE_MIN = BORE_LIMITS[0] - (pivot_screw.SHOULDER_DIA + _shoulder_upper)
PIVOT_LOCATING_CLEARANCE_MAX = BORE_LIMITS[1] - (pivot_screw.SHOULDER_DIA + _shoulder_lower)
if PIVOT_LOCATING_CLEARANCE_MIN < 0.0:
    raise AssertionError("purchased pivot shoulder interferes with its block H7 seat")
PIVOT_TAP = "M8x1.25"
PIVOT_TAP_DRILL = 6.8
PIVOT_THREAD_LENGTH = BLOCK_HEIGHT - BORE_DEPTH
# Rule 18 counts full-form thread only: the TL-VN-77's 13 of thread less 1.5
# incomplete pitches, 11.125 (1.39D). That falls short of 1.5D; the owner's
# 2026-10-27 ruling accepts it (jig assembly config RV-05) and the tap callout
# states it as a plain fact.
PIVOT_THREAD_ENGAGEMENT = pivot_screw.THREAD_LENGTH - 1.5 * pivot_screw.THREAD_PITCH
PIVOT_THREAD_ENGAGEMENT_MIN_D = 1.39  # RV-05's stated floor
PIVOT_ENGAGEMENT_TEXT = f"{math.floor(PIVOT_THREAD_ENGAGEMENT * 100.0) / 100.0:.2f} MIN ENGAGEMENT"
PIVOT_AXIS_NAME = "PivotAxis"
BOLT_X = BOLT_Y = 13.0
BOLT_POINTS = tuple((x, y) for x in (-BOLT_X, BOLT_X) for y in (-BOLT_Y, BOLT_Y))
HOLE_DIA, CBORE_DIA = 4.5, 8.0
CBORE_FLOOR = 15.6
CBORE_DEPTH = BLOCK_HEIGHT - CBORE_FLOOR
CBORE_FLOOR_REFERENCE = "CboreFloorReference"
CARRIAGE_THREAD_DEPTH = 5.0
UNDER_HEAD = CBORE_FLOOR
CBORE_SECTION_PLANE = "CboreSectionPlane"
CBORE_SECTION_X = BOLT_X  # B-B cuts the +X hole column
# Hidden construction sketch on the top face: a line on the -X edge and
# circles on the bore and one hole per column, so the plan's X ordinates start
# on that edge (rule 10) while staying model dimensions.
PLAN_DATUM_REFERENCE = "PlanDatumReference"
PLAN_DATUM_HOLES = ((-BOLT_X, BOLT_Y), (BOLT_X, BOLT_Y))
SCREW_LENGTH, SCREW_LENGTH_TOL = 20.0, 0.42
ENGAGEMENT_MIN = SCREW_LENGTH - SCREW_LENGTH_TOL - CBORE_FLOOR - printed_band_mm(3)
ENGAGEMENT_MAX = SCREW_LENGTH + SCREW_LENGTH_TOL - CBORE_FLOOR + printed_band_mm(3)
SCREW_HOLE_SPEC = HoleSpec("counterbore_socket", "#8", overrides_mm={
    "HoleDiameter": HOLE_DIA, "CounterBoreDiameter": CBORE_DIA,
    "CounterBoreDepth": CBORE_DEPTH,
})
DRAWING_VALUES = {
    "BlockLength": BLOCK_LENGTH, "BlockWidth": BLOCK_WIDTH,
    "SectionBlockHeight": BLOCK_HEIGHT, "BlockSideY": BLOCK_WIDTH / 2,
    "BoreDia": BORE_DIA, "TopBoreDepth": BORE_DEPTH,
    "TapDrillDia": PIVOT_TAP_DRILL,
    "CboreFloor": CBORE_FLOOR,
    "CarriageDrills1Dia": HOLE_DIA,
    # The counterbore prints on hole 3, the drill on hole 1: one leader each.
    "CarriageCounterbores3Dia": CBORE_DIA,
    "CarriageDrills3Y": BOLT_Y, "CarriageDrills4Y": BOLT_Y,
    "PlanBoreX": BORE_X - BLOCK_X0,
    **{f"PlanHole{i}X": x - BLOCK_X0 for i, (x, _y) in enumerate(PLAN_DATUM_HOLES, 1)},
}
DRAWING_DIMENSIONS = {
    "BlockProfile": ("BlockLength", "BlockWidth", "BlockSideY"),
    "TopBoreProfile": ("BoreDia",),
    "TopBore": ("TopBoreDepth",),
    "PivotTapProfile": ("TapDrillDia",),
    CBORE_FLOOR_REFERENCE: ("CboreFloor", "SectionBlockHeight"),
    "CarriageDrillProfile": ("CarriageDrills3Y", "CarriageDrills4Y", "CarriageDrills1Dia"),
    "CarriageCboreProfile": ("CarriageCounterbores3Dia",),
    PLAN_DATUM_REFERENCE: ("PlanBoreX", "PlanHole1X", "PlanHole2X"),
}
THREE_PLACE_DIMENSIONS = frozenset({
    "CboreFloor", "TopBoreDepth", "CarriageDrills3Y", "CarriageDrills4Y",
    "PlanHole1X", "PlanHole2X",
})
DRAWING_PRECISION = {
    feature: {name: (3 if name in THREE_PLACE_DIMENSIONS else 2) for name in names}
    for feature, names in DRAWING_DIMENSIONS.items()
}
DRAWING_PRECISION_BY_NAME = {name: places for names in DRAWING_PRECISION.values() for name, places in names.items()}
CALLOUTS_SUFFIX: dict[str, str] = {}
CALLOUTS_ABOVE = {
    "BoreDia": "REAM H7", "TapDrillDia": "DRILL THRU",
    "CarriageDrills1Dia": "4X DRILL THRU",
    "CarriageCounterbores3Dia": "4X COUNTERBORE FROM TOP",
}
CALLOUTS_BELOW = {
    "BoreDia": "LOCATING FIT ON MHA-CH-06-TL-VN-77 SHOULDER",
    "TapDrillDia": f"M8x1.25 TAP THRU BELOW SHOULDER SEAT\n{PIVOT_ENGAGEMENT_TEXT}",
    "TopBoreDepth": "SETS TL-VN-77 SHOULDER HEIGHT",
    "CarriageDrills1Dia": "MATCHES HGH15CA CARRIAGE M4 PATTERN",
    "CarriageCounterbores3Dia": "FLOOR: SECTION B-B",
    # Under the value, two rows, right of B-B (an above-text newline dropped
    # the note, farm run 20261027T175531766Z): the block height's extension
    # lines pass left of it.
    "CboreFloor": "M4x20 IN HGH15CA:\n3.85 MIN ENGAGEMENT",
}
REFERENCE_SKETCHES = (CBORE_FLOOR_REFERENCE, PLAN_DATUM_REFERENCE)
WALLS_MM = {
    "pivot seat to spindle end": BORE_X - BORE_DIA / 2 - BLOCK_X0,
    "carriage counterbore to side": BLOCK_WIDTH / 2 - BOLT_Y - CBORE_DIA / 2,
    "carriage counterbore to end": BLOCK_X1 - BOLT_X - CBORE_DIA / 2,
    "pivot seat to carriage counterbore": math.hypot(BORE_X + BOLT_X, BOLT_Y) - BORE_DIA / 2 - CBORE_DIA / 2,
}
assert min(WALLS_MM.values()) >= 2.0
assert 3.8 <= round(ENGAGEMENT_MIN, 6) <= round(ENGAGEMENT_MAX, 6) <= 4.95
assert round(PIVOT_THREAD_ENGAGEMENT / pivot_screw.THREAD_DIA, 2) >= PIVOT_THREAD_ENGAGEMENT_MIN_D
assert PIVOT_THREAD_LENGTH > pivot_screw.THREAD_LENGTH
