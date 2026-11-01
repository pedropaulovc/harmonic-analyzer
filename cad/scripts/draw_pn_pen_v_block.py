r"""Create the curated machinist drawing for the pen v-block.

The SLDPRT remains authoritative.  This recipe supplies only the v-block's
views, the placement of its imported model dimensions, the two native hole
callouts and the isometric's scale note; sheet/template and export behavior
lives in ``_drawing_common``.  Dimension import and curation live in
``_drawing_hidden_sketches`` (the part saves its reference sketches hidden;
each shows in the view that dimensions it); places and the pivot band are
authored on the part (``pn_pen_v_block_spec``).

The views follow the part frame (x 0 the paper end, z 0 the neck's front
face); every feature is located across the depth from the body's front face
(z BODY_Z0), the print's one depth datum:

* front: ``*Back`` looks at the body's front face, where the set screw
  enters, so the paper end is on the RIGHT; the neck's front face stands back
  from it at the step.  It carries the height and the tap's two coordinates,
  the tap's wall to the step (RV-01, from the part's hidden TapWallReference
  sketch, shown in that view only), the tap's native callout, and section
  A-A's cutting line on the pivot-bore axis.
* right (third angle, right of the ``*Back`` face): ``*Left``, the paper end,
  shows the neck's end face with the V in solid lines and the body's wider
  faces beyond it.  Under it, one baseline row from the body's front face:
  the V's two mouth edges; at the back mouth corner, out of the view in the
  wedge vertically opposite the groove's, the flanks' "2X 45°" to the bottom
  face, its short arc at the corner and its text offset right of the view;
  under the V's apex flat, inside the opening, its width; right of the view,
  the flat's reference height.  Its inside corners print nothing: the title
  block's INSIDE CORNERS R.040 MAX governs them.
  Through the V it looks along
  the open relief slot: the V is cut on past the step
  (``pn_pen_v_block_spec.V_CUT_LENGTH``), so no brass shows inside it.
* bottom: ``*Bottom`` turned 180 degrees to keep the front view's X, looking
  up into the V and the relief; through the relief the roof shows the pivot
  bore.  It carries the stations from the paper end and the overall length
  under it, the neck's two faces and the
  body's back face from the body's front face (right of the paper end, where
  the neck's step is an outline change) and the pivot bore's reamed, banded
  diameter.
* section A-A through the pivot-bore axis: bore, tap and relief in one cut,
  looking toward the free end as the paper-end view does (front face on the
  left in both); it carries both relief walls from the body's front face and
  their height, the pivot bore's station from that face, and the bore's top
  chamfer.  The tap, cut on its axis, shows its cosmetic thread's major
  diameter as thin solid lines.

No datums, frames, basic dimensions or roughness (drawing-simplicity-policy.md
rules 5 and 6), no note block: material and finish ride the title block.  The
sheet prints decimal inch (the part's ``drawing_unit: in``) and runs 4:1; the
tap callout's drill diameter prints .XXX.  The isometric runs 3:2.

Run with SolidWorks open::

    uv run python cad\scripts\draw_pn_pen_v_block.py pn-pen-v-block
"""

from __future__ import annotations

import argparse
import math
import sys
from typing import Any

from solidworks_mcp.adapters.com_variant import double_array
from solidworks_mcp.adapters.solidworks.drawing import (
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
    rebuild_drawing,
    stamp_drawing_summary,
)
from _drawing_detail_projection import settle_detail_projection
from _drawing_dimension_import import import_cosmetic_threads
from _drawing_dimensions import (
    assert_imported_precision,
    offset_dimension_text,
    set_dimension_callouts,
)
from _drawing_edges import scan_view_edges
from _drawing_hidden_sketches import curate_view_dimensions, part_sketches_shown
from _drawing_hole_callout import add_native_hole_callout, set_hole_callout_precision
from _drawing_leaders import set_near_side_diameter
from _drawing_notes import add_property_linked_note
from _drawing_projection import model_point_in_view, model_points_in_view
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_sections import create_section_view
from _drawing_view_display import set_hidden_lines_removed
from _hole_callout_thread_class import omit_title_block_thread_class
from _hole_spec import TAP_DRILL_MM
from _machinist_review_mode import MachinistReviewMode
from _part_properties import part_drawing_unit
from _paths import CAD_ROOT
from _section_axis import position_section_caption
from _session import run_build
import _telemetry
from pn_pen_v_block_spec import (
    BLOCK_HEIGHT,
    BLOCK_LENGTH,
    BODY_Z0,
    BODY_Z1,
    DEPTH_MID_Z,
    DIMENSION_CALLOUTS,
    DIMENSION_CALLOUTS_ABOVE,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    ISOMETRIC_VIEW_SCALE,
    NECK_DEPTH,
    PIVOT_BORE_DIA,
    PIVOT_BORE_TOP_CHAMFER,
    PIVOT_BORE_X,
    RELIEF_HEIGHT,
    RELIEF_X0,
    RELIEF_Z0,
    SECTION_REFERENCE_SKETCHES,
    SET_SCREW_TAP_SPEC,
    SET_SCREW_Y,
    TAP_WALL_MIN_MM,
    TAP_WALL_START_X,
    V_ANGLE_DEG,
    V_FLAT_Y,
    V_MOUTH_Z0,
    V_MOUTH_Z1,
)


# Cached machinist review leaf: a FIX or ERROR verdict fails the build.
MACHINIST_REVIEW = MachinistReviewMode.ENFORCE

SPEC = DRAWINGS_BY_NAME["pn_pen_v_block"]
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

SHEET_SCALE = (4.0, 1.0)
VIEW_SCALE = (4, 1)
ISO_SCALE = ISOMETRIC_VIEW_SCALE
_S = VIEW_SCALE[0] / VIEW_SCALE[1] / 1000.0  # sheet metres per model mm

