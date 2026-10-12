r"""Create the curated machinist drawing for the magnifying wheel.

A Ø100 cast-iron spider: six tapered spokes, a grooved rim, a Ø25 boss with
the Ø14.5 drum spigot, a reamed axle bore and two wire-tie holes.  The wheel
axis is local +Z, so the FRONT view is the face (rim, spokes, fillets, bore,
ties) and SECTION A-A, cut on the axis through the model's Right plane, is
the hub profile, the groove and the axial widths in solid lines (policy rule
7).  Every size rides the part's marked dimensions; only the rim's axial
width and the rim-bore round's R (on its cut arc) are added on the sheet.
The bore's and the spigot's mates print on
their own diameter callouts (rule 6), and each carries the part-owned
roughness its fit needs (rule 5).

Run with SolidWorks open::

    uv run python cad\scripts\draw_mg_magnifying_wheel.py mg-magnifying-wheel
"""

from __future__ import annotations

import argparse
import math
import sys
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

import _telemetry
from _check import check
from _com import _early_bound
from _drawing_common import (
    DrawingOutputs,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    rebuild_drawing,
    stamp_drawing_summary,
)
from _drawing_dimension_import import curate_view_dimensions
from _drawing_dimensions import assert_imported_precision, set_dimension_callouts
from _drawing_edge_dimensions import add_edge_dimension, assert_dimension_measures
from _drawing_edges import ViewEdges, scan_view_edges
from _drawing_finish import add_surface_finish
from _drawing_leaders import (
    assert_leaders_clear,
    dimension_segments,
    leader_segments,
    section_line_segments,
    set_near_side_diameter,
)
from _drawing_notes import add_property_linked_note
from _drawing_projection import model_points_in_view
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_sections import create_section_view
from _drawing_selection import _select_view_entity
from _drawing_view_display import set_hidden_lines_removed
from _gear_drawing_entities import visible_circle_edge
from _layout_geometry import Box, estimate_text_box
from _paths import CAD_ROOT
from _section_axis import position_section_caption
from _session import run_build
from _surface_finish import surface_finish_by_key
from mg_magnifying_wheel_geom import (
    HUB_BACK_Z,
    HUB_FRONT_Z,
    HUB_STEP_Z,
    SPOKE_X0,
)
from mg_magnifying_wheel_spec import (
    BORE_DIA,
    CAST_ROUND_R,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION,
    DRAWING_REFERENCE_PRECISION,
    HUB_DIA,
    HUB_FILLET_R,
    RIM_AXIAL,
    RIM_FILLET_R,
    RIM_INNER_DIA,
    RIM_OUTER_DIA,
    SPIGOT_DIA,
    SURFACE_FINISHES,
    TIE1_CLOCK_DEG,
    TIE1_R,
    TIE2_CLOCK_DEG,
    TIE_HOLE_DIA,
    clock_to_local_deg,
    fillet,
)
from mg_wheel_axle_spec import PIN_DIA, PIN_DIA_TOL
from mg_wheel_drum_geom import DRUM_BORE, DRUM_BORE_BAND
from solidworks_mcp.adapters.com_variant import double_array
from solidworks_mcp.adapters.solidworks.drawing import dimension_name, place_view


SPEC = DRAWINGS_BY_NAME["mg_magnifying_wheel"]
PART_STEM = SPEC.artifact_stem
SOURCE = CAD_ROOT / "out" / "sldprt" / f"{PART_STEM}.SLDPRT"
OUTPUTS = DrawingOutputs(
    slddrw=SPEC.outputs["slddrw"],
    pdf=SPEC.outputs["pdf"],
    png=SPEC.outputs["png"],
)
SLDDRW = OUTPUTS.slddrw
PDF = OUTPUTS.pdf
PNG = OUTPUTS.png

SHEET_SCALE = (1.0, 1.0)
FRONT_CENTER = (0.125, 0.150)
# Section A-A stands right of the face, 15 mm above its axis (it is placed
# unaligned, so its y is set here): the side view's caption was one small
# line, the section's native SECTION A-A is a tall one (~17 mm on the crank
# drive gear), and it needs the room between the hub's axial rows and the
# title block.
SECTION_CENTER = (0.255, 0.165)
# The isometric stands right of the section's Ø14.5 text, ISO_CLEAR off it.
ISO_CENTER = (0.367, 0.150)
ISO_CLEAR = 0.005

_RIM_R = RIM_OUTER_DIA * SHEET_SCALE[0] / 2000.0
# The cutting line runs the face view's full height on the axis, this far
# past the OD at each end; the A-A caption's top centre stands under the
# section's axial rows, above the title block.
SECTION_LINE_OVERRUN = 0.006
SECTION_LINE_LANDING = (0.0, _RIM_R + SECTION_LINE_OVERRUN + 0.005)
SECTION_CAPTION_XY = (SECTION_CENTER[0], 0.088)
_SECTION_PLACEMENT_TOL = 1e-5

DRAWING_PRECISION_BY_NAME = {
    name: digits
    for names in DRAWING_PRECISION.values()
    for name, digits in names.items()
}

