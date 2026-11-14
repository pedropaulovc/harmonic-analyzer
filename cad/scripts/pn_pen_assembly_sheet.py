"""Drawing-only data of the pen-carriage fitter package (MHA-PN-00).

The BOM item numbers and descriptions, the settings' display on the sheet
(which is a reference, the nominals and bands it reads back, tolerance
places), setting callouts and their text points, the explode trails, the
detail regions and titles, the as-shipped note, the assembly steps and checks
the sheets print. Only draw_pn_pen_assembly (and its tests) import this
module; no assembly builder may (``test_assembly_sheet_isolation`` pins it),
so a wording edit here does not rebuild the pen assembly. No SolidWorks.
Printed lengths are decimal inch, the assembly contract's ``drawing_unit``.
"""

from __future__ import annotations

import math

import pn_pen_adjust_screw_spec as stud
import pn_pen_carriage_geom as carriage
import pn_pen_hanger_spec as hanger
import pn_pen_v_block_spec as v_block
import pn_vn_hanger_screw_spec as hanger_screw
import pn_vn_pen_adjust_nut_spec as stud_nut
import pn_vn_pen_hanger_jam_nut_spec as hanger_jam_nut
import pn_vn_pen_hanger_nut_spec as hanger_nut
import sh_vn_arbor_set_screw_spec as rod_set_screw
import _mcmaster_99607a213 as thumb_screw
import ha_harmonic_analyzer_assembly_steps as ha_steps
from _inch_fraction import inch_fraction
from _assembly_contract import assembly_contract
from _column_clamp_interface import BAR_DEPTH as WHEEL_BAR_DEPTH
from pn_pen_assembly_spec import (
    BOM_ORDER,
    CARRIAGE_END_MACHINE,
    FRAME,
    HANGER,
    HANGER_JAM_NUT,
    HANGER_NUT,
    HANGER_SCREW,
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
)
from pn_pen_explode_spec import EXPLODE_STEPS
from sh_vn_music_wire_pen_spec import BOM_DESCRIPTION as _WIRE_BOM_DESCRIPTION

DRAWING_NUMBER = "MHA-PN-00"
# A literal stem: the build graph narrows this drawing's assemblies/*
# dependency to exactly the contracts its closure names.
UNIT = assembly_contract("pn-pen").drawing_unit
# A top-level BOM numbers its rows in the builder's insertion order
# (pn_pen_assembly_spec.BOM_ORDER); the drawing proves each row against this
# and the steps cite it.
ITEM = {stem: index for index, stem in enumerate(BOM_ORDER, 1)}

# How the sheet shows the builder's setting dimensions. A reference dimension
# carries no band: the stud's band rides on the measured-length setting the
# callout and step 1 print.
REFERENCE_DIMENSIONS = frozenset({STUD_DIMENSION})
DIMENSION_TOLERANCES = {NIB_DIMENSION: NIB_TOLERANCE_MM}
ANGULAR_TOLERANCES = {YAW_DIMENSION: YAW_TOLERANCE_DEG}
TOLERANCE_PRECISION = {NIB_DIMENSION: NIB_PRECISION, YAW_DIMENSION: 0}
DIMENSION_NOMINALS = {STUD_DIMENSION: STUD_HEIGHT, NIB_DIMENSION: NIB_PROTRUSION}


def exploded_point(stem: str, point: tuple[float, float, float]) -> tuple[float, ...]:
    """``point`` (machine mm, assembled) carried by every
    ``pn_pen_explode_spec.EXPLODE_STEPS`` step that moves ``stem``."""
    moved = list(point)
    for _label, stems, key, distance in EXPLODE_STEPS:
        if stem in stems:
            moved["xyz".index(key)] += distance
    return tuple(moved)


def _inch(mm: float) -> str:
    """A purchased size in the vendor's fractional inches (5/32, 1/4, 1)."""
    return inch_fraction(mm, what="pen purchased size")