# Sheet layout (meters).  At 4:1 the 27.3 x 18 block, 22.2 deep across its
# body, is 109.2 x 72 mm in the front view, 109.2 x 88.8 in the bottom view
# and 88.8 x 72 in the end view and the section.  The front (x 0.045..0.155,
# y 0.156..0.228) stacks over the bottom view (y 0.039..0.128), both left of
# the title block (x 0.216); the end view (x 0.188..0.276) and section A-A
# (x 0.306..0.394) share the front's row, 33 mm and 30 mm apart.
# The isometric runs 3:2 (pn_pen_v_block_spec).  At 1:1 an isometric projects
# a model axis at 0.8165 of its length, so the block's ink is (27.3 + 22.2) x
# 0.7071 = 35.0 wide and 18 x 0.8165 + 49.5 x 0.4082 = 34.9 tall (the old 36 x
# 18 x 18 chamfered block computed 38.2 wide against the 38.3 farm
# 20261014T005925878Z measured); at 3:2, 52.5 x 52.4.  Centred at (0.315,
# 0.097), its ink centred 1.8 mm under it as measured, it fills x
# 0.289..0.341, y 0.069..0.121: 78 mm right of the reamed diameter's callout
# (to x ~0.213), 4 mm over the title block (top 0.0651), under the flank
# angle's text (x ~0.2815..0.2955, from y ~0.134).
# Its scale note (top-left anchor, ~58 mm wide) beside it at mid-height, from
# x 0.350 (9 mm right of the ink) to ~0.408, 11 mm inside the border (0.4188),
# under the caption and over the title block.
FRONT_CENTER = (0.100, 0.192)
BOTTOM_CENTER = (FRONT_CENTER[0], 0.0836)
RIGHT_CENTER = (0.232, FRONT_CENTER[1])
SECTION_CENTER = (0.350, FRONT_CENTER[1])
ISO_CENTER = (0.315, 0.097)
ISO_NOTE_XY = (0.350, 0.097)
# The tap's callout rows centre on this point.  Ending "INTO PIVOT BORE" both
# rows run 28 characters ("DRILL Ø 2.26 INTO PIVOT BORE" from r14), ~71 mm:
# x ~0.165..0.236 at y ~0.249 / 0.255, over the end view (top 0.228), right of
# section line A's top end and label (x 0.105) and 66 mm left of the pivot
# chamfer's line (from x ~0.302, SECTION_KEEP).  The leader runs from the
# hole (x 0.105, y 0.204) up-right across the block's top edge.
TAP_CALLOUT_XY = (0.200, 0.252)
# Section A-A's cutting line: the pivot-bore axis (x = PIVOT_BORE_X), 1.5 mm
# past the bottom and top faces, so the cut closes across the whole block.
SECTION_LINE_MODEL_MM = (
    (PIVOT_BORE_X, -1.5, BODY_Z0),
    (PIVOT_BORE_X, BLOCK_HEIGHT + 1.5, BODY_Z0),
)

# Every view's centre: the body runs BODY_Z0..BODY_Z1 about the mid-depth.
_CX, _CY, _CZ = BLOCK_LENGTH / 2.0, BLOCK_HEIGHT / 2.0, DEPTH_MID_Z
_TAP_DRILL_R = TAP_DRILL_MM[SET_SCREW_TAP_SPEC.size] / 2.0


def _fx(model_x_mm: float) -> float:
    """Sheet X of a model-X point in the front (``*Back``) and bottom views:
    both run model +X to the sheet's left (the paper end on the right)."""
    return FRONT_CENTER[0] - (model_x_mm - _CX) * _S


def _fy(model_y_mm: float) -> float:
    return FRONT_CENTER[1] + (model_y_mm - _CY) * _S


def _bz(model_z_mm: float) -> float:
    """Sheet Y of a model-Z point in the turned bottom view: the front faces
    toward the front view above it."""
    return BOTTOM_CENTER[1] - (model_z_mm - _CZ) * _S


def _rz(model_z_mm: float) -> float:
    """Sheet X of a model-Z point in the paper-end view: the front faces on its
    left, next to the front view."""
    return RIGHT_CENTER[0] + (model_z_mm - _CZ) * _S


def _ry(model_y_mm: float) -> float:
    return RIGHT_CENTER[1] + (model_y_mm - _CY) * _S


def _sz(model_z_mm: float) -> float:
    """Sheet X of a model-Z point in section A-A: it looks toward the free end
    (+X), as the paper-end view beside it does, so the body's front face
    (where the tap enters) is on its LEFT in both (``_orient_section``)."""
    return SECTION_CENTER[0] + (model_z_mm - _CZ) * _S


def _sy(model_y_mm: float) -> float:
    return SECTION_CENTER[1] + (model_y_mm - _CY) * _S


