r"""Create the drawing for the oblique trammel's base bar (MHA-CH-06-TL-20).

One part, one configuration, two off (the title block's quantity); the
second bar is the same part turned over. Its plan (the *Front view, looking
down on the top face) carries the bar's length and milled width (owner
ruling #2083), the rail holes' baseline stations and the
row's lateral station from the -Y edge under one native tap callout, the end
brackets' eight counterbored holes (stations from the end face, four rows
from the -Y edge, one native callout naming the far-side counterbores and the
TL-28 mate), and both slots' stations, rises, width and centre-to-centre run
(slot centre marks); the end view, projected right of the plan on its
centreline, carries the faced thickness and both faced seats' Ra 125 µin
under their one reason; the shaded isometric rides bottom left under the
plan's stack, left of the title block. The sheet prints decimal inch
(#290); the model keeps its millimetre nominals. The rail holes' and the
brackets' stations belong to metric vendor lines (HGR15R, KP08) and print
exact millimetres, labelled mm (owner ruling 4, 2026-11-01).

Run with SolidWorks open::

    uv run python cad\scripts\draw_ch_rocker_arm_tl_oblique_base_bar.py ch-rocker-arm-tl-oblique-base-bar
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

from solidworks_mcp.adapters.solidworks.drawing import (
    add_note,
    auto_center_marks,
    dimension_name,
    place_view,
    view_name,
)

from _check import check
from _com import _early_bound
from _drawing_common import (
    DrawingOutputs,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    stamp_drawing_summary,
)
from _drawing_dimensions import assert_imported_precision, set_dimension_callouts
from _drawing_edges import visible_view_entities
from _drawing_finish import add_surface_finish
from _drawing_hidden_sketches import curate_view_dimensions
from _drawing_hole_callout import add_native_hole_callout, set_hole_callout_precision
from _drawing_notes import add_property_linked_note
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_projection import model_point_in_view
from _drawing_view_display import set_hidden_lines_removed
from _hole_callout_thread_class import omit_title_block_thread_class
from _machinist_review_mode import MachinistReviewMode
from _paths import CAD_ROOT
from _session import run_build
import _telemetry
import ch_rocker_arm_tl_oblique_base_bar_spec as part_spec
from _feature_requirements import part_metadata, requirement
from _gtol_cylinder import CylinderFace
from _gtol_planar import PlanarFace
from _surface_finish import SEAT_UM, surface_finish_by_key
from _printed_limits import limits
from _part_properties import part_drawing_unit
from _printed_tolerance import drilled_oversize_mm
from _drawing_metric_vendor import assert_imported_metric_dimensions
from ch_rocker_arm_tl_oblique_callouts import set_callout_lengths_to_three_places
from ch_rocker_arm_tl_oblique_base_bar_spec import (
    BAR_LENGTH,
    BAR_THICK,
    BAR_WIDTH,
    BRACKET_CALLOUT_PRECISION,
    BRACKET_CALLOUT_PROCESS,
    BRACKET_HOLE_DIA,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    FAR_SLOT_RISE,
    FAR_SLOT_X,
    FAR_SLOT_Y,
    HIGH_SIDE_Y,
    LOW_SIDE_Y,
    METRIC_DIMENSIONS,
    NEAR_SLOT_RISE,
    NEAR_SLOT_X,
    RAIL_HOLE_X,
    RAIL_MATE_CALLOUT,
    RAIL_ROW_CALLOUT,
    SEAT_FINISH_REASON,
    SLOT_RUN,
    SURFACE_FINISHES,
    TAP_DRILL,
    TAP_SPEC,
)
import ch_rocker_arm_tl_vn_oblique_leadscrew_spec as leadscrew

# Cached machinist review leaf: a FIX or ERROR verdict fails the build.
MACHINIST_REVIEW = MachinistReviewMode.ENFORCE

SPEC = DRAWINGS_BY_NAME["ch_rocker_arm_tl_oblique_base_bar"]
PART_STEM = SPEC.artifact_stem
SOURCE = CAD_ROOT / "out" / "sldprt" / f"{PART_STEM}.SLDPRT"
OUTPUTS = DrawingOutputs(
    slddrw=SPEC.outputs["slddrw"], pdf=SPEC.outputs["pdf"], png=SPEC.outputs["png"]
)
SLDDRW, PDF, PNG = OUTPUTS.slddrw, OUTPUTS.pdf, OUTPUTS.png

# A 17.32 x 5.50 x .47 bar: 1:2 puts the 220-wide plan on the B sheet, its end
# view projected right of it on the same centreline (third angle). The
# vertical budget: the rail-hole stack tops out at about 265 under the 267
# border. The plan sits right of centre so the three side lanes (the row's
# three-line callout the widest) and the width's text clear the left
# border (about 12); r3 moved plan and end view 8 right, r4 another 3.5 (the
# row's block measured wider than estimated). C4: the bracket holes' callout
# takes the bottom-right corner under the end view, so the 1:5 iso and its
# note move to the free bottom-left corner, under the plan's six-lane stack
# and left of the title block (x from about 216). The 2026-10-17 widening
# (1/2 x 4 to 1/2 x 6, ruling A′) grew the plan and the end view 25.4 taller
# and the iso about 8: the plan drops 11.0, as far as the rail-hole stack
# allows, so the iso (about 66 x 62) and its note still fit under the stack;
# its four bracket rows (two before A′) take three lanes right of the plan,
# so the end view moves 21.5 right to clear the outermost row's text, and
# 5 more for the far slot's rise outside them (c3-r6). c4-r8 read the
# 400.00 block's top line touching the border: the plan and end view drop
# 3, the iso staying put, its top 7 under the length's text. The 2026-10-30
# narrowing to 5.50 shortens the plan and end view 12.7 at the +Y side.
# #290 moved the plan and end view 3 right for the stock width's "(5-1/2 in)"
# reference; #2083 mills the width and prints a bare 5.50 there instead.
SHEET_SCALE = (1.0, 2.0)
VIEW_SCALE = (1, 2)
ISO_SCALE = (1, 5)
_S = SHEET_SCALE[0] / SHEET_SCALE[1]
FRONT_CENTER = (0.1865, 0.1695)
END_CENTER = (0.366, FRONT_CENTER[1])
ISO_CENTER = (0.090, 0.056)
ISO_NOTE_XY = (0.060, 0.022)
# The r3 sheet measured 0.033 x 0.027 for the 101.6 bar; the widening adds
# 0.816 x 50.8 / 5 to the iso's height.
ISO_HALF = (0.033, 0.031)


def _sheet_x(center: tuple[float, float], model_x_mm: float) -> float:
    """Sheet X of a model-X point in a plan view (bbox-centred)."""
    return center[0] + (model_x_mm - BAR_LENGTH / 2.0) * _S / 1000.0


# The view centres on the bar's bounding box; the rail axis (model y 0) sits
# off it since the 2026-10-17 widening.
_Y_MID = (LOW_SIDE_Y + HIGH_SIDE_Y) / 2.0  # -12.7


def _sheet_y(center: tuple[float, float], model_y_mm: float) -> float:
    """Sheet Y of a model-Y point in a plan view (bbox-centred)."""
    return center[1] + (model_y_mm - _Y_MID) * _S / 1000.0


_HALF_W_SHEET = BAR_WIDTH * _S / 2000.0  # half the plan's (and end view's) height
_HALF_L_SHEET = BAR_LENGTH * _S / 2000.0
_TOP = FRONT_CENTER[1] + _HALF_W_SHEET
_BOTTOM = FRONT_CENTER[1] - _HALF_W_SHEET
_LEFT = FRONT_CENTER[0] - _HALF_L_SHEET
_RIGHT = FRONT_CENTER[0] + _HALF_L_SHEET
TAP_R_SHEET = TAP_DRILL * _S / 2000.0
BRACKET_R_SHEET = BRACKET_HOLE_DIA * _S / 2000.0
# The leadscrew layout's bracket holes: a row of four at each KP08 station
# (near, far), innermost first.
BRACKET_HOLES = leadscrew.BASE_BAR_HOLES
BRACKET_NEAR_X = BRACKET_HOLES[0][0]
BRACKET_FAR_X = BRACKET_HOLES[-1][0]
# The four rows (ruling A′), innermost first, as the builder's.
BRACKET_ROW_Y = tuple(-lateral for lateral in leadscrew.BAR_SCREW_LATERALS)
BRACKET_OUTER_Y = BRACKET_ROW_Y[-1]
LANE = 0.008  # one side-dimension lane
# Stacked dimensions (the rail-hole baselines above the plan, the stations
# and length below it): first dimension line STACK_FIRST off the part, then
# STACK_LANE apart (ASME Y14.5's 6 mm spacing). The curation keep point is the
# text block's centre; SolidWorks hangs the dimension line about TEXT_DROP
# below a one-line block and TWO_LINE_DROP below a two-line one.
STACK_FIRST = 0.008
STACK_LANE = 0.006
TEXT_DROP = 0.0027
TWO_LINE_DROP = 0.0056


def _above_line(k: int) -> float:
    """Sheet Y of the k-th (from 0) dimension line above the plan."""
    return _TOP + STACK_FIRST + k * STACK_LANE


def _below_line(k: int) -> float:
    """Sheet Y of the k-th (from 0) dimension line below the plan."""
    return _BOTTOM - STACK_FIRST - k * STACK_LANE


# The plan: the rail-hole stations stack above it from the end face, nearest
# first (DRO absolutes), each in its own lane; the outermost (400.00 ±0.08 mm)
# carries the mate on a second line, the only lane no extension line crosses.
# The 40.00 span is shorter than its text, so its text sits outside it. The
# millimetre label (owner ruling 4) left it too wide for the gap between holes
# 1 and 2, so it stands left of the end face's extension line, where no other
# line runs (r1 printed it across that line).
#
# Below it, nearest first: the near slot's width (its extension lines then
# cross no other dimension), the near slot's station, the near bracket row's
# station, the far slot's, the far row's, the length. A span shorter than
# its text prints the text beside it, clear of both extension lines (r2
# struck "2X 13.50" and "20.9" with their own lines): the near station's
# right of the slot's centre line; the near row's (57.000 ±0.13 mm, wider
# than its span) right of its own extension line. The width's "2X 13.50 THRU"
# (r5: the slots' depth) sits right of the near row's extension line, which
# runs down through lane 0 too close to the slot for the text to fit
# between them (Y14.5 lets an extension line cross a dimension line).
#
# Left of it, shortest nearest: the near rise, the rail row's lateral station
# (88.90, from the -Y edge to the row's centreline, its function on two
# callout lines under it; r3), the width, whose text rides above the
# row's line so the row's upper extension line ends short of it. The row's
# three-line block sits above the near rise's upper extension line.
# Right of it: the bracket rows from the -Y edge (the outer row's 6.400
# below the bar, its span too short, its text right of its line on a
# shoulder; each taller row mid-span, one lane further out, its line far
# enough out that its outside arrow under the bar's edge clears the 6.400's
# text: c4-r2 struck the "8" and bunched the two lines), the far slot's run
# (2X; the far slot so the dimension lands off the part), its text below the
# 3 mm span (r2 struck "2X 6.00" with its arrows), then the far slot's rise
# from the -Y edge, the datum of every other location in the view (c3-r6,
# rule 10: its drop from the +Y edge was a second datum). The rise is the
# tallest, so it takes the outermost lane (the rows' upper extension lines
# would cross it nearer in), its text between the outermost row's upper
# extension line and the run. The bracket callout's leader leaves the far
# outer hole down and right, crossing only the length's extension line, to a
# block in the bottom-right corner.
_TEXT_GAP = 0.0025  # a text's clearance from the line it sits beside
# Half text widths (sheet m, measured on the r2 sheet's 3.5 mm text).
_SLOT_WIDTH_TEXT_HALF = 0.017  # "2X .53 THRU", 11 glyphs at r4's 2.6
_NEAR_SLOT_X_TEXT_HALF = 0.0045  # ".87"
_SLOT_RUN_TEXT_HALF = 0.008  # "2X .16"
_FAR_RISE_TEXT_HALF = 0.0055  # "4.90": the r6 sheet's "23.0" was 8.8 wide
# "FOR HGR15R RAIL", its widest line (15 glyphs): 38.8 wide on the r4 sheet.
_RAIL_ROW_TEXT_HALF = 0.0195
# "5.50", four glyphs at 2.6 (the #290 "(5-1/2 in)" over "STOCK" was 0.0104).
_BAR_WIDTH_TEXT_HALF = 0.0055
# The metric vendor stations at about 2.6 a glyph (owner ruling 4).
_RAIL_HOLE_1_TEXT_HALF = 0.0182  # "40.00 ±0.08 mm", 14 glyphs
_BRACKET_NEAR_X_TEXT_HALF = 0.0195  # "57.000 ±0.13 mm", 15 glyphs
_BRACKET_ROW_TEXT_HALF = 0.0070  # "2.425": "61.400" was 13.9 wide on the c4-r9 sheet
_BRACKET_OUTER_TEXT_BELOW = 0.004  # "6.400"'s centre under the bar's -Y edge
# SolidWorks sets an outside text right of its own line on a shoulder: the
# 6.800 spanned from about 1.5 to 14.2 right of its line (c4-r2 sheet).
_SHOULDER_TEXT_SPAN = (0.0015, 0.0142)
_SLOT_RUN_TEXT_LOW = 0.0055  # text centre below the run's lower line
# The row's block: three lines, 14.6 tall (measured on the 2026-10-30 farm
# sheet). The near rise (49.4) carries its text inside its own span, so the
# block sits inside the row's span above the rise's upper extension line,
# 0.7 clear, and under the row's line clear of its upper arrowhead (3.55
# long). At 0.8 clear and an estimated 17 tall, the 5.50 narrowing's
# taller rise put that arrowhead in "88.90" (machinist review, farm run
# 20261030T181155138Z); above the row line, outside its span, the block ran
# into the border and under the width's line (run 20261030T185048712Z).
_RAIL_ROW_TEXT_HALF_HIGH = 0.0073
_ROW_ARROW_LENGTH = 0.00355
_ROW_SHEET_Y = _sheet_y(FRONT_CENTER, 0.0)
_RISE_TOP_SHEET_Y = _sheet_y(FRONT_CENTER, LOW_SIDE_Y + NEAR_SLOT_RISE)
_RAIL_ROW_BLOCK_LOW = _RISE_TOP_SHEET_Y + 0.0007
# Side lanes (sheet m off the plan's end). The row's text clears the near
# rise's line by 2.5 (r4: the 10.3's outside arrow and its tail struck the
# block's last "L"); the width's line clears the row's text by 2.
_RAIL_ROW_LANE = LANE + 0.0025 + _RAIL_ROW_TEXT_HALF
_BAR_WIDTH_LANE = _RAIL_ROW_LANE + _RAIL_ROW_TEXT_HALF + 0.002
_SLOT_RUN_LANE = 0.011  # its text's left end clears the bar's end face
_BRACKET_OUTER_LANE = LANE
# The next row's (22.900) line clears the 6.400's shouldered text by 3.8.
_BRACKET_INNER_LANE = LANE + _SHOULDER_TEXT_SPAN[1] + 0.0038  # 0.026
# Each taller row one step further out (ruling A′'s four rows): its mid-span
# text clears the shorter row's line and that row's extension-line overshoot
# by 2.5 past a 2 overshoot (the texts and extension lines share heights).
_BRACKET_ROW_STEP = 0.0115
_BRACKET_ROW_LANES = (
    *(
        _BRACKET_INNER_LANE + step * _BRACKET_ROW_STEP
        for step in range(len(BRACKET_ROW_Y) - 2, -1, -1)
    ),
    _BRACKET_OUTER_LANE,
)  # rows 1-4: 0.049, 0.0375, 0.026, 0.008
# The far rise (c3-r6) past the outermost row: its text sits above that
# row's upper extension line, so its line need only clear the row's text, by
# 1.5 (c4-r9: one stack lane out, the line struck the 61.400's last "0",
# which reached 0.9 past it). Its text then stands 3.3 left of the end view.
_FAR_RISE_LANE = _BRACKET_ROW_LANES[0] + _BRACKET_ROW_TEXT_HALF + 0.0015  # 0.0575
# Rows 2 and 3 print mid-span; c4-r8 read the 44.900 and 61.400 texts, both
# mid-span, as one cluster, so the outermost row's text stands at the top of
# its span instead, 5 under its upper arrow tip.
_ROW_TEXT_UNDER_TIP = 0.005
_BRACKET_ROW_TEXT_Y = (
    _sheet_y(FRONT_CENTER, BRACKET_ROW_Y[0]) - _ROW_TEXT_UNDER_TIP - 0.00175,
    *(_sheet_y(FRONT_CENTER, (LOW_SIDE_Y + y) / 2.0) for y in BRACKET_ROW_Y[1:-1]),
)
_LAST_HOLE = len(RAIL_HOLE_X)
_HOLE_TEXT_X = (
    -(_TEXT_GAP + _RAIL_HOLE_1_TEXT_HALF) * 1000.0 / _S,  # left of the end face
    *(x / 2.0 for x in RAIL_HOLE_X[1:]),
)
FRONT_KEEP = {
    **{
        f"RailHole{k}X": (
            _sheet_x(FRONT_CENTER, text_x),
            _above_line(k - 1) + (TWO_LINE_DROP if k == _LAST_HOLE else TEXT_DROP),
        )
        for k, text_x in enumerate(_HOLE_TEXT_X, start=1)
    },
    "BarLength": (FRONT_CENTER[0], _below_line(5) + TEXT_DROP),
    "BarWidth": (_LEFT - _BAR_WIDTH_LANE, _ROW_SHEET_Y + 0.010),
    "RailRowY": (
        _LEFT - _RAIL_ROW_LANE,
        _RAIL_ROW_BLOCK_LOW + _RAIL_ROW_TEXT_HALF_HIGH,
    ),
    "SlotWidth": (
        _sheet_x(FRONT_CENTER, BRACKET_NEAR_X) + _TEXT_GAP + _SLOT_WIDTH_TEXT_HALF,
        _below_line(0) + TEXT_DROP,
    ),
    "NearSlotX": (
        _sheet_x(FRONT_CENTER, NEAR_SLOT_X) + _TEXT_GAP + _NEAR_SLOT_X_TEXT_HALF,
        _below_line(1) + TEXT_DROP,
    ),
    "BracketHole1X": (
        _sheet_x(FRONT_CENTER, BRACKET_NEAR_X) + _TEXT_GAP + _BRACKET_NEAR_X_TEXT_HALF,
        _below_line(2) + TEXT_DROP,
    ),
    "FarSlotX": (_sheet_x(FRONT_CENTER, FAR_SLOT_X / 2.0), _below_line(3) + TEXT_DROP),
    "BracketHole5X": (
        _sheet_x(FRONT_CENTER, BRACKET_FAR_X / 2.0),
        _below_line(4) + TEXT_DROP,
    ),
    **{
        f"BracketRow{row}Y": (_RIGHT + lane, text_y)
        for row, (lane, text_y) in enumerate(
            zip(_BRACKET_ROW_LANES[:-1], _BRACKET_ROW_TEXT_Y, strict=True), start=1
        )
    },
    f"BracketRow{len(BRACKET_ROW_Y)}Y": (
        _RIGHT + _BRACKET_OUTER_LANE,
        _BOTTOM - _BRACKET_OUTER_TEXT_BELOW,
    ),
    "SlotRun": (
        _RIGHT + _SLOT_RUN_LANE,
        _sheet_y(FRONT_CENTER, FAR_SLOT_Y - SLOT_RUN / 2.0) - _SLOT_RUN_TEXT_LOW,
    ),
    "NearSlotRise": (
        _LEFT - LANE,
        _sheet_y(FRONT_CENTER, LOW_SIDE_Y + NEAR_SLOT_RISE / 2.0),
    ),
    "FarSlotRise": (
        _RIGHT + _FAR_RISE_LANE,
        _sheet_y(FRONT_CENTER, (BRACKET_ROW_Y[0] + FAR_SLOT_RISE + LOW_SIDE_Y) / 2.0),
    ),
}
END_KEEP = {
    "BarThick": (END_CENTER[0] + _HALF_W_SHEET + LANE, END_CENTER[1]),
}
# The faced seats (rule 6, owner ruling 2026-10-30): each Ra 3.2 lands on its
# face's edge in the end view, SEAT_LAND_BELOW_TOP (model) under the view's
# top. The *Right view puts model +Z to the sheet's left, so the top seat's
# symbol stands up-left of the left edge and the underside's up-right of the
# right edge, both above the view and clear of the far rise's line; their
# one reason sits centred above them, under the tap callout's block.
FINISH_CHAR_HEIGHT = 0.0025
SEAT_LAND_BELOW_TOP = 10.0
_END_TOP = END_CENTER[1] + _HALF_W_SHEET
_END_HALF_THICK = BAR_THICK * _S / 2000.0
SEAT_SYMBOL_OUT = 0.006  # symbol from its edge, sheet x
SEAT_SYMBOL_UP = 0.010  # symbol above the view's top
TOP_SEAT_FINISH_XY = (
    END_CENTER[0] - _END_HALF_THICK - SEAT_SYMBOL_OUT,
    _END_TOP + SEAT_SYMBOL_UP,
)
UNDERSIDE_SEAT_FINISH_XY = (
    END_CENTER[0] + _END_HALF_THICK + SEAT_SYMBOL_OUT,
    _END_TOP + SEAT_SYMBOL_UP,
)
_SEAT_REASON_HALF = 0.026  # "TABLE AND RAIL SEATS", 20 glyphs
SEAT_REASON_XY = (END_CENTER[0] - _SEAT_REASON_HALF, _END_TOP + 0.026)  # top-left
# One slot's sizes count both slots; the width says they go through (r5).
DIMENSION_TEXT = {"SlotWidth": ("2X ", " THRU"), "SlotRun": ("2X ", "")}
# The width is milled to size (owner ruling #2083) and the thickness faced:
# both take the title block's .XX band. The rail-hole stations' tight band
# names its mate under the outermost station, the row, at the title block's
# band since c3-r7, keeps its reason (r3: every hole in line with the rail's
# row, which the one DRO setting gives).
CALLOUTS_BELOW = {
    f"RailHole{_LAST_HOLE}X": RAIL_MATE_CALLOUT,
    "RailRowY": RAIL_ROW_CALLOUT,
}
# The tap callout's two lines, centred about here, clear the 267 border by
# about 6 (r3 printed its first line touching it).
TAP_CALLOUT_XY = (0.318, 0.256)
# The bracket callout's four lines (two process, two native), centred about
# here: right of the length's extension line, under the end view, above the
# title block (the widening dropped the end view's foot 13, so the block
# drops 20 and moves 10 right to keep its leader under the 6.400's text).
BRACKET_CALLOUT_XY = (0.345, 0.105)

part_metadata(precision_sources=("DRAWING_PRECISION_BY_NAME",))

_INTO_BAR = ([0.0, 0.0, -1.0], ("__frame__",))
_UNIT = part_spec.UNIT


def _limits(model: float, places: int) -> list[float]:
    """A general-band dimension's acceptance limits on the inch sheet: the
    title block's band about the value printed at ``places``."""
    return limits(model, places, unit=_UNIT)


