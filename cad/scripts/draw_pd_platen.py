r"""Create the curated machinist drawing for the platen plate (MHA-PD-02).

The platen is a 10.62 x 5.31 brass plate, .152 thick, with four #2-56
clip-screw through taps and ten counterbored #4 loose through holes for the
guide screws.  The sheet prints decimal inch (the part's ``drawing_unit: in``)
and runs at 1:2: the front view carries the outline, one native callout per
hole size and a tag at every hole; a native hole table right of VIEW B locates all
fourteen holes from the plate's lower-left corner and names each group's mate
(rule 10).  VIEW B, the 1:1 right side its lettered arrow looks at, carries the
thickness on a native text shelf clear of its witnesses,
a 2:1 partial section A-A through one counterbore the user-accepted
counterbore floor as a reference dimension with its worst case, and a 1:4
isometric the form.  The counterbores' far side is named in their callout.

Every printed dimension is an associative model dimension whose places the
part authors (``pd_platen_spec.DRAWING_PRECISION``); the hole sizes ship as
native Hole Wizard callouts and the hole table's locations print at the
part's ``POSITION_PLACES``.

Run (SolidWorks already open)::

    uv run python cad\scripts\draw_pd_platen.py pd-platen
"""

from __future__ import annotations

import argparse
import math
import sys
from typing import Any

from solidworks_mcp.adapters.com_variant import double_array
from solidworks_mcp.adapters.solidworks.drawing import (
    add_note,
    dimension_name,
    place_view,
    view_name,
)
from solidworks_mcp.adapters.sw_type_info import constant

from _check import check
from _com import _early_bound
import _config
from _drawing_annotation_extent import (
    CLEAR_GAP_M,
    PLACE_SETTLE_M,
    Box,
    callout_ink,
    move_annotation,
    require_clear,
    require_inside,
    sheet_region,
)
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
import _drawing_hidden_sketches
from _drawing_hole_callout import add_native_hole_callout, set_hole_callout_precision
from _drawing_leader_notes import add_leader_note
from _drawing_leaders import dimension_segments
from _drawing_notes import add_property_linked_note
from _drawing_projection import model_point_in_view, model_points_in_view
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_sections import create_section_view
from _drawing_tables import insert_hole_table
from _drawing_view_display import set_hidden_lines_removed
from _hole_callout_thread_class import omit_title_block_thread_class
from _hole_spec import THREAD_MAJOR_MM, blind_cut_dia_mm
from _machinist_review_mode import MachinistReviewMode
from _part_properties import part_drawing_unit
from _paths import CAD_ROOT
from _section_axis import position_section_caption
from _session import run_build
import _telemetry
from _title_block_units import LENGTH_UNITS
from pd_platen_callouts import SOCKET_ENGAGEMENT_LINE
from pd_platen_spec import (
    CBORE_DEPTH,
    CBORE_FLOOR_CALLOUT,
    CBORE_SECTION_HOLE_Y,
    CBORE_SECTION_X,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    GUIDE_CALLOUT_PRECISION,
    GUIDE_HOLE_DIA,
    GUIDE_HOLE_X,
    GUIDE_HOLE_XY,
    GUIDE_HOLE_Y,
    PLATE_HEIGHT,
    PLATE_THICKNESS,
    PLATE_WIDTH,
    POSITION_PLACES,
    SOCKET_SPEC,
    SOCKET_XY,
)


# Cached machinist review leaf: a FIX or ERROR verdict fails the build.
MACHINIST_REVIEW = MachinistReviewMode.ENFORCE

SPEC = DRAWINGS_BY_NAME["pd_platen"]
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
UNIT = part_drawing_unit(PART_STEM)

SHEET_SCALE = (1.0, 2.0)
VIEW_SCALE = (1, 2)
RIGHT_SCALE = (1, 1)
ISO_SCALE = (1, 4)
_S = SHEET_SCALE[0] / SHEET_SCALE[1] / 1000.0  # sheet m per model mm, 1:2
_RIGHT_S = 1.0 / 1000.0  # VIEW B, 1:1

# Sheet layout (meters; the B-size field is x 0.0127..0.4191, y 0.0127..0.2667
# and the title block holds x >= 0.216, y <= 0.066).  The front view stands top
# left (x 0.0726..0.2074, y 0.1563..0.2237) with VIEW B (the 1:1 right side,
# x 0.297..0.303, y 0.108..0.242) right of it.  The hole table (15 rows of
# ~11 mm, 165 mm tall) fits only the field right of VIEW B, above the title
# block (HOLE_TABLE_ANCHOR), so the isometric and section A-A share the field
# under the front view, left of the title block, 34 mm and more under the
# width's text (y 0.148): the isometric on the left, its body about 50 x 57 mm
# at 1:4 round ISO_CENTER and its one-row note (~60 mm) 32 mm left of and
# 34 mm under that centre (the v48 render's iso and note); the group spans
# x 0.033..0.093, y 0.046..0.113.  Section A-A stands right of it (its group
# x 0.121..0.188, y 0.038..0.111: SECTION_CENTER's comment), 28 mm short of the
# title block and 27 mm clear of the isometric's note.
FRONT_CENTER = (0.140, 0.190)
RIGHT_CENTER = (0.300, 0.175)
ISO_CENTER = (0.065, 0.084)
ISO_NOTE_XY = (ISO_CENTER[0] - 0.032, ISO_CENTER[1] - 0.034)
# Section A-A: a partial cut down the top row's middle guide hole (x =
# CBORE_SECTION_X, its cutting plane the part's CBORE_SECTION_PLANE) from
# SECTION_SPAN below the hole's centre to as far above, at 2:1 (40 mm tall
# uncropped), +Y up.  The span sets the cutting-plane line's length on the
# 1:2 front view: at 4.5 (4.5 mm of line) its two arrows stood side by
# side and the lower A's apex sat in the upper A's legs (machinist review
# round 2); at 10 the line runs 10 mm, each labelled end ~4 mm clear of the
# Ø.26 counterbore.
# Machinist review (rule 9, owner review 2026-11-07): the template's
# end-segments-only line style printed A-A as two arrow stubs with a gap
# across the hole.  The document's section line style is set to
# StandardWithConnector before the cut, so the short line runs whole from one
# arrow to the other across that hole only (draw_fr_rocker_arm_support,
# draw_dt_cone_swing_platform).
# swDetailingSectionViewLineStyleDisplay = StandardWithConnector.
_SECTION_LINE_STYLE_PREFERENCE = 542
_SECTION_LINE_WITH_CONNECTOR = 0
# The cut stays symmetric about the hole: run from 14.7 below to 5.3 above,
# the section imported no CboreFloorReference sketch (farm fail8, round 4).
# The floor reference stands
# mid-annulus below the hole (pd_platen_spec), so its value hangs below the
# cut's lower end, where the dimension line runs under the text: the text
# stands LEFT of the extension lines, its right end at SECTION_TEXT_RIGHT
# (r5: centred on them, they ran down through all three of its rows); the
# native caption's top centre stands above the cut.
# Machinist review v47: the cut's ends printed as solid object lines and read
# as the plate's own edges (it is 5.31 tall).  A Crop2 fence trims the cut to
# SECTION_CROP_HALF either side of the hole with no outline
# (draw_ch_rocker_arm_tl_oblique_carrier's _crop_section),
# and a thin long-break line with one Z stands on each trimmed end across the
# thickness, past both faces by _SECTION_BREAK_OVERRUN (inside the fence's
# margin).  The Z keeps 0.3 clear of the floor's extension line at the
# counterbore floor (z = CBORE_DEPTH), where the lower break crosses it.
SECTION_SCALE = (2, 1)
_SECTION_S = SECTION_SCALE[0] / SECTION_SCALE[1] / 1000.0
SECTION_SPAN = 10.0
SECTION_CROP_HALF = 5.0
_SECTION_FENCE_MARGIN = 1.0
# The section's group about SECTION_CENTER (sheet m): the cropped cut's outline
# +-10 x +-18 mm (r2 Crop2 telemetry), the native caption's top centre 5 mm left
# of and 33 mm over the centre (the v48 render's "SECTION A-A / SCALE 2:1",
# ~46 mm wide, down to ~17 mm over the centre), the floor value's three rows
# 47 mm wide ending at SECTION_TEXT_RIGHT and hanging to ~40 mm under the
# centre: x -49..+18 mm, y -40..+33 mm.  At (0.170, 0.078), under the front
# view's right half, that is x 0.121..0.188, y 0.038..0.111: 37 mm under the
# width's text, 25 mm over the border, 28 mm short of the title block.
SECTION_CENTER = (0.170, 0.078)
SECTION_CAPTION_XY = (SECTION_CENTER[0] - 0.005, SECTION_CENTER[1] + 0.033)
# The floor value's top row stands 14 mm of sheet under the cut's lower end.
_SECTION_TEXT_DROP_M = 0.014
# The value's widest row (".027 MIN WORST CASE", ~47 mm) ends 2.5
# short of the near extension line, the floor's counterbore face.
_SECTION_TEXT_HALF_WIDTH = 0.0245
SECTION_TEXT_RIGHT = (
    SECTION_CENTER[0] + (CBORE_DEPTH - PLATE_THICKNESS / 2.0) * _SECTION_S - 0.0025
)
# Model mm, in the cutting plane: the cut's ends, its crop fence's corners,
# its break lines, its centre (the hole's axis at mid-thickness) and the
# floor value's text, _SECTION_TEXT_DROP_M below the cropped end and left of
# the floor (model +Z is sheet +X in the cut).
SECTION_LINE_MODEL_MM = (
    (CBORE_SECTION_X, CBORE_SECTION_HOLE_Y - SECTION_SPAN, 0.0),
    (CBORE_SECTION_X, CBORE_SECTION_HOLE_Y + SECTION_SPAN, 0.0),
)
_SECTION_ENDS_Y = (
    CBORE_SECTION_HOLE_Y - SECTION_CROP_HALF,
    CBORE_SECTION_HOLE_Y + SECTION_CROP_HALF,
)
SECTION_CROP_MODEL_MM = (
    (CBORE_SECTION_X, _SECTION_ENDS_Y[0], -_SECTION_FENCE_MARGIN),
    (CBORE_SECTION_X, _SECTION_ENDS_Y[1], PLATE_THICKNESS + _SECTION_FENCE_MARGIN),
)
_SECTION_BREAK_OVERRUN = 0.6
_SECTION_BREAK_MID = PLATE_THICKNESS / 2.0
SECTION_BREAKS = tuple(
    tuple(
        (CBORE_SECTION_X, y + dy, z)
        for dy, z in (
            (0.0, -_SECTION_BREAK_OVERRUN),
            (0.0, _SECTION_BREAK_MID - 0.7),
            (0.6, _SECTION_BREAK_MID - 0.35),
            (-0.6, _SECTION_BREAK_MID + 0.35),
            (0.0, _SECTION_BREAK_MID + 0.7),
            (0.0, PLATE_THICKNESS + _SECTION_BREAK_OVERRUN),
        )
    )
    for y in _SECTION_ENDS_Y
)
_SECTION_ANCHOR_MM = (CBORE_SECTION_X, CBORE_SECTION_HOLE_Y, PLATE_THICKNESS / 2.0)
SECTION_TEXT_MODEL_MM = {
    "CboreFloor": (
        CBORE_SECTION_X,
        _SECTION_ENDS_Y[0] - _SECTION_TEXT_DROP_M / _SECTION_S,
        PLATE_THICKNESS / 2.0
        + (SECTION_TEXT_RIGHT - _SECTION_TEXT_HALF_WIDTH - SECTION_CENTER[0])
        / _SECTION_S,
    ),
}
# The right view's bbox spans the plate (model Z).
_DEPTH_SPAN = PLATE_THICKNESS