# Per-view survivors of the marked-dimension import: parametric name -> sheet
# position.  Single-row text: its ink ~1.8 mm under to ~1.7 mm over the keep,
# its dimension line ~3.3 mm under it (r9 / r11 sheets 20261014T011745149Z,
# 20261014T023836943Z).
# Front: the height left; the tap's coordinates from the paper-end/bottom
# corner right of and below the view (the station at y 0.136, ink to ~0.138,
# its extension lines at x 0.105 / 0.154 down to ~0.132, 4 mm over the bottom
# view's NeckZ0 extension line at y 0.127).  Between it and the view, the
# tap's wall to the step: its reference line runs from the thread's rim
# toward the step at the tap's height (x ~0.110..0.117, y 0.204), its
# extension lines straight down through the face, right of the section
# line, to its line 11 mm under the bottom face, inside the station's
# extension lines.  Over the view they would cross the tap callout's leader.
# The keep is the line itself (farm 20261101T085904510Z: at 6 mm under, y
# 0.150, the line's outside leg ran along section line A's arrow, drawn at
# the cutting line's bottom end, 1.5 mm model under the face), so the line
# stands 5 mm under that arrow and 7 mm over the station's text.
_SECTION_ARROW_Y = _fy(SECTION_LINE_MODEL_MM[0][1])
FRONT_KEEP = {
    "Height": (_fx(BLOCK_LENGTH) - 0.014, _fy(_CY)),
    "SetScrewY": (_fx(0.0) + 0.010, _fy(SET_SCREW_Y / 2.0)),
    "SetScrewX": (_fx(PIVOT_BORE_X / 4.0), _fy(0.0) - 0.020),
    "TapWallMin": (
        _fx(TAP_WALL_START_X - TAP_WALL_MIN_MM / 2.0),
        _SECTION_ARROW_Y - 0.005,
    ),
}
# The wall's 6.5 mm run cannot hold its ~21 x 9 mm two-row text (the
# frame's lesson): native OffsetText parks it on a leader right of the line,
# ~6 mm clear of its extension lines, between the view's bottom face (~3.5 mm
# over the text) and the station's text (~7 mm under), its leader dropping
# to the line's right end; the anchor is the value row's bottom centre.
TAP_WALL_TEXT_XY = (0.134, _fy(0.0) - 0.007)
_TEXT_SETTLE_M = 0.0005
# Paper end: one baseline row under the view from the body's front face (the
# view's left edge, x 0.188), nested shortest-innermost 7 mm apart so no
# extension line crosses a dimension line it does not end on: the V's front
# and back mouth edges (x 0.208, 0.256).  The back edge stands right of the
# front, so its extension line passes right of the front's span; its line,
# the lower, at ~0.140.  The neck's faces and the depth print in the bottom
# view, where its step is an outline change (blind review final8: here,
# edge-on beyond the neck's end face, they read as ribs; final9: the depth
# closes their row there, so the back face's "20.10" no longer reads as the
# overall).
# * the flanks' angle to the bottom face, "2X 45°", measured at the back
#   mouth corner (x 0.256, y 0.156) in the wedge vertically opposite the
#   groove's: under the bottom face, between the flank's and the face's
#   continuations past the corner, where the build's sketch measures it.  Its
#   arc stands on that wedge's bisector 12 mm about the corner, out of the
#   view (x ~0.264..0.268, y ~0.148..0.156), right of the back edge's
#   extension line (x 0.256, straight down from the corner); its text,
#   offset off the arc on a leader (draw_pd_transgear_thumbnut's countersink
#   angle), stands right of the view under section A-A's dimension rows:
#   ~14 mm at x ~0.2815..0.2955, y ~0.1335..0.1375, its shelf (~0.133) 5 mm
#   under the far wall's line (~0.1377), 12 mm from the near wall's outside
#   arrow (tail x ~0.299, y ~0.1445) and 10 mm left of section A-A (x
#   0.306).  Release review 41bbeec: at y ~0.148 its shelf (~0.1453) ended
#   1 mm short of that arrow's tail at its height and read as one line.
#   Blind review final9: in the groove's wedge the arc, through the text,
#   ran into its "4"; final8: placed outside the wedge it measures,
#   SOLIDWORKS swept the arc 40 mm about the corner through the depth row's
#   text.
# * the apex flat's width under the flat, inside the V's opening (its text
#   ~5 mm under the flat, its line ~10 mm under, model y ~2.5, where the
#   opening is 28 mm wide), so its extension lines drop ~11 mm from the
#   flat's ends (x 0.228 / 0.236) through air (round 3 review: over the view
#   they ran across the whole end face).
# * the flat's height, a reference "(.20)", right of the view (x
#   ~0.283..0.292), 12 mm clear of section A-A (from x 0.306).
_END_ROW = 0.007
# The flank's continuation past the corner runs down-right at the flank's
# angle under the bottom face's line; the arc stands on the bisector between.
_FLANK_ARC_BEARING = -math.radians(90.0 - V_ANGLE_DEG / 2.0) / 2.0
_FLANK_ARC_RUN = 0.012
FLANK_ANGLE_TEXT_XY = (_rz(BODY_Z1) + 0.0125, _ry(0.0) - 0.0205)
RIGHT_KEEP = {
    "VMouthZ0": ((_rz(BODY_Z0) + _rz(V_MOUTH_Z0)) / 2.0, _ry(0.0) - 0.006),
    "VMouthZ1": (_rz(_CZ), _ry(0.0) - 0.006 - _END_ROW),
    # The arc's position: the text is offset to FLANK_ANGLE_TEXT_XY after.
    "VFlankAngle": (
        _rz(V_MOUTH_Z1) + _FLANK_ARC_RUN * math.cos(_FLANK_ARC_BEARING),
        _ry(0.0) + _FLANK_ARC_RUN * math.sin(_FLANK_ARC_BEARING),
    ),
    "VFlatWidth": (RIGHT_CENTER[0], _ry(V_FLAT_Y) - 0.0066),
    "VFlatY": (_rz(BODY_Z1) + 0.012, _ry(V_FLAT_Y / 2.0)),
}
# Bottom (front faces at the top, y 0.128 for the body's, 0.1196 for the
# neck's):
# * the stations from the paper end under the view, one baseline row nested
#   shortest-innermost 6.5 mm apart: the relief step, the pivot axis and the
#   overall length (lines ~0.030, ~0.023, ~0.017, the last 4 mm over the
#   border).  The length's extension lines drop from the paper end's and the
#   free end's back corners; its text toward the free end (x ~0.065..0.076).
#   Over the view, from the front corners, its line fenced off the air in
#   front of the block.
# * the neck's two faces and the body's back face right of the paper end,
#   one baseline row from the body's front face at the step, nested
#   shortest-innermost: the front face's "2.10" inside its 8.4 mm span (x
#   ~0.156..0.165, its arrows outside; nothing rises from the paper end's
#   front corner beside it now that the length prints under the view), the
#   back face's "20.10" 7 mm right at mid-span (x ~0.161..0.173, y ~0.088)
#   and the depth 8 mm further, its line 2 mm clear of "20.10"'s end, its
#   "22.2" lower, halfway between the neck's back edge and the mid-depth (x
#   ~0.171..0.179, y ~0.066).  The datum's extension line runs from the
#   step's corner on the body's front edge (x 0.119) through the air in front
#   of the neck; the depth's from the body's back corner at the step (y
#   0.039) through the air behind it.
# * the reamed diameter's callout below them, wholly right of the paper end,
#   its single arrow on the near rim (set_near_side_diameter), so no leader
#   crosses the bore.  Five rows, ~34 mm wide and ~32 mm tall about its keep:
#   x ~0.178..0.212, y ~0.025..0.057, 2.5 mm right of the depth's line (x
#   0.175) and 1 mm right of its extension line's end (~0.1765), 4 mm left of
#   the title block (x 0.216) and 12 mm over the border.  Its leader, from
#   the rim down-right to the block's lower left, leaves the view through the
#   neck's back edge, passes the paper end's extension line ~4 mm under the
#   neck's back corner (y 0.0476), then crosses the depth's extension line (y
#   0.0392) and passes ~12 mm under the depth line's end, so it crosses no
#   dimension line.
_PAPER_ROW = 0.0065
_NECK_ROW_X = _fx(0.0) + 0.0055
BOTTOM_KEEP = {
    "ReliefX0": (_fx(RELIEF_X0 / 2.0), _bz(BODY_Z1) - _PAPER_ROW),
    "PivotX": (_fx(PIVOT_BORE_X / 2.0), _bz(BODY_Z1) - 2 * _PAPER_ROW),
    "Length": (_fx(BLOCK_LENGTH) + 0.025, _bz(BODY_Z1) - 3 * _PAPER_ROW),
    "NeckZ0": (_NECK_ROW_X, (_bz(BODY_Z0) + _bz(0.0)) / 2.0),
    "NeckZ1": (_NECK_ROW_X + _END_ROW, (_bz(BODY_Z0) + _bz(NECK_DEPTH)) / 2.0),
    "Depth": (
        _NECK_ROW_X + _END_ROW + 0.008,
        (_bz(NECK_DEPTH) + _bz(DEPTH_MID_Z)) / 2.0,
    ),
    "PivotDia": (_fx(0.0) + 0.040, _bz(NECK_DEPTH) - 0.0067),
}
# Section A-A looks the same way as the paper-end view beside it: the body's
# front face at x 0.306 on the LEFT, the bottom face at y 0.156, the top at
# 0.228.  Its two reference sketches show here (they lie in the cut), every
# chord on a drawn edge: a stub up the front face from its foot, both relief
# walls, stubs down the front face and the bore axis from the top face, and
# the far chamfer face.
# * the relief's two walls from the front face, a baseline pair under the
#   bottom face 7 mm apart, their extension lines on the wall feet: the near
#   wall's "3.1" centred in its 12.4 mm span (line ~0.144), the far wall's
#   "19.1" left of the section's axis (line ~0.137), clear of the near wall's
#   extension line (x 0.318) and its own (x 0.382).
# * the relief height right of the cut, on the far wall (x 0.382) from its
#   foot to the roof: "6.5" at x ~0.402..0.410, 9 mm inside the border.
# * the pivot station 8 mm over the top face (y 0.236), from the front face's
#   top corner (x 0.306) to the bore axis (x 0.350, a sketched centreline
#   from y 0.179 to 0.231); its extension lines top out near y 0.2375.
# * the chamfer size on the bore's far rim (x 0.358..0.359; its extension
#   lines stand at x 0.356..0.361), its text LEFT of that rim so the
#   dimension line runs left, away from the border (farm 20261014T005925878Z:
#   text right put the line's end 1 mm off it).  The line runs under the
#   whole text block, out to the far end of its widest row, the one-row
#   "CLEARS ROD ... FILLET" above (~72 mm).  Centred 21 mm left of the rim
#   (x 0.338) the "0.3 min." / "X 45°" rows (~24 mm) end 6 mm short of
#   the extension lines and the line runs x ~0.302..0.364 at y ~0.2425, 4.8
#   mm over PivotZ's "11.1" (top 0.2377) and 8 mm over both of its extension
#   lines' tops (0.2345), crossing neither; the block (keep y 0.251, rows
#   from the line up to ~0.2585) stays 8 mm under the top border (0.2667)
#   and 66 mm right of the tap callout (to x ~0.236; TAP_CALLOUT_XY).
SECTION_KEEP = {
    "ReliefZ0": (
        (_sz(BODY_Z0) + _sz(RELIEF_Z0)) / 2.0,
        _sy(0.0) - 0.0085,
    ),
    "ReliefZ1": (_sz(_CZ) - 0.006, _sy(0.0) - 0.0155),
    "ReliefHeight": (_sz(BODY_Z1) + 0.012, _sy(RELIEF_HEIGHT / 2.0)),
    "PivotZ": (_sz((BODY_Z0 + _CZ) / 2.0), _sy(BLOCK_HEIGHT) + 0.008),
    "PivotChamferSize": (
        _sz(_CZ + PIVOT_BORE_DIA / 2.0 + PIVOT_BORE_TOP_CHAMFER) - 0.021,
        _sy(BLOCK_HEIGHT) + 0.023,
    ),
}
# The native SECTION A-A / SCALE caption's top centre, lowered 23 mm under the
# bottom face (default ~17 mm) so it stands ~4 mm under the far wall's line
# (~0.137): its rows ~0.127..0.133 and ~0.118..0.122, over the iso's note
# (top 0.097) and clear of the iso's sloping top at its left end.
SECTION_CAPTION_XY = (SECTION_CENTER[0], _sy(0.0) - 0.023)
# Section A-A cuts the set-screw tap on its axis: its cosmetic thread's major
# diameter prints there as two lines 5.7 mm either side of the axis (y 0.204,
# so 0.198 / 0.210) from the front face (x 0.306) to the bore wall (x 0.342),
# inside the section's ink, clear of every dimension (PivotZ's extension lines
# start at the top face, y 0.228; the bore axis's centreline at x 0.350).
# SolidWorks prints a section's thread annotation dashed, as a hidden thread
# (draw_sm_knife_mount, MHA review 2026-10-09), so it moves onto a visible
# thin continuous layer of its own.
SECTION_THREAD_LAYER = "TAP-THREAD-SECTION"
TAPPED_HOLE_NOTE = f"{SET_SCREW_TAP_SPEC.size} Tapped Hole"
_COSMETIC_THREAD_ANNOTATION = 1  # swAnnotationType_e.swCosmeticThread


