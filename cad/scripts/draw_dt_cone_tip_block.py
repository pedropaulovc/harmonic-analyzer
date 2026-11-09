r"""Create the simplicity-policy machinist drawing for the cone tip block."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from enum import Enum
import math
import re
import sys
import textwrap
from typing import Any

from solidworks_mcp.adapters.solidworks.drawing import (
    add_note,
    auto_center_marks,
    dimension_name,
    place_view,
)

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
    set_reference_dimension,
)
from _drawing_edges import visible_view_entities
from _drawing_finish import add_surface_finish
import _drawing_hidden_sketches as hidden_sketches
from _drawing_hole_callout import add_native_hole_callout, set_hole_callout_precision
from _drawing_leader_notes import add_leader_note
import _drawing_leaders
from _drawing_attachment import _is_same_attachment
from _drawing_edge_dimensions import (
    add_edge_dimension,
    assert_dimension_measures,
)
from _drawing_projection import model_point_in_view
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_view_display import set_hidden_lines_removed
from _machinist_review_mode import MachinistReviewMode
from _paths import CAD_ROOT
from _part_properties import part_drawing_unit
from _session import run_build
from _surface_finish import surface_finish_by_key
import _config
import _telemetry
from dt_cone_tip_block_spec import (
    ADJUSTER_AXIS_HEIGHT,
    ADJUSTER_BORE_DIA,
    ADJUSTER_CSK,
    BLOCK_HEIGHT,
    BLOCK_X,
    BLOCK_Z,
    DOWEL_HOLE_DEPTH,
    DOWEL_HOLE_DEPTH_PLACES,
    DOWEL_HOLE_DIA,
    DOWEL_HOLE_PRINTED_TEXT,
    DOWEL_X,
    DOWEL_X_PRINTED_TEXT,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    DRAWING_REFERENCE_PRECISION,
    FOOT_BORE_DIA,
    FOOT_DEPTH,
    FOOT_DEPTH_PLACES,
    FOOT_TAP_X,
    FOOT_TAP_Z,
    FOOT_THREAD_DEPTH,
    HOLDDOWN_THREAD,
    PINCH_BORE_DIA,
    PINCH_CLEARANCE_DIA,
    PINCH_HEIGHT,
    SLIT_DEPTH,
    SLIT_W,
    SURFACE_FINISHES,
    length_text,
    printed_value_text,
)
from dt_drive_train_steps import step_ref


# Cached machinist review leaf: a FIX or ERROR verdict fails the build.
MACHINIST_REVIEW = MachinistReviewMode.ENFORCE

SPEC = DRAWINGS_BY_NAME["dt_cone_tip_block"]
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

# Rule-23 retention, owner ruling 2026-11-07 (MHA-DT-00 rubric sample, PR
# #2248).  The press ream's callout, under its banded diameter on
# the bottom view: the process and its depth (rule 12; no view shows the
# blind hole's floor, hidden lines removed and no section cut, so the depth
# rides the callout at its .XX with the native depth symbol), then the flag
# to the numbered note that carries the rest.  Machinist review of round 6:
# four rows of words under the size (#2, rule 7 allows two), depth in words
# (#3), and "TO FLOOR", an assembly instruction that the MHA-DT-00 step
# already states (#1).
DOWEL_PIN_NUMBER = _config.parts("dt-vn-locating-pin")["number"]
PLATFORM_NUMBER = _config.parts("dt-cone-swing-platform")["number"]
DOWEL_NOTE_NUMBER = 1
DOWEL_HOLE_DEPTH_TEXT = length_text(DOWEL_HOLE_DEPTH, DOWEL_HOLE_DEPTH_PLACES)
DOWEL_HOLE_CALLOUT = "\n".join(
    (
        f"REAM <HOLE-DEPTH> {DOWEL_HOLE_DEPTH_TEXT}",
        f"SEE NOTE {DOWEL_NOTE_NUMBER}",
    )
)
# The callout as it prints (the native token is one depth glyph), for its
# ink estimate.
DOWEL_HOLE_CALLOUT_PRINTED = DOWEL_HOLE_CALLOUT.replace("<HOLE-DEPTH>", "\u21a7")
# The numbered note the callout flags: the fit and its mate, where and
# through what the hole is match-drilled (the lift rod's made-at-assembly
# precedent, dt_pinion_lift_rod_spec.PIN_HOLE_CALLOUT; MHA-DT-00 step
# post-and-tip-block points back at this callout), and the pair's
# disassembly (round 6, #0: the dowel is pressed into a blind ream, so the
# sheet declares the press fit permanent; the dowel only slips in MHA-DT-20,
# so the two lift off it together).  Round 7 (#0, #1): the note is the
# requirement only, four rows at most (rule 7), clear of the border.
# Wrapped to a hanging indent under its number, at most DOWEL_NOTE_WIDTH
# characters a row; the step reference never breaks across rows.
DOWEL_NOTE_WIDTH = 30
_NBSP = "\u00a0"
DOWEL_NOTE = textwrap.fill(
    f"PRESS FIT FOR {DOWEL_PIN_NUMBER}, PERMANENT. MATCH-DRILLED UP THRU "
    f"{PLATFORM_NUMBER} AT {step_ref('post-and-tip-block').replace(' ', _NBSP)}.",
    width=DOWEL_NOTE_WIDTH,
    initial_indent=f"{DOWEL_NOTE_NUMBER}. ",
    subsequent_indent="   ",
    break_on_hyphens=False,
).replace(_NBSP, " ")

# User ruling 2026-09-29 (eight-views-4.png, lower right): the block is a
# plain straight prism standing on the swing platform, held down by one
# socket head cap screw rising from under the platform into a blind tap in
# its foot.  The prism is only 11.75 deep, so the sheet is back at 2:1 and a
# bottom view under the front view carries the tap.
SHEET_SCALE = (2.0, 1.0)
_S = SHEET_SCALE[0] / SHEET_SCALE[1] / 1000.0
# The 52.66 block (38.100 common cone-axis height) prints 105 mm tall: the
# front row rises 3 mm and everything above it 7.8 mm over the 47.93 block's
# layout, so every gap above the row keeps its measured air, and the bottom
# view drops 1.8 mm.  The plan rides 9.7 mm higher again (machinist review
# of d84a42ca7): PassageCenter's function line stands over its value, with
# the view-crowding air (the shorter box's height) under the cutting-plane
# letter the plan then carried.  Section A-A is gone (machinist review of
# f86ff6bf8: its cut clipped the hold-down tap drill into an unexplained
# sliver, and every hole it showed is fully defined by its callout, rule 1),
# and the plan keeps its place so every other gap keeps its measured air.
FRONT_CENTER = (0.072, 0.132)
TOP_CENTER = (FRONT_CENTER[0], 0.2395)
BOTTOM_CENTER = (FRONT_CENTER[0], 0.0382)
# The right view and the removed VIEW B stand on the front view's projection
# row; their x follows from the adjuster callout between the front and right
# views (RIGHT_CENTER, below).
# The 2:1 isometric (38 x 108 mm) stands right of the row, past its top.
ISO_CENTER = (0.365, 0.209)
# Every view centres on the prism, whose centre is the model origin.
Z_NORTH = BLOCK_Z / 2.0
Z_SOUTH = -BLOCK_Z / 2.0


def _elevation_y(model_y: float, center: tuple[float, float]) -> float:
    return center[1] + (model_y - BLOCK_HEIGHT / 2.0) * _S


def _plan_y(model_z: float) -> float:
    """Sheet y of a model station in the plan (*Top shows +Z, north, down)."""
    return TOP_CENTER[1] - model_z * _S


def _bottom_y(model_z: float) -> float:
    """Sheet y of a model station in the bottom view (north up, by the front)."""
    return BOTTOM_CENTER[1] + model_z * _S


def _right_x(model_z: float) -> float:
    """Sheet x of a model station in the right view (north on the left)."""
    return RIGHT_CENTER[0] - model_z * _S


# Imported value text measured on run 5637ac42: a four-character value
# ("1.20", "7.50") prints ~9.1 mm wide, a three-character one ("6.0", "7.5")
# ~6.4 mm, and a native arrowhead ~3.4 mm long.  Main's eye-pass of that run
# found values printed across their own witness lines and a hole centreline
# (d976281d ruling: no text on a line), so the values below are placed from
# these sizes rather than centred on a feature.
VALUE_TEXT_HALF_WIDTH = 0.0046
VALUE_TEXT_HALF_HEIGHT = 0.0019
# A value's glyph, from the four-character value's measured width.
_VALUE_GLYPH_WIDTH = 2.0 * VALUE_TEXT_HALF_WIDTH / 4.0
ARROW_LENGTH = 0.0034
# An inside arrowhead is about 0.6 mm across (287c).
ARROW_HALF_WIDTH = 0.0003
TEXT_CLEARANCE = 0.0015
# Clearances are rounded outward by this much, so a placement derived to one
# does not stand exactly on the audit's limit.
ROUND_OUT = 0.0001

# The adjuster's hole callout stands between the adjuster elevation and the
# right view.  #946 / MHA-DT-21: at 9a0f50b1c it stood below-right of the hole
# and its leader climbed ~28 mm over the front view to the rim, ~16 mm
# further than the hole's approach from the right face, reading as an edge of
# the part.  The short way in is from the right face, so the callout stands
# right of the hole with the shaft-tip flag over it (review: named above
# the thread callout it describes): the flag's top keeps the height it took
# an arrow clearance (plus half an arrowhead) under the slit floor's depth
# witness, which no longer prints (machinist review of e04fd60ab: the floor
# stands inside the bore, dt_cone_tip_block_spec), so the right-hand views
# keep their measured places, and the callout a text clearance under the
# name.  Its leader leaves the shoulder's left end at
# ADJUSTER_LEADER_ANGLE: at 45 deg the run over the part is 4.4 mm longer
# than the hole's approach, past Main's ~4 mm brief (swing's RD2 fix,
# 4dda16fd5, left 3.8); at 3:2, 40 deg made it 3.2.  At 2:1 the hole's
# approach from the right face grows to 13.8 mm and 40 deg runs 4.25 over it,
# so the leader drops to 37 deg (3.5).  Every degree shallower slides the
# right-hand views ~1.2 mm further right.  Hole callouts' extents (every
# line plus the shoulder) are measured on the I31 render like the rest of the
# sheet's ink (see "Sheet ink audit"), except the right end: on the c289ee94
# render the shoulder ran 29.0 mm right of the callout's point, 1.2 mm past
# I31's 27.8, and stopped 0.3 mm short of the right view's north face.
ADJUSTER_CALLOUT_EXTENT = (0.0295, 0.0086, 0.0290, 0.0078)
# The flag's ink from its upper-left corner: ADJUSTER ENTRY's fourteen
# glyphs measured 36.3 x 3.4 mm (287c); its 21 glyphs at that pitch, rounded
# out.  An estimate until a render measures it.
ADJUSTER_ENTRY_EXTENT = (0.0, 0.0036, 0.0560, 0.0)
ADJUSTER_LEADER_ANGLE = math.radians(37.0)
ADJUSTER_FLOOR_GAP = _drawing_leaders.ARROW_TEXT_CLEARANCE + ARROW_HALF_WIDTH + ROUND_OUT
ADJUSTER_ENTRY_Y = _elevation_y(BLOCK_HEIGHT - SLIT_DEPTH, FRONT_CENTER) - ADJUSTER_FLOOR_GAP
ADJUSTER_SHOULDER_Y = (
    ADJUSTER_ENTRY_Y
    - ADJUSTER_ENTRY_EXTENT[1]
    - TEXT_CLEARANCE
    - ROUND_OUT
    - ADJUSTER_CALLOUT_EXTENT[3]
    - ADJUSTER_CALLOUT_EXTENT[1]
)
_ADJUSTER_SHOULDER_DX = (
    _elevation_y(ADJUSTER_AXIS_HEIGHT, FRONT_CENTER) - ADJUSTER_SHOULDER_Y
) / math.tan(ADJUSTER_LEADER_ANGLE)
ADJUSTER_CALLOUT_DX = _ADJUSTER_SHOULDER_DX + ADJUSTER_CALLOUT_EXTENT[0]
ADJUSTER_CALLOUT_Y = ADJUSTER_SHOULDER_Y + ADJUSTER_CALLOUT_EXTENT[1]
# The name stands centred over the callout.
ADJUSTER_ENTRY_DX = _ADJUSTER_SHOULDER_DX + (
    ADJUSTER_CALLOUT_EXTENT[0] + ADJUSTER_CALLOUT_EXTENT[2] - ADJUSTER_ENTRY_EXTENT[2]
) / 2.0
# The right view's north face stands ADJUSTER_VIEW_AIR past the callout's
# right end.  (I31, 7ab69742b: at x 0.166 the callout's longest line ran over
# that face; the right view slid 5 mm then, the removed views with it.  Blind
# machinist review of c289ee94: a text clearance of air read as the callout
# pressing against the view, so the air is 3 mm.)  The removed views B and C
# keep the row's 72 mm pitch, so the gaps to their right keep their measured
# air.
ADJUSTER_VIEW_AIR = 0.003
_RIGHT_NORTH_FACE_X = (
    FRONT_CENTER[0]
    + ADJUSTER_CALLOUT_DX
    + ADJUSTER_CALLOUT_EXTENT[2]
    + ADJUSTER_VIEW_AIR
    + ROUND_OUT
)
VIEW_ROW_PITCH = 0.072
RIGHT_CENTER = (_RIGHT_NORTH_FACE_X + Z_NORTH * _S, FRONT_CENTER[1])
LEFT_CENTER = (RIGHT_CENTER[0] + VIEW_ROW_PITCH, FRONT_CENTER[1])
# The 1.2 slot prints 2.4 mm wide, narrower than its value, so the arrows
# stand outside the slot walls and the text sits right of the right arrow's
# tail on the extended dimension line.  Right, because on the adjuster
# elevation PassageCenter's span from the -X face (r3) occupies the slot's
# left.  Its one-line SLOT INTO BORE row above the value is wider than the
# value, so the text block's left edge stands a text clearance past the
# right arrow's tail (an outside arrow runs 6.4 mm past its extension line,
# OUTSIDE_ARROW_RUN below), which also clears PassageCenter's outside tail
# over the slot centre.  The line stands 8 mm over the block's top, so the
# row prints under PassageCenter's line with text clearance between them.
SLIT_LINE_RISE = 0.008
SLIT_ROW_LEFT = SLIT_W * _S / 2.0 + 0.0064 + TEXT_CLEARANCE + ROUND_OUT
# Machinist review of d84a42ca7 (rules 3/4): a three-place size given a
# function names its mate and what it holds at its own dimension.  Above a
# value the text keeps to one line (SolidWorks drops multi-line text placed
# above a dimension); below it, the full mate number gets its own row.
DIMENSION_CALLOUTS = {
    # The adjuster thread runs through the block's depth: its length is the
    # cup screw's engagement window (build_dt_drive_train_assembly's embed
    # stack).  Two rows of words (round-1 farm review, dt-fab-4); the whole
    # value/mate block sits on a native offset shelf right of the plan.
    "Depth": "SETS MHA-DT-VN-55\nENGAGEMENT",
    # Rule-23 retention, owner ruling 2026-11-07 (MHA-DT-00 rubric sample, PR
    # #2248): the locating dowel's press ream -- its depth,
    # the dowel pressed to its floor and the match-drilling through MHA-DT-20.
    "DowelHoleDia": DOWEL_HOLE_CALLOUT,
}
DIMENSION_CALLOUTS_ABOVE = {
    # The +X face stands over the platform's narrow west edge
    # (build_dt_drive_train_assembly's print-worst containment): no fit, so
    # rule 4's few words of reason name the edge it keeps inside (machinist
    # review of c4c0e848a: "STAYS ON" named no feature).
    "Width": "WITHIN MHA-DT-20 EDGE",
    # Screen review (dt-fab-4): a location carries its value only; the
    # shaft-tip function moved to the bore's callout (BORE_FLAG_TEXT).
    # Machinist review of e04fd60ab (clarity, gating): the slit depth's floor
    # stands inside the Ø4.04 bore, so its lower extension line ended on no
    # drawn edge and its 15.2 read against 52.7 - 38.10 = 14.6 to the bore
    # centre.  The slit only has to open into the bore, so the part no longer
    # marks its depth and the slot width states the extent.
    "SlitW": "SLOT INTO BORE",
}
# Callout text measured on the d84a42ca7 render: SLOT DEPTH's ten glyphs
# print 25.3 mm wide, and each row stacks 4.55 mm (the 15.2 over SLOT
# DEPTH).  A value and its rows centre on the dimension's point; a
# horizontal dimension with a row over its value prints its line 4.5 mm
# under that point (the 3.97's stacked deviations, 287c).
CALLOUT_GLYPH_WIDTH = 0.00253
TEXT_ROW_HEIGHT = 0.00455
TWO_ROW_LINE_DROP = 0.0045


def _callout_half_width(text: str) -> float:
    return max(len(line) for line in text.split("\n")) * CALLOUT_GLYPH_WIDTH / 2.0


# Left of the adjuster elevation, stepping out from the part: the axis
# height on the inner line, its value at half its span; then the block
# height, its value at half the block, clear of the axis height's value and
# the sheet border.
AXIS_HEIGHT_LINE_DX = 0.031
BLOCK_HEIGHT_LINE_DX = 0.052
# The width's value and its function line are wider than its span, so they
# stand right of the +X extension line on the extended dimension line, 3.5
# mm under the bottom view's south edge.  Round-1 farm review (dt-fab-4):
# the width moved off the front view's foot, which now carries the seat's
# finish symbol; the base sketch's width reads in the view of the foot.
WIDTH_LINE_DROP = 0.0035
FRONT_KEEP = {
    "BlockHt": (FRONT_CENTER[0] - BLOCK_HEIGHT_LINE_DX, FRONT_CENTER[1]),
    "SlitW": (
        FRONT_CENTER[0]
        + SLIT_ROW_LEFT
        + _callout_half_width(DIMENSION_CALLOUTS_ABOVE["SlitW"]),
        _elevation_y(BLOCK_HEIGHT, FRONT_CENTER) + SLIT_LINE_RISE + TWO_ROW_LINE_DROP,
    ),
}
# PassageCenter stands above SlitW on the adjuster elevation, its line
# 21.2 mm over the block's top; the plan's north edge is the ceiling for
# both.  A single-row value prints its line 2.8 mm under it
# (HORIZONTAL_LINE_DROP, defined with the ink audit below).
PASSAGE_CENTER_RISE = 0.0212 + 0.0028
# swDimensionArrowsSide_e, set rather than left to the document's smart
# arrows: swDimArrowsOutside = 1, swDimArrowsInside = 0.  The 4.875's short
# span leaves no room for inside arrows (d84a42ca7: the 4.875's line and
# arrows struck its "5"); outside, a vertical dimension prints no line
# between them.
ARROWS_OUTSIDE = ("SlitW", "FootTapZ")
# The pinch depth's span holds its two 3.4 mm
# arrows: with no outside tail right of the hole-centre witness, the pinch
# clearance callout's leader passes there (leader-crosses-line, af13c8ff8).
# The width and FootTapX hold theirs inside too, so no tail runs toward the
# bottom view's callout.  The plan depth's text stands on its offset shelf,
# so its 19.3 mm span holds both arrows and the line joining them, which the
# shelf's leader meets (machinist review of PR 2107: with outside arrows the
# leader ended in empty space between the witnesses).
ARROWS_INSIDE = (
    "PinchHeight",
    "PinchDepthCenter",
    "Width",
    "FootTapX",
    "DowelX",
    "Depth",
)
_DIM_ARROWS_OUTSIDE = 1
_DIM_ARROWS_INSIDE = 0
# The 9.750 value and its three mate/function rows are almost as tall as
# the depth's 19.5 mm printed span.  Outside arrows alone still strike the
# first and last rows (PR1709's reviewed PDF).  Put the dimension right of
# the plan, then use native OffsetText so moving the complete text block
# onto its right-hand shelf cannot drag the witnesses through it again.
_PLAN_RIGHT = TOP_CENTER[0] + BLOCK_X * _S / 2.0
PLAN_DEPTH_LINE_X = _PLAN_RIGHT + 0.010
TOP_KEEP = {
    "Depth": (PLAN_DEPTH_LINE_X, _plan_y(0.0)),
}
TOP_TEXT_OFFSETS = {
    "Depth": (
        PLAN_DEPTH_LINE_X + 0.010 + _callout_half_width(DIMENSION_CALLOUTS["Depth"]),
        _plan_y(0.0),
    ),
}
# The half-block station below runs from the north face to the pinch-hole
# centre, so its value sits midway along its span.  Centred on the hole (run
# 5637ac42), the witness and centreline ended in the decimal point; at +0.003
# its dimension line printed on the block's top edge.
#
# r3: the pinch-hole height from the foot stands past the block's south face,
# on the right; both witnesses leave the south face, whose outline hides the
# model's reference line (build_cone_tip_block, PinchHeightReference).
PINCH_HEIGHT_LINE_X = _right_x(Z_SOUTH) + 0.010
RIGHT_KEEP = {
    "PinchDepthCenter": (
        _right_x(BLOCK_Z / 4.0),
        _elevation_y(BLOCK_HEIGHT, RIGHT_CENTER) + 0.007,
    ),
    "PinchHeight": (
        PINCH_HEIGHT_LINE_X,
        _elevation_y(PINCH_HEIGHT / 2.0, RIGHT_CENTER),
    ),
}
LEFT_KEEP: dict[str, tuple[float, float]] = {}
# The bottom view: the hold-down tap's two stations, each from the face the
# model locates it from -- across from the -X face (the PassageCenter datum)
# above the view, along the axis from the north face (the view's upper edge)
# left of it.  Both witnesses leave the tap's centre.
_BOTTOM_LEFT = BOTTOM_CENTER[0] - BLOCK_X * _S / 2.0
_BOTTOM_RIGHT = BOTTOM_CENTER[0] + BLOCK_X * _S / 2.0
FOOT_TAP_CENTER = (_BOTTOM_LEFT + FOOT_TAP_X * _S, _bottom_y(Z_NORTH - FOOT_TAP_Z))
FOOT_TAP_X_RISE = 0.0078
FOOT_TAP_Z_LINE_X = _BOTTOM_LEFT - 0.013
# Rule-23 retention, owner ruling 2026-11-07 (MHA-DT-00 rubric sample, PR
# #2248): the locating dowel's press ream, on the tap's line.  Machinist
# review of round 6, #9: its station is a baseline from the -X face (the
# FootTapX datum), printed as a reference.  Its line runs 1.5 mm under the
# view's south edge, 2 mm over the width's line (round-1 farm review,
# dt-fab-4: the width reads under this view, where the BOTTOM VIEW caption
# stood); inside its span the value would stand on that edge.  Its value
# hangs LEFT of the view, past FootTapZ's line and that line's lower outside
# arrow by an arrow's clearance, so the space right of the view is the
# width's and the ream callout's (round 6, #4: on the r6 render the ream's
# leader ran through the old ".228 ±.01" value and its line).
DOWEL_CENTER = (_BOTTOM_LEFT + DOWEL_X * _S, FOOT_TAP_CENTER[1])
DOWEL_X_EXTENT = (
    len(DOWEL_X_PRINTED_TEXT) * _VALUE_GLYPH_WIDTH / 2.0,
    VALUE_TEXT_HALF_HEIGHT,
    len(DOWEL_X_PRINTED_TEXT) * _VALUE_GLYPH_WIDTH / 2.0,
    VALUE_TEXT_HALF_HEIGHT,
)
DOWEL_X_TEXT_RIGHT = (
    FOOT_TAP_Z_LINE_X
    - _drawing_leaders.ARROW_TEXT_CLEARANCE
    - ARROW_HALF_WIDTH
    - ROUND_OUT
)
DOWEL_X_TEXT_RISE = 0.0013
# The ream's size and its two callout rows, measured on the r6 render (run
# 20261107T030627004Z): its callout rows printed 2.71 mm a glyph and 5.3 mm
# a line, the size row two lines (its stacked band), and SolidWorks centred
# the block, from the last row's underline to the band's top, on the
# dimension's point.  The leader leaves that underline's near (left) end.
DOWEL_CALLOUT_GLYPH_WIDTH = 0.00271
DOWEL_CALLOUT_LINE_PITCH = 0.0053
_DOWEL_HOLE_HALF_WIDTH = max(
    len(line) * DOWEL_CALLOUT_GLYPH_WIDTH / 2.0
    for line in (DOWEL_HOLE_PRINTED_TEXT, *DOWEL_HOLE_CALLOUT_PRINTED.split("\n"))
)
_DOWEL_HOLE_HALF_HEIGHT = (
    (2 + len(DOWEL_HOLE_CALLOUT.split("\n"))) * DOWEL_CALLOUT_LINE_PITCH / 2.0
)
DOWEL_HOLE_EXTENT = (
    _DOWEL_HOLE_HALF_WIDTH,
    _DOWEL_HOLE_HALF_HEIGHT,
    _DOWEL_HOLE_HALF_WIDTH,
    _DOWEL_HOLE_HALF_HEIGHT,
)
BOTTOM_KEEP = {
    "FootTapX": (
        (_BOTTOM_LEFT + FOOT_TAP_CENTER[0]) / 2.0,
        _bottom_y(Z_NORTH) + FOOT_TAP_X_RISE,
    ),
    "FootTapZ": (
        FOOT_TAP_Z_LINE_X,
        (_bottom_y(Z_NORTH) + FOOT_TAP_CENTER[1]) / 2.0,
    ),
    "Width": (
        _BOTTOM_RIGHT
        + TEXT_CLEARANCE
        + ROUND_OUT
        + _callout_half_width(DIMENSION_CALLOUTS_ABOVE["Width"]),
        _bottom_y(Z_SOUTH) - WIDTH_LINE_DROP + TWO_ROW_LINE_DROP,
    ),
    "DowelX": (
        DOWEL_X_TEXT_RIGHT - DOWEL_X_EXTENT[2],
        _bottom_y(Z_SOUTH) + DOWEL_X_TEXT_RISE,
    ),
}
# Round-1 farm review (dt-fab-4, rule 7): VIEW B's far-jaw thread is located
# in its own view by two driven drawing dimensions that mirror the right
# view's stations: from the north face (VIEW B's right edge, as it looks from
# -X) and from the foot, both to the hole's centre.  The depth's value stands
# over the view as the right view's does; the height's line stands right of
# the view, clear of the thread callout's leader from the upper left.
_LEFT_NORTH_X = LEFT_CENTER[0] + Z_NORTH * _S
VIEW_B_DIMENSIONS = {
    "ViewBPinchDepth": (
        LEFT_CENTER[0] + BLOCK_Z * _S / 4.0,
        _elevation_y(BLOCK_HEIGHT, LEFT_CENTER) + 0.007,
    ),
    "ViewBPinchHeight": (
        _LEFT_NORTH_X + 0.010,
        _elevation_y(PINCH_HEIGHT / 2.0, LEFT_CENTER),
    ),
}
# VIEW B's letter caption sits just under its foot; the projected right and
# bottom views carry none (rule 9).
CAPTION_Y = _elevation_y(0.0, FRONT_CENTER) - 0.004
# A one-line "VIEW B": six glyphs at the 287c captions' 2.6 mm pitch, rounded
# out.  An estimate until a render measures it.
VIEW_CAPTION_EXTENT = (0.0, 0.0036, 0.0160, 0.0)
# The shaft tip the bore locates, named at the bore's callout (screen review
# dt-fab-4: the location carries its value only, rule 4).
BORE_FLAG_TEXT = "LOCATES MHA-DT-04 TIP"
# Review C1: the left view sits right of the right view, out of third-angle
# order, so it is a removed view named by a letter arrow on the view that
# shows the face it looks at.  VIEW B looks at the -X (pinch-thread) face:
# the arrow meets the front view's left edge between the axis-height and
# block-top extension lines.  The pair is (note upper-left, leader tip),
# sheet metres.  The letter is ~5 mm (run 6cab17f6) and sits square to its
# face, level with its tip, so the leader reads as a viewing arrow.  Round-1
# farm review (dt-fab-4): the rear view (VIEW C) repeated the front view's
# outline and through bore, so it and its arrow are gone.
VIEW_LETTER_HEIGHT = 0.005
_VIEW_B_TIP_Y = _elevation_y((ADJUSTER_AXIS_HEIGHT + BLOCK_HEIGHT) / 2.0, FRONT_CENTER)
VIEW_B_ARROW = (
    (
        FRONT_CENTER[0] - BLOCK_X * _S / 2.0 - 0.013,
        _VIEW_B_TIP_Y + VIEW_LETTER_HEIGHT / 2.0,
    ),
    (FRONT_CENTER[0] - BLOCK_X * _S / 2.0, _VIEW_B_TIP_Y),
)
# The adjuster's hole callout is placed with the view row (ADJUSTER_CALLOUT_*,
# above).
# The pinch clearance callout stands above the right view.  At
# (x - 0.033, 0.1735) its text printed over the 6.0 (I31); raised to 0.178
# (287c) its leader still dropped almost straight down beside the pinch
# depth's hole-centre witness and crossed its dimension line.  r3 moved it
# far left, but the north-face witness rises from the hole's height, not the
# block's top (af13c8ff8 print), so that leader crossed it
# (leader-crosses-line).  At 2:1 the pinch depth's line spans far enough
# that a leader from the text's right end still crossed it, so the text
# reaches past the hole centre: its leader drops from the shoulder's right
# end to the hole, right of the hole-centre witness and the line's arrow.
# Blind machinist review of e2cfa0d03: 3.5 mm past the centre the leader
# fell 8 deg off vertical, on the hole's vertical centreline, and read as
# it.  The shoulder's right end now stands far enough right that the leader
# meets the rim PINCH_CLEARANCE_LEADER_ANGLE off vertical (17.4 mm past the
# centre); it still enters through the view's top, under a millimetre
# longer over the part than the hole's approach from the south face.
#
# Round 8 (fit-up route): the callout gains the joint drill's line over its
# own and "THIS JAW " in its own.  On the round-8 render (run
# 20261107T184300356Z) the callout glyphs printed 2.35 mm wide and its rows
# 5.7 mm apart; SolidWorks centres a callout's lines on the commanded point.
# The point rises half a row and slides left half the growth so the
# shoulder's right end, where the leader leaves, keeps its place.
CALLOUT_TEXT_GLYPH = 0.00235
CALLOUT_TEXT_ROW = 0.0057
_PINCH_CLEARANCE_GROWTH = 0.0196 + len("THIS JAW ") * CALLOUT_TEXT_GLYPH
PINCH_CLEARANCE_CALLOUT_EXTENT = (
    0.0150 + _PINCH_CLEARANCE_GROWTH / 2.0,
    0.0030 + CALLOUT_TEXT_ROW / 2.0,
    0.0166 + _PINCH_CLEARANCE_GROWTH / 2.0,
    0.0023 + CALLOUT_TEXT_ROW / 2.0,
)
_PINCH_CLEARANCE_SHOULDER_Y = 0.2013 - 0.0030
PINCH_CLEARANCE_CALLOUT_Y = _PINCH_CLEARANCE_SHOULDER_Y + PINCH_CLEARANCE_CALLOUT_EXTENT[1]
PINCH_CLEARANCE_LEADER_ANGLE = math.radians(35.0)
_PINCH_CLEARANCE_SHOULDER_DX = (
    _PINCH_CLEARANCE_SHOULDER_Y - _elevation_y(PINCH_HEIGHT, RIGHT_CENTER)
) * math.tan(PINCH_CLEARANCE_LEADER_ANGLE)
PINCH_CLEARANCE_CALLOUT_XY = (
    RIGHT_CENTER[0] + _PINCH_CLEARANCE_SHOULDER_DX - PINCH_CLEARANCE_CALLOUT_EXTENT[2],
    PINCH_CLEARANCE_CALLOUT_Y,
)
# The pinch thread callout stands above VIEW B, its shoulder's left end left
# of the hole so the leader drops steeply through the 2:1 view's top.  Its
# shoulder (0.0085 under its point) stands a text clearance over VIEW B's own
# depth value (round-1 farm review, dt-fab-4), whose line and arrows run
# right of the hole's centre.  Round 8: its longest line grows from "4-40 UNC
# - 2B TO SLOT" to "Ø .089 DRILL THRU BOTH JAWS", six glyphs; the point slides
# right half that so the shoulder's left end, where the leader leaves, keeps
# its place.
_PINCH_THREAD_GROWTH = 6 * CALLOUT_TEXT_GLYPH
PINCH_THREAD_CALLOUT_EXTENT = (
    0.0322 + _PINCH_THREAD_GROWTH / 2.0,
    0.0085,
    0.0310 + _PINCH_THREAD_GROWTH / 2.0,
    0.0078,
)
PINCH_THREAD_CALLOUT_XY = (
    LEFT_CENTER[0] + 0.015 + _PINCH_THREAD_GROWTH / 2.0,
    VIEW_B_DIMENSIONS["ViewBPinchDepth"][1]
    + VALUE_TEXT_HALF_HEIGHT
    + TEXT_CLEARANCE
    + ROUND_OUT
    + PINCH_THREAD_CALLOUT_EXTENT[1],
)
# The hold-down tap's callout stands above the bottom view, right of the
# FootTapX value and under the front view's foot finish, so its leader drops
# steeply (53 degrees) through the view's north edge.  With the tap 1.00
# toward -X (2026-09-29) a callout right of the view ran 5.4 mm longer over
# the part than the tap's shortest approach.  SolidWorks centres the block
# on the point, so the mate line (machinist review of c4c0e848a) dropped the
# shoulder 2.8 mm onto the north edge and the 4.875's witness; 10.0 mm over
# the edge the shoulder clears it by 1.65, as the two-line block's did, and
# the block's left end stands 8.5 mm right of the tap.
FOOT_TAP_CALLOUT_XY = (FOOT_TAP_CENTER[0] + 0.0373, _bottom_y(Z_NORTH) + 0.0100)
# The locating foot's finish symbol, on the front view's foot edge (round-1
# farm review, dt-fab-4: the seat that stands on MHA-DT-20).  The width
# dimension that once ran under that foot reads in the bottom view, so the
# leader reaches the foot edge-on with nothing dimensioned under it.  Blind
# machinist review of c289ee94: 11.5 mm under the foot leaves ~2.5 mm from
# the symbol's top to the foot.
FOOT_FINISH_DX = 0.034
FOOT_FINISH_DROP = 0.0115


def _adjuster_axis_keep() -> dict[str, tuple[float, float]]:
    """The adjuster-axis values, kept on the front view."""
    # r3: PassageCenter measures from the -X face (PASSAGE_CENTER_DATUM), so
    # its value stands over the front view's -X (left) half.
    return {
        "AxisHeight": (
            FRONT_CENTER[0] - AXIS_HEIGHT_LINE_DX,
            _elevation_y(ADJUSTER_AXIS_HEIGHT / 2.0, FRONT_CENTER),
        ),
        "PassageCenter": (
            FRONT_CENTER[0] - BLOCK_X * _S / 4.0,
            _elevation_y(BLOCK_HEIGHT, FRONT_CENTER) + PASSAGE_CENTER_RISE,
        ),
    }


ADJUSTER_CALLOUT_XY = (FRONT_CENTER[0] + ADJUSTER_CALLOUT_DX, ADJUSTER_CALLOUT_Y)


def _sheet_notes() -> tuple[tuple[str, float, float], ...]:
    """Every free note this sheet adds: (text, upper-left x, upper-left y)."""
    return (
        # The removed view's caption is its letter, centred under it.
        ("VIEW B", LEFT_CENTER[0] - VIEW_CAPTION_EXTENT[2] / 2.0, CAPTION_Y),
        # Review: named above the thread callout it describes.
        (BORE_FLAG_TEXT, FRONT_CENTER[0] + ADJUSTER_ENTRY_DX, ADJUSTER_ENTRY_Y),
        # The ream callout's SEE NOTE 1 (round 6, #2).
        (DOWEL_NOTE, *DOWEL_NOTE_XY),
    )


# ---------------------------------------------------------------------------
# Sheet ink audit
#
# Main's eye-pass of the I31 farm render (7ab69742b) found three collisions no
# gate saw: two plan values run into each other (value text on value text),
# the pinch clearance callout printed over the right view's pinch depth
# (callout text on value text), and the adjuster callout's THRU ALL / BOTH
# ENDS printed over the right view's north face (callout text on a view's
# model outline), its shoulder also crossed by an outside arrow (callout text
# on a dimension line).  The shared audit cannot see any of those classes:
# _drawing_common._dim_element boxes every display dimension and hole callout
# as a nominal 8 mm square with CollisionScope.NONE, _drawing_layout_check.
# _may_collide drops every pair holding a NONE element, and since ab28f4e49
# finalize_drawing no longer runs check_drawing_layout at all.
#
# So the sheet audits its own ink before it opens a document: every text
# block it places, boxed from where it places it and how large that text
# printed, against every other text block, every view's model silhouette, and
# the outside-arrow dimension lines that stand in the gaps between the views.
#
# Extents are (left, down, right, up) of the printed ink from the point the
# module commands, in sheet metres, measured on the I31 render's 300 dpi PNG
# (11.81 px/mm) by connected-component ink boxes and rounded outward to
# 0.1 mm.  A single value uses the module's value-text half sizes (4.6 x 1.9
# mm, over the 4.3 x 1.7 mm a four-character value measured).
_VALUE_EXTENT = (
    VALUE_TEXT_HALF_WIDTH,
    VALUE_TEXT_HALF_HEIGHT,
    VALUE_TEXT_HALF_WIDTH,
    VALUE_TEXT_HALF_HEIGHT,
)


def _value_extent(name: str, nominal: float) -> tuple[float, float, float, float]:
    """A value's ink from its point: the text the model prints at its
    places, centred the way SolidWorks centres the text.  An estimate from
    the glyph width until a render measures it."""
    half = len(printed_value_text(name, nominal)) * _VALUE_GLYPH_WIDTH / 2.0
    return (half, VALUE_TEXT_HALF_HEIGHT, half, VALUE_TEXT_HALF_HEIGHT)


def _value_and_rows_extent(
    name: str, nominal: float, text: str
) -> tuple[float, float, float, float]:
    """A value and its callout rows, centred together on the point."""
    half_width = max(_value_extent(name, nominal)[0], _callout_half_width(text))
    half_height = (1 + len(text.split("\n"))) * TEXT_ROW_HEIGHT / 2.0
    return (half_width, half_height, half_width, half_height)


_VALUE_EXTENTS = {
    # "5.9": three characters, 5.8 mm wide (I31's "6.0").
    "PinchDepthCenter": (0.0033, 0.0019, 0.0033, 0.0019),
    # The locating dowel's station and its ream's banded size with rows.
    "DowelX": DOWEL_X_EXTENT,
    "DowelHoleDia": DOWEL_HOLE_EXTENT,
    **{
        name: _value_extent(name, nominal)
        for name, nominal in (
            ("AxisHeight", ADJUSTER_AXIS_HEIGHT),
            ("PinchHeight", PINCH_HEIGHT),
            ("PassageCenter", BLOCK_X / 2.0),
            ("FootTapX", FOOT_TAP_X),
            ("FootTapZ", FOOT_TAP_Z),
        )
    },
    **{
        name: _value_and_rows_extent(name, nominal, text)
        for name, nominal, text in (
            ("Depth", BLOCK_Z, DIMENSION_CALLOUTS["Depth"]),
            ("Width", BLOCK_X, DIMENSION_CALLOUTS_ABOVE["Width"]),
            # "1.20" under its SLOT INTO BORE row.
            ("SlitW", SLIT_W, DIMENSION_CALLOUTS_ABOVE["SlitW"]),
        )
    },
}
# Hole callouts: every line plus the shoulder the leader leaves from
# (ADJUSTER_CALLOUT_EXTENT is with the adjuster callout's placement, the
# pinch callouts' with theirs).  r3: "Ø 3.26 ↓ 6.9" measured 28.5 mm of text
# (I31); "Ø 2.26 TO SLOT" on the same sheet 33.7 mm; "DRILL " added 19.6 mm,
# the 0.0196 in the pinch clearance callout's growth.
# The hold-down tap's lines (the tap drill and its depth, the thread and its
# full-thread depth, then the mate its stations locate on) plus the
# shoulder, measured on the c4c0e848a render: SolidWorks centres the block
# on the point, 7.8 mm over it to the shoulder 8.35 under it, and the mate
# line prints 57.6 mm wide.
FOOT_TAP_QUALIFIER = "LOCATES ON MHA-DT-20"
FOOT_TAP_CALLOUT_EXTENT = (0.0293, 0.0086, 0.0293, 0.0080)
# The locating dowel's ream callout (rule-23 retention, owner ruling
# 2026-11-07 (MHA-DT-00 rubric sample, PR #2248)).  Right of the bottom view
# the width's value and row (round-1 farm review, dt-fab-4) stand under the
# hold-down tap's callout, leaving 15 mm between them, too little for the
# ream's 21 mm block.  So the block stands right of the tap's callout, a text
# clearance past it, and its leader -- from the underline's left end --
# runs midway between the width's row and the tap callout's shoulder, under
# the view's +X face, to the rim right of the station's dowel witness: it
# crosses no text and no dimension line.  Placed once the texts it clears
# are boxed, hence after BOTTOM_KEEP.
DOWEL_HOLE_TEXT_LEFT = (
    FOOT_TAP_CALLOUT_XY[0] + FOOT_TAP_CALLOUT_EXTENT[2] + TEXT_CLEARANCE + ROUND_OUT
)
DOWEL_HOLE_LEADER_Y = (
    BOTTOM_KEEP["Width"][1]
    + _VALUE_EXTENTS["Width"][3]
    + FOOT_TAP_CALLOUT_XY[1]
    - FOOT_TAP_CALLOUT_EXTENT[1]
) / 2.0
BOTTOM_KEEP["DowelHoleDia"] = (
    DOWEL_HOLE_TEXT_LEFT + DOWEL_HOLE_EXTENT[0],
    DOWEL_HOLE_LEADER_Y + DOWEL_HOLE_EXTENT[1],
)
# The ream's numbered note (DOWEL_NOTE), by its upper-left corner.  The
# sheet's free-note text prints 2.64 mm a glyph and 4.05 mm a row (the old
# captions' measured extents).  The note is 79 mm wide: no gap beside the
# ream's block or under the view row holds it short of the title block, so
# it stands in the open field over the title block, right of VIEW B's
# height dimension and under the isometric, with room right and below for
# an estimate that prints wide or tall (draw_pd_transgear_knob_shaft's
# notes field).
NOTE_GLYPH_WIDTH = 0.00264
NOTE_ROW_HEIGHT = 0.00405
DOWEL_NOTE_XY = (0.300, 0.100)
DOWEL_NOTE_EXTENT = (
    0.0,
    len(DOWEL_NOTE.split("\n")) * NOTE_ROW_HEIGHT,
    max(len(line) for line in DOWEL_NOTE.split("\n")) * NOTE_GLYPH_WIDTH,
    0.0,
)
# Free notes are placed by their upper-left corner.
_NOTE_EXTENTS = {
    BORE_FLAG_TEXT: ADJUSTER_ENTRY_EXTENT,
    "VIEW B": VIEW_CAPTION_EXTENT,
    DOWEL_NOTE: DOWEL_NOTE_EXTENT,
}
# The locating-foot finish symbol: its leader lands midway along the right
# half of the foot edge; measured on the 287c render, its ink (shoulder,
# triangle, arm and "Ra 3.2") spans this far round the commanded point and
# its leader leaves from the shoulder's left end.
FOOT_FINISH_EXTENT = (0.0072, 0.0003, 0.0178, 0.0087)
FOOT_FINISH_LEADER_DX = -0.0067
# A view letter's ink from its note's upper-left corner (287c: B 48.3-52.8 x
# 150.7-155.5 mm); its leader leaves its right side level with the tip.
VIEW_LETTER_EXTENT = (0.0, 0.0053, 0.0051, 0.0)
VIEW_B_LEADER_DX = 0.0058

# Dimension ink, measured on the 287c render (run mha092-287c): a horizontal
# dimension's line prints 2.7-2.8 mm under its value's centre (4.5 mm under
# the 3.97's, whose deviations stack above it); a vertical one's value sits
# on its line.  Extension lines start 0.5-1.1 mm off the feature and run
# 1.0-1.3 mm past the line.  An outside arrow's arrowhead and tail run
# 6.3-6.4 mm past its extension line; an inside arrowhead is 3.4 mm long and
# about 0.6 mm across.  A vertical dimension with its arrows outside prints
# no line between them (the 12.0, 8.42, 10.7, 5.56, 3.50, 15.2 on 287c).
OUTSIDE_ARROW_RUN = 0.0064
HORIZONTAL_LINE_DROP = 0.0028
EXTENSION_GAP = 0.0005
EXTENSION_OVERSHOOT = 0.0013
LINE_PAST_TEXT = 0.0013
# A text block may not come nearer a view's model outline than this.
OUTLINE_CLEARANCE = 0.0005
# Main's eye-pass of 287c: an arrowhead or its tail within 0.2-0.4 mm of
# foreign text reads as part of it; _drawing_leaders keeps 2 mm between them.
ARROW_TEXT_CLEARANCE = _drawing_leaders.ARROW_TEXT_CLEARANCE
# Two dimensions' parallel lines nearer than this read as one: 287c ran the
# 3.97's line 0.52 mm off the 10.7's witness from the slot centre.  The 1.20
# slot's walls stand 0.9 mm either side of the 7.50's slot-centre witness,
# which reads as three lines.  Collinear lines (a shared witness) are one.
LINE_SEPARATION = 0.0008
COLLINEAR = 0.00005

Box = _drawing_leaders.Box
Point = _drawing_leaders.Point
Segment = _drawing_leaders.Segment


class ArrowSide(Enum):
    INSIDE = "inside"
    OUTSIDE = "outside"


class Axis(Enum):
    HORIZONTAL = "horizontal"  # measures along the sheet's x
    VERTICAL = "vertical"  # measures along the sheet's y


@dataclass(frozen=True)
class DimensionInk:
    """What one dimension prints besides its value, in sheet metres."""

    lines: tuple[Segment, ...] = ()  # dimension-line pieces and extension lines
    arrows: tuple[Segment, ...] = ()  # arrowheads, and an outside arrow's tail

    def segments(self) -> tuple[Segment, ...]:
        return (*self.lines, *self.arrows)


@dataclass(frozen=True)
class Leader:
    """A leader, from where it leaves its annotation to its arrow's tip."""

    start: Point
    tip: Point

    def segment(self) -> Segment:
        return (self.start, self.tip)

    def arrowhead(self) -> Segment:
        (x0, y0), (x1, y1) = self.start, self.tip
        length = math.hypot(x1 - x0, y1 - y0)
        run = min(ARROW_LENGTH, length) / length if length else 0.0
        return ((x1 - (x1 - x0) * run, y1 - (y1 - y0) * run), self.tip)


