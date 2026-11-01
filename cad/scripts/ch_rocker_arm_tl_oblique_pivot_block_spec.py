"""TL-22: one plain shoulder-screw block on rail 2.

Frame: carriage-pattern centre, bottom Z0; +X away from spindle. New
6061 1 x 3-1/2 inch stock is shared with TL-32. No cartridge hardware.
The print locates every X from the -X (left) edge, never from the frame
centre: ``PLAN_DATUM_REFERENCE`` carries those ordinates.

Issue #290: the sheet prints decimal inch. Lengths stay physical millimetres,
each fabricated nominal the exact millimetres of its printed inch value. Exempt:
the HGH15CA's 26 x 26 M4 pattern (vendor), and the seat's station
``BORE_X``, the trammel calculator's ``PIN_OFFSET`` (kinematic). The -X edge
puts the seat station on the .XX grid; the hole columns print the
three-place rounding of their exact vendor offsets from it.

The seat takes the TL-VN-77 inch shoulder screw (owner ruling 2026-10-30: the
metric shop tap becomes an extended-thread 5/16-18 precision shoulder screw): a
.375 REAM_SLIDE seat on the owned .3760 reamer, and a 5/16-18 tap through
below it. The shop cuts the screw's thread to length so that its full-form
engagement meets 1.5D and its tip stands inside the block at every band.
"""
from __future__ import annotations

import math

import _config
import ch_rocker_arm_tl_vn_oblique_pivot_screw_spec as pivot_screw
from _fit_deviations import deviations
from _fit_ream_slide import REAM_SLIDE
from _hole_spec import TAP_DRILL_MM
from _inch_wall_limits import WALL_TARGET_MM
from _package_units import drawing_unit
from _printed_tolerance import printed_band_mm

PART_NAME = "ch-rocker-arm-tl-oblique-pivot-block"
UNIT = drawing_unit(
    "parts/ch-rocker-arm-tl-oblique-pivot-block",
    _config.parts("ch-rocker-arm-tl-oblique-pivot-block"),
)
NUMBER = "MHA-CH-06-TL-22"
QUANTITY = 1
BORE_X, BORE_Y = -32.0, 0.0  # trammel PIN_OFFSET: kinematic, not snapped
PLAN_BORE_X = 9.906  # .39, the seat from the -X edge
BLOCK_X0 = BORE_X - PLAN_BORE_X
BLOCK_LENGTH = 61.976  # 2.44
BLOCK_X1 = BLOCK_X0 + BLOCK_LENGTH
BLOCK_WIDTH = 40.132  # 1.58
BLOCK_HEIGHT = 24.384  # .96
STOCK_THICKNESS, STOCK_WIDTH = 25.4, 88.9
# The TL-VN-77 shoulder bottoms on the seat floor, so the 3-place depth sets
# how high the screw stands, hence the head-to-carrier gap the assembly's
# shim selection then trims (jig assembly ``PIVOT_RUNNING_GAP``). Shallow
# enough that the unshimmed gap is open at every band; shims, which only
# close it, are the fitting adjustment.
BORE_DIA = 9.525  # .375
BORE_BAND = REAM_SLIDE  # .3760-.3765 on the owned .3760 reamer
BORE_PLACES = 4
BORE_DEPTH = 9.1186  # .359
_bore_lower, _bore_upper = deviations(BORE_BAND)
_shoulder_lower, _shoulder_upper = deviations(pivot_screw.SHOULDER_DIA_BAND)
BORE_LIMITS = (BORE_DIA + _bore_lower, BORE_DIA + _bore_upper)
PIVOT_LOCATING_CLEARANCE_MIN = BORE_LIMITS[0] - (pivot_screw.SHOULDER_DIA + _shoulder_upper)
PIVOT_LOCATING_CLEARANCE_MAX = BORE_LIMITS[1] - (pivot_screw.SHOULDER_DIA + _shoulder_lower)
if PIVOT_LOCATING_CLEARANCE_MIN <= 0.0:
    raise AssertionError("purchased pivot shoulder does not clear its block seat")
