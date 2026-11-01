"""TL-32 integral feed block, rail 1; same pivot/carriage interface as TL-22.

Nut holes are drilled to print, never transfer spotted. The nut flange seats
on the -X lug face with its long body proud; all coordinates are block-local.
The nut face's print locates the nut axis from the lug end and the bottom
face, and the four taps from that axis (``NutPatternReference``), so the
pattern holds to the spigot recess it surrounds.

Issue #290: the sheet prints decimal inch. The lug outline, the recess and the
screw clearance sit on the inch grid; the Tr8 nut's interface does not: its
Ø16 PCD and Ø10.2 spigot are the vendor's, and the nut axis closes on the
leadscrew's (``NUT_AXIS_Y`` from its lateral, ``NUT_AXIS_Z`` = its height
over the carriage top). The axis height and the flange's tap pattern belong to
that metric-only vendor line, so they print exact millimetres, labelled mm
(owner ruling 4, 2026-11-01; ``METRIC_DIMENSIONS``).
"""
from __future__ import annotations
import math
import _config
import ch_rocker_arm_tl_oblique_pivot_block_spec as pivot
import ch_rocker_arm_tl_oblique_trammel_spec as trammel
import ch_rocker_arm_tl_vn_oblique_leadscrew_spec as lead
from _hole_spec import HoleSpec, TAP_DRILL_MM, THREAD_MAJOR_MM
from _inch_wall_limits import WALL_FLOOR_MM
from _package_units import drawing_unit
from _printed_tolerance import printed_band_mm

PART_NAME = "ch-rocker-arm-tl-oblique-feed-block"
UNIT = drawing_unit(
    "parts/ch-rocker-arm-tl-oblique-feed-block",
    _config.parts("ch-rocker-arm-tl-oblique-feed-block"),
)
NUMBER = "MHA-CH-06-TL-32"
QUANTITY = 1
BLOCK_X0, BLOCK_X1 = pivot.BLOCK_X0, pivot.BLOCK_X1
BLOCK_LENGTH, BLOCK_WIDTH, BLOCK_HEIGHT = pivot.BLOCK_LENGTH, pivot.BLOCK_WIDTH, pivot.BLOCK_HEIGHT
PLAN_LUG_X = 32.766  # 1.29, the lug's -X face from the block's -X edge
LUG_WIDTH = 18.542  # .73
PLAN_OVERALL_Y = 88.138  # 3.47, +Y edge to the lug end
LUG_X0 = BLOCK_X0 + PLAN_LUG_X
LUG_X1 = LUG_X0 + LUG_WIDTH
LUG_Y1 = -BLOCK_WIDTH / 2
LUG_Y0 = BLOCK_WIDTH / 2 - PLAN_OVERALL_Y
LUG_LENGTH = LUG_Y1 - LUG_Y0
NUT_FACE_X = LUG_X0
NUT_AXIS_Y = -lead.SCREW_LATERAL
NUT_AXIS_Z = 12.4  # the leadscrew axis over the carriage top (checked below)
NUT_RECESS_DEPTH = 1.778  # .07: clears the bought nut's 1.5 spigot at .06 min
NUT_SEAT_DIA = 10.668  # .42, clears the Ø10.2 spigot
SCREW_CLEARANCE_DIA = 8.636  # .34, clears the Tr8 major
NUT_PCD = lead.NUT_HOLE_PCD  # the bought nut's Ø16
NUT_PATTERN_ANGLE = 45.0
NUT_HOLE_OFFSET = NUT_PCD / (2 * math.sqrt(2))
NUT_HOLES_YZ = tuple((NUT_AXIS_Y + dy * NUT_HOLE_OFFSET, NUT_AXIS_Z + dz * NUT_HOLE_OFFSET)
                     for dy in (-1, 1) for dz in (-1, 1))
SCREW_TAP_DEPTH = lead.NUT_SCREW_TAP_DEPTH  # .39
NUT_TAP_DRILL_DEPTH = 11.938  # .47
NUT_TAP_DRILL = TAP_DRILL_MM["#4-40"]
NUT_TAP_SPEC = HoleSpec("tapped", "#4-40", end="blind", depth_mm=NUT_TAP_DRILL_DEPTH,
                        overrides_mm={"ThreadDepth": SCREW_TAP_DEPTH})
NUT_REACH_X = (NUT_FACE_X - lead.NUT_FLANGE_THICK - lead.NUT_BODY_LONG,
               max(LUG_X1, NUT_FACE_X + lead.NUT_BODY_SHORT))