def _extent_box(
    point: tuple[float, float], extent: tuple[float, float, float, float]
) -> Box:
    left, down, right, up = extent
    return (point[0] - left, point[1] - down, point[0] + right, point[1] + up)


def _foot_finish_placement() -> tuple[Point, Point]:
    """(symbol point, leader tip) of the locating-foot finish."""
    foot = _elevation_y(0.0, FRONT_CENTER)
    return (
        (FRONT_CENTER[0] + FOOT_FINISH_DX, foot - FOOT_FINISH_DROP),
        (FRONT_CENTER[0] + BLOCK_X * _S / 4.0, foot),
    )


def _sheet_keeps() -> dict[str, tuple[float, float]]:
    """Every dimension's commanded text point, imported or driven."""
    return {
        **FRONT_KEEP,
        **_adjuster_axis_keep(),
        **TOP_KEEP,
        **RIGHT_KEEP,
        **LEFT_KEEP,
        **BOTTOM_KEEP,
        **VIEW_B_DIMENSIONS,
    }


def sheet_text_boxes() -> dict[str, Box]:
    """Every text block this module places, keyed by dimension or note name."""
    keeps = _sheet_keeps()
    keeps.update(TOP_TEXT_OFFSETS)
    boxes = {
        name: _extent_box(point, _VALUE_EXTENTS.get(name, _VALUE_EXTENT))
        for name, point in keeps.items()
    }
    boxes["adjuster callout"] = _extent_box(ADJUSTER_CALLOUT_XY, ADJUSTER_CALLOUT_EXTENT)
    boxes["pinch clearance callout"] = _extent_box(
        PINCH_CLEARANCE_CALLOUT_XY, PINCH_CLEARANCE_CALLOUT_EXTENT
    )
    boxes["pinch thread callout"] = _extent_box(
        PINCH_THREAD_CALLOUT_XY, PINCH_THREAD_CALLOUT_EXTENT
    )
    boxes["foot tap callout"] = _extent_box(FOOT_TAP_CALLOUT_XY, FOOT_TAP_CALLOUT_EXTENT)
    boxes["foot finish"] = _extent_box(_foot_finish_placement()[0], FOOT_FINISH_EXTENT)
    boxes["view B letter"] = _extent_box(VIEW_B_ARROW[0], VIEW_LETTER_EXTENT)
    for text, x, y in _sheet_notes():
        boxes[text] = _extent_box((x, y), _NOTE_EXTENTS[text])
    return boxes


