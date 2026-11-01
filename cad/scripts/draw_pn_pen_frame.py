r"""Create the curated machinist drawing for the pen frame (stirrup).

The SLDPRT remains authoritative.  This recipe supplies only the frame's views,
the dimension layout and the tapped-hole callout; sheet/template and export
behavior lives in ``_drawing_common``.  Dimension import and curation live in
``_drawing_dimension_import``.

The pen frame is a flat rectangular brass ring with a centred, corner-filleted
window and a #4-40 thumb-screw hole tapped up through the bottom rail.  Every
size is a native associative dimension marked on the part
(``pn_pen_frame_spec``): the front view carries the outer envelope, the
window's size, its lower-left corner from the left and bottom faces and the
4X window-corner radius; the bottom view, looking up at the tapped rail,
carries the depth, the hole's two coordinates from the outer faces, the
hole's native Hole Wizard callout and the tap's stated far-wall minimum (the
hidden TapWallReference sketch, shown in that view only).  No datums, no
frames (drawing-guidelines.md rule 5), no note block.  The sheet runs 2:1 in
decimal inch (the part's ``drawing_unit: in``); the isometric stays 2:1.

Run with SolidWorks open::

    uv run python cad\scripts\draw_pn_pen_frame.py pn-pen-frame
"""

from __future__ import annotations

import argparse
import math
import sys
from typing import Any

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
    stamp_drawing_summary,
)
from _drawing_dimensions import (
    assert_imported_precision,
    offset_dimension_text,
    set_dimension_callouts,
)
from _drawing_hidden_sketches import curate_view_dimensions
from _drawing_edges import scan_view_edges
from _drawing_hole_callout import add_native_hole_callout, set_hole_callout_precision
from _drawing_notes import add_property_linked_note
from _drawing_registry import DRAWINGS_BY_NAME
from _part_properties import part_drawing_unit
from _drawing_view_display import set_hidden_lines_removed
from _hole_callout_thread_class import omit_title_block_thread_class
from _hole_spec import blind_cut_dia_mm
from _machinist_review_mode import MachinistReviewMode
from _paths import CAD_ROOT
from _session import run_build
import _telemetry
from pn_pen_frame_spec import (
    DIMENSION_CALLOUTS,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    FRAME_DEPTH,
    OUTER_HEIGHT,
    OUTER_WIDTH,
    RAIL_END,
    RAIL_SIDE,
    SET_SCREW_TAP_SPEC,
    TAP_WALL_MIN_MM,
    TAP_WALL_START_Z,
    WINDOW_CORNER_R,
)


# Cached machinist review leaf: a FIX or ERROR verdict fails the build.
MACHINIST_REVIEW = MachinistReviewMode.ENFORCE

SPEC = DRAWINGS_BY_NAME["pn_pen_frame"]
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

SHEET_SCALE = (2.0, 1.0)
VIEW_SCALE = SHEET_SCALE[0] / SHEET_SCALE[1]  # sheet-mm per model-mm

# Sheet layout (meters).  Third angle: the bottom view projects straight
# below the front view (model X shared); the isometric rides to the right.
# Both orthographic views are bbox-centred: the front on the 28 x 40 ring face
# (x 0.087..0.143, y 0.145..0.225), the bottom on the 28 x 8 underside
# (x 0.087..0.143, y 0.097..0.113), whose centre IS the tapped hole's axis.
FRONT_CENTER = (0.115, 0.185)
BOTTOM_CENTER = (0.115, 0.105)
# The pictorial runs 2:1 like the sheet: at 1:1 the 2.26 tap mouth and the R1.0
# window fillets read as polygons and banded shading (machinist review r1).
# A true isometric of the 28 x 40 x 8 ring spans (28 + 8) cos 45 = 25.5 wide
# and 40 x 0.816 + (28 + 8) x 0.408 = 47.3 tall, so at 2:1 about 51 x 95 mm:
# centred at (0.320, 0.180) it fills x 0.295..0.345, y 0.133..0.228, clear of
# the front view's 40.0 dimension (x 0.173), its note (ends ~x 0.23), the top
# border (0.267) and the title block (top 0.065).
ISO_SCALE = (2, 1)
ISO_CENTER = (0.320, 0.180)
ISO_HALF_EXTENT = (
    (OUTER_WIDTH + FRAME_DEPTH) * 0.7071 * ISO_SCALE[0] / ISO_SCALE[1] / 2000.0,
    (OUTER_HEIGHT * 0.8165 + (OUTER_WIDTH + FRAME_DEPTH) * 0.4082)
    * ISO_SCALE[0]
    / ISO_SCALE[1]
    / 2000.0,
)


