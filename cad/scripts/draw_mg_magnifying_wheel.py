r"""Create the curated machinist drawing for the magnifying wheel.

A Ø100 cast-iron spider: six tapered spokes, a grooved rim, a Ø28.5 boss with
the Ø14.0 drum spigot, a reamed axle bore and two wire-tie holes.  The wheel
axis is local +Z, so the FRONT view is the face (rim, spokes, fillets, bore,
ties) and SECTION A-A, cut on the axis through the model's Right plane, is
the hub profile, the groove and the axial widths in solid lines
(drawing-guidelines.md rule 9 (show internal shape in solid lines)).  Every size rides the part's marked dimensions; only the rim's axial
width and the rim-bore round's R (on its cut arc) are added on the sheet.
The bore's and the spigot's mates print on
their own diameter callouts (drawing-guidelines.md rule 7 (notes: few, flagged, never a method)), and the running bore carries the
part-owned roughness its fit needs (drawing-guidelines.md rule 6 (roughness symbols only where a surface runs, slides or locates)).

Run with SolidWorks open::

    uv run python cad\scripts\draw_mg_magnifying_wheel.py mg-magnifying-wheel
"""

from __future__ import annotations

import argparse
import math
import sys
from typing import Any

import _config
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
from _drawing_dimensions import (
    assert_imported_precision,
    offset_dimension_text,
    set_dimension_callouts,
    set_reference_dimensions,
)
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
from _machinist_review_mode import MachinistReviewMode
from _section_axis import position_section_caption
from _session import run_build
from _surface_finish import surface_finish_by_key
from _mg_wheel_rim_geometry import RIM_AXIAL, RIM_INNER_DIA, RIM_OUTER_DIA
from mg_magnifying_wheel_geom import (
    DRUM_PRESS,
    HUB_BACK_Z,
    HUB_FRONT_Z,
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
    REFERENCE_DIMENSIONS,
    RIM_FILLET_R,
    ROUND_TEXT_SUFFIX,
    SPIGOT_DIA,
    SURFACE_FINISHES,
    TIE1_CLOCK_DEG,
    TIE1_R,
    TIE2_CLOCK_DEG,
    TIE_HOLE_DIA,
    clock_to_local_deg,
    fillet,
)
from mg_wheel_group import HUB_RUNNING
from solidworks_mcp.adapters.com_variant import double_array
from solidworks_mcp.adapters.solidworks.drawing import dimension_name, place_view