def sheet_view_silhouettes() -> dict[str, Box]:
    """Each view's model outline: the prism prints a rectangle in every view."""
    foot = _elevation_y(0.0, FRONT_CENTER)
    top = _elevation_y(BLOCK_HEIGHT, FRONT_CENTER)
    half_x = BLOCK_X * _S / 2.0
    half_z = BLOCK_Z * _S / 2.0
    return {
        "front": (FRONT_CENTER[0] - half_x, foot, FRONT_CENTER[0] + half_x, top),
        "right": (RIGHT_CENTER[0] - half_z, foot, RIGHT_CENTER[0] + half_z, top),
        "view B": (LEFT_CENTER[0] - half_z, foot, LEFT_CENTER[0] + half_z, top),
        "plan": (
            TOP_CENTER[0] - half_x,
            _plan_y(Z_NORTH),
            TOP_CENTER[0] + half_x,
            _plan_y(Z_SOUTH),
        ),
        "bottom": (_BOTTOM_LEFT, _bottom_y(Z_SOUTH), _BOTTOM_RIGHT, _bottom_y(Z_NORTH)),
    }


def _dimension_ink(
    axis: Axis,
    ends: tuple[float, float],
    origins: tuple[float | None, float | None],
    line: float,
    arrows: ArrowSide,
    text: Box,
) -> DimensionInk:
    """A linear dimension's line, extension lines and arrows.

    ``ends`` are the two measured stations along ``axis``; ``origins`` the
    cross-axis coordinate each extension line leaves its feature from (None:
    the dimension line meets the feature itself); ``line`` the dimension
    line's cross-axis coordinate.  Built in (along, across) and mapped back.
    """

    def point(along: float, across: float) -> Point:
        return (along, across) if axis is Axis.HORIZONTAL else (across, along)

    lo, hi = sorted(ends)
    text_lo, text_hi = (text[0], text[2]) if axis is Axis.HORIZONTAL else (text[1], text[3])
    lines: list[Segment] = []
    for end, origin in zip(ends, origins):
        if origin is None:
            continue
        side = 1.0 if line >= origin else -1.0
        lines.append(
            (
                point(end, origin + side * EXTENSION_GAP),
                point(end, line + side * EXTENSION_OVERSHOOT),
            )
        )
    if arrows is ArrowSide.OUTSIDE:
        arrow_ink = [
            (point(lo, line), point(lo - OUTSIDE_ARROW_RUN, line)),
            (point(hi, line), point(hi + OUTSIDE_ARROW_RUN, line)),
        ]
    else:
        arrow_ink = [
            (point(lo, line), point(lo + ARROW_LENGTH, line)),
            (point(hi, line), point(hi - ARROW_LENGTH, line)),
        ]
    start = lo - (OUTSIDE_ARROW_RUN if arrows is ArrowSide.OUTSIDE else 0.0)
    stop = hi + (OUTSIDE_ARROW_RUN if arrows is ArrowSide.OUTSIDE else 0.0)
    if text_hi <= lo:
        start = min(start, text_lo - LINE_PAST_TEXT)
    if text_lo >= hi:
        stop = max(stop, text_hi + LINE_PAST_TEXT)
    if axis is Axis.HORIZONTAL:
        # The value stands above a continuous line.
        lines.append((point(start, line), point(stop, line)))
    elif arrows is ArrowSide.INSIDE:
        # The value breaks the line; outside arrows leave only their tails.
        lines.append((point(lo, line), point(max(lo, text_lo - LINE_PAST_TEXT), line)))
        lines.append((point(min(hi, text_hi + LINE_PAST_TEXT), line), point(hi, line)))
        if text_hi <= lo or text_lo >= hi:
            lines.append((point(start, line), point(stop, line)))
    return DimensionInk(tuple(lines), tuple(arrow_ink))


