"""Pure fitting contract for pn-pen.SLDASM (MHA-PN-000): inventory, explode,
the three carriage settings and the fitter text.

The builder (``build_pn_pen_assembly``) authors the settings as blanked
construction sketches carrying driving, toleranced model dimensions and the
``PN_EXPLODED`` presentation from ``EXPLODE_STEPS``; the fitter drawing
(``draw_pn_pen_assembly``) imports those dimensions and prints the text
below. Every number comes from the part and carriage contracts
(``pn_pen_carriage_geom``, the part/vendor specs); nothing here restates a
dimension. No SolidWorks imports.

Settings (drawing-guidelines.md rule 22 (an assembly package is complete),
setup and adjustment):

* STUD HEIGHT -- the #0-80 eye stud's head top above the rod's top face,
  ``StudHeadAboveRodTop@StudSetting`` on the Front plane. The band keeps the
  engagement in the rod's tap at least 1.5 D and short of its thread depth.
* PEN YAW -- the marker axis to the rod flats (the paper face),
  ``PenYaw@CarriageSetting`` on the Top plane.
* NIB PRESET -- the nib tip beyond the v-block/stirrup paper-end face along
  the marker axis, ``NibProtrusion@CarriageSetting``. The nib-to-paper
  clearance is set at MHA-HA-000, where the paper exists.
"""

from __future__ import annotations

import math
from fractions import Fraction

import pn_pen_adjust_screw_spec as stud
import pn_pen_hanger_spec as hanger
import pn_pen_carriage_geom as carriage
import pn_pen_rod_spec as rod
import pn_pen_v_block_spec as v_block
import vn_hanger_screw_spec as hanger_screw
import vn_pen_adjust_nut_spec as stud_nut
import vn_pen_hanger_jam_nut_spec as hanger_jam_nut
import vn_pen_hanger_nut_spec as hanger_nut
import vn_pen_marker_spec as marker
import vn_pen_rod_set_screw_spec as rod_set_screw
import _mcmaster_99607a213 as thumb_screw
from _hole_spec import THREAD_MAJOR_MM
from mg_wheel_bar_geom import BAR_DEPTH as WHEEL_BAR_DEPTH

ASM_NAME = "pn-pen"
DRAWING_NUMBER = "MHA-PN-000"

HANGER = "pn-pen-hanger"
ROD = "pn-pen-rod"
STUD = "pn-pen-adjust-screw"
STUD_NUT = "vn-pen-adjust-nut"
V_BLOCK = "pn-pen-v-block"
ROD_SET_SCREW = "vn-pen-rod-set-screw"
FRAME = "pn-pen-frame"
THUMB_SCREW = "vn-pen-set-screw"
MARKER = "vn-pen-marker"
WIRE = "vn-pen-wire"
HANGER_SCREW = "vn-hanger-screw"
HANGER_NUT = "vn-pen-hanger-nut"
HANGER_JAM_NUT = "vn-pen-hanger-jam-nut"

# Every component family and its count: the builder places, the explode
# moves and the drawing's BOM proves exactly this inventory. BOM_ORDER is
# the builder's insertion order (hanger, rod, its RIDERS, then the hanger
# fastening), which is the order a top-level BOM numbers its rows in; the
# drawing proves each row's item number against ITEM, which the steps cite.
BOM_ORDER = (
    HANGER,
    ROD,
    V_BLOCK,
    MARKER,
    FRAME,
    THUMB_SCREW,
    ROD_SET_SCREW,
    STUD,
    STUD_NUT,
    WIRE,
    HANGER_SCREW,
    HANGER_NUT,
    HANGER_JAM_NUT,
)
QUANTITIES = {stem: 1 for stem in BOM_ORDER}
ITEM = {stem: index for index, stem in enumerate(BOM_ORDER, 1)}


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