def _front_xy(model_x_mm: float, model_y_mm: float) -> tuple[float, float]:
    """Sheet point of a model (x, y) in the front view (bbox-centred)."""
    return (
        FRONT_CENTER[0] + (model_x_mm - OUTER_WIDTH / 2.0) * VIEW_SCALE / 1000.0,
        FRONT_CENTER[1] + (model_y_mm - OUTER_HEIGHT / 2.0) * VIEW_SCALE / 1000.0,
    )


def _bottom_xy(model_x_mm: float, model_z_mm: float) -> tuple[float, float]:
    """Sheet point of a model (x, z) in the bottom view: model X across, model
    +Z up (the face nearer the front view's viewer stands nearer it)."""
    return (
        BOTTOM_CENTER[0] + (model_x_mm - OUTER_WIDTH / 2.0) * VIEW_SCALE / 1000.0,
        BOTTOM_CENTER[1] + (model_z_mm - FRAME_DEPTH / 2.0) * VIEW_SCALE / 1000.0,
    )


FRONT_LEFT_X, FRONT_BOTTOM_Y = _front_xy(0.0, 0.0)
FRONT_RIGHT_X, FRONT_TOP_Y = _front_xy(OUTER_WIDTH, OUTER_HEIGHT)
BOTTOM_LEFT_X, BOTTOM_LOW_Y = _bottom_xy(0.0, 0.0)
BOTTOM_RIGHT_X, BOTTOM_HIGH_Y = _bottom_xy(OUTER_WIDTH, FRAME_DEPTH)
HOLE_CENTER_MM = (OUTER_WIDTH / 2.0, 0.0, FRAME_DEPTH / 2.0)
HOLE_SHEET_XY = _bottom_xy(HOLE_CENTER_MM[0], HOLE_CENTER_MM[2])
HOLE_R_SHEET = blind_cut_dia_mm(SET_SCREW_TAP_SPEC) * VIEW_SCALE / 2000.0
# The printed (top-right) window-corner fillet's arc centre.
CORNER_ARC_CENTER_XY = _front_xy(
    OUTER_WIDTH - RAIL_SIDE - WINDOW_CORNER_R, OUTER_HEIGHT - RAIL_END - WINDOW_CORNER_R
)