def _front_x(model_x_mm: float) -> float:
    """Sheet X of a model-X point in the front view (bbox-centred)."""
    return FRONT_CENTER[0] + (model_x_mm - PLATE_WIDTH / 2.0) * _S


def _front_y(model_y_mm: float) -> float:
    """Sheet Y of a model-Y point in the front view (bbox-centred)."""
    return FRONT_CENTER[1] + (model_y_mm - PLATE_HEIGHT / 2.0) * _S


def _right_x(model_z_mm: float) -> float:
    """Sheet X of a model-Z point in the right view (seen from +X: -Z right)."""
    return RIGHT_CENTER[0] - (model_z_mm - _DEPTH_SPAN / 2.0) * _RIGHT_S


def _right_y(model_y_mm: float) -> float:
    """Sheet Y of a model-Y point in VIEW B (the 1:1 right side)."""
    return RIGHT_CENTER[1] + (model_y_mm - PLATE_HEIGHT / 2.0) * _RIGHT_S


LEFT_EDGE_X = _front_x(0.0)
RIGHT_EDGE_X = _front_x(PLATE_WIDTH)
BOTTOM_EDGE_Y = _front_y(0.0)
TOP_EDGE_Y = _front_y(PLATE_HEIGHT)
_SOCKET_LEFT_X, _SOCKET_RIGHT_X = sorted({x for x, _ in SOCKET_XY})
_SOCKET_LOW_Y, _SOCKET_HIGH_Y = sorted({y for _, y in SOCKET_XY})

# Per-view survivors of the marked-dimension import: parametric name -> sheet
# position.  The hole table locates every hole (HOLE_TABLE_LOCATED), so the
# front view keeps the overall size: the width 8 mm under the plate, clear
# above the isometric and section A-A; the height right of it, beyond VIEW B's
# arrow.
# VIEW B carries the plate's thickness above it; section A-A the counterbore
# floor (SECTION_TEXT_MODEL_MM, placed by projection once the cut stands).
FRONT_KEEP = {
    "Width": (FRONT_CENTER[0], BOTTOM_EDGE_Y - 0.008),
    "Height": (0.272, FRONT_CENTER[1]),
}
RIGHT_KEEP = {
    "Depth": (_right_x(PLATE_THICKNESS / 2.0), 0.251),
}
SECTION_KEEP_NAMES = frozenset(SECTION_TEXT_MODEL_MM)
# The thickness states what its .XXX is spent on (the clearance to the
# reducer disc, by number: r7 review; rule 26 retired the shop-private
# "AIR"); the floor is a reference dimension (the user-accepted exception)
# that also states its printed worst case (pd_platen_spec.CBORE_FLOOR_CALLOUT).
DISC_NUMBER = "MHA-PD-06"
DIMENSION_CALLOUTS_ABOVE = {"Depth": f"SETS CLEARANCE TO {DISC_NUMBER} DISC"}
DIMENSION_CALLOUTS_BELOW = {
    "CboreFloor": CBORE_FLOOR_CALLOUT,  # pd-platen RV-02
}
REFERENCE_DIMENSION = "CboreFloor"

