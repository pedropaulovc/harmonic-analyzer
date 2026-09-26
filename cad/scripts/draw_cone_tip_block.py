r"""Create the simplicity-policy machinist drawing for the cone tip block."""
# TODO(#910): stray sketch lines + 12.0/20.8 and 5.56/1.53 crowding -- sheet ships as-is, reassess later.

from __future__ import annotations

import argparse
import math
import re
import sys
from dataclasses import dataclass
from enum import Enum
from typing import Any

import _drawing_hidden_sketches as hidden_sketches
import _drawing_leaders
import _telemetry
from _common import CAD_ROOT, _early_bound, check, run_build
from _drawing_common import (
    DrawingOutputs,
    add_leader_note,
    add_native_hole_callout,
    add_surface_finish,
    assert_imported_precision,
    create_section_view,
    curate_view_dimensions,
    dimension_name,
    finalize_drawing,
    model_point_in_view,
    new_project_drawing,
    read_required_properties,
    rebuild_drawing,
    set_dimension_callouts,
    set_hidden_lines_removed,
    stamp_drawing_summary,
    visible_view_entities,
)
from _drawing_registry import DRAWINGS_BY_NAME
from _surface_finish import surface_finish_by_key
from cone_tip_block_spec import (
    ADJUSTER_AXIS_HEIGHT,
    ADJUSTER_BORE_DIA,
    ADJUSTER_CSK,
    BLOCK_HEIGHT,
    BLOCK_X,
    BLOCK_Z,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    FLANGE_LEN,
    FLANGE_SLOT_NORTH_Z,
    FLANGE_SLOT_SOUTH_Z,
    FLANGE_SLOT_W,
    FLANGE_SLOT_Z,
    FLANGE_T,
    HEEL_RELIEF_DEPTH,
    HEEL_RELIEF_HEIGHT,
    PINCH_BORE_DIA,
    PINCH_CLEARANCE_DIA,
    PINCH_HEIGHT,
    SLIT_DEPTH,
    SLIT_W,
    SURFACE_FINISHES,
)
from solidworks_mcp.adapters.com_variant import double_array
from solidworks_mcp.adapters.solidworks.drawing import (
    add_note,
    auto_center_marks,
    place_view,
    view_name,
)


SPEC = DRAWINGS_BY_NAME["cone_tip_block"]
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

# I31: the foot flange runs the block 20.8 further south, 32.8 long in all;
# at 2:1 the plan and the side views no longer fit between the front view's
# dimensions and the sheet edge, so the sheet drops to 3:2.
SHEET_SCALE = (3.0, 2.0)
_S = SHEET_SCALE[0] / SHEET_SCALE[1] / 1000.0
FRONT_CENTER = (0.072, 0.129)
TOP_CENTER = (FRONT_CENTER[0], 0.222)
# The right view and the removed views B and C stand on the front view's
# projection row; their x follows from the adjuster callout between the front
# and right views (RIGHT_CENTER, below).
SECTION_CENTER = (0.190, 0.225)
ISO_CENTER = (0.350, 0.215)
# A view centres on the part's box.  Along the cone axis that box runs from
# the north face to the flange's south end, so the block's own centre (the
# model origin) sits Z_MID north of each view's centre.
Z_NORTH = BLOCK_Z / 2.0
Z_SOUTH = -BLOCK_Z / 2.0 - FLANGE_LEN
Z_MID = (Z_NORTH + Z_SOUTH) / 2.0
FLANGE_SLOT_CENTER_Z = -BLOCK_Z / 2.0 - FLANGE_SLOT_Z
FLANGE_SLOT_NORTH_CENTER_Z = -BLOCK_Z / 2.0 - FLANGE_SLOT_NORTH_Z
FLANGE_SLOT_SOUTH_CENTER_Z = -BLOCK_Z / 2.0 - FLANGE_SLOT_SOUTH_Z


def _elevation_y(model_y: float, center: tuple[float, float]) -> float:
    return center[1] + (model_y - BLOCK_HEIGHT / 2.0) * _S


def _plan_y(model_z: float) -> float:
    """Sheet y of a model station in the plan (*Top shows +Z, north, down)."""
    return TOP_CENTER[1] - (model_z - Z_MID) * _S


def _right_x(model_z: float) -> float:
    """Sheet x of a model station in the right view (north on the left)."""
    return RIGHT_CENTER[0] - (model_z - Z_MID) * _S


# Imported value text measured on run 5637ac42: a four-character value
# ("1.20", "7.50") prints ~9.1 mm wide, a three-character one ("6.0", "7.5")
# ~6.4 mm, and a native arrowhead ~3.4 mm long.  Main's eye-pass of that run
# found values printed across their own witness lines and a hole centreline
# (d976281d ruling: no text on a line), so the values below are placed from
# these sizes rather than centred on a feature.
VALUE_TEXT_HALF_WIDTH = 0.0046
VALUE_TEXT_HALF_HEIGHT = 0.0019
ARROW_LENGTH = 0.0034
# An inside arrowhead is about 0.6 mm across (287c).
ARROW_HALF_WIDTH = 0.0003
TEXT_CLEARANCE = 0.0015
# Clearances are rounded outward by this much, so a placement derived to one
# does not stand exactly on the audit's limit.
ROUND_OUT = 0.0001