NUT_MACHINE_Z = trammel.CARRIAGE_TOP_Z + NUT_AXIS_Z
PLAN_DATUM_REFERENCE = pivot.PLAN_DATUM_REFERENCE
CBORE_FLOOR_REFERENCE = pivot.CBORE_FLOOR_REFERENCE
# B-B prints the block height from the floor sketch's interior line (TL-22,
# whose sections never imported it, prints the Block extrusion's depth on a
# standard Right view).
DRAWING_VALUES = {k: v for k, v in pivot.DRAWING_VALUES.items() if k != "BlockHeight"} | {
    "SectionBlockHeight": BLOCK_HEIGHT,
    "LugWidth": LUG_WIDTH, "PlanLugX": LUG_X0 - BLOCK_X0,
    "PlanOverallY": BLOCK_WIDTH / 2 - LUG_Y0,
    "NutSeatDia": NUT_SEAT_DIA, "NutClearanceDia": SCREW_CLEARANCE_DIA,
    "NutCentreZ": NUT_AXIS_Z, "NutCentreY": NUT_AXIS_Y - LUG_Y0,
    **{f"NutTap{i}{axis}": NUT_HOLE_OFFSET for i in range(1, 5) for axis in ("Z", "Y")},
}
# The four taps print as offsets from the nut axis: rows on the -Z column
# (taps 1 and 3), columns on the +Y row (taps 3 and 4).
NUT_PATTERN_PRINTED = ("NutCentreZ", "NutCentreY", "NutTap3Z", "NutTap4Z", "NutTap1Y", "NutTap3Y")
DRAWING_DIMENSIONS = {k: v for k, v in pivot.DRAWING_DIMENSIONS.items() if k != "Block"} | {
    CBORE_FLOOR_REFERENCE: pivot.DRAWING_DIMENSIONS[CBORE_FLOOR_REFERENCE] + ("SectionBlockHeight",),
    PLAN_DATUM_REFERENCE: pivot.DRAWING_DIMENSIONS[PLAN_DATUM_REFERENCE] + ("PlanLugX", "PlanOverallY"),
    "LugProfile": ("LugWidth",),
    "NutSeatProfile": ("NutSeatDia",),
    "NutClearanceProfile": ("NutClearanceDia",),
    "NutPatternReference": NUT_PATTERN_PRINTED,
}
# The nut axis and its pattern are the bought nut's interface: three places.
# The axis is the leadscrew's closure (not on the .01 grid) and its height
# has only the spigot's float in the recess to take up error: KP08 floats
# in X/Y on its bracket, never in Z. The axis height and the tap pattern are
# the Tr8/KP08 vendor line's: exact millimetres with the millimetre title
# block's three-place band (owner ruling 4).
NUT_PATTERN_PLACES = 3
NUT_SEAT_PLACES = 2
METRIC_UNIT = "mm"
METRIC_BAND = printed_band_mm(NUT_PATTERN_PLACES, unit=METRIC_UNIT)  # 0.13
METRIC_DIMENSIONS = {
    ("NutPatternReference", name): (NUT_PATTERN_PLACES, METRIC_BAND)
    for name in ("NutCentreZ", "NutTap3Z", "NutTap4Z", "NutTap1Y", "NutTap3Y")
}
# The leadscrew clearance is drilled: inch drill sizes print three places.
THREE_PLACE_DIMENSIONS = pivot.THREE_PLACE_DIMENSIONS | {"NutClearanceDia"}
DRAWING_PRECISION = {k: v for k, v in pivot.DRAWING_PRECISION.items() if k != "Block"} | {
    feature: {
        name: (3 if name in THREE_PLACE_DIMENSIONS or feature == "NutPatternReference" else 2)
        for name in DRAWING_DIMENSIONS[feature]
    }
    for feature in (CBORE_FLOOR_REFERENCE, PLAN_DATUM_REFERENCE, "LugProfile", "NutSeatProfile",
                    "NutClearanceProfile", "NutPatternReference")
}
DRAWING_PRECISION_BY_NAME = {
    name: places for dimensions in DRAWING_PRECISION.values()
    for name, places in dimensions.items()
}
assert DRAWING_PRECISION_BY_NAME["NutTap3Z"] == DRAWING_PRECISION_BY_NAME["NutCentreY"] == NUT_PATTERN_PLACES
assert DRAWING_PRECISION_BY_NAME["NutSeatDia"] == NUT_SEAT_PLACES
# The #4-40 taps' Hole Wizard callout: the number drill at three places, the
# drill and thread depths at the title block's two.
NUT_TAP_CALLOUT_PRECISION = {"hw-tapdrldia": 3, "hw-tapdrldepth": 2, "hw-threaddepth": 2}


def _inch_text(value_in: float, places: int) -> str:
    """An inch length as the sheet prints it: ``.059``."""
    return f"{value_in:.{places}f}".removeprefix("0")


