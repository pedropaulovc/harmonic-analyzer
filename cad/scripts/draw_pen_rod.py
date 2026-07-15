r"""Create the curated machinist drawing for the pen square rod."""

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
from pen_rod_spec import ROD_LENGTH, WIRE_HOLE_DIA, WIRE_HOLE_Y
from solidworks_mcp.adapters.solidworks.drawing import (
    auto_center_marks,
    place_view,
)


SPEC = DRAWINGS_BY_NAME["pen_rod"]
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

SHEET_SCALE = (1.0, 1.0)
TOP_VIEW_SCALE = 4.0
FRONT_CENTER = (0.070, 0.150)
RIGHT_CENTER = (0.140, 0.150)
TOP_CENTER = (0.070, 0.245)
ISO_CENTER = (0.340, 0.195)

FRONT_KEEP = {
    "Length": (FRONT_CENTER[0] - 0.030, FRONT_CENTER[1]),
    "Section": (FRONT_CENTER[0], FRONT_CENTER[1] - ROD_LENGTH / 2000.0 - 0.012),
}
TOP_KEEP = {
    "Depth": (TOP_CENTER[0] - 0.034, TOP_CENTER[1]),
}
# No-oversize on BOTH functional slide faces: Section (front, X width) and Depth
# (top, Z width) are the two 5 mm faces the rod rides on in the v-block, so each
# is controlled +0.00/-0.05 rather than leaning on the general SECTION +/-0.05.
DIMENSION_CALLOUTS = {"Section": "+0.00/-0.05"}
TOP_DIMENSION_CALLOUTS = {"Depth": "+0.00/-0.05"}


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open pen-rod source", await adapter.open_model(str(SOURCE)))
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
            "Top View Note",
        ),
        required=(
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
            "Manufacturing Notes",
            "Top View Note",
        ),
    )
    drawing_model, _sheet = new_project_drawing(
        adapter, property_view=PART_STEM, scale=SHEET_SCALE
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Pen Rod Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "pen rod; square brass slide rod; wire hole",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=(1, 1))
    right = place_view(adapter, str(SOURCE), "*Right", *RIGHT_CENTER, scale=(1, 1))
    top = place_view(adapter, str(SOURCE), "*Top", *TOP_CENTER, scale=(4, 1))
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=(1, 1))
    for view in (front, top, iso):
        set_hidden_lines_removed(adapter, view)
    set_hidden_lines_visible(adapter, right)

    front_annotations = curate_view_dimensions(
        adapter, front, keep=FRONT_KEEP, view_label="front"
    )
    top_annotations = curate_view_dimensions(
        adapter, top, keep=TOP_KEEP, view_label="top"
    )
    set_dimension_callouts(adapter, front_annotations, DIMENSION_CALLOUTS)
    set_dimension_callouts(adapter, top_annotations, TOP_DIMENSION_CALLOUTS)
    if not auto_center_marks(adapter, front, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center mark to the wire hole")

    front_bottom = (FRONT_CENTER[0], FRONT_CENTER[1] - ROD_LENGTH / 2000.0)
    front_top = (FRONT_CENTER[0], FRONT_CENTER[1] + ROD_LENGTH / 2000.0)
    front_side = (FRONT_CENTER[0] - 0.0025, FRONT_CENTER[1])
    front_far_side = (FRONT_CENTER[0] + 0.0025, FRONT_CENTER[1])
    hole_center_y = front_bottom[1] + WIRE_HOLE_Y / 1000.0
    hole_bottom = (FRONT_CENTER[0], hole_center_y - WIRE_HOLE_DIA / 2000.0)
    hole_side = (FRONT_CENTER[0] + WIRE_HOLE_DIA / 2000.0, hole_center_y)
    right_bottom = (RIGHT_CENTER[0], RIGHT_CENTER[1] - ROD_LENGTH / 2000.0)
    right_top = (RIGHT_CENTER[0], RIGHT_CENTER[1] + ROD_LENGTH / 2000.0)

    add_edge_dimension(
        adapter,
        front,
        p0=front_bottom,
        p1=hole_bottom,
        text_xy=(FRONT_CENTER[0] + 0.032, FRONT_CENTER[1] + 0.030),
        label="wire-hole length location",
    )
    # Locate the wire hole ACROSS the square section too: the native callout gives
    # only the drill size, so without this the cross-hole could sit off-centre and
    # still satisfy every shown dimension. Left slide face -> hole (line-to-circle,
    # so the value is to the hole centre) reads 2.50 of the 5.00 section = centred.
    add_edge_dimension(
        adapter,
        front,
        p0=front_side,
        p1=hole_side,
        text_xy=(FRONT_CENTER[0] - 0.030, hole_center_y + 0.020),
        label="wire-hole centerline location",
    )
    add_native_hole_callout(
        adapter,
        front,
        edge_xy=hole_side,
        callout_xy=(FRONT_CENTER[0] + 0.034, hole_center_y + 0.017),
        label="pen-rod wire hole",
    )

    add_datum_feature(
        adapter,
        front,
        edge_xy=front_side,
        symbol_xy=(front_side[0] - 0.016, FRONT_CENTER[1] - 0.030),
        datum="A",
        label="pen-rod slide face",
    )
    add_feature_control_frame(
        adapter,
        front,
        edge_xy=front_far_side,
        frame_xy=(FRONT_CENTER[0] + 0.032, FRONT_CENTER[1] - 0.018),
        characteristic="parallelism",
        tolerance="0.03",
        datums=("A",),
        label="pen-rod opposite slide face parallelism",
    )
    add_feature_control_frame(
        adapter,
        front,
        edge_xy=front_bottom,
        frame_xy=(FRONT_CENTER[0] + 0.032, FRONT_CENTER[1] - 0.042),
        characteristic="perpendicularity",
        tolerance="0.05",
        datums=("A",),
        label="pen-rod bottom end squareness",
    )
    add_surface_finish(
        adapter,
        front,
        edge_xy=front_side,
        symbol_xy=(front_side[0] - 0.026, FRONT_CENTER[1] + 0.015),
        roughness_ra="1.6",
        label="pen-rod slide face finish",
    )
    for edge, y, label in (
        (right_bottom, right_bottom[1] - 0.016, "bottom end finish"),
        (right_top, right_top[1] + 0.016, "top end finish"),
    ):
        add_surface_finish(
            adapter,
            right,
            edge_xy=edge,
            symbol_xy=(RIGHT_CENTER[0] + 0.018, y),
            roughness_ra="3.2",
            label=label,
        )

    add_property_linked_note(adapter, "Manufacturing Notes", 0.014, 0.058)
    add_property_linked_note(adapter, "Top View Note", 0.036, 0.266)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Pen Rod Manufacturing Drawing",
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
