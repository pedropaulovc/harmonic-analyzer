r"""Create the curated machinist drawing for the pinion pivot block.

The SLDPRT remains authoritative.  This recipe supplies only the block's
views, dimension layout, hole callouts, and manufacturing notes; every shared
sheet/template, import, curation, and export behavior lives in
``_drawing_common``.

The sheet runs at 3:1 (the block is 40 x 20.5 x 10.25); the isometric carries an
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
    DrawingOutputs,
    add_edge_dimension,
    add_native_hole_callout,
    add_property_linked_note,
    add_surface_finish,
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
from _surface_finish import surface_finish_by_key
from pinion_pivot_block_spec import (
    BLOCK_DEPTH,
    BLOCK_WEST,
    BLOCK_WIDTH as BLOCK_WIDTH,
    BORE_DIA,
    FRONT_BBOX_CX,
    FRONT_BBOX_CY,
    LIFT_BORE_SPACING,
    SCREW_HALF_SPACING,
    SCREW_HOLE_DIA,
    SURFACE_FINISHES,
)
from solidworks_mcp.adapters.solidworks.drawing import (
    auto_center_marks,
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

# Sheet layout (meters).  U28: the part origin is the PIVOT bore, so
# the front view's model bbox runs -26..14 in X and -12..8.5 in Y; at 3:1 the
# view is 120 x 61.5 mm.  Third angle: the top view (block seen from above,
# carrying the two hold-down holes) sits ABOVE the front view; the right view
# (20.5 x 10.25 stock section) sits to its right.
FRONT_CENTER = (0.140, 0.128)
TOP_CENTER = (0.140, 0.222)
RIGHT_CENTER = (0.285, 0.128)
ISO_CENTER = (0.360, 0.225)


def _front_x(model_x_mm: float) -> float:
    """Sheet X of a model-X point in the front/top views (3:1, bbox-centred)."""
    return FRONT_CENTER[0] + (model_x_mm - FRONT_BBOX_CX) * SHEET_SCALE[0] / 1000.0


def _front_y(model_y_mm: float) -> float:
    """Sheet Y of a model-Y point in the front view (3:1, bbox-centred)."""
    return FRONT_CENTER[1] + (model_y_mm - FRONT_BBOX_CY) * SHEET_SCALE[0] / 1000.0


BORE_R_SHEET = BORE_DIA * SHEET_SCALE[0] / 2000.0
SCREW_R_SHEET = SCREW_HOLE_DIA * SHEET_SCALE[0] / 2000.0

# Per-view survivors of the marked-dimension import: parametric name -> sheet
# position.  Everything is measured from the pivot bore (the part
# origin): the lift-bore spacing sits above the view, the pivot-to-west-end
# station and overall width below it; the pivot height and overall height stack
# on the east side next to the pivot; the lift-bore rise sits between the bores; the
# leadered diameters land in the clear corners.
FRONT_KEEP = {
    "BlockWidth": (_front_x(FRONT_BBOX_CX), 0.074),
    "AnchorX": (_front_x(-BLOCK_WEST / 2.0), 0.084),
    "LiftBoreX": (_front_x(-LIFT_BORE_SPACING / 2.0), 0.165),
    "BlockHeight": (0.226, 0.123),
    "AnchorZ": (0.212, 0.113),
    # BETWEEN the bores: the witnesses leave each centre toward the other and
    # stop at the dimension line, so neither crosses the other bore (render r1:
    # placed left, the pivot-centre witness ran through the lift bore).
    "LiftBoreCz": (_front_x(-LIFT_BORE_SPACING / 2.0), 0.1365),
    # Every horizontal/vertical witness from the pivot centre crosses its rim
    # at 0/90/180/270 deg.  The leader runs to the NEAR end of the text's
    # shoulder, so the text sits right of the bore (render r1: centred at
    # 0.180 the leader ran straight up LiftBoreX's east witness) and the
    # leader climbs at ~65 deg, clear of the Ra symbol's ~30 deg sector.
    "PivotBoreDia": (0.212, 0.195),
    # Shallow, to the left: the parallelism frame's leader climbs from the
    # lift bore's top above this one, so the two never cross.
    "LiftBoreDia": (0.045, 0.168),
}
RIGHT_KEEP = {"Depth": (RIGHT_CENTER[0], 0.168)}
TOP_KEEP = {}
DIMENSION_CALLOUTS = {
    "PivotBoreDia": "THRU - REAM 1/4 IN",
    "LiftBoreDia": "THRU - REAM 1/4 IN",
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
        adapter, property_view=PART_STEM, scale=SHEET_SCALE, layout=SPEC.layout
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
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=(2, 1))
    for view in (front, iso):
        set_hidden_lines_removed(adapter, view)
    # The top view exposes the two vertical hold-down drills; the right view
    # shows both Z-bores edge-on.  HLV keeps their hidden circles readable.
    for view in (top, right):
        set_hidden_lines_visible(adapter, view)

    front_annotations = curate_view_dimensions(
        adapter, front, keep=FRONT_KEEP, view_label="front"
    )
    # Right view: the 20.5 x 10.25 stock section carries only the block depth.
    right_annotations = curate_view_dimensions(
        adapter, right, keep=RIGHT_KEEP, view_label="right"
    )
    # Top view: the hold-downs are located by sheet dimensions below.
    top_annotations = curate_view_dimensions(
        adapter, top, keep=TOP_KEEP, view_label="top"
    )
    set_dimension_callouts(
        adapter,
        [*front_annotations, *top_annotations, *right_annotations],
        DIMENSION_CALLOUTS,
    )

    for view, label in ((front, "front"), (top, "top")):
        if not auto_center_marks(adapter, view, holes=True, size=0.0025):
            raise RuntimeError(f"failed to add ASME center marks to {label} view")

    # Hold-down holes: ordinary coordinates baselined from the WEST end, the
    # edge the pivot bore's 26.00 already runs from.  Policy rules 3/4: a block
    # carries no frames, datums or basic boxes.  Both drills sit at exact
    # mid-depth, so one depth coordinate from the broad face locates the pair.
    west_end = (_front_x(-BLOCK_WEST), TOP_CENTER[1])
    for x_mm, text_y, label in (
        (-SCREW_HALF_SPACING, 0.248, "west hold-down station"),
        (SCREW_HALF_SPACING, 0.258, "east hold-down station"),
    ):
        add_edge_dimension(
            adapter,
            top,
            p0=west_end,
            p1=(_front_x(x_mm), TOP_CENTER[1] + SCREW_R_SHEET),
            text_xy=((west_end[0] + _front_x(x_mm)) / 2.0, text_y),
            label=label,
            orientation="horizontal",
        )
    add_edge_dimension(
        adapter,
        top,
        p0=(
            _front_x(-SCREW_HALF_SPACING - 5.0),
            TOP_CENTER[1] - BLOCK_DEPTH * SHEET_SCALE[0] / 2000.0,
        ),
        p1=(_front_x(-SCREW_HALF_SPACING), TOP_CENTER[1] - SCREW_R_SHEET),
        text_xy=(0.062, 0.212),
        label="hold-down depth location",
    )
    # The size callout rides the EAST hole, from the clear sheet right of the
    # top view (render r1: led from the left margin it crossed the block).
    east_screw_edge = (
        _front_x(SCREW_HALF_SPACING),
        TOP_CENTER[1] + SCREW_R_SHEET,
    )
    add_native_hole_callout(
        adapter,
        top,
        edge_xy=east_screw_edge,
        callout_xy=(0.245, 0.250),
        label="hold-down screw hole",
    )
    # Anchored on the bore rim at ~30 deg: the pivot centre's AnchorZ witness
    # leaves the rim at 0 deg and LiftBoreX's at 90 deg, and the diameter
    # leader climbs at ~70 deg, so 30 deg is the clear sector.  The arm
    # (x~0.199..0.215) sits above BlockHeight's upper extension line (y=0.154)
    # and the text, which renders ABOVE and RIGHT of the arm, stays under the
    # PivotBoreDia callout.
    pivot_right_edge = (
        _front_x(0.0) + BORE_R_SHEET * 0.866,
        _front_y(0.0) + BORE_R_SHEET * 0.5,
    )
    add_surface_finish(
        adapter,
        front,
        edge_xy=pivot_right_edge,
        symbol_xy=(0.205, 0.161),
        control=surface_finish_by_key(SURFACE_FINISHES, "pivot_bore"),
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
        layout=SPEC.layout,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[PART_STEM])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