def _decimal(mm: float, places: int) -> str:
    """A length as the inch sheet prints it at ``places``, rounded, no
    leading zero (.126, 1.024)."""
    if UNIT != "in":
        raise AssertionError(f"pen fitter text is authored in inch, not {UNIT!r}")
    text = f"{mm / 25.4:.{places}f}"
    return text[1:] if text.startswith("0.") else text


STUD_NUT_WRENCH = _inch(stud_nut.ACROSS_FLATS)
HANGER_NUT_WRENCH = _inch(hanger_nut.ACROSS_FLATS)
HANGER_JAM_NUT_WRENCH = _inch(hanger_jam_nut.ACROSS_FLATS)
HANGER_SCREW_WRENCH = _inch(hanger_screw.HEAD_AF)
ROD_SET_SCREW_KEY = _decimal(rod_set_screw.HEX_AF, 3)

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
    WIRE: _WIRE_BOM_DESCRIPTION,
    HANGER_SCREW: f"HEX HEAD SCREW, #8-32 X {_inch(hanger_screw.SHANK_LEN)}",
    HANGER_NUT: f"HEX NUT, {hanger_nut.THREAD}",
    HANGER_JAM_NUT: f"THIN HEX JAM NUT, {hanger_jam_nut.THREAD}",
}
if set(BOM_DESCRIPTIONS) != set(BOM_ORDER):
    raise AssertionError("every BOM row needs exactly one description")
# The steps call the stud by its BOM name (machinist review c03368c).
_STUD_NAME = BOM_DESCRIPTIONS[STUD].partition(",")[0]
# The rod and everything its pivot carries; the checks call it the carriage,
# defined once by its BOM rows (one run of items).
CARRIAGE_STEMS = (ROD, V_BLOCK, FRAME, THUMB_SCREW, ROD_SET_SCREW, MARKER)
_CARRIAGE_ITEMS = sorted(ITEM[stem] for stem in CARRIAGE_STEMS)
if _CARRIAGE_ITEMS != list(range(_CARRIAGE_ITEMS[0], _CARRIAGE_ITEMS[-1] + 1)):
    raise AssertionError("the carriage's BOM items must run as one range")
# Step 6: the rod rides up through both guides and the stud and wire stand
# above them; what hangs below the lower guide is the block, its marker and
# the stirrup (one run of BOM items).
_BELOW_GUIDE_ITEMS = sorted(ITEM[stem] for stem in (V_BLOCK, MARKER, FRAME))
if _BELOW_GUIDE_ITEMS != list(range(_BELOW_GUIDE_ITEMS[0], _BELOW_GUIDE_ITEMS[-1] + 1)):
    raise AssertionError("the block, marker and stirrup must run as one range")
_BELOW_GUIDE = (
    "V-BLOCK, MARKER AND STIRRUP "
    f"(ITEMS {_BELOW_GUIDE_ITEMS[0]}-{_BELOW_GUIDE_ITEMS[-1]})"
)