def _offset_tap_wall_text(adapter: Any, annotations: list[Any]) -> None:
    """Park the tap wall's text on its leader shelf and read it back."""
    offset_dimension_text(adapter, annotations, {"TapWallMin": TAP_WALL_TEXT_XY})
    for raw in annotations:
        annotation = _early_bound(raw, "IAnnotation")
        if dimension_name(adapter, annotation) != "TapWallMin":
            continue
        display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
        position = annotation.GetPosition()
        if (
            not bool(display.OffsetText)
            or position is None
            or math.dist(position[:2], TAP_WALL_TEXT_XY) > _TEXT_SETTLE_M
        ):
            raise RuntimeError(
                f"tap wall text at {position!r}, not offset to {TAP_WALL_TEXT_XY!r}"
            )


def _place_flank_angle(adapter: Any, annotations: list[Any]) -> None:
    """Keep the flanks' angle arc short at the back mouth corner and move only
    its text off the part (draw_pd_transgear_thumbnut's countersink angle).

    An angular dimension's arc runs through its text's position: the arc
    goes first (no offset, RIGHT_KEEP), then the text, offset on a leader.
    Both positions are read back.
    """
    name = "VFlankAngle"
    matches = [item for item in annotations if dimension_name(adapter, item) == name]
    if len(matches) != 1:
        raise RuntimeError(f"v-block needs one native {name}, got {len(matches)}")
    annotation = _early_bound(matches[0], "IAnnotation")
    display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
    # An inherited offset would move only the text, leaving the arc behind.
    display.OffsetText = False
    if bool(display.OffsetText):
        raise RuntimeError("v-block flank angle offset could not be reset")
    if not annotation.SetPosition2(*RIGHT_KEEP[name], 0.0):
        raise RuntimeError("failed to position the v-block flank angle arc")
    arc_position = annotation.GetPosition()
    if (
        not arc_position
        or math.dist((float(arc_position[0]), float(arc_position[1])), RIGHT_KEEP[name])
        > 1e-5
    ):
        raise RuntimeError(f"v-block flank angle arc did not persist: {arc_position!r}")
    offset_dimension_text(adapter, [annotation], {name: FLANK_ANGLE_TEXT_XY})
    if not bool(display.OffsetText):
        raise RuntimeError("v-block flank angle text did not stay offset")
    position = annotation.GetPosition()
    if (
        not position
        or math.dist((float(position[0]), float(position[1])), FLANK_ANGLE_TEXT_XY)
        > 1e-5
    ):
        raise RuntimeError(f"v-block flank angle text did not persist: {position!r}")