# The adjuster's hole callout stands between the adjuster elevation and the
# right view.  #946 / MHA-092: at 9a0f50b1c it stood below-right of the hole
# and its leader climbed ~28 mm over the front view to the rim, ~16 mm
# further than the hole's approach from the right face, reading as an edge of
# the part.  The short way in, from the right face, is SLOT DEPTH's: its
# lower extension line leaves the slit floor 0.97 mm under the hole centre
# and runs out to its value, so the callout stands under that line, its top
# an arrow clearance (plus half an arrowhead) below it, clear of the 15.2's
# lower arrow.  Its leader leaves the shoulder's left end at
# ADJUSTER_LEADER_ANGLE: at 45 deg the run over the part is 4.4 mm longer
# than the hole's approach, past Main's ~4 mm brief (swing's RD2 fix,
# 4dda16fd5, left 3.8); at 40 deg it is 3.2.  Every degree shallower slides
# the right-hand views ~0.6 mm further right.  Hole callouts' extents (every
# line plus the shoulder) are measured on the I31 render like the rest of the
# sheet's ink (see "Sheet ink audit").
ADJUSTER_CALLOUT_EXTENT = (0.0295, 0.0086, 0.0278, 0.0078)
ADJUSTER_LEADER_ANGLE = math.radians(40.0)
ADJUSTER_FLOOR_GAP = _drawing_leaders.ARROW_TEXT_CLEARANCE + ARROW_HALF_WIDTH + ROUND_OUT
ADJUSTER_SHOULDER_Y = (
    _elevation_y(BLOCK_HEIGHT - SLIT_DEPTH, FRONT_CENTER)
    - ADJUSTER_FLOOR_GAP
    - ADJUSTER_CALLOUT_EXTENT[3]
    - ADJUSTER_CALLOUT_EXTENT[1]
)
_ADJUSTER_SHOULDER_DX = (
    _elevation_y(ADJUSTER_AXIS_HEIGHT, FRONT_CENTER) - ADJUSTER_SHOULDER_Y
) / math.tan(ADJUSTER_LEADER_ANGLE)
ADJUSTER_CALLOUT_DX = _ADJUSTER_SHOULDER_DX + ADJUSTER_CALLOUT_EXTENT[0]
ADJUSTER_CALLOUT_Y = ADJUSTER_SHOULDER_Y + ADJUSTER_CALLOUT_EXTENT[1]
# ADJUSTER ENTRY names the elevation from under the callout's shoulder (the
# floor line leaves no room over it), a text clearance down, left-aligned.
ADJUSTER_ENTRY_DX = _ADJUSTER_SHOULDER_DX
ADJUSTER_ENTRY_Y = ADJUSTER_SHOULDER_Y - TEXT_CLEARANCE - ROUND_OUT
# The right view's north face stands a text clearance past the callout's right
# end.  (I31, 7ab69742b: at x 0.166 the callout's longest line ran over that
# face; the right view slid 5 mm then, the removed views with it.)  The
# removed views B and C keep the row's 72 mm pitch, so the gaps to their
# right keep their measured air.
_RIGHT_NORTH_FACE_X = (
    FRONT_CENTER[0] + ADJUSTER_CALLOUT_DX + ADJUSTER_CALLOUT_EXTENT[2] + TEXT_CLEARANCE + ROUND_OUT
)
VIEW_ROW_PITCH = 0.072
RIGHT_CENTER = (_RIGHT_NORTH_FACE_X + (Z_NORTH - Z_MID) * _S, FRONT_CENTER[1])
LEFT_CENTER = (RIGHT_CENTER[0] + VIEW_ROW_PITCH, FRONT_CENTER[1])
BACK_CENTER = (RIGHT_CENTER[0] + 2.0 * VIEW_ROW_PITCH, FRONT_CENTER[1])
# The 1.2 slot prints 1.8 mm wide, narrower than its value, so the arrows
# stand outside the slot walls and the text sits right of the right arrow's
# tail on the extended dimension line.  Right, because on the adjuster
# elevation PassageCenter's span from the -X face (r3) occupies the slot's
# left; 14.5 mm over the top, so its line clears the pinch clearance
# callout below it by 1.9 mm.
SLIT_TEXT_RISE = 0.0145
SLIT_TEXT_OFFSET = (
    SLIT_W * _S / 2.0 + ARROW_LENGTH + TEXT_CLEARANCE + VALUE_TEXT_HALF_WIDTH
)
FRONT_KEEP = {
    "Width": (FRONT_CENTER[0], _elevation_y(0.0, FRONT_CENTER) - 0.012),
    "BlockHt": (FRONT_CENTER[0] - 0.033, FRONT_CENTER[1]),
    "SlitW": (
        FRONT_CENTER[0] + SLIT_TEXT_OFFSET,
        _elevation_y(BLOCK_HEIGHT, FRONT_CENTER) + SLIT_TEXT_RISE,
    ),
}
# PassageCenter stands above SlitW on the adjuster elevation; the plan's
# north edge is the ceiling for both.
PASSAGE_CENTER_RISE = 0.024
# swDimensionArrowsSide_e, set rather than left to the document's smart
# arrows: swDimArrowsOutside = 1, swDimArrowsInside = 0.
ARROWS_OUTSIDE = ("SlitW", "HeelReliefDepth", "FlangeSlotW", "FlangeSlotNorthZ")
# Main eye-pass of 287c: the 15.2's smart arrows stood outside, and its lower
# tail ran down to 0.4 mm over ADJUSTER ENTRY.  Its 22.8 mm span holds the
# two-line value and both arrows inside.
ARROWS_INSIDE = ("SlitDepth", "FlangeSlotSouthZ", "PinchHeight")
_DIM_ARROWS_OUTSIDE = 1
_DIM_ARROWS_INSIDE = 0
# The plan.  Left of it, stepping out from the part: the slot's two arc
# centres, each baselined from the body's south face (r3, option A; the 6.5
# arrows outside, its span being shorter than its value and two arrows), then
# the block depth and the flange length chained on one line.  All three
# leave the south face's -X corner, one shared witness.  Right of it: the
# slot width's value (arrows outside) level with the slot's midpoint.  Above
# the flange's south end, higher than the A-A cutting-plane arrow and its
# letter at that end: the slot's location from the -X face (r3, the
# PassageCenter datum), its witness rising from the flange's south-west
# corner.
_PLAN_LEFT = TOP_CENTER[0] - BLOCK_X * _S / 2.0
_PLAN_RIGHT = TOP_CENTER[0] + BLOCK_X * _S / 2.0
# Each line stands one value-width plus air outside the last: a vertical
# value sits on its line, and two values on neighbouring lines keep 1.8 mm.
PLAN_BASELINE_STEP = 0.011
FLANGE_SLOT_NORTH_LINE_X = _PLAN_LEFT - PLAN_BASELINE_STEP
FLANGE_SLOT_SOUTH_LINE_X = _PLAN_LEFT - 2.0 * PLAN_BASELINE_STEP
PLAN_CHAIN_X = _PLAN_LEFT - 3.0 * PLAN_BASELINE_STEP
# The 3.97's line prints 4.5 mm (3 model mm at 3:2) under its value's centre.
# With no witness leaving the slot's right side any more (r3), the value
# stands 3 mm south of the slot's middle so its line runs across that middle,
# 6.3 mm from either arc centre's witness on the left.
FLANGE_SLOT_W_Z = FLANGE_SLOT_CENTER_Z - 3.0
FLANGE_SLOT_X_RISE = 0.016
TOP_KEEP = {
    "Depth": (PLAN_CHAIN_X, _plan_y(0.0)),
    "FlangeLen": (PLAN_CHAIN_X, _plan_y((-BLOCK_Z / 2.0 + Z_SOUTH) / 2.0)),
    "FlangeSlotNorthZ": (
        FLANGE_SLOT_NORTH_LINE_X,
        _plan_y((-BLOCK_Z / 2.0 + FLANGE_SLOT_NORTH_CENTER_Z) / 2.0),
    ),
    "FlangeSlotSouthZ": (
        FLANGE_SLOT_SOUTH_LINE_X,
        _plan_y((-BLOCK_Z / 2.0 + FLANGE_SLOT_SOUTH_CENTER_Z) / 2.0),
    ),
    # 287c: centred 9.5 mm right of the plan, the value-and-deviation pair
    # printed "3.97" 0.2 mm off the plan's right edge.  Its value now starts
    # 2 mm clear of it.
    "FlangeSlotW": (
        _PLAN_RIGHT + 0.0094 + 0.002,
        _plan_y(FLANGE_SLOT_W_Z),
    ),
    "FlangeSlotX": (
        TOP_CENTER[0] - BLOCK_X * _S / 4.0,
        _plan_y(Z_SOUTH) + FLANGE_SLOT_X_RISE,
    ),
}
# r3: section A-A carries no dimension; the pinch-hole height moved to the
# right view, where the hole is drilled and seen end-on.
SECTION_KEEP: dict[str, tuple[float, float]] = {}
# The half-block station below runs from the north face to the pinch-hole
# centre, so its value sits midway along its span.  Centred on the hole (run
# 5637ac42), the witness and centreline ended in the decimal point; at +0.003
# its dimension line printed on the block's top edge.
#
# I31 heel relief: the right view has north on the left, so the step is its
# lower-left notch.  The depth's dimension line runs through the notch's air
# half way up (at 3:2 the notch is only 8.3 mm tall), arrows outside, its value left of the north face;
# the height stands further left, so the depth's value sits between the
# height's two extension lines.  The flange thickness stands past the
# flange's south end, on the right, and (r3) the pinch-hole height from the
# foot one value-width further out: its witness leaves the foot at the
# flange's south-end corner, shared with the thickness's.
_RIGHT_NORTH_X = _right_x(Z_NORTH)
HEEL_DEPTH_TEXT_X = _RIGHT_NORTH_X - ARROW_LENGTH - TEXT_CLEARANCE - VALUE_TEXT_HALF_WIDTH
HEEL_HEIGHT_LINE_X = HEEL_DEPTH_TEXT_X - VALUE_TEXT_HALF_WIDTH - 0.008
FLANGE_T_LINE_X = _right_x(Z_SOUTH) + 0.010
PINCH_HEIGHT_LINE_X = FLANGE_T_LINE_X + PLAN_BASELINE_STEP
RIGHT_KEEP = {
    "PinchDepthCenter": (
        _right_x(BLOCK_Z / 4.0),
        _elevation_y(BLOCK_HEIGHT, RIGHT_CENTER) + 0.007,
    ),
    "HeelReliefDepth": (
        HEEL_DEPTH_TEXT_X,
        _elevation_y(HEEL_RELIEF_HEIGHT / 2.0, RIGHT_CENTER),
    ),
    "HeelReliefHt": (
        HEEL_HEIGHT_LINE_X,
        _elevation_y(HEEL_RELIEF_HEIGHT / 2.0, RIGHT_CENTER),
    ),
    "FlangeT": (
        FLANGE_T_LINE_X,
        _elevation_y(FLANGE_T / 2.0, RIGHT_CENTER),
    ),
    "PinchHeight": (
        PINCH_HEIGHT_LINE_X,
        _elevation_y(PINCH_HEIGHT / 2.0, RIGHT_CENTER),
    ),
}
LEFT_KEEP: dict[str, tuple[float, float]] = {}
# The bottom-row captions sit just under the views' feet.
CAPTION_Y = _elevation_y(0.0, FRONT_CENTER) - 0.004
# A centreline runs a short way past the part it marks.
AXIS_OVERRUN = 0.002
# Review C1: the left and rear views sit right of the right view, out of
# third-angle order, so each is a removed view named by a letter arrow on the
# view that shows the face it looks at.  VIEW B looks at the -X (pinch-thread)
# face: the arrow meets the front view's left edge between the 32.3 and
# 46.8 extension lines.  VIEW C looks at the -Z (shaft-entry) face, from
# the plan's upper (south) end, left of the A-A cutting-plane stem.  Each pair
# is (note upper-left, leader tip), sheet metres.
# The letters match the A-A cutting-plane letters (~5 mm, run 6cab17f6), and
# each note sits square to its face so the leader reads as a viewing arrow:
# B level with its tip, C centred above its tip.
VIEW_LETTER_HEIGHT = 0.005
_VIEW_B_TIP_Y = _elevation_y((ADJUSTER_AXIS_HEIGHT + BLOCK_HEIGHT) / 2.0, FRONT_CENTER)
VIEW_B_ARROW = (
    (
        FRONT_CENTER[0] - BLOCK_X * _S / 2.0 - 0.013,
        _VIEW_B_TIP_Y + VIEW_LETTER_HEIGHT / 2.0,
    ),
    (FRONT_CENTER[0] - BLOCK_X * _S / 2.0, _VIEW_B_TIP_Y),
)
# 287c: at +0.013 the letter C stood 0.5 mm under the 7.50's left arrow tail.
VIEW_C_ARROW = (
    (TOP_CENTER[0] - 0.006 - 0.0018, _plan_y(Z_SOUTH) + 0.0105),
    (TOP_CENTER[0] - 0.006, _plan_y(Z_SOUTH)),
)
DIMENSION_CALLOUTS = {
    "SlitDepth": "SLOT DEPTH",
}