# Per-view survivors of the marked-dimension import: parametric name -> sheet
# text position.  Front view (ring x 0.087..0.143, y 0.145..0.225; window
# x 0.095..0.135, y 0.157..0.213):
# - The 28.0 width rides above, alone: no other dimension leaves the top.
# - The window corner's two location dims and its two sizes all leave from
#   the window's left and bottom edges (build_pn_pen_frame's chain order), so
#   they stack left and below, each smaller one nearer the ring: the 28.0
#   window height 10 mm left (its text 4.5 mm off the left face), the 6.00
#   bottom wall 24 mm left with its text between its own extension lines; the
#   20.00 window width 8 mm below, the 4.00 left wall 17 mm below with its
#   text outboard left as before.  Each pair shares the extension line from
#   the window's bottom-left corner, so neither crosses the other's
#   dimension line.
# - The top-right corner is the one no extension line leaves from: the 4X R1.0
#   text stands 14 mm right of the ring, 6 mm under its top (clear of the
#   40.0's top extension line), so its leader runs from the arc out through
#   the right rail, ~20-30 deg above horizontal from the arc centre (inside the
#   arc's 0-90 deg span), crossing only the ring's right face.
# - The 40.0 height moves 30 mm right (was 16) to leave that text 6 mm clear
#   of its dimension line.
FRONT_KEEP = {
    "OuterSpanX": (FRONT_CENTER[0], FRONT_TOP_Y + 0.014),
    "OuterHeightDim": (FRONT_RIGHT_X + 0.030, FRONT_CENTER[1]),
    "WindowHeight": (FRONT_LEFT_X - 0.010, FRONT_CENTER[1]),
    "BottomWall": (FRONT_LEFT_X - 0.024, _front_xy(0.0, RAIL_END / 2.0)[1]),
    "WindowWidth": (FRONT_CENTER[0], FRONT_BOTTOM_Y - 0.008),
    "LeftWall": (FRONT_LEFT_X - 0.012, FRONT_BOTTOM_Y - 0.017),
    "WindowCornerR": (FRONT_RIGHT_X + 0.014, FRONT_TOP_Y - 0.006),
}
# Bottom view: the hole's X coordinate below, its Z coordinate left, the depth
# right; the hole callout stands above-right, between the bottom view and the
# front view's height dimension.  The tap's far-wall minimum (.074 MIN over
# TAP WALL) stands left too, outboard of the .16: its reference line runs up
# the far wall from the thread's rim on the hole's axis (sheet y
# ~0.108..0.112), so its extension lines run left across the rail above the
# .16's top extension line (y 0.105, from the hole's centre).
BOTTOM_KEEP = {
    "ScrewX": (_bottom_xy(OUTER_WIDTH / 4.0, 0.0)[0], BOTTOM_LOW_Y - 0.010),
    "ScrewZ": (BOTTOM_LEFT_X - 0.010, _bottom_xy(0.0, FRAME_DEPTH / 4.0)[1]),
    "Depth": (BOTTOM_RIGHT_X + 0.016, BOTTOM_CENTER[1]),
    "TapWallMin": (
        BOTTOM_LEFT_X - 0.020,
        _bottom_xy(0.0, TAP_WALL_START_Z + TAP_WALL_MIN_MM / 2.0)[1],
    ),
}
# The wall's 3.8 mm run cannot hold its ~21 x 9 mm two-row text: centred on
# its own line, the line, its arrows and both extension lines ran through
# ".074 min. TAP WALL" (machinist review of 6988bc279, 3/3).  Native
# OffsetText parks the text on a leader left of the extension lines' ends
# (line x - 0.001), its right edge ~4 mm clear of them and ~12 mm clear of
# the .16's text; the anchor is the value row's bottom centre.
TAP_WALL_TEXT_XY = (BOTTOM_LEFT_X - 0.036, BOTTOM_KEEP["TapWallMin"][1])
_TEXT_SETTLE_M = 0.0005
_CENTER_MARK_ANNOTATION = 13  # swAnnotationType_e.swCenterMarkSym
# The one printed fillet stands for all four equal window corners.  A custom
# prefix replaces SolidWorks' own radius "R", so it carries it
# (draw_pd_guide_lock: "4X 1.8" printed without).
DIMENSION_PREFIXES = {"WindowCornerR": "4X R"}
HOLE_CALLOUT_XY = (0.165, 0.128)
HOLE_CALLOUT_PROCESS = "TAP"
# The through-next tap's one Hole Wizard length variable, its drill
# diameter, prints .XXX.
TAP_CALLOUT_PRECISION = {"hw-tapdrldia": 3}

FRONT_VIEW_NOTE_XY = (0.175, 0.240)
BOTTOM_VIEW_NOTE_XY = (0.070, 0.072)
# The note's left end; its ~60 mm text centres under the isometric (x 0.320),
# ~15 mm below the view's lowest corner (y 0.133).
ISO_VIEW_NOTE_XY = (0.290, 0.116)


def _set_dimension_prefixes(
    adapter: Any, annotations: list[Any], prefixes: dict[str, str]
) -> None:
    """Write a native prefix on named imported dimensions and read it back."""
    remaining = dict(prefixes)
    for raw in annotations:
        annotation = _early_bound(raw, "IAnnotation")
        prefix = remaining.pop(dimension_name(adapter, annotation), None)
        if prefix is None:
            continue
        display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
        display.SetText(1, prefix)  # swDimensionTextPrefix
        if str(display.GetText(1) or "") != prefix:
            raise RuntimeError(f"dimension prefix {prefix!r} did not persist")
    if remaining:
        raise RuntimeError(f"dimension prefixes not applied: {sorted(remaining)}")


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