def _printed(model: float, places: int) -> float:
    """The millimetres of ``model`` printed at ``places`` inch decimals."""
    return round(round(model / 25.4, places) * 25.4, 9)


_CALLOUT_PLACES = 3  # every Hole Wizard length prints .XXX
_TAP_DRILL_PRINTED = _printed(part_spec.TAP_DRILL, _CALLOUT_PLACES)
_DRILLED = (drilled_oversize_mm(unit=_UNIT), 0.0)
_PLACES = part_spec.RAIL_HOLE_PLACES
_BAND = (part_spec.RAIL_HOLE_BAND, -part_spec.RAIL_HOLE_BAND)
_FROM_LOW_SIDE = (
    "bar_low_side",
    (("draw_ch_rocker_arm_tl_oblique_base_bar", "build"),),
)

# The faced -Y side: the datum the row's lateral station and the slot rises
# measure from.
requirement(
    "bar_low_side",
    kind="face",
    faces=(PlanarFace((0.0, -1.0, 0.0), -part_spec.LOW_SIDE_Y),),
    requirements=(),
    fields={
        "normal": ([0.0, -1.0, 0.0], ("__frame__",)),
        "plane": (
            {"frame": "model", "axis": "y", "value": part_spec.LOW_SIDE_Y},
            ("LOW_SIDE_Y",),
        ),
    },
)