# The adjuster's hole callout is placed with the view row (ADJUSTER_CALLOUT_*,
# above).
# The pinch clearance callout stands above and left of the right view.  At
# (x - 0.033, 0.1735) its text printed over the 6.0 (I31); raised to 0.178
# (287c) its leader still dropped almost straight down beside the 6.0's
# hole-centre witness and crossed the 6.0's dimension line.  25 mm further
# left the leader runs down to the hole at about 35 degrees, passing 3.5 mm
# outside the 6.0's left arrow tail and under its north-face witness, into
# the view across its north face.  r3: DRILL TO SLOT prints about 20 mm wider
# than the blind depth did (PINCH_CLEARANCE_CALLOUT_EXTENT, an estimate), so
# the callout steps 2.5 mm further left, its left end 1 mm right of the
# adjuster elevation's right edge at W 17, above that view and under the slit
# width's value, and drops 4.5 mm so its leader leaves the shoulder low
# enough to pass outside the 6.0's arrow tail.
PINCH_CLEARANCE_CALLOUT_XY = (RIGHT_CENTER[0] - 0.0605, 0.1715)
PINCH_THREAD_CALLOUT_XY = (LEFT_CENTER[0] + 0.016, 0.190)
ROTATED_NOTE_XY = (SECTION_CENTER[0] - 0.015, 0.195)
# The locating foot's finish symbol, on the elevation named here.  On the
# front view (287c) its "Ra 3.2" stood 0.2 mm off the 5.56's lower arrow, and
# no leader can reach that foot without crossing the 15.0's extension or
# dimension line.  VIEW C shows the same foot edge-on with nothing
# dimensioned under it.
FOOT_FINISH_CENTER = BACK_CENTER
FOOT_FINISH_DX = 0.034
FOOT_FINISH_DROP = 0.013


def _adjuster_axis_keep(
    adjuster_center: tuple[float, float],
) -> dict[str, tuple[float, float]]:
    """The adjuster-axis values, kept on whichever elevation shows its entry."""
    # r3: PassageCenter measures from the -X face (PASSAGE_CENTER_DATUM), so
    # its value stands over the -X half of whichever elevation shows it.
    minus_x_side = -1.0 if adjuster_center == FRONT_CENTER else 1.0
    return {
        "AxisHeight": (
            adjuster_center[0] - 0.045,
            _elevation_y(ADJUSTER_AXIS_HEIGHT / 2.0, adjuster_center),
        ),
        "PassageCenter": (
            adjuster_center[0] + minus_x_side * BLOCK_X * _S / 4.0,
            _elevation_y(BLOCK_HEIGHT, adjuster_center) + PASSAGE_CENTER_RISE,
        ),
        "SlitDepth": (
            adjuster_center[0] + 0.043,
            _elevation_y(BLOCK_HEIGHT - SLIT_DEPTH / 2.0, adjuster_center),
        ),
    }


def _adjuster_callout_xy(adjuster_center: tuple[float, float]) -> tuple[float, float]:
    return (adjuster_center[0] + ADJUSTER_CALLOUT_DX, ADJUSTER_CALLOUT_Y)


