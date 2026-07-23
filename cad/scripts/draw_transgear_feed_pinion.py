r"""Create the curated manufacturing drawing for the transgear feed pinion (12T).

Follows the batch gear-drawing pattern (see ``draw_cylinder_gear``). Drawn 3:1
so the small long-faced pinion reads clearly.
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
    add_feature_control_frame,
    add_property_linked_note,
    add_surface_finish,
    curate_view_dimensions,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    set_dimension_callouts,
    set_dimension_precision,
    set_hidden_lines_removed,
    stamp_drawing_summary,
)
from _drawing_registry import DRAWINGS_BY_NAME
from _gear_drawing_entities import visible_circle_edge
from transgear_feed_pinion_spec import BORE_DIA, FACE_WIDTH, OUTSIDE_DIA
from solidworks_mcp.adapters.solidworks.drawing import (
    auto_center_marks,
    place_view,
)


SPEC = DRAWINGS_BY_NAME["transgear_feed_pinion"]
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
VIEW_SCALE = (3, 1)
FRONT_CENTER = (0.190, 0.175)
RIGHT_CENTER = (0.295, 0.175)
ISO_CENTER = (0.385, 0.210)

BORE_R = BORE_DIA * VIEW_SCALE[0] / 2000.0
HALF_OD = OUTSIDE_DIA * VIEW_SCALE[0] / 2000.0
FRONT_FACE_X = RIGHT_CENTER[0] - FACE_WIDTH * VIEW_SCALE[0] / 2000.0

FRONT_KEEP = {
    "BoreDia": (FRONT_CENTER[0] - 0.055, FRONT_CENTER[1] - 0.030),
}
DIMENSION_CALLOUTS = {
    # Reamed slip fit on the stud's turned Ø5 front seat (nominal-or-under, like
    # the arbor journals): min 0.03 diametral clearance, inside the project's
    # 0.025..0.075 shaft-in-bushing policy. Also settles which tolerance-block
    # row governs the bore (neither .XX +/-0.51 nor DRILLED +0.10/0 -- the
    # callout's own limits do).
    "BoreDia": "THRU - REAM\n+0.05/+0.03",
}
DIMENSION_PRECISION = {"BoreDia": 2}


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open transgear-feed-pinion source", await adapter.open_model(str(SOURCE)))
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
        adapter,
        category=SPEC.category,
        property_view=PART_STEM,
        scale=SHEET_SCALE,
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Transgear Feed Pinion Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "transgear feed pinion; brass; 12T; meshes the rack",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=VIEW_SCALE)
    right = place_view(adapter, str(SOURCE), "*Right", *RIGHT_CENTER, scale=VIEW_SCALE)
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=VIEW_SCALE)
    for view in (front, right, iso):
        set_hidden_lines_removed(adapter, view)

    front_annotations = curate_view_dimensions(
        adapter, front, keep=FRONT_KEEP, view_label="front"
    )
    set_dimension_callouts(adapter, front_annotations, DIMENSION_CALLOUTS)
    set_dimension_precision(adapter, front_annotations, DIMENSION_PRECISION)
    if not auto_center_marks(adapter, front, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center mark to pinion bore")
    bore_edge = visible_circle_edge(adapter, front, BORE_DIA)

    bore_top = (FRONT_CENTER[0], FRONT_CENTER[1] + BORE_R)
    add_datum_feature(
        adapter,
        front,
        edge_xy=bore_top,
        symbol_xy=(FRONT_CENTER[0], FRONT_CENTER[1] + 0.030),
        datum="A",
        label="feed pinion bore axis",
        shoulder=True,
        position_tolerance_m=0.0001,
    )
    add_feature_control_frame(
        adapter,
        right,
        edge_xy=(FRONT_FACE_X, RIGHT_CENTER[1] + HALF_OD * 0.55),
        frame_xy=(FRONT_FACE_X - 0.034, RIGHT_CENTER[1] + HALF_OD + 0.010),
        characteristic="perpendicularity",
        tolerance="0.05",
        datums=("A",),
        label="pinion face squareness to bore",
    )
    add_surface_finish(
        adapter,
        front,
        symbol_xy=(FRONT_CENTER[0] + 0.016, FRONT_CENTER[1] - 0.058),
        roughness_ra="1.6",
        label="feed pinion bore finish",
        entity=bore_edge,
    )

    add_property_linked_note(adapter, "Gear Data", 0.018, 0.262)
    add_property_linked_note(adapter, "Manufacturing Notes", 0.018, 0.092)
    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Transgear Feed Pinion Manufacturing Drawing",
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
