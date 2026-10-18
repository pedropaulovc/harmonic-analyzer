"""Pure fitting contract for pn-pen.SLDASM (MHA-PN-000): inventory, the
exploded view's octant and the three carriage settings.

The builder (``build_pn_pen_assembly``) authors the settings as blanked
construction sketches carrying driving, toleranced model dimensions; its
explode module (``_pn_pen_explode``) authors the ``PN_EXPLODED``
presentation from ``pn_pen_explode_spec``; the fitter drawing
(``draw_pn_pen_assembly``) imports those dimensions. The BOM descriptions,
callouts, detail regions, steps and checks the sheets print live in
``pn_pen_assembly_notes``, which only the drawing reads, so a wording edit
does not rebuild the assembly. Every number comes from the part and carriage
contracts (``pn_pen_carriage_geom``, the part/vendor specs); nothing here
restates a dimension. No SolidWorks imports.

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
  clearance is set at MHA-HA-000, where the paper exists.
"""

from __future__ import annotations

import math

import pn_pen_adjust_screw_spec as stud
import pn_pen_carriage_geom as carriage
import pn_pen_rod_spec as rod
import pn_pen_v_block_spec as v_block
from _hole_spec import THREAD_MAJOR_MM
from _printed_tolerance import printed_band_mm

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


# --- exploded view -------------------------------------------------------------
# The named explode and its steps live in pn_pen_explode_spec, which only the
# builder's explode module and the drawing read (the EXPLODE refresh tier).
# The exploded view's viewer octant (_named_views) stays here: the builder
# names that octant view in the operational model. REAR-TOP-LEFT: the rod
# set screw's tap opens on the yawed block's front face, whose normal is
# machine (-X, -Z); the built-in *Isometric (+X+Y+Z) sees that face edge-on
# from behind, so its set screw read as a part in the block's top bore. From
# (-1, +1, -1) the face and the tap's axis come toward the reader.
EXPLODED_OCTANT = (-1, 1, -1)


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
# stud's printed length band (26.0 at one place, ±0.8) alone spans 1.6 of the
# 1.70 the tap's guaranteed thread leaves above 1.5 D, so no fixed head
# height holds the engagement: the fitter sets the head top the measured
# length less rod.STUD_ENGAGEMENT, ±STUD_TOLERANCE_MM. STUD_HEIGHT is that
# setting for a nominal stud, the value the model and DETAIL A's reference
# dimension carry.
STUD_TOLERANCE_MM = 0.4
STUD_PRECISION = 1
REFERENCE_DIMENSIONS = frozenset({STUD_DIMENSION})
_STUD_MAJOR = THREAD_MAJOR_MM[stud.THREAD]
STUD_LENGTH_EXTREMES = (
    stud.OVERALL_LENGTH - printed_band_mm(1),
    stud.OVERALL_LENGTH + printed_band_mm(1),
)
# The rod sheet's native tap callout prints the thread depth at two places
# ("TAP 0-80 UNF 4.50"), so the shallowest accepted full thread is 3.99.
TAP_THREAD_DEPTH_MIN = (
    rod.STUD_TAP_SPEC.overrides_mm["ThreadDepth"] - printed_band_mm(2)
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

# The drawing imports exactly these, at these places.
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    STUD_FEATURE: {STUD_DIMENSION},
    CARRIAGE_FEATURE: {YAW_DIMENSION, NIB_DIMENSION},
}
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    STUD_FEATURE: {STUD_DIMENSION: STUD_PRECISION},
    CARRIAGE_FEATURE: {YAW_DIMENSION: YAW_PRECISION, NIB_DIMENSION: NIB_PRECISION},
}
# A reference dimension carries no band: the stud's band rides on the
# measured-length setting the callout and step 1 print.
DIMENSION_TOLERANCES = {NIB_DIMENSION: NIB_TOLERANCE_MM}
ANGULAR_TOLERANCES = {YAW_DIMENSION: YAW_TOLERANCE_DEG}
TOLERANCE_PRECISION = {NIB_DIMENSION: 1, YAW_DIMENSION: 0}
DIMENSION_NOMINALS = {STUD_DIMENSION: STUD_HEIGHT, NIB_DIMENSION: NIB_PROTRUSION}

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
    stud.FULL_THREAD_LENGTH - printed_band_mm(1)
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