# Rule 17 shortfall, stated on the sheet (rule 20): the Ø16 PCD is the bought
# nut's, so a #4-40 major sits close to the spigot recess at nominal; no
# recess that still clears the Ø10.2 spigot reaches the .060 floor. Worst
# case: the recess at its upper .XX limit, each tap off the axis by its
# 0.13 mm band in both Y and Z.
NUT_TAP_MAJOR = THREAD_MAJOR_MM["#4-40"]
_PATTERN_BAND = METRIC_BAND
NUT_SEAT_WALL_NOMINAL = NUT_PCD / 2 - NUT_SEAT_DIA / 2 - NUT_TAP_MAJOR / 2
NUT_SEAT_WALL_MIN = (
    NUT_PCD / 2
    - math.hypot(_PATTERN_BAND, _PATTERN_BAND)
    - (NUT_SEAT_DIA + printed_band_mm(NUT_SEAT_PLACES, unit=UNIT)) / 2
    - NUT_TAP_MAJOR / 2
)
# A MIN printed to .XXX never overstates the worst case.
NUT_SEAT_WALL_TEXT = f"WALL {_inch_text(math.floor(NUT_SEAT_WALL_MIN / 25.4 * 1000) / 1000, 3)} MIN TO 4-40 TAPS"
assert 0.0 < NUT_SEAT_WALL_MIN < NUT_SEAT_WALL_NOMINAL < WALL_FLOOR_MM
assert NUT_PCD / 2 - lead.NUT_BODY_DIA / 2 - NUT_TAP_MAJOR / 2 < WALL_FLOOR_MM
# The recess clears the bought spigot at its least size and depth; the bore
# clears the screw.
assert NUT_SEAT_DIA - printed_band_mm(NUT_SEAT_PLACES, unit=UNIT) > lead.NUT_BODY_DIA
assert NUT_RECESS_DEPTH - printed_band_mm(NUT_SEAT_PLACES, unit=UNIT) > lead.NUT_BODY_SHORT
assert SCREW_CLEARANCE_DIA - printed_band_mm(2, unit=UNIT) > lead.SCREW_MAJOR_DIA
# The flange screws stop inside the full thread at its shallowest.
assert SCREW_TAP_DEPTH - printed_band_mm(2, unit=UNIT) > lead.NUT_SCREW_ENGAGEMENT
CALLOUTS_SUFFIX = dict(pivot.CALLOUTS_SUFFIX) | {
    "NutSeatDia": f" <HOLE-DEPTH> {_inch_text(NUT_RECESS_DEPTH / 25.4, NUT_SEAT_PLACES)}",
}
CALLOUTS_ABOVE = dict(pivot.CALLOUTS_ABOVE) | {"NutClearanceDia": "DRILL THRU"}
CALLOUTS_BELOW = dict(pivot.CALLOUTS_BELOW) | {
    "NutSeatDia": f"SPIGOT CLEARANCE: TL-VN-55 NUT\n{NUT_SEAT_WALL_TEXT}",
    "NutClearanceDia": "LEADSCREW CLEARANCE",
    "NutCentreZ": "FROM BOTTOM FACE\nON KP08 LEADSCREW AXIS",
    "NutCentreY": "ON LEADSCREW AXIS",
}
NUT_FLANGE_MATE_TEXT = "MATCHES TL-VN-55 NUT FLANGE"
REFERENCE_SKETCHES = pivot.REFERENCE_SKETCHES + ("NutPatternReference",)
# The flange rim remains within the full-height lug.
assert NUT_AXIS_Z - lead.NUT_FLANGE_DIA / 2 >= 0
assert NUT_AXIS_Z + lead.NUT_FLANGE_DIA / 2 <= BLOCK_HEIGHT
assert -NUT_AXIS_Y + lead.NUT_FLANGE_DIA / 2 + 2 <= -LUG_Y0
assert LUG_Y0 < min(y for y, _z in NUT_HOLES_YZ) and max(y for y, _z in NUT_HOLES_YZ) < LUG_Y1
assert BLOCK_WIDTH / 2 - LUG_Y0 < pivot.STOCK_WIDTH
assert abs(NUT_MACHINE_Z - lead.SCREW_AXIS_Z) < 1e-6
assert NUT_FACE_X + SCREW_TAP_DEPTH < LUG_X1
assert NUT_TAP_DRILL_DEPTH + NUT_TAP_DRILL / 2 * 0.60086 < LUG_WIDTH
# Travel-end clearance includes the proud purchased nut, not only the lug.
for _box in lead.KP08_BOXES.values():
    for _station in trammel.CARRIAGE_TRAVEL:
        _lo, _hi = _station + NUT_REACH_X[0], _station + NUT_REACH_X[1]
        assert max(_box[0] - _hi, _lo - _box[1]) >= lead.FEED_GAP