# --- explode trails (machine mm, exploded): from the moved part back to where it
# fits, along the move ---------------------------------------------------------------
# The rod set screw: from its exploded cup back to its tap's mouth on the
# exploded block's front face. Along the tap's axis the exploded view draws the
# screw's way out down-left, off the face's verticals; the trail lands it on
# the front-face tap step 4 names.
ROD_SET_SCREW_TRAIL = (
    exploded_point(ROD_SET_SCREW, carriage.ROD_SET_SCREW_POS),
    exploded_point(
        V_BLOCK,
        carriage.block_to_machine(
            (v_block.PIVOT_BORE_X, v_block.SET_SCREW_Y, v_block.BODY_Z0)
        ),
    ),
)
# The thumb screw: from its exploded tip up its axis to the tap's mouth on the
# exploded stirrup's bottom-rail underside (step 3).
THUMB_SCREW_TRAIL = (
    exploded_point(
        THUMB_SCREW,
        carriage.block_to_machine(
            (
                carriage.FRAME_X_CENTER_LOCAL,
                carriage.MARKER_BOTTOM_LOCAL_Y,
                v_block.DEPTH_MID_Z,
            )
        ),
    ),
    exploded_point(
        FRAME,
        carriage.block_to_machine(
            (
                carriage.FRAME_X_CENTER_LOCAL,
                carriage.FRAME_ORIGIN_LOCAL[1],
                v_block.DEPTH_MID_Z,
            )
        ),
    ),
)
# The stirrup: from its exploded rod-side face, at the block's mid-height on
# the section's centre line, back along the slide-on axis to the block's
# paper-end face, which it seats flush with (step 3).
_STIRRUP_TRAIL_Y = v_block.BLOCK_HEIGHT / 2.0
STIRRUP_TRAIL = (
    exploded_point(
        FRAME,
        carriage.block_to_machine(
            (carriage.FRAME_ORIGIN_LOCAL[0], _STIRRUP_TRAIL_Y, v_block.DEPTH_MID_Z)
        ),
    ),
    exploded_point(
        V_BLOCK,
        carriage.block_to_machine(
            (carriage.FRAME_X0_LOCAL, _STIRRUP_TRAIL_Y, v_block.DEPTH_MID_Z)
        ),
    ),
)
EXPLODE_TRAILS = {
    "rod set screw": ROD_SET_SCREW_TRAIL,
    "thumb screw": THUMB_SCREW_TRAIL,
    "stirrup": STIRRUP_TRAIL,
}

EXPLODED_CAPTION = "EXPLODED VIEW - ASSEMBLY SEQUENCE ON SHEETS 3-4"

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

# The stud is set from its measured length (code review C05): the head top
# stands that length less the nominal engagement, ±STUD_TOLERANCE_MM.
_STUD_LESS_TEXT = _decimal(stud.OVERALL_LENGTH - STUD_HEIGHT, STUD_PRECISION)
_STUD_LESS = f"{_STUD_LESS_TEXT} ±{_decimal(STUD_TOLERANCE_MM, STUD_PRECISION)}"
DIMENSION_CALLOUTS = {
    STUD_DIMENSION: f"STUD HEAD\nABOVE ROD TOP:\nSTUD LENGTH\nLESS {_STUD_LESS}",
    NIB_DIMENSION: "NIB PRESET\nBEYOND END FACE",
    YAW_DIMENSION: "MARKER TO\nROD FLAT",
}

# --- fitter text ----------------------------------------------------------------
_STUD_SETTING = f"THE STUD'S MEASURED LENGTH LESS {_STUD_LESS}"
# The worked example quotes the nominal stud at the setting's three places
# (1.024, not the stud sheet's two-place 1.02) so the printed numbers add up
# with the rule and with DETAIL A's native reference (.898): 1.024 - .126.
_STUD_LENGTH_TEXT = _decimal(stud.OVERALL_LENGTH, STUD_PRECISION)
_STUD_HEIGHT_TEXT = _decimal(STUD_HEIGHT, STUD_PRECISION)
if round(
    float(_STUD_LENGTH_TEXT) - float(_STUD_LESS_TEXT) - float(_STUD_HEIGHT_TEXT),
    STUD_PRECISION,
):
    raise AssertionError("the stud setting's worked example does not add up")
_STUD_NOMINAL = f"{_STUD_HEIGHT_TEXT} FOR A {_STUD_LENGTH_TEXT} STUD"
_NIB_SETTING = (
    f"{_decimal(NIB_PROTRUSION, NIB_PRECISION)} "
    f"±{_decimal(NIB_TOLERANCE_MM, NIB_PRECISION)}"
)
_YAW_SETTING = f"{YAW_DEG:.0f}° ±{YAW_TOLERANCE_DEG:.0f}°"
_TRAVEL = f"±{_decimal(carriage.PEN_TRAVEL_HALF_MM, 2)}"

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
# In the plan as placed (sheet x = machine X, sheet y = machine -Z) that axis
# runs up and right, so laying it along +X turns the view clockwise by its
# angle; the title says by how much and the drawing proves it on the sheet.
CARRIAGE_TURN_CW_DEG = round(
    math.degrees(
        math.atan2(
            CARRIAGE_AXIS_POINTS[0][2] - CARRIAGE_AXIS_POINTS[1][2],
            CARRIAGE_AXIS_POINTS[1][0] - CARRIAGE_AXIS_POINTS[0][0],
        )
    ),
    6,
)