def _sheet_notes(
    adjuster_center: tuple[float, float],
) -> tuple[tuple[str, float, float], ...]:
    """Every free note this sheet adds: (text, upper-left x, upper-left y)."""
    # The through thread shows the same rim from both ends; VIEW C (the
    # opposite elevation) is the shaft's entry.
    shaft_entry_center = BACK_CENTER if adjuster_center == FRONT_CENTER else FRONT_CENTER
    return (
        ("VIEW C\nSHAFT ENTRY", shaft_entry_center[0] - 0.021, CAPTION_Y),
        ("RIGHT VIEW\nPINCH CLEARANCE ENTRY", RIGHT_CENTER[0] - 0.026, CAPTION_Y),
        ("VIEW B\nPINCH THREAD ENTRY", LEFT_CENTER[0] - 0.023, CAPTION_Y),
        # Review: named with the thread callout it describes (under it since
        # #946; SLOT DEPTH's floor line runs over it).
        (
            "ADJUSTER ENTRY",
            adjuster_center[0] + ADJUSTER_ENTRY_DX,
            ADJUSTER_ENTRY_Y,
        ),
        ("ROTATED 90°", *ROTATED_NOTE_XY),
    )


# ---------------------------------------------------------------------------
# Sheet ink audit
#
# Main's eye-pass of the I31 farm render (7ab69742b) found three collisions no
# gate saw: "20.8" run into "8.42" on the plan (value text on value text), the
# pinch clearance callout printed over the right view's "6.0" (callout text on
# value text), and the adjuster callout's THRU ALL / BOTH ENDS printed over the
# right view's north face (callout text on a view's model outline), its
# shoulder also crossed by the 5.56 heel height's outside arrow (callout text
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
_VALUE_EXTENTS = {
    # "3.97" with its stacked +0.1 / 0.0 deviations to the right; SolidWorks
    # centres the pair, so the value starts 9.3 mm left of its point (287c).
    "FlangeSlotW": (0.0094, 0.0040, 0.0097, 0.0045),
    # "6.0": three characters, 5.8 mm wide (I31).
    "PinchDepthCenter": (0.0033, 0.0019, 0.0033, 0.0019),
    # "15.2" over its SLOT DEPTH callout line.
    "SlitDepth": (0.0129, 0.0046, 0.0124, 0.0045),
}
# Hole callouts: every line plus the shoulder the leader leaves from
# (ADJUSTER_CALLOUT_EXTENT is with the adjuster callout's placement).
# r3: "Ø 3.26 ↓ 6.9" measured 28.5 mm of text (I31); "Ø 2.26 TO SLOT" on
# the same sheet 33.7 mm.  "Ø 3.26 DRILL TO SLOT" adds "DRILL " (six glyphs at
# the 2.4 mm that line averages) to the latter: 19.6 mm over the old text,
# split both sides of the commanded point as SolidWorks centres it.  An
# estimate until a render measures it.
_PINCH_CLEARANCE_TEXT_GROWTH = 0.0196
PINCH_CLEARANCE_CALLOUT_EXTENT = (
    0.0150 + _PINCH_CLEARANCE_TEXT_GROWTH / 2.0,
    0.0030,
    0.0166 + _PINCH_CLEARANCE_TEXT_GROWTH / 2.0,
    0.0023,
)
PINCH_THREAD_CALLOUT_EXTENT = (0.0322, 0.0085, 0.0310, 0.0078)
# Free notes are placed by their upper-left corner.
_NOTE_EXTENTS = {
    "ADJUSTER ENTRY": (0.0, 0.0036, 0.0365, 0.0),
    "ROTATED 90°": (0.0, 0.0036, 0.0257, 0.0),
    "RIGHT VIEW\nPINCH CLEARANCE ENTRY": (0.0, 0.0081, 0.0581, 0.0),
    "VIEW B\nPINCH THREAD ENTRY": (0.0, 0.0081, 0.0476, 0.0),
    "VIEW C\nSHAFT ENTRY": (0.0, 0.0081, 0.0278, 0.0),
}
# SolidWorks places section A-A's "SECTION A-A / SCALE 3:2" label under the
# view; its ink relative to SECTION_CENTER.
SECTION_LABEL_BOX = (-0.0227, -0.0537, 0.0227, -0.0392)
# Section A-A's cutting-plane arrows.  SolidWorks draws one from each end of
# the chain line (SECTION_LINE_OVERSHOOT past the plan's ends) toward the
# section view on the right: a 12 mm shaft (run 1's leaf dump, d09c2b9eb,
# GetSectionLineInfo2) and a head 1/4 in long and 1/8 in across (6.0-6.2 by
# 3.0-3.1 measured on the run-1 and 72ab renders), with its letter printed
# just past the tip (SECTION_LETTER_BOX, from the tip: the 72ab render's "A"
# ink, 2.44..8.12 right and -1.12..4.89 up, padded 0.2).
# Until r3 this audit never saw them: layoutcheck's replay of run 1 found
# its north arrow 1.45 mm over PassageCenter's 7.50.
SECTION_LINE_OVERSHOOT = 0.004
SECTION_ARROW_LENGTH = 0.012
SECTION_ARROW_HEAD = (0.00635, 0.003175)  # along the shaft, across it
SECTION_LETTER_BOX = (0.0022, -0.0013, 0.0083, 0.0051)
# The locating-foot finish symbol: its leader lands midway along the right
# half of the foot edge; measured on the 287c render, its ink (shoulder,
# triangle, arm and "Ra 3.2") spans this far round the commanded point and
# its leader leaves from the shoulder's left end.
FOOT_FINISH_EXTENT = (0.0072, 0.0003, 0.0178, 0.0087)
FOOT_FINISH_LEADER_DX = -0.0067
# A view letter's ink from its note's upper-left corner (287c: C 64.5-69.2 x
# 254.4-259.3 mm, B 48.3-52.8 x 150.7-155.5 mm).  C's leader leaves the
# letter's left side at mid-height; B's leaves its right side level with
# the tip.
VIEW_LETTER_EXTENT = (0.0, 0.0053, 0.0051, 0.0)
VIEW_B_LEADER_DX = 0.0058
VIEW_C_LEADER_DX = -0.0005

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
FLANGE_SLOT_W_LINE_DROP = 0.0045
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
    foot = _elevation_y(0.0, FOOT_FINISH_CENTER)
    return (
        (FOOT_FINISH_CENTER[0] + FOOT_FINISH_DX, foot - FOOT_FINISH_DROP),
        (FOOT_FINISH_CENTER[0] + BLOCK_X * _S / 4.0, foot),
    )


