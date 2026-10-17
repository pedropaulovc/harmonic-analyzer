"""Drawing-only text of the pen-carriage fitter package (MHA-PN-000).

The BOM descriptions, setting callouts and their text points, the detail
regions and titles, the as-shipped note, the assembly steps and checks the
sheets print. Only draw_pn_pen_assembly (and its tests) import this module;
the builder reads pn_pen_assembly_spec alone, so a wording edit here does not
rebuild the pen assembly. No SolidWorks.
"""

from __future__ import annotations

import math
from fractions import Fraction

import pn_pen_adjust_screw_spec as stud
import pn_pen_carriage_geom as carriage
import pn_pen_hanger_spec as hanger
import pn_pen_v_block_spec as v_block
import vn_hanger_screw_spec as hanger_screw
import vn_pen_adjust_nut_spec as stud_nut
import vn_pen_hanger_jam_nut_spec as hanger_jam_nut
import vn_pen_hanger_nut_spec as hanger_nut
import vn_pen_rod_set_screw_spec as rod_set_screw
import _mcmaster_99607a213 as thumb_screw
from mg_wheel_bar_geom import BAR_DEPTH as WHEEL_BAR_DEPTH
from pn_pen_assembly_spec import (
    BOM_ORDER,
    CARRIAGE_END_MACHINE,
    FRAME,
    HANGER,
    HANGER_JAM_NUT,
    HANGER_NUT,
    HANGER_SCREW,
    ITEM,
    MARKER,
    NIB_DIMENSION,
    NIB_PRECISION,
    NIB_PROTRUSION,
    NIB_TOLERANCE_MM,
    NIB_UV,
    ROD,
    ROD_SET_SCREW,
    STUD,
    STUD_DIMENSION,
    STUD_HEIGHT,
    STUD_LINE,
    STUD_NUT,
    STUD_PRECISION,
    STUD_TOLERANCE_MM,
    THUMB_SCREW,
    V_BLOCK,
    WIRE,
    YAW_DEG,
    YAW_DIMENSION,
    YAW_TOLERANCE_DEG,
    exploded_point,
)


def _inch(mm: float) -> str:
    """A purchased size in the vendor's fractional inches (5/32, 1/4, 1)."""
    fraction = Fraction(mm / 25.4).limit_denominator(64)
    if abs(float(fraction) * 25.4 - mm) > 1e-6:
        raise AssertionError(f"{mm} mm is not a 1/64 in size")
    if fraction.denominator == 1:
        return str(fraction.numerator)
    return f"{fraction.numerator}/{fraction.denominator}"


STUD_NUT_WRENCH = _inch(stud_nut.ACROSS_FLATS)
HANGER_NUT_WRENCH = _inch(hanger_nut.ACROSS_FLATS)
HANGER_JAM_NUT_WRENCH = _inch(hanger_jam_nut.ACROSS_FLATS)
HANGER_SCREW_WRENCH = _inch(hanger_screw.HEAD_AF)
ROD_SET_SCREW_KEY = f"{rod_set_screw.HEX_AF / 25.4:.3f}"
WIRE_DIA_IN = f"{stud.PEN_WIRE_DIA / 25.4:.3f}"

BOM_DESCRIPTIONS = {
    HANGER: "PEN HANGER, STRAP + 2 U GUIDES",
    ROD: "PEN ROD",
    STUD: f"PEN-HEIGHT EYE STUD, {stud.THREAD}",
    STUD_NUT: f"HEX JAM NUT, {stud_nut.THREAD}, BRASS",
    V_BLOCK: "PEN V-BLOCK",
    ROD_SET_SCREW: (
        f"CUP-POINT SET SCREW, {rod_set_screw.THREAD} X {_inch(rod_set_screw.LENGTH)}"
    ),
    FRAME: "PEN STIRRUP",
    THUMB_SCREW: f"KNURLED THUMB SCREW, #4-40 X {_inch(thumb_screw.SHANK_LEN)}",
    MARKER: "MARKER, SHARPIE FINE (CONSUMABLE)",
    WIRE: f"PEN WIRE 2, {WIRE_DIA_IN} MUSIC WIRE",
    HANGER_SCREW: f"HEX HEAD SCREW, #8-32 X {_inch(hanger_screw.SHANK_LEN)}",
    HANGER_NUT: f"HEX NUT, {hanger_nut.THREAD}",
    HANGER_JAM_NUT: f"THIN HEX JAM NUT, {hanger_jam_nut.THREAD}",
}
if set(BOM_DESCRIPTIONS) != set(BOM_ORDER):
    raise AssertionError("every BOM row needs exactly one description")

