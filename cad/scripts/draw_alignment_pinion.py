r"""Create the curated manufacturing drawing for the alignment pinion drum (42T).

Follows the batch gear-drawing pattern (see ``draw_cylinder_gear``), adapted for
a long drum: the *Front end view carries the bore + tooth datum, and the *Right
profile view shows the full 143 mm face length. Drawn 1:1; no isometric (a long
thin drum is fully described by the two orthographic views).
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
    set_hidden_lines_removed,
    stamp_drawing_summary,
)
from _drawing_registry import DRAWINGS_BY_NAME
from _gear_drawing_entities import visible_circle_edge
from alignment_pinion_spec import BORE_DIA, FACE_WIDTH, OUTSIDE_DIA
from solidworks_mcp.adapters.solidworks.drawing import (
    auto_center_marks,
    place_view,
)


SPEC = DRAWINGS_BY_NAME["alignment_pinion"]
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
VIEW_SCALE = (1, 1)
FRONT_CENTER = (0.150, 0.185)   # toothed end view
RIGHT_CENTER = (0.285, 0.185)   # long drum profile (143 mm face)

BORE_R = BORE_DIA * VIEW_SCALE[0] / 2000.0
HALF_OD = OUTSIDE_DIA * VIEW_SCALE[0] / 2000.0
HALF_FACE = FACE_WIDTH * VIEW_SCALE[0] / 2000.0
LEFT_END_X = RIGHT_CENTER[0] - HALF_FACE
RIGHT_END_X = RIGHT_CENTER[0] + HALF_FACE

FRONT_KEEP = {
    "ArborBoreDia": (FRONT_CENTER[0] - 0.050, FRONT_CENTER[1] - 0.030),
}


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open alignment-pinion source", await adapter.open_model(str(SOURCE)))
    read_required_properties(
        adapter.currentModel,
        (
            "Number",
            "Revision",
            "Title",
            "Material Specification",
            "Finish",
            "Quantity",
            "Gear Data",
            "Manufacturing Notes",
        ),
        required=(
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
            "Gear Data",
            "Manufacturing Notes",
        ),
    )
    drawing_model, _sheet = new_project_drawing(
        adapter, property_view=PART_STEM, scale=SHEET_SCALE
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Alignment Pinion Drum Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "alignment pinion; brass drum; 42T; zeroing drive",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=VIEW_SCALE)
    right = place_view(adapter, str(SOURCE), "*Right", *RIGHT_CENTER, scale=VIEW_SCALE)
    for view in (front, right):
        set_hidden_lines_removed(adapter, view)

    curate_view_dimensions(adapter, front, keep=FRONT_KEEP, view_label="front")
    if not auto_center_marks(adapter, front, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center mark to drum bore")
    bore_edge = visible_circle_edge(adapter, front, BORE_DIA)

    # Overall face length across the drum ends in the profile view.
    add_edge_dimension(
        adapter,
        right,
        p0=(LEFT_END_X, RIGHT_CENTER[1] - HALF_OD),
        p1=(RIGHT_END_X, RIGHT_CENTER[1] - HALF_OD),
        text_xy=(RIGHT_CENTER[0], RIGHT_CENTER[1] - HALF_OD - 0.028),
        label="drum face length",
    )

    bore_top = (FRONT_CENTER[0], FRONT_CENTER[1] + BORE_R)
    add_datum_feature(
        adapter,
        front,
        edge_xy=bore_top,
        symbol_xy=(FRONT_CENTER[0], FRONT_CENTER[1] + 0.025),
        datum="A",
        label="drum bore axis",
        entity=bore_edge,
        shoulder=True,
    )
    add_feature_control_frame(
        adapter,
        right,
        edge_xy=(LEFT_END_X, RIGHT_CENTER[1] + HALF_OD * 0.55),
        frame_xy=(LEFT_END_X - 0.030, RIGHT_CENTER[1] + HALF_OD + 0.014),
        characteristic="perpendicularity",
        tolerance="0.05",
        datums=("A",),
        label="drum end squareness to bore",
    )
    bore_bottom = (FRONT_CENTER[0], FRONT_CENTER[1] - BORE_R)
    add_surface_finish(
        adapter,
        front,
        edge_xy=bore_bottom,
        symbol_xy=(FRONT_CENTER[0] + 0.014, FRONT_CENTER[1] - 0.050),
        roughness_ra="1.6",
        label="drum bore finish",
        entity=bore_edge,
    )

    add_property_linked_note(adapter, "Gear Data", 0.018, 0.262)
    add_property_linked_note(adapter, "Manufacturing Notes", 0.018, 0.085)
    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Alignment Pinion Drum Manufacturing Drawing",
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