# Face view.  The sheet's front view is the model's XY plane at 1:1 (sheet x
# = model x), so each text point below is derived from the feature it names.
# Every text and finish symbol stands outside the Ø100 silhouette (policy
# rule 8) except the spoke-root width, whose vertical dimension line would
# otherwise run across the next spoke and the rim, and no leader or shoulder
# may cross another's line.  Farm run 7 (396077c3e) failed on exactly that:
# the native Ø100 and Ø88 lines ran rim to rim through the centre, so the
# shoulders under them crossed them.  The three diameters take one arrow on
# their near rim (set_near_side_diameter), so only the bore's leader and its
# finish's cross the face.  The A-A cutting line stands on the axis
# (x = 0): its arrows point left (the section looks along -X) with their
# letters beyond the tips, so every leader leaves its feature away from it.
#
# A dimension's position is its text block's mid-height above the point its
# leader or shoulder meets (run 7 readback: the one-line Tie1Y shoulder ran
# 2.8 mm under its point, the two-line SpokeRootWidth one 5.6 mm; the crank
# drive gear's multi-line bore callout stands on one shoulder under its last
# line), and its text runs away from the feature it measures.
_TEXT_LINE = 0.0056
# A leadered Ø callout's shoulder starts this far (mm) left of its point, and
# its stacked tolerance tops out this far over it (run 8 readback).
_CALLOUT_SHOULDER_LEFT = 15.3
_CALLOUT_ABOVE = 6.3


def _face(x_mm: float, y_mm: float) -> tuple[float, float]:
    """A model XY point (mm) on the sheet (m)."""
    return (
        FRONT_CENTER[0] + x_mm * SHEET_SCALE[0] / 1000.0,
        FRONT_CENTER[1] + y_mm * SHEET_SCALE[0] / 1000.0,
    )


def _polar(origin_mm: tuple[float, float], bearing_deg: float, reach_mm: float):
    """The model point ``reach_mm`` from ``origin_mm`` along ``bearing_deg``."""
    bearing = math.radians(bearing_deg)
    return (
        origin_mm[0] + reach_mm * math.cos(bearing),
        origin_mm[1] + reach_mm * math.sin(bearing),
    )


def _over(attach_mm: tuple[float, float], lines: int) -> tuple[float, float]:
    """The text point whose ``lines``-line block stands on ``attach_mm``."""
    x, y = _face(*attach_mm)
    return (x, y + lines * _TEXT_LINE / 2.0)