def _section_thread_on_visible_layer(adapter: Any, section: Any) -> None:
    """Import section A-A's cosmetic thread and print it thin and solid.

    draw_fr_harmonic_base's section import (at least one native instance
    required) and draw_sm_knife_mount._layer_cosmetic_threads' layer: created
    thin continuous (``ILayerMgr::AddLayer``), its state and every thread
    annotation's layer read back.
    """
    threads = import_cosmetic_threads(adapter, section)
    if threads[1] < 1:
        raise RuntimeError("section A-A has no native cosmetic-thread instance")
    draw = adapter.currentModel
    manager = _early_bound(draw.GetLayerManager(), "ILayerMgr")
    layer = manager.GetLayer(SECTION_THREAD_LAYER)
    if layer is None:
        # COLORREF black, swLineCONTINUOUS (0), swLW_THIN (0).
        if (
            int(
                manager.AddLayer(
                    SECTION_THREAD_LAYER, "section A-A tap thread", 0, 0, 0
                )
            )
            != 1
        ):
            raise RuntimeError(f"failed to add layer {SECTION_THREAD_LAYER}")
        layer = manager.GetLayer(SECTION_THREAD_LAYER)
    layer = _early_bound(layer, "ILayer")
    layer.Visible = True
    if not bool(layer.Visible) or int(layer.Style) != 0 or int(layer.Width) != 0:
        raise RuntimeError(
            f"layer {SECTION_THREAD_LAYER} reads visible={layer.Visible!r}, style "
            f"{layer.Style!r}, width {layer.Width!r}; wanted visible thin continuous"
        )
    moved = 0
    for raw_annotation in _early_bound(section, "IView").GetAnnotations() or ():
        annotation = _early_bound(raw_annotation, "IAnnotation")
        if int(annotation.GetType()) != _COSMETIC_THREAD_ANNOTATION:
            continue
        annotation.Layer = SECTION_THREAD_LAYER
        if str(annotation.Layer or "") != SECTION_THREAD_LAYER:
            raise RuntimeError(
                f"a cosmetic thread refused layer {SECTION_THREAD_LAYER}"
            )
        moved += 1
    if moved < 1:
        raise RuntimeError("section A-A lists no cosmetic-thread annotation to layer")
    rebuild_drawing(adapter, label=f"cosmetic threads to {SECTION_THREAD_LAYER}")
    # SolidWorks' own "#4-40 Tapped Hole" note (the tap's hole callout states
    # the tap, rule 7) is swept once by finalize_drawing: farm r16 (no section
    # import) and r17 (section import, then a sweep here) each found exactly
    # one on the sheet, so the import adds none and the final sweep owns it.
    _telemetry.info(
        f"section A-A cosmetic threads: seeds/instances={threads!r}, {moved} on "
        f"{SECTION_THREAD_LAYER}"
    )


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open pen-v-block source", await adapter.open_model(str(SOURCE)))
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
        unit=part_drawing_unit("pn-pen-v-block"),
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Pen V-Block Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "pen v-block; brass; grip V, body relief, reamed pivot bore",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )
    # Explicit per-view scale: a view placed without one can silently
    # auto-scale, which shifts every coordinate-based pick on it.
    front = place_view(adapter, str(SOURCE), "*Back", *FRONT_CENTER, scale=VIEW_SCALE)
    right = place_view(adapter, str(SOURCE), "*Left", *RIGHT_CENTER, scale=VIEW_SCALE)
    bottom = place_view(
        adapter, str(SOURCE), "*Bottom", *BOTTOM_CENTER, scale=VIEW_SCALE
    )
    _orient_bottom_view(adapter, bottom)
    for view in (front, right, bottom):
        set_hidden_lines_removed(adapter, view)
    annotations = [
        annotation
        for view, keep, label in (
            (front, FRONT_KEEP, "front"),
            (right, RIGHT_KEEP, "paper end"),
            (bottom, BOTTOM_KEEP, "bottom"),
        )
        for annotation in curate_view_dimensions(
            adapter,
            view,
            keep=keep,
            view_label=label,
            dimensions_by_feature=DRAWING_DIMENSIONS,
        )
    ]
    # The section's reference sketches lie in its cutting plane, saved hidden:
    # a derived view takes them from the part as it stands when it is cut,
    # and selects them through its base view, so the section is cut and
    # curated while the part shows them (the bond cradle's recipe).
    line = [
        model_point_in_view(
            adapter,
            front,
            tuple(value / 1000.0 for value in point),
            label="section line",
        )
        for point in SECTION_LINE_MODEL_MM
    ]
    with part_sketches_shown(
        adapter,
        source_model,
        SECTION_REFERENCE_SKETCHES,
        label="section A-A references",
        base_view=front,
    ):
        section = create_section_view(
            adapter,
            front,
            line_start=line[0],
            line_end=line[1],
            view_xy=SECTION_CENTER,
            section_label="A",
            scale=VIEW_SCALE,
            label="pivot bore and set-screw tap section",
        )
        # Look along +X like the paper-end view beside it, so the front face
        # is on the left in both; a section shows no hidden lines (rule 9),
        # set before centring so the display change cannot shift the ink.
        _orient_section(adapter, section)
        set_hidden_lines_removed(adapter, section)
        _centre_section(adapter, section)
        annotations += curate_view_dimensions(
            adapter,
            section,
            keep=SECTION_KEEP,
            view_label="section A-A",
            dimensions_by_feature=DRAWING_DIMENSIONS,
        )
    position_section_caption(
        adapter, section, SECTION_CAPTION_XY, label="v-block section A-A"
    )
    _section_thread_on_visible_layer(adapter, section)
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=ISO_SCALE)
    # The iso too: a new view already reads Shaded With Edges, so
    # finalize_drawing's SetDisplayMode4 is a no-op that leaves its cosmetic
    # threads at draft quality (farm c0b95549c readback cosmetic_threads=False
    # on the hanger and rod). From HLR the shading call really changes the mode
    # and takes precision.
    set_hidden_lines_removed(adapter, iso)
    set_dimension_callouts(adapter, annotations, DIMENSION_CALLOUTS)
    set_dimension_callouts(
        adapter, annotations, DIMENSION_CALLOUTS_ABOVE, location="above"
    )
    # Natively the reamed diameter's leader runs rim to rim through the bore
    # and across its centre mark; one arrow on the near rim keeps it outside.
    pivot_dia = [a for a in annotations if dimension_name(adapter, a) == "PivotDia"]
    if len(pivot_dia) != 1:
        raise RuntimeError(f"expected one PivotDia dimension, found {len(pivot_dia)}")
    set_near_side_diameter(pivot_dia[0], "reamed pivot-bore diameter")
    # The flanks' angle: its short arc at the back mouth corner, out of the
    # view, and its text offset right of the view.
    _place_flank_angle(adapter, annotations)
    _offset_tap_wall_text(adapter, annotations)
    # Places (and the pivot band) are authored on the part; the sheet only
    # proves the import kept them.
    assert_imported_precision(adapter, annotations, DRAWING_PRECISION_BY_NAME)
    for view, label in ((front, "front"), (bottom, "bottom")):
        if not auto_center_marks(adapter, view, holes=True, size=0.0025):
            raise RuntimeError(f"failed to add ASME center marks to the {label} view")
    # PivotZ's extension line rises from the bore axis at the top face: the
    # axis's centreline is the geometry it lands on.
    _add_pivot_axis_centerline(adapter, section)

    # The native Hole Wizard callout on the tap's mouth, on the body's front face.
    tap_rim = scan_view_edges(front, label="front").circle_at(
        (PIVOT_BORE_X, SET_SCREW_Y, BODY_Z0),
        _TAP_DRILL_R,
        axis=(0.0, 0.0, 1.0),
        label="set-screw tap mouth",
    )
    tap_callout = add_native_hole_callout(
        adapter,
        front,
        edge=tap_rim.edge,
        callout_xy=TAP_CALLOUT_XY,
        label="rod set-screw tap into the pivot bore",
        process="TAP",
    )
    # The title block's THREADS row owns the general thread class (rule 2).
    omit_title_block_thread_class(tap_callout, label="rod set-screw tap")
    # Both rows end where the hole does, in the pivot bore, not through; the
    # drill row opens with its process word (rule 12).
    _set_tap_callout_text(tap_callout)
    set_hole_callout_precision(
        tap_callout, TAP_CALLOUT_PRECISION, label="rod set-screw tap"
    )
    rebuild_drawing(adapter, label="near-side diameter leaders")

    add_property_linked_note(adapter, "Isometric View Note", *ISO_NOTE_XY)

    # Materialize the iso's cosmetic thread before the strict final note cleanup;
    # otherwise its descriptive label first appears during the native drawing save.
    import_cosmetic_threads(adapter, iso)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Pen V-Block Manufacturing Drawing",
        scale=SHEET_SCALE,
        layout=SPEC.layout,
        redundant_note_substrings=(TAPPED_HOLE_NOTE,),
        expected_redundant_notes=1,
    )