# --- explode -----------------------------------------------------------------
# The disassembly order, ASSEMBLY_STEPS read back to front: the hanger's
# loose fastening off, the wire off the eye, the carriage out of the U guides'
# open front ends, the stud and its jam nut up off the rod top, the carriage
# down off the rod's pivot, the rod set screw back out along its tap, the
# marker back out along its own axis, the thumb screw down, the stirrup off
# the paper end. (label, families, axis, signed distance mm), all along the
# assembly's global axes; a move along the yawed block's axes is a pair of
# equal X/Z steps.
EXPLODED_VIEW_NAME = "PN_EXPLODED"
SOURCE_CONFIGURATION = "Default"
# The exploded view's viewer octant (_named_views): REAR-TOP-LEFT. The rod set
# screw's tap opens on the yawed block's front face, whose normal is machine
# (-X, -Z); the built-in *Isometric (+X+Y+Z) sees that face edge-on from
# behind, so its set screw read as a part in the block's top bore. From
# (-1, +1, -1) the face and the tap's axis come toward the reader.
EXPLODED_OCTANT = (-1, 1, -1)
_CARRIAGE = (V_BLOCK, ROD_SET_SCREW, FRAME, THUMB_SCREW, MARKER)
EXPLODE_STEPS = (
    ("hanger jam nut off", (HANGER_JAM_NUT,), "z", -26.0),
    ("hanger nut off", (HANGER_NUT,), "z", -14.0),
    ("hanger screw out behind", (HANGER_SCREW,), "z", 22.0),
    ("wire off the stud eye", (WIRE,), "y", 26.0),
    ("rod out of the guides", (ROD, STUD, STUD_NUT, *_CARRIAGE), "z", -48.0),
    ("stud out of the rod", (STUD, STUD_NUT), "y", 12.0),
    ("jam nut off the stud", (STUD,), "y", 10.0),
    ("carriage off the pivot", _CARRIAGE, "y", -24.0),
    # 36.8 mm along the tap: the screw's cup clears the block's front face
    # and its silhouette below the face's lower edge in the octant view.
    ("rod set screw out x", (ROD_SET_SCREW,), "x", -26.0),
    ("rod set screw out z", (ROD_SET_SCREW,), "z", -26.0),
    ("marker back x", (MARKER,), "x", 36.0),
    ("marker back z", (MARKER,), "z", -36.0),
    ("thumb screw down", (THUMB_SCREW,), "y", -16.0),
    ("stirrup off x", (FRAME,), "x", -16.0),
    ("stirrup off z", (FRAME,), "z", 16.0),
)
EXPLODED_CAPTION = "EXPLODED VIEW - ASSEMBLY SEQUENCE ON SHEET 3"

# --- settings ----------------------------------------------------------------
# STUD HEIGHT (Front plane, sketch (u, v) = machine (X, Y)): a vertical
# construction line on the rod axis from the rod's top face to the stud's
# head top, both in the rest pose the model is saved in.
STUD_FEATURE = "StudSetting"
STUD_DIMENSION = "StudHeadAboveRodTop"
STUD_LINE = (
    (carriage.PEN_ROD_X, carriage.ROD_SQUARE_TOP_REST_Y),
    (carriage.PEN_ROD_X, carriage.STUD_HEAD_TOP_REST_Y),
)
STUD_HEIGHT = carriage.STUD_HEAD_TOP_REST_Y - carriage.ROD_SQUARE_TOP_REST_Y
STUD_TOLERANCE_MM = 0.4
STUD_PRECISION = 1
_STUD_MAJOR = THREAD_MAJOR_MM[stud.THREAD]
_TAP_THREAD_DEPTH = rod.STUD_TAP_SPEC.overrides_mm["ThreadDepth"]
_STUD_ENGAGEMENT_MIN = stud.OVERALL_LENGTH - STUD_HEIGHT - STUD_TOLERANCE_MM
_STUD_ENGAGEMENT_MAX = stud.OVERALL_LENGTH - STUD_HEIGHT + STUD_TOLERANCE_MM

# PEN YAW and NIB PRESET (Top plane, sketch (u, v) = machine (X, -Z), the
# v-block plan sketch's convention): from the marker axis at the block's
# paper-end face, one construction line runs along machine -X (parallel to
# the rod flats and the paper face) and one along the marker axis to the nib
# tip. Their angle is the yaw; the second line's length the nib preset.
CARRIAGE_FEATURE = "CarriageSetting"
YAW_DIMENSION = "PenYaw"
NIB_DIMENSION = "NibProtrusion"
_END_MACHINE = carriage.block_to_machine(
    (0.0, v_block.MARKER_AXIS_Y, v_block.DEPTH_MID_Z)
)
CARRIAGE_END_UV = (_END_MACHINE[0], -_END_MACHINE[2])
NIB_UV = (carriage.MARKER_POS[0], -carriage.MARKER_POS[2])
FLAT_LINE_LENGTH = 18.0  # the rod-flat reference arm, unprinted
FLAT_END_UV = (CARRIAGE_END_UV[0] - FLAT_LINE_LENGTH, CARRIAGE_END_UV[1])
NIB_PROTRUSION = -carriage.MARKER_NIB_LOCAL_X
NIB_TOLERANCE_MM = 0.5
NIB_PRECISION = 1
YAW_DEG = carriage.PEN_BLOCK_YAW_DEG
YAW_TOLERANCE_DEG = 1.0
YAW_PRECISION = 0
# The angle's text point, sketch mm: inside the wedge between the two arms,
# on its bisector (the same wedge on the sheet, which keeps 45 not 135), far
# enough out that the arc's arrowheads land beyond the three-line text block
# (about 26 x 18 sheet mm at 2:1) and the 45-degree arm clears its corner; at
# 15 the arrowhead struck the "1°" (machinist review, farm run
# 20261016T071639431Z).
_BISECTOR_DEG = 180.0 + YAW_DEG / 2.0
YAW_TEXT_RADIUS = 23.0
YAW_TEXT_UV = (
    CARRIAGE_END_UV[0] + YAW_TEXT_RADIUS * math.cos(math.radians(_BISECTOR_DEG)),
    CARRIAGE_END_UV[1] + YAW_TEXT_RADIUS * math.sin(math.radians(_BISECTOR_DEG)),
)
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
# The stud height's text point, machine mm: left of the rod axis, mid-height,
# far enough out that the callout's widest line clears the stud's shank.
STUD_TEXT_XY = (carriage.PEN_ROD_X - 13.0, (STUD_LINE[0][1] + STUD_LINE[1][1]) / 2.0)