_HUB_FILLET_CENTRE = fillet(HUB_DIA / 2.0, HUB_FILLET_R, outside=True)["centre"]
_RIM_FILLET_CENTRE = fillet(RIM_INNER_DIA / 2.0, RIM_FILLET_R, outside=False)["centre"]
_TIE1 = _polar((0.0, 0.0), clock_to_local_deg(TIE1_CLOCK_DEG), TIE1_R)
# TIE 2's angle is driven between its radial axis (outward at 223 deg) and the
# horizontal inner end, where the axis enters the rim bore: the sketch's own
# sector runs from that point's outward horizontal (180 deg) to the axis, so
# a text in it draws one arc and no extension arcs.  Its text stands 35 mm
# out on the sector's bisector, past the OD, so its arc meets the axis 79 mm
# out: beyond the end of TIE 2's Ø extension lines (run 11: the arc, 15 mm
# out, crossed them).
_TIE2_OUTWARD = clock_to_local_deg(TIE2_CLOCK_DEG) % 360.0
_TIE2_INNER = _polar((0.0, 0.0), _TIE2_OUTWARD, RIM_INNER_DIA / 2.0)
_TIE2_ANGLE_SECTOR = (180.0, _TIE2_OUTWARD)
# A leader-borne radius's shoulder starts this far (mm) left of its point
# (run 11 readback: the R3.0's at 142.9 for a point at 149.1).
_RADIUS_SHOULDER_LEFT = 6.2
_HUB_FILLET_SHOULDER = _polar((0.0, 0.0), 30.0, RIM_OUTER_DIA / 2.0 + 10.0)
# A near-side Ø's leader runs radially from its circle to its shoulder's near
# end, 10.0 mm left of its text point and 2.8 mm under it; the Ø88's shoulder
# is 18.5 mm long (run 12c readback: 136.57 to 155.07 for a text point at
# 146.62).  Run 12c's Ø88 left the rim bore at 79 deg and crossed the A-A
# line's top arrow; the 60-120 window has no landing whose radial leader
# clears that arrow and its letter, so the Ø88 lands in the 0-60 window at
# 19 deg, its near end 14 mm past the OD: the block stands between the R4's
# (top 16.5 mm above the axis) and the R3's shoulder (30 mm), right of the
# wheel and left of A-A's Ø25.
_DIA_SHOULDER_LEFT = 10.0
_RIM_INNER_SHOULDER = _polar((0.0, 0.0), 19.0, RIM_OUTER_DIA / 2.0 + 14.0)
# The bore's block: its "RUNS ON MG-WHEEL-AXLE" line is the face's widest
# text (21 characters at run 7's 2.45 mm each); the block stands left of the
# wheel on a shoulder 30 mm above the axis, its right end 7 mm off the OD.
_BORE_SHOULDER_Y = 30.0
_BORE_BLOCK_HALF = 21 * 2.45 / 2.0
_BORE_BLOCK_X = (
    -math.sqrt((RIM_OUTER_DIA / 2.0) ** 2 - _BORE_SHOULDER_Y**2)
    - 7.0
    - _BORE_BLOCK_HALF
)
FRONT_KEEP = {
    # Near-side, one arrow each: Ø100 up-left on the OD, over the bore's
    # block; Ø88 right through the 0-60 window at 19 deg, clear of the A-A
    # line; the bore up-left through the 120-180 window to its block's
    # shoulder (stacked Ø plus three callout lines).
    "RimOuterDiaDim": _over(_polar((0.0, 0.0), 125.0, RIM_OUTER_DIA / 2.0 + 40.0), 1),
    "RimInnerDiaDim": _over(
        (_RIM_INNER_SHOULDER[0] + _DIA_SHOULDER_LEFT, _RIM_INNER_SHOULDER[1]), 1
    ),
    "BoreDiaDim": _over((_BORE_BLOCK_X, _BORE_SHOULDER_Y), 5),
    # The R3 (concave, inside the 0-60 window) leadered out along the window
    # to a shoulder past the OD at 30 deg; the R4 (convex, from outside the
    # rim) on its centre's -3 deg ray, past the OD and above the tip width's
    # extension lines.
    "HubFilletR": _over(
        (_HUB_FILLET_SHOULDER[0] + _RADIUS_SHOULDER_LEFT, _HUB_FILLET_SHOULDER[1]), 2
    ),
    "RimFilletR": _over(_polar(_RIM_FILLET_CENTRE, -3.0, 26.0), 2),
    # Each spoke width beside its own end, its text down into the 300-360
    # window: the root's line inside the hub fillets' feet, the tip's outside
    # the rim, so neither's extension lines reach the other's line.  The
    # root's text stays inside the silhouette: outside, its vertical line
    # would run 45 mm across the 300 deg spoke and the rim.
    "SpokeRootWidth": _over((SPOKE_X0 + 4.5, -22.0), 2),
    "SpokeTipWidth": _over((RIM_OUTER_DIA / 2.0 + 3.0, -22.0), 2),
    # TIE 1's 9.85 between its own extension lines, which run left from the
    # bore's and the hole's centres past the OD: the text breaks its line
    # 16 mm outside the rim, a quarter line under mid-span, so the block
    # stays between the lines whether its point reads as the block's middle
    # or (inside the lines) its bottom.
    "Tie1Y": _face(
        -(RIM_OUTER_DIA / 2.0 + 16.0), _TIE1[1] / 2.0 - _TEXT_LINE * 1000.0 / 4.0
    ),
    # The two tie Ø callouts hang off the face, the block's leader from its
    # shoulder's near end (the shoulder runs 7.3 mm under the point).  TIE
    # 1's block stands below the wheel, its top (DRILL THRU over the stacked
    # Ø) 3.2 mm under the OD; its shoulder starts 20 mm right of the hole, so
    # the leader slopes away from the A-A line that runs through the hole
    # (run 11 dropped it down that line).
    "Tie1HoleDia": _face(
        _TIE1[0] + 20.0 + _CALLOUT_SHOULDER_LEFT,
        -RIM_OUTER_DIA / 2.0 - 3.2 - _CALLOUT_ABOVE - _TEXT_LINE * 1000.0,
    ),
    "Tie2Angle": _face(*_polar(_TIE2_INNER, sum(_TIE2_ANGLE_SECTOR) / 2.0, 35.0)),
    # TIE 2's Ø is a linear width across the radial hole: its extension lines
    # run out along the hole's axis to the dimension line's foot, ~1 mm past
    # the text's projection onto the axis.  Run 8 hung the block ON that foot,
    # so both lines ran through it: the block stands 25 mm off the axis on
    # the side away from the angle, its projection 75 mm out (the extension
    # lines stop ~76, short of the angle's arc at 79), a one-line "TIE 2"
    # under it (the hole's run is in the notes); it stays outside the OD and
    # left of the A-A line's lower "A".
    "Tie2HoleDia": _face(
        *_polar(_polar((0.0, 0.0), _TIE2_OUTWARD, 75.0), _TIE2_OUTWARD + 90.0, 25.0)
    ),
}
# Near-side leaders: no segment of these comes nearer the axis than half the
# circle's radius, and each ends on its own circle (sheet metres; a reading
# outside the band means the ink is not in sheet space).
NEAR_SIDE_DIAMETERS = {
    "RimOuterDiaDim": RIM_OUTER_DIA,
    "RimInnerDiaDim": RIM_INNER_DIA,
    "BoreDiaDim": BORE_DIA,
}
# TIE 1 sits ON the A-A line, so its Ø takes one arrow on the rim nearest its
# block, down-right of the hole, and no line through the centre (run 11's
# default leader ran down the cutting line).  Every face leader near the line
# is proven off it, each landing on its own feature's radius from the axis.
TIE1_NEAR_SIDE = "Tie1HoleDia"
_BORE_LANDING = (0.8 * BORE_DIA / 2000.0, 1.2 * BORE_DIA / 2000.0)
FACE_LEADER_LANDINGS = {
    "RimOuterDiaDim": (0.8 * RIM_OUTER_DIA / 2000.0, 1.2 * RIM_OUTER_DIA / 2000.0),
    "RimInnerDiaDim": (0.8 * RIM_INNER_DIA / 2000.0, 1.2 * RIM_INNER_DIA / 2000.0),
    "BoreDiaDim": _BORE_LANDING,
    "BoreFinish": _BORE_LANDING,
    TIE1_NEAR_SIDE: (
        (TIE1_R - TIE_HOLE_DIA) / 1000.0,
        (TIE1_R + TIE_HOLE_DIA) / 1000.0,
    ),
    "SectionLine": SECTION_LINE_LANDING,
}
# The template centre-marks each hole as the view is placed, so an explicit
# AutoInsertCenterMarks2 printed a second, identical mark (run 7: two
# duplicate-annotation findings; sm_knife_mount #913).  Each mark keeps its
# cross only: the extended lines ran 47.5 mm along the axes, through the
# bore's Ø text and every window's dimension.  The face view is 1:1, so the
# mark's model-length arm is its sheet length.
CENTRE_MARK_ARM = 0.0025
_CENTER_MARK_ANNOTATION = 13  # swAnnotationType_e.swCenterMarkSym
_MARK_ON_HOLE = 0.0005
# Section A-A: sheet right = model -Z (the pen side, where the spigot
# stands), model +Y up, as the Right view drew it; _orient_section proves
# both and puts the hub's back face on the axis at _section_x(HUB_BACK_Z), so
# the section centres on the part's axial extent and each hub face's sheet x
# follows from its z.
_SIDE_MID_Z = (HUB_BACK_Z + HUB_FRONT_Z) / 2.0