# DETAIL D, from the front at 1:1: the stirrup on the block's paper end, its
# window round the marker grip, and the thumb screw up through the bottom
# rail's tap to the grip -- what step 3 assembles and the exploded view, with
# the stirrup and screw slid apart, cannot show in place. Its crop runs from
# the thumb screw's head up to the block top, centred on the stirrup's depth.
_THUMB_SCREW_HEAD_LOCAL_Y = carriage.MARKER_BOTTOM_LOCAL_Y - carriage.THUMB_SCREW_REACH
STIRRUP_DETAIL_CENTRE = carriage.block_to_machine(
    (
        carriage.FRAME_X_CENTER_LOCAL,
        (_THUMB_SCREW_HEAD_LOCAL_Y + v_block.BLOCK_HEIGHT) / 2.0,
        v_block.DEPTH_MID_Z,
    )
)
STIRRUP_DETAIL_RADIUS = (v_block.BLOCK_HEIGHT - _THUMB_SCREW_HEAD_LOCAL_Y) / 2.0 + 2.0
# DETAIL C's viewing arrow on FRONT points straight down onto the carriage,
# nib-ward of the rod where FRONT has open paper (the strap stands over the
# rod): its tip just over the stirrup's top, which FRONT draws as the
# carriage's top edge, and clear above D's circle, which crests inside the
# stirrup just over the block top.
_STIRRUP_TOP_Y = carriage.block_to_machine((0.0, carriage.FRAME_TOP_LOCAL_Y, 0.0))[1]
CARRIAGE_ARROW_TIP = (
    carriage.PEN_ROD_X - 13.0,
    _STIRRUP_TOP_Y + 1.0,
    carriage.PEN_Z_MID,
)

# A, B and D are circled on the view they enlarge (A and B on RIGHT, D on
# FRONT) and drawn from its direction. C, the turned plan, is named by a
# viewing arrow on FRONT; its title says which way it looks and how it is
# turned.
DETAIL_LETTERS = {"stud": "A", "hanger": "B", "carriage": "C", "stirrup": "D"}
SHEET_TITLES = {
    "carriage": f"VIEW {DETAIL_LETTERS['carriage']} - FROM ABOVE\n"
    f"ROTATED {CARRIAGE_TURN_CW_DEG:g} DEG CW\nPEN YAW + NIB PRESET\nSCALE 2 : 1",
    "stud": f"DETAIL {DETAIL_LETTERS['stud']}\nSTUD HEIGHT + LOCK\nSCALE 2 : 1",
    "hanger": f"DETAIL {DETAIL_LETTERS['hanger']}\nHANGER SCREW LOCK\nSCALE 2 : 1",
    "stirrup": f"DETAIL {DETAIL_LETTERS['stirrup']}\nSTIRRUP + THUMB SCREW\nSCALE 1 : 1",
}
# A view scale prints only where it differs from the sheet's 1:2 (rule 9).
VIEW_TITLES = {
    "front": "FRONT",
    "right": "RIGHT",
    "finished": "AS ASSEMBLED",
}
SETTINGS_NOTE = (
    "AS SHIPPED: STUD SET AND LOCKED (DETAIL A); YAW SET, SET SCREW TIGHT; "
    "NIB PRESET, THUMB SCREW FINGER-TIGHT (VIEW C); ROD FREE IN BOTH "
    f"GUIDES. ITEMS {ITEM[HANGER_SCREW]}-{ITEM[HANGER_JAM_NUT]} BAGGED WITH "
    "THE SUB-ASSEMBLY; UPPER END OF THE PEN WIRE LEFT LONG, COILED. "
    "NO LUBRICANT, NO THREAD LOCKER."
)