def sheet_text_boxes(adjuster_center: tuple[float, float] = FRONT_CENTER) -> dict[str, Box]:
    """Every text block this module places, keyed by dimension or note name."""
    keeps = {
        **FRONT_KEEP,
        **_adjuster_axis_keep(adjuster_center),
        **TOP_KEEP,
        **SECTION_KEEP,
        **RIGHT_KEEP,
        **LEFT_KEEP,
    }
    boxes = {
        name: _extent_box(point, _VALUE_EXTENTS.get(name, _VALUE_EXTENT))
        for name, point in keeps.items()
    }
    boxes["adjuster callout"] = _extent_box(
        _adjuster_callout_xy(adjuster_center), ADJUSTER_CALLOUT_EXTENT
    )
    boxes["pinch clearance callout"] = _extent_box(
        PINCH_CLEARANCE_CALLOUT_XY, PINCH_CLEARANCE_CALLOUT_EXTENT
    )
    boxes["pinch thread callout"] = _extent_box(
        PINCH_THREAD_CALLOUT_XY, PINCH_THREAD_CALLOUT_EXTENT
    )
    boxes["foot finish"] = _extent_box(_foot_finish_placement()[0], FOOT_FINISH_EXTENT)
    for label, (text_xy, _tip) in (("view B letter", VIEW_B_ARROW), ("view C letter", VIEW_C_ARROW)):
        boxes[label] = _extent_box(text_xy, VIEW_LETTER_EXTENT)
    for text, x, y in _sheet_notes(adjuster_center):
        boxes[text.split("\n")[0]] = _extent_box((x, y), _NOTE_EXTENTS[text])
    for name, (_tail, tip) in sheet_section_arrows().items():
        left, down, right, up = SECTION_LETTER_BOX
        boxes[name] = (tip[0] + left, tip[1] + down, tip[0] + right, tip[1] + up)
    x0, y0, x1, y1 = SECTION_LABEL_BOX
    boxes["SECTION A-A label"] = (
        SECTION_CENTER[0] + x0,
        SECTION_CENTER[1] + y0,
        SECTION_CENTER[0] + x1,
        SECTION_CENTER[1] + y1,
    )
    return boxes


def sheet_view_silhouettes() -> dict[str, Box]:
    """Each view's model outline as rectangles (an L view is two)."""
    foot = _elevation_y(0.0, FRONT_CENTER)
    top = _elevation_y(BLOCK_HEIGHT, FRONT_CENTER)
    flange_top = _elevation_y(FLANGE_T, FRONT_CENTER)
    half_x = BLOCK_X * _S / 2.0
    boxes = {
        "front": (FRONT_CENTER[0] - half_x, foot, FRONT_CENTER[0] + half_x, top),
        "back": (BACK_CENTER[0] - half_x, foot, BACK_CENTER[0] + half_x, top),
        "plan": (
            TOP_CENTER[0] - half_x,
            _plan_y(Z_NORTH),
            TOP_CENTER[0] + half_x,
            _plan_y(Z_SOUTH),
        ),
        # Rotated 90 degrees: the block height runs across the sheet.
        "section A-A": (
            SECTION_CENTER[0] - BLOCK_HEIGHT * _S / 2.0,
            SECTION_CENTER[1] - (Z_NORTH - Z_SOUTH) * _S / 2.0,
            SECTION_CENTER[0] + BLOCK_HEIGHT * _S / 2.0,
            SECTION_CENTER[1] + (Z_NORTH - Z_SOUTH) * _S / 2.0,
        ),
    }
    # The right view has north on the left, VIEW B north on the right.
    for label, center, sign in (("right", RIGHT_CENTER, -1.0), ("view B", LEFT_CENTER, 1.0)):
        north, south_face, south_end = (
            center[0] + sign * (z - Z_MID) * _S
            for z in (Z_NORTH, -BLOCK_Z / 2.0, Z_SOUTH)
        )
        boxes[f"{label} body"] = (min(north, south_face), foot, max(north, south_face), top)
        boxes[f"{label} flange"] = (
            min(south_face, south_end),
            foot,
            max(south_face, south_end),
            flange_top,
        )
    return boxes


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


def sheet_dimension_ink(
    adjuster_center: tuple[float, float] = FRONT_CENTER,
) -> dict[str, DimensionInk]:
    """Every kept dimension's printed lines and arrows, and section A-A's
    cutting-plane arrows (shaft and head, keyed like their letters)."""
    texts = sheet_text_boxes(adjuster_center)
    keeps = {
        **FRONT_KEEP,
        **_adjuster_axis_keep(adjuster_center),
        **TOP_KEEP,
        **SECTION_KEEP,
        **RIGHT_KEEP,
    }
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
        return keeps[name][1] - (
            FLANGE_SLOT_W_LINE_DROP if name == "FlangeSlotW" else HORIZONTAL_LINE_DROP
        )

    front_x = FRONT_CENTER[0]
    foot = _elevation_y(0.0, FRONT_CENTER)
    top = _elevation_y(BLOCK_HEIGHT, FRONT_CENTER)
    ax = adjuster_center[0]
    plus_x = 1.0 if adjuster_center == FRONT_CENTER else -1.0
    slit = SLIT_W * _S / 2.0
    tc = TOP_CENTER[0]
    slot_north = _plan_y(FLANGE_SLOT_NORTH_CENTER_Z)
    slot_south = _plan_y(FLANGE_SLOT_SOUTH_CENTER_Z)
    slot_w = FLANGE_SLOT_W * _S / 2.0
    south_face = _plan_y(-BLOCK_Z / 2.0)
    north = _right_x(Z_NORTH)
    heel_top = _elevation_y(HEEL_RELIEF_HEIGHT, RIGHT_CENTER)
    specs = {
        "Width": (h, (front_x - half_x, front_x + half_x), (foot, foot), drop("Width"), out),
        "BlockHt": (v, (foot, top), (front_x - half_x,) * 2, keeps["BlockHt"][0], inside),
        "SlitW": (h, (front_x - slit, front_x + slit), (top, top), drop("SlitW"), out),
        "AxisHeight": (
            v,
            (foot, _elevation_y(ADJUSTER_AXIS_HEIGHT, adjuster_center)),
            (ax - half_x,) * 2,
            keeps["AxisHeight"][0],
            inside,
        ),
        "PassageCenter": (
            h, (ax - plus_x * half_x, ax), (top, top), drop("PassageCenter"), out
        ),
        "SlitDepth": (
            v,
            (_elevation_y(BLOCK_HEIGHT - SLIT_DEPTH, adjuster_center), top),
            (ax + slit, ax + half_x),
            keeps["SlitDepth"][0],
            out,
        ),
        "Depth": (
            v, (_plan_y(Z_NORTH), south_face), (_PLAN_LEFT,) * 2, PLAN_CHAIN_X, out
        ),
        "FlangeLen": (
            v, (south_face, _plan_y(Z_SOUTH)), (_PLAN_LEFT,) * 2, PLAN_CHAIN_X, inside
        ),
        "FlangeSlotNorthZ": (
            v,
            (south_face, slot_north),
            (_PLAN_LEFT, tc),
            keeps["FlangeSlotNorthZ"][0],
            out,
        ),
        "FlangeSlotSouthZ": (
            v,
            (south_face, slot_south),
            (_PLAN_LEFT, tc),
            keeps["FlangeSlotSouthZ"][0],
            inside,
        ),
        "FlangeSlotW": (h, (tc - slot_w, tc + slot_w), (None, None), drop("FlangeSlotW"), out),
        "FlangeSlotX": (
            h, (_PLAN_LEFT, tc), (_plan_y(Z_SOUTH),) * 2, drop("FlangeSlotX"), out
        ),
        "PinchDepthCenter": (
            h,
            (north, _right_x(0.0)),
            (top, top - 0.002),
            drop("PinchDepthCenter"),
            out,
        ),
        "HeelReliefDepth": (
            h,
            (north, north + HEEL_RELIEF_DEPTH * _S),
            (heel_top, None),
            drop("HeelReliefDepth"),
            out,
        ),
        "HeelReliefHt": (v, (foot, heel_top), (north, north), keeps["HeelReliefHt"][0], out),
        "FlangeT": (
            v,
            (foot, _elevation_y(FLANGE_T, RIGHT_CENTER)),
            (_right_x(Z_SOUTH),) * 2,
            keeps["FlangeT"][0],
            out,
        ),
        # r3: from the foot's corner at the flange's south end to the pinch
        # hole's centre, whose witness crosses the body's south face.
        "PinchHeight": (
            v,
            (foot, _elevation_y(PINCH_HEIGHT, RIGHT_CENTER)),
            (_right_x(Z_SOUTH), _right_x(0.0)),
            keeps["PinchHeight"][0],
            inside,
        ),
    }
    ink = {
        name: _dimension_ink(
            axis, ends, origins, line, set_sides.get(name, arrows), texts[name]
        )
        for name, (axis, ends, origins, line, arrows) in specs.items()
    }
    for name, (tail, tip) in sheet_section_arrows().items():
        ink[name] = section_arrow_ink(tail, tip)
    return ink


