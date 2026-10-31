"""Pure fitting contract for pn-pen.SLDASM (MHA-PN-00): inventory, the
exploded view's camera and the three carriage settings.

Builder data only: the builder (``build_pn_pen_assembly``) authors the
settings as blanked construction sketches carrying driving, toleranced model
dimensions; its explode module (``_pn_pen_explode``) authors the
``PN_EXPLODED`` presentation from ``pn_pen_explode_spec``; the fitter drawing
(``draw_pn_pen_assembly``) imports those dimensions. The BOM item numbers and
descriptions, the drawing's dimension display (reference, nominal and
tolerance maps), callouts, detail regions, steps and checks the sheets print
live in ``pn_pen_assembly_sheet``, which only the drawing reads, so a wording
edit does not rebuild the assembly. Every number comes from the part and
carriage contracts (``pn_pen_carriage_geom``, the part/vendor specs); nothing
here restates a dimension. No SolidWorks imports.

Settings (drawing-guidelines.md rule 22 (an assembly package is complete),
setup and adjustment):

* STUD HEIGHT -- the #0-80 eye stud's head top above the rod's top face,
  ``StudHeadAboveRodTop@StudSetting`` on the Right plane, set from the
  stud's measured length so the engagement in the rod's tap stays at least
  1.5 D and short of its guaranteed thread depth; DETAIL A prints the
  nominal stud's value as a reference.
* PEN YAW -- the marker axis to the rod flats (the paper face),
  ``PenYaw@CarriageSetting`` on the Top plane.
* NIB PRESET -- the nib tip beyond the v-block/stirrup paper-end face along
  the marker axis, ``NibProtrusion@CarriageSetting``. The nib-to-paper
  clearance is set at MHA-HA-00, where the paper exists.
"""

from __future__ import annotations

import math

import pn_pen_adjust_screw_spec as stud
import pn_pen_carriage_geom as carriage
import pn_pen_rod_spec as rod
import pn_pen_v_block_spec as v_block
from _hole_spec import THREAD_MAJOR_MM
from _printed_tolerance import printed_band_mm, printed_deviations

ASM_NAME = "pn-pen"

HANGER = "pn-pen-hanger"
ROD = "pn-pen-rod"
STUD = "pn-pen-adjust-screw"
STUD_NUT = "pn-vn-pen-adjust-nut"
V_BLOCK = "pn-pen-v-block"
ROD_SET_SCREW = "pn-vn-pen-rod-set-screw"
FRAME = "pn-pen-frame"
THUMB_SCREW = "pn-vn-pen-set-screw"
MARKER = "pn-vn-pen-marker"
WIRE = "sh-vn-music-wire"
HANGER_SCREW = "pn-vn-hanger-screw"
HANGER_NUT = "pn-vn-pen-hanger-nut"
HANGER_JAM_NUT = "pn-vn-pen-hanger-jam-nut"

# Every component family and its count: the builder places, the explode
# moves and the drawing's BOM proves exactly this inventory. BOM_ORDER is
# the builder's insertion order (hanger, rod, its RIDERS, then the hanger
# fastening), which is the order a top-level BOM numbers its rows in; the
# drawing proves each row's item number against pn_pen_assembly_sheet.ITEM,
# which the steps cite.
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


