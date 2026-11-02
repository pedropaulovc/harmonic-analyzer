"""TL-32 integral feed block, rail 1; same pivot/carriage interface as TL-22.

Nut holes are drilled to print, never transfer spotted. The shop-made TL-27
feed nut (``ch_rocker_arm_tl_oblique_feed_nut_spec``, owner ruling
2026-11-01, item 4) seats on the -X lug face, proud toward the spindle, on two
#4-40 X 3/4 SHCS through its loose holes into the lug's two #4-40 taps,
tapped THRU (ruling C1); all coordinates are block-local. The nut face's
print locates the leadscrew axis from the lug end and the bottom face, the
first tap from that axis and the second from the first
(``NutPatternReference``), the pair's .680 matching the nut's (ruling B1).

Issue #290: the sheet prints decimal inch. The lug outline, the screw
clearance and the taps sit on the inch grid; the axis closes on the
leadscrew's (``NUT_AXIS_Y`` from its lateral, ``NUT_AXIS_Z`` = its height
over the carriage top). The axis height belongs to the metric-only KP08
vendor line, so it prints exact millimetres, labelled mm (owner ruling 4,
2026-11-01; ``METRIC_DIMENSIONS``).
"""
from __future__ import annotations
import math
import _config
import ch_rocker_arm_tl_oblique_feed_nut_spec as feed_nut
import ch_rocker_arm_tl_oblique_pivot_block_spec as pivot
import ch_rocker_arm_tl_oblique_trammel_spec as trammel
import ch_rocker_arm_tl_vn_oblique_leadscrew_spec as lead
from _hole_spec import HoleSpec, TAP_DRILL_MM, THREAD_MAJOR_MM
from _inch_wall_limits import WALL_TARGET_MM
from _package_units import drawing_unit
from _printed_tolerance import drilled_oversize_mm, printed_band_mm

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
SCREW_CLEARANCE_DIA = 8.636  # .34, clears the Tr8 major
# The nut's screw pair: the first tap toward the lug end, .34 from the axis;
# the second .680 from the first, the nut's own spacing (ruling B1).
NUT_TAP_OFFSET = feed_nut.HOLE_OFFSET
NUT_TAP_SPACING = feed_nut.HOLE_SPACING
NUT_HOLES_YZ = (
    (NUT_AXIS_Y - NUT_TAP_OFFSET, NUT_AXIS_Z),
    (NUT_AXIS_Y - NUT_TAP_OFFSET + NUT_TAP_SPACING, NUT_AXIS_Z),
)
NUT_TAP_SPEC = HoleSpec("tapped", feed_nut.SCREW_THREAD, end="through_all")
NUT_TAP_DRILL = TAP_DRILL_MM[feed_nut.SCREW_THREAD]
# The nut, its screw heads and the lug, along X from the lug's -X face.
NUT_REACH_X = (NUT_FACE_X - feed_nut.REACH, LUG_X1)
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
    "NutClearanceDia": SCREW_CLEARANCE_DIA,
    "NutCentreZ": NUT_AXIS_Z, "NutCentreY": NUT_AXIS_Y - LUG_Y0,
    "NutTap1Y": NUT_TAP_OFFSET, "NutTapSpacing": NUT_TAP_SPACING,
}
# VIEW D prints the axis from the lug end and the bottom face, the first tap
# from the axis and the second from the first.
NUT_PATTERN_PRINTED = ("NutCentreZ", "NutCentreY", "NutTap1Y", "NutTapSpacing")
DRAWING_DIMENSIONS = {k: v for k, v in pivot.DRAWING_DIMENSIONS.items() if k != "Block"} | {
    CBORE_FLOOR_REFERENCE: pivot.DRAWING_DIMENSIONS[CBORE_FLOOR_REFERENCE] + ("SectionBlockHeight",),
    PLAN_DATUM_REFERENCE: pivot.DRAWING_DIMENSIONS[PLAN_DATUM_REFERENCE] + ("PlanLugX", "PlanOverallY"),
    "LugProfile": ("LugWidth",),
    "NutClearanceProfile": ("NutClearanceDia",),
    "NutPatternReference": NUT_PATTERN_PRINTED,
}
# The axis is the leadscrew's closure (not on the .01 grid): three places;
# its height is the KP08 vendor line's, exact millimetres with the millimetre
# title block's three-place band (owner ruling 4). The pair's spacing is the
# nut's fixed-fastener fit: three places; the first tap's offset from the
# axis sets only walls: two.
NUT_PATTERN_PLACES = 3
NUT_TAP_OFFSET_PLACES = feed_nut.HOLE_OFFSET_PLACES
METRIC_UNIT = "mm"
METRIC_BAND = printed_band_mm(NUT_PATTERN_PLACES, unit=METRIC_UNIT)  # 0.13
METRIC_DIMENSIONS = {("NutPatternReference", "NutCentreZ"): (NUT_PATTERN_PLACES, METRIC_BAND)}
# The leadscrew clearance is drilled: inch drill sizes print three places.
THREE_PLACE_DIMENSIONS = pivot.THREE_PLACE_DIMENSIONS | {
    "NutClearanceDia", "NutCentreZ", "NutCentreY", "NutTapSpacing",
}
DRAWING_PRECISION = {k: v for k, v in pivot.DRAWING_PRECISION.items() if k != "Block"} | {
    feature: {
        name: (3 if name in THREE_PLACE_DIMENSIONS else 2)
        for name in DRAWING_DIMENSIONS[feature]
    }
    for feature in (CBORE_FLOOR_REFERENCE, PLAN_DATUM_REFERENCE, "LugProfile",
                    "NutClearanceProfile", "NutPatternReference")
}
DRAWING_PRECISION_BY_NAME = {
    name: places for dimensions in DRAWING_PRECISION.values()
    for name, places in dimensions.items()
}
assert DRAWING_PRECISION_BY_NAME["NutCentreY"] == DRAWING_PRECISION_BY_NAME["NutCentreZ"] == NUT_PATTERN_PLACES
assert DRAWING_PRECISION_BY_NAME["NutTapSpacing"] == feed_nut.HOLE_SPACING_PLACES
assert DRAWING_PRECISION_BY_NAME["NutTap1Y"] == NUT_TAP_OFFSET_PLACES
CALLOUTS_SUFFIX = dict(pivot.CALLOUTS_SUFFIX)
CALLOUTS_ABOVE = dict(pivot.CALLOUTS_ABOVE) | {"NutClearanceDia": "DRILL THRU"}
NUT_MATE_TEXT = "MATCHES TL-27 FEED NUT"
CALLOUTS_BELOW = dict(pivot.CALLOUTS_BELOW) | {
    "NutClearanceDia": "LEADSCREW CLEARANCE",
    # r2 review: "BOTTOM" named no face a view defines; the face the
    # counterbored screws pull onto the HGH15CA carriage does.
    "NutCentreZ": "FROM CARRIAGE FACE\nON KP08 LEADSCREW AXIS",
    "NutCentreY": "ON KP08 LEADSCREW AXIS",
    "NutTapSpacing": NUT_MATE_TEXT,
}
REFERENCE_SKETCHES = pivot.REFERENCE_SKETCHES + ("NutPatternReference",)