def sheet_section_arrows() -> dict[str, tuple[Point, Point]]:
    """Section A-A's two cutting-plane arrows, (tail on the chain line, tip)."""
    tail_x = TOP_CENTER[0]
    ends = (
        ("north", _plan_y(Z_NORTH) - SECTION_LINE_OVERSHOOT),
        ("south", _plan_y(Z_SOUTH) + SECTION_LINE_OVERSHOOT),
    )
    return {
        f"section A {end}": ((tail_x, y), (tail_x + SECTION_ARROW_LENGTH, y))
        for end, y in ends
    }


def section_arrow_ink(tail: Point, tip: Point) -> DimensionInk:
    """One cutting-plane arrow: its shaft and its head's outline."""
    along, across = SECTION_ARROW_HEAD
    head = _drawing_leaders.arrowhead_outline((tail, tip), along, across)[:3]
    return DimensionInk(arrows=((tail, tip), *head))


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


def sheet_leaders(adjuster_center: tuple[float, float] = FRONT_CENTER) -> dict[str, Leader]:
    """Every leader this module places, keyed like its text block."""
    pinch_y = _elevation_y(PINCH_HEIGHT, RIGHT_CENTER)
    finish, finish_tip = _foot_finish_placement()
    view_b_text, view_b_tip = VIEW_B_ARROW
    view_c_text, view_c_tip = VIEW_C_ARROW
    return {
        "adjuster callout": _callout_leader(
            _adjuster_callout_xy(adjuster_center),
            ADJUSTER_CALLOUT_EXTENT,
            (adjuster_center[0], _elevation_y(ADJUSTER_AXIS_HEIGHT, adjuster_center)),
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
            (LEFT_CENTER[0] + (0.0 - Z_MID) * _S, pinch_y),
            PINCH_BORE_DIA * _S / 2.0,
        ),
        "foot finish": Leader((finish[0] + FOOT_FINISH_LEADER_DX, finish[1]), finish_tip),
        "view B letter": Leader((view_b_text[0] + VIEW_B_LEADER_DX, view_b_tip[1]), view_b_tip),
        "view C letter": Leader(
            (view_c_text[0] + VIEW_C_LEADER_DX, view_c_text[1] - VIEW_LETTER_HEIGHT / 2.0),
            view_c_tip,
        ),
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


def assert_sheet_ink_clear(adjuster_center: tuple[float, float] = FRONT_CENTER) -> None:
    """Refuse a placement whose own ink collides before any COM work is spent."""
    findings = sheet_ink_collisions(
        sheet_text_boxes(adjuster_center),
        sheet_view_silhouettes(),
        sheet_dimension_ink(adjuster_center),
        sheet_leaders(adjuster_center),
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


def _add_adjuster_axis(adapter: Any, section: Any) -> None:
    """Sketch the adjuster bore's axis across section A-A, owned by the view.

    The through thread and its countersinks read as one bore only with their
    centreline (review 2026-09-23, when the 8.85 pinch rise still rose from
    it).  The cutting plane is X = 0, so the adjuster axis
    (along Z) lies in it and projects as a line, while the pinch axis (along
    X) projects to a point -- run 71f5acc5 sketched that zero-length line and
    CreateCenterLine returned None.  Run 6cab17f6 then sketched it with sheet
    coordinates while the section was the active view, so it landed in the
    view's own sketch frame, off the sheet.  This is draw_top_frame's proven
    owned-centreline recipe: activate the view, map each sheet point through
    the view sketch's ModelToSketchTransform, and colour the segment black
    (a sketch line otherwise prints in the under-defined blue).
    """
    half = BLOCK_Z / 2000.0 + AXIS_OVERRUN * SHEET_SCALE[1] / SHEET_SCALE[0]
    ends = [
        model_point_in_view(
            adapter,
            section,
            (0.0, ADJUSTER_AXIS_HEIGHT / 1000.0, z),
            label=f"adjuster axis end {index}",
        )
        for index, z in enumerate((-half, half))
    ]
    length = math.dist(ends[0][:2], ends[1][:2])
    expected = 2.0 * half * SHEET_SCALE[0] / SHEET_SCALE[1]
    if abs(length - expected) > 0.0005:
        raise RuntimeError(
            f"adjuster axis projects {length:.4f} m long in section A-A, "
            f"expected {expected:.4f}"
        )
    draw = adapter.currentModel
    drawing = _early_bound(draw, "IDrawingDoc")
    if not drawing.ActivateView(view_name(adapter, section)):
        raise RuntimeError("failed to activate section A-A for the adjuster axis")
    draw.ClearSelection2(True)
    sketch = _early_bound(section.GetSketch(), "ISketch")
    transform = _early_bound(sketch.ModelToSketchTransform, "IMathTransform")
    utility = _early_bound(adapter.swApp.GetMathUtility(), "IMathUtility")
    points = []
    for x, y in ends:
        point = _early_bound(
            utility.CreatePoint(double_array([x, y, 0.0])), "IMathPoint"
        )
        points.append(
            tuple(_early_bound(point.MultiplyTransform(transform), "IMathPoint").ArrayData)
        )
    manager = _early_bound(draw.SketchManager, "ISketchManager")
    centerline = manager.CreateCenterLine(*points[0], *points[1])
    if centerline is None:
        raise RuntimeError("failed to sketch the adjuster axis in section A-A")
    segment = _early_bound(centerline, "ISketchSegment")
    segment.Color = 0
    if int(segment.Color) != 0:
        raise RuntimeError("adjuster axis colour did not persist")
    draw.ClearSelection2(True)
    rebuild_drawing(adapter, label="section A-A adjuster axis")


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

def _preferred_entry_circle(
    adapter: Any,
    candidates: tuple[
        tuple[Any, tuple[float, float]],
        tuple[Any, tuple[float, float]],
    ],
    *,
    radius_mm: float,
    center_y_mm: float,
    label: str,
) -> tuple[Any, tuple[float, float], Any]:
    """Use the first opposed view that exposes the requested real model edge."""
    matches: list[tuple[Any, tuple[float, float], Any]] = []
    for view, center in candidates:
        try:
            edge = _circle_entity(
                adapter,
                view,
                radius_mm=radius_mm,
                center_y_mm=center_y_mm,
                label=label,
            )
        except RuntimeError:
            continue
        matches.append((view, center, edge))
    if not matches:
        raise RuntimeError(f"{label} is absent from both opposed views")
    # The through thread exposes the same tap-drill rim from both sides.
    # Both selections still belong to the same native Hole Wizard feature; the
    # caller's candidate order supplies a stable sheet-side preference.
    return matches[0]

# Hole-callout order: drill line, thread line, then the prose (Main eye-pass
# af561fa7); the caption already names the pinch-thread jaw.
_PINCH_THREAD_QUALIFIER = "COAXIAL WITH CLEARANCE"
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
    updated = {
        part: text.replace("<hw-thru>", "TO SLOT")
        for part, text in definitions.items()
    }
    thread_parts = [part for part, text in updated.items() if "<hw-threadclass>" in text]
    if len(thread_parts) != 1:
        raise RuntimeError(f"pinch thread line is not in one callout part: {updated!r}")
    thread_part = thread_parts[0]
    updated[thread_part] = f"{updated[thread_part].rstrip()}\n{_PINCH_THREAD_QUALIFIER}"
    rewritten = "\n".join(updated.values())
    if (
        "THRU ALL" in rewritten
        or rewritten.count("TO SLOT") != 2
        or any(token not in rewritten for token in _PINCH_THREAD_NATIVE_TOKENS)
    ):
        raise RuntimeError(f"pinch-thread callout rewrite lost semantics: {updated!r}")
    return updated


# r3 blocker: the near jaw is drilled full diameter until it opens into the
# slit, so the native blind depth ("<HOLE-DEPTH> <hw-depth>") becomes the
# instruction; the diameter stays the Hole Wizard variable.
PINCH_CLEARANCE_EXTENT_TEXT = "DRILL TO SLOT"
_BLIND_DEPTH_TOKENS = re.compile(r"<HOLE-DEPTH>\s*<hw-depth>")


def _pinch_clearance_callout_definitions(definitions: dict[int, str]) -> dict[int, str]:
    """Swap the one native blind-depth pair for DRILL TO SLOT, loudly."""
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
        part: _BLIND_DEPTH_TOKENS.sub(PINCH_CLEARANCE_EXTENT_TEXT, text)
        for part, text in definitions.items()
    }
    rewritten = "\n".join(updated.values())
    if "<hw-depth>" in rewritten or "<HOLE-DEPTH>" in rewritten:
        raise RuntimeError(f"pinch clearance rewrite left a depth: {updated!r}")
    return updated


def _pinch_clearance_callout_resolved(resolved_parts: dict[int, str]) -> bool:
    joined = "\n".join(resolved_parts.values())
    return (
        joined.count(PINCH_CLEARANCE_EXTENT_TEXT) == 1
        and "<HOLE-DEPTH>" not in joined
        and f"{PINCH_CLEARANCE_DIA:.2f}" in joined
    )


def _set_pinch_clearance_callout_text(display: Any) -> None:
    """State DRILL TO SLOT without severing the diameter's Hole Wizard variable."""
    definitions = {part: str(display.GetText(part) or "") for part in (5, 6, 7, 8)}
    updated = _pinch_clearance_callout_definitions(definitions)
    for definition_part, writable_part in ((5, 1), (6, 2), (7, 3), (8, 4)):
        if updated[definition_part] != definitions[definition_part]:
            display.SetText(writable_part, updated[definition_part])
    persisted = {part: str(display.GetText(part) or "") for part in (5, 6, 7, 8)}
    resolved_parts = {part: str(display.GetText(part) or "") for part in (1, 2, 3, 4)}
    if persisted != updated or not _pinch_clearance_callout_resolved(resolved_parts):
        raise RuntimeError(
            "pinch clearance DRILL TO SLOT did not persist: "
            f"definitions={persisted!r}, resolved={resolved_parts!r}"
        )


def _pinch_thread_callout_resolved(resolved_parts: dict[int, str]) -> bool:
    """Whether the resolved callout keeps both extents and qualifies the thread.

    GetText(1..4) resolves definition parts 5..8 in part order, which is not
    the sheet's line order: af561fa7 printed part 7 (the tap drill) above
    part 5 (the thread).  So the check is per part -- the qualifier ends the
    thread's own part, which then prints last -- not by string position.
    """
    joined = "\n".join(resolved_parts.values())
    thread = [text for text in resolved_parts.values() if "UNC" in text]
    return (
        "THRU ALL" not in joined
        and joined.count("TO SLOT") == 2
        and len(thread) == 1
        and thread[0].rstrip().endswith(f"TO SLOT\n{_PINCH_THREAD_QUALIFIER}")
    )


# E11/W1: the through thread's two countersinks are one chamfer feature; the
# callout names them under the thread line, so the hole reads in one place.
ADJUSTER_CSK_QUALIFIER = (
    f"90\u00b0 CSK \u00d8{ADJUSTER_BORE_DIA + 2.0 * ADJUSTER_CSK:.1f} BOTH ENDS"
)


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
    if (
        persisted != updated
        or len(thread) != 1
        or not thread[0].rstrip().endswith(ADJUSTER_CSK_QUALIFIER)
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


_COSMETIC_THREAD_LAYER = "CONE-TIP-SECTION-THREADS-HIDDEN"


def _hide_cosmetic_threads(adapter: Any, view: Any, *, label: str) -> int:
    """Keep cosmetic-thread annotation ink out of a view (section, pictorial)."""
    draw = adapter.currentModel
    manager = _early_bound(draw.GetLayerManager(), "ILayerMgr")
    layer = manager.GetLayer(_COSMETIC_THREAD_LAYER)
    if layer is None:
        if int(
            manager.AddLayer(
                _COSMETIC_THREAD_LAYER,
                "cosmetic thread ink hidden in cone-tip section",
                0,
                0,
                0,
            )
        ) != 1:
            raise RuntimeError("failed to add cone-tip section thread layer")
        layer = manager.GetLayer(_COSMETIC_THREAD_LAYER)
    layer = _early_bound(layer, "ILayer")
    layer.Visible = False
    if bool(layer.Visible) or bool(layer.Printable):
        raise RuntimeError("cone-tip section thread layer is not hidden")
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
        adapter.currentModel,
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
        adapter, property_view=PART_STEM, scale=SHEET_SCALE, layout=SPEC.layout
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
    back = place_view(adapter, str(SOURCE), "*Back", *BACK_CENTER, scale=SHEET_SCALE)
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=SHEET_SCALE)
    for view in (front, top, right, left, back, iso):
        set_hidden_lines_removed(adapter, view)

    # The top-view cutting plane passes through both orthogonal bore axes.  The
    # resulting solid-line section shows the through adjuster thread, its
    # countersinks, split jaws and pinch bore relationship without dashed
    # inference.
    #
    # r3: the section carries no dimension (the pinch height moved to the
    # right view), so no part-hidden sketch needs showing while it is cut.
    section = create_section_view(
        adapter,
        top,
        line_start=(TOP_CENTER[0], _plan_y(Z_NORTH) - SECTION_LINE_OVERSHOOT),
        line_end=(TOP_CENTER[0], _plan_y(Z_SOUTH) + SECTION_LINE_OVERSHOOT),
        view_xy=SECTION_CENTER,
        section_label="A",
        scale=SHEET_SCALE,
        label="adjuster and pinch-bore centre section",
    )
    set_hidden_lines_removed(adapter, section)
    section_annotations = curate_view_dimensions(
        adapter,
        section,
        keep=SECTION_KEEP,
        view_label="bore centre section",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    _add_adjuster_axis(adapter, section)

    adjuster_view, adjuster_center, adjuster_edge = _preferred_entry_circle(
        adapter,
        ((front, FRONT_CENTER), (back, BACK_CENTER)),
        radius_mm=ADJUSTER_BORE_DIA / 2.0,
        center_y_mm=ADJUSTER_AXIS_HEIGHT,
        label="through adjuster thread",
    )
    assert_sheet_ink_clear(adjuster_center)
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
    front_keep = dict(FRONT_KEEP)
    back_keep: dict[str, tuple[float, float]] = {}
    adjuster_axis_keep = _adjuster_axis_keep(adjuster_center)
    if adjuster_view is front:
        front_keep.update(adjuster_axis_keep)
    else:
        back_keep.update(adjuster_axis_keep)

    # Views that dimension part-hidden reference sketches (995a7c94) import
    # through the opt-in helper, which shows each owner sketch in that view
    # only.  AxisHeight/PassageCenter go to whichever elevation shows the
    # adjuster entry, so only that one opts in; the other shows no sketch.
    adjuster_curate = hidden_sketches.curate_view_dimensions
    front_curate = adjuster_curate if adjuster_view is front else curate_view_dimensions
    back_curate = curate_view_dimensions if adjuster_view is front else adjuster_curate
    front_annotations = front_curate(
        adapter,
        front,
        keep=front_keep,
        view_label="adjuster entry elevation",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    top_annotations = hidden_sketches.curate_view_dimensions(
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
    back_annotations = back_curate(
        adapter,
        back,
        keep=back_keep,
        view_label="adjuster threaded entry",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    annotations = [
        *front_annotations,
        *top_annotations,
        *section_annotations,
        *right_annotations,
        *left_annotations,
        *back_annotations,
    ]
    set_dimension_callouts(adapter, annotations, DIMENSION_CALLOUTS)
    _set_arrow_sides(
        adapter,
        annotations,
        {
            **{name: _DIM_ARROWS_OUTSIDE for name in ARROWS_OUTSIDE},
            **{name: _DIM_ARROWS_INSIDE for name in ARROWS_INSIDE},
        },
    )
    assert_imported_precision(adapter, annotations, DRAWING_PRECISION_BY_NAME)

    for view, label in (
        (front, "adjuster entry elevation"),
        (right, "pinch clearance entry"),
        (left, "pinch threaded entry"),
        (back, "adjuster threaded entry"),
    ):
        if not auto_center_marks(adapter, view, holes=True, size=0.0025):
            raise RuntimeError(f"failed to add centre marks to {label} view")

    adjuster_callout = add_native_hole_callout(
        adapter,
        adjuster_view,
        edge=adjuster_edge,
        callout_xy=_adjuster_callout_xy(adjuster_center),
        label="through adjuster thread",
    )
    _set_adjuster_callout_text(adjuster_callout)
    pinch_clearance_callout = add_native_hole_callout(
        adapter,
        right,
        edge=pinch_clearance_edge,
        callout_xy=PINCH_CLEARANCE_CALLOUT_XY,
        label="pinch entry-jaw clearance",
    )
    _set_pinch_clearance_callout_text(pinch_clearance_callout)
    pinch_thread_callout = add_native_hole_callout(
        adapter,
        left,
        edge=pinch_thread_edge,
        callout_xy=PINCH_THREAD_CALLOUT_XY,
        label="pinch opposite-jaw thread",
    )
    _set_pinch_thread_callout_text(pinch_thread_callout)
    _audit_isometric_annotation_provenance(adapter, iso)
    # Main eye-pass af561fa7: the shaded pictorial carries no thread ink.
    _hide_cosmetic_threads(adapter, iso, label="isometric")

    _hide_cosmetic_threads(adapter, section, label="section")
    for text, x, y in _sheet_notes(adjuster_center):
        if add_note(adapter, text, x, y) is None:
            raise RuntimeError(f"failed to add the {text.lower()!r} note")
    # C1 verdict (2026-09-23): the native projected-view arrow is not
    # switchable through the documented API -- IProjectionArrow.Visible is
    # get-only and no document preference or IView member sets it; only the
    # PropertyManager "Arrow" box does.  Untested: an IProjectionArrow.SetLabel
    # side effect, a PropertyManager RunCommand route.  So each removed view
    # is named by a letter note whose straight leader is the viewing arrow.
    for letter, view, (text_xy, tip_xy) in (
        ("B", front, VIEW_B_ARROW),
        ("C", top, VIEW_C_ARROW),
    ):
        note = add_leader_note(
            adapter,
            letter,
            text_xy=text_xy,
            attach_xy=tip_xy,
            view=view,
            label=f"view {letter} viewing arrow",
        )
        # add_note leaves text at the document height; size the letter here
        # (the add_surface_finish char_height recipe) and prove the leader
        # tip did not move with it.
        annotation = _early_bound(note.GetAnnotation(), "IAnnotation")
        text_format = annotation.GetTextFormat(0)
        if text_format is None:
            raise RuntimeError(f"view {letter} arrow note has no text format")
        text_format.CharHeight = VIEW_LETTER_HEIGHT
        if not annotation.SetTextFormat(0, False, text_format):
            raise RuntimeError(f"failed to size the view {letter} arrow letter")
        rebuild_drawing(adapter, label=f"view {letter} arrow letter")
        points = list(annotation.GetLeaderPointsAtIndex(0) or ())
        if len(points) < 6 or math.dist((points[-3], points[-2]), tip_xy) > 0.001:
            raise RuntimeError(f"view {letter} arrow tip moved when its letter was sized")

    foot_view = {FRONT_CENTER: front, BACK_CENTER: back}[FOOT_FINISH_CENTER]
    foot_edge = _foot_edge(adapter, foot_view)
    # Onto the foot edge itself, midway along its right half: at the corner
    # vertex (run 6cab17f6) it could name the side face as well as the seat.
    foot_symbol, foot_right = _foot_finish_placement()
    foot_finish = add_surface_finish(
        adapter,
        foot_view,
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
    if not any(
        abs(point[0] - foot_right[0]) < 1e-6
        and abs(point[1] - foot_right[1]) < 1e-6
        and abs(point[2]) < 1e-6
        for point in leader_points
    ):
        raise RuntimeError(
            "foot-seat finish leader missed the verified bottom-edge endpoint: "
            f"expected={foot_right!r}, points={leader_points!r}"
        )

    # Annotation insertion can regenerate a view with inherited display state;
    # every manufacturing view is explicitly HLR at export.
    for view in (front, top, right, left, back, section):
        set_hidden_lines_removed(adapter, view)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Cone Tip Block Manufacturing Drawing",
        scale=SHEET_SCALE,
        layout=SPEC.layout,
        # SolidWorks auto-inserts one descriptive "... Tapped Hole" note per
        # tapped Hole Wizard hole it shows: the adjuster's (I31 retired the
        # U30 foot tap, the second one run 66084ed9 counted).
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