# --- exploded view -------------------------------------------------------------
# The named explode and its steps live in pn_pen_explode_spec, which only the
# builder's explode module and the drawing read (the EXPLODE refresh tier).
# The exploded view's camera stays here: the builder names it in the
# operational model. The rod set screw's tap opens on the yawed block's front
# face, whose normal is machine (-X, -Z); the built-in *Isometric (+X+Y+Z)
# sees that face edge-on from behind, so its set screw read as a part in the
# block's top bore. The REAR-TOP-LEFT octant (-1, +1, -1) looks straight
# down that normal's plan direction, so the screw's explode along it drew
# straight down the sheet, parallel to model +Y, and read as a screw entering
# the block's bottom face (machinist review, farm run 20261023T222629630Z).
# The camera is that octant turned a further 20 deg about +Y (*Isometric
# turned 200 deg): the block's front-face normal now runs down-left on the
# sheet, 45 deg off its verticals, while the reader still sees the front face,
# the top and the paper end, and the stirrup's window. The "ISO " prefix is
# what marks a pictorial for the shared finalizer and layout audit
# (_drawing_common.is_pictorial_orientation).
EXPLODED_VIEW = "ISO PN EXPLODED"
EXPLODED_VIEW_STANDARD = 7  # swStandardViews_e.swIsometricView: +X+Y+Z
EXPLODED_VIEW_TURN_DEG = 200.0
_TURN = math.radians(EXPLODED_VIEW_TURN_DEG)
# The turn about +Y as the images of the model axes (rows), the
# ``model_rotation`` convention of _assembly_named_views.name_standard_views.
EXPLODED_VIEW_TURN = (
    (math.cos(_TURN), 0.0, -math.sin(_TURN)),
    (0.0, 1.0, 0.0),
    (math.sin(_TURN), 0.0, math.cos(_TURN)),
)
_ISOMETRIC_AXES = (
    (1.0 / math.sqrt(2.0), 0.0, -1.0 / math.sqrt(2.0)),
    (-1.0 / math.sqrt(6.0), 2.0 / math.sqrt(6.0), -1.0 / math.sqrt(6.0)),
    (1.0 / math.sqrt(3.0), 1.0 / math.sqrt(3.0), 1.0 / math.sqrt(3.0)),
)
# The exploded view's (sheet-right, sheet-up, toward-the-reader) axes in model
# coordinates: *Isometric's axes (_named_views.octant_axes(1, 1, 1)) carried
# by the turn.
EXPLODED_VIEW_AXES = tuple(
    tuple(sum(axis[k] * EXPLODED_VIEW_TURN[k][j] for k in range(3)) for j in range(3))
    for axis in _ISOMETRIC_AXES
)


# --- settings ----------------------------------------------------------------
# STUD HEIGHT (Right plane, sketch (u, v) = machine (-Z, Y)): a vertical
# construction line on the rod axis from the rod's top face to the stud's
# head top, both in the rest pose the model is saved in. On the Right plane
# so DETAIL A looks the same way as the RIGHT view its circle is drawn on
# (the eye face-on); from the front the detail was no enlargement of the
# circled region (machinist review, farm run 20261016T102522250Z).
STUD_FEATURE = "StudSetting"
STUD_DIMENSION = "StudHeadAboveRodTop"
STUD_LINE = (
    (-carriage.PEN_Z_MID, carriage.ROD_SQUARE_TOP_REST_Y),
    (-carriage.PEN_Z_MID, carriage.STUD_HEAD_TOP_REST_Y),
)
STUD_HEIGHT = carriage.STUD_HEAD_TOP_REST_Y - carriage.ROD_SQUARE_TOP_REST_Y
# Set by the stud's measured length (owner ruling on code review C05). The
# stud's printed length band (1.02 at two places about the 26.0 closure,
# -.0136/+.0064) is not the engagement's limit: the fitter sets the head top
# the measured length less rod.STUD_ENGAGEMENT, ±STUD_TOLERANCE_MM, so the
# engagement is that band whatever the stud's length. STUD_HEIGHT is that
# setting for a nominal stud, the value the model and DETAIL A's reference
# dimension carry.
STUD_TOLERANCE_MM = 0.381  # ±.015
STUD_PRECISION = 3
_STUD_MAJOR = THREAD_MAJOR_MM[stud.THREAD]
_STUD_LENGTH_DEVIATIONS = printed_deviations(
    stud.OVERALL_LENGTH, stud.OVERALL_PLACES, unit=stud.UNIT
)
STUD_LENGTH_EXTREMES = (
    stud.OVERALL_LENGTH + _STUD_LENGTH_DEVIATIONS[0],
    stud.OVERALL_LENGTH + _STUD_LENGTH_DEVIATIONS[1],
)
_STUD_FULL_THREAD_BAND = printed_band_mm(
    stud.DRAWING_PRECISION_BY_NAME["FullThreadLength"], unit=stud.UNIT
)
# The rod sheet's native tap callout prints the thread depth at the rod's
# places (rod.STUD_TAP_DEPTH_PLACES, "TAP 0-80 UNF .18"), so the shallowest
# accepted full thread is .17.
TAP_THREAD_DEPTH_MIN = rod.STUD_TAP_SPEC.overrides_mm["ThreadDepth"] - printed_band_mm(
    rod.STUD_TAP_DEPTH_PLACES, unit=rod.UNIT
)


