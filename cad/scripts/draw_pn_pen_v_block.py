r"""Create the curated machinist drawing for the pen v-block.

The SLDPRT remains authoritative.  This recipe supplies only the v-block's
views, the placement of its imported model dimensions, the two native hole
callouts and the isometric's scale note; sheet/template and export behavior
lives in ``_drawing_common``.  Dimension import and curation live in
``_drawing_hidden_sketches`` (the part saves its reference sketches hidden;
each shows in the view that dimensions it); places and the pivot band are
authored on the part (``pn_pen_v_block_spec``).

The views follow the part frame (x 0 the paper end, z 0 the front face); every
feature is located across the depth from the front face:

* front: ``*Back`` looks at the z 0 face the set screw enters, so the paper
  end is on the RIGHT.  It carries the chamfered outline and the tap's two
  coordinates, the tap's native callout, and section A-A's cutting line on
  the pivot-bore axis.
* right (third angle, right of the ``*Back`` face): ``*Left``, the paper end,
  shows the V in solid lines -- its front mouth edge from the front face,
  mouth width, apex height, and the block depth.
* bottom: ``*Bottom`` turned 180 degrees to keep the front view's X, looking
  up into the V and the relief; through the relief the roof shows both
  vertical bores.  It carries the relief's start station and corner radius,
  the pivot bore (station and reamed, banded diameter) and the lightening
  bore's two stations with its native callout.
* section A-A through the pivot-bore axis: bore, tap and relief in one cut,
  looking toward the free end as the paper-end view does (front face on the
  left in both); it carries the relief's near wall, width and height, the
  pivot bore's station from the front face, and the bore's top chamfer.

No datums, frames, basic dimensions or roughness (drawing-simplicity-policy.md
rules 5 and 6), no note block: material and finish ride the title block.  The
sheet runs 4:1; the isometric stays 1:1.

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
from _drawing_dimensions import assert_imported_precision, set_dimension_callouts
from _drawing_edges import scan_view_edges
from _drawing_hidden_sketches import curate_view_dimensions, part_sketches_shown
from _drawing_hole_callout import add_native_hole_callout
from _drawing_leaders import set_near_side_diameter
from _drawing_notes import add_property_linked_note
from _drawing_projection import model_point_in_view, model_points_in_view
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_sections import create_section_view
from _drawing_view_display import set_hidden_lines_removed
from _hole_callout_thread_class import omit_title_block_thread_class
from _hole_spec import TAP_DRILL_MM
from _paths import CAD_ROOT
from _section_axis import position_section_caption
from _session import run_build
import _telemetry
from pn_pen_v_block_spec import (
    BLOCK_DEPTH,
    BLOCK_HEIGHT,
    BLOCK_LENGTH,
    CHAMFER,
    DIMENSION_CALLOUTS,
    DIMENSION_CALLOUTS_ABOVE,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    ISOMETRIC_VIEW_SCALE,
    LIGHTENING_DIA,
    LIGHTENING_X,
    PIVOT_BORE_DIA,
    PIVOT_BORE_TOP_CHAMFER,
    PIVOT_BORE_X,
    RELIEF_CORNER_R,
    RELIEF_HEIGHT,
    RELIEF_WIDTH,
    RELIEF_X0,
    SECTION_REFERENCE_SKETCHES,
    SET_SCREW_TAP_SPEC,
    SET_SCREW_Y,
    V_APEX_Y,
)


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

# Sheet layout (meters).  At 4:1 the 36 x 18 x 18 block is 144 x 72 mm in the
# front and bottom views and 72 x 72 in the end view and the section.  The
# front (x 0.040..0.184, y 0.156..0.228) stacks over the bottom view (y
# 0.054..0.126), both left of the title block (x 0.216); the end view
# (x 0.215..0.287) and section A-A (x 0.324..0.396) share the front's row.
# The end view sits 31 mm right of the front and 37 mm left of the section
# (not centred between them): the relief's near-wall station needs the wider
# gap for its function rows (SECTION_KEEP), the V's mouth station the
# narrower one (RIGHT_KEEP).
# The isometric runs 3:2 (pn_pen_v_block_spec): its ink is 1.5x the 38.3 x
# 34.5 mm the 1:1 view measured on farm 20261014T005925878Z, 57.5 x 51.8,
# centred 1.8 mm above its ink.  Centred at (0.315, 0.097) it fills x
# 0.286..0.344, y 0.069..0.121: 9.8 mm right of the reamed diameter's callout
# (to x 0.2764, y 0.100 up), 4 mm over the title block (top 0.0651), under the
# end view's depth row (y 0.132, to x 0.287) and section A-A's 2.500 (y 0.138
# up).  Its silhouette slopes down to the right from its top vertex (45%
# across), so at the caption's left end (x 0.330) its ink tops out ~0.110,
# 10 mm under the caption (bottom ~0.120 there).  2:1 (77 x 69 mm) fits
# nowhere between the views, the caption and the title block (65 mm tall at
# most).
# Its scale note (top-left anchor, ~58 mm wide) beside it at mid-height, from
# x 0.350 (6 mm right of the ink) to ~0.408, 11 mm inside the border (0.4188),
# under the caption and over the title block.
FRONT_CENTER = (0.112, 0.192)
BOTTOM_CENTER = (FRONT_CENTER[0], 0.090)
RIGHT_CENTER = (0.251, FRONT_CENTER[1])
SECTION_CENTER = (0.360, FRONT_CENTER[1])
ISO_CENTER = (0.315, 0.097)
ISO_NOTE_XY = (0.350, 0.097)
TAP_CALLOUT_XY = (0.235, 0.252)
# Above-left of the bottom view, the lightening bore's near (upper-left) rim
# 13 mm down-right of the text: one arrow there, no line through the bore
# (set_near_side_diameter), clear of LighteningZ's extension line at the
# view's z 0 edge (y 0.126) left of x 0.040, which ends 11 mm below the text.
LIGHTENING_CALLOUT_XY = (0.060, 0.140)
# Section A-A's cutting line: the pivot-bore axis (x = PIVOT_BORE_X), 1.5 mm
# past the bottom and top faces, so the cut closes across the whole block.
SECTION_LINE_MODEL_MM = (
    (PIVOT_BORE_X, -1.5, 0.0),
    (PIVOT_BORE_X, BLOCK_HEIGHT + 1.5, 0.0),
)

_CX, _CY, _CZ = BLOCK_LENGTH / 2.0, BLOCK_HEIGHT / 2.0, BLOCK_DEPTH / 2.0
_TAP_DRILL_R = TAP_DRILL_MM[SET_SCREW_TAP_SPEC.size] / 2.0


def _fx(model_x_mm: float) -> float:
    """Sheet X of a model-X point in the front (``*Back``) and bottom views:
    both run model +X to the sheet's left (the paper end on the right)."""
    return FRONT_CENTER[0] - (model_x_mm - _CX) * _S