def _section_x(z_mm: float) -> float:
    """The section's sheet x (m) of the model plane at ``z_mm``."""
    return SECTION_CENTER[0] + (_SIDE_MID_Z - z_mm) * SHEET_SCALE[0] / 1000.0


# Run 7 printed "9.85 ±0.05" (10 characters) 24.5 mm wide.
_TEXT_CHAR = 0.00245
# Text kept this far off any extension line it does not own, past the half
# text height inside which the audit gates a crossing (DIM_CROSSING_TEXT_HEIGHTS).
_TEXT_OFF_LINE = 0.004


def _beside(face_x: float, side: int, chars: int, y: float) -> tuple[float, float]:
    """A ``chars``-wide text centred ``side`` (-1 left, +1 right) of ``face_x``."""
    return (face_x + side * (_TEXT_OFF_LINE + chars * _TEXT_CHAR / 2.0), y)


# Section text points (the side view's run-8 readback): a size whose text stands between
# its extension lines prints it centred on the point, breaking its line round
# it; one whose text stands outside hangs it off the line's end, centred on
# the point (axial) or running from the point away from the view (diameters).
# A one-line text's point stands _ONE_LINE_UP over its dimension line, a
# stacked tolerance's _STACK_UP; the line runs 6.3 mm past the extension line
# away from its text.
_ONE_LINE_UP = 0.0028
_STACK_UP = 0.0045
# Run 8 printed "Ø25.00 +0.1/-0.1" 30.1 mm wide.
_DIA_TEXT_HALF = 0.0151
# Run 8 stacked all three diameters right of the view, where the Ø14.5 printed
# over the isometric and the Ø97.6's line ran through it, and the axial sizes
# below the hub, where the 4.0's line crossed three hub extension lines.
#
# Left of the view, the Ø25 and the Ø97.6 print BETWEEN their extension
# lines: the Ø25 centred on the hub, its line _TEXT_OFF_LINE plus half its
# text left of the back face; the Ø97.6 up between the hub and the rim bore,
# its line as far again left of the Ø25's, so neither line nor text reaches
# the other's, and the hub's extension lines stop short of the Ø97.6's line.
_HUB_DIA_X = _section_x(HUB_BACK_Z) - _TEXT_OFF_LINE - _DIA_TEXT_HALF
_GROOVE_DIA_X = _HUB_DIA_X - _DIA_TEXT_HALF - _TEXT_OFF_LINE
# Above the hub, two rows left of the back face, the spokes' 4.0 under the
# rim's 8.00 (added below): both lines run from the part leftward to their
# text, above the hub's extension lines and under the rim bore.
_SPOKE_ROW = SECTION_CENTER[1] + HUB_DIA / 2000.0 + 0.0055
_RIM_WIDTH_ROW = _SPOKE_ROW + 0.010
# The hub's three axial sizes below the rim, one row each, all from the hub's
# faced back end (policy rule 7) except the spigot's own length, which the
# drum's length must match (DRUM_RECESS); each text OUTSIDE its span so no
# extension line runs through a text (run 7: four extension-through-own-text
# findings): HubBackZ ("7.09") left of the back face, its arrows inside its
# span so no tail crosses the spigot step's extension line (run 11);
# SpigotLength ("9.00 +0.10/0") right of the spigot end; the overall
# HubLength ("19.60 ±0.10") left of the back face under HubBackZ, above the
# A-A caption.
_HUB_ROWS = tuple(SECTION_CENTER[1] - _RIM_R - 0.007 * row for row in (1, 2, 3))
ARROWS_INSIDE = ("HubBackZ",)
_DIM_ARROWS_INSIDE = 0  # swDimensionArrowsSide_e.swDimArrowsInside
SECTION_KEEP = {
    "HubDia": (_HUB_DIA_X, SECTION_CENTER[1]),
    "GrooveBottomDia": (_GROOVE_DIA_X, SECTION_CENTER[1] + 0.035),
    # Right of the view only the spigot's Ø, its line 7.2 mm past the spigot
    # end and its text under the spigot, so the press-fit callout lines
    # stack down toward the spigot length's row: ISO_CLEAR off the
    # isometric, proven at build (_assert_text_off_iso).
    "SpigotDia": (
        _section_x(HUB_FRONT_Z) + 0.0072,
        SECTION_CENTER[1] - SPIGOT_DIA / 2000.0 - 0.012,
    ),
    "SpokeAxial": _beside(_section_x(HUB_BACK_Z), -1, 3, _SPOKE_ROW + _ONE_LINE_UP),
    "HubBackZ": _beside(_section_x(HUB_BACK_Z), -1, 4, _HUB_ROWS[0] + _ONE_LINE_UP),
    "SpigotLength": _beside(_section_x(HUB_FRONT_Z), 1, 12, _HUB_ROWS[1] + _STACK_UP),
    "HubLength": _beside(_section_x(HUB_BACK_Z), -1, 11, _HUB_ROWS[2] + _STACK_UP),
    # The groove's R up right, its leader down-left onto the groove clear of
    # the rim's front corner, so the Ø97.6's extension line, which leaves the
    # groove bottom leftward, runs nowhere near its arrow.
    "GrooveR": (SECTION_CENTER[0] + 0.020, SECTION_CENTER[1] + 0.060),
}
# The rim-bore round's R is a sheet radial on its cut arc: A-A cannot import
# a fillet radius whose arc IS the cut (round-12 farm leaves: neither the
# targeted import nor DragModelDimension landed CastRoundR there).  It takes
# the arc at the rim's front (sheet-right, model -Z) top corner, the circle's
# centre one R in from the bore and the side face, normal to the cut plane.
# Its callout stands right, between the spigot's finish and the groove's R,
# its shoulder 10 mm under the rim bore: the Ø97.6 holds the left.
_ROUND_ARC_CENTER = (
    0.0,
    RIM_INNER_DIA / 2.0 + CAST_ROUND_R,
    -(RIM_AXIAL / 2.0 - CAST_ROUND_R),
)
_CUT_NORMAL = (1.0, 0.0, 0.0)
ROUND_TEXT_XY = (SECTION_CENTER[0] + 0.0292, SECTION_CENTER[1] + 0.0413)
ROUND_CALLOUT = "2X RIM BORE EDGES"