# The rod set screw's trail on the exploded view: from its exploded cup back
# to its tap's mouth on the exploded block's front face. Along the tap's axis
# the octant view draws the screw's way out straight down the sheet, where it
# read as entering the block's bottom (machinist review r4); the trail lands
# it on the front-face tap step 4 names.
ROD_SET_SCREW_TRAIL = (
    exploded_point(ROD_SET_SCREW, carriage.ROD_SET_SCREW_POS),
    exploded_point(
        V_BLOCK,
        carriage.block_to_machine(
            (v_block.PIVOT_BORE_X, v_block.SET_SCREW_Y, v_block.BODY_Z0)
        ),
    ),
)
EXPLODED_CAPTION = "EXPLODED VIEW - ASSEMBLY SEQUENCE ON SHEET 3"

# The nib preset's text point, sketch mm: on the side of the marker-axis arm
# away from the yaw wedge, and beyond the nib tip along the axis, so the
# three-line callout (about 42 mm wide on the sheet, 21 model mm at 2:1) stands
# clear outside both extension lines rather than between them (farm run
# 20261016T071639431Z: the end-face extension line ran through the text there).
NIB_TEXT_OFFSET = 10.0
NIB_TEXT_BEYOND = 13.0
NIB_TEXT_UV = (
    NIB_UV[0] - (NIB_TEXT_BEYOND - NIB_TEXT_OFFSET) * math.sqrt(0.5),
    NIB_UV[1] - (NIB_TEXT_BEYOND + NIB_TEXT_OFFSET) * math.sqrt(0.5),
)
# The stud height's text point, machine mm: on the sheet-left of the rod axis
# in a Right view (machine +Z), away from the wire, mid-height, far enough out
# that the callout's widest line clears the stud's shank.
STUD_TEXT_POINT = (
    carriage.PEN_ROD_X,
    (STUD_LINE[0][1] + STUD_LINE[1][1]) / 2.0,
    carriage.PEN_Z_MID + 13.0,
)

DIMENSION_CALLOUTS = {
    STUD_DIMENSION: "STUD HEAD\nABOVE ROD TOP",
    NIB_DIMENSION: "NIB PRESET\nBEYOND END FACE",
    YAW_DIMENSION: "MARKER TO\nROD FLAT",
}

# --- fitter text ----------------------------------------------------------------
_STUD_SETTING = f"{STUD_HEIGHT:.{STUD_PRECISION}f} ±{STUD_TOLERANCE_MM:.1f}"
_NIB_SETTING = f"{NIB_PROTRUSION:.{NIB_PRECISION}f} ±{NIB_TOLERANCE_MM:.1f}"
_YAW_SETTING = f"{YAW_DEG:.0f}° ±{YAW_TOLERANCE_DEG:.0f}°"
_TRAVEL = f"±{carriage.PEN_TRAVEL_HALF_MM:.0f}"