# The mates whose patterns the two hole groups match, by released number.
GUIDE_NUMBER = _config.parts("pd-platen-guide")["number"]
GUIDE_SCREW_NUMBER = _config.parts("sh-vn-brass-fillister-screw")["number"]
CLIP_NUMBER = _config.parts("pd-platen-clip")["number"]
# The guide-hole callout rides the top row's first hole, its leader up to
# text above the plate's left half, right of the upper left socket; the socket
# callout rides the upper right socket's tap drill, its leader up to text above
# the plate's right end.  Each is its group's one size callout (rule 10: the
# hole table carries no SIZE) and names the part whose pattern the table's
# .XXX locations match; the counterbores open on the far (paper) face, deep
# enough to sink the named guide screw's heads.
_GUIDE_PICK_HOLE = (GUIDE_HOLE_X[0], GUIDE_HOLE_Y[1])
_DIAG = math.sqrt(0.5)
GUIDE_EDGE_XY = (
    _front_x(_GUIDE_PICK_HOLE[0]) + GUIDE_HOLE_DIA / 2.0 * _S * _DIAG,
    _front_y(_GUIDE_PICK_HOLE[1]) + GUIDE_HOLE_DIA / 2.0 * _S * _DIAG,
)
# The guide text's centre stands one half-width right of the pick, so its
# leader rises from the text's left end almost straight down to the rim
# (round 3: centred at x 0.128, its left end at x 0.078 sent the leader up-left
# through the upper left socket's A2 tag).  Half-widths from the v48 render's
# ink: the guide's C'BORE row runs ~96 mm, the socket's TAP row ~69 mm; the
# socket text moves right with it, ~6 mm clear of the guide's right end.
GUIDE_CALLOUT_HALF_WIDTH = 0.050
GUIDE_CALLOUT_XY = (0.137, 0.248)
# Three rows: the size, the pattern's mate, and the counterbore by its symbol
# with its side and the screw whose heads it sinks after its depth (round 4,
# rule 26: "DRILL, C'BORE FAR SIDE FOR ..." wrote the counterbore in words over
# its own symbol row).  The side and screw join the definition part that ends
# on the counterbore's depth (_name_counterbore_side).
GUIDE_CALLOUT_PROCESS = f"PATTERN MATCHES {GUIDE_NUMBER}\n"
GUIDE_CBORE_SUFFIX = f"FAR SIDE FOR {GUIDE_SCREW_NUMBER}"
# A hole callout's format parts (prefix, suffix, callout above, callout below)
# read back at their definitions 5-8 and are written at 1-4.
_DEFINITION_TO_WRITABLE = {5: 1, 6: 2, 7: 3, 8: 4}
SOCKET_DRILL_DIA = blind_cut_dia_mm(SOCKET_SPEC)
SOCKET_DRILL_R_SHEET = SOCKET_DRILL_DIA / 2.0 * _S
SOCKET_EDGE_XY = (
    _front_x(_SOCKET_RIGHT_X) + SOCKET_DRILL_R_SHEET * _DIAG,
    _front_y(_SOCKET_HIGH_Y) + SOCKET_DRILL_R_SHEET * _DIAG,
)
# Its engagement row (#2411) is the widest, ~78 mm in the farm layout audit
# (run 20261112T194605766Z: its left end at x 187.0 put the leader
# through the guide callout's right end at 188.1), so the text stands 7 mm
# further right, ~6 mm clear of the guide's right end.
SOCKET_CALLOUT_HALF_WIDTH = 0.040
SOCKET_CALLOUT_XY = (0.233, 0.252)
# The engagement line states the clip screws' worst-case full thread in the
# plate, under 1.5D (rule 20, pd_platen_callouts; pd-platen RV-03, #2411).
SOCKET_CALLOUT_PROCESS = (  # pd-platen RV-01, RV-03
    f"PATTERN MATCHES {CLIP_NUMBER}\n{SOCKET_ENGAGEMENT_LINE}\nTAP"
)
# The template centre-marks every hole as the view is placed (an explicit
# AutoInsertCenterMarks2 printed all 28 marks twice in r1); the front view
# proves exactly one mark per hole.
_CENTER_MARK_ANNOTATION = 13  # swAnnotationType_e.swCenterMarkSym
CENTER_MARKS_PER_VIEW = len(SOCKET_XY) + len(GUIDE_HOLE_XY)
# The socket's native callout drops one automatic "Tapped Hole" note.
REDUNDANT_NOTE = "Tapped Hole"

# Hole table (rule 10: fourteen hole axes on one view).  Its origin is the
# plate's lower-left corner vertex, the sharp the shop picks up with an edge
# finder (model 0, 0: build_pd_platen's corner-anchored outline), and every
# row prints its station at the part's .XXX (POSITION_PLACES; pd-platen RV-01
# accepts the taps' three-place stations), checked back against the model's
# stations so a mis-anchored origin fails the build.  No position frame on
# this part, so the locations are ordinary toleranced dimensions, not basic.
# Each row names the mate its group's pattern matches in a MATE column, by
# that part's number alone: the guide holes the guide (the guide screw they
# take is named on the guide callout's C'BORE row), the sockets the clip.  The
# generated SIZE column is hidden, because each group's one native callout on
# the view prints its size at the part's callout places (GUIDE_CALLOUT_PRECISION:
# a table SIZE cell takes the document's places and cannot be edited).
HOLE_TABLE_LOCATED = DRAWING_DIMENSIONS["Sockets"] | DRAWING_DIMENSIONS["GuideHoles"]
GUIDE_MATE = GUIDE_NUMBER
SOCKET_MATE = CLIP_NUMBER
HOLE_TABLE_MATES: dict[tuple[float, float], str] = {
    **dict.fromkeys(GUIDE_HOLE_XY, GUIDE_MATE),
    **dict.fromkeys(SOCKET_XY, SOCKET_MATE),
}
HOLE_TABLE_MATE_COLUMN = "MATE"
_HOLE_TABLE_SIZE_COLUMN = 3
_HOLE_TABLE_MATE_INDEX = 4
_INSERT_COLUMN_AFTER = 3  # swTableItemInsertPosition_After
_INSERT_COLUMN_DEFAULT_WIDTH = 0  # swInsertColumn_DefaultWidth
_TABLE_SIZE_CAN_CHANGE = 0  # swTableRowColChange_TableSizeCanChange
# Printed LOC cells convert back to model mm within half a .001 in step; a
# rim's radius matches its Hole Wizard cut to the spec's pinned 3-place mm.
_HOLE_TABLE_TOLERANCE_MM = 0.02
_RIM_RADIUS_TOLERANCE_MM = 0.005
_NOTE_ANNOTATION = 6  # swAnnotationType_e.swNote
# ASME B title block (sheet m): x >= 0.216, y <= 0.066.
_TITLE_BLOCK_LEFT = 0.216
_TITLE_BLOCK_TOP = 0.066
# TAG, X LOC, Y LOC and MATE widths (sheet m; "10.446" prints ~15 mm, at
# ~2.55 mm a character: v48's 23-character guide mate filled 59 mm of a
# 66 mm cell).  A mate number ("MHA-PD-11", nine characters) prints ~23 mm,
# so its cell is 30 mm; the table stands 82 mm wide.
HOLE_TABLE_WIDTHS = {0: 0.012, 1: 0.020, 2: 0.020, _HOLE_TABLE_MATE_INDEX: 0.030}
# The rows keep their natural height: SetRowHeight(row, 0.006) never took
# (round 2 read 15 rows back at 0.1644 m, ~0.01096 each), so the layout plans
# an 11 mm pitch, 165 mm for the header and fourteen holes, and the build reads
# the real heights back (_check_hole_table).
HOLE_TABLE_ROW_PITCH = 0.011
HOLE_TABLE_ROWS = 1 + len(HOLE_TABLE_MATES)
# Top-left corner, in the field right of VIEW B and above the title block,
# the one field on the sheet 165 mm tall.  Its left edge (x 0.320) stands
# 17 mm right of VIEW B's far face (x 0.303) and ~9 mm right of its caption
# (RIGHT_CAPTION_XY, "SCALE 1:1" ~23 mm from x 0.2885), its right edge
# (x 0.402) 17 mm short of the border.  Its top (y 0.241) stands 4.4 mm under
# the thickness's function text over VIEW B (round 2 ink y 0.2454..0.2566
# across x 0.311..0.396), its bottom (y 0.076) 10 mm over the title block.
HOLE_TABLE_ANCHOR = (0.320, 0.241)
HOLE_TABLE_BOX = (
    HOLE_TABLE_ANCHOR[0],
    HOLE_TABLE_ANCHOR[1] - HOLE_TABLE_ROWS * HOLE_TABLE_ROW_PITCH,
    HOLE_TABLE_ANCHOR[0] + sum(HOLE_TABLE_WIDTHS.values()),
    HOLE_TABLE_ANCHOR[1],
)
# Inch sheets drop the leading zero (ASME Y14.5): the hole table's own
# document option follows the template and would print 0.170
# (draw_fr_rocker_arm_support).  Document Properties > Tables > Hole.
HOLE_TABLE_LEADING_ZERO = "swLeadingZero_DoNotShow"
_HOLE_TABLE_LOC_COLUMNS = (1, 2)
# Each native tag stands in the quadrant of its hole that faces the plate's
# interior and clears its neighbours: the bottom guide row's tags above-right,
# the top row's below-right, except the cut hole's, below-left, off section
# A-A's arrows (they point right); each socket's toward mid-height, inboard.
# The tag box's near corner stands on the 45-degree diagonal, _TAG_GAP_M past
# the hole's rim (a socket's: its thread's major Ø, the cosmetic thread's
# circle), so it clears the hole and both arms of its centre mark.
_TAG_GAP_M = 0.001
_TAG_LANDED_M = 5e-4
_SECTION_HOLE = (CBORE_SECTION_X, CBORE_SECTION_HOLE_Y)