def _band_mm(low: float, high: float) -> str:
    """``low-high`` to the .XXX place, rounded half up: a float's 4.7575 is
    4.75749..., which ``:.3f`` prints 4.757."""
    return "-".join(
        str(Decimal(repr(round(value, 6))).quantize(Decimal("0.001"), ROUND_HALF_UP))
        for value in (low, high)
    )


# The two fits print on their own diameters (policy rule 6), every limit read
# from the mate's spec: the axle's 3/16 drill rod runs in the reamed bore;
# the spigot is pressed into the drum's H7 bore.
_AXLE_LIMITS = _band_mm(PIN_DIA - PIN_DIA_TOL, PIN_DIA + PIN_DIA_TOL)
_DRUM_BORE_LIMITS = _band_mm(
    DRUM_BORE + DRUM_BORE_BAND[1], DRUM_BORE + DRUM_BORE_BAND[0]
)
DIMENSION_CALLOUTS = {
    "BoreDiaDim": f"REAM THRU\nRUNS ON MG-WHEEL-AXLE\n<MOD-DIAM>{_AXLE_LIMITS}",
    "SpigotDia": f"PRESS FIT IN\nMG-WHEEL-DRUM\n<MOD-DIAM>{_DRUM_BORE_LIMITS}\nBORE",
    "SpokeRootWidth": "6X ROOT",
    "SpokeTipWidth": "6X TIP",
    "HubFilletR": "12X",
    "RimFilletR": "12X",
    "Tie1HoleDia": "TIE 1",
    "Tie2HoleDia": "TIE 2",
}
# The tie holes' operation stands over their Ø, keeping each block as narrow
# as its stacked Ø.
CALLOUTS_ABOVE = {
    "Tie1HoleDia": "DRILL THRU",
    "Tie2HoleDia": "DRILL THRU",
}
# Three note lines, top-left anchored, under the two tie blocks and left of
# the title block.
NOTES_XY = (0.020, 0.062)

# The rim's axial width spans its two OD corner circles (r = RIM_OUTER_DIA/2 at
# z = +/-RIM_AXIAL/2; the rim is extruded both ways off the mid-plane). Edge-on
# in the section each is a vertical line beyond the cut, picked as a native
# entity.
_RIM_AXIS = (0.0, 0.0, 1.0)
# The bore's finish symbol stands outside the OD up the 0-60 window, 45 deg,
# between the R3's shoulder and the Ø88's text; its leader lands on the bore
# on that bearing, right of the A-A line.
_BORE_FINISH_BEARING = 45.0
BORE_FINISH_SYMBOL = _face(
    *_polar((0.0, 0.0), _BORE_FINISH_BEARING, RIM_OUTER_DIA / 2.0 + 16.0)
)
_BORE_FINISH_POINT = (*_polar((0.0, 0.0), _BORE_FINISH_BEARING, BORE_DIA / 2.0), 0.0)
# The spigot's finish lands mid-length on the spigot's upper cut line (the
# cylinder's edge where the A-A plane cuts it, model +Y), its symbol up and
# right of the landing, above the Ø14.5's upper extension line and under the
# rim-bore round's shoulder (sheet metres).
_SPIGOT_FINISH_POINT = (0.0, SPIGOT_DIA / 2.0, (HUB_STEP_Z + HUB_FRONT_Z) / 2.0)
_SPIGOT_FINISH_OFFSET = (0.012, 0.014)
FINISH_CHAR_HEIGHT = 0.0025


def _near_side_diameters(
    adapter: Any, annotations: list[Any], *, axis: tuple[float, float]
) -> None:
    """One arrow on each face-view diameter's near rim, proven off the face."""
    named = {
        dimension_name(adapter, annotation): annotation for annotation in annotations
    }
    for name in (*NEAR_SIDE_DIAMETERS, TIE1_NEAR_SIDE):
        set_near_side_diameter(named[name], f"wheel {name}")
    rebuild_drawing(adapter, label="wheel near-side diameters")
    radii = {
        name: diameter * SHEET_SCALE[0] / 2000.0
        for name, diameter in NEAR_SIDE_DIAMETERS.items()
    }
    assert_leaders_clear(
        {name: dimension_segments(named[name]) for name in NEAR_SIDE_DIAMETERS},
        centre=axis,
        keep_out={name: radius / 2.0 for name, radius in radii.items()},
        lands_within={
            name: (0.8 * radius, 1.2 * radius) for name, radius in radii.items()
        },
        label="wheel near-side diameters",
    )