# The tap runs from the front face into the pivot bore (Hole Wizard "up to
# next"), which the native callout prints as THRU on both its drill row
# ("Ø2.26 THRU", callout-above) and its thread row ("TAP 4-40 UNC THRU",
# prefix).  The block is not drilled through, so both rows name where the hole
# ends instead (draw_dt_cone_tip_block's pinch-thread "TO SLOT" recipe): only
# the extent variable is replaced, the size and thread variables stay live.
# r13: "Ø 2.26 INTO PIVOT BORE" carried no process word, so the drill row
# opens with DRILL (rule 12).
_TAP_END = "INTO PIVOT BORE"
# The through-next tap's one Hole Wizard length variable, its drill
# diameter, prints .XXX.
TAP_CALLOUT_PRECISION = {"hw-tapdrldia": 3}
_THRU_TOKEN = "<hw-thru>"
_DRILL_WORD = "DRILL"
# The drill row's size variable: <hw-tapdrldia> (or <hw-thrutapdrldia> for a
# through tap); the thread row carries <hw-threaddesc>.
_TAP_DRILL_TOKEN = "tapdrldia>"
# swDimensionTextParts_e: each definition part and the part SetText writes.
_DEFINITION_TO_WRITABLE = {5: 1, 6: 2, 7: 3, 8: 4}


def _tap_callout_definitions(definitions: dict[int, str]) -> dict[int, str]:
    """Replace the native THRU extent on both rows with ``_TAP_END`` and open
    the drill row with ``_DRILL_WORD``; every native variable stays."""
    if set(definitions) != set(_DEFINITION_TO_WRITABLE):
        raise RuntimeError(f"unexpected tap callout definition parts: {definitions!r}")
    original = "\n".join(definitions.values())
    if original.count(_THRU_TOKEN) != 2 or "<hw-threaddesc>" not in original:
        raise RuntimeError(f"unexpected native tap callout definition: {definitions!r}")
    updated = {}
    drill_rows = 0
    for part, text in definitions.items():
        rows = text.replace(_THRU_TOKEN, _TAP_END).split("\n")
        for index, row in enumerate(rows):
            if _TAP_DRILL_TOKEN not in row:
                continue
            if "<hw-threaddesc>" in row or "TAP" in row or _DRILL_WORD in row:
                raise RuntimeError(f"tap drill row shares its text: {definitions!r}")
            body = row.lstrip()
            rows[index] = f"{row[: len(row) - len(body)]}{_DRILL_WORD} {body}"
            drill_rows += 1
        updated[part] = "\n".join(rows)
    rewritten = "\n".join(updated.values())
    if (
        drill_rows != 1
        or rewritten.count(_TAP_END) != 2
        or "<hw-threaddesc>" not in rewritten
    ):
        raise RuntimeError(f"tap callout rewrite lost its rows: {updated!r}")
    return updated