def hole_tag_corner(
    station: tuple[float, float],
) -> tuple[tuple[float, float], tuple[int, int]]:
    """A station's tag box near corner (sheet m) and the quadrant it opens to."""
    x, y = station
    if station in SOCKET_XY:
        rim = THREAD_MAJOR_MM[SOCKET_SPEC.size] / 2.0
        sx = 1 if x < PLATE_WIDTH / 2.0 else -1
        sy = 1 if y < PLATE_HEIGHT / 2.0 else -1
    else:
        rim = GUIDE_HOLE_DIA / 2.0
        sx = -1 if station == _SECTION_HOLE else 1
        sy = 1 if y == GUIDE_HOLE_Y[0] else -1
    offset = rim * _S * _DIAG + _TAG_GAP_M
    return (_front_x(x) + sx * offset, _front_y(y) + sy * offset), (sx, sy)


def counterbore_side_definition(definitions: dict[int, str]) -> tuple[int, str]:
    """The one format part ending on the counterbore's depth, with its side
    and screw (GUIDE_CBORE_SUFFIX) after it: ``⌴ Ø.26 ↧ .115 FAR SIDE FOR ...``.
    The through hole prints THRU, so the counterbore's is the callout's only
    depth token; any other shape fails loud."""
    if set(definitions) != set(_DEFINITION_TO_WRITABLE):
        raise RuntimeError(f"unexpected hole callout parts: {definitions!r}")
    holders = [part for part, text in definitions.items() if "<HOLE-DEPTH>" in text]
    if len(holders) != 1 or GUIDE_CBORE_SUFFIX in "\n".join(definitions.values()):
        raise RuntimeError(f"guide callout has no single counterbore depth: {definitions!r}")
    part = holders[0]
    definition = definitions[part]
    head, _marker, tail = definition.rpartition("<HOLE-DEPTH>")
    if "<HOLE-DEPTH>" in head or len(tail.split()) != 1:
        raise RuntimeError(f"guide callout's depth does not close its part: {definitions!r}")
    return part, f"{definition.rstrip()} {GUIDE_CBORE_SUFFIX}"


def _name_counterbore_side(display: Any) -> None:
    """Write the counterbore's side and screw after its depth; read back."""
    display = _early_bound(display, "IDisplayDimension")
    definitions = {
        part: str(display.GetText(part) or "") for part in _DEFINITION_TO_WRITABLE
    }
    part, updated = counterbore_side_definition(definitions)
    display.SetText(_DEFINITION_TO_WRITABLE[part], updated)
    applied = str(display.GetText(part) or "")
    if applied.replace("\r", "") != updated.replace("\r", ""):
        raise RuntimeError(f"guide counterbore side did not persist: {applied!r}")


# VIEW B (rules 9, 26): the 1:1 right side is not projected at the sheet's
# 1:2, so it carries a letter and its scale, and a lettered viewing arrow on
# the front view's right edge looks at it (_oblique_block_drawing._view_arrow).
# The arrow's tip lands on the edge midway between the right-hand sockets, its
# letter 15 mm out, left of the height's dimension line (x 0.272).  The
# caption is the sheet's own (the part's "Right View Note" is no longer
# printed) and stands under the view as the old prose caption did.
VIEW_LETTER = "B"
VIEW_LETTER_HEIGHT = 0.005
VIEW_ARROW_RUN = 0.015
VIEW_ARROW_TIP = (RIGHT_EDGE_X, _front_y((_SOCKET_LOW_Y + _SOCKET_HIGH_Y) / 2.0))
VIEW_ARROW_TEXT_XY = (
    VIEW_ARROW_TIP[0] + VIEW_ARROW_RUN,
    VIEW_ARROW_TIP[1] + VIEW_LETTER_HEIGHT / 2.0,
)
RIGHT_CAPTION = f"VIEW {VIEW_LETTER}\nSCALE {RIGHT_SCALE[0]}:{RIGHT_SCALE[1]}"
RIGHT_CAPTION_XY = (0.2885, 0.100)

_VIEW_KEEPS = {
    "front": FRONT_KEEP,
    "right": RIGHT_KEEP,
    "section A-A": dict.fromkeys(SECTION_KEEP_NAMES),
}
PRINTED_DIMENSIONS = frozenset().union(*_VIEW_KEEPS.values())
if PRINTED_DIMENSIONS & HOLE_TABLE_LOCATED or (
    PRINTED_DIMENSIONS | HOLE_TABLE_LOCATED != set().union(*DRAWING_DIMENSIONS.values())
):
    raise AssertionError(
        "the platen views and hole table must print each marked dimension once"
    )
if {DRAWING_PRECISION_BY_NAME[name] for name in HOLE_TABLE_LOCATED} != {
    POSITION_PLACES
}:
    raise AssertionError("the hole table prints every located hole at POSITION_PLACES")
PRINTED_PRECISION = {
    name: DRAWING_PRECISION_BY_NAME[name] for name in PRINTED_DIMENSIONS
}


def _place_thickness_text(adapter: Any, annotations: list[Any]) -> Box:
    """Keep the 3.850 line fixed and shelf its complete function/value block.

    The native review crop shows both witnesses striking the digits.  Offset
    only the text, then measure its full native shoulder rather than sizing
    the move from the number alone (the function row is much wider).  Returns
    the placed text block (sheet m): the hole table stands under it.
    """
    matches = [
        _early_bound(annotation, "IAnnotation")
        for annotation in annotations
        if dimension_name(adapter, annotation) == "Depth"
    ]
    if len(matches) != 1:
        raise RuntimeError(f"expected one platen Depth dimension, found {len(matches)}")
    annotation = matches[0]
    display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
    if int(display.Type2) not in (2, 11, 12):
        raise RuntimeError("platen thickness is not a native linear dimension")
    rebuild_drawing(adapter, label="platen thickness function text")
    lines = dimension_segments(annotation)
    if not lines:
        raise RuntimeError("platen thickness has no native dimension lines")
    right = max(point[0] for line in lines for point in line)
    position = tuple(float(value) for value in annotation.GetPosition())
    # Seed beside the existing line and outside-arrow tail.  The native
    # shoulder then supplies the actual width of both rows for the final move.
    offset_dimension_text(adapter, [annotation], {"Depth": (right, position[1])})
    ink = callout_ink(adapter, annotation, label="platen thickness")
    dx = right + CLEAR_GAP_M + PLACE_SETTLE_M - ink.text[0]
    target = (right + dx, position[1])
    move_annotation(adapter, annotation, dx, 0.0, label="platen thickness text")
    ink = callout_ink(adapter, annotation, label="platen thickness")
    placed = tuple(float(value) for value in annotation.GetPosition())
    if not bool(display.OffsetText) or math.dist(placed[:2], target) > 1e-5:
        raise RuntimeError(f"platen thickness text offset did not persist: {placed}")
    if str(display.GetText(3) or "") != DIMENSION_CALLOUTS_ABOVE["Depth"]:
        raise RuntimeError("platen thickness lost its native function text")
    if ink.text[0] < right + CLEAR_GAP_M:
        raise RuntimeError(
            f"platen thickness text {ink.text} still crowds its native line at {right}"
        )
    require_inside("platen thickness text", ink.text, sheet_region(adapter))
    return ink.text