# Both large faces: faced to the printed .X thickness, each a locating seat.
_SEAT_RA = (SEAT_UM, ("SURFACE_FINISHES",))
requirement(
    "top_seat",
    kind="face",
    faces=(surface_finish_by_key(SURFACE_FINISHES, "top_seat").face,),
    requirements=("height", "finish_ra"),
    fields={
        "normal": ([0.0, 0.0, 1.0], ("SURFACE_FINISHES",)),
        "plane": (
            {"frame": "model", "axis": "z", "value": part_spec.BAR_THICK},
            ("BAR_THICK",),
        ),
        "height": (
            _limits(part_spec.BAR_THICK, part_spec.THICK_PLACES),
            ("BAR_THICK",),
        ),
        "height_nominal": (part_spec.BAR_THICK, ("BAR_THICK",)),
        "finish_ra": _SEAT_RA,
    },
    precision={"height": part_spec.THICK_PLACES, "finish_ra": 1},
)
requirement(
    "underside_seat",
    kind="face",
    faces=(surface_finish_by_key(SURFACE_FINISHES, "underside_seat").face,),
    requirements=("finish_ra",),
    fields={
        "normal": ([0.0, 0.0, -1.0], ("SURFACE_FINISHES",)),
        "plane": ({"frame": "model", "axis": "z", "value": 0.0}, ("__frame__",)),
        "finish_ra": _SEAT_RA,
    },
    precision={"finish_ra": 1},
)

