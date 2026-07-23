r"""Create the curated machinist drawing for the rocker pivot spacer bushing."""

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
    add_view_centerline,
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
from pivot_bushing_spec import BORE_DIA, LENGTH, OUTER_DIA
from solidworks_mcp.adapters.solidworks.drawing import (
    auto_center_marks,
    place_view,
)


SPEC = DRAWINGS_BY_NAME["pivot_bushing"]
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
FRONT_CENTER = (0.080, 0.205)
RIGHT_CENTER = (
    FRONT_CENTER[0] + (OUTER_DIA + LENGTH) * SHEET_SCALE[0] / 1000.0 + 0.045,
    FRONT_CENTER[1],
)
ISO_CENTER = (0.315, 0.205)

FRONT_KEEP = {
    "OuterDia": (
        FRONT_CENTER[0] - 0.035,
        FRONT_CENTER[1] + 0.010,
    ),
    "BoreDia": (
        FRONT_CENTER[0] + OUTER_DIA * SHEET_SCALE[0] / 1000.0 + 0.005,
        FRONT_CENTER[1] - 0.010,
    ),
}
RIGHT_KEEP = {
    "Depth": (RIGHT_CENTER[0], RIGHT_CENTER[1] - 0.040),
}
DIMENSION_CALLOUTS = {
    "BoreDia": "THRU - REAM\n+0.03/-0.00",
    "Depth": "+/-0.03",
}


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open pivot-bushing source", await adapter.open_model(str(SOURCE)))
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
        ),
        required=(
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
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
            0: "Pivot Bushing Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "pivot bushing; turned spacer; brass",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=(4, 1))
    right = place_view(adapter, str(SOURCE), "*Right", *RIGHT_CENTER, scale=(4, 1))
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=(4, 1))
    for view in (front, iso):
        set_hidden_lines_removed(adapter, view)
    set_hidden_lines_visible(adapter, right)

    front_annotations = curate_view_dimensions(
        adapter, front, keep=FRONT_KEEP, view_label="front"
    )
    right_annotations = curate_view_dimensions(
        adapter, right, keep=RIGHT_KEEP, view_label="right"
    )
    annotations = [*front_annotations, *right_annotations]
    set_dimension_callouts(adapter, annotations, DIMENSION_CALLOUTS)
    if not auto_center_marks(adapter, front, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center marks to front view")
    add_view_centerline(
        adapter,
        right,
        face_xy=(RIGHT_CENTER[0], RIGHT_CENTER[1] + 0.012),
        label="bushing axis centerline",
    )

    # Spread the front-view attach points around the circles (bore top for the
    # datum, OD 45-degree points for runout/finish) so the four leaders do not
    # converge on one spot at the circle's right side.
    outer_r = OUTER_DIA * SHEET_SCALE[0] / 2000.0
    diag = 0.7071
    outer_edge_upper = (
        FRONT_CENTER[0] + outer_r * diag,
        FRONT_CENTER[1] + outer_r * diag,
    )
    bore_edge = (
        FRONT_CENTER[0] + BORE_DIA * SHEET_SCALE[0] / 2000.0,
        FRONT_CENTER[1],
    )
    bore_top = (
        FRONT_CENTER[0],
        FRONT_CENTER[1] + BORE_DIA * SHEET_SCALE[0] / 2000.0,
    )
    half_depth = LENGTH * SHEET_SCALE[0] / 2000.0
    left_end = (RIGHT_CENTER[0] - half_depth, RIGHT_CENTER[1])
    right_end = (RIGHT_CENTER[0] + half_depth, RIGHT_CENTER[1])
    # Live readback normalizes this restricted axis tag by 4.478 um.  Bound
    # only the annotation placement; part dimensions and GD&T remain unchanged.
    add_datum_feature(
        adapter,
        front,
        edge_xy=bore_top,
        symbol_xy=(FRONT_CENTER[0], FRONT_CENTER[1] + 0.037),
        datum="A",
        label="bushing bore axis",
        position_tolerance_m=0.000005,
    )
    add_datum_feature(
        adapter,
        right,
        edge_xy=left_end,
        symbol_xy=(left_end[0] - 0.018, RIGHT_CENTER[1]),
        datum="B",
        label="bushing reference end",
    )
    add_feature_control_frame(
        adapter,
        front,
        edge_xy=outer_edge_upper,
        frame_xy=(0.115, 0.255),
        characteristic="circular_runout",
        tolerance="0.05",
        datums=("A",),
        label="bushing OD runout",
    )
    add_feature_control_frame(
        adapter,
        right,
        edge_xy=right_end,
        frame_xy=(right_end[0] + 0.014, 0.180),
        characteristic="parallelism",
        tolerance="0.03",
        datums=("B",),
        label="bushing end-face parallelism",
    )
    # Held close to the bore it controls: at (0.160, 0.225) the leader ran back
    # across the whole front view as a long shallow diagonal and converged on
    # the bore with the two diameter leaders. Here it is a short, roughly
    # horizontal pull into the gap between the two views. The symbol arm reaches
    # ~6 mm LEFT of the anchor (clearing the OD circle at x=0.100) and the text
    # renders ABOVE the arm and to its RIGHT, spanning ~0.131..0.157 at y~0.224:
    # clear of the O6.50 callout below (its text tops out at y=0.201), of the
    # runout frame above, and of the right view starting at x=0.174.
    add_surface_finish(
        adapter,
        front,
        edge_xy=bore_edge,
        symbol_xy=(0.118, 0.210),
        roughness_ra="1.6",
        label="bushing bore finish",
    )

    add_property_linked_note(adapter, "Manufacturing Notes", 0.020, 0.095)
    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Pivot Bushing Manufacturing Drawing",
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