def sheet_dimension_ink() -> dict[str, DimensionInk]:
    """Every kept dimension's printed lines and arrows."""
    texts = sheet_text_boxes()
    keeps = _sheet_keeps()
    half_x = BLOCK_X * _S / 2.0
    # Each spec's side is the smart side it printed on 287c, unless the
    # module sets it.
    out, inside = ArrowSide.OUTSIDE, ArrowSide.INSIDE
    set_sides = {
        **{name: ArrowSide.OUTSIDE for name in ARROWS_OUTSIDE},
        **{name: ArrowSide.INSIDE for name in ARROWS_INSIDE},
    }
    h, v = Axis.HORIZONTAL, Axis.VERTICAL

    def drop(name: str) -> float:
        line_drop = TWO_ROW_LINE_DROP if name in DIMENSION_CALLOUTS_ABOVE else HORIZONTAL_LINE_DROP
        return keeps[name][1] - line_drop

    front_x = FRONT_CENTER[0]
    foot = _elevation_y(0.0, FRONT_CENTER)
    top = _elevation_y(BLOCK_HEIGHT, FRONT_CENTER)
    slit = SLIT_W * _S / 2.0
    north = _right_x(Z_NORTH)
    pinch_y = _elevation_y(PINCH_HEIGHT, RIGHT_CENTER)
    tap_x, tap_y = FOOT_TAP_CENTER
    bottom_south = _bottom_y(Z_SOUTH)
    specs = {
        "Width": (
            h,
            (_BOTTOM_LEFT, _BOTTOM_RIGHT),
            (bottom_south, bottom_south),
            drop("Width"),
            out,
        ),
        "BlockHt": (v, (foot, top), (front_x - half_x,) * 2, keeps["BlockHt"][0], inside),
        "SlitW": (h, (front_x - slit, front_x + slit), (top, top), drop("SlitW"), out),
        "AxisHeight": (
            v,
            (foot, _elevation_y(ADJUSTER_AXIS_HEIGHT, FRONT_CENTER)),
            (front_x - half_x,) * 2,
            keeps["AxisHeight"][0],
            inside,
        ),
        "PassageCenter": (
            h, (front_x - half_x, front_x), (top, top), drop("PassageCenter"), out
        ),
        "Depth": (
            v,
            (_plan_y(Z_NORTH), _plan_y(Z_SOUTH)),
            (_PLAN_RIGHT,) * 2,
            PLAN_DEPTH_LINE_X,
            inside,
        ),
        # The north-face witness leaves the face at the hole centre's height
        # (af13c8ff8 print: from 1.0 mm above it), not at the block's top.
        "PinchDepthCenter": (
            h,
            (north, _right_x(0.0)),
            (_elevation_y(PINCH_HEIGHT, RIGHT_CENTER), top - 0.002),
            drop("PinchDepthCenter"),
            out,
        ),
        # From the foot's south corner to the pinch hole's height, both
        # witnesses off the south face.
        "PinchHeight": (
            v,
            (foot, _elevation_y(PINCH_HEIGHT, RIGHT_CENTER)),
            (_right_x(Z_SOUTH),) * 2,
            keeps["PinchHeight"][0],
            inside,
        ),
        # VIEW B's driven stations: the north face's witness leaves its top
        # corner, the hole's its centre; the height's from the foot's north
        # corner and the hole's centre.
        "ViewBPinchDepth": (
            h,
            (LEFT_CENTER[0], _LEFT_NORTH_X),
            (pinch_y, top),
            drop("ViewBPinchDepth"),
            inside,
        ),
        "ViewBPinchHeight": (
            v,
            (foot, pinch_y),
            (_LEFT_NORTH_X, LEFT_CENTER[0]),
            keeps["ViewBPinchHeight"][0],
            inside,
        ),
    }
    ink = {
        name: _dimension_ink(
            axis, ends, origins, line, set_sides.get(name, arrows), texts[name]
        )
        for name, (axis, ends, origins, line, arrows) in specs.items()
    }
    # The offset shelf belongs to the same native dimension.  Keep its text
    # and connecting run in this recipe's ink model, not at the import seed.
    # Offset, the value no longer breaks the line: it runs whole between the
    # inside arrows, and the shelf's leader leaves its midpoint.
    depth = ink["Depth"]
    witnesses = depth.lines[:2]
    ink["Depth"] = DimensionInk(
        (
            *witnesses,
            (
                (PLAN_DEPTH_LINE_X, _plan_y(Z_NORTH)),
                (PLAN_DEPTH_LINE_X, _plan_y(Z_SOUTH)),
            ),
            (
                (PLAN_DEPTH_LINE_X, _plan_y(0.0)),
                (texts["Depth"][0], TOP_TEXT_OFFSETS["Depth"][1]),
            ),
        ),
        depth.arrows,
    )
    # The hold-down tap's stations: both witnesses of each leave the model's
    # reference line, which runs through the tap's centre.
    ink["FootTapX"] = _dimension_ink(
        h,
        (_BOTTOM_LEFT, tap_x),
        (tap_y, tap_y),
        drop("FootTapX"),
        set_sides["FootTapX"],
        texts["FootTapX"],
    )
    ink["FootTapZ"] = _dimension_ink(
        v,
        (tap_y, _bottom_y(Z_NORTH)),
        (tap_x, tap_x),
        keeps["FootTapZ"][0],
        set_sides["FootTapZ"],
        texts["FootTapZ"],
    )
    # The locating dowel's REF station from the -X face: the -X witness runs
    # down the face from the tap's line, the dowel's from its centre, the
    # value left of the span (rule-23 retention, owner ruling 2026-11-07
    # (MHA-DT-00 rubric sample, PR #2248); round 6, #9).
    ink["DowelX"] = _dimension_ink(
        h,
        (_BOTTOM_LEFT, DOWEL_CENTER[0]),
        (tap_y, tap_y),
        drop("DowelX"),
        set_sides["DowelX"],
        texts["DowelX"],
    )
    return ink