# The drawing imports exactly these, at these places.
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    STUD_FEATURE: {STUD_DIMENSION},
    CARRIAGE_FEATURE: {YAW_DIMENSION, NIB_DIMENSION},
}
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    STUD_FEATURE: {STUD_DIMENSION: STUD_PRECISION},
    CARRIAGE_FEATURE: {YAW_DIMENSION: YAW_PRECISION, NIB_DIMENSION: NIB_PRECISION},
}
DIMENSION_TOLERANCES = {
    STUD_DIMENSION: STUD_TOLERANCE_MM,
    NIB_DIMENSION: NIB_TOLERANCE_MM,
}
ANGULAR_TOLERANCES = {YAW_DIMENSION: YAW_TOLERANCE_DEG}
TOLERANCE_PRECISION = {STUD_DIMENSION: 1, NIB_DIMENSION: 1, YAW_DIMENSION: 0}
DIMENSION_NOMINALS = {STUD_DIMENSION: STUD_HEIGHT, NIB_DIMENSION: NIB_PROTRUSION}
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
STUD_DETAIL_CENTRE = (carriage.PEN_ROD_X, STUD_TEXT_XY[1], carriage.PEN_Z_MID)
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
CARRIAGE_AXIS_POINTS = (carriage.MARKER_POS, _END_MACHINE)

SHEET_TITLES = {
    "carriage": "DETAIL C\nPEN YAW + NIB PRESET\nSCALE 2 : 1",
    "stud": "DETAIL A\nSTUD HEIGHT + LOCK\nSCALE 2 : 1",
    "hanger": "DETAIL B\nHANGER SCREW LOCK\nSCALE 2 : 1",
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

# --- contract asserts ---------------------------------------------------------
assert sorted(QUANTITIES) == sorted(BOM_ORDER)
assert set(BOM_DESCRIPTIONS) == set(BOM_ORDER)
assert {stem for _label, stems, _key, _d in EXPLODE_STEPS for stem in stems} == set(
    BOM_ORDER
) - {HANGER}, "every family but the ground hanger moves in the explode"
assert all(key in "xyz" and distance != 0.0 for _l, _s, key, distance in EXPLODE_STEPS)
assert math.isclose(
    STUD_HEIGHT, stud.OVERALL_LENGTH - rod.STUD_ENGAGEMENT, abs_tol=1e-9
)
# Across the stud band the thread stays at least 1.5 D in the rod and short
# of the tap's full-thread depth (drawing-guidelines.md rule 18).
assert _STUD_ENGAGEMENT_MIN >= 1.5 * _STUD_MAJOR, _STUD_ENGAGEMENT_MIN
assert _STUD_ENGAGEMENT_MAX < _TAP_THREAD_DEPTH, _STUD_ENGAGEMENT_MAX
# The nib preset band keeps the grip seated in the V both ways.
assert carriage.MARKER_GRIP_LOCAL_X[0] + NIB_TOLERANCE_MM <= 0.0
assert (
    carriage.MARKER_GRIP_LOCAL_X[1] - NIB_TOLERANCE_MM
    >= v_block.RELIEF_X0 + carriage.CLEARANCE
)
# The nib tip lies on the marker axis through the end-face point.
assert math.isclose(math.dist(CARRIAGE_END_UV, NIB_UV), NIB_PROTRUSION, abs_tol=1e-9), (
    CARRIAGE_END_UV,
    NIB_UV,
)
_nib_dir = (
    (NIB_UV[0] - CARRIAGE_END_UV[0]) / NIB_PROTRUSION,
    (NIB_UV[1] - CARRIAGE_END_UV[1]) / NIB_PROTRUSION,
)
assert math.isclose(
    math.degrees(math.atan2(-_nib_dir[1], -_nib_dir[0])), YAW_DEG, abs_tol=1e-9
), _nib_dir
assert marker.SKU and thumb_screw.SHANK_LEN > 0.0