# --- detail regions (machine mm): what each fitter detail is centred on and how
# far round it reaches ------------------------------------------------------------
STUD_DETAIL_CENTRE = (carriage.PEN_ROD_X, STUD_TEXT_POINT[1], carriage.PEN_Z_MID)
STUD_DETAIL_RADIUS = 14.0
_BAR_BACK_Z = hanger.HANGER_POS[2] + max(hanger.STRAP_Z) + WHEEL_BAR_DEPTH
_HANGER_SCREW_TIP_Z = _BAR_BACK_Z - hanger_screw.SHANK_LEN
HANGER_DETAIL_CENTRE = (
    hanger.HANGER_POS[0] + hanger.SCREW_HOLE_XY[0],
    hanger.HANGER_POS[1] + hanger.SCREW_HOLE_XY[1],
    (_BAR_BACK_Z + _HANGER_SCREW_TIP_Z) / 2.0,
)
HANGER_DETAIL_RADIUS = (_BAR_BACK_Z - _HANGER_SCREW_TIP_Z) / 2.0 + 4.0
# DETAIL C is turned so the marker axis reads left to right (nib left): its
# crop centres a little into the block from the paper-end face, so the nib tip
# and the stirrup's corners fall inside the circle and the block's far end is
# cut off.
CARRIAGE_DETAIL_INSET = 5.0
CARRIAGE_DETAIL_CENTRE = carriage.block_to_machine(
    (CARRIAGE_DETAIL_INSET, v_block.MARKER_AXIS_Y, v_block.DEPTH_MID_Z)
)
CARRIAGE_DETAIL_RADIUS = 20.0
# The two points whose sheet direction the turned detail lays along +X.
CARRIAGE_AXIS_POINTS = (carriage.MARKER_POS, CARRIAGE_END_MACHINE)

# A and B are bounded on RIGHT and drawn from the right; C is the turned
# plan, so its title names its viewing direction.
DETAIL_LETTERS = {"stud": "A", "hanger": "B", "carriage": "C"}
SHEET_TITLES = {
    "carriage": f"DETAIL {DETAIL_LETTERS['carriage']} - FROM ABOVE\n"
    "PEN YAW + NIB PRESET\nSCALE 2 : 1",
    "stud": f"DETAIL {DETAIL_LETTERS['stud']}\nSTUD HEIGHT + LOCK\nSCALE 2 : 1",
    "hanger": f"DETAIL {DETAIL_LETTERS['hanger']}\nHANGER SCREW LOCK\nSCALE 2 : 1",
}
VIEW_TITLES = {
    "front": "FRONT\nSCALE 1 : 2",
    "right": "RIGHT\nSCALE 1 : 2",
    "finished": "AS ASSEMBLED\nSCALE 1 : 2",
}
SETTINGS_NOTE = (
    "AS SHIPPED: STUD SET AND LOCKED (DETAIL A); YAW SET, SET SCREW TIGHT; "
    "NIB PRESET, THUMB SCREW FINGER-TIGHT (DETAIL C); ROD FREE IN BOTH "
    f"GUIDES. ITEMS {ITEM[HANGER_SCREW]}-{ITEM[HANGER_JAM_NUT]} BAGGED WITH "
    "THE SUB-ASSEMBLY; UPPER END OF THE PEN WIRE LEFT LONG, COILED. "
    "NO LUBRICANT, NO THREAD LOCKER."
)