def _set_whole_cutting_lines(drawing_model: Any) -> None:
    """Draw every cutting-plane line whole, joining its two arrows (rule 9)."""
    extension = _early_bound(drawing_model.Extension, "IModelDocExtension")
    if not extension.SetUserPreferenceInteger(
        _SECTION_LINE_STYLE_PREFERENCE, 0, _SECTION_LINE_WITH_CONNECTOR
    ):
        raise RuntimeError("failed to set the platen's whole cutting-plane lines")
    applied = int(extension.GetUserPreferenceInteger(_SECTION_LINE_STYLE_PREFERENCE, 0))
    if applied != _SECTION_LINE_WITH_CONNECTOR:
        raise RuntimeError(
            f"platen cutting-plane line style did not persist: {applied}"
        )


def _front_hole_rims(view: Any) -> dict[tuple[float, float], Any]:
    """Each hole station's visible rim in the front view, by centre and radius.

    A coordinate pick alone selected a neighbouring circle at 1:2 (r2: the
    since-removed boss's rim printed as a "tap"), so every rim is found
    among the view's visible circles instead (*Front: model +X right, +Y up):
    a guide hole's drill circle (its counterbore is on the hidden far side)
    and a socket's tap-drill circle, exactly one per station.
    """
    radii = {
        **dict.fromkeys(GUIDE_HOLE_XY, GUIDE_HOLE_DIA / 2.0),
        **dict.fromkeys(SOCKET_XY, SOCKET_DRILL_DIA / 2.0),
    }
    found: dict[tuple[float, float], list[Any]] = {station: [] for station in radii}
    for raw in visible_view_entities(view, 1, label="platen front hole rims"):
        edge = _early_bound(raw, "IEdge")
        raw_curve = edge.GetCurve()
        if raw_curve is None:
            continue
        curve = _early_bound(raw_curve, "ICurve")
        if not curve.IsCircle():
            continue
        params = tuple(float(value) * 1000.0 for value in curve.CircleParams)
        for station, radius in radii.items():
            if (
                math.dist(params[:2], station) <= _HOLE_TABLE_TOLERANCE_MM
                and abs(params[6] - radius) <= _RIM_RADIUS_TOLERANCE_MM
            ):
                found[station].append(edge)
    wrong = {station: len(edges) for station, edges in found.items() if len(edges) != 1}
    if wrong:
        raise RuntimeError(f"platen front view rims are not one per hole: {wrong}")
    return {station: edges[0] for station, edges in found.items()}


def _rim_pick(station: tuple[float, float]) -> tuple[float, float]:
    """A sheet point on a station's rim (the table's diagnostic pick)."""
    diameter = SOCKET_DRILL_DIA if station in SOCKET_XY else GUIDE_HOLE_DIA
    return (_front_x(station[0]) + diameter / 2.0 * _S, _front_y(station[1]))


def _drop_hole_table_leading_zeros(adapter: Any) -> None:
    """Set the drawing's hole-table leading-zero option before the table exists."""
    extension = _early_bound(adapter.currentModel.Extension, "IModelDocExtension")
    preference = constant("swDetailingLeadingZero")
    option = constant("swDetailingHoleTable")
    value = constant(HOLE_TABLE_LEADING_ZERO)
    if not extension.SetUserPreferenceInteger(preference, option, value):
        raise RuntimeError("failed to drop the platen hole table's leading zeros")
    if int(extension.GetUserPreferenceInteger(preference, option)) != value:
        raise RuntimeError("platen hole-table leading-zero option did not persist")


def _table_cells(table: Any, columns: int) -> tuple[tuple[str, ...], ...]:
    """Every row's first ``columns`` cells, hidden columns counted."""
    return tuple(
        tuple(
            str(table.DisplayedText2(row, column, True) or "").strip()
            for column in range(columns)
        )
        for row in range(int(table.RowCount))
    )


def _hole_table_rows(table: Any) -> dict[str, tuple[int, tuple[float, float]]]:
    """Bind every generated row to its one model station by its own LOC cells.

    The rows are tag-ordered, not selection-ordered, so each row's printed
    X/Y LOC (sheet unit, .XXX) names its station; tag -> (row, station).
    """
    scale = LENGTH_UNITS[UNIT]
    rows: dict[str, tuple[int, tuple[float, float]]] = {}
    bound: set[tuple[float, float]] = set()
    for row, cells in enumerate(_table_cells(table, 3)[1:], start=1):
        tag = cells[0]
        try:
            location = (float(cells[1]) * scale, float(cells[2]) * scale)
        except ValueError as error:
            raise RuntimeError(
                f"platen hole-table row {row} has unreadable LOC cells: {cells!r}"
            ) from error
        matches = [
            station
            for station in HOLE_TABLE_MATES
            if all(
                abs(printed - model) <= _HOLE_TABLE_TOLERANCE_MM
                for printed, model in zip(location, station)
            )
        ]
        if not tag or tag in rows or len(matches) != 1 or matches[0] in bound:
            raise RuntimeError(
                f"platen hole-table row {row} binds no single station: {cells!r} "
                f"-> {matches!r}"
            )
        bound.add(matches[0])
        rows[tag] = (row, matches[0])
    if len(rows) != len(HOLE_TABLE_MATES):
        raise RuntimeError(
            f"platen hole table binds {len(rows)} of {len(HOLE_TABLE_MATES)} holes"
        )
    return rows


def _assert_no_leading_zero_locations(table: Any) -> None:
    """Read every LOC cell back: none prints a leading zero."""
    cells = [
        row[column]
        for row in _table_cells(table, 3)[1:]
        for column in _HOLE_TABLE_LOC_COLUMNS
    ]
    if any(cell.startswith(("0.", "-0.")) for cell in cells):
        raise RuntimeError(
            f"platen hole-table LOC cells kept a leading zero: {cells!r}"
        )


def _name_hole_table_mates(
    adapter: Any,
    table: Any,
    rows: dict[str, tuple[int, tuple[float, float]]],
    neighbours: dict[str, Box],
) -> Box:
    """Add the MATE column, size the table and hide the generated SIZE column.

    The generated cells are not text-editable (only the header row and custom
    columns are: draw_fr_harmonic_base ``_annotate_hole_table_rows``), so the
    mate is a custom column after SIZE, written row by row, and SIZE is then
    hidden: each group's size is its one native callout on the view.  Hiding
    comes last, after every index-based write, and the readback counts hidden
    columns (``IncludeHidden``), so no index shifts under it.  The rows keep
    their natural height (HOLE_TABLE_ROW_PITCH).  Returns the table's
    measured box (sheet m).
    """
    if int(table.ColumnCount) != 4:
        raise RuntimeError("platen hole-table mates expect the native four columns")
    generated = _table_cells(table, 4)
    inserted = table.InsertColumn2(
        _INSERT_COLUMN_AFTER,
        _HOLE_TABLE_SIZE_COLUMN,
        HOLE_TABLE_MATE_COLUMN,
        _INSERT_COLUMN_DEFAULT_WIDTH,
    )
    if inserted is not True:
        raise RuntimeError("platen hole table refused the MATE column")
    if (
        table.SetColumnTitle2(_HOLE_TABLE_MATE_INDEX, HOLE_TABLE_MATE_COLUMN, False)
        is not True
    ):
        raise RuntimeError("platen hole-table MATE column title did not set")
    for tag, (row, station) in rows.items():
        if table.IsCellTextEditable(row, _HOLE_TABLE_MATE_INDEX) is not True:
            raise RuntimeError(f"platen hole-table MATE cell of {tag} is not editable")
        table.SetText2(row, _HOLE_TABLE_MATE_INDEX, False, HOLE_TABLE_MATES[station])
    # No SetRowHeight: a row will not print shorter than its text (round 2
    # asked 6 mm and read ~11 mm back), so the check measures what stands.
    for column, width in HOLE_TABLE_WIDTHS.items():
        actual = float(table.SetColumnWidth(column, width, _TABLE_SIZE_CAN_CHANGE))
        if abs(actual - width) > 1e-6:
            raise RuntimeError(
                f"platen hole-table column {column} width did not persist: {actual!r}"
            )
    rebuild_drawing(adapter, label="platen hole-table widths")
    widths = {column: float(table.GetColumnWidth(column)) for column in HOLE_TABLE_WIDTHS}
    if any(abs(widths[column] - width) > 1e-6 for column, width in HOLE_TABLE_WIDTHS.items()):
        raise RuntimeError(f"platen hole-table widths drifted: {widths!r}")
    table.SetColumnHidden(_HOLE_TABLE_SIZE_COLUMN, True)  # VT_VOID, not success.
    rebuild_drawing(adapter, label="platen hole-table mates")
    return _check_hole_table(adapter, table, generated, rows, neighbours)


