r"""Create the curated machinist drawing for the magnifying-lever clamp block.

A prismatic brass block (20 x 26 x 12) carrying two skew slip bores -- the lever
bore Ø6.2 along the depth, the vertical-rod bore Ø5.2 along the height -- and a
#4-40 thumb-screw tapped from the top into the lever bore.  Every face is flat,
so the block dimensions ride the auto-imported profile marks (FRONT: block +
lever bore; TOP: rod bore) with the depth added across the right-view section.

Run with SolidWorks open::

    uv run python cad\scripts\draw_magnifying_clamp.py magnifying-clamp
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

import _telemetry
from _common import CAD_ROOT, check, run_build
from _drawing_common import (
    DrawingOutputs,
    add_datum_feature,
    add_edge_dimension,
    add_feature_control_frame,
    add_property_linked_note,
    add_surface_finish,
    curate_view_dimensions,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    set_dimension_callouts,
    stamp_drawing_summary,
)
from _drawing_registry import DRAWINGS_BY_NAME
from magnifying_clamp_spec import (
    BLOCK_DEPTH,
    BLOCK_HEIGHT,
    BLOCK_WIDTH,
    LEVER_BORE_DIA,
    LEVER_BORE_Y,
    ROD_BORE_X,
)
from solidworks_mcp.adapters.solidworks.drawing import (
    auto_center_marks,
    place_view,
)


SPEC = DRAWINGS_BY_NAME["magnifying_clamp"]
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

FRONT_CENTER = (0.120, 0.120)
TOP_CENTER = (0.120, 0.215)
# Right view pulled left of the title block (x>~0.258, y<~0.070): the 48x104 mm
# section at x=0.250 clipped the title block's top-left corner (layout audit).
RIGHT_CENTER = (0.225, 0.120)
ISO_CENTER = (0.350, 0.215)


def _front_x(model_x_mm: float) -> float:
    return FRONT_CENTER[0] + (model_x_mm) * SHEET_SCALE[0] / 1000.0


def _front_y(model_y_mm: float) -> float:
    return FRONT_CENTER[1] + (model_y_mm - BLOCK_HEIGHT / 2.0) * SHEET_SCALE[0] / 1000.0


FRONT_KEEP = {
    # In the 0.176..0.201 free band between the notes paragraph (whose longest
    # line reaches ~0.175) and the right view's left edge: at a centred or
    # +0.052 position the 20.00 text landed inside the notes text (eye pass;
    # display dims are overlap-exempt in the audit, so only the eye catches it).
    "Width": (FRONT_CENTER[0] + 0.072, _front_y(0.0) - 0.014),
    "Height": (FRONT_CENTER[0] - BLOCK_WIDTH * 2.0 / 1000.0 - 0.022, FRONT_CENTER[1]),
    "LeverBoreYDim": (FRONT_CENTER[0] + BLOCK_WIDTH * 2.0 / 1000.0 + 0.020, _front_y(LEVER_BORE_Y / 2.0)),
    "LeverBoreDiaDim": (FRONT_CENTER[0] - 0.045, _front_y(LEVER_BORE_Y) + 0.030),
}
TOP_KEEP = {
    "RodBoreXDim": (_front_x(ROD_BORE_X / 2.0), TOP_CENTER[1] - 0.038),
    "RodBoreDiaDim": (_front_x(ROD_BORE_X) + 0.034, TOP_CENTER[1] + 0.030),
}
RIGHT_KEEP: dict[str, tuple[float, float]] = {}

DIMENSION_CALLOUTS = {
    "LeverBoreDiaDim": "THRU - SLIP FIT Ø6 ROD",
    "RodBoreDiaDim": "THRU - SLIP FIT Ø5 ROD",
}

RIGHT_HALF_Z = BLOCK_DEPTH / 2.0 * SHEET_SCALE[0] / 1000.0
RIGHT_HALF_Y = BLOCK_HEIGHT / 2.0 * SHEET_SCALE[0] / 1000.0


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open magnifying-clamp source", await adapter.open_model(str(SOURCE)))
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
    drawing_model, _sheet = new_project_drawing(
        adapter, property_view=PART_STEM, scale=SHEET_SCALE
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Magnifying Clamp Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "magnifying clamp; brass block; skew slip bores",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=(4, 1))
    top = place_view(adapter, str(SOURCE), "*Top", *TOP_CENTER, scale=(4, 1))
    right = place_view(adapter, str(SOURCE), "*Right", *RIGHT_CENTER, scale=(4, 1))
    place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=(2, 1))
    # Front carries the vertical-rod + screw hidden bores; top exposes the rod
    # bore + the tapped screw hole crossing the depth.

    front_annotations = curate_view_dimensions(
        adapter, front, keep=FRONT_KEEP, view_label="front"
    )
    top_annotations = curate_view_dimensions(
        adapter, top, keep=TOP_KEEP, view_label="top"
    )
    curate_view_dimensions(adapter, right, keep=RIGHT_KEEP, view_label="right")
    set_dimension_callouts(
        adapter, [*front_annotations, *top_annotations], DIMENSION_CALLOUTS
    )
    for view, label in ((front, "front"), (top, "top")):
        if not auto_center_marks(adapter, view, holes=True, size=0.0025):
            raise RuntimeError(f"failed to add ASME center marks to {label} view")

    # Block depth (12): dimension the right view's flat front/back silhouette
    # faces (a prism section, so the edges are pickable).
    add_edge_dimension(
        adapter,
        right,
        p0=(RIGHT_CENTER[0] - RIGHT_HALF_Z, RIGHT_CENTER[1]),
        p1=(RIGHT_CENTER[0] + RIGHT_HALF_Z, RIGHT_CENTER[1]),
        text_xy=(RIGHT_CENTER[0], RIGHT_CENTER[1] - RIGHT_HALF_Y - 0.014),
        label="block-depth overall",
    )

    # The #4-40 thumb-screw hole is a small top-view circle whose exact sheet
    # edge is not a dependable pick at this scale; its size + function ride the
    # notes (spec DRAWING_NOTES) and the top-view centre mark locates it, rather
    # than a fragile associative callout.

    # Datum A = the block bottom seat (front view); Ra 1.6 on the lever bore (the
    # functional sliding surface), tagged on its rim.
    # Datum A hangs off the END view's bottom edge: everything below the front
    # view belongs to the notes paragraph, which swallowed the flag at both
    # round-1 positions (obscured, then inside the notes text).
    add_datum_feature(
        adapter,
        right,
        edge_xy=(RIGHT_CENTER[0] + 0.010, _front_y(0.0)),
        symbol_xy=(RIGHT_CENTER[0] + 0.024, _front_y(0.0) - 0.020),
        datum="A",
        label="block bottom seat",
    )
    add_feature_control_frame(
        adapter,
        front,
        # pick + frame right of the rod-bore hidden-line column: at the centred
        # pick both blind reviews read the top-face parallelism as attached to
        # the vertical bore
        edge_xy=(FRONT_CENTER[0] + 0.038, _front_y(BLOCK_HEIGHT)),
        frame_xy=(FRONT_CENTER[0] + 0.052, _front_y(BLOCK_HEIGHT) + 0.016),
        characteristic="parallelism",
        tolerance="0.10",
        datums=("A",),
        label="block top-face parallelism",
    )
    add_surface_finish(
        adapter,
        front,
        edge_xy=(
            FRONT_CENTER[0] + LEVER_BORE_DIA * SHEET_SCALE[0] / 2000.0,
            _front_y(LEVER_BORE_Y),
        ),
        symbol_xy=(FRONT_CENTER[0] + 0.030, _front_y(LEVER_BORE_Y) + 0.008),
        roughness_ra="1.6",
        label="lever bore finish",
    )

    add_property_linked_note(adapter, "Manufacturing Notes", 0.020, 0.060)
    add_property_linked_note(adapter, "Isometric View Note", 0.330, 0.180)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Magnifying Clamp Manufacturing Drawing",
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