# A step does one thing (rule 22): a numbered step's own sub-steps carry a
# letter (1A, 1B, ...; no I or O), so the step numbers other sheets cite
# (MHA-PN-VN-57's steps 2 and 8, MHA-HA-00's hanger screw lock) stay put.
_HA_WIRE_TIED = ha_steps.step_number("pen-wire-tied")
_HA_NIB = (ha_steps.step_number("nib-set"), ha_steps.step_number("nib-on-paper"))
ASSEMBLY_STEPS = (
    "AT THE BENCH:",
    f"1. STUD HEIGHT: MEASURE THE OVERALL LENGTH OF THE STUD (ITEM {ITEM[STUD]}), "
    "THREAD END TO HEAD END.",
    f"1A. RUN THE JAM NUT (ITEM {ITEM[STUD_NUT]}) ONTO THE STUD UP TO THE HEAD.",
    f"1B. SCREW THE STUD INTO THE TOP TAP OF THE ROD (ITEM {ITEM[ROD]}) UNTIL "
    f"ITS HEAD TOP STANDS {_STUD_SETTING} ABOVE THE ROD TOP ({_STUD_NOMINAL}; "
    "DETAIL A).",
    "1C. STUD LOCK: HOLD THE STUD BY ITS HEAD AND TIGHTEN THE JAM NUT DOWN ON "
    f"THE ROD TOP ({STUD_NUT_WRENCH} WRENCH).",
    f"2. PEN WIRE TO STUD EYE: PASS THE LOWER END OF THE PEN WIRE (ITEM "
    f"{ITEM[WIRE]}) THROUGH THE EYE OF THE {_STUD_NAME} (ITEM {ITEM[STUD]}).",
    "2A. KNOT THAT END ROUND THE WIRE ABOVE THE EYE.",
    "2B. CHECK: THE KNOT DOES NOT SLIP UNDER A LIGHT PULL BY HAND.",
    "2C. TRIM THE TAIL CLOSE TO THE KNOT; THE UPPER END STAYS LONG.",
    f"3. STIRRUP: SLIDE THE STIRRUP (ITEM {ITEM[FRAME]}) ONTO THE V-BLOCK "
    f"(ITEM {ITEM[V_BLOCK]}) FLUSH WITH THE BLOCK'S END FACE AT THE NIB END "
    "(VIEW C).",
    f"3A. START THE THUMB SCREW (ITEM {ITEM[THUMB_SCREW]}) UP INTO THE "
    "STIRRUP'S BOTTOM-RAIL TAP (DETAIL D).",
    f"4. DROP THE TURNED PIVOT OF THE ROD (ITEM {ITEM[ROD]}) INTO THE BORE OF "
    f"THE V-BLOCK (ITEM {ITEM[V_BLOCK]}), SQUARE SHOULDER DOWN ON THE BLOCK TOP.",
    f"4A. PEN YAW: TURN THE V-BLOCK (ITEM {ITEM[V_BLOCK]}) UNTIL ITS V STANDS "
    f"{_YAW_SETTING} TO A FLAT OF THE ROD (ITEM {ITEM[ROD]}) (VIEW C; "
    "PROTRACTOR ON THE BLOCK SIDE AND THE FLAT).",
    f"4B. TIGHTEN THE CUP-POINT SET SCREW (ITEM {ITEM[ROD_SET_SCREW]}) IN THE "
    f"BLOCK'S FRONT-FACE TAP ({ROD_SET_SCREW_KEY} IN HEX KEY).",
    f"5. NIB PRESET: MARKER (ITEM {ITEM[MARKER]}, CONSUMABLE), CAP OFF, NIB "
    "FIRST THROUGH THE STIRRUP WINDOW INTO THE V UNTIL THE NIB TIP STANDS "
    f"{_NIB_SETTING} BEYOND THE END FACE ALONG THE MARKER AXIS (VIEW C).",
    "5A. TIGHTEN THE THUMB SCREW FINGER-TIGHT: ITS TIP CLAMPS THE GRIP INTO "
    "THE V.",
    "5B. CHECK: THE MARKER DOES NOT SLIDE OR TURN IN THE V BY HAND, AND THE "
    f"NIB STILL STANDS {_NIB_SETTING} BEYOND THE END FACE (VIEW C).",
    f"6. INTO THE GUIDES: ENTER THE SQUARE OF THE ROD (ITEM {ITEM[ROD]}) INTO BOTH U GUIDES OF THE "
    f"HANGER (ITEM {ITEM[HANGER]}) FROM THEIR OPEN FRONT ENDS, THE {_BELOW_GUIDE} "
    "BELOW THE LOWER GUIDE.",
    "AT MHA-HA-00:",
    f"7. HANGER SCREW LOCK: PASS THE HANGER SCREW (ITEM {ITEM[HANGER_SCREW]}) "
    "THROUGH THE MHA-MG-08 WHEEL BAR AND THE STRAP HOLE, HEAD ON THE WHEEL-BAR "
    "SIDE (DETAIL B).",
    f"7A. RUN THE HEX NUT (ITEM {ITEM[HANGER_NUT]}) ONTO THE SCREW AGAINST THE "
    "STRAP, SNUG ONLY.",
    "7B. SWING THE STRAP ON THE SCREW UNTIL A SQUARE STANDING ON THE BAR TOP "
    "READS THE ROD SQUARE TO IT.",
    f"7C. HOLD THE NUT ({HANGER_NUT_WRENCH} WRENCH) WHILE TIGHTENING THE SCREW "
    f"({HANGER_SCREW_WRENCH} WRENCH).",
    "7D. CHECK: THE SQUARE ON THE BAR TOP STILL READS THE ROD SQUARE TO IT.",
    "7E. IF IT DOES NOT, SLACKEN THE SCREW AND REPEAT 7B-7D.",
    f"7F. HOLD THE NUT STILL AND TIGHTEN THE JAM NUT (ITEM {ITEM[HANGER_JAM_NUT]}, "
    f"{HANGER_JAM_NUT_WRENCH} WRENCH) AGAINST IT (DETAIL B): THE SCREW'S LOCK.",
    "8. TIE THE UPPER END OF THE PEN WIRE TO THE MHA-MG-05 WHEEL RIM PER "
    f"MHA-HA-00 STEP {_HA_WIRE_TIED}.",
    f"8A. SET THE NIB TO PAPER PER MHA-HA-00 STEPS {_HA_NIB[0]}-{_HA_NIB[1]}.",
    "8B. TO CHANGE A DRY MARKER, SLACKEN THE THUMB SCREW (ITEM "
    f"{ITEM[THUMB_SCREW]}).",
    f"8C. PULL THE OLD MARKER (ITEM {ITEM[MARKER]}) OUT OF THE V.",
    "8D. FIT THE NEW MARKER PER STEPS 5-5B.",
    "8E. SET ITS NIB TO PAPER PER STEP 8A.",
)
ASSEMBLY_CHECKS = (
    "CHECKS:",
    f"- THE ROD SLIDES FREELY THROUGH BOTH GUIDES OVER ITS {_TRAVEL} TRAVEL "
    f"AND FALLS UNDER THE WEIGHT OF ITEMS {_CARRIAGE_ITEMS[0]}-"
    f"{_CARRIAGE_ITEMS[-1]} WHEN LIFTED AND RELEASED.",
    "- THE V-BLOCK DOES NOT TURN ON THE PIVOT BY HAND, AND THE YAW STILL "
    f"READS {_YAW_SETTING} (VIEW C) AFTER TRYING IT.",
    f"- BOTH JAM NUTS (ITEMS {ITEM[STUD_NUT]}, {ITEM[HANGER_JAM_NUT]}) TIGHT; "
    "THE STUD AND THE HANGER SCREW DO NOT TURN BY HAND.",
    "- A SQUARE ON THE BAR TOP STILL READS THE ROD SQUARE TO IT.",
)
