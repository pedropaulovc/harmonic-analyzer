r"""Create the curated machinist drawing for the pen frame (stirrup).

The SLDPRT remains authoritative.  This recipe supplies only the frame's views,
the dimension layout and the tapped-hole callout; sheet/template and export
behavior lives in ``_drawing_common``.  Dimension import and curation live in
``_drawing_dimension_import``.

The pen frame is a flat rectangular brass ring with a centred window and a
#4-40 thumb-screw hole tapped up through the bottom rail.  Every size is a
native associative dimension marked on the part (``pn_pen_frame_spec``):
the front view carries the outer envelope and the two rail widths; the bottom
view, looking up at the tapped rail, carries the depth, the hole's two
coordinates from the outer faces and the hole's native Hole Wizard callout.
No datums, no frames (drawing-guidelines.md rule 5), no note block.  The sheet
runs 2:1; the isometric stays 1:1.

Run with SolidWorks open::

    uv run python cad\scripts\draw_pn_pen_frame.py pn-pen-frame
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

from solidworks_mcp.adapters.solidworks.drawing import auto_center_marks, place_view

from _check import check
from _drawing_common import (
    DrawingOutputs,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    stamp_drawing_summary,
)
from _drawing_dimension_import import curate_view_dimensions
from _drawing_dimensions import assert_imported_precision
from _drawing_edges import scan_view_edges
from _drawing_hole_callout import add_native_hole_callout
from _drawing_notes import add_property_linked_note
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_view_display import set_hidden_lines_removed
from _hole_spec import blind_cut_dia_mm
from _paths import CAD_ROOT
from _session import run_build
import _telemetry
from pn_pen_frame_spec import (
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    FRAME_DEPTH,
    OUTER_HEIGHT,
    OUTER_WIDTH,
    SET_SCREW_TAP_SPEC,
)


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
# below the front view (model X shared); the 1:1 isometric rides to the right.
# Both orthographic views are bbox-centred: the front on the 28 x 40 ring face
# (x 0.087..0.143, y 0.145..0.225), the bottom on the 28 x 8 underside
# (x 0.087..0.143, y 0.097..0.113), whose centre IS the tapped hole's axis.
FRONT_CENTER = (0.115, 0.185)
BOTTOM_CENTER = (0.115, 0.105)
ISO_CENTER = (0.320, 0.185)


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

# Per-view survivors of the marked-dimension import: parametric name -> sheet
# text position.  Front: the width above, the height right, the two rail
# widths (window corner from the origin corner) left and below, each text
# outboard of its own extension lines.  Bottom: the hole's X coordinate below,
# its Z coordinate left, the depth right; the hole callout stands above-right,
# between the bottom view and the front view's height dimension.
FRONT_KEEP = {
    "OuterSpanX": (FRONT_CENTER[0], FRONT_TOP_Y + 0.014),
    "OuterHeightDim": (FRONT_RIGHT_X + 0.016, FRONT_CENTER[1]),
    "InnerAnchorY": (FRONT_LEFT_X - 0.012, _front_xy(0.0, 3.0)[1]),
    "InnerAnchorX": (FRONT_LEFT_X - 0.012, FRONT_BOTTOM_Y - 0.010),
}
BOTTOM_KEEP = {
    "ScrewX": (_bottom_xy(OUTER_WIDTH / 4.0, 0.0)[0], BOTTOM_LOW_Y - 0.010),
    "ScrewZ": (BOTTOM_LEFT_X - 0.010, _bottom_xy(0.0, FRAME_DEPTH / 4.0)[1]),
    "Depth": (BOTTOM_RIGHT_X + 0.016, BOTTOM_CENTER[1]),
}
HOLE_CALLOUT_XY = (0.165, 0.128)
HOLE_CALLOUT_PROCESS = "TAP"

FRONT_VIEW_NOTE_XY = (0.175, 0.240)
BOTTOM_VIEW_NOTE_XY = (0.070, 0.072)
ISO_VIEW_NOTE_XY = (0.290, 0.140)


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
        adapter, property_view=PART_STEM, scale=SHEET_SCALE, layout=SPEC.layout
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
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=(1, 1))
    # The tapped hole is fully defined by its callout (drawing-guidelines.md
    # rule 9): no view needs hidden lines.
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

    if not auto_center_marks(adapter, bottom, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center marks to the bottom view")
    hole_rim = scan_view_edges(bottom, label="bottom").circle_at(
        HOLE_CENTER_MM,
        blind_cut_dia_mm(SET_SCREW_TAP_SPEC) / 2.0,
        axis=(0.0, 1.0, 0.0),
        label="thumb-screw tap mouth",
    )
    add_native_hole_callout(
        adapter,
        bottom,
        edge=hole_rim.edge,
        callout_xy=HOLE_CALLOUT_XY,
        label="thumb-screw tapped hole",
        process=HOLE_CALLOUT_PROCESS,
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