def _center_mark_count(view: Any) -> int:
    """The view's centre-mark annotations (a bare view answers None)."""
    return len(
        _early_bound(view, "IView").GetAnnotationsByType(_CENTER_MARK_ANNOTATION) or ()
    )


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open pen-frame source", await adapter.open_model(str(SOURCE)))
    read_required_properties(
        adapter.currentModel,
        (
            "Number",
            "Revision",
            "Title",
            "Material Specification",
            "Finish",
            "Quantity",
            "Front View Note",
            "Bottom View Note",
            "Isometric View Note",
        ),
        required=(
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
            "Front View Note",
            "Bottom View Note",
            "Isometric View Note",
        ),
    )
    drawing_model, _sheet = new_project_drawing(
        adapter,
        property_view=PART_STEM,
        scale=SHEET_SCALE,
        layout=SPEC.layout,
        unit=part_drawing_unit(PART_STEM),
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Pen Frame Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "pen frame; brass stirrup; #4-40 thumb-screw tap",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )
    # Explicit per-view scale: a view placed without one can silently
    # auto-scale, which shifts every coordinate-based pick on it.
    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=(2, 1))
    bottom = place_view(adapter, str(SOURCE), "*Bottom", *BOTTOM_CENTER, scale=(2, 1))
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=ISO_SCALE)
    # The tapped hole is fully defined by its callout (drawing-guidelines.md
    # rule 9): no view needs hidden lines.  finalize_drawing turns the
    # pictorial into precise Shaded With Edges (rule 8); at 2:1 its tap mouth
    # and window fillets read round rather than faceted.
    for view in (front, bottom, iso):
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
            bottom,
            keep=BOTTOM_KEEP,
            view_label="bottom",
            dimensions_by_feature=DRAWING_DIMENSIONS,
        ),
    ]
    # Places are authored on the part; the sheet only proves the import kept them.
    assert_imported_precision(adapter, annotations, DRAWING_PRECISION_BY_NAME)
    _set_dimension_prefixes(adapter, annotations, DIMENSION_PREFIXES)
    set_dimension_callouts(adapter, annotations, DIMENSION_CALLOUTS)
    _offset_tap_wall_text(adapter, annotations)

    # The template may centre-mark the tap as the view is placed: every round's
    # layout audit found two identical marks on it (duplicate-annotation, as
    # draw_pn_pen_rod, fleet issue #913).  Mark only a bare view, then prove
    # the tap carries exactly one.
    if _center_mark_count(bottom) == 0 and not auto_center_marks(
        adapter, bottom, holes=True, size=0.0025
    ):
        raise RuntimeError("failed to add ASME center marks to the bottom view")
    if (found := _center_mark_count(bottom)) != 1:
        raise RuntimeError(
            f"bottom view carries {found} centre marks, not the tap's one"
        )
    hole_rim = scan_view_edges(bottom, label="bottom").circle_at(
        HOLE_CENTER_MM,
        blind_cut_dia_mm(SET_SCREW_TAP_SPEC) / 2.0,
        axis=(0.0, 1.0, 0.0),
        label="thumb-screw tap mouth",
    )
    tap_callout = add_native_hole_callout(
        adapter,
        bottom,
        edge=hole_rim.edge,
        callout_xy=HOLE_CALLOUT_XY,
        label="thumb-screw tapped hole",
        process=HOLE_CALLOUT_PROCESS,
    )
    # The title block's THREADS row owns the 2B class (drawing-guidelines.md
    # rule 2): the callout reads TAP 4-40 UNC THRU.
    omit_title_block_thread_class(tap_callout, label="thumb-screw tapped hole")
    set_hole_callout_precision(
        tap_callout, TAP_CALLOUT_PRECISION, label="thumb-screw tapped hole"
    )

    add_property_linked_note(adapter, "Front View Note", *FRONT_VIEW_NOTE_XY)
    add_property_linked_note(adapter, "Bottom View Note", *BOTTOM_VIEW_NOTE_XY)
    add_property_linked_note(adapter, "Isometric View Note", *ISO_VIEW_NOTE_XY)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Pen Frame Manufacturing Drawing",
        scale=SHEET_SCALE,
        layout=SPEC.layout,
        # SolidWorks pins its own "#4-40 Tapped Hole" note to the bottom view
        # once the tap carries a hole callout; the callout already states the
        # thread, and the note sat under it with the callout's leader through
        # it (farm c0b95549c: merged-blocks + leader-through-text).
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