# The spindle-end face: the frame's x 0, the datum every printed station
# measures from; the far end carries the printed length.
requirement(
    "bar_spindle_end",
    kind="face",
    faces=(PlanarFace((-1.0, 0.0, 0.0), 0.0),),
    requirements=(),
    fields={
        "normal": ([-1.0, 0.0, 0.0], ("__frame__",)),
        "plane": ({"frame": "model", "axis": "x", "value": 0.0}, ("__frame__",)),
    },
)
requirement(
    "bar_far_end",
    kind="face",
    faces=(PlanarFace((1.0, 0.0, 0.0), BAR_LENGTH),),
    requirements=("length",),
    fields={
        "normal": ([1.0, 0.0, 0.0], ("__frame__",)),
        "plane": (
            {"frame": "model", "axis": "x", "value": BAR_LENGTH},
            ("BAR_LENGTH",),
        ),
        "length": (
            _limits(BAR_LENGTH, part_spec.STATION_PLACES),
            ("BAR_LENGTH", "STATION_PLACES"),
        ),
        "length_nominal": (BAR_LENGTH, ("BAR_LENGTH",)),
    },
    precision={"length": part_spec.STATION_PLACES},
)
# The +Y side: the width, milled to size from the 1/2 x 6 bar (owner ruling
# #2083), a size across both sides at the title block's .XX band.
requirement(
    "bar_high_side",
    kind="face",
    faces=(PlanarFace((0.0, 1.0, 0.0), HIGH_SIDE_Y),),
    requirements=("width",),
    fields={
        "normal": ([0.0, 1.0, 0.0], ("__frame__",)),
        "plane": (
            {"frame": "model", "axis": "y", "value": HIGH_SIDE_Y},
            ("HIGH_SIDE_Y",),
        ),
        "width": (
            _limits(BAR_WIDTH, part_spec.WIDTH_PLACES),
            ("BAR_WIDTH", "WIDTH_PLACES"),
        ),
        "width_nominal": (BAR_WIDTH, ("BAR_WIDTH",)),
    },
    precision={"width": part_spec.WIDTH_PLACES},
)

