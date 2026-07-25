r"""Create the curated machinist drawing for the pinion pivot block.

The SLDPRT remains authoritative.  This recipe supplies only the block's
views, dimension layout, hole callouts, and manufacturing notes; every shared
sheet/template, import, curation, and export behavior lives in
``_drawing_common``.

The sheet runs at 3:1 (the block is 36 x 16 x 12); the isometric carries an
explicit 2:1 override so it stays clear of the title block.

Run with SolidWorks open::

    uv run python cad\scripts\draw_pinion_pivot_block.py pinion-pivot-block
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

import _telemetry
from _common import CAD_ROOT, check, run_build
from _drawing_common import (
    auto_center_marks,
    DrawingOutputs,
    add_datum_feature,
    add_edge_dimension,
    add_feature_control_frame,
    add_native_hole_callout,
    add_property_linked_note,
    add_surface_finish,
    curate_view_dimensions,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    set_dimension_callouts,
    set_basic_dimension,
    stamp_drawing_summary,
)
from _drawing_registry import DRAWINGS_BY_NAME
from pinion_pivot_block_spec import (
    BLOCK_BOTTOM_Y,
    BLOCK_DEPTH,
    BLOCK_WIDTH as BLOCK_WIDTH,
    BORE_DIA,
    BORE_HALF_SPACING,
    FRONT_BBOX_CY,
    LIFT_BORE_DROP,
    SCREW_HALF_SPACING,
    SCREW_HOLE_DIA,
)
from solidworks_mcp.adapters.solidworks.drawing import (
    place_view,
)


SPEC = DRAWINGS_BY_NAME["pinion_pivot_block"]
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

SHEET_SCALE = (3.0, 1.0)

# Sheet layout (meters).  The front view's model bbox runs -18..18 in X and
# -12..4 in Y; at 3:1 the view is 108 x 48 mm.  Third angle: the top view
# (block seen from above, carrying the two hold-down holes) sits ABOVE the
# front view; the right view (16 x 12 stock section) sits to its right.
FRONT_CENTER = (0.135, 0.130)
TOP_CENTER = (0.135, 0.220)
RIGHT_CENTER = (0.280, 0.130)
ISO_CENTER = (0.360, 0.225)


def _front_x(model_x_mm: float) -> float:
    """Sheet X of a model-X point in the front/top views (3:1, bbox-centred)."""
    return FRONT_CENTER[0] + model_x_mm * SHEET_SCALE[0] / 1000.0


def _front_y(model_y_mm: float) -> float:
    """Sheet Y of a model-Y point in the front view (3:1, bbox-centred)."""
    return FRONT_CENTER[1] + (model_y_mm - FRONT_BBOX_CY) * SHEET_SCALE[0] / 1000.0


BORE_R_SHEET = BORE_DIA * SHEET_SCALE[0] / 2000.0
SCREW_R_SHEET = SCREW_HOLE_DIA * SHEET_SCALE[0] / 2000.0

# Per-view survivors of the marked-dimension import: parametric name -> sheet
# position.  The bore-station pair (7.5/7.5 off the symmetric mid-plane) stacks
# above the view; the vertical chain (bore height, lift drop) sits left; the
# leadered diameters land in the clear corners.
FRONT_KEEP = frozenset(
    {
        "BlockWidth",
        "BlockHeight",
        "AnchorZ",
        "PivotBoreX",
        "LiftBoreX",
        "LiftBoreCz",
        "PivotBoreDia",
        "LiftBoreDia",
    }
)
RIGHT_KEEP = frozenset({"Depth"})
TOP_KEEP = frozenset()
DIMENSION_CALLOUTS = {
    "PivotBoreDia": "THRU - REAM 1/4 IN\n+0.05/-0.00",
    "LiftBoreDia": "THRU - REAM 1/4 IN\n+0.05/-0.00",
}


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open pinion-pivot-block source", await adapter.open_model(str(SOURCE)))
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
            0: "Pinion Pivot Block Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "pinion pivot block; manufacturing drawing; pivot bores",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )
    # Explicit per-view scale: a view placed without one can silently
    # auto-scale, which shifts every coordinate-based pick on it.
    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=(3, 1))
    top = place_view(adapter, str(SOURCE), "*Top", *TOP_CENTER, scale=(3, 1))
    right = place_view(adapter, str(SOURCE), "*Right", *RIGHT_CENTER, scale=(3, 1))
    place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=(2, 1))
    front_annotations = curate_view_dimensions(
        adapter, front, keep=FRONT_KEEP, view_label="front"
    )
    # Right view: the 16 x 12 stock section carries only the block depth.
    right_annotations = curate_view_dimensions(
        adapter, right, keep=RIGHT_KEEP, view_label="right"
    )
    # Top view: hold-down geometry is located by the basic spacing dim + FCF.
    top_annotations = curate_view_dimensions(
        adapter, top, keep=TOP_KEEP, view_label="top"
    )
    set_dimension_callouts(
        adapter,
        [*front_annotations, *top_annotations, *right_annotations],
        DIMENSION_CALLOUTS,
    )

    for view, label in ((front, "front"), (top, "top")):
        if not auto_center_marks(adapter, view, holes=True):
            raise RuntimeError(f"failed to add ASME center marks to {label} view")

    # Hold-down screw spacing (27): dimension across the two hole circles in
    # the top view; both sit at mid-depth so the pick heights are identical.
    screw_spacing = add_edge_dimension(
        adapter,
        top,
        p0=(_front_x(-SCREW_HALF_SPACING), TOP_CENTER[1] + SCREW_R_SHEET),
        p1=(_front_x(SCREW_HALF_SPACING), TOP_CENTER[1] + SCREW_R_SHEET),
        text_xy=(TOP_CENTER[0], 0.248),
        label="hold-down screw spacing",
    )
    set_basic_dimension(adapter, screw_spacing, label="hold-down screw spacing")

    # Hold-down pattern across the depth: both drills sit at exact mid-depth,
    # so a single basic 6 from the broad face (datum C) locates the pair.
    depth_location = add_edge_dimension(
        adapter,
        top,
        p0=(_front_x(-17.0), TOP_CENTER[1] - BLOCK_DEPTH * SHEET_SCALE[0] / 2000.0),
        p1=(_front_x(-SCREW_HALF_SPACING), TOP_CENTER[1] - SCREW_R_SHEET),
        text_xy=(0.062, 0.212),
        label="hold-down depth location",
    )
    set_basic_dimension(adapter, depth_location, label="hold-down depth location")

    # Native datum/GD&T/surface annotations.  A = the base seat (right view's
    # bottom edge); B = the pivot bore; C = a broad face (constrains the depth
    # direction B leaves free -- the right view's sheet-right edge is z = 0).
    add_datum_feature(
        adapter,
        right,
        edge_xy=(RIGHT_CENTER[0], _front_y(BLOCK_BOTTOM_Y)),
        symbol_xy=(RIGHT_CENTER[0], _front_y(BLOCK_BOTTOM_Y) - 0.018),
        datum="A",
        label="block base seat",
    )
    # Tagged at the bore's LOWER-RIGHT (299 deg), not its top-right.
    # PivotBoreDia is a DIAMETRAL dimension, so SolidWorks draws it as a line
    # across the whole bore with an arrowhead on each end -- the up-right end
    # landing on the circle at 49.3 deg.  A datum symbol placed up-right of the
    # bore re-attaches to the circle point NEAREST it (SetPosition2 confines a
    # symbol to "along that edge"; on a circle the permitted set IS the
    # circumference), which resolved to 49.4 deg: 0.9 mm from the diameter
    # arrow, so the two arrowheads stacked on one point and the B box straddled
    # the diameter line.  Moving the SYMBOL is the only lever -- edge_xy just
    # picks the circle, it cannot pin where the tag lands.
    # 3 o'clock is spoken for by the bore's Ra symbol and 225 deg by the
    # diameter line's far arrow, which leaves the lower right: 16.4 mm of clear
    # circumference from one and 9.6 mm from the other, with the symbol 10 mm
    # inside the block's bottom edge and clear of BlockHeight's extension lines
    # (those start at x=0.189).
    pivot_edge = (
        _front_x(BORE_HALF_SPACING),
        _front_y(0.0) - BORE_R_SHEET,
    )
    # SolidWorks restricts this axis-attached tag and live readback normalizes
    # the intended sheet point by 2.927 mm.  Bound only annotation placement.
    add_datum_feature(
        adapter,
        front,
        edge_xy=pivot_edge,
        symbol_xy=(_front_x(BORE_HALF_SPACING) + 0.0145, _front_y(0.0) - 0.026),
        datum="B",
        label="pivot bore axis",
    )
    right_half_depth = BLOCK_DEPTH * SHEET_SCALE[0] / 2000.0
    add_datum_feature(
        adapter,
        right,
        edge_xy=(RIGHT_CENTER[0] + right_half_depth, RIGHT_CENTER[1]),
        symbol_xy=(RIGHT_CENTER[0] + right_half_depth + 0.016, RIGHT_CENTER[1] + 0.020),
        datum="C",
        label="block broad face",
    )
    lift_edge = (
        _front_x(-BORE_HALF_SPACING),
        _front_y(-LIFT_BORE_DROP) + BORE_R_SHEET,
    )
    add_feature_control_frame(
        adapter,
        front,
        edge_xy=lift_edge,
        frame_xy=(0.048, 0.172),
        characteristic="parallelism",
        tolerance="0.10",
        datums=("B",),
        diameter=True,
        label="lift-bore parallelism",
    )
    west_screw_edge = (
        _front_x(-SCREW_HALF_SPACING),
        TOP_CENTER[1] + SCREW_R_SHEET,
    )
    add_native_hole_callout(
        adapter,
        top,
        edge_xy=west_screw_edge,
        callout_xy=(0.052, 0.252),
        label="hold-down screw hole",
    )
    # Position frame stacked directly UNDER the 2X size callout, led to the
    # same hole, so the control unambiguously governs the two-hole pattern.
    add_feature_control_frame(
        adapter,
        top,
        edge_xy=west_screw_edge,
        frame_xy=(0.052, 0.240),
        characteristic="position",
        tolerance="0.25",
        datums=("A", "B", "C"),
        diameter=True,
        quantity="2X",
        label="hold-down hole position",
    )
    # Anchored on the bore's RIGHT quadrant, not its top (which datum B already
    # uses), so the pull is a short one into the band between the two views.
    # At (0.188, 0.196) the symbol's arm -- which reaches ~6 mm LEFT of the
    # anchor -- printed over the top view's lower-right corner; the leader only
    # grazed the view boundary, so the crossing gate stayed silent and just the
    # render showed it. Three things box in the replacement:
    #   * y=0.163 keeps the leader BELOW datum B's frame (y=0.166..0.174) the
    #     whole way -- routed at B's own height it drew straight through it;
    #   * the arm (x=0.194..0.210) sits above BlockHeight's upper extension line
    #     at y=0.155 and right of the front view, which ends at x=0.189; and
    #   * the text, which renders ABOVE the arm and to its RIGHT (~0.213..0.239
    #     at y~0.177), stays under PivotBoreDia's leader shoulder at y=0.196.
    pivot_right_edge = (
        _front_x(BORE_HALF_SPACING) + BORE_R_SHEET,
        _front_y(0.0),
    )
    add_surface_finish(
        adapter,
        front,
        edge_xy=pivot_right_edge,
        symbol_xy=(0.200, 0.163),
        roughness_ra="1.6",
        label="pivot bore finish",
    )

    # 0.020: a note is left-aligned on its anchor, so the ink starts here. The
    # bound is the 12.7 mm zone margin (~0.0127) the layout gate measures against,
    # which the re-centred frame rule now matches (~0.0126); 0.020 clears both.
    add_property_linked_note(adapter, "Manufacturing Notes", 0.020, 0.060)
    add_property_linked_note(adapter, "Isometric View Note", 0.335, 0.180)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Pinion Pivot Block Manufacturing Drawing",
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