# --- Fit-up (ruling B1): the nut's loose holes float a #4 over both pairs ------
# The nut rides the leadscrew and the KP08s float laterally, so only the
# pair's spacing and its height on the axis line must meet the nut's: each
# screw sees half the two spacing bands along the pair, and both parts' pair
# heights (the nut's three-place line, the lug's 12.400 ±.13 mm axis) across.
NUT_SPACING_BAND = printed_band_mm(feed_nut.HOLE_SPACING_PLACES, unit=UNIT)
FIT_UP_Y = (feed_nut.PAIR_BAND + NUT_SPACING_BAND) / 2.0
FIT_UP_Z = feed_nut.PAIR_BAND + METRIC_BAND
FIT_UP_RESIDUAL = math.hypot(FIT_UP_Y, FIT_UP_Z)  # .0113
assert feed_nut.NORMAL_HOLE_FLOAT < FIT_UP_RESIDUAL <= feed_nut.HOLE_FLOAT

# --- Rule 17: lug walls at the printed worst case (.080 target) -----------------
NUT_TAP_MAJOR = THREAD_MAJOR_MM[feed_nut.SCREW_THREAD]
_OFFSET_BAND = printed_band_mm(NUT_TAP_OFFSET_PLACES, unit=UNIT)  # .01
_AXIS_Y_BAND = printed_band_mm(NUT_PATTERN_PLACES, unit=UNIT)  # .005
_CLEARANCE_R = (SCREW_CLEARANCE_DIA + drilled_oversize_mm(unit=UNIT)) / 2
LUG_WALLS_MM = {
    "tap 1 to the leadscrew clearance": NUT_TAP_OFFSET - _OFFSET_BAND - NUT_TAP_MAJOR / 2 - _CLEARANCE_R,
    "tap 2 to the leadscrew clearance": (NUT_TAP_SPACING - NUT_TAP_OFFSET)
    - (_OFFSET_BAND + NUT_SPACING_BAND) - NUT_TAP_MAJOR / 2 - _CLEARANCE_R,
    "tap 1 to the lug end": (NUT_AXIS_Y - LUG_Y0) - _AXIS_Y_BAND - NUT_TAP_OFFSET - _OFFSET_BAND
    - NUT_TAP_MAJOR / 2,
    "taps to the bottom face": NUT_AXIS_Z - METRIC_BAND - NUT_TAP_MAJOR / 2,
    "taps to the top face": BLOCK_HEIGHT - NUT_AXIS_Z - METRIC_BAND - NUT_TAP_MAJOR / 2,
}
assert min(LUG_WALLS_MM.values()) >= WALL_TARGET_MM, LUG_WALLS_MM
# The leadscrew clearance clears the screw at its least size.
assert SCREW_CLEARANCE_DIA - printed_band_mm(3, unit=UNIT) > lead.SCREW_MAJOR_DIA
# The nut screws' tips stop inside the THRU tap (the shortest nut, the
# longest screw: B18.3 never long).
assert feed_nut.SCREW_TIP_REACH_MAX < LUG_WIDTH
# The nut stands within the lug's height; it overhangs the lug end by
# NUT_OVERHANG (.105) and stays off the block body.
NUT_Y = (NUT_AXIS_Y - (feed_nut.WIDTH - feed_nut.BORE_X), NUT_AXIS_Y + feed_nut.BORE_X)
NUT_Z = (NUT_AXIS_Z - feed_nut.BORE_Y, NUT_AXIS_Z - feed_nut.BORE_Y + feed_nut.HEIGHT)
NUT_OVERHANG = LUG_Y0 - NUT_Y[0]
assert 0.0 <= NUT_Z[0] and NUT_Z[1] <= BLOCK_HEIGHT
assert NUT_Y[1] < LUG_Y1
assert BLOCK_WIDTH / 2 - LUG_Y0 < pivot.STOCK_WIDTH
assert abs(NUT_MACHINE_Z - lead.SCREW_AXIS_Z) < 1e-6
# Travel-end clearance includes the proud nut and its screw heads, not only
# the lug, at the longest nut.
FEED_GAPS = {
    (name, station): max(box[0] - (station + NUT_REACH_X[1]), (station + NUT_REACH_X[0]) - box[1])
    for name, box in lead.KP08_BOXES.items()
    for station in trammel.CARRIAGE_TRAVEL
}
assert min(FEED_GAPS.values()) >= lead.FEED_GAP, FEED_GAPS