def _trim_centre_marks(
    adapter: Any, view: Any, holes: dict[str, tuple[float, float]]
) -> None:
    """Keep the template's centre marks as bare crosses, one per hole, and
    fail on a second mark at any hole or a mark at no hole."""
    marks = [
        _early_bound(annotation, "IAnnotation")
        for annotation in _early_bound(view, "IView").GetAnnotationsByType(
            _CENTER_MARK_ANNOTATION
        )
        or ()
    ]
    for annotation in marks:
        mark = _early_bound(annotation.GetSpecificAnnotation(), "ICenterMark")
        mark.UseDocDisplaySettings = False
        mark.ShowLines = False
        mark.Size = CENTRE_MARK_ARM
    rebuild_drawing(adapter, label="trim wheel centre marks")
    marked = []
    for annotation in marks:
        mark = _early_bound(annotation.GetSpecificAnnotation(), "ICenterMark")
        if bool(mark.UseDocDisplaySettings) or bool(mark.ShowLines):
            raise RuntimeError("a wheel centre mark kept its extended lines")
        data = _early_bound(annotation.GetDisplayData(), "IDisplayData")
        lines = [
            tuple(float(value) for value in data.GetLineAtIndex2(index))
            for index in range(int(data.GetLineCount()))
        ]
        if not lines:
            raise RuntimeError("a wheel centre mark draws no line")
        xs = [value for line in lines for value in (line[4], line[7])]
        ys = [value for line in lines for value in (line[5], line[8])]
        centre = ((min(xs) + max(xs)) / 2.0, (min(ys) + max(ys)) / 2.0)
        marked.append(
            next(
                (
                    name
                    for name, hole in holes.items()
                    if math.dist(hole, centre) <= _MARK_ON_HOLE
                ),
                f"no hole at {centre}",
            )
        )
    if (
        marked.count("bore") != 1
        or marked.count("tie 1") > 1
        or set(marked) - set(holes)
    ):
        raise RuntimeError(f"expected one centre mark per wheel hole, found {marked}")
    _telemetry.info(f"wheel centre marks: {sorted(marked)}")


def _assert_text_off_iso(adapter: Any, annotations: list[Any], iso: Any) -> None:
    """Fail when any dimension's text block comes within ISO_CLEAR of the
    isometric's outline (run 8 printed the side view's Ø14.5 over the iso
    wheel).  Every text item a dimension draws (value, stacked tolerance,
    callout lines) is boxed by the layout audit's estimator, as
    draw_dt_cone_gear_shaft does: no API returns a text's width."""
    iso_box = Box(*(float(value) for value in _early_bound(iso, "IView").GetOutline()))
    nearest = math.inf
    crowding = []
    for annotation in annotations:
        annotation = _early_bound(annotation, "IAnnotation")
        label = dimension_name(adapter, annotation) or "unnamed dimension"
        display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
        data = _early_bound(display.GetDisplayData(), "IDisplayData")
        for index in range(int(data.GetTextCount())):
            anchor = [float(value) for value in data.GetTextPositionAtIndex(index)]
            reference = int(data.GetTextRefPositionAtIndex(index))
            box = estimate_text_box(
                str(data.GetTextAtIndex(index) or ""),
                anchor=(anchor[0], anchor[1]),
                height=float(data.GetTextHeightAtIndex(index)),
                reference=reference if 0 <= reference <= 5 else 0,
                angle=float(data.GetTextAngleAtIndex(index)),
            )
            if box is None:
                continue
            gap = box.gap(iso_box)
            nearest = min(nearest, gap)
            if gap < ISO_CLEAR:
                crowding.append(f"{label} {box.format_mm()}")
    if crowding:
        raise RuntimeError(
            f"dimension text within {ISO_CLEAR * 1000:.0f} mm of the isometric "
            f"{iso_box.format_mm()}: {crowding}"
        )
    _telemetry.info(
        f"wheel dimension text clears the isometric {iso_box.format_mm()} by "
        f"{nearest * 1000:.1f} mm"
    )


def _orient_section(adapter: Any, section: Any) -> None:
    """Stand section A-A as SECTION_KEEP draws it: the hub's back face left of
    the spigot, +Y up, the back face on the axis at
    (_section_x(HUB_BACK_Z), SECTION_CENTER[1]).

    A half turn swaps both ways; reversing the cut (looking from the other
    side of the plane) mirrors left-right only, so the two fix every
    orientation, as draw_pd_transgear_thumbnut's _stand_section_rim_up.  The
    view is then moved by its projection, not its outline: the hub stands
    off the rim's mid-plane, so the outline's centre is not a hub face.
    """
    native = _early_bound(section, "IView")

    def read() -> list[tuple[float, float]]:
        return model_points_in_view(
            adapter,
            native,
            (
                (0.0, 0.0, HUB_BACK_Z / 1000.0),
                (0.0, 0.0, HUB_FRONT_Z / 1000.0),
                (0.0, RIM_OUTER_DIA / 2000.0, HUB_BACK_Z / 1000.0),
            ),
            label="wheel section orientation",
            names=("hub back face", "spigot end", "rim top"),
        )

    back, front, top = read()
    if top[1] < back[1]:
        native.Angle = float(native.Angle) + math.pi
        rebuild_drawing(adapter, label="wheel section turned")
        back, front, top = read()
    if back[0] > front[0]:
        cut = _early_bound(native.GetSection(), "IDrSection")
        reversed_cut = not bool(cut.GetReversedCutDirection())
        cut.SetReversedCutDirection(reversed_cut)
        rebuild_drawing(adapter, label="wheel section reversed")
        if bool(cut.GetReversedCutDirection()) != reversed_cut:
            raise RuntimeError("wheel section cut direction did not persist")
        back, front, top = read()
    if not (back[0] < front[0] and top[1] > back[1]):
        raise RuntimeError(
            f"wheel section A-A is not back face left, +Y up: back={back}, "
            f"spigot end={front}, rim top={top}"
        )
    target = (_section_x(HUB_BACK_Z), SECTION_CENTER[1])
    for attempt in range(4):
        if math.dist(back, target) <= _SECTION_PLACEMENT_TOL:
            break
        position = tuple(float(value) for value in native.Position)
        moved = [position[axis] + target[axis] - back[axis] for axis in (0, 1)]
        if not native.SetViewPosition(double_array(moved), False):
            raise RuntimeError("failed to move wheel section A-A")
        rebuild_drawing(adapter, label=f"wheel section placed, pass {attempt}")
        back, front, top = read()
    else:
        raise RuntimeError(
            f"wheel section A-A back face stayed at {back}, requested {target}"
        )
    _telemetry.info(
        f"wheel section: angle={float(native.Angle):.6f} rad, back={back}, "
        f"spigot end={front}, rim top={top}"
    )