# The two through hold-down slots: two walls and two end arcs each, located
# to their lower end centres (station from the spindle end, rise from the
# faced -Y side); width and the end centres' run at .XX.
for _name, _x, _y, _rise, _x_source, _y_source, _rise_source in (
    (
        "near_slot",
        NEAR_SLOT_X,
        part_spec.NEAR_SLOT_Y,
        NEAR_SLOT_RISE,
        "NEAR_SLOT_X",
        "NEAR_SLOT_Y",
        "NEAR_SLOT_RISE",
    ),
    (
        "far_slot",
        FAR_SLOT_X,
        FAR_SLOT_Y,
        FAR_SLOT_RISE,
        "FAR_SLOT_X",
        "FAR_SLOT_Y",
        "FAR_SLOT_RISE",
    ),
):
    requirement(
        _name,
        kind="slot",
        faces=(
            PlanarFace((1.0, 0.0, 0.0), _x - part_spec.SLOT_WIDTH / 2.0),
            PlanarFace((-1.0, 0.0, 0.0), -(_x + part_spec.SLOT_WIDTH / 2.0)),
            CylinderFace(part_spec.SLOT_WIDTH, contains_x_mm=_x),
        ),
        requirements=("width", "separation", "station", "height", "thru"),
        fields={
            # The end centre nearer the -Y side: the point the station and rise locate.
            "at": (
                [_x, _y - SLOT_RUN / 2.0, part_spec.BAR_THICK],
                (_x_source, _y_source, "SLOT_RUN", "BAR_THICK"),
            ),
            "axis": _INTO_BAR,
            "width": (
                _limits(part_spec.SLOT_WIDTH, part_spec.SLOT_PLACES),
                ("SLOT_WIDTH", "SLOT_PLACES"),
            ),
            "width_nominal": (part_spec.SLOT_WIDTH, ("SLOT_WIDTH",)),
            "separation": (
                _limits(SLOT_RUN, part_spec.SLOT_PLACES),
                ("SLOT_RUN", "SLOT_PLACES"),
            ),
            "station": (
                _limits(_x, part_spec.STATION_PLACES),
                (_x_source, "STATION_PLACES"),
            ),
            "station_nominal": (_x, (_x_source,)),
            "height": (
                _limits(_rise, part_spec.STATION_PLACES),
                (_rise_source, "STATION_PLACES"),
            ),
            "height_nominal": (_rise, (_rise_source,)),
            "height_from": _FROM_LOW_SIDE,
            "thru": (True, ("SLOT_WIDTH",)),
        },
        precision={
            "width": part_spec.SLOT_PLACES,
            "separation": part_spec.SLOT_PLACES,
            "station": part_spec.STATION_PLACES,
            "height": part_spec.STATION_PLACES,
        },
    )