def _fy(model_y_mm: float) -> float:
    return FRONT_CENTER[1] + (model_y_mm - _CY) * _S


def _bz(model_z_mm: float) -> float:
    """Sheet Y of a model-Z point in the turned bottom view: the front face
    (z 0) toward the front view above it."""
    return BOTTOM_CENTER[1] - (model_z_mm - _CZ) * _S


def _rz(model_z_mm: float) -> float:
    """Sheet X of a model-Z point in the paper-end view: z 0 on its left, next
    to the front view."""
    return RIGHT_CENTER[0] + (model_z_mm - _CZ) * _S


def _ry(model_y_mm: float) -> float:
    return RIGHT_CENTER[1] + (model_y_mm - _CY) * _S


def _sz(model_z_mm: float) -> float:
    """Sheet X of a model-Z point in section A-A: it looks toward the free end
    (+X), as the paper-end view beside it does, so z 0 (the front face, where
    the tap enters) is on its LEFT in both (``_orient_section``)."""
    return SECTION_CENTER[0] + (model_z_mm - _CZ) * _S


def _sy(model_y_mm: float) -> float:
    return SECTION_CENTER[1] + (model_y_mm - _CY) * _S


# Per-view survivors of the marked-dimension import: parametric name -> sheet
# position.
# Front: overall length on top over the free-end chamfer leg, whose wide
# callout sits right of the leg so the length's end extension line clears it;
# height left; the tap's coordinates from the paper-end/bottom corner sit right
# of and below the view, the station clear of section A-A's cutting-line end.
FRONT_KEEP = {
    "Length": (_fx(_CX), _fy(BLOCK_HEIGHT) + 0.028),
    "Chamfer2dx": (_fx(BLOCK_LENGTH - CHAMFER) + 0.023, _fy(BLOCK_HEIGHT) + 0.012),
    "Height": (_fx(BLOCK_LENGTH) - 0.014, _fy(_CY)),
    "SetScrewY": (_fx(0.0) + 0.010, _fy(SET_SCREW_Y / 2.0)),
    "SetScrewX": (_fx(PIVOT_BORE_X / 4.0), _fy(0.0) - 0.012),
}
# Paper end: the depth under the view; one row above it the V's front mouth
# edge from the front face (z 0, the view's left edge) chained with the mouth
# width.  Both are .XXX, so each carries its function under its value
# (pn_pen_v_block_spec.DIMENSION_CALLOUTS), the text block centred on its
# keep point, rows 5.6 mm apart, the dimension line ~1 mm under the last row
# (r9 sheet 20261014T011745149Z).
# * the mouth's "12.000" / "CENTRES MARKER" (~40 mm) centred between its
#   extension lines (x 0.227 / 0.275, 48 mm apart) at y 0.149: value row in
#   the V's mouth, the function row ~0.1445..0.148, its line ~0.1435, 6 mm
#   over the depth's "18.00" (top 0.1377).
# * the mouth edge's 12 mm span would cramp its text, so "3.000" /
#   "CENTRES" / "MARKER" (~21 mm wide) sits left of the z 0 corner, its right
#   end 3.5 mm short of the corner's extension line (x 0.215): x ~0.191..0.212,
#   rows from ~0.1538 (1 mm under the front view's SetScrewY extension line,
#   y 0.156, which ends at x 0.195) down to ~0.139, its line at ~0.138, 6 mm
#   over the depth's line (0.132) and 10 mm over the reamed diameter's
#   callout (top 0.128); the front view's SetScrewX extension line (x 0.184)
#   stays 6.5 mm left.
# The apex height right of the view.
RIGHT_KEEP = {
    "Depth": (RIGHT_CENTER[0], _ry(0.0) - 0.020),
    "VMouth": (RIGHT_CENTER[0], _ry(0.0) - 0.007),
    "VMouthZ": (_rz(0.0) - 0.014, _ry(0.0) - 0.0095),
    "VApexY": (_rz(BLOCK_DEPTH) + 0.012, _ry(V_APEX_Y / 2.0)),
}
# Bottom: all three stations from the paper end below the view, a baseline
# stack nested shortest-innermost (relief step x 0.144, pivot axis 0.134,
# lightening axis 0.092; rows 10 mm apart down to y 0.024, 11 mm above the
# border) so no extension line crosses a dimension line under it.  That frees
# the gap above the view for the relief corner's radius: its text sits 45 deg
# up-right of the front-face corner arc (centre x 0.140, y 0.112), so the
# radial leader runs out from the arc's midpoint across only the bottom face's
# land; the text (x 0.153..0.168) is clear of the front view's SetScrewX line
# (y 0.142) above and the reamed diameter's callout (from x 0.188) right.  The
# lightening bore's depth station left of the free end, its extension lines
# from that end's front-face corner (x 0.040, y 0.126) and from the bore's
# level on the same edge (y 0.090), whose reference chord (shown here, on the
# free end's edge) carries on along the centreline to the centre mark.  The
# reamed diameter's wide callout wholly right of the paper end, its single
# arrow on the near rim (set_near_side_diameter), so no leader crosses the bore.
BOTTOM_KEEP = {
    "ReliefX0": (_fx(RELIEF_X0 / 2.0), _bz(BLOCK_DEPTH) - 0.010),
    "PivotX": (_fx(PIVOT_BORE_X / 2.0), _bz(BLOCK_DEPTH) - 0.020),
    "LighteningX": (_fx(LIGHTENING_X / 2.0), _bz(BLOCK_DEPTH) - 0.030),
    "LighteningZ": (_fx(BLOCK_LENGTH) - 0.012, _bz(_CZ / 2.0)),
    "ReliefCornerR": (
        _fx(RELIEF_X0 + RELIEF_CORNER_R) + 0.020,
        _bz((BLOCK_DEPTH - RELIEF_WIDTH) / 2.0 + RELIEF_CORNER_R) + 0.020,
    ),
    "PivotDia": (_fx(0.0) + 0.048, _bz(0.0) - 0.008),
}
# Section A-A looks the same way as the paper-end view beside it: z 0 at
# x 0.324 on the LEFT, the bottom face at y 0.156, the top at 0.228.  Its two
# reference sketches show here (they lie in the cut), every chord on a drawn
# edge: both relief walls, stubs down the front face and the bore axis from
# the top face, and the far chamfer face.
# * the relief's near wall from the front face and its width, a chain under
#   the bottom face, their extension lines on the wall feet.  Both are .XXX
#   and carry their function under the value (pn_pen_v_block_spec), the text
#   block centred on its keep point, rows 5.6 mm apart, the dimension line
#   ~1 mm under the last row.  The 2.500's 10 mm span is too short for its
#   text, so "2.500" / "CLEARS" / "MARKER BODY" (~31 mm wide) sits left of
#   the z 0 foot, x ~0.290..0.322: 3 mm right of the end view's depth
#   extension line (x 0.287, down to y 0.132), 2 mm short of the foot's; its
#   value's top (~0.1538) 2 mm under the end view's apex-height arrow and
#   extension line (y 0.156, to x 0.300); its line at ~0.138.  The width's
#   "13.000" / "CLEARS MARKER" / "BODY MHA-VN-060" (~42 mm) centred between
#   the wall feet's extension lines (x 0.334 / 0.386, 5 mm a side) one notch
#   lower, its line at ~0.1346: 3.5 mm under the 2.500's, so neither line
#   runs along the other (r9 printed the width's arrows outside its span).
# * the relief height right of the cut, on the far wall (z 15.5, x 0.386)
#   from its foot to the roof.
# * the pivot station 8 mm over the top face (y 0.236), from the front face's
#   top corner (x 0.324) to the bore axis (x 0.360, a sketched centreline
#   from y 0.179 to 0.231); its extension lines top out near y 0.2375.
# * the chamfer size on the bore's far rim (x 0.368..0.369, the z 11 side; its
#   extension lines stand at x 0.366..0.371), its text LEFT of that rim so the
#   dimension line runs left, away from the border (farm 20261014T005925878Z:
#   text right put the line's end 1 mm off it).  The line runs under the
#   whole text block, out to the far end of its widest row, the one-row
#   "CLEARS ROD ... FILLET" above (~72 mm).  Centred 21 mm left of the rim
#   (x 0.348) the "0.3 min." / "X 45 DEG" rows (~24 mm) end 6 mm short of
#   the extension lines and the line runs x ~0.312..0.374 at y ~0.2425, 4.8
#   mm over PivotZ's "9.00" (top 0.2377) and 8 mm over both of its extension
#   lines' tops (0.2345), crossing neither; the block (keep y 0.251, rows
#   from the line up to ~0.2585) stays 8 mm under the top border (0.2667)
#   and ~56 mm right of the tap callout (to x 0.2563).
SECTION_KEEP = {
    "ReliefZ0": (_sz(0.0) - 0.018, _sy(0.0) - 0.0095),
    "ReliefWidth": (_sz(_CZ), _sy(0.0) - 0.013),
    "ReliefHeight": (_sz(BLOCK_DEPTH) + 0.012, _sy(RELIEF_HEIGHT / 2.0)),
    "PivotZ": (_sz(_CZ / 2.0), _sy(BLOCK_HEIGHT) + 0.008),
    "PivotChamferSize": (
        _sz(_CZ + PIVOT_BORE_DIA / 2.0 + PIVOT_BORE_TOP_CHAMFER) - 0.021,
        _sy(BLOCK_HEIGHT) + 0.023,
    ),
}
# The native SECTION A-A / SCALE caption's top centre, lowered 29 mm under the
# bottom face (default ~17 mm) so it stands ~8 mm under the width's line
# (~0.1346): its rows ~0.1205..0.1268 and ~0.112..0.116, over the iso's note
# (top 0.097) and 10 mm clear of the iso's sloping top at its left end.
SECTION_CAPTION_XY = (SECTION_CENTER[0], _sy(0.0) - 0.029)


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
        adapter, property_view=PART_STEM, scale=SHEET_SCALE, layout=SPEC.layout
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
    # Places (and the pivot band) are authored on the part; the sheet only
    # proves the import kept them.
    assert_imported_precision(adapter, annotations, DRAWING_PRECISION_BY_NAME)
    for view, label in ((front, "front"), (bottom, "bottom")):
        if not auto_center_marks(adapter, view, holes=True, size=0.0025):
            raise RuntimeError(f"failed to add ASME center marks to the {label} view")
    # PivotZ's extension line rises from the bore axis at the top face: the
    # axis's centreline is the geometry it lands on.
    _add_pivot_axis_centerline(adapter, section)

    # Native Hole Wizard callouts on each hole's visible rim: the tap's mouth on
    # the front face, the lightening bore where it breaks through the relief roof.
    tap_rim = scan_view_edges(front, label="front").circle_at(
        (PIVOT_BORE_X, SET_SCREW_Y, 0.0),
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
    lightening_rim = scan_view_edges(bottom, label="bottom").circle_at(
        (LIGHTENING_X, RELIEF_HEIGHT, _CZ),
        LIGHTENING_DIA / 2.0,
        axis=(0.0, 1.0, 0.0),
        label="lightening bore at the relief roof",
    )
    lightening_callout = add_native_hole_callout(
        adapter,
        bottom,
        edge=lightening_rim.edge,
        callout_xy=LIGHTENING_CALLOUT_XY,
        label="free-end lightening bore",
        process="DRILL",
    )
    # Natively its leader ran through the bore and across its centre mark:
    # one arrow on the near rim, the leader wholly outside.
    set_near_side_diameter(
        lightening_callout.GetAnnotation(), "lightening bore callout"
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
        redundant_note_substrings=(f"{SET_SCREW_TAP_SPEC.size} Tapped Hole",),
        expected_redundant_notes=1,
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
    the sheet's right, +y up, so the front face (z 0) is on the left in both.

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
    wall-edge pair is a dependable handle.  dt_cone_pivot_post's section
    recipe instead: the model axis projected through the section's own
    transform into sheet space, a sheet-owned centreline between the ends,
    black in the CENTER font, read back.
    """
    _early_bound(section, "IView").UpdateViewDisplayGeometry()
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
    outline = tuple(float(v) for v in _early_bound(section, "IView").GetOutline())
    if not (
        outline[0] < middle[0] < outline[2] and outline[1] < middle[1] < outline[3]
    ):
        raise RuntimeError(
            f"section A-A pivot axis {middle!r} falls outside the section {outline!r}"
        )
    drawing = _early_bound(adapter.currentModel, "IDrawingDoc")
    # EditSheet makes the line sheet-owned; the ends are already in sheet space.
    drawing.EditSheet()
    sketch_manager = _early_bound(adapter.currentModel.SketchManager, "ISketchManager")
    centerline = sketch_manager.CreateCenterLine(
        ends[0][0], ends[0][1], 0.0, ends[1][0], ends[1][1], 0.0
    )
    if centerline is None:
        raise RuntimeError("failed to create the pivot-bore centreline in section A-A")
    # A sheet sketch line otherwise prints in the under-defined sketch blue.
    segment = _early_bound(centerline, "ISketchSegment")
    segment.Color = 0  # COLORREF black
    segment.Style = _SW_LINE_CENTER
    adapter.currentModel.ClearSelection2(True)
    rebuild_drawing(adapter, label="section A-A pivot axis")
    if int(segment.Color) != 0 or int(segment.Style) != _SW_LINE_CENTER:
        raise RuntimeError(
            "pivot-bore centreline did not keep black centreline font: "
            f"color={int(segment.Color)}, style={int(segment.Style)}"
        )
    # Against the keep maps' arithmetic (x 0.360): logged, not gated.
    _telemetry.info(
        f"section A-A pivot axis drawn {ends[0]!r} -> {ends[1]!r}; "
        f"keep-map axis x {_sz(_CZ):.4f}, off by {middle[0] - _sz(_CZ):+.5f} m"
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