def _set_arrows_inside(adapter: Any, annotations: list[Any]) -> None:
    """Stand each ARROWS_INSIDE dimension's arrows inside its extension lines,
    as draw_dt_cone_tip_block's _set_arrow_sides."""
    remaining = set(ARROWS_INSIDE)
    for raw in annotations:
        annotation = _early_bound(raw, "IAnnotation")
        name = dimension_name(adapter, annotation)
        if name not in remaining:
            continue
        remaining.discard(name)
        display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
        display.ArrowSide = _DIM_ARROWS_INSIDE
        if int(display.ArrowSide) != _DIM_ARROWS_INSIDE:
            raise RuntimeError(f"{name} did not keep its arrows inside")
    if remaining:
        raise RuntimeError(f"no dimension to set arrows inside: {sorted(remaining)}")


def _assert_face_leaders_clear(
    adapter: Any,
    front: Any,
    annotations: list[Any],
    bore_finish: Any,
    *,
    axis: tuple[float, float],
) -> None:
    """Fail unless the face's leaders, the bore finish's and the A-A cutting
    line cross none of each other (policy rule 8), each landing on its own
    feature."""
    named = {
        dimension_name(adapter, annotation): annotation for annotation in annotations
    }
    groups = {
        name: dimension_segments(named[name])
        for name in (*NEAR_SIDE_DIAMETERS, TIE1_NEAR_SIDE)
    }
    groups["BoreFinish"] = leader_segments(bore_finish.GetAnnotation())
    groups["SectionLine"] = section_line_segments(adapter, front)
    assert_leaders_clear(
        groups,
        centre=axis,
        keep_out={},
        lands_within=FACE_LEADER_LANDINGS,
        label="wheel face leaders vs A-A",
    )