def _leader_to_circle(start: Point, center: Point, radius: float) -> Leader:
    dx, dy = start[0] - center[0], start[1] - center[1]
    length = math.hypot(dx, dy)
    return Leader(start, (center[0] + dx / length * radius, center[1] + dy / length * radius))


def _callout_leader(
    callout: Point, extent: tuple[float, float, float, float], center: Point, radius: float
) -> Leader:
    """A hole callout's leader leaves its shoulder's end nearer the hole."""
    left, down, right, _up = extent
    x = callout[0] + right if center[0] >= callout[0] else callout[0] - left
    return _leader_to_circle((x, callout[1] - down), center, radius)


def sheet_leaders() -> dict[str, Leader]:
    """Every leader this module places, keyed like its text block."""
    pinch_y = _elevation_y(PINCH_HEIGHT, RIGHT_CENTER)
    finish, finish_tip = _foot_finish_placement()
    view_b_text, view_b_tip = VIEW_B_ARROW
    return {
        "adjuster callout": _callout_leader(
            ADJUSTER_CALLOUT_XY,
            ADJUSTER_CALLOUT_EXTENT,
            (FRONT_CENTER[0], _elevation_y(ADJUSTER_AXIS_HEIGHT, FRONT_CENTER)),
            ADJUSTER_BORE_DIA * _S / 2.0,
        ),
        "pinch clearance callout": _callout_leader(
            PINCH_CLEARANCE_CALLOUT_XY,
            PINCH_CLEARANCE_CALLOUT_EXTENT,
            (_right_x(0.0), pinch_y),
            PINCH_CLEARANCE_DIA * _S / 2.0,
        ),
        "pinch thread callout": _callout_leader(
            PINCH_THREAD_CALLOUT_XY,
            PINCH_THREAD_CALLOUT_EXTENT,
            (LEFT_CENTER[0], pinch_y),
            PINCH_BORE_DIA * _S / 2.0,
        ),
        "foot tap callout": _callout_leader(
            FOOT_TAP_CALLOUT_XY,
            FOOT_TAP_CALLOUT_EXTENT,
            FOOT_TAP_CENTER,
            FOOT_BORE_DIA * _S / 2.0,
        ),
        # The ream's diameter: SolidWorks runs its leader from the near end of
        # the underline under its last row (r6 render) to the rim.
        "DowelHoleDia": _leader_to_circle(
            (
                BOTTOM_KEEP["DowelHoleDia"][0] - DOWEL_HOLE_EXTENT[0],
                BOTTOM_KEEP["DowelHoleDia"][1] - DOWEL_HOLE_EXTENT[1],
            ),
            DOWEL_CENTER,
            DOWEL_HOLE_DIA * _S / 2.0,
        ),
        "foot finish": Leader((finish[0] + FOOT_FINISH_LEADER_DX, finish[1]), finish_tip),
        "view B letter": Leader((view_b_text[0] + VIEW_B_LEADER_DX, view_b_tip[1]), view_b_tip),
    }


def _box_gap(a: Box, b: Box) -> float:
    """Air between two boxes along their clearer axis; negative when they overlap."""
    return max(b[0] - a[2], a[0] - b[2], b[1] - a[3], a[1] - b[3])


def _segment_meets_box(segment: Segment, box: Box) -> bool:
    """Whether any part of ``segment`` touches or lies inside ``box``."""
    return _drawing_leaders.distance_to_box(segment, box) == 0.0


def _parallel_gap(a: Segment, b: Segment) -> float | None:
    """Cross distance of two axis-aligned parallel segments that overlap along
    their length by more than a millimetre, else None."""
    for along, across in ((0, 1), (1, 0)):
        if a[0][across] != a[1][across] or b[0][across] != b[1][across]:
            continue
        lo = max(min(a[0][along], a[1][along]), min(b[0][along], b[1][along]))
        hi = min(max(a[0][along], a[1][along]), max(b[0][along], b[1][along]))
        if hi - lo > 0.001:
            return abs(a[0][across] - b[0][across])
    return None


def sheet_ink_collisions(
    texts: dict[str, Box],
    silhouettes: dict[str, Box],
    dimensions: dict[str, DimensionInk],
    leaders: dict[str, Leader],
    *,
    text_clearance: float = TEXT_CLEARANCE,
    outline_clearance: float = OUTLINE_CLEARANCE,
    arrow_clearance: float = ARROW_TEXT_CLEARANCE,
) -> list[str]:
    """Every collision among this sheet's text, outlines, lines and leaders.

    * text-on-text: two text blocks nearer than ``text_clearance``;
    * text-on-outline: a text block nearer a view's model outline than
      ``outline_clearance``;
    * text-on-line: another dimension's line, extension line or arrow, or
      another annotation's leader, running through a text block;
    * leader-on-dimension / leader-on-leader: a leader crossing a
      dimension's line, extension line or arrow, or another leader
      (``_drawing_leaders.leader_crossings``);
    * arrow-near-text: a dimension's arrow (head and outside tail) or a
      leader's arrowhead within ``arrow_clearance`` of foreign text ink
      (``_drawing_leaders.arrows_near_text``);
    * line-beside-line: two dimensions' parallel lines nearer than
      ``LINE_SEPARATION`` but not collinear.

    The geometry is ``_drawing_leaders``'; which ink to compare, and where it
    prints, is this sheet's.
    """
    findings: list[str] = []
    names = sorted(texts)
    for index, first in enumerate(names):
        for second in names[index + 1 :]:
            gap = _box_gap(texts[first], texts[second])
            if gap < text_clearance:
                findings.append(
                    f"text-on-text: {first!r} and {second!r} stand "
                    f"{gap * 1000.0:.2f} mm apart"
                )
    for name in names:
        box = texts[name]
        for view, outline in sorted(silhouettes.items()):
            gap = _box_gap(box, outline)
            if gap < outline_clearance:
                findings.append(
                    f"text-on-outline: {name!r} stands {gap * 1000.0:.2f} mm "
                    f"from the {view} outline"
                )
        for owner, ink in sorted(dimensions.items()):
            if owner != name and any(_segment_meets_box(s, box) for s in ink.segments()):
                findings.append(f"text-on-line: {owner}'s dimension line crosses {name!r}")
        for owner, leader in sorted(leaders.items()):
            if owner != name and _segment_meets_box(leader.segment(), box):
                findings.append(f"text-on-line: {owner}'s leader crosses {name!r}")
    shared = set(leaders) & set(dimensions)
    if shared:
        raise ValueError(f"leaders and dimensions share names: {sorted(shared)}")
    # Leaders first, so every pair a leader is in names the leader first.
    groups = {
        **{owner: [leader.segment()] for owner, leader in sorted(leaders.items())},
        **{owner: list(ink.segments()) for owner, ink in sorted(dimensions.items())},
    }
    for first, second in _drawing_leaders.leader_crossings(groups):
        if first not in leaders:
            continue  # two dimensions' lines may cross
        if second in leaders:
            findings.append(f"leader-on-leader: {first}'s and {second}'s leaders cross")
            continue
        findings.append(
            f"leader-on-dimension: {first}'s leader crosses {second}'s "
            "dimension or extension line"
        )
    owned = sorted(dimensions.items())
    for index, (first, ink_a) in enumerate(owned):
        for second, ink_b in owned[index + 1 :]:
            gaps = [
                gap
                for a in ink_a.segments()
                for b in ink_b.segments()
                if (gap := _parallel_gap(a, b)) is not None and COLLINEAR < gap < LINE_SEPARATION
            ]
            if gaps:
                findings.append(
                    f"line-beside-line: {first}'s and {second}'s lines run "
                    f"{min(gaps) * 1000.0:.2f} mm apart"
                )
    arrows = {
        **{owner: ink.arrows for owner, ink in sorted(dimensions.items())},
        **{owner: (leader.arrowhead(),) for owner, leader in sorted(leaders.items())},
    }
    for owner, name, gap in _drawing_leaders.arrows_near_text(
        arrows,
        {name: texts[name] for name in names},
        clearance=arrow_clearance,
        half_width=ARROW_HALF_WIDTH,
    ):
        findings.append(
            f"arrow-near-text: {owner}'s arrow stands {gap * 1000.0:.2f} mm from {name!r}"
        )
    return findings