PIVOT_TAP = pivot_screw.THREAD
PIVOT_TAP_DRILL = TAP_DRILL_MM[PIVOT_TAP]
PIVOT_THREAD_LENGTH = BLOCK_HEIGHT - BORE_DEPTH
PIVOT_AXIS_NAME = "PivotAxis"
BOLT_X = BOLT_Y = 13.0  # HGH15CA 26 x 26 M4 pattern (vendor)
BOLT_POINTS = tuple((x, y) for x in (-BOLT_X, BOLT_X) for y in (-BOLT_Y, BOLT_Y))
HOLE_DIA = 4.572  # .18, M4 clearance
CBORE_DIA = 7.874  # .31, M4 socket head
# .614: the M4 x 20 keeps its 1.1D nominal reach (20 mm less .614 in is at
# least 4.4 mm) and, long and floor-low at their bands, still stops short of
# the M4 x 5 thread end.
CBORE_FLOOR = 15.5956  # .614
CBORE_DEPTH = BLOCK_HEIGHT - CBORE_FLOOR
CBORE_FLOOR_REFERENCE = "CboreFloorReference"
CARRIAGE_THREAD_DEPTH = 5.0  # the HGH15CA's M4 x 5 (vendor)
CBORE_SECTION_PLANE = "CboreSectionPlane"
CBORE_SECTION_X = BOLT_X  # B-B cuts the +X hole column
# B-B's block height: its own sketch on a plane just behind the cut, inside
# the material B-B keeps (it looks toward -X).
BLOCK_HEIGHT_REFERENCE = "BlockHeightReference"
BLOCK_HEIGHT_PLANE = "BlockHeightPlane"
BLOCK_HEIGHT_SECTION_X = CBORE_SECTION_X - 0.5
# Hidden construction sketch on the top face: a line on the -X edge and
# circles on the bore and one hole per column, so the plan's X ordinates start
# on that edge (rule 10) while staying model dimensions.
PLAN_DATUM_REFERENCE = "PlanDatumReference"
PLAN_DATUM_HOLES = ((-BOLT_X, BOLT_Y), (BOLT_X, BOLT_Y))
DRAWING_VALUES = {
    "BlockLength": BLOCK_LENGTH, "BlockWidth": BLOCK_WIDTH,
    "BlockHeight": BLOCK_HEIGHT, "SectionBlockHeight": BLOCK_HEIGHT, "BlockSideY": BLOCK_WIDTH / 2,
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
    # Marked for B-B's import experiment (farm round 7); not printed.
    "Block": ("BlockHeight",),
    "TopBoreProfile": ("BoreDia",),
    "TopBore": ("TopBoreDepth",),
    "PivotTapProfile": ("TapDrillDia",),
    CBORE_FLOOR_REFERENCE: ("CboreFloor",),
    BLOCK_HEIGHT_REFERENCE: ("SectionBlockHeight",),
    "CarriageDrillProfile": ("CarriageDrills3Y", "CarriageDrills4Y", "CarriageDrills1Dia"),
    "CarriageCboreProfile": ("CarriageCounterbores3Dia",),
    PLAN_DATUM_REFERENCE: ("PlanBoreX", "PlanHole1X", "PlanHole2X"),
}
# Three places: the carriage pattern's fits, the seat depth and counterbore
# floor that set the stacks, the tap drill's letter size, and the drilled
# clearance holes (inch drill sizes print three places; the DRILLED HOLES row
# bands them).
THREE_PLACE_DIMENSIONS = frozenset({
    "CboreFloor", "TopBoreDepth", "TapDrillDia", "CarriageDrills3Y", "CarriageDrills4Y",
    "PlanHole1X", "PlanHole2X", "CarriageDrills1Dia",
})


def _places(name: str) -> int:
    if name == "BoreDia":
        return BORE_PLACES
    return 3 if name in THREE_PLACE_DIMENSIONS else 2


DRAWING_PRECISION = {
    feature: {name: _places(name) for name in names}
    for feature, names in DRAWING_DIMENSIONS.items()
}
DRAWING_PRECISION_BY_NAME = {name: places for names in DRAWING_PRECISION.values() for name, places in names.items()}


def _band(name: str) -> float:
    return printed_band_mm(DRAWING_PRECISION_BY_NAME[name], unit=UNIT)


# The outline sets the counterbore walls (rule 17, worst case at the printed
# bands): the +X end wall through BlockLength less the hole column, the -Y side
# wall through BlockWidth less BlockSideY and the row. At .X (±.1) both would
# fall under the floor, so both print at two places and their callouts name
# the wall they set.
_CBORE_R_MAX = (CBORE_DIA + _band("CarriageCounterbores3Dia")) / 2
_ROW_BAND = max(_band(name) for name in ("CarriageDrills3Y", "CarriageDrills4Y"))
CBORE_END_WALL_MIN = BLOCK_X1 - BOLT_X - _CBORE_R_MAX - _band("BlockLength") - _band("PlanHole2X")
CBORE_SIDE_WALL_MIN = (BLOCK_WIDTH / 2 - BOLT_Y - _CBORE_R_MAX - _ROW_BAND
                       - _band("BlockWidth") - _band("BlockSideY"))