def _add_round_radius(adapter: Any, section: Any, edges: ViewEdges) -> Any:
    """Dimension the rim-bore round on its A-A cut arc (the T rail root radius
    pattern of draw_fr_top_frame) and return its annotation.

    The arc is picked as a native entity from the section's edge scan, so a
    moved round fails loud in ``circle_at``; the radial must attach to that
    arc alone and measure the spec's R (``assert_dimension_measures``).  No
    band is drawn: the spec's three places put it under the title block's
    .XXX row, which ``TIE2_FACE_WALL`` is proved against.
    """
    label = "rim bore round"
    arc = edges.circle_at(
        _ROUND_ARC_CENTER, CAST_ROUND_R, axis=_CUT_NORMAL, label=label
    ).edge
    draw = adapter.currentModel
    _select_view_entity(adapter, section, "EDGE", None, label=label, entity=arc)
    display = draw.AddRadialDimension2(*ROUND_TEXT_XY, 0.0)
    draw.ClearSelection2(True)
    if display is None:
        raise RuntimeError(f"failed to dimension the {label}")
    display = _early_bound(display, "IDisplayDimension")
    assert_dimension_measures(
        adapter,
        display,
        expected_mm=CAST_ROUND_R,
        label=label,
        entities=(arc,),
        entity_types=("EDGE",),
    )
    places = DRAWING_REFERENCE_PRECISION[label]
    display.SetPrecision3(DRAWING_REFERENCE_PRECISION[label], -1, -1, -1)
    if int(display.GetPrimaryPrecision2()) != places:
        raise RuntimeError(f"{label}: {places} decimal places did not persist")
    annotation = _early_bound(display.GetAnnotation(), "IAnnotation")
    set_dimension_callouts(
        adapter, [annotation], {dimension_name(adapter, annotation): ROUND_CALLOUT}
    )
    return annotation


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open magnifying-wheel source", await adapter.open_model(str(SOURCE)))
    read_required_properties(
        adapter.currentModel,
        (
            "Number",
            "Revision",
            "Title",
            "Material Specification",
            "Finish",
            "Quantity",
            "Manufacturing Notes",
            "Isometric View Note",
        ),
        required=(
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
            "Manufacturing Notes",
            "Isometric View Note",
        ),
    )
    drawing_model, _sheet = new_project_drawing(
        adapter, property_view=PART_STEM, scale=SHEET_SCALE, layout=SPEC.layout
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Magnifying Wheel Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "magnifying wheel; cast-iron spider; six spokes",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=(1, 1))
    section = create_section_view(
        adapter,
        front,
        line_start=(FRONT_CENTER[0], FRONT_CENTER[1] - _RIM_R - SECTION_LINE_OVERRUN),
        line_end=(FRONT_CENTER[0], FRONT_CENTER[1] + _RIM_R + SECTION_LINE_OVERRUN),
        view_xy=SECTION_CENTER,
        section_label="A",
        scale=(1, 1),
        label="wheel section A-A",
    )
    _orient_section(adapter, section)
    position_section_caption(adapter, section, SECTION_CAPTION_XY, label="wheel")
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=(1, 1))
    # Policy rule 7: a section shows no hidden lines, and the face view needs
    # none once the section carries the hub.
    for view in (front, section, iso):
        set_hidden_lines_removed(adapter, view)

    annotations = [
        *curate_view_dimensions(
            adapter,
            front,
            keep=FRONT_KEEP,
            view_label="front",
            dimensions_by_feature=DRAWING_DIMENSIONS,
        ),
        *curate_view_dimensions(
            adapter,
            section,
            keep=SECTION_KEEP,
            view_label="section",
            dimensions_by_feature=DRAWING_DIMENSIONS,
        ),
    ]
    # Decimal places (and so the general-tolerance row each dimension claims)
    # are authored on the part; the sheet only proves the import kept them.
    assert_imported_precision(adapter, annotations, DRAWING_PRECISION_BY_NAME)
    set_dimension_callouts(adapter, annotations, DIMENSION_CALLOUTS)
    set_dimension_callouts(adapter, annotations, CALLOUTS_ABOVE, location="above")
    _set_arrows_inside(adapter, annotations)
    axis, tie1, bore_landing = model_points_in_view(
        adapter,
        front,
        (
            (0.0, 0.0, 0.0),
            (_TIE1[0] / 1000.0, _TIE1[1] / 1000.0, 0.0),
            tuple(value / 1000.0 for value in _BORE_FINISH_POINT),
        ),
        label="wheel hole centres",
        names=("bore", "tie 1", "bore finish landing"),
    )
    _near_side_diameters(adapter, annotations, axis=axis)
    _trim_centre_marks(adapter, front, {"bore": axis, "tie 1": tie1})

    # Policy rule 5: the bore is a running fit (the general machined grade),
    # the spigot a static locating press seat; both controls are authored on
    # the part and read back here.  The boss step is the drum's register face
    # and takes no symbol.
    bore_finish = add_surface_finish(
        adapter,
        front,
        edge_entity=visible_circle_edge(adapter, front, BORE_DIA),
        symbol_xy=BORE_FINISH_SYMBOL,
        control=surface_finish_by_key(SURFACE_FINISHES, "mg_wheel_bore"),
        label="wheel bore finish",
        leader_attach_xy=bore_landing,
        char_height=FINISH_CHAR_HEIGHT,
    )
    _assert_face_leaders_clear(adapter, front, annotations, bore_finish, axis=axis)

    # The rim's axial width across the section, its text left of the rim's
    # back face on its own row (above). The two OD corner circles are
    # selected as native entities: a coordinate hit-test at the corner where
    # each edge-on circle ends on the OD silhouette found no edge on farm run
    # 4 (85a5d462d).  One sweep serves them and the spigot's cut line.
    section_edges = scan_view_edges(section, label="wheel section edges")
    rim_corners = tuple(
        section_edges.circle_at(
            (0.0, 0.0, z),
            RIM_OUTER_DIA / 2.0,
            axis=_RIM_AXIS,
            label=f"rim OD corner at z={z:+g}",
        ).edge
        for z in (RIM_AXIAL / 2.0, -RIM_AXIAL / 2.0)
    )
    rim_back, rim_front, spigot_landing = model_points_in_view(
        adapter,
        section,
        (
            (0.0, RIM_OUTER_DIA / 2000.0, RIM_AXIAL / 2000.0),
            (0.0, RIM_OUTER_DIA / 2000.0, -RIM_AXIAL / 2000.0),
            tuple(value / 1000.0 for value in _SPIGOT_FINISH_POINT),
        ),
        label="wheel section picks",
        names=("rim back corner", "rim front corner", "spigot finish landing"),
    )
    rim_width = add_edge_dimension(
        adapter,
        section,
        p0=rim_back,
        p1=rim_front,
        text_xy=_beside(
            _section_x(RIM_AXIAL / 2.0), -1, 4, _RIM_WIDTH_ROW + _ONE_LINE_UP
        ),
        label="rim axial width",
        orientation="horizontal",
        entities=rim_corners,
    )
    assert_dimension_measures(
        adapter,
        rim_width,
        expected_mm=RIM_AXIAL,
        label="rim axial width",
        entities=rim_corners,
    )
    add_surface_finish(
        adapter,
        section,
        edge_entity=section_edges.exact_line_through(
            _SPIGOT_FINISH_POINT, label="spigot upper cut line"
        ).edge,
        symbol_xy=(
            spigot_landing[0] + _SPIGOT_FINISH_OFFSET[0],
            spigot_landing[1] + _SPIGOT_FINISH_OFFSET[1],
        ),
        control=surface_finish_by_key(SURFACE_FINISHES, "mg_wheel_spigot"),
        label="wheel spigot finish",
        leader_attach_xy=spigot_landing,
        char_height=FINISH_CHAR_HEIGHT,
    )
    round_radius = _add_round_radius(adapter, section, section_edges)
    rebuild_drawing(adapter, label="wheel dimension layout")
    _assert_text_off_iso(
        adapter,
        [
            *annotations,
            _early_bound(rim_width, "IDisplayDimension").GetAnnotation(),
            round_radius,
        ],
        iso,
    )

    add_property_linked_note(adapter, "Manufacturing Notes", *NOTES_XY)
    add_property_linked_note(
        adapter, "Isometric View Note", ISO_CENTER[0] - 0.030, 0.085
    )

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Magnifying Wheel Manufacturing Drawing",
        scale=SHEET_SCALE,
        layout=SPEC.layout,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[PART_STEM])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