def assert_sheet_ink_clear() -> None:
    """Refuse a placement whose own ink collides before any COM work is spent."""
    findings = sheet_ink_collisions(
        sheet_text_boxes(),
        sheet_view_silhouettes(),
        sheet_dimension_ink(),
        sheet_leaders(),
    )
    if findings:
        raise RuntimeError(
            "cone-tip-block sheet ink collides:\n"
            + "\n".join(f"  - {finding}" for finding in findings)
        )
    _telemetry.debug("cone-tip-block sheet ink clear")


def _foot_edge(adapter: Any, view: Any, *, min_span_mm: float = 13.9) -> Any:
    """Return the longest real edge on the block's locating foot plane."""
    candidates: list[tuple[float, Any]] = []
    for raw_edge in visible_view_entities(view, 1, label="tip-block foot edges"):
        edge = _early_bound(raw_edge, "IEdge")
        start = edge.GetStartVertex()
        end = edge.GetEndVertex()
        if start is None or end is None:
            continue
        p0 = tuple(float(value) * 1000.0 for value in _early_bound(start, "IVertex").GetPoint())
        p1 = tuple(float(value) * 1000.0 for value in _early_bound(end, "IVertex").GetPoint())
        if abs(p0[1]) > 0.01 or abs(p1[1]) > 0.01:
            continue
        span = max(abs(p1[0] - p0[0]), abs(p1[2] - p0[2]))
        candidates.append((span, edge))
    if not candidates:
        raise RuntimeError("view has no real edge on the locating foot plane")
    span, edge = max(candidates, key=lambda item: item[0])
    if span < min_span_mm:
        raise RuntimeError(f"locating-foot edge span is only {span:.3f} mm")
    return edge


def _set_arrow_sides(
    adapter: Any, annotations: list[Any], sides: dict[str, int]
) -> None:
    """Stand each named dimension's arrows on its swDimensionArrowsSide_e side."""
    remaining = dict(sides)
    for raw in annotations:
        annotation = _early_bound(raw, "IAnnotation")
        name = dimension_name(adapter, annotation)
        if name not in remaining:
            continue
        side = remaining.pop(name)
        display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
        display.ArrowSide = side
        if int(display.ArrowSide) != side:
            raise RuntimeError(f"{name} did not keep its arrows on side {side}")
    if remaining:
        raise RuntimeError(f"no dimension to set arrow sides: {sorted(remaining)}")


def _circle_entity(
    adapter: Any,
    view: Any,
    *,
    radius_mm: float,
    center_y_mm: float,
    label: str,
) -> Any:
    """Resolve a real circular edge by model size and vertical station."""
    candidates: list[tuple[float, float, Any]] = []
    for raw_edge in visible_view_entities(view, 1, label=f"{label} circles"):
        edge = _early_bound(raw_edge, "IEdge")
        curve = edge.GetCurve()
        if curve is None:
            continue
        curve = _early_bound(curve, "ICurve")
        if not curve.IsCircle():
            continue
        params = tuple(float(value) * 1000.0 for value in curve.CircleParams)
        candidates.append((params[6], params[1], edge))
    if not candidates:
        raise RuntimeError(f"{label} view has no visible circular model edges")
    radius, center_y, edge = min(
        candidates,
        key=lambda item: abs(item[0] - radius_mm) + abs(item[1] - center_y_mm),
    )
    if abs(radius - radius_mm) > 0.01 or abs(center_y - center_y_mm) > 0.01:
        raise RuntimeError(
            f"no {label} circle matches radius {radius_mm:.3f} mm at "
            f"height {center_y_mm:.3f} mm; nearest is "
            f"R{radius:.3f} at {center_y:.3f} mm"
        )
    return edge


def _view_b_face_edge(adapter: Any, view: Any, *, along: int, label: str) -> Any:
    """VIEW B's visible straight edge on the -X face running along model
    axis ``along`` (1: the north face's vertical edge; 2: the foot edge).

    Picked by model geometry, not a sheet hit-test: round 2's coordinate pick
    beside the hole's centre mark left three entities selected (farm run
    20261107T104940656Z).  The north edge lies on z = Z_NORTH, the foot edge
    on y = 0; of the coincident projections the -X face's (least x) is the
    one VIEW B looks at.
    """
    candidates: list[tuple[float, float, Any]] = []
    for raw_edge in visible_view_entities(view, 1, label=f"{label} edges"):
        edge = _early_bound(raw_edge, "IEdge")
        start, end = edge.GetStartVertex(), edge.GetEndVertex()
        if start is None or end is None:
            continue
        p0 = tuple(float(v) * 1000.0 for v in _early_bound(start, "IVertex").GetPoint())
        p1 = tuple(float(v) * 1000.0 for v in _early_bound(end, "IVertex").GetPoint())
        across = [axis for axis in range(3) if axis != along]
        if any(abs(p0[axis] - p1[axis]) > 0.01 for axis in across):
            continue
        on_plane = abs(p0[2] - Z_NORTH) < 0.01 if along == 1 else abs(p0[1]) < 0.01
        if not on_plane:
            continue
        candidates.append((abs(p1[along] - p0[along]), p0[0], edge))
    full = BLOCK_HEIGHT if along == 1 else BLOCK_Z
    spanning = [item for item in candidates if abs(item[0] - full) < 0.01]
    if not spanning:
        raise RuntimeError(
            f"{label}: no visible {full:.2f} mm edge; spans "
            f"{sorted(round(item[0], 3) for item in candidates)!r}"
        )
    return min(spanning, key=lambda item: item[1])[2]


def _check_face_attachment(adapter: Any, dimension: Any, face_edge: Any, label: str) -> None:
    """The dimension hangs on the face edge it was given plus one other entity.

    The hole end is a point pick, which may resolve to the drill circle or the
    concentric cosmetic-thread circle; both share the centre, so the value
    readback guards that end and only the face edge's identity is checked.
    """
    display = _early_bound(dimension, "IDisplayDimension")
    annotation = _early_bound(display.GetAnnotation(), "IAnnotation")
    attached = [item for item in (annotation.GetAttachedEntities3() or ()) if item is not None]
    types = tuple(int(t) for t in (annotation.GetAttachedEntityTypes() or ()))
    faces = [item for item in attached if _is_same_attachment(adapter, item, face_edge, "EDGE")]
    if bool(annotation.IsDangling()) or len(attached) != 2 or len(faces) != 1:
        raise RuntimeError(
            f"{label} is not attached to its face edge and one hole entity: "
            f"attachments={len(attached)}, face matches={len(faces)}, types={types}"
        )
    _telemetry.debug(f"{label}: attachment types {types}")


def _add_view_b_pinch_dimensions(adapter: Any, view: Any, thread_edge: Any) -> None:
    """Locate VIEW B's far-jaw thread in its own view (VIEW_B_DIMENSIONS).

    Each runs from a face edge (picked by entity) to the thread's circle,
    which SolidWorks dimensions at its centre.  The circle is picked by sheet
    point on its rim at 45 deg, clear of the 0/90/180/270 deg centre-mark arms
    (none exist yet: this runs before the centre marks), so
    add_edge_dimension's entity pick never meets the round-2 failure (farm
    run 20261107T104940656Z: the entity pick left three entities selected).
    """
    curve = _early_bound(_early_bound(thread_edge, "IEdge").GetCurve(), "ICurve")
    params = tuple(float(value) for value in curve.CircleParams)
    centre = model_point_in_view(adapter, view, params[:3], label="VIEW B thread centre")
    rim_offset = params[6] * 1000.0 * _S / math.sqrt(2.0)
    rim_xy = (centre[0] + rim_offset, centre[1] + rim_offset)
    north = _view_b_face_edge(adapter, view, along=1, label="VIEW B north face")
    foot = _view_b_face_edge(adapter, view, along=2, label="VIEW B foot")
    for name, face_edge, face_xy, orientation, expected_mm in (
        (
            "ViewBPinchDepth",
            north,
            (_LEFT_NORTH_X, _elevation_y(BLOCK_HEIGHT / 2.0, LEFT_CENTER)),
            "horizontal",
            BLOCK_Z / 2.0,
        ),
        (
            "ViewBPinchHeight",
            foot,
            (LEFT_CENTER[0] - BLOCK_Z * _S / 4.0, _elevation_y(0.0, LEFT_CENTER)),
            "vertical",
            PINCH_HEIGHT,
        ),
    ):
        label = f"VIEW B {name}"
        dimension = add_edge_dimension(
            adapter,
            view,
            p0=face_xy,
            p1=rim_xy,
            text_xy=VIEW_B_DIMENSIONS[name],
            label=label,
            orientation=orientation,
            entities=(face_edge, None),
        )
        assert_dimension_measures(adapter, dimension, expected_mm=expected_mm, label=label)
        _check_face_attachment(adapter, dimension, face_edge, label)
        display = _early_bound(dimension, "IDisplayDimension")
        places = DRAWING_REFERENCE_PRECISION[name]
        display.SetPrecision3(DRAWING_REFERENCE_PRECISION[name], -1, -1, -1)
        if int(display.GetPrimaryPrecision2()) != places:
            raise RuntimeError(f"{label} did not keep {places} decimal places")
        display.ArrowSide = _DIM_ARROWS_INSIDE
        if int(display.ArrowSide) != _DIM_ARROWS_INSIDE:
            raise RuntimeError(f"{label} did not keep its arrows inside")
    rebuild_drawing(adapter, label="VIEW B pinch stations")


# Round-8 farm review (dt-fab-4, rules 4/19): the clearance and the tap are
# one feature on one axis.  Their .19/1.85 stations stay loose; the fit-up
# route at both callouts holds the axes together: one Ø tap-drill hole drilled
# through both jaws in one pass, the near jaw opened to clearance up to the
# slot, the far jaw tapped up to the slot.  Both callouts name the joint
# drill by the same words, and each keeps to two lines (rule 7).
PINCH_JOINT_DRILL_TEXT = "DRILL THRU BOTH JAWS"
PINCH_TAP_EXTENT_TEXT = "TAP TO SLOT"
# Hole-callout order: drill line, then thread line.  VIEW B's own driven
# stations locate the far-jaw thread (_add_view_b_pinch_dimensions).
_PINCH_THREAD_NATIVE_TOKENS = frozenset(
    {"<hw-thrutapdrldia>", "<hw-threaddesc>", "<hw-threadclass>"}
)


def _pinch_thread_callout_definitions(
    definitions: dict[int, str],
) -> dict[int, str]:
    """Replace only the native extent words; keep every associative variable."""
    if set(definitions) != {5, 6, 7, 8}:
        raise RuntimeError(f"unexpected pinch callout definition parts: {definitions!r}")
    original = "\n".join(definitions.values())
    missing = _PINCH_THREAD_NATIVE_TOKENS - {
        token for token in _PINCH_THREAD_NATIVE_TOKENS if token in original
    }
    if missing or original.count("<hw-thru>") != 2:
        raise RuntimeError(
            "unexpected native pinch-thread callout definition: "
            f"missing={sorted(missing)!r}, definitions={definitions!r}"
        )
    # The tap drill's line is the joint drill both callouts name; the
    # thread's line says TAP (rule 12).
    updated = {
        part: text.replace(
            "<hw-thru>",
            PINCH_TAP_EXTENT_TEXT
            if "<hw-threadclass>" in text
            else PINCH_JOINT_DRILL_TEXT,
        )
        for part, text in definitions.items()
    }
    thread_parts = [part for part, text in updated.items() if "<hw-threadclass>" in text]
    if len(thread_parts) != 1:
        raise RuntimeError(f"pinch thread line is not in one callout part: {updated!r}")
    rewritten = "\n".join(updated.values())
    if (
        "THRU ALL" in rewritten
        or "<hw-thru>" in rewritten
        or rewritten.count(PINCH_TAP_EXTENT_TEXT) != 1
        or rewritten.count(PINCH_JOINT_DRILL_TEXT) != 1
        or any(token not in rewritten for token in _PINCH_THREAD_NATIVE_TOKENS)
    ):
        raise RuntimeError(f"pinch-thread callout rewrite lost semantics: {updated!r}")
    return updated