for _index, _x in enumerate(part_spec.RAIL_HOLE_X, start=1):
    # Baseline from the spindle-end face (the frame's x 0), in the rail
    # screws' clearance band, and from the faced -Y side at the title block's
    # band (c3-r7: the row's height has no mate; one DRO setting lines the
    # holes up).
    _station: dict[str, tuple[Any, tuple[Any, ...]]] = {
        "station": (
            limits(_x, _PLACES, _BAND),
            ("RAIL_HOLE_X", "RAIL_HOLE_BAND"),
        ),
        "station_nominal": (_x, ("RAIL_HOLE_X",)),
        "height": (
            _limits(part_spec.RAIL_ROW_Y, part_spec.RAIL_ROW_PLACES),
            ("RAIL_ROW_Y", "RAIL_ROW_PLACES"),
        ),
        "height_nominal": (part_spec.RAIL_ROW_Y, ("RAIL_ROW_Y",)),
        "height_from": _FROM_LOW_SIDE,
    }
    requirement(
        f"rail_hole_{_index}",
        kind="threaded_hole",
        faces=(CylinderFace(part_spec.TAP_DRILL, contains_x_mm=_x),),
        requirements=("thread", "dia", "station", "height", "thru", "note"),
        fields={
            "at": ([_x, 0.0, part_spec.BAR_THICK], ("RAIL_HOLE_X", "BAR_THICK")),
            "axis": _INTO_BAR,
            "thread": (
                f"{part_spec.RAIL_SCREW} UNC-{part_spec.TAP_SPEC.thread_class}",
                ("TAP_SPEC", "RAIL_SCREW"),
            ),
            "tap_drill_mm": (part_spec.TAP_DRILL, ("TAP_SPEC",)),
            "dia": (
                limits(_TAP_DRILL_PRINTED, _CALLOUT_PLACES, _DRILLED),
                ("TAP_SPEC", "TAP_DRILL"),
            ),
            "nominal_dia": (_TAP_DRILL_PRINTED, ("TAP_DRILL",)),
            "thru": (True, ("TAP_SPEC",)),
            **_station,
            # The matched-fit callout names the mate (RAIL_MATE_CALLOUT).
            "note": (
                RAIL_MATE_CALLOUT,
                ("RAIL_MATE_CALLOUT", "RAIL_SCREW_CLEARANCE", "RAIL_HOLE_BAND"),
            ),
        },
        precision={
            "dia": _CALLOUT_PLACES,
            "station": _PLACES,
            "height": part_spec.RAIL_ROW_PLACES,
        },
    )

_BRACKET_PLACES = part_spec.BRACKET_HOLE_PLACES
_STATION_PLACES = part_spec.BRACKET_STATION_PLACES
_STATION_BAND = (part_spec.BRACKET_STATION_BAND, -part_spec.BRACKET_STATION_BAND)
_CBORE_PLACES = part_spec.BRACKET_CBORE_PLACES
_BRACKET_DIA_PRINTED = _printed(BRACKET_HOLE_DIA, _CALLOUT_PLACES)
_FROM_UNDERSIDE = ([0.0, 0.0, 1.0], ("__frame__",))
_BRACKET_SOURCE = (("ch_rocker_arm_tl_vn_oblique_leadscrew_spec", "BASE_BAR_HOLES"),)
for _index, (_x, _y) in enumerate(BRACKET_HOLES, start=1):
    # Stations from the spindle-end face (the KP08's, exact millimetres with
    # their own band), rows from the faced -Y side at .XXX: each row holds
    # TL-28's four taps inside the screws' float.
    requirement(
        f"bracket_hole_{_index}",
        kind="hole",
        faces=(CylinderFace(BRACKET_HOLE_DIA, contains_x_mm=_x, contains_y_mm=_y),),
        requirements=("station", "height", "dia", "thru", "note"),
        fields={
            "at": ([_x, _y, 0.0], _BRACKET_SOURCE),
            "axis": _FROM_UNDERSIDE,
            "station": (
                limits(_x, _STATION_PLACES, _STATION_BAND),
                (*_BRACKET_SOURCE, "BRACKET_STATION_PLACES", "BRACKET_STATION_BAND"),
            ),
            "station_nominal": (_x, _BRACKET_SOURCE),
            "height": (
                _limits(_y - part_spec.LOW_SIDE_Y, _BRACKET_PLACES),
                (*_BRACKET_SOURCE, "LOW_SIDE_Y", "BRACKET_HOLE_PLACES"),
            ),
            "height_nominal": (
                _y - part_spec.LOW_SIDE_Y,
                (*_BRACKET_SOURCE, "LOW_SIDE_Y"),
            ),
            "height_from": _FROM_LOW_SIDE,
            "dia": (
                limits(_BRACKET_DIA_PRINTED, _CALLOUT_PLACES, _DRILLED),
                ("BRACKET_HOLE_DIA", "BRACKET_HOLE_SPEC"),
            ),
            "dia_nominal": (_BRACKET_DIA_PRINTED, ("BRACKET_HOLE_DIA",)),
            "thru": (True, ("BRACKET_HOLE_SPEC",)),
            # The pattern's tight band names its mate; the counterbores open
            # on the face the plan does not show.
            "note": (
                " ".join(BRACKET_CALLOUT_PROCESS.split("\n")).strip(),
                ("BRACKET_CALLOUT_PROCESS", "BRACKET_MATE"),
            ),
        },
        precision={
            "station": _STATION_PLACES,
            "height": _BRACKET_PLACES,
            "dia": _CALLOUT_PLACES,
        },
    )
    requirement(
        f"bracket_hole_{_index}_counterbore",
        kind="counterbore",
        faces=(
            CylinderFace(
                part_spec.BRACKET_CBORE_DIA, contains_x_mm=_x, contains_y_mm=_y
            ),
        ),
        requirements=("dia", "depth"),
        fields={
            "parent": (
                f"bracket_hole_{_index}",
                (
                    "BRACKET_HOLE_DIA",
                    ("draw_ch_rocker_arm_tl_oblique_base_bar", "build"),
                ),
            ),
            "dia": (
                _limits(part_spec.BRACKET_CBORE_DIA, _CBORE_PLACES),
                ("BRACKET_CBORE_DIA", "BRACKET_SCREW_HEAD_DIA"),
            ),
            "dia_nominal": (part_spec.BRACKET_CBORE_DIA, ("BRACKET_CBORE_DIA",)),
            "depth": (
                _limits(part_spec.BRACKET_CBORE_DEPTH, _CBORE_PLACES),
                ("BRACKET_CBORE_DEPTH", "BRACKET_SCREW_HEAD_HEIGHT"),
            ),
            "depth_ref": (part_spec.BRACKET_CBORE_DEPTH, ("BRACKET_CBORE_DEPTH",)),
        },
        precision={"dia": _CBORE_PLACES, "depth": _CBORE_PLACES},
    )


