r"""Create the curated machinist drawing for the lever fulcrum shaft."""

from __future__ import annotations

import argparse
import sys
from typing import Any

import _telemetry
from _common import CAD_ROOT, check, run_build
from _drawing_common import (
    DrawingOutputs,
    add_datum_feature,
    add_feature_control_frame,
    add_property_linked_note,
    add_surface_finish,
    curate_view_dimensions,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    set_dimension_callouts,
    set_hidden_lines_removed,
    stamp_drawing_summary,
)
from _drawing_registry import DRAWINGS_BY_NAME
from fulcrum_shaft_spec import SHAFT_DIA, SHAFT_LENGTH
from solidworks_mcp.adapters.solidworks.drawing import (
    auto_center_marks,
    place_view,
)


SPEC = DRAWINGS_BY_NAME["fulcrum_shaft"]
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
END_VIEW_SCALE = 2.0
FRONT_CENTER = (0.055, 0.205)
RIGHT_CENTER = (
    FRONT_CENTER[0] + SHAFT_LENGTH * SHEET_SCALE[0] / 2000.0 + 0.045,
    FRONT_CENTER[1],
)
ISO_CENTER = (0.355, 0.205)

FRONT_KEEP = {
    "ShaftDia": (
        FRONT_CENTER[0] - SHAFT_DIA * END_VIEW_SCALE / 1000.0 - 0.025,
        FRONT_CENTER[1] + 0.008,
    ),
}
RIGHT_KEEP = {
    "Depth": (RIGHT_CENTER[0], RIGHT_CENTER[1] - 0.025),
}
DIMENSION_CALLOUTS = {"ShaftDia": "+0.00/-0.02"}


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open fulcrum-shaft source", await adapter.open_model(str(SOURCE)))
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
            "End View Note",
        ),
        required=(
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
            "Manufacturing Notes",
            "End View Note",
        ),
    )
    drawing_model, _sheet = new_project_drawing(
        adapter, property_view=PART_STEM, scale=SHEET_SCALE
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Fulcrum Shaft Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "fulcrum shaft; bearing shaft; turned steel",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=(2, 1))
    right = place_view(adapter, str(SOURCE), "*Right", *RIGHT_CENTER, scale=(1, 1))
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=(1, 1))
    for view in (front, right, iso):
        set_hidden_lines_removed(adapter, view)

    front_annotations = curate_view_dimensions(
        adapter, front, keep=FRONT_KEEP, view_label="front"
    )
    curate_view_dimensions(adapter, right, keep=RIGHT_KEEP, view_label="right")
    set_dimension_callouts(adapter, front_annotations, DIMENSION_CALLOUTS)
    # SolidWorks classifies a solid circular end silhouette under the same
    # AutoInsertCenterMarks2 "hole" bit as a bored circle; disabling that bit
    # makes the API a guaranteed no-op even though the end view is circular.
    if not auto_center_marks(adapter, front, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center mark to shaft end view")

    end_circle = (
        FRONT_CENTER[0] + SHAFT_DIA * END_VIEW_SCALE / 2000.0,
        FRONT_CENTER[1],
    )
    left_end = (RIGHT_CENTER[0] - SHAFT_LENGTH / 2000.0, RIGHT_CENTER[1])
    right_end = (RIGHT_CENTER[0] + SHAFT_LENGTH / 2000.0, RIGHT_CENTER[1])
    add_datum_feature(
        adapter,
        front,
        edge_xy=end_circle,
        symbol_xy=(FRONT_CENTER[0], FRONT_CENTER[1] + 0.024),
        datum="A",
        label="fulcrum shaft axis",
    )
    add_feature_control_frame(
        adapter,
        front,
        edge_xy=end_circle,
        frame_xy=(RIGHT_CENTER[0], 0.232),
        characteristic="cylindricity",
        tolerance="0.01",
        label="fulcrum bearing cylindricity",
    )
    for edge, x, label in (
        (left_end, left_end[0] - 0.014, "left end perpendicularity"),
        (right_end, right_end[0] + 0.014, "right end perpendicularity"),
    ):
        add_feature_control_frame(
            adapter,
            right,
            edge_xy=edge,
            frame_xy=(x, 0.180),
            characteristic="perpendicularity",
            tolerance="0.05",
            datums=("A",),
            label=label,
        )
    add_surface_finish(
        adapter,
        front,
        edge_xy=end_circle,
        symbol_xy=(RIGHT_CENTER[0], 0.245),
        roughness_ra="1.6",
        label="fulcrum bearing finish",
    )

    add_property_linked_note(adapter, "Manufacturing Notes", 0.014, 0.108)
    add_property_linked_note(adapter, "End View Note", 0.020, 0.170)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Fulcrum Shaft Manufacturing Drawing",
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