def _check_hole_table(
    adapter: Any,
    table: Any,
    generated: tuple[tuple[str, ...], ...],
    rows: dict[str, tuple[int, tuple[float, float]]],
    neighbours: dict[str, Box],
) -> Box:
    """Only the MATE column changed: generated cells kept, SIZE hidden, every
    mate on its row, the recipe's widths, and the table, grown down and right
    from its top-left anchor by its rows' read-back heights, inside the border
    and clear of the title block and of ``neighbours`` by CLEAR_GAP_M."""
    columns = int(table.TotalColumnCount)
    if columns != _HOLE_TABLE_MATE_INDEX + 1:
        raise RuntimeError(f"platen hole table has {columns} columns, expected 5")
    cells = _table_cells(table, columns)
    if tuple(row[:4] for row in cells) != generated:
        raise RuntimeError(f"MATE column changed generated hole-table cells: {cells!r}")
    mates = {row: HOLE_TABLE_MATES[station] for row, station in rows.values()}
    actual = tuple(row[_HOLE_TABLE_MATE_INDEX] for row in cells)
    if actual[0].upper() != HOLE_TABLE_MATE_COLUMN or any(
        actual[row] != mate for row, mate in mates.items()
    ):
        raise RuntimeError(f"platen hole-table MATE column did not persist: {actual!r}")
    if table.ColumnHidden(_HOLE_TABLE_SIZE_COLUMN) is not True or any(
        table.ColumnHidden(column) for column in HOLE_TABLE_WIDTHS
    ):
        raise RuntimeError("platen hole table shows SIZE or hides a printed column")
    # Widths are read only in the all-visible window (_name_hole_table_mates,
    # before SIZE is hidden): with a column hidden, GetColumnWidth's index
    # domain no longer matches ColumnHidden's (round 1 read the MATE column's
    # width as 0.0 at index 4), as on the paper-drive BOM.
    if int(table.ColumnCount) != columns - 1:
        raise RuntimeError(
            f"platen hole table shows {int(table.ColumnCount)} of {columns} columns, expected {columns - 1}"
        )
    heights = [float(table.GetRowHeight(row)) for row in range(int(table.RowCount))]
    position = tuple(
        float(value)
        for value in _early_bound(table.GetAnnotation(), "IAnnotation").GetPosition()
    )
    # The annotation's position is the table's top-left anchor (round 2 read
    # it back at HOLE_TABLE_ANCHOR exactly).
    left, top = position[:2]
    box = (left, top - sum(heights), left + sum(HOLE_TABLE_WIDTHS.values()), top)
    region = sheet_region(adapter)
    _telemetry.info(
        f"platen hole table: box {box!r} (planned {HOLE_TABLE_BOX!r}), annotation "
        f"position {position!r}, row heights {heights!r}, rows {rows!r}"
    )
    inside = (
        box[0] >= region.xmin + CLEAR_GAP_M
        and box[1] >= region.ymin + CLEAR_GAP_M
        and box[2] <= region.xmax - CLEAR_GAP_M
        and box[3] <= region.ymax - CLEAR_GAP_M
    )
    clear_of_title_block = (
        box[1] >= _TITLE_BLOCK_TOP + CLEAR_GAP_M
        or box[2] <= _TITLE_BLOCK_LEFT - CLEAR_GAP_M
    )
    if not (inside and clear_of_title_block):
        raise RuntimeError(
            f"platen hole table crosses the border or title block: {box!r}"
        )
    require_clear("platen hole table", box, neighbours)
    return box


def _note_box(note: Any, *, label: str) -> Box:
    """A note's text box on the sheet (INote.GetExtent: two corners, sheet m)."""
    extent = [float(value) for value in _early_bound(note, "INote").GetExtent()]
    if len(extent) != 6:
        raise RuntimeError(f"{label} extent is unreadable: {extent!r}")
    xs = sorted((extent[0], extent[3]))
    ys = sorted((extent[1], extent[4]))
    return (xs[0], ys[0], xs[1], ys[1])


def _tag_corner(note: Any, quadrant: tuple[int, int]) -> tuple[float, float]:
    """The corner of a tag's text box nearest its hole."""
    box = _note_box(note, label="platen hole tag")
    return (
        box[0] if quadrant[0] > 0 else box[2],
        box[1] if quadrant[1] > 0 else box[3],
    )


def _place_hole_tags(
    adapter: Any, view: Any, rows: dict[str, tuple[int, tuple[float, float]]]
) -> None:
    """Move each native hole tag into its hole's clear quadrant (hole_tag_corner)."""
    stations = {tag: station for tag, (_row, station) in rows.items()}
    tags: dict[str, tuple[Any, Any]] = {}
    for raw in _early_bound(view, "IView").GetAnnotations() or ():
        annotation = _early_bound(raw, "IAnnotation")
        if int(annotation.GetType()) != _NOTE_ANNOTATION:
            continue
        note = _early_bound(annotation.GetSpecificAnnotation(), "INote")
        tag = str(note.GetText() or "").strip()
        if tag not in stations:
            continue
        if tag in tags:
            raise RuntimeError(f"duplicate native platen hole tag {tag}")
        tags[tag] = (annotation, note)
    if set(tags) != set(stations):
        raise RuntimeError(
            f"platen hole tags missing from the front view: "
            f"{sorted(set(stations) - set(tags))}"
        )
    for tag, (annotation, note) in tags.items():
        target, quadrant = hole_tag_corner(stations[tag])
        corner = _tag_corner(note, quadrant)
        x, y, z = (float(value) for value in annotation.GetPosition())
        if not annotation.SetPosition2(
            x + target[0] - corner[0], y + target[1] - corner[1], z
        ):
            raise RuntimeError(f"failed to move platen hole tag {tag}")
    rebuild_drawing(adapter, label="platen hole tags")
    landed = {}
    for tag, (_annotation, note) in tags.items():
        target, quadrant = hole_tag_corner(stations[tag])
        landed[tag] = (_tag_corner(note, quadrant), target)
    _telemetry.info(f"platen hole tags (corner, target): {landed!r}")
    misplaced = {
        tag: pair for tag, pair in landed.items() if math.dist(*pair) > _TAG_LANDED_M
    }
    if misplaced:
        raise RuntimeError(f"platen hole tags missed their corners: {misplaced!r}")


def _size_note(adapter: Any, note: Any, height: float, *, label: str) -> None:
    """Set a note's character height (add_note leaves the document's)."""
    annotation = _early_bound(
        _early_bound(note, "INote").GetAnnotation(), "IAnnotation"
    )
    text_format = annotation.GetTextFormat(0)
    if text_format is None:
        raise RuntimeError(f"{label} has no text format")
    text_format.CharHeight = height
    if not annotation.SetTextFormat(0, False, text_format):
        raise RuntimeError(f"failed to size {label}")
    rebuild_drawing(adapter, label=label)