def _set_dimension_text(
    adapter: Any, annotations: list[Any], texts: dict[str, tuple[str, str]]
) -> None:
    """Write a native prefix/suffix on named imported dimensions; read back."""
    remaining = dict(texts)
    for raw in annotations:
        annotation = _early_bound(raw, "IAnnotation")
        text = remaining.pop(dimension_name(adapter, annotation), None)
        if text is None:
            continue
        display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
        display.SetText(1, text[0])  # swDimensionTextPrefix
        display.SetText(2, text[1])  # swDimensionTextSuffix
        got = (str(display.GetText(1) or ""), str(display.GetText(2) or ""))
        if got != text:
            raise RuntimeError(f"dimension text {text!r} did not persist: {got!r}")
    if remaining:
        raise RuntimeError(f"dimension texts not applied: {sorted(remaining)}")


def _omit_tap_thread_class(display: Any) -> None:
    """The title block's THREADS row owns the class (rule 2): the tap row
    reads ``7X 8-32 UNC THRU ALL``, not ``... - 2B ...``."""
    omit_title_block_thread_class(display, label="rail screw taps")
    native = _early_bound(display, "IDisplayDimension")
    resolved = [str(native.GetText(part) or "") for part in (1, 2, 3, 4)]
    if any(TAP_SPEC.thread_class in text for text in resolved):
        raise RuntimeError(
            f"rail screw taps: callout still prints its class: {resolved!r}"
        )


def _activate_view(adapter: Any, view: Any, *, label: str) -> None:
    """Make ``view`` the active view (a note lands in the active view)."""
    name = view_name(adapter, view)
    if not _early_bound(adapter.currentModel, "IDrawingDoc").ActivateView(name):
        raise RuntimeError(f"failed to activate the {label} view {name!r}")


def _seat_edges(view: Any) -> dict[str, Any]:
    """Each seat's edge in the end view, keyed by its finish control: the
    visible edge along Y (the bar's width) at that face's model Z, on the far
    end face the *Right view looks at. One scan serves both seats."""
    stations = {
        control.key: control.face.normal[2] * control.face.offset_mm
        for control in SURFACE_FINISHES
    }
    found: dict[str, list[tuple[float, Any]]] = {key: [] for key in stations}
    for raw in visible_view_entities(view, 1, label="end view seat edges"):
        edge = _early_bound(raw, "IEdge")
        start, end = edge.GetStartVertex(), edge.GetEndVertex()
        if start is None or end is None:
            continue
        p0, p1 = (
            tuple(float(v) * 1000.0 for v in _early_bound(vertex, "IVertex").GetPoint())
            for vertex in (start, end)
        )
        for key, z_mm in stations.items():
            if abs(p0[2] - z_mm) <= 0.01 and abs(p1[2] - z_mm) <= 0.01:
                found[key].append((abs(p1[1] - p0[1]), edge))
    edges = {}
    for key, candidates in found.items():
        if not candidates:
            raise RuntimeError(f"end view shows no {key} edge at z={stations[key]}")
        span, edge = max(candidates, key=lambda item: item[0])
        if abs(span - BAR_WIDTH) > 0.01:
            raise RuntimeError(f"end view's {key} edge spans {span:.3f}, not the width")
        edges[key] = edge
    return edges