# r3 blocker: the near jaw is drilled full diameter until it opens into the
# slit, so the native blind depth ("<HOLE-DEPTH> <hw-depth>") becomes the
# instruction; the diameter stays the Hole Wizard variable.  Round 8: the
# joint drill's line stands over it, its Ø the tap drill's (the clearance
# hole's Hole Wizard has no tap-drill variable, so it prints from the spec).
PINCH_CLEARANCE_EXTENT_TEXT = "DRILL THIS JAW TO SLOT"
_BLIND_DEPTH_TOKENS = re.compile(r"<HOLE-DEPTH>\s*<hw-depth>")


def _pinch_joint_drill_line() -> str:
    return (
        f"<MOD-DIAM>{length_text(PINCH_BORE_DIA, HOLE_CALLOUT_PLACES)} "
        f"{PINCH_JOINT_DRILL_TEXT}"
    )


def _pinch_clearance_callout_definitions(definitions: dict[int, str]) -> dict[int, str]:
    """Put the joint drill over the clearance line and swap the one native
    blind-depth pair for DRILL THIS JAW TO SLOT, loudly."""
    if set(definitions) != {5, 6, 7, 8}:
        raise RuntimeError(f"unexpected pinch clearance callout parts: {definitions!r}")
    hits = {
        part: len(_BLIND_DEPTH_TOKENS.findall(text)) for part, text in definitions.items()
    }
    if sorted(hits.values()) != [0, 0, 0, 1]:
        raise RuntimeError(
            f"pinch clearance callout has no single blind depth to replace: {definitions!r}"
        )
    updated = {
        part: (
            f"{_pinch_joint_drill_line()}\n"
            f"{_BLIND_DEPTH_TOKENS.sub(PINCH_CLEARANCE_EXTENT_TEXT, text)}"
            if hits[part]
            else text
        )
        for part, text in definitions.items()
    }
    rewritten = "\n".join(updated.values())
    if "<hw-depth>" in rewritten or "<HOLE-DEPTH>" in rewritten:
        raise RuntimeError(f"pinch clearance rewrite left a depth: {updated!r}")
    return updated


def _pinch_clearance_callout_resolved(resolved_parts: dict[int, str]) -> bool:
    """The joint drill's line, then the clearance line, in one part."""
    joint = f"{length_text(PINCH_BORE_DIA, HOLE_CALLOUT_PLACES)} {PINCH_JOINT_DRILL_TEXT}"
    clearance = (
        f"{length_text(PINCH_CLEARANCE_DIA, HOLE_CALLOUT_PLACES)} "
        f"{PINCH_CLEARANCE_EXTENT_TEXT}"
    )
    parts = [text for text in resolved_parts.values() if text.strip()]
    if len(parts) != 1 or "<HOLE-DEPTH>" in parts[0]:
        return False
    lines = [line.rstrip() for line in parts[0].strip().split("\n")]
    return len(lines) == 2 and lines[0].endswith(joint) and lines[1].endswith(clearance)


def _set_pinch_clearance_callout_text(display: Any) -> None:
    """State the joint drill and the clearance extent without severing the
    diameter's Hole Wizard variable."""
    definitions = {part: str(display.GetText(part) or "") for part in (5, 6, 7, 8)}
    updated = _pinch_clearance_callout_definitions(definitions)
    for definition_part, writable_part in ((5, 1), (6, 2), (7, 3), (8, 4)):
        if updated[definition_part] != definitions[definition_part]:
            display.SetText(writable_part, updated[definition_part])
    persisted = {part: str(display.GetText(part) or "") for part in (5, 6, 7, 8)}
    resolved_parts = {part: str(display.GetText(part) or "") for part in (1, 2, 3, 4)}
    if persisted != updated or not _pinch_clearance_callout_resolved(resolved_parts):
        raise RuntimeError(
            "pinch clearance fit-up lines did not persist: "
            f"definitions={persisted!r}, resolved={resolved_parts!r}"
        )


def _pinch_thread_callout_resolved(resolved_parts: dict[int, str]) -> bool:
    """Whether the resolved callout keeps the joint drill and the tap extent.

    GetText(1..4) resolves definition parts 5..8 in part order, which is not
    the sheet's line order: af561fa7 printed part 7 (the tap drill) above
    part 5 (the thread).  So the check is per part, not by string position.
    """
    joined = "\n".join(resolved_parts.values())
    thread = [text for text in resolved_parts.values() if "UNC" in text]
    drill = [text for text in resolved_parts.values() if text.strip() and "UNC" not in text]
    return (
        "THRU ALL" not in joined
        and len(thread) == 1
        and thread[0].rstrip().endswith(PINCH_TAP_EXTENT_TEXT)
        and len(drill) == 1
        and drill[0].rstrip().endswith(
            f"{length_text(PINCH_BORE_DIA, HOLE_CALLOUT_PLACES)} {PINCH_JOINT_DRILL_TEXT}"
        )
    )


# drawing-guidelines.md rule 12 (hole and slot callouts say what to do): a blind tap states its full-thread depth, and here its
# tap-drill depth too, which sets the lead the tap needs past the thread.
# Both print at FOOT_DEPTH_PLACES, the general band the spec's reach and lead
# stacks read, as does the tap drill's size: every Hole Wizard callout prints
# three inch places (#290).
HOLE_CALLOUT_PLACES = 3
FOOT_TAP_DEPTH_PRECISION = {
    "hw-tapdrldia": HOLE_CALLOUT_PLACES,
    "hw-threaddepth": FOOT_DEPTH_PLACES,
    "hw-tapdrldepth": FOOT_DEPTH_PLACES,
}
THRU_TAP_DRILL_PRECISION = {"hw-thrutapdrldia": HOLE_CALLOUT_PLACES}
PINCH_CLEARANCE_PRECISION = {"hw-diam": HOLE_CALLOUT_PLACES}


def _states_depth(text: str, depth_mm: float) -> bool:
    printed = re.escape(length_text(depth_mm, FOOT_DEPTH_PLACES))
    return re.search(rf"(?<![\d.]){printed}(?!\d)", text) is not None


def _foot_tap_callout_resolved(resolved_parts: dict[int, str]) -> bool:
    """Whether the hold-down tap's callout reads as a blind UNC-2B tap: the
    thread's line carries its full-thread depth, the tap drill's line its
    depth, nothing says THRU, and the thread's part ends on the mate."""
    thread_desc = f"{HOLDDOWN_THREAD.lstrip('#')} UNC"
    lines = [text for text in resolved_parts.values() if text.strip()]
    thread = [text for text in lines if thread_desc in text]
    drill = [text for text in lines if thread_desc not in text]
    return (
        not any("THRU" in text for text in lines)
        and len(thread) == 1
        and "2B" in thread[0]
        and _states_depth(thread[0], FOOT_THREAD_DEPTH)
        and thread[0].rstrip().endswith(f"\n{FOOT_TAP_QUALIFIER}")
        and any(_states_depth(text, FOOT_DEPTH) for text in drill)
    )


def _foot_tap_callout_definitions(definitions: dict[int, str]) -> dict[int, str]:
    """Append the mate the tap's .XXX stations locate on (rule 4) to the one
    compartment holding the thread, under its native thread line."""
    if set(definitions) != {5, 6, 7, 8}:
        raise RuntimeError(f"unexpected foot tap callout parts: {definitions!r}")
    thread_parts = [part for part, text in definitions.items() if "<hw-threadclass>" in text]
    if len(thread_parts) != 1:
        raise RuntimeError(f"foot tap thread line is not in one callout part: {definitions!r}")
    updated = dict(definitions)
    part = thread_parts[0]
    updated[part] = f"{updated[part].rstrip()}\n{FOOT_TAP_QUALIFIER}"
    return updated


def _set_foot_tap_callout_text(display: Any) -> None:
    """Name the mate under the native thread line, keeping every variable."""
    definitions = {part: str(display.GetText(part) or "") for part in (5, 6, 7, 8)}
    updated = _foot_tap_callout_definitions(definitions)
    for definition_part, writable_part in ((5, 1), (6, 2), (7, 3), (8, 4)):
        if updated[definition_part] != definitions[definition_part]:
            display.SetText(writable_part, updated[definition_part])
    persisted = {part: str(display.GetText(part) or "") for part in (5, 6, 7, 8)}
    if persisted != updated:
        raise RuntimeError(
            f"foot tap mate line did not persist: definitions={persisted!r}"
        )


def _check_foot_tap_callout(display: Any) -> None:
    resolved = {part: str(display.GetText(part) or "") for part in (1, 2, 3, 4)}
    if not _foot_tap_callout_resolved(resolved):
        raise RuntimeError(
            f"hold-down foot tap callout does not state its depths and mate: {resolved!r}"
        )


# E11/W1: the through thread's two countersinks are one chamfer feature; the
# callout names them under the thread line, so the hole reads in one place,
# with the countersink symbol (<HOLE-SINK>, as draw_fr_top_frame's callouts)
# and the ASME Ø X angle order.
_CSK_DIA_TEXT = length_text(ADJUSTER_BORE_DIA + 2.0 * ADJUSTER_CSK, HOLE_CALLOUT_PLACES)
_CSK_TAIL = " X 90\u00b0 BOTH ENDS"
ADJUSTER_CSK_QUALIFIER = f"<HOLE-SINK><MOD-DIAM>{_CSK_DIA_TEXT}{_CSK_TAIL}"


def _adjuster_callout_definitions(definitions: dict[int, str]) -> dict[int, str]:
    """Append the countersink line to the one compartment holding the thread."""
    if set(definitions) != {5, 6, 7, 8}:
        raise RuntimeError(f"unexpected adjuster callout parts: {definitions!r}")
    thread_parts = [part for part, text in definitions.items() if "<hw-threadclass>" in text]
    if len(thread_parts) != 1:
        raise RuntimeError(f"adjuster thread line is not in one callout part: {definitions!r}")
    updated = dict(definitions)
    part = thread_parts[0]
    updated[part] = f"{updated[part].rstrip()}\n{ADJUSTER_CSK_QUALIFIER}"
    return updated


def _set_adjuster_callout_text(display: Any) -> None:
    """Name both countersinks under the native through-thread line."""
    definitions = {part: str(display.GetText(part) or "") for part in (5, 6, 7, 8)}
    updated = _adjuster_callout_definitions(definitions)
    for definition_part, writable_part in ((5, 1), (6, 2), (7, 3), (8, 4)):
        if updated[definition_part] != definitions[definition_part]:
            display.SetText(writable_part, updated[definition_part])
    persisted = {part: str(display.GetText(part) or "") for part in (5, 6, 7, 8)}
    resolved = {part: str(display.GetText(part) or "") for part in (1, 2, 3, 4)}
    thread = [text for text in resolved.values() if "UNF" in text]
    # The resolved text may print the symbol tags as glyphs, so the check is
    # on the countersink line's value and tail.
    csk_line = thread[0].rstrip().rsplit("\n", 1)[-1] if len(thread) == 1 else ""
    if (
        persisted != updated
        or len(thread) != 1
        or not csk_line.endswith(f"{_CSK_DIA_TEXT}{_CSK_TAIL}")
    ):
        raise RuntimeError(
            "adjuster countersink line did not persist: "
            f"definitions={persisted!r}, resolved={resolved!r}"
        )


def _set_pinch_thread_callout_text(display: Any) -> None:
    """State the final two-jaw extent without severing Hole Wizard variables."""
    definitions = {
        part: str(display.GetText(part) or "")
        for part in (5, 6, 7, 8)
    }
    updated = _pinch_thread_callout_definitions(definitions)
    for definition_part, writable_part in ((5, 1), (6, 2), (7, 3), (8, 4)):
        if updated[definition_part] != definitions[definition_part]:
            display.SetText(writable_part, updated[definition_part])
    persisted = {
        part: str(display.GetText(part) or "")
        for part in (5, 6, 7, 8)
    }
    resolved_parts = {
        part: str(display.GetText(part) or "") for part in (1, 2, 3, 4)
    }
    resolved = "\n".join(resolved_parts.values())
    if persisted != updated or not _pinch_thread_callout_resolved(resolved_parts):
        raise RuntimeError(
            "pinch-thread native extent override did not persist: "
            f"definitions={persisted!r}, resolved={resolved!r}"
        )




def _audit_isometric_annotation_provenance(adapter: Any, view: Any) -> int:
    """Prove every isometric annotation is native cosmetic-thread ink (to hide)."""
    annotation_types = [
        int(_early_bound(raw, "IAnnotation").GetType())
        for raw in (_early_bound(view, "IView").GetAnnotations() or ())
    ]
    if not annotation_types or any(kind != 1 for kind in annotation_types):
        raise RuntimeError(
            "cone-tip isometric annotation provenance changed: "
            f"types={annotation_types!r}"
        )
    _telemetry.debug(
        f"cone-tip isometric: {len(annotation_types)} cosmetic-thread annotations"
    )
    return len(annotation_types)


