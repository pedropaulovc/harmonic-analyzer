r"""Create the curated machinist drawing for the pen v-block.

The SLDPRT remains authoritative.  This recipe supplies only the pen-v-block
views, dimension layout, hole callouts, and manufacturing notes; every shared
sheet/template, import, curation, and export behavior lives in
``_drawing_common``.

The sheet runs at 4:1 (the block is 36 mm end to end); the isometric carries an
explicit 2:1 override so it stays clear of the title block.

The print is deliberately plain (cad/docs/drawing-simplicity-policy.md): the
block is set-screwed to the pen rod, so nothing runs on its bores and it
carries no datums, frames, roughness symbols or basic dimensions.  The marker
groove is dimensioned on the END view, where it is visible (policy rule 7:
never dimension to a hidden line); the chamfer is a leader callout.

Run with SolidWorks open::

    uv run python cad\scripts\draw_pen_v_block.py pen-v-block
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

import _telemetry
from _common import CAD_ROOT, check, run_build
from _drawing_common import (
    DrawingOutputs,
    add_attached_note,
    add_edge_dimension,
    add_property_linked_note,
    curate_view_dimensions,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    set_dimension_callouts,
    set_hidden_lines_removed,
    set_hidden_lines_visible,
    stamp_drawing_summary,
)
from _drawing_registry import DRAWINGS_BY_NAME
from pen_v_block_spec import (
    BLOCK_DEPTH,
    BLOCK_HEIGHT,
    BLOCK_LENGTH,
    BORE_X,
    CHAMFER,
    SCREW_HOLE_XY,
    GROOVE_DEPTH,
    GROOVE_WIDTH,
    GROOVE_Z0,
)
from solidworks_mcp.adapters.solidworks.drawing import (
    auto_center_marks,
    place_view,
)


SPEC = DRAWINGS_BY_NAME["pen_v_block"]
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

# Sheet layout (meters).  The front view's model bbox is 36 x 18 mm; at 4:1 the
# view is 144 x 72 mm.  Third angle: the top view (block seen from above,
# carrying the two pen bores) sits ABOVE the front view; the right view (16 x 18
# stock section, the groove visible in its bottom edge) sits to its right.
FRONT_CENTER = (0.130, 0.115)
TOP_CENTER = (0.130, 0.215)
RIGHT_CENTER = (0.265, 0.115)
ISO_CENTER = (0.360, 0.225)


def _sheet_x(model_x_mm: float) -> float:
    """Sheet X of a model-X point in the front/top views (4:1, bbox-centred)."""
    return FRONT_CENTER[0] + (model_x_mm - BLOCK_LENGTH / 2.0) * SHEET_SCALE[0] / 1000.0


def _front_y(model_y_mm: float) -> float:
    """Sheet Y of a model-Y point in the front view (4:1, bbox-centred)."""
    return FRONT_CENTER[1] + (model_y_mm - BLOCK_HEIGHT / 2.0) * SHEET_SCALE[0] / 1000.0


def _mm(span_mm: float) -> float:
    """A model span in sheet meters at the 4:1 view scale."""
    return span_mm * SHEET_SCALE[0] / 1000.0


# Per-view survivors of the marked-dimension import: parametric name -> sheet
# position.  The linear chain stacks below the front view, smallest span nearest
# the geometry; the set-screw hole is located right of the block and called out
# left of it, so neither annotation crosses the other.
FRONT_KEEP = {
    "Length": (_sheet_x(BLOCK_LENGTH / 2.0), 0.058),
    # The set-screw hole sits ON the rod-bore axis (x 10), so its station dim
    # goes in the free band under the front view, clear of the top view's
    # Bore0X (10.00).
    "ScrewHoleCx": (_sheet_x(SCREW_HOLE_XY[0] / 2.0), 0.070),
    # Height of the hole: a vertical dimension right of the block, its text at
    # MID-height so it sits on the dimension line, not on the hole's own
    # centreline extension (machinist review 2026-09-02).
    "ScrewHoleCz": (_sheet_x(BLOCK_LENGTH) + 0.012, _front_y(SCREW_HOLE_XY[1] / 2.0)),
    # Hole size: left of the block at hole height, so the leader is short,
    # runs horizontally out through the left face BELOW the chamfer corner
    # (Y 12) and crosses nothing else.  x keeps the text's left edge clear of
    # the sheet's 12.7 mm zone margin.
    "ScrewHoleDiaDim": (_sheet_x(0.0) - 0.022, _front_y(SCREW_HOLE_XY[1])),
}
TOP_KEEP = {
    "Bore0X": (_sheet_x(BORE_X[0] / 2.0), TOP_CENTER[1] - 0.042),
    "Bore1X": (_sheet_x(BORE_X[1] / 2.0), TOP_CENTER[1] - 0.052),
    "Bore0Dia": (_sheet_x(BORE_X[0]) + 0.030, TOP_CENTER[1] + 0.042),
}

# Right-view half extents at 4:1: the 16 (Z) x 18 (Y) stock section, and the
# groove's half width across it.
RIGHT_HALF_Z = _mm(BLOCK_DEPTH / 2.0)
RIGHT_HALF_Y = _mm(BLOCK_HEIGHT / 2.0)
GROOVE_HALF_W = _mm(GROOVE_WIDTH / 2.0)
RIGHT_BOTTOM_Y = RIGHT_CENTER[1] - RIGHT_HALF_Y
RIGHT_TOP_Y = RIGHT_CENTER[1] + RIGHT_HALF_Y
RIGHT_LEFT_X = RIGHT_CENTER[0] - RIGHT_HALF_Z
RIGHT_RIGHT_X = RIGHT_CENTER[0] + RIGHT_HALF_Z
# Mid-height of the groove walls: the only band where a pick cannot land on
# the bores' hidden lines (Z 4 / 12, 0.25 mm inside the walls), which start at
# the groove floor.
GROOVE_WALL_PICK_Y = RIGHT_BOTTOM_Y + _mm(GROOVE_DEPTH / 2.0)
# One dimension lane fits between the right view's bottom edge and the title
# block (top edge ~0.065): the groove width and its offset chain there.
RIGHT_BELOW_LANE_Y = RIGHT_BOTTOM_Y - 0.010
RIGHT_KEEP = {
    # The stock depth moves ABOVE the view: the lane below it belongs to the
    # groove dimensions.
    "Depth": (RIGHT_CENTER[0], RIGHT_TOP_Y + 0.010),
    # The groove rise, right of the end view with its text at mid-groove.  It
    # used to sit LEFT of the view, where its floor witness line ran collinear
    # with the front view's dashed groove floor and read as a dimension to a
    # hidden line (machinist review 2026-09-02).
    "GrooveDepth": (RIGHT_RIGHT_X + 0.010, GROOVE_WALL_PICK_Y),
}
# Block height outside the groove-depth lane.
HEIGHT_TEXT_XY = (RIGHT_RIGHT_X + 0.022, RIGHT_CENTER[1])

DIMENSION_CALLOUTS = {
    "Bore0Dia": "2X DRILL THRU",
    "ScrewHoleDiaDim": "DRILL THRU",
}
# The two end chamfers as one leader callout off the right chamfer edge, so no
# dimension line runs through the text (a 24 mm dimension line cannot carry it).
CHAMFER_CALLOUT = f"2X {CHAMFER:.2f} X 45°"
CHAMFER_EDGE_XY = (
    _sheet_x(BLOCK_LENGTH - CHAMFER / 2.0),
    _front_y(BLOCK_HEIGHT - CHAMFER / 2.0),
)
# Above the block's top-right: right of the top view's Bore1X (26.00) arrow at
# x~0.162, below the top view (bottom edge 0.183), left of the right view's
# depth witness line at 0.233.
CHAMFER_NOTE_XY = (_sheet_x(BLOCK_LENGTH - CHAMFER), RIGHT_TOP_Y + 0.015)


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open pen-v-block source", await adapter.open_model(str(SOURCE)))
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
    drawing_model, sheet = new_project_drawing(
        adapter, property_view=PART_STEM, scale=SHEET_SCALE
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Pen V-Block Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "pen v-block; brass; marker groove; manufacturing drawing",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )
    # Explicit per-view scale: a view placed without one can silently
    # auto-scale, which shifts every coordinate-based pick on it.
    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=(4, 1))
    top = place_view(adapter, str(SOURCE), "*Top", *TOP_CENTER, scale=(4, 1))
    right = place_view(adapter, str(SOURCE), "*Right", *RIGHT_CENTER, scale=(4, 1))
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=(2, 1))
    set_hidden_lines_removed(adapter, iso)
    # Hidden lines stay ON in every orthographic view: the front view carries
    # the vertical pen bores and the groove floor, the top view the groove
    # edges and the screw hole crossing the depth, the right view the bores
    # through the section.
    for view in (front, top, right):
        set_hidden_lines_visible(adapter, view)

    front_annotations = curate_view_dimensions(
        adapter, front, keep=FRONT_KEEP, view_label="front"
    )
    top_annotations = curate_view_dimensions(
        adapter, top, keep=TOP_KEEP, view_label="top"
    )
    # Right view: the 16 x 18 stock section.  Depth and the groove rise are
    # model dims; the 18 height and the groove width/offset are drawing-added
    # across the view's visible edges (the groove sketch lives on the Top
    # plane, so its model dims could only land in the top view, where the
    # groove is hidden).
    right_annotations = curate_view_dimensions(
        adapter, right, keep=RIGHT_KEEP, view_label="right"
    )
    set_dimension_callouts(
        adapter,
        [*front_annotations, *top_annotations, *right_annotations],
        DIMENSION_CALLOUTS,
    )
    # Block height (18): dimension the right view's flat top/bottom silhouette
    # edges.  The bottom edge is interrupted by the marker groove, so pick it on
    # the remaining land beside the groove, not at mid-depth.
    _bottom_land_x = RIGHT_LEFT_X + _mm(GROOVE_Z0 / 2.0)
    add_edge_dimension(
        adapter,
        right,
        p0=(_bottom_land_x, RIGHT_BOTTOM_Y),
        p1=(RIGHT_CENTER[0], RIGHT_TOP_Y),
        text_xy=HEIGHT_TEXT_XY,
        label="block-height overall",
    )
    # Groove width (8.50): across the two visible groove walls.
    add_edge_dimension(
        adapter,
        right,
        p0=(RIGHT_CENTER[0] - GROOVE_HALF_W, GROOVE_WALL_PICK_Y),
        p1=(RIGHT_CENTER[0] + GROOVE_HALF_W, GROOVE_WALL_PICK_Y),
        text_xy=(RIGHT_CENTER[0], RIGHT_BELOW_LANE_Y),
        label="groove width",
        orientation="horizontal",
    )
    # Groove offset (3.75): from the outer face to the near groove wall, chained
    # on the same lane.  The outer edge is picked BELOW the chamfer break (Y 12),
    # where the section's side is one model edge.
    add_edge_dimension(
        adapter,
        right,
        p0=(RIGHT_LEFT_X, RIGHT_BOTTOM_Y + _mm(BLOCK_HEIGHT - CHAMFER) / 2.0),
        p1=(RIGHT_CENTER[0] - GROOVE_HALF_W, GROOVE_WALL_PICK_Y),
        text_xy=(RIGHT_LEFT_X + _mm(GROOVE_Z0 / 2.0), RIGHT_BELOW_LANE_Y),
        label="groove offset",
        orientation="horizontal",
    )
    add_attached_note(
        adapter,
        front,
        text=CHAMFER_CALLOUT,
        entity_xy=CHAMFER_EDGE_XY,
        note_xy=CHAMFER_NOTE_XY,
        label="chamfer callout",
    )

    for view, label in ((front, "front"), (top, "top")):
        if not auto_center_marks(adapter, view, holes=True, size=0.0025):
            raise RuntimeError(f"failed to add ASME center marks to {label} view")

    # x=0.020 clears the sheet's 12.7 mm zone margin; y=0.046 keeps the block
    # below the 36.00/26.00 locator chain under the front view.
    add_property_linked_note(adapter, "Manufacturing Notes", 0.020, 0.046)
    add_property_linked_note(adapter, "Isometric View Note", 0.330, 0.180)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Pen V-Block Manufacturing Drawing",
        scale=SHEET_SCALE,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[PART_STEM])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