def _label_view_b(adapter: Any, front: Any, hole_table: Box) -> None:
    """VIEW B's lettered viewing arrow on the front view and its caption, the
    caption read back clear of the hole table right of it."""
    label = f"view {VIEW_LETTER} viewing arrow"
    arrow = add_leader_note(
        adapter,
        VIEW_LETTER,
        text_xy=VIEW_ARROW_TEXT_XY,
        attach_xy=VIEW_ARROW_TIP,
        view=front,
        label=label,
    )
    _size_note(adapter, arrow, VIEW_LETTER_HEIGHT, label=f"{label} letter")
    caption = add_note(adapter, RIGHT_CAPTION, *RIGHT_CAPTION_XY)
    if caption is None:
        raise RuntimeError(f"failed to insert the VIEW {VIEW_LETTER} caption")
    rebuild_drawing(adapter, label=f"view {VIEW_LETTER} caption")
    caption_box = _note_box(caption, label=f"view {VIEW_LETTER} caption")
    _telemetry.info(f"view {VIEW_LETTER} caption: box {caption_box!r}")
    require_clear(
        f"view {VIEW_LETTER} caption", caption_box, {"platen hole table": hole_table}
    )


def _metres(point_mm: tuple[float, float, float]) -> tuple[float, float, float]:
    return tuple(value / 1000.0 for value in point_mm)


def _orient_section(adapter: Any, section: Any) -> None:
    """Turn section A-A until model +Y runs up the sheet, as in the right view.

    Which way the cut looks along X only mirrors the symmetric counterbore,
    so the cut direction is left as SolidWorks takes it.
    """
    native = _early_bound(section, "IView")
    for attempt in range(3):
        origin = model_point_in_view(
            adapter, native, _metres(_SECTION_ANCHOR_MM), label="section A-A axis"
        )
        above = model_point_in_view(
            adapter,
            native,
            _metres(
                (
                    _SECTION_ANCHOR_MM[0],
                    _SECTION_ANCHOR_MM[1] + 1.0,
                    _SECTION_ANCHOR_MM[2],
                )
            ),
            label="section A-A +Y",
        )
        dx, dy = above[0] - origin[0], above[1] - origin[1]
        if dy > 0.0 and abs(dx) <= 1e-7:
            _telemetry.info(
                f"section A-A +Y up after {attempt} turn(s), "
                f"angle={float(native.Angle):.6f} rad"
            )
            return
        native.Angle = float(native.Angle) + math.pi / 2.0 - math.atan2(dy, dx)
        rebuild_drawing(adapter, label="platen section A-A turned")
    raise RuntimeError(f"section A-A does not run +Y up: ({dx:g}, {dy:g})")


def _centre_section(adapter: Any, section: Any) -> None:
    """Land the cut's centre (the hole's axis at mid-thickness) on
    SECTION_CENTER; a section's Position is its cut-plane origin, not its
    outline's centre (draw_pn_pen_v_block ``_centre_section``)."""
    native = _early_bound(section, "IView")
    for attempt in range(4):
        native.UpdateViewDisplayGeometry()
        projected = model_point_in_view(
            adapter,
            native,
            _metres(_SECTION_ANCHOR_MM),
            label=f"section A-A centre, pass {attempt}",
        )
        if math.dist(projected, SECTION_CENTER) <= 1e-4:
            return
        position = tuple(float(value) for value in native.Position)
        moved = [
            position[axis] + SECTION_CENTER[axis] - projected[axis] for axis in (0, 1)
        ]
        if not native.SetViewPosition(double_array(moved), False):
            raise RuntimeError("failed to re-centre platen section A-A")
        rebuild_drawing(adapter, label="platen section A-A re-centred")
    raise RuntimeError(
        f"section A-A centre stands at {projected}, not {SECTION_CENTER}"
    )


def _view_sketch_points(
    adapter: Any, native: Any, sheet_points: list[tuple[float, float]]
) -> list[tuple[float, ...]]:
    """Sheet points (metres) in the active view's own sketch frame, through
    its ModelToSketchTransform (draw_ch_rocker_arm_tl_oblique_carrier)."""
    sketch = _early_bound(native.GetSketch(), "ISketch")
    transform = _early_bound(sketch.ModelToSketchTransform, "IMathTransform")
    math_utility = _early_bound(adapter.swApp.GetMathUtility(), "IMathUtility")
    points = []
    for x, y in sheet_points:
        point = _early_bound(
            math_utility.CreatePoint(double_array([float(x), float(y), 0.0])),
            "IMathPoint",
        )
        projected = _early_bound(point.MultiplyTransform(transform), "IMathPoint")
        points.append(tuple(float(value) for value in projected.ArrayData))
    return points


def _crop_section(adapter: Any, section: Any) -> None:
    """Crop section A-A to SECTION_CROP_MODEL_MM with no crop outline, so the
    cut's trimmed ends print no object line (draw_ch_rocker_arm_tl_oblique_carrier
    ``_crop_section``'s sequence: a rectangle sketched in the view's own sketch
    round the projected fence corners, selected, then Crop2)."""
    draw = adapter.currentModel
    ddoc = _early_bound(draw, "IDrawingDoc")
    native = _early_bound(section, "IView")
    rebuild_drawing(adapter, label="platen section A-A before crop")
    sheet_corners = model_points_in_view(
        adapter,
        native,
        [_metres(point) for point in SECTION_CROP_MODEL_MM],
        label="section A-A crop corners",
    )
    if not ddoc.ActivateView(view_name(adapter, native)):
        raise RuntimeError("failed to activate platen section A-A for its crop")
    draw.ClearSelection2(True)
    before = tuple(float(value) for value in native.GetOutline())
    sketch_manager = _early_bound(draw.SketchManager, "ISketchManager")
    corners = _view_sketch_points(adapter, native, sheet_corners)
    segments = tuple(
        sketch_manager.CreateCornerRectangle(*corners[0], *corners[1]) or ()
    )
    if len(segments) != 4:
        raise RuntimeError(f"section A-A crop fence has {len(segments)} segments")
    for segment in segments:
        if not _early_bound(segment, "ISketchSegment").Select4(True, None):
            raise RuntimeError("failed to select the section A-A crop fence")
    # Crop2(jagged, no outline, intensity) returns swCropViewErrors_e; 1 is
    # NoError.
    status = int(native.Crop2(False, True, 0))
    draw.ClearSelection2(True)
    rebuild_drawing(adapter, label="platen section A-A crop")
    native.UpdateViewDisplayGeometry()
    outline = tuple(float(value) for value in native.GetOutline())
    _telemetry.info(
        f"section A-A Crop2 status {status}: outline {before!r} -> {outline!r}, "
        f"fence corners {sheet_corners!r}"
    )
    # The outline carries a margin past the fence (carrier, fr_nameplate), so
    # the proof is that it still holds the fence and lost height: the 20 mm
    # of cut trimmed off its ends.
    fence_x = sorted(float(x) for x, _ in sheet_corners)
    fence_y = sorted(float(y) for _, y in sheet_corners)
    contains = (
        outline[0] <= fence_x[0]
        and outline[2] >= fence_x[-1]
        and outline[1] <= fence_y[0]
        and outline[3] >= fence_y[-1]
    )
    if (
        status != 1
        or not bool(native.IsCropped())
        or not contains
        or outline[3] - outline[1] >= before[3] - before[1]
    ):
        raise RuntimeError(
            f"section A-A did not crop to its fence: status {status}, "
            f"outline {before!r} -> {outline!r}, fence corners {sheet_corners!r}"
        )


