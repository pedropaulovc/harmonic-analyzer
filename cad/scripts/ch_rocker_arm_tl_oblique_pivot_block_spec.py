"""TL-22: one plain shoulder-screw block on rail 2.

Frame: carriage-pattern centre, bottom Z0; +X away from spindle. New
6061 1 x 3-1/2 inch stock is shared with TL-32. No cartridge hardware.
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
PIVOT_THREAD_ENGAGEMENT = 13.0
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
SCREW_LENGTH, SCREW_LENGTH_TOL = 20.0, 0.42
ENGAGEMENT_MIN = SCREW_LENGTH - SCREW_LENGTH_TOL - CBORE_FLOOR - printed_band_mm(3)
ENGAGEMENT_MAX = SCREW_LENGTH + SCREW_LENGTH_TOL - CBORE_FLOOR + printed_band_mm(3)
SCREW_HOLE_SPEC = HoleSpec("counterbore_socket", "#8", overrides_mm={
    "HoleDiameter": HOLE_DIA, "CounterBoreDiameter": CBORE_DIA,
    "CounterBoreDepth": CBORE_DEPTH,
})
DRAWING_VALUES = {
    "BlockLength": BLOCK_LENGTH, "BlockWidth": BLOCK_WIDTH,
    "BlockHeight": BLOCK_HEIGHT, "BlockEndX": -BLOCK_X0,
    "BlockSideY": BLOCK_WIDTH / 2, "BoreX": -BORE_X,
    "BoreDia": BORE_DIA, "TopBoreDepth": BORE_DEPTH,
    "TapDrillDia": PIVOT_TAP_DRILL, "TapX": -BORE_X,
    "CboreFloor": CBORE_FLOOR,
    "CarriageDrills1Dia": HOLE_DIA,
    "CarriageCounterbores1Dia": CBORE_DIA,
    **{f"CarriageDrills{i}{axis}": abs(value)
       for i, point in enumerate(BOLT_POINTS, 1)
       for axis, value in zip(("X", "Y"), point)},
}
DRAWING_DIMENSIONS = {
    "BlockProfile": ("BlockLength", "BlockWidth", "BlockEndX", "BlockSideY"),
    "Block": ("BlockHeight",),
    "TopBoreProfile": ("BoreX", "BoreDia"),
    "TopBore": ("TopBoreDepth",),
    "PivotTapProfile": ("TapDrillDia",),
    CBORE_FLOOR_REFERENCE: ("CboreFloor",),
    "CarriageDrillProfile": tuple(n for i in range(1, 5) for n in (f"CarriageDrills{i}X", f"CarriageDrills{i}Y")) + ("CarriageDrills1Dia",),
    "CarriageCboreProfile": ("CarriageCounterbores1Dia",),
}
DRAWING_PRECISION = {
    feature: {name: (3 if name in ("CboreFloor", "TopBoreDepth") or name.startswith("CarriageDrills") and not name.endswith("Dia") else 2)
              for name in names}
    for feature, names in DRAWING_DIMENSIONS.items()
}
DRAWING_PRECISION_BY_NAME = {name: places for names in DRAWING_PRECISION.values() for name, places in names.items()}
CALLOUTS_ABOVE = {
    "BoreDia": "REAM H7", "TapDrillDia": "DRILL THRU",
    "CarriageDrills1Dia": "4X DRILL THRU",
    "CarriageCounterbores1Dia": "4X COUNTERBORE FROM TOP",
}
CALLOUTS_BELOW = {
    "BoreDia": "LOCATING FIT ON MHA-CH-06-TL-VN-77 SHOULDER",
    "TapDrillDia": "M8x1.25 TAP THRU BELOW SHOULDER SEAT",
    "CboreFloor": "M4x20 IN HGH15CA: 3.85 MIN ENGAGEMENT",
}
REFERENCE_SKETCHES = (CBORE_FLOOR_REFERENCE,)
ISOMETRIC_VIEW_NOTE = "RAIL 2 / QTY 1"
WALLS_MM = {
    "pivot seat to spindle end": BORE_X - BORE_DIA / 2 - BLOCK_X0,
    "carriage counterbore to side": BLOCK_WIDTH / 2 - BOLT_Y - CBORE_DIA / 2,
    "carriage counterbore to end": BLOCK_X1 - BOLT_X - CBORE_DIA / 2,
    "pivot seat to carriage counterbore": math.hypot(BORE_X + BOLT_X, BOLT_Y) - BORE_DIA / 2 - CBORE_DIA / 2,
}
assert min(WALLS_MM.values()) >= 2.0
assert 3.8 <= round(ENGAGEMENT_MIN, 6) <= round(ENGAGEMENT_MAX, 6) <= 4.95
assert PIVOT_THREAD_ENGAGEMENT >= 1.5 * 8.0
assert PIVOT_THREAD_LENGTH > PIVOT_THREAD_ENGAGEMENT