_COSMETIC_THREAD_LAYER = "CONE-TIP-THREADS-HIDDEN"


def _hide_cosmetic_threads(adapter: Any, view: Any, *, label: str) -> int:
    """Keep cosmetic-thread annotation ink out of a view (the pictorial)."""
    draw = adapter.currentModel
    manager = _early_bound(draw.GetLayerManager(), "ILayerMgr")
    layer = manager.GetLayer(_COSMETIC_THREAD_LAYER)
    if layer is None:
        if int(
            manager.AddLayer(
                _COSMETIC_THREAD_LAYER,
                "cosmetic thread ink hidden in the cone-tip pictorial",
                0,
                0,
                0,
            )
        ) != 1:
            raise RuntimeError("failed to add cone-tip thread layer")
        layer = manager.GetLayer(_COSMETIC_THREAD_LAYER)
    layer = _early_bound(layer, "ILayer")
    layer.Visible = False
    if bool(layer.Visible) or bool(layer.Printable):
        raise RuntimeError("cone-tip thread layer is not hidden")
    hidden = 0
    for raw_annotation in _early_bound(view, "IView").GetAnnotations() or ():
        annotation = _early_bound(raw_annotation, "IAnnotation")
        if int(annotation.GetType()) != 1:  # swCosmeticThread
            continue
        annotation.Layer = _COSMETIC_THREAD_LAYER
        if str(annotation.Layer or "") != _COSMETIC_THREAD_LAYER:
            raise RuntimeError(f"cone-tip {label} cosmetic thread refused hidden layer")
        hidden += 1
    if not hidden:
        raise RuntimeError(f"cone-tip {label} has no cosmetic thread to hide")
    rebuild_drawing(adapter, label=f"hide {label} cosmetic threads")
    return hidden




async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open cone-tip-block source", await adapter.open_model(str(SOURCE)))
    source_model = adapter.currentModel
    read_required_properties(
        source_model,
        (
            "Number",
            "Revision",
            "Title",
            "Material Specification",
            "Finish",
            "Quantity",
        ),
        required=(
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
        ),
    )
    drawing_model, _sheet = new_project_drawing(
        adapter,
        property_view=PART_STEM,
        scale=SHEET_SCALE,
        layout=SPEC.layout,
        unit=part_drawing_unit("dt-cone-tip-block"),
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Cone Tip Block Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "cone tip block; adjuster carrier; split pinch clamp",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=SHEET_SCALE)
    top = place_view(adapter, str(SOURCE), "*Top", *TOP_CENTER, scale=SHEET_SCALE)
    right = place_view(adapter, str(SOURCE), "*Right", *RIGHT_CENTER, scale=SHEET_SCALE)
    left = place_view(adapter, str(SOURCE), "*Left", *LEFT_CENTER, scale=SHEET_SCALE)
    assert_sheet_ink_clear()
    bottom = place_view(adapter, str(SOURCE), "*Bottom", *BOTTOM_CENTER, scale=SHEET_SCALE)
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=SHEET_SCALE)
    for view in (front, top, right, left, bottom, iso):
        set_hidden_lines_removed(adapter, view)

    adjuster_edge = _circle_entity(
        adapter,
        front,
        radius_mm=ADJUSTER_BORE_DIA / 2.0,
        center_y_mm=ADJUSTER_AXIS_HEIGHT,
        label="through adjuster thread",
    )
    pinch_clearance_edge = _circle_entity(
        adapter,
        right,
        radius_mm=PINCH_CLEARANCE_DIA / 2.0,
        center_y_mm=PINCH_HEIGHT,
        label="pinch entry-jaw clearance",
    )
    pinch_thread_edge = _circle_entity(
        adapter,
        left,
        radius_mm=PINCH_BORE_DIA / 2.0,
        center_y_mm=PINCH_HEIGHT,
        label="pinch opposite-jaw thread",
    )
    foot_tap_edge = _circle_entity(
        adapter,
        bottom,
        radius_mm=FOOT_BORE_DIA / 2.0,
        center_y_mm=0.0,
        label="hold-down foot tap",
    )
    # Views that dimension part-hidden reference sketches (995a7c94) import
    # through the opt-in helper, which shows each owner sketch in that view
    # only: the front view's AxisHeight/PassageCenter, the right view's pinch
    # stations and the bottom view's tap stations.  The plan's depth is the
    # block's own edge, and VIEW B keeps no model dimension (its stations are
    # driven, _add_view_b_pinch_dimensions).
    front_annotations = hidden_sketches.curate_view_dimensions(
        adapter,
        front,
        keep={**FRONT_KEEP, **_adjuster_axis_keep()},
        view_label="adjuster entry elevation",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    top_annotations = curate_view_dimensions(
        adapter,
        top,
        keep=TOP_KEEP,
        view_label="plan",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    right_annotations = hidden_sketches.curate_view_dimensions(
        adapter,
        right,
        keep=RIGHT_KEEP,
        view_label="pinch clearance entry",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    left_annotations = curate_view_dimensions(
        adapter,
        left,
        keep=LEFT_KEEP,
        view_label="pinch threaded entry",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    bottom_annotations = hidden_sketches.curate_view_dimensions(
        adapter,
        bottom,
        keep=BOTTOM_KEEP,
        view_label="hold-down tap",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    annotations = [
        *front_annotations,
        *top_annotations,
        *right_annotations,
        *left_annotations,
        *bottom_annotations,
    ]
    set_dimension_callouts(adapter, annotations, DIMENSION_CALLOUTS)
    set_dimension_callouts(adapter, annotations, DIMENSION_CALLOUTS_ABOVE, location="above")
    # The locating dowel's station from the -X face is a reference (round 6,
    # #9): the hole is match-drilled from MHA-DT-20, so it carries no band.
    dowel_station = [
        item for item in bottom_annotations if dimension_name(adapter, item) == "DowelX"
    ]
    if len(dowel_station) != 1:
        raise RuntimeError("expected one locating dowel station on the bottom view")
    set_reference_dimension(
        adapter, dowel_station[0], label="locating dowel reference station"
    )
    _set_arrow_sides(
        adapter,
        annotations,
        {
            **{name: _DIM_ARROWS_OUTSIDE for name in ARROWS_OUTSIDE},
            **{name: _DIM_ARROWS_INSIDE for name in ARROWS_INSIDE},
        },
    )
    offset_dimension_text(adapter, top_annotations, TOP_TEXT_OFFSETS)
    assert_imported_precision(adapter, annotations, DRAWING_PRECISION_BY_NAME)

    # VIEW B's stations go on before any centre mark exists, so neither pick
    # can meet a centre-mark line.
    _add_view_b_pinch_dimensions(adapter, left, pinch_thread_edge)
    for view, label in (
        (front, "adjuster entry elevation"),
        (right, "pinch clearance entry"),
        (left, "pinch threaded entry"),
        (bottom, "hold-down tap"),
    ):
        if not auto_center_marks(adapter, view, holes=True, size=0.0025):
            raise RuntimeError(f"failed to add centre marks to {label} view")

    adjuster_callout = add_native_hole_callout(
        adapter,
        front,
        edge=adjuster_edge,
        callout_xy=ADJUSTER_CALLOUT_XY,
        label="through adjuster thread",
    )
    # These four render-time precision writes are the declared exception
    # RV-01 in cad/config/parts/dt-cone-tip-block.yaml (Owner ruling
    # 2026-11-08 (Pedro), #2144 item 1.2): a part-authored precision does not
    # reach the callout (run 20261102T230110877Z).
    set_hole_callout_precision(
        adjuster_callout, THRU_TAP_DRILL_PRECISION, label="through adjuster thread"
    )
    _set_adjuster_callout_text(adjuster_callout)
    pinch_clearance_callout = add_native_hole_callout(
        adapter,
        right,
        edge=pinch_clearance_edge,
        callout_xy=PINCH_CLEARANCE_CALLOUT_XY,
        label="pinch entry-jaw clearance",
    )
    set_hole_callout_precision(
        pinch_clearance_callout, PINCH_CLEARANCE_PRECISION, label="pinch entry-jaw clearance"
    )
    _set_pinch_clearance_callout_text(pinch_clearance_callout)
    pinch_thread_callout = add_native_hole_callout(
        adapter,
        left,
        edge=pinch_thread_edge,
        callout_xy=PINCH_THREAD_CALLOUT_XY,
        label="pinch opposite-jaw thread",
    )
    set_hole_callout_precision(
        pinch_thread_callout, THRU_TAP_DRILL_PRECISION, label="pinch opposite-jaw thread"
    )
    _set_pinch_thread_callout_text(pinch_thread_callout)
    foot_tap_callout = add_native_hole_callout(
        adapter,
        bottom,
        edge=foot_tap_edge,
        callout_xy=FOOT_TAP_CALLOUT_XY,
        label="hold-down foot tap",
    )
    _set_foot_tap_callout_text(foot_tap_callout)
    set_hole_callout_precision(
        foot_tap_callout, FOOT_TAP_DEPTH_PRECISION, label="hold-down foot tap sizes"
    )
    _check_foot_tap_callout(foot_tap_callout)
    _audit_isometric_annotation_provenance(adapter, iso)
    # Main eye-pass af561fa7: the shaded pictorial carries no thread ink.
    _hide_cosmetic_threads(adapter, iso, label="isometric")

    for text, x, y in _sheet_notes():
        if add_note(adapter, text, x, y) is None:
            raise RuntimeError(f"failed to add the {text.lower()!r} note")
    # C1 verdict (2026-09-23): the native projected-view arrow is not
    # switchable through the documented API -- IProjectionArrow.Visible is
    # get-only and no document preference or IView member sets it; only the
    # PropertyManager "Arrow" box does.  Untested: an IProjectionArrow.SetLabel
    # side effect, a PropertyManager RunCommand route.  So the removed view
    # is named by a letter note whose straight leader is the viewing arrow.
    text_xy, tip_xy = VIEW_B_ARROW
    note = add_leader_note(
        adapter,
        "B",
        text_xy=text_xy,
        attach_xy=tip_xy,
        view=front,
        label="view B viewing arrow",
    )
    # add_note leaves text at the document height; size the letter here
    # (the add_surface_finish char_height recipe) and prove the leader
    # tip did not move with it.
    annotation = _early_bound(note.GetAnnotation(), "IAnnotation")
    text_format = annotation.GetTextFormat(0)
    if text_format is None:
        raise RuntimeError("view B arrow note has no text format")
    text_format.CharHeight = VIEW_LETTER_HEIGHT
    if not annotation.SetTextFormat(0, False, text_format):
        raise RuntimeError("failed to size the view B arrow letter")
    rebuild_drawing(adapter, label="view B arrow letter")
    points = list(annotation.GetLeaderPointsAtIndex(0) or ())
    if len(points) < 6 or math.dist((points[-3], points[-2]), tip_xy) > 0.001:
        raise RuntimeError("view B arrow tip moved when its letter was sized")

    foot_edge = _foot_edge(adapter, front)
    # Onto the foot edge itself, midway along its right half: at the corner
    # vertex (run 6cab17f6) it could name the side face as well as the seat.
    foot_symbol, foot_right = _foot_finish_placement()
    foot_finish = add_surface_finish(
        adapter,
        front,
        edge_entity=foot_edge,
        symbol_xy=foot_symbol,
        leader_attach_xy=foot_right,
        control=surface_finish_by_key(SURFACE_FINISHES, "foot_seat"),
        char_height=0.003,
        label="swing-platform locating foot seat",
    )
    finish_annotation = _early_bound(foot_finish.GetAnnotation(), "IAnnotation")
    if int(finish_annotation.GetLeaderCount()) != 1:
        raise RuntimeError("foot-seat finish does not have exactly one leader")
    leader_values = tuple(
        float(value) for value in finish_annotation.GetLeaderPointsAtIndex(0)
    )
    leader_points = tuple(
        leader_values[index : index + 3] for index in range(0, len(leader_values), 3)
    )
    # Sheet x/y only: an attached leader end carries the edge's model depth
    # in z.  The old z == 0 test matched the free sheet point that the
    # leader setter left once it had detached the symbol.
    if not any(
        abs(point[0] - foot_right[0]) < 1e-6
        and abs(point[1] - foot_right[1]) < 1e-6
        for point in leader_points
    ):
        raise RuntimeError(
            "foot-seat finish leader missed the verified bottom-edge endpoint: "
            f"expected={foot_right!r}, points={leader_points!r}"
        )

    # Annotation insertion can regenerate a view with inherited display state;
    # every manufacturing view is explicitly HLR at export.
    for view in (front, top, right, left, bottom):
        set_hidden_lines_removed(adapter, view)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Cone Tip Block Manufacturing Drawing",
        scale=SHEET_SCALE,
        layout=SPEC.layout,
        # SolidWorks auto-inserts one descriptive "... Tapped Hole" note per
        # tapped Hole Wizard hole it shows: the adjuster's and the hold-down
        # foot tap's (run 66084ed9 counted the same two).
        redundant_note_substrings=("Tapped Hole",),
        expected_redundant_notes=2,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[PART_STEM])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