def _tap_callout_resolved(resolved: str) -> bool:
    """Both rows end in the bore; exactly one row, the drill's, opens DRILL."""
    drill = [row for row in resolved.split("\n") if _DRILL_WORD in row]
    return (
        resolved.count(_TAP_END) == 2
        and "THRU" not in resolved
        and len(drill) == 1
        and drill[0].lstrip().startswith(f"{_DRILL_WORD} ")
        and _TAP_END in drill[0]
        and "UNC" not in drill[0]
    )


def _set_tap_callout_text(display: Any) -> None:
    """Write the drill word and into-bore extent on the native callout and
    read both back."""
    native = _early_bound(display, "IDisplayDimension")
    definitions = {
        part: str(native.GetText(part) or "") for part in _DEFINITION_TO_WRITABLE
    }
    updated = _tap_callout_definitions(definitions)
    for definition_part, writable_part in _DEFINITION_TO_WRITABLE.items():
        if updated[definition_part] != definitions[definition_part]:
            native.SetText(writable_part, updated[definition_part])  # void return
    persisted = {
        part: str(native.GetText(part) or "") for part in _DEFINITION_TO_WRITABLE
    }
    resolved = "\n".join(
        str(native.GetText(part) or "") for part in _DEFINITION_TO_WRITABLE.values()
    )
    if persisted != updated or not _tap_callout_resolved(resolved):
        raise RuntimeError(
            "tap callout drill word / into-bore extent did not persist: "
            f"definitions={persisted!r}, resolved={resolved!r}"
        )


# ASME Y14.2 runs a centreline a short, uniform distance past its feature: 3 mm
# on paper, 0.75 model mm at 4:1.  Above the top face it runs on under PivotZ's
# axis extension line (which continues from it); below the roof it ends in the
# relief's open air.
_CENTERLINE_OVERSHOOT_MM = 3.0 / (VIEW_SCALE[0] / VIEW_SCALE[1])
_SW_LINE_CENTER = 4  # swLineStyles_e.swLineCENTER


def _section_axes(
    adapter: Any, native: Any
) -> tuple[tuple[float, float], tuple[float, float]]:
    """Sheet directions of model +z and +y (1 mm each) in section A-A, read
    behind the projection barrier (``_drawing_detail_projection``)."""
    native.UpdateViewDisplayGeometry()
    x = PIVOT_BORE_X / 1000.0
    origin, plus_z, plus_y = model_points_in_view(
        adapter,
        native,
        (
            (x, _CY / 1000.0, _CZ / 1000.0),
            (x, _CY / 1000.0, (_CZ + 1.0) / 1000.0),
            (x, (_CY + 1.0) / 1000.0, _CZ / 1000.0),
        ),
        label="v-block section A-A axes",
        names=("origin", "plus z", "plus y"),
    )
    return (
        (plus_z[0] - origin[0], plus_z[1] - origin[1]),
        (plus_y[0] - origin[0], plus_y[1] - origin[1]),
    )


def _orient_section(adapter: Any, section: Any) -> None:
    """Look along +X, toward the free end, as the paper-end view does: +z to
    the sheet's right, +y up, so the body's front face is on the left in both.

    SolidWorks cuts A-A looking toward the paper end (farm 20261014T003549Z:
    front face on the right), which mirrors the end view beside it and reads
    the V and the relief as located from opposite faces.  Looking along +X
    with +y up puts +z on the right, a right-handed pair on the sheet; a
    left-handed pair is the cut looking the other way, so the cut direction
    is reversed, then the view turned until +z reads right
    (draw_pn_pen_hanger ``_orient_section``).
    """
    native = _early_bound(section, "IView")
    right, up = _section_axes(adapter, native)
    if right[0] * up[1] - right[1] * up[0] < 0.0:
        cut = _early_bound(native.GetSection(), "IDrSection")
        reversed_cut = not bool(cut.GetReversedCutDirection())
        cut.SetReversedCutDirection(reversed_cut)
        rebuild_drawing(adapter, label="v-block section reversed")
        if bool(cut.GetReversedCutDirection()) != reversed_cut:
            raise RuntimeError("v-block section A-A cut direction did not persist")
        right, up = _section_axes(adapter, native)
    native.Angle = float(native.Angle) - math.atan2(right[1], right[0])
    rebuild_drawing(adapter, label="v-block section turned")
    right, up = _section_axes(adapter, native)
    tolerance = 1e-7
    if (
        right[0] <= 0.0
        or abs(right[1]) > tolerance
        or up[1] <= 0.0
        or abs(up[0]) > tolerance
    ):
        raise RuntimeError(
            f"v-block section A-A does not look along +X: {right=}, {up=}"
        )
    _telemetry.info(f"v-block section A-A angle={float(native.Angle):.6f} rad")


def _centre_section(adapter: Any, section: Any) -> None:
    """Land the cut's centre (the bore axis at mid-height) on SECTION_CENTER.

    Placed by projection, not by outline: every SECTION_KEEP position is
    computed from where that point projects, and a reversed cut may leave the
    view off its creation target (draw_pd_transgear_thumbnut).
    ``SetViewPosition`` moves the ink by the difference from the Position it
    reads (draw_pn_pen_hanger ``_centre_section``).
    """
    native = _early_bound(section, "IView")
    anchor = (PIVOT_BORE_X / 1000.0, _CY / 1000.0, _CZ / 1000.0)
    for attempt in range(4):
        native.UpdateViewDisplayGeometry()
        projected = model_point_in_view(
            adapter, native, anchor, label=f"v-block section A-A centre, pass {attempt}"
        )
        if math.dist(projected, SECTION_CENTER) <= 1e-4:
            break
        position = tuple(float(value) for value in native.Position)
        moved = [
            position[axis] + SECTION_CENTER[axis] - projected[axis] for axis in (0, 1)
        ]
        if not native.SetViewPosition(double_array(moved), False):
            raise RuntimeError("failed to re-centre v-block section A-A")
        rebuild_drawing(adapter, label="v-block section re-centred")
    settle_detail_projection(
        adapter,
        native,
        anchor,
        ink_xy=SECTION_CENTER,
        tolerance_xy=(0.0005, 0.0005),
        label="v-block section A-A",
    )