def stud_head_setting(stud_length: float) -> float:
    """The head top's height above the rod top for a stud measured at
    ``stud_length`` (mm), the centre of its ±STUD_TOLERANCE_MM band."""
    return stud_length - rod.STUD_ENGAGEMENT


def stud_engagement_range(stud_length: float) -> tuple[float, float]:
    """The thread a stud of ``stud_length`` puts in the rod at the two ends of
    its setting band (head set high, head set low)."""
    setting = stud_head_setting(stud_length)
    return (
        stud_length - (setting + STUD_TOLERANCE_MM),
        stud_length - (setting - STUD_TOLERANCE_MM),
    )


_STUD_ENGAGEMENT_MIN = min(stud_engagement_range(n)[0] for n in STUD_LENGTH_EXTREMES)
_STUD_ENGAGEMENT_MAX = max(stud_engagement_range(n)[1] for n in STUD_LENGTH_EXTREMES)

# PEN YAW and NIB PRESET (Top plane, sketch (u, v) = machine (X, -Z), the
# v-block plan sketch's convention): from the marker axis at the block's
# paper-end face, one construction line runs along machine -X (parallel to
# the rod flats and the paper face) and one along the marker axis to the nib
# tip. Their angle is the yaw; the second line's length the nib preset.
CARRIAGE_FEATURE = "CarriageSetting"
YAW_DIMENSION = "PenYaw"
NIB_DIMENSION = "NibProtrusion"
CARRIAGE_END_MACHINE = carriage.block_to_machine(
    (0.0, v_block.MARKER_AXIS_Y, v_block.DEPTH_MID_Z)
)
CARRIAGE_END_UV = (CARRIAGE_END_MACHINE[0], -CARRIAGE_END_MACHINE[2])
NIB_UV = (carriage.MARKER_POS[0], -carriage.MARKER_POS[2])
FLAT_LINE_LENGTH = 18.0  # the rod-flat reference arm, unprinted
FLAT_END_UV = (CARRIAGE_END_UV[0] - FLAT_LINE_LENGTH, CARRIAGE_END_UV[1])
# A closure (pn_pen_carriage_geom: the nib placed its clearance off the paper
# face), 14.024, printed rounded, .552.
NIB_PROTRUSION = -carriage.MARKER_NIB_LOCAL_X
NIB_TOLERANCE_MM = 0.508  # ±.020
NIB_PRECISION = 3
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

# The builder marks exactly these for the drawing, at these places.
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    STUD_FEATURE: {STUD_DIMENSION},
    CARRIAGE_FEATURE: {YAW_DIMENSION, NIB_DIMENSION},
}
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    STUD_FEATURE: {STUD_DIMENSION: STUD_PRECISION},
    CARRIAGE_FEATURE: {YAW_DIMENSION: YAW_PRECISION, NIB_DIMENSION: NIB_PRECISION},
}

# --- contract asserts ---------------------------------------------------------
assert sorted(QUANTITIES) == sorted(BOM_ORDER)
assert math.isclose(
    STUD_HEIGHT, stud_head_setting(stud.OVERALL_LENGTH), abs_tol=1e-9
)
# Across the stud's printed length band and the setting band the thread stays
# at least 1.5 D in the rod and short of the tap's guaranteed full-thread
# depth (drawing-guidelines.md rule 18), and the shortest accepted full
# thread still covers the deepest engagement, the jam nut and the pen-height
# adjustment.
assert _STUD_ENGAGEMENT_MIN >= 1.5 * _STUD_MAJOR, _STUD_ENGAGEMENT_MIN
assert _STUD_ENGAGEMENT_MAX < TAP_THREAD_DEPTH_MIN, _STUD_ENGAGEMENT_MAX
assert (
    stud.FULL_THREAD_LENGTH - _STUD_FULL_THREAD_BAND
    >= _STUD_ENGAGEMENT_MAX + stud.jam_nut.THICKNESS + stud.ADJUSTMENT_RANGE
), _STUD_ENGAGEMENT_MAX
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