def _sketch_section_breaks(adapter: Any, section: Any) -> None:
    """Draw SECTION_BREAKS into A-A's own sketch as thin lines
    (draw_ch_rocker_arm_tl_oblique_carrier ``_sketch_section_breaks``).
    AddToDB keeps sketch inference from snapping the short Z segments onto
    the cut face's edges."""
    draw = adapter.currentModel
    ddoc = _early_bound(draw, "IDrawingDoc")
    native = _early_bound(section, "IView")
    if not ddoc.ActivateView(view_name(adapter, native)):
        raise RuntimeError("failed to activate platen section A-A for its breaks")
    draw.ClearSelection2(True)
    sketch_manager = _early_bound(draw.SketchManager, "ISketchManager")
    previous_add_to_db = bool(sketch_manager.AddToDB)
    sketch_manager.AddToDB = True
    try:
        for end, polyline in enumerate(SECTION_BREAKS):
            sheet_points = model_points_in_view(
                adapter,
                native,
                [_metres(point) for point in polyline],
                label=f"section A-A break line {end}",
            )
            points = _view_sketch_points(adapter, native, sheet_points)
            for index in range(len(points) - 1):
                if (
                    sketch_manager.CreateLine(*points[index], *points[index + 1])
                    is None
                ):
                    raise RuntimeError(
                        f"section A-A break line {end} segment {index} failed"
                    )
    finally:
        sketch_manager.AddToDB = previous_add_to_db
    draw.ClearSelection2(True)
    rebuild_drawing(adapter, label="platen section A-A break lines")


def _floor_section(adapter: Any, source_model: Any, front: Any) -> list[Any]:
    """Section A-A through one counterbore, carrying the floor reference.

    The floor's hidden owner sketch lies in the cutting plane; a derived view
    takes it from the part as it stands when cut and selects it through its
    base view, so the section is cut and curated while the part shows it
    (draw_pn_pen_v_block's recipe).  A section shows no hidden lines.  The
    floor is imported before the crop (the carrier's order: cropped first, an
    import there lost a dimension), and the trimmed ends get break lines.
    """
    line = [
        model_point_in_view(adapter, front, _metres(point), label="section A-A line")
        for point in SECTION_LINE_MODEL_MM
    ]
    with _drawing_hidden_sketches.part_sketches_shown(
        adapter,
        source_model,
        ("CboreFloorReference",),
        label="section A-A floor reference",
        base_view=front,
    ):
        section = create_section_view(
            adapter,
            front,
            line_start=line[0],
            line_end=line[1],
            view_xy=SECTION_CENTER,
            section_label="A",
            scale=SECTION_SCALE,
            partial=True,
            label="counterbore floor section",
        )
        _orient_section(adapter, section)
        set_hidden_lines_removed(adapter, section)
        _centre_section(adapter, section)
        keep = {
            name: model_point_in_view(
                adapter, section, _metres(point), label=f"section A-A {name} text"
            )
            for name, point in SECTION_TEXT_MODEL_MM.items()
        }
        annotations = _drawing_hidden_sketches.curate_view_dimensions(
            adapter,
            section,
            keep=keep,
            view_label="section A-A",
            dimensions_by_feature=DRAWING_DIMENSIONS,
        )
        _crop_section(adapter, section)
        _centre_section(adapter, section)
    _sketch_section_breaks(adapter, section)
    position_section_caption(
        adapter, section, SECTION_CAPTION_XY, label="platen section A-A"
    )
    return annotations


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open platen source", await adapter.open_model(str(SOURCE)))
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
            "Isometric View Note",
        ),
        required=(
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
            "Isometric View Note",
        ),
    )
    drawing_model, _sheet = new_project_drawing(
        adapter,
        property_view=PART_STEM,
        scale=SHEET_SCALE,
        layout=SPEC.layout,
        unit=UNIT,
    )
    _set_whole_cutting_lines(drawing_model)
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Platen Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "platen; manufacturing drawing; #2-56 taps; #4 counterbores",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )
    # Explicit per-view scale: a view placed without one can silently
    # auto-scale, which shifts every coordinate-based pick on it.
    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=VIEW_SCALE)
    right = place_view(adapter, str(SOURCE), "*Right", *RIGHT_CENTER, scale=RIGHT_SCALE)
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=ISO_SCALE)
    # The holes are fully defined by their callouts and section A-A draws the
    # counterbore, so no view shows hidden lines (r4).
    for view in (front, right, iso):
        set_hidden_lines_removed(adapter, view)

    front_annotations = curate_view_dimensions(
        adapter,
        front,
        keep=FRONT_KEEP,
        view_label="front",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    right_annotations = curate_view_dimensions(
        adapter,
        right,
        keep=RIGHT_KEEP,
        view_label="right",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    section_annotations = _floor_section(adapter, source_model, front)
    annotations = [*front_annotations, *right_annotations, *section_annotations]
    assert_imported_precision(adapter, annotations, PRINTED_PRECISION)
    floor = [
        a
        for a in section_annotations
        if dimension_name(adapter, a) == REFERENCE_DIMENSION
    ]
    if len(floor) != 1:
        raise RuntimeError(
            f"expected one {REFERENCE_DIMENSION} dimension, found {len(floor)}"
        )
    set_reference_dimension(adapter, floor[0], label="counterbore floor")
    set_dimension_callouts(
        adapter, annotations, DIMENSION_CALLOUTS_ABOVE, location="above"
    )
    set_dimension_callouts(adapter, annotations, DIMENSION_CALLOUTS_BELOW)
    thickness_text = _place_thickness_text(adapter, right_annotations)

    marks = (
        _early_bound(front, "IView").GetAnnotationsByType(_CENTER_MARK_ANNOTATION) or ()
    )
    if len(marks) != CENTER_MARKS_PER_VIEW:
        raise RuntimeError(
            f"expected {CENTER_MARKS_PER_VIEW} centre marks in the front view, "
            f"found {len(marks)}"
        )

    guide_callout = add_native_hole_callout(
        adapter,
        front,
        edge_xy=GUIDE_EDGE_XY,
        callout_xy=GUIDE_CALLOUT_XY,
        label="guide-screw counterbored holes",
        process=GUIDE_CALLOUT_PROCESS,
    )
    set_hole_callout_precision(
        guide_callout, GUIDE_CALLOUT_PRECISION, label="guide-screw counterbored holes"
    )
    _name_counterbore_side(guide_callout)
    socket = (_SOCKET_RIGHT_X, _SOCKET_HIGH_Y)  # *Front: model +X right, +Y up
    socket_callout = add_native_hole_callout(
        adapter,
        front,
        edge_xy=SOCKET_EDGE_XY,
        edge=_front_hole_rims(front)[socket],
        callout_xy=SOCKET_CALLOUT_XY,
        label="clip-screw through taps",
        process=SOCKET_CALLOUT_PROCESS,
    )
    # The title block's THREADS row owns the general thread class (r4).
    omit_title_block_thread_class(socket_callout, label="clip-screw through taps")
    set_hole_callout_precision(
        socket_callout, {"hw-thrutapdrldia": 3}, label="clip-screw through taps"
    )

    # The rims are read again: the callouts' rebuilds can retire the edges.
    rims = _front_hole_rims(front)
    _drop_hole_table_leading_zeros(adapter)
    hole_table = insert_hole_table(
        adapter,
        front,
        datum_xy=(LEFT_EDGE_X, BOTTOM_EDGE_Y),
        hole_points=tuple(_rim_pick(station) for station in HOLE_TABLE_MATES),
        hole_entities=tuple(rims[station] for station in HOLE_TABLE_MATES),
        expected_locations_mm=tuple(HOLE_TABLE_MATES),
        anchor_xy=HOLE_TABLE_ANCHOR,
        basic_locations=False,
        label="platen holes",
        unit=UNIT,
        location_places=POSITION_PLACES,
    )
    rows = _hole_table_rows(hole_table)
    _assert_no_leading_zero_locations(hole_table)
    table_box = _name_hole_table_mates(
        adapter,
        hole_table,
        rows,
        {
            "VIEW B": tuple(
                float(value) for value in _early_bound(right, "IView").GetOutline()
            ),
            "VIEW B thickness text": thickness_text,
        },
    )
    _place_hole_tags(adapter, front, rows)
    _label_view_b(adapter, front, table_box)
    add_property_linked_note(adapter, "Isometric View Note", *ISO_NOTE_XY)
    _telemetry.info("platen sheet: views, dimensions, callouts and hole table placed")

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Platen Manufacturing Drawing",
        scale=SHEET_SCALE,
        layout=SPEC.layout,
        redundant_note_substrings=(REDUNDANT_NOTE,),
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