ASSEMBLY_STEPS = (
    "AT THE BENCH:",
    f"1. STUD HEIGHT: RUN THE JAM NUT (ITEM {ITEM[STUD_NUT]}) ONTO THE STUD "
    f"(ITEM {ITEM[STUD]}) UP TO THE HEAD. SCREW THE STUD INTO THE TOP TAP OF "
    f"THE ROD (ITEM {ITEM[ROD]}) UNTIL ITS HEAD TOP STANDS {_STUD_SETTING} "
    "ABOVE THE ROD TOP (DETAIL A). HOLD THE STUD BY ITS HEAD AND TIGHTEN THE "
    f"JAM NUT DOWN ON THE ROD TOP ({STUD_NUT_WRENCH} WRENCH): THE STUD'S LOCK.",
    f"2. PEN WIRE TO STUD EYE: PASS THE LOWER END OF THE PEN WIRE (ITEM "
    f"{ITEM[WIRE]}) THROUGH THE STUD EYE, BEND IT BACK, WRAP 3 TIGHT TURNS "
    "ROUND ITSELF, TRIM THE TAIL. LEAVE THE UPPER END LONG.",
    f"3. STIRRUP: SLIDE THE STIRRUP (ITEM {ITEM[FRAME]}) ONTO THE V-BLOCK "
    f"(ITEM {ITEM[V_BLOCK]}) FLUSH WITH ITS PAPER END. START THE THUMB SCREW "
    f"(ITEM {ITEM[THUMB_SCREW]}) UP INTO THE STIRRUP'S BOTTOM-RAIL TAP.",
    "4. PEN YAW: DROP THE ROD'S TURNED PIVOT INTO THE V-BLOCK BORE, SQUARE "
    "SHOULDER DOWN ON THE BLOCK TOP. TURN THE BLOCK UNTIL ITS V STANDS "
    f"{_YAW_SETTING} TO A ROD FLAT (DETAIL C; PROTRACTOR ON THE BLOCK SIDE "
    "AND THE FLAT), THEN TIGHTEN THE CUP-POINT SET SCREW (ITEM "
    f"{ITEM[ROD_SET_SCREW]}) IN THE BLOCK'S FRONT-FACE TAP "
    f"({ROD_SET_SCREW_KEY} IN HEX KEY). NOTHING ON ITS THREAD: IT IS "
    "SLACKENED TO RE-SET THE YAW.",
    f"5. NIB PRESET: MARKER (ITEM {ITEM[MARKER]}, CONSUMABLE), CAP OFF, NIB "
    "FIRST THROUGH THE STIRRUP WINDOW INTO THE V UNTIL THE NIB TIP STANDS "
    f"{_NIB_SETTING} BEYOND THE BLOCK/STIRRUP PAPER-END FACE ALONG THE "
    "MARKER AXIS (DETAIL C). TIGHTEN THE THUMB SCREW FINGER-TIGHT: ITS TIP "
    "CLAMPS THE GRIP INTO THE V. SLACKEN IT TO CHANGE A DRY MARKER.",
    "6. INTO THE GUIDES: ENTER THE ROD'S SQUARE INTO BOTH U GUIDES OF THE "
    f"HANGER (ITEM {ITEM[HANGER]}) FROM THEIR OPEN FRONT ENDS, CARRIAGE BELOW "
    "THE LOWER GUIDE.",
    "AT MHA-HA-000:",
    f"7. HANGER SCREW LOCK: HANGER SCREW (ITEM {ITEM[HANGER_SCREW]}) FROM "
    "BEHIND THE MHA-MG-008 WHEEL BAR THROUGH THE BAR AND THE STRAP HOLE. RUN "
    f"THE HEX NUT (ITEM {ITEM[HANGER_NUT]}) ON AGAINST THE STRAP FRONT AND "
    f"HOLD IT ({HANGER_NUT_WRENCH} WRENCH) WHILE TIGHTENING THE SCREW "
    f"({HANGER_SCREW_WRENCH} WRENCH). HOLD THAT NUT STILL AND TIGHTEN THE "
    f"JAM NUT (ITEM {ITEM[HANGER_JAM_NUT]}, {HANGER_JAM_NUT_WRENCH} WRENCH) "
    "AGAINST IT (DETAIL B): THE SCREW'S LOCK.",
    "8. PEN WIRE TO RIM, NIB TO PAPER: PER MHA-HA-000. THE STUD STAYS AT ITS "
    "STEP 1 SETTING; MOVE THE MARKER ONLY WITH THE THUMB SCREW SLACKENED, "
    "THEN RE-TIGHTEN IT FINGER-TIGHT.",
)
ASSEMBLY_CHECKS = (
    "CHECKS:",
    f"- THE ROD SLIDES FREELY THROUGH BOTH GUIDES OVER ITS {_TRAVEL} TRAVEL "
    "AND FALLS UNDER THE CARRIAGE'S WEIGHT WHEN LIFTED AND RELEASED.",
    "- THE V-BLOCK DOES NOT TURN ON THE PIVOT BY HAND, AND THE YAW STILL "
    f"READS {_YAW_SETTING} (DETAIL C) AFTER TRYING IT.",
    f"- BOTH JAM NUTS (ITEMS {ITEM[STUD_NUT]}, {ITEM[HANGER_JAM_NUT]}) TIGHT; "
    "THE STUD AND THE HANGER SCREW DO NOT TURN BY HAND.",
)