# Cached machinist review leaf: a FIX or ERROR verdict fails the build.
MACHINIST_REVIEW = MachinistReviewMode.ENFORCE


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
# The isometric stands right of the section's Ø14.0 text, ISO_CLEAR off it.
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
# Every text and finish symbol stands outside the Ø100 silhouette
# (drawing-guidelines.md rule 14 (keep text off the part)), and no leader or shoulder may cross another's line.  Farm run 7
# (396077c3e) failed on exactly that: the native Ø100 and Ø88 lines ran rim
# to rim through the centre, so the shoulders under them crossed them.  The
# three diameters take one arrow on their near rim (set_near_side_diameter),
# so only the bore's leader, its finish's and the spoke root's offset-text
# leader cross the face.  The A-A cutting line stands on the axis
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
# wheel and left of A-A's hub Ø.
_DIA_SHOULDER_LEFT = 10.0
_RIM_INNER_SHOULDER = _polar((0.0, 0.0), 19.0, RIM_OUTER_DIA / 2.0 + 14.0)
# The mates the matched fits and the tight bands name (drawing-guidelines.md
# rule 4 (tighten only for function, and name the mate)), by drawing number.
AXLE_NUMBER = str(_config.parts("mg-wheel-axle")["number"])
DRUM_NUMBER = str(_config.parts("mg-wheel-drum")["number"])
PEN_WIRE_NUMBER = str(_config.parts("sh-vn-music-wire")["number"])
BORE_CALLOUT = (
    f"REAM THRU\n{HUB_RUNNING[0]:.3f}-{HUB_RUNNING[1]:.3f} DIAMETRAL\n"
    f"CLEARANCE ON\nMG-WHEEL-AXLE {AXLE_NUMBER}"
)
# The bore's block: its widest line sets its width (run 7's 2.45 mm a
# character); the block stands left of the wheel on a shoulder 30 mm above
# the axis, its right end 7 mm off the OD.
_BORE_SHOULDER_Y = 30.0
_BORE_BLOCK_HALF = max(len(line) for line in BORE_CALLOUT.splitlines()) * 2.45 / 2.0
_BORE_BLOCK_X = (
    -math.sqrt((RIM_OUTER_DIA / 2.0) ** 2 - _BORE_SHOULDER_Y**2)
    - 7.0
    - _BORE_BLOCK_HALF
)
FRONT_KEEP = {
    # Near-side, one arrow each: Ø100 up-left on the OD, over the bore's
    # block, its need in two lines under it; Ø88 right through the 0-60
    # window at 19 deg, clear of the A-A line; the bore up-left through the
    # 120-180 window to its block's shoulder (stacked Ø plus four callout
    # lines).
    "RimOuterDiaDim": _over(_polar((0.0, 0.0), 125.0, RIM_OUTER_DIA / 2.0 + 40.0), 3),
    "RimInnerDiaDim": _over(
        (_RIM_INNER_SHOULDER[0] + _DIA_SHOULDER_LEFT, _RIM_INNER_SHOULDER[1]), 1
    ),
    "BoreDiaDim": _over((_BORE_BLOCK_X, _BORE_SHOULDER_Y), 6),
    # The R3 (concave, inside the 0-60 window) leadered out along the window
    # to a shoulder past the OD at 30 deg; the R4 (convex, from outside the
    # rim) on its centre's -3 deg ray, past the OD and above the tip width's
    # extension lines.
    "HubFilletR": _over(
        (_HUB_FILLET_SHOULDER[0] + _RADIUS_SHOULDER_LEFT, _HUB_FILLET_SHOULDER[1]), 2
    ),
    "RimFilletR": _over(_polar(_RIM_FILLET_CENTRE, -3.0, 26.0), 2),
    # Each spoke width's line beside its own end: the root's inside the hub
    # fillets' feet, its text off on a leader (SPOKE_ROOT_TEXT_XY); the
    # tip's outside the rim, its text below the line beside the OD, so
    # neither's extension lines reach the other's line.
    "SpokeRootWidth": _face(SPOKE_X0 + 4.5, 0.0),
    "SpokeTipWidth": _over((RIM_OUTER_DIA / 2.0 + 3.0, -22.0), 2),
    # TIE 1's radius between its own extension lines, which run left from the
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
# The spoke root's text hangs off its dimension line on an OffsetText leader
# (draw_sm_gooseneck_spring_screw): the leader runs down-right across the
# 300-360 window and the rim to the LEFT end of the callout line, one text
# line under the point the value centres on (the pivot screw's readback).
# That end stands under the tip width's line, 14 mm below its block's foot:
# the block sits outside the OD, right of TIE 1's block and left of A-A.
_ROOT_CALLOUT = "6X ROOT"
SPOKE_ROOT_TEXT_XY = _face(
    RIM_OUTER_DIA / 2.0 + 3.0 + len(_ROOT_CALLOUT) * 2.45 / 2.0,
    -36.0 + _TEXT_LINE * 1000.0,
)
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
# Run 8 printed "Ø25.00 +0.1/-0.1" 30.1 mm wide: the widest hub Ø text.
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
# rim's 8.0 (added below): both lines run from the part leftward to their
# text, above the hub's extension lines and under the rim bore.
_SPOKE_ROW = SECTION_CENTER[1] + HUB_DIA / 2000.0 + 0.0055
_RIM_WIDTH_ROW = _SPOKE_ROW + 0.010
# The hub's three axial sizes below the rim, one row each, all from the
# spigot's faced front end (drawing-guidelines.md rule 11 (turned parts read like the lathe)) and all texts right of it except
# the overall's; each text OUTSIDE its span so no extension line runs
# through a text (run 7: four extension-through-own-text findings).
# Nearest the part the spigot length ("9.00 +0.10/0"), whose band keeps the
# drum from standing proud (DRUM_RECESS); then the web's centre plane
# ("12.5"), which the rim and its groove share, its extension line rising
# from the axis left of the spigot step's, so the row above stops short of
# it; last the overall ("19.60 ±0.10"), which holds the axle's nut stack,
# left of the back face above the A-A caption.  Each band's need, and the
# plane the 12.5 locates, stands over its value (CALLOUTS_ABOVE), its text
# centred clear of the face it leaves.  The two right-hand sizes keep their
# arrows inside their spans, so no tail reaches a neighbouring extension
# line (run 11).
#
# _HUB_ROWS are the dimension lines.  A text block centres on its point, so
# a callout over the value lifts the point half a line more than
# _ONE_LINE_UP / _STACK_UP (run 14: each line printed 2.8 mm under its
# estimate).  The overall's row stays where run 14 printed it, over the
# caption; the plane's runs 5.4 mm above it; the spigot length's stands
# 11.9 mm over the plane's, so its block clears the plane's two-line block
# by the layout audit's text separation (run 17: 2.73 mm apart at a 10.4 mm
# step, under the 3.57 mm it needs).
_ABOVE_UP = _TEXT_LINE / 2.0
_HUB_ROWS = tuple(
    SECTION_CENTER[1] - _RIM_R - drop for drop in (0.0050, 0.0184, 0.0238)
)
SPIGOT_LENGTH_CALLOUT = "DRUM NOT PROUD"
WEB_CENTER_CALLOUT = "WEB & RIM CENTER"
HUB_LENGTH_CALLOUT = f"LOCKNUT ON FULL THREAD OF\nMG-WHEEL-AXLE {AXLE_NUMBER}"
# The groove's two bands seat the pen wire (mg_magnifying_wheel_spec
# GROOVE_WIDTH_MIN, GROOVE_DEPTH_MIN): each callout names it.
GROOVE_CALLOUT = f"PEN-WIRE SEAT\n{PEN_WIRE_NUMBER}"
# Capitals print wider than _TEXT_CHAR (run 13: "2X RIM BORE EDGES" measured
# 2.6 mm a character), so a callout's span is estimated two characters wide.
_CALLOUT_MARGIN_CHARS = 2
ARROWS_INSIDE = ("SpigotLength", "HubFrontZ")
_DIM_ARROWS_INSIDE = 0  # swDimensionArrowsSide_e.swDimArrowsInside
SECTION_KEEP = {
    "HubDia": (_HUB_DIA_X, SECTION_CENTER[1]),
    "GrooveBottomDia": (_GROOVE_DIA_X, SECTION_CENTER[1] + 0.035),
    # Right of the view only the spigot's Ø, its line 7.2 mm past the spigot
    # end and its text under the spigot, so the matched-fit callout lines
    # stack down toward the spigot length's row: ISO_CLEAR off the
    # isometric, proven at build (_assert_text_off_iso), so no line is wider
    # than "INTERFERENCE IN".  Its point stands half a line over run 14's, so
    # the fourth callout line ends a line and a half over run 14's foot.
    "SpigotDia": (
        _section_x(HUB_FRONT_Z) + 0.0072,
        SECTION_CENTER[1] - SPIGOT_DIA / 2000.0 - 0.012 + _TEXT_LINE / 2.0,
    ),
    "SpokeAxial": _beside(_section_x(HUB_BACK_Z), -1, 3, _SPOKE_ROW + _ONE_LINE_UP),
    "SpigotLength": _beside(
        _section_x(HUB_FRONT_Z),
        1,
        len(SPIGOT_LENGTH_CALLOUT) + _CALLOUT_MARGIN_CHARS,
        _HUB_ROWS[0] + _STACK_UP + _ABOVE_UP,
    ),
    "HubFrontZ": _beside(
        _section_x(HUB_FRONT_Z),
        1,
        len(WEB_CENTER_CALLOUT) + _CALLOUT_MARGIN_CHARS,
        _HUB_ROWS[1] + _ONE_LINE_UP + _ABOVE_UP,
    ),
    "HubLength": _beside(
        _section_x(HUB_BACK_Z),
        -1,
        max(len(line) for line in HUB_LENGTH_CALLOUT.splitlines())
        + _CALLOUT_MARGIN_CHARS,
        _HUB_ROWS[2] + _STACK_UP + _ABOVE_UP,
    ),
    # The groove's R up right, its leader down-left onto the groove at run
    # 13's 35 deg, so the stub it draws past the arc leaves the rim's back
    # face above the rim width's extension line; its shoulder 7.3 mm over
    # the top of the rim-bore round's R block (ROUND_TEXT_XY), moved up and
    # right along that bearing.  Run 17's 5.8 mm left its stacked +0.1 2.93
    # mm over the "R0.8 MAX" (text separation needs 3.57 mm): 1.5 mm more,
    # 2.1 mm right on the bearing.
    "GrooveR": (SECTION_CENTER[0] + 0.0335, SECTION_CENTER[1] + 0.0695),
}
# The rim-bore round's R is a sheet radial on its cut arc: A-A cannot import
# a fillet radius whose arc IS the cut (round-12 farm leaves: neither the
# targeted import nor DragModelDimension landed CastRoundR there).  It takes
# the arc at the rim's front (sheet-right, model -Z) top corner, the circle's
# centre one R in from the bore and the side face.  A cut-face arc lies in
# the cut plane, so its axis is the cut's normal (model X); the round's
# tangent circles beyond the cut keep the wheel's Z (run 13's scan read the
# r = 44.8 one so), and the axis keeps the pick off them.
# Its callout stands right, between the spigot's Ø block and the groove's R:
# the value on its point and the two callout lines under it, the shoulder
# under the last (run 13 readback: 5.6 mm a line, starting 23.8 mm left of
# the point).  The shoulder runs 1.8 mm under the arc's centre, so the
# radial leader lands on the arc 20 deg below the side face's tangent and
# crosses the rim's front face 0.7 mm above the top of the rim width's
# extension line (run 13's farm audit: landing 61 deg below, it crossed
# that line).  The Ø97.6 holds the left.
_ROUND_ARC_CENTER = (
    0.0,
    RIM_INNER_DIA / 2.0 + CAST_ROUND_R,
    -(RIM_AXIAL / 2.0 - CAST_ROUND_R),
)
_CUT_NORMAL = (1.0, 0.0, 0.0)
ROUND_TEXT_XY = (SECTION_CENTER[0] + 0.0292, SECTION_CENTER[1] + 0.0542)
# The R's single limit holds TIE 2's 2.0 wall to the rim's side faces
# (mg_magnifying_wheel_spec.TIE2_FACE_WALL), so the callout says so.
ROUND_CALLOUT = "2X RIM BORE EDGES\nHOLDS TIE 2 WALL"


# The two fits print on their own diameters (drawing-guidelines.md rule 7 (notes: few, flagged, never a method)) as matched fits
# (drawing-guidelines.md rule 4 (tighten only for function, and name the mate)): each Ø is a reference nominal (REFERENCE_DIMENSIONS), and
# its callout names the mate and states the diametral fit the finished pair
# must make (mg_wheel_group.HUB_RUNNING, mg_magnifying_wheel_geom.DRUM_PRESS):
# the bore is reamed to run on the finished axle, and the spigot turned to
# press into the drum's finished H7 bore.
DIMENSION_CALLOUTS = {
    "BoreDiaDim": BORE_CALLOUT,
    "SpigotDia": (
        f"{DRUM_PRESS[0]:.3f}-{DRUM_PRESS[1]:.3f}\nDIAMETRAL\n"
        f"INTERFERENCE IN\nMG-WHEEL-DRUM\n{DRUM_NUMBER}"
    ),
    "GrooveBottomDia": GROOVE_CALLOUT,
    # The OD's .XX floor keeps the groove deeper than the pen wire
    # (mg_magnifying_wheel_spec.GROOVE_DEPTH_MIN).
    "RimOuterDiaDim": "HOLDS PEN WIRE\nIN GROOVE",
    "SpokeRootWidth": _ROOT_CALLOUT,
    "SpokeTipWidth": "6X TIP",
    "HubFilletR": "12X",
    "RimFilletR": "12X",
    "Tie1HoleDia": "TIE 1",
    "Tie2HoleDia": "TIE 2",
}
# The tie holes' operation stands over their Ø, keeping each block as narrow
# as its stacked Ø; each axial band's need, the plane the 12.5 locates and
# the groove R's seat stand over their values.
CALLOUTS_ABOVE = {
    "Tie1HoleDia": "DRILL THRU",
    "Tie2HoleDia": "DRILL THRU",
    "SpigotLength": SPIGOT_LENGTH_CALLOUT,
    "HubFrontZ": WEB_CENTER_CALLOUT,
    "HubLength": HUB_LENGTH_CALLOUT,
    "GrooveR": GROOVE_CALLOUT,
}
# Three note lines, top-left anchored, under the two tie blocks and left of
# the title block.
NOTES_XY = (0.020, 0.062)

# The rim's axial width spans its two side faces where A-A cuts them: at the
# rim's top each is a straight cut-face line at z = +/-RIM_AXIAL/2, running
# from the rim-bore round's tangent (r = RIM_INNER_DIA/2 + CAST_ROUND_R) to
# the OD, picked through its midpoint as a native entity.  Farm run 13
# (c09670314) found no OD corner circle (r = 50, z = +/-4) in the section's
# scan: edge-on, each lies under the cut face's boundary and the round's
# tangent circle, which A-A draws instead.  The OD is no single line to
# measure either: the groove splits it into two lands.
_RIM_SIDE_Y = (RIM_INNER_DIA / 2.0 + CAST_ROUND_R + RIM_OUTER_DIA / 2.0) / 2.0
_RIM_SIDE_POINTS = tuple(
    (0.0, _RIM_SIDE_Y, z) for z in (RIM_AXIAL / 2.0, -RIM_AXIAL / 2.0)
)
# A failed section pick names every scanned edge passing this near its point.
_PICK_INVENTORY_MM = 6.0
# The bore's finish symbol stands outside the OD up the 0-60 window, 45 deg,
# between the R3's shoulder and the Ø88's text; its leader lands on the bore
# on that bearing, right of the A-A line.
_BORE_FINISH_BEARING = 45.0
BORE_FINISH_SYMBOL = _face(
    *_polar((0.0, 0.0), _BORE_FINISH_BEARING, RIM_OUTER_DIA / 2.0 + 16.0)
)
_BORE_FINISH_POINT = (*_polar((0.0, 0.0), _BORE_FINISH_BEARING, BORE_DIA / 2.0), 0.0)
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
    line cross none of each other (drawing-guidelines.md rule 14 (keep text off the part)), each landing on its own
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


def _mm(values: Any) -> str:
    return "(" + ", ".join(f"{value:.3f}" for value in values) + ")"


def _edge_inventory(edges: ViewEdges, point_mm: tuple[float, float, float]) -> str:
    """Every scanned line and circle passing within _PICK_INVENTORY_MM of
    ``point_mm`` (model mm; a circle by its full curve), so a missed section
    pick names what the scan does hold there."""
    rows = []
    for item in edges.edges:
        if item.line is not None:
            start, end = item.line
            vector = [b - a for a, b in zip(start, end)]
            length_sq = sum(value * value for value in vector)
            t = 0.0
            if length_sq > 0.0:
                along = sum((p - a) * v for p, a, v in zip(point_mm, start, vector))
                t = min(1.0, max(0.0, along / length_sq))
            reach = math.dist(point_mm, [a + t * v for a, v in zip(start, vector)])
            text = f"line {_mm(start)}-{_mm(end)}"
        elif item.circle is not None:
            cx, cy, cz, nx, ny, nz, radius = item.circle
            offset = [p - c for p, c in zip(point_mm, (cx, cy, cz))]
            height = sum(o * n for o, n in zip(offset, (nx, ny, nz)))
            in_plane = math.sqrt(max(sum(o * o for o in offset) - height**2, 0.0))
            reach = math.hypot(height, in_plane - radius)
            text = f"circle c={_mm((cx, cy, cz))} n={_mm((nx, ny, nz))} r={radius:.3f}"
        else:
            continue
        if reach <= _PICK_INVENTORY_MM:
            rows.append(f"{text} {reach:.2f} off")
    return (
        f"{len(rows)} of {len(edges.edges)} scanned edges within "
        f"{_PICK_INVENTORY_MM:g} mm of {_mm(point_mm)}: {'; '.join(rows) or 'none'}"
    )


def _line_through(
    edges: ViewEdges, point_mm: tuple[float, float, float], *, label: str
) -> Any:
    """The section's cut-face line through ``point_mm``, its edge inventory
    on a miss."""
    try:
        return edges.exact_line_through(point_mm, label=label).edge
    except RuntimeError as error:
        raise RuntimeError(f"{error}; {_edge_inventory(edges, point_mm)}") from error


def _pass_through_places(display: Any, label: str) -> None:
    """Give a sheet-added dimension the places the spec owns for it
    (DRAWING_REFERENCE_PRECISION), so it prints the value the spec's walls
    are proved against."""
    display.SetPrecision3(DRAWING_REFERENCE_PRECISION[label], -1, -1, -1)
    places = DRAWING_REFERENCE_PRECISION[label]
    if int(display.GetPrimaryPrecision2()) != places:
        raise RuntimeError(f"{label}: {places} decimal places did not persist")


def _add_round_radius(adapter: Any, section: Any, edges: ViewEdges) -> Any:
    """Dimension the rim-bore round on its A-A cut arc (the T rail root radius
    pattern of draw_fr_top_frame) and return its annotation.

    The arc is picked as a native entity from the section's edge scan, so a
    moved round fails loud in ``circle_at``; the radial must attach to that
    arc alone and measure the spec's R (``assert_dimension_measures``).  It
    prints a single limit, R0.8 MAX (one place and the spec's suffix), the
    largest R ``TIE2_FACE_WALL`` is proved against; a sharp edge falls under
    the title block's edge break.
    """
    label = "rim bore round"
    try:
        arc = edges.circle_at(
            _ROUND_ARC_CENTER, CAST_ROUND_R, axis=_CUT_NORMAL, label=label
        ).edge
    except RuntimeError as error:
        inventory = _edge_inventory(edges, _ROUND_ARC_CENTER)
        raise RuntimeError(f"{error}; {inventory}") from error
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
    _pass_through_places(display, label)
    display.SetText(2, ROUND_TEXT_SUFFIX)  # swDimensionTextSuffix
    suffix = str(display.GetText(2) or "")
    if suffix != ROUND_TEXT_SUFFIX:
        raise RuntimeError(f"{label}: suffix {suffix!r} did not persist")
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
    # drawing-guidelines.md rule 9 (show internal shape in solid lines): a section shows no hidden lines, and the face view needs
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
    # The matched fits' Ø are reference nominals: "(Ø14.00)", "(Ø4.80)".
    set_reference_dimensions(adapter, annotations, REFERENCE_DIMENSIONS)
    set_dimension_callouts(adapter, annotations, CALLOUTS_ABOVE, location="above")
    offset_dimension_text(adapter, annotations, {"SpokeRootWidth": SPOKE_ROOT_TEXT_XY})
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

    # drawing-guidelines.md rule 6 (roughness symbols only where a surface runs, slides or locates): the bore is a running fit (the general machined grade),
    # authored on the part and read back here.  The spigot is pressed into
    # the drum and the boss step is the drum's register face: neither takes
    # a symbol.
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

    # The rim's axial width across the section between its side faces' cut
    # lines (_RIM_SIDE_POINTS), its text left of the rim's back face on its
    # own row (above).  Each line is selected as a native entity: a
    # coordinate hit-test found no edge on farm run 4 (85a5d462d).  One sweep
    # serves them and the rim-bore round's arc.
    section_edges = scan_view_edges(section, label="wheel section edges")
    rim_sides = tuple(
        _line_through(section_edges, point, label=f"rim side cut line z={point[2]:+g}")
        for point in _RIM_SIDE_POINTS
    )
    rim_back, rim_front = model_points_in_view(
        adapter,
        section,
        tuple(tuple(value / 1000.0 for value in point) for point in _RIM_SIDE_POINTS),
        label="wheel section picks",
        names=("rim back side", "rim front side"),
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
        entities=rim_sides,
    )
    assert_dimension_measures(
        adapter,
        rim_width,
        expected_mm=RIM_AXIAL,
        label="rim axial width",
        entities=rim_sides,
    )
    _pass_through_places(
        _early_bound(rim_width, "IDisplayDimension"), "rim axial width"
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