def _add_view_note(
    adapter: Any, view: Any, text: str, xy: tuple[float, float], *, label: str
) -> None:
    """A free note in ``view`` at ``xy`` (its top-left corner); a note that
    did not land in its view raises (draw_mg_magnifying_vertical_rod)."""
    _activate_view(adapter, view, label=label)
    if add_note(adapter, text, *xy) is None:
        raise RuntimeError(f"failed to add the {label} note")
    texts = [
        " ".join(str(_early_bound(found, "INote").GetText() or "").split())
        for found in (_early_bound(view, "IView").GetNotes() or ())
    ]
    if texts.count(" ".join(text.split())) != 1:
        raise RuntimeError(f"{label} note did not land in its view: {texts!r}")


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open base bar source", await adapter.open_model(str(SOURCE)))
    required = (
        "Number",
        "Material Specification",
        "Finish",
        "Quantity",
        "Isometric View Note",
    )
    read_required_properties(
        adapter.currentModel, ("Revision", "Title", *required), required=required
    )
    drawing_model, _sheet = new_project_drawing(
        adapter,
        property_view=PART_STEM,
        scale=SHEET_SCALE,
        layout=SPEC.layout,
        unit=part_drawing_unit("ch-rocker-arm-tl-oblique-base-bar"),
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Rocker Oblique Trammel Base Bar Drawing",
            1: "Harmonic Analyzer shop fixture drawing",
            2: "Harmonic Analyzer Project",
            3: "rocker oblique trammel base bar; aluminum flat bar; MHA-CH-06-TL-20",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    # Explicit per-view scale: a view placed without one can silently
    # auto-scale, which shifts every coordinate-based pick on it. The end view
    # shares the plan's centre height: projected right of it (r2 hung it low).
    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=VIEW_SCALE)
    end = place_view(adapter, str(SOURCE), "*Right", *END_CENTER, scale=VIEW_SCALE)
    # finalize_drawing shades the pictorial isometric with edges.
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=ISO_SCALE)
    for view in (front, end, iso):
        set_hidden_lines_removed(adapter, view)

    # The plan shows the hidden RailRowReference and BracketRowReference
    # sketches, whose 88.90 and four bracket rows it prints.
    annotations = [
        *curate_view_dimensions(
            adapter,
            front,
            keep=FRONT_KEEP,
            view_label="plan",
            dimensions_by_feature=DRAWING_DIMENSIONS,
        ),
        *curate_view_dimensions(
            adapter,
            end,
            keep=END_KEEP,
            view_label="end view",
            dimensions_by_feature=DRAWING_DIMENSIONS,
        ),
    ]
    # Places (and so each dimension's tolerance) are authored on the part; the
    # sheet only proves the import kept them, then marks the slot counts and
    # writes the mate callouts.
    assert_imported_precision(adapter, annotations, DRAWING_PRECISION_BY_NAME)
    assert_imported_metric_dimensions(
        adapter,
        annotations,
        {
            name: places
            for (_feature, name), (places, _band) in METRIC_DIMENSIONS.items()
        },
    )
    _set_dimension_text(adapter, annotations, DIMENSION_TEXT)
    set_dimension_callouts(adapter, annotations, CALLOUTS_BELOW)

    if not auto_center_marks(adapter, front, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center marks to the plan")
    # One mark on each slot's round ends (draw_ch_rocker_arm_tl_outline_template):
    # the rises and the 2X 6.00 run land on them, so the run reads as
    # centre-to-centre (rule 12) and not as the slot's overall length.
    if not auto_center_marks(adapter, front, holes=False, slots=True, size=0.0025):
        raise RuntimeError("failed to add the slot center marks to the plan")
    tap_callout = add_native_hole_callout(
        adapter,
        front,
        edge_xy=(
            _sheet_x(FRONT_CENTER, RAIL_HOLE_X[-1]) + 0.6 * TAP_R_SHEET,
            _sheet_y(FRONT_CENTER, 0.0) + 0.8 * TAP_R_SHEET,
        ),
        callout_xy=TAP_CALLOUT_XY,
        label="rail screw taps",
    )
    _omit_tap_thread_class(tap_callout)
    # A THRU tap's callout carries no hw-tapdrldia (farm r1): every length
    # it does carry prints .XXX.
    set_callout_lengths_to_three_places(tap_callout, label="rail screw taps")
    # The far outer hole's edge, down and right of its centre: the leader
    # leaves away from the far row's station line.
    bracket_callout = add_native_hole_callout(
        adapter,
        front,
        edge_xy=(
            _sheet_x(FRONT_CENTER, BRACKET_FAR_X) + 0.6 * BRACKET_R_SHEET,
            _sheet_y(FRONT_CENTER, BRACKET_OUTER_Y) - 0.8 * BRACKET_R_SHEET,
        ),
        callout_xy=BRACKET_CALLOUT_XY,
        label="end bracket holes",
        process=BRACKET_CALLOUT_PROCESS,
    )
    set_hole_callout_precision(
        bracket_callout, BRACKET_CALLOUT_PRECISION, label="end bracket holes"
    )
    # The faced seats' Ra 125 µin, each on its own face's edge in the end view,
    # under their one reason (rule 7: say why, beside the symbols).
    seat_edges = _seat_edges(end)
    for key, symbol_xy, label in (
        ("top_seat", TOP_SEAT_FINISH_XY, "top seat finish"),
        ("underside_seat", UNDERSIDE_SEAT_FINISH_XY, "underside seat finish"),
    ):
        control = surface_finish_by_key(SURFACE_FINISHES, key)
        z_mm = control.face.normal[2] * control.face.offset_mm
        add_surface_finish(
            adapter,
            end,
            symbol_xy=symbol_xy,
            control=control,
            label=label,
            char_height=FINISH_CHAR_HEIGHT,
            entity=seat_edges[key],
            leader_attach_xy=model_point_in_view(
                adapter,
                end,
                (
                    BAR_LENGTH / 1000.0,
                    (HIGH_SIDE_Y - SEAT_LAND_BELOW_TOP) / 1000.0,
                    z_mm / 1000.0,
                ),
                label=f"{label} landing",
            ),
        )
    _add_view_note(
        adapter, end, SEAT_FINISH_REASON, SEAT_REASON_XY, label="seat finish reason"
    )

    # The property-linked blocks land in the active view: the plan.
    _activate_view(adapter, front, label="plan")
    add_property_linked_note(adapter, "Isometric View Note", *ISO_NOTE_XY)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Rocker Oblique Trammel Base Bar Drawing",
        scale=SHEET_SCALE,
        layout=SPEC.layout,
        # SolidWorks pins its own "#8-32 Tapped Hole" note to the plan once
        # the tap carries a hole callout; the callout already states it.
        redundant_note_substrings=("Tapped Hole",),
        expected_redundant_notes=1,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[PART_STEM])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
