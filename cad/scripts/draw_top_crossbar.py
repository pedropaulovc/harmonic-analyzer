r"""Create the curated machinist drawing for the cast-iron top crossbar."""

from __future__ import annotations

import argparse
import sys
from typing import Any

import _telemetry
from _common import CAD_ROOT, run_build
from _drawing_common import (
    DrawingOutputs,
    add_datum_feature,
    add_feature_control_frame,
    add_native_hole_callout,
    add_property_linked_note,
    add_surface_finish,
    add_edge_dimension,
    curate_view_dimensions,
    finalize_drawing,
    new_project_drawing,
    read_required_view_properties,
    set_hidden_lines_removed,
    set_hidden_lines_visible,
    set_basic_dimension,
    stamp_drawing_summary,
)
from _drawing_registry import DRAWINGS_BY_NAME
from solidworks_mcp.adapters.solidworks.drawing import (
    auto_center_marks,
    place_view,
)
from top_crossbar_spec import (
    BAR_HEIGHT,
    BAR_LENGTH,
    BAR_WIDTH,
    STUD_HOLE_DIA,
)


SPEC = DRAWINGS_BY_NAME["top_crossbar"]
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
TOP_CENTER = (0.090, 0.215)
FRONT_CENTER = (0.165, 0.135)
ISO_CENTER = (0.355, 0.200)

TOP_KEEP = {
    "Depth": (TOP_CENTER[0] - 0.035, TOP_CENTER[1]),
}
FRONT_KEEP = {
    "Width": (FRONT_CENTER[0], FRONT_CENTER[1] - 0.034),
    "Height": (FRONT_CENTER[0] - 0.035, FRONT_CENTER[1]),
}

async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    drawing_model, _sheet = new_project_drawing(
        adapter, property_view=PART_STEM, scale=SHEET_SCALE
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Top Crossbar Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "top crossbar; cast iron; clearance hole",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    top = place_view(adapter, str(SOURCE), "*Top", *TOP_CENTER, scale=(1, 2))
    read_required_view_properties(
        adapter,
        top,
        (
            "Number", "Revision", "Title", "Material Specification", "Finish",
            "Quantity", "Manufacturing Notes", "Top View Note",
            "Isometric View Note",
        ),
        required=(
            "Number", "Material Specification", "Finish", "Quantity",
            "Manufacturing Notes", "Top View Note", "Isometric View Note",
        ),
    )
    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=(1, 1))
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=(1, 2))
    for view in (top, iso):
        set_hidden_lines_removed(adapter, view)
    set_hidden_lines_visible(adapter, front)

    curate_view_dimensions(adapter, top, keep=TOP_KEEP, view_label="top")
    curate_view_dimensions(adapter, front, keep=FRONT_KEEP, view_label="front")
    if not auto_center_marks(adapter, top, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center mark to top-view stud hole")

    hole_radius_sheet = STUD_HOLE_DIA / 4000.0
    length_location = add_edge_dimension(
        adapter,
        top,
        p0=(TOP_CENTER[0], TOP_CENTER[1] - BAR_LENGTH / 4000.0),
        p1=(TOP_CENTER[0], TOP_CENTER[1] - hole_radius_sheet),
        text_xy=(TOP_CENTER[0] + 0.030, TOP_CENTER[1] - 0.025),
        label="stud-hole length location",
    )
    set_basic_dimension(adapter, length_location, label="stud-hole length location")

    front_bottom = (
        FRONT_CENTER[0],
        FRONT_CENTER[1] - BAR_HEIGHT / 2000.0,
    )
    front_left = (
        FRONT_CENTER[0] - BAR_WIDTH / 2000.0,
        FRONT_CENTER[1],
    )
    lower_end = (TOP_CENTER[0], TOP_CENTER[1] - BAR_LENGTH / 4000.0)
    upper_end = (TOP_CENTER[0], TOP_CENTER[1] + BAR_LENGTH / 4000.0)
    hole_edge = (
        TOP_CENTER[0] + STUD_HOLE_DIA / 4000.0,
        TOP_CENTER[1],
    )
    add_datum_feature(
        adapter,
        front,
        edge_xy=front_bottom,
        symbol_xy=(FRONT_CENTER[0], front_bottom[1] - 0.016),
        datum="A",
        label="crossbar bottom face",
    )
    add_datum_feature(
        adapter,
        front,
        edge_xy=front_left,
        symbol_xy=(front_left[0] - 0.016, FRONT_CENTER[1]),
        datum="B",
        label="crossbar side face",
    )
    add_datum_feature(
        adapter,
        top,
        edge_xy=lower_end,
        symbol_xy=(TOP_CENTER[0] + 0.018, lower_end[1]),
        datum="C",
        label="crossbar reference end seat",
    )
    add_feature_control_frame(
        adapter,
        top,
        edge_xy=hole_edge,
        frame_xy=(0.112, 0.235),
        characteristic="position",
        tolerance="0.20",
        datums=("A", "B", "C"),
        diameter=True,
        label="crossbar stud-hole position",
    )
    add_feature_control_frame(
        adapter,
        top,
        edge_xy=lower_end,
        frame_xy=(0.115, 0.175),
        characteristic="perpendicularity",
        tolerance="0.10",
        datums=("A", "B"),
        label="crossbar reference-end squareness",
    )
    add_feature_control_frame(
        adapter,
        top,
        edge_xy=upper_end,
        frame_xy=(0.115, 0.255),
        characteristic="parallelism",
        tolerance="0.10",
        datums=("C",),
        label="crossbar end-seat parallelism",
    )
    for edge, y, label in (
        (lower_end, 0.165, "lower end-seat finish"),
        (upper_end, 0.245, "upper end-seat finish"),
    ):
        add_surface_finish(
            adapter,
            top,
            edge_xy=edge,
            symbol_xy=(0.175, y),
            roughness_ra="3.2",
            label=label,
        )
    add_property_linked_note(adapter, "Manufacturing Notes", 0.014, 0.090)
    add_property_linked_note(adapter, "Top View Note", 0.045, 0.155)
    add_native_hole_callout(
        adapter,
        top,
        edge_xy=hole_edge,
        callout_xy=(0.125, TOP_CENTER[1] - 0.010),
        label="crossbar stud hole",
    )
    add_property_linked_note(adapter, "Isometric View Note", 0.330, 0.155)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Top Crossbar Manufacturing Drawing",
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
