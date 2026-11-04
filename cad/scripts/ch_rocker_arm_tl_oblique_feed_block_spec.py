"""TL-32 integral feed block, rail 1; same pivot/carriage interface as TL-22.

The shop-made TL-27 feed nut (``ch_rocker_arm_tl_oblique_feed_nut_spec``,
owner ruling 2026-11-01, item 4) seats on the -X lug face, proud toward the
spindle, on two #4-40 X 3/4 flanged BHCS through its loose holes into the
lug's two #4-40 taps, tapped THRU (ruling C1); one 3/32 dowel
(MHA-CH-06-TL-VN-81), pressed in the nut, slips into the lug's #41 hole
drilled THRU; all coordinates are block-local. The taps and the dowel hole
are transferred through TL-27 at TL-00 assembly, with the nut threaded on the
aligned leadscrew (Main ruling 2026-11-03, Codjiflo P1 on #2112): the sheet
prints the taps as REF stations under that transfer callout, and the dowel
hole's size with its own. The nut face's print locates the leadscrew
clearance from the lug end and the carriage face (``NutPatternReference``).

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
import ch_rocker_arm_tl_oblique_end_bracket_spec as end_bracket
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
SCREW_CLEARANCE_DIA = 9.525  # .375, clears the Tr8 major at the vertical stack
# The nut's screw pair and dowel, transferred from the nut: at its stations
# from the axis (each tap on the axis, never on the other tap).
NUT_TAP_OFFSET = feed_nut.HOLE_OFFSET
NUT_HOLES_YZ = (
    (NUT_AXIS_Y - NUT_TAP_OFFSET, NUT_AXIS_Z),
    (NUT_AXIS_Y + NUT_TAP_OFFSET, NUT_AXIS_Z),
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
    "NutTap1Y": NUT_TAP_OFFSET, "NutTap2Y": NUT_TAP_OFFSET,
    "NutDowelDia": 0.096 * 25.4,
}
# VIEW D prints the clearance from the lug end and the carriage face, and each
# transferred tap's station from it REF (REF_DIMENSIONS); the dowel hole's
# transfer callout locates it.
NUT_PATTERN_PRINTED = ("NutCentreZ", "NutCentreY", "NutTap1Y", "NutTap2Y")
REF_DIMENSIONS = ("NutTap1Y", "NutTap2Y")
DRAWING_DIMENSIONS = {k: v for k, v in pivot.DRAWING_DIMENSIONS.items() if k != "Block"} | {
    CBORE_FLOOR_REFERENCE: pivot.DRAWING_DIMENSIONS[CBORE_FLOOR_REFERENCE] + ("SectionBlockHeight",),
    PLAN_DATUM_REFERENCE: pivot.DRAWING_DIMENSIONS[PLAN_DATUM_REFERENCE] + ("PlanLugX", "PlanOverallY"),
    "LugProfile": ("LugWidth",),
    "NutClearanceProfile": ("NutClearanceDia",),
    "NutDowelProfile": ("NutDowelDia",),
    "NutPatternReference": NUT_PATTERN_PRINTED,
}
# The axis is the leadscrew's closure (not on the .01 grid): three places;
# its height is the KP08 vendor line's, exact millimetres with the millimetre
# title block's three-place band (owner ruling 4). The transferred stations
# print the nut's own places, REF.
NUT_PATTERN_PLACES = 3
NUT_TAP_OFFSET_PLACES = feed_nut.HOLE_OFFSET_PLACES
METRIC_UNIT = "mm"
METRIC_BAND = printed_band_mm(NUT_PATTERN_PLACES, unit=METRIC_UNIT)  # 0.13
METRIC_DIMENSIONS = {("NutPatternReference", "NutCentreZ"): (NUT_PATTERN_PLACES, METRIC_BAND)}
# The leadscrew clearance is drilled: inch drill sizes print three places.
THREE_PLACE_DIMENSIONS = pivot.THREE_PLACE_DIMENSIONS | {
    "NutClearanceDia", "NutCentreZ", "NutCentreY", "NutDowelDia",
}
DRAWING_PRECISION = {k: v for k, v in pivot.DRAWING_PRECISION.items() if k != "Block"} | {
    feature: {
        name: (3 if name in THREE_PLACE_DIMENSIONS else 2)
        for name in DRAWING_DIMENSIONS[feature]
    }
    for feature in (CBORE_FLOOR_REFERENCE, PLAN_DATUM_REFERENCE, "LugProfile",
                    "NutClearanceProfile", "NutDowelProfile", "NutPatternReference")
}
DRAWING_PRECISION_BY_NAME = {
    name: places for dimensions in DRAWING_PRECISION.values()
    for name, places in dimensions.items()
}
assert DRAWING_PRECISION_BY_NAME["NutCentreY"] == DRAWING_PRECISION_BY_NAME["NutCentreZ"] == NUT_PATTERN_PLACES
assert DRAWING_PRECISION_BY_NAME["NutTap1Y"] == DRAWING_PRECISION_BY_NAME["NutTap2Y"] == NUT_TAP_OFFSET_PLACES
CALLOUTS_SUFFIX = dict(pivot.CALLOUTS_SUFFIX)
CALLOUTS_ABOVE = dict(pivot.CALLOUTS_ABOVE) | {
    "NutClearanceDia": "DRILL THRU",
    "NutDowelDia": "#41 DRILL THRU",
}
CALLOUTS_BELOW = dict(pivot.CALLOUTS_BELOW) | {
    "NutClearanceDia": "LEADSCREW CLEARANCE",
    "NutDowelDia": f"TRANSFER THROUGH {feed_nut.NUMBER}\nAT ASSEMBLY\nSLIP FIT ON MHA-CH-06-TL-VN-81",
    # r2 review: "BOTTOM" named no face a view defines; the face the
    # counterbored screws pull onto the HGH15CA carriage does.
    "NutCentreZ": "FROM CARRIAGE FACE\nON KP08 LEADSCREW AXIS",
    "NutCentreY": "ON KP08 LEADSCREW AXIS",
}
REFERENCE_SKETCHES = pivot.REFERENCE_SKETCHES + ("NutPatternReference",)
# The transferred taps' native callout leads with where they come from
# (MHA-FR-05's transferred seats); TL-00 says how.
TRANSFER_PROCESS = f"TRANSFER THROUGH {feed_nut.NUMBER}\nAT ASSEMBLY;\n"

# --- The dowel's hole: #41 THRU, a slip on the dowel pressed in the nut --------
# Spotted with a #43 through the nut's reamed hole before the dowel is
# pressed, then drilled #41 THRU (a through slip hole needs no depth and
# leaves the dowel a way out). The title block's drilled +.004/0 keeps it a
# slip on the largest dowel.
DOWEL_SPOT_DIA = 0.089 * 25.4  # #43, 2.261
DOWEL_DRILL = 0.096 * 25.4  # #41, 2.438
DOWEL_YZ = (NUT_AXIS_Y + feed_nut.DOWEL_DX, NUT_AXIS_Z + feed_nut.DOWEL_DY)
assert DOWEL_SPOT_DIA < feed_nut.DOWEL_HOLE_DIA
assert DOWEL_DRILL > feed_nut.DOWEL_DIA_MAX
assert DRAWING_VALUES["NutDowelDia"] == DOWEL_DRILL
# The dowel stands flush with the nut's head face, so it reaches into the lug
# by its length less the nut's (the length band charged: ASME B18.8.2's ±.010
# for hardened ground dowels, the standard the 98381A438 page cites; the page
# itself states none).
_DOWEL_LENGTH_BAND = 0.010 * 25.4
DOWEL_LUG_ENGAGEMENT_MIN = feed_nut.DOWEL_LENGTH - _DOWEL_LENGTH_BAND - feed_nut.LENGTH_MAX  # .08
DOWEL_LUG_ENGAGEMENT_MAX = feed_nut.DOWEL_LENGTH + _DOWEL_LENGTH_BAND - feed_nut.LENGTH_MIN  # .12
assert 0.0 < DOWEL_LUG_ENGAGEMENT_MIN <= DOWEL_LUG_ENGAGEMENT_MAX < LUG_WIDTH

# --- The leadscrew in the lug: the vertical stack the clearance absorbs ---------
# The KP08s seat on TL-28's as-bought 1 in thickness (±.012) and the lug's
# clearance stands 12.400 ±.13 mm over the carriage face, so the leadscrew may
# run LEADSCREW_OFFSET_Z (.435 mm) off the clearance's axis vertically
# (Codjiflo P1 on #2112); laterally the KP08s float to centre it, within the
# clearance's own station band. The opened Ø.375 clears the Tr8's major at
# both.
_AXIS_Y_BAND = printed_band_mm(NUT_PATTERN_PLACES, unit=UNIT)  # .005
LEADSCREW_OFFSET_Z = end_bracket.THICK_STOCK_BAND + METRIC_BAND  # .435 mm
LEADSCREW_OFFSET_Y = _AXIS_Y_BAND
LEADSCREW_OFFSET = math.hypot(LEADSCREW_OFFSET_Y, LEADSCREW_OFFSET_Z)
LEADSCREW_RADIAL_CLEARANCE = (SCREW_CLEARANCE_DIA - lead.SCREW_MAJOR_DIA) / 2
assert LEADSCREW_RADIAL_CLEARANCE > LEADSCREW_OFFSET, (LEADSCREW_RADIAL_CLEARANCE, LEADSCREW_OFFSET)

# --- Fit-up: each tap spotted through its nut hole ------------------------------
# A #18 drill (.1695) spots each tap through the nut's Ø.170 hole, so a screw
# stands at most FIT_UP_RESIDUAL off its hole's axis; the #43 spot through the
# nut's reamed hole leaves the dowel hole DOWEL_RESIDUAL off its axis.
TRANSFER_SPOT_DIA = 0.1695 * 25.4  # #18
assert TRANSFER_SPOT_DIA < feed_nut.HOLE_DIA
FIT_UP_RESIDUAL = (2 * feed_nut.HOLE_R_MAX - TRANSFER_SPOT_DIA) / 2  # .0023
DOWEL_RESIDUAL = feed_nut.DOWEL_HOLE_R_MAX - DOWEL_SPOT_DIA / 2
# The heads seat flat at that eccentricity (Codjiflo P1 on #2112): each
# screw's underhead fillet, at its largest, clears the least hole's mouth, and
# the flange's flat bearing face, at its least, covers the largest hole with
# land to bear on the brass.
HEAD_FILLET_CLEARANCE = feed_nut.HOLE_DIA / 2 - (feed_nut.SCREW_FILLET_DIA_MAX / 2 + FIT_UP_RESIDUAL)
HEAD_BEARING_LAND_MIN = feed_nut.SCREW_BEARING_DIA_MIN / 2 - (feed_nut.HOLE_R_MAX + FIT_UP_RESIDUAL)
assert HEAD_FILLET_CLEARANCE > 0.0 and HEAD_BEARING_LAND_MIN > 0.0
# The flanges clear the leadscrew that runs past them: each screw stands at
# least the nut's .34 less the fit-up from the nut's (the leadscrew's) axis.
HEAD_TO_LEADSCREW_MIN = (
    feed_nut.HOLE_OFFSET - feed_nut.HOLE_OFFSET_BAND - FIT_UP_RESIDUAL
    - feed_nut.SCREW_DIMS.flange_dia / 2 - lead.SCREW_MAJOR_DIA / 2
)
assert HEAD_TO_LEADSCREW_MIN > 0.0

# --- Rule 17: lug walls at the printed worst case (.080 target) -----------------
# Every transferred hole sits where the nut puts it: the leadscrew at its
# offset from the clearance, the nut's station at its band, plus the spot.
NUT_TAP_MAJOR = THREAD_MAJOR_MM[feed_nut.SCREW_THREAD]
NUT_TAP_OFFSET_BAND = feed_nut.HOLE_OFFSET_BAND  # .010
_CLEARANCE_R = (SCREW_CLEARANCE_DIA + drilled_oversize_mm(unit=UNIT)) / 2
_TAP_SHIFT = NUT_TAP_OFFSET_BAND + FIT_UP_RESIDUAL
_DOWEL_R = (DOWEL_DRILL + drilled_oversize_mm(unit=UNIT)) / 2
_DOWEL_SHIFT = math.sqrt(2) * feed_nut.DOWEL_STATION_BAND + DOWEL_RESIDUAL
_DOWEL_TO_TAP_2 = math.hypot(NUT_TAP_OFFSET - feed_nut.DOWEL_DX, feed_nut.DOWEL_DY)
LUG_WALLS_MM = {
    "taps to the leadscrew clearance": NUT_TAP_OFFSET - _TAP_SHIFT - LEADSCREW_OFFSET_Y
    - NUT_TAP_MAJOR / 2 - _CLEARANCE_R,
    "tap 1 to the lug end": (NUT_AXIS_Y - LUG_Y0) - _AXIS_Y_BAND - LEADSCREW_OFFSET_Y
    - NUT_TAP_OFFSET - _TAP_SHIFT - NUT_TAP_MAJOR / 2,
    "taps to the bottom face": NUT_AXIS_Z - METRIC_BAND - LEADSCREW_OFFSET_Z - FIT_UP_RESIDUAL
    - NUT_TAP_MAJOR / 2,
    "taps to the top face": BLOCK_HEIGHT - NUT_AXIS_Z - METRIC_BAND - LEADSCREW_OFFSET_Z
    - FIT_UP_RESIDUAL - NUT_TAP_MAJOR / 2,
    "dowel hole to the leadscrew clearance": feed_nut.DOWEL_RADIUS - _DOWEL_SHIFT - LEADSCREW_OFFSET
    - _DOWEL_R - _CLEARANCE_R,
    "dowel hole to tap 2": _DOWEL_TO_TAP_2 - _DOWEL_SHIFT - _TAP_SHIFT - _DOWEL_R - NUT_TAP_MAJOR / 2,
    "dowel hole to the bottom face": DOWEL_YZ[1] - METRIC_BAND - LEADSCREW_OFFSET_Z
    - _DOWEL_SHIFT - _DOWEL_R,
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