def _add_pivot_axis_centerline(adapter: Any, section: Any) -> None:
    """Draw the pivot bore's axis through section A-A, from the relief roof to
    the top face plus the overshoot.

    Farm 2229cc4db: ``InsertCenterLine2`` on the bore face picked at (z 10,
    y 15) returned None; in this cut the bore wall is split by the tap on the
    near side and trimmed by the chamfer on top, so neither a face nor a
    wall-edge pair is a dependable handle.  The model axis is projected
    through the section's own transform instead.  r13 (98ffd38a8) drew it
    sheet-owned after ``EditSheet`` (dt_cone_pivot_post's recipe) and passed
    its colour readback, yet no axis printed: the reviewer saw PivotZ's 9.0
    end in mid-air.  So this is draw_fr_top_frame's view-owned recipe, which
    reads the line back where it was authored: the section activated, each
    sheet point mapped through the view sketch's ModelToSketchTransform, the
    line added straight to the database (an inferred endpoint snaps onto
    nearby ink), its endpoints read back, black in the CENTER font.
    """
    native = _early_bound(section, "IView")
    native.UpdateViewDisplayGeometry()
    ends = [
        model_point_in_view(
            adapter,
            section,
            (PIVOT_BORE_X / 1000.0, y / 1000.0, _CZ / 1000.0),
            label=f"section A-A pivot axis at y {y:g}",
        )
        for y in (
            RELIEF_HEIGHT - _CENTERLINE_OVERSHOOT_MM,
            BLOCK_HEIGHT + _CENTERLINE_OVERSHOOT_MM,
        )
    ]
    length = BLOCK_HEIGHT - RELIEF_HEIGHT + 2.0 * _CENTERLINE_OVERSHOOT_MM
    # The axis must print square to the top face and at true length.
    if (
        abs(ends[0][0] - ends[1][0]) > 1e-6
        or abs((ends[1][1] - ends[0][1]) - length * _S) > 1e-6
    ):
        raise RuntimeError(f"section A-A pivot axis projects as {ends!r}")
    middle = ((ends[0][0] + ends[1][0]) / 2.0, (ends[0][1] + ends[1][1]) / 2.0)
    outline = tuple(float(v) for v in native.GetOutline())
    if not (
        outline[0] < middle[0] < outline[2] and outline[1] < middle[1] < outline[3]
    ):
        raise RuntimeError(
            f"section A-A pivot axis {middle!r} falls outside the section {outline!r}"
        )
    draw = adapter.currentModel
    drawing = _early_bound(draw, "IDrawingDoc")
    if not drawing.ActivateView(view_name(adapter, section)):
        raise RuntimeError("failed to activate section A-A for the pivot axis")
    draw.ClearSelection2(True)
    sketch = _early_bound(native.GetSketch(), "ISketch")
    transform = _early_bound(sketch.ModelToSketchTransform, "IMathTransform")
    utility = _early_bound(adapter.swApp.GetMathUtility(), "IMathUtility")
    points = [
        tuple(
            _early_bound(
                _early_bound(
                    utility.CreatePoint(double_array([x, y, 0.0])), "IMathPoint"
                ).MultiplyTransform(transform),
                "IMathPoint",
            ).ArrayData
        )
        for x, y in ends
    ]
    manager = _early_bound(draw.SketchManager, "ISketchManager")
    previous_add_to_db = bool(manager.AddToDB)
    manager.AddToDB = True
    try:
        centerline = manager.CreateCenterLine(*points[0], *points[1])
    finally:
        manager.AddToDB = previous_add_to_db
    if centerline is None:
        raise RuntimeError("failed to create the pivot-bore centreline in section A-A")
    _assert_centreline_placed(adapter, centerline, points)
    # A view sketch line otherwise prints in the under-defined sketch blue.
    segment = _early_bound(centerline, "ISketchSegment")
    segment.Color = 0  # COLORREF black
    segment.Style = _SW_LINE_CENTER
    draw.ClearSelection2(True)
    rebuild_drawing(adapter, label="section A-A pivot axis")
    if int(segment.Color) != 0 or int(segment.Style) != _SW_LINE_CENTER:
        raise RuntimeError(
            "pivot-bore centreline did not keep black centreline font: "
            f"color={int(segment.Color)}, style={int(segment.Style)}"
        )
    _assert_centreline_placed(adapter, centerline, points)
    # Against the keep maps' arithmetic (x 0.350): logged, not gated.
    _telemetry.info(
        f"section A-A pivot axis drawn {ends[0]!r} -> {ends[1]!r} "
        f"(view sketch {points[0]!r} -> {points[1]!r}); "
        f"keep-map axis x {_sz(_CZ):.4f}, off by {middle[0] - _sz(_CZ):+.5f} m"
    )


def _assert_centreline_placed(
    adapter: Any, segment: Any, points: list[tuple[float, ...]]
) -> None:
    """Fail when the axis's endpoints are not where they were authored
    (draw_fr_top_frame ``_assert_centreline_placed``)."""
    line = _early_bound(segment, "ISketchLine")
    for expected, accessor in zip(points, ("GetStartPoint2", "GetEndPoint2")):
        point = _early_bound(adapter._get_attr_or_call(line, accessor), "ISketchPoint")
        actual = [
            float(adapter._get_attr_or_call(point, axis)) for axis in ("X", "Y", "Z")
        ]
        drift = max(abs(a - b) for a, b in zip(actual, expected))
        if drift > 1e-9:
            raise RuntimeError(
                f"section A-A pivot axis {accessor[3:-6].lower()} point sits "
                f"{drift * 1000.0:.4g} mm from where it was authored "
                f"({actual} instead of {list(expected)})"
            )


def _orient_bottom_view(adapter: Any, view: Any) -> None:
    """Make *Bottom the third-angle underside of the displayed *Back face."""
    native = _early_bound(view, "IView")
    native.Angle = math.pi
    rebuild_drawing(adapter, label="v-block underside orientation")
    applied = float(native.Angle)
    if (
        not math.isfinite(applied)
        or abs(math.remainder(applied - math.pi, math.tau)) > 1e-9
    ):
        raise RuntimeError(
            f"v-block underside rotation did not take: {applied!r} rad, expected pi"
        )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[PART_STEM])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