# The M4 x 20 carriage screws' reach into the HGH15CA's M4 x 5 holes.
SCREW_LENGTH, SCREW_LENGTH_TOL = 20.0, 0.42
ENGAGEMENT_MIN = SCREW_LENGTH - SCREW_LENGTH_TOL - CBORE_FLOOR - _band("CboreFloor")
ENGAGEMENT_MAX = SCREW_LENGTH + SCREW_LENGTH_TOL - CBORE_FLOOR + _band("CboreFloor")
ENGAGEMENT_TEXT = f"{math.floor(ENGAGEMENT_MIN / 25.4 * 1000.0) / 1000.0:.3f}".lstrip("0")
# The cut screw in its tap: full-form engagement (rule 18) is the cut thread
# less 1.5 incomplete pitches; the tip stands inside the block at every band
# (block height at .XX, seat depth and cut length at .XXX).
_CUT_MIN = pivot_screw.CUT_THREAD_LENGTH - printed_band_mm(pivot_screw.CUT_THREAD_PLACES, unit=pivot_screw.UNIT)
_CUT_MAX = pivot_screw.CUT_THREAD_LENGTH + printed_band_mm(pivot_screw.CUT_THREAD_PLACES, unit=pivot_screw.UNIT)
PIVOT_THREAD_ENGAGEMENT = pivot_screw.CUT_THREAD_LENGTH - 1.5 * pivot_screw.THREAD_PITCH
PIVOT_THREAD_ENGAGEMENT_MIN = _CUT_MIN - 1.5 * pivot_screw.THREAD_PITCH
PIVOT_TIP_CLEARANCE = BLOCK_HEIGHT - BORE_DEPTH - pivot_screw.CUT_THREAD_LENGTH
PIVOT_TIP_CLEARANCE_MIN = (BLOCK_HEIGHT - _band("SectionBlockHeight")
                           - (BORE_DEPTH + _band("TopBoreDepth")) - _CUT_MAX)
CALLOUTS_SUFFIX: dict[str, str] = {}
CALLOUTS_ABOVE = {
    "BoreDia": "REAM", "TapDrillDia": "DRILL THRU",
    "CarriageDrills1Dia": "4X DRILL THRU",
    "CarriageCounterbores3Dia": "4X COUNTERBORE FROM TOP",
}
CALLOUTS_BELOW = {
    "BoreDia": "LOCATING FIT ON MHA-CH-06-TL-VN-77 SHOULDER",
    "TapDrillDia": f"{PIVOT_TAP} UNC TAP THRU BELOW SHOULDER SEAT",
    "TopBoreDepth": "SETS TL-VN-77 SHOULDER HEIGHT",
    "CarriageDrills1Dia": "MATCHES HGH15CA CARRIAGE M4 PATTERN",
    "CarriageCounterbores3Dia": "FLOOR: SECTION B-B",
    # Under the value, two rows, right of B-B (an above-text newline dropped
    # the note, farm run 20261027T175531766Z): the block height's extension
    # lines pass left of it.
    "CboreFloor": f"M4x20 IN HGH15CA:\n{ENGAGEMENT_TEXT} MIN ENGAGEMENT",
    "BlockLength": "SETS COUNTERBORE END WALL",
    # Two narrow rows between the row (CarriageDrills3Y/4Y) values and the
    # BlockSideY and TL-32 PlanOverallY dimension lines (x 231 and 285 on TL-32's
    # sheet). One 26-character row spanned x 225..294 and met all three
    # (layout audit, farm run 20261031T200222206Z).
    "BlockWidth": "SETS COUNTERBORE\nSIDE WALL",
}
REFERENCE_SKETCHES = (CBORE_FLOOR_REFERENCE, BLOCK_HEIGHT_REFERENCE, PLAN_DATUM_REFERENCE)
WALLS_MM = {
    "pivot seat to spindle end": BORE_X - BORE_LIMITS[1] / 2 - BLOCK_X0,
    "carriage counterbore to side": BLOCK_WIDTH / 2 - BOLT_Y - CBORE_DIA / 2,
    "carriage counterbore to end": BLOCK_X1 - BOLT_X - CBORE_DIA / 2,
    "pivot seat to carriage counterbore": math.hypot(BORE_X + BOLT_X, BOLT_Y) - BORE_LIMITS[1] / 2 - CBORE_DIA / 2,
}
assert min(WALLS_MM.values()) >= WALL_TARGET_MM
assert CBORE_END_WALL_MIN >= WALL_TARGET_MM
assert CBORE_SIDE_WALL_MIN >= WALL_TARGET_MM
# 0.045: the worst-case reach margin, the long screw at the low floor still
# stopping short of the carriage's M4 x 5 thread end.
assert 3.8 <= round(ENGAGEMENT_MIN, 6) <= round(ENGAGEMENT_MAX, 6) <= CARRIAGE_THREAD_DEPTH - 0.045
assert PIVOT_TAP_DRILL < BORE_LIMITS[0]
# Rule 18 at the worst case, and the tip inside the block (.011 minimum).
assert PIVOT_THREAD_ENGAGEMENT_MIN >= 1.5 * pivot_screw.THREAD_DIA
assert PIVOT_TIP_CLEARANCE_MIN >= 0.011 * 25.4 - 1e-9
