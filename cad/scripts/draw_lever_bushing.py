r"""Create the curated machinist drawing for the lever-bank spacer bushing."""

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
    set_hidden_lines_visible,
    stamp_drawing_summary,
)
from _drawing_registry import DRAWINGS_BY_NAME
from lever_bushing_spec import BORE_DIA, LENGTH, OUTER_DIA
from solidworks_mcp.adapters.solidworks.drawing import (
    auto_center_marks,
    place_view,
)


SPEC = DRAWINGS_BY_NAME["lever_bushing"]
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

    check("open lever-bushing source", await adapter.open_model(str(SOURCE)))
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
            0: "Lever Bushing Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "lever bushing; turned spacer; brass",
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

    outer_edge = (
        FRONT_CENTER[0] + OUTER_DIA * SHEET_SCALE[0] / 2000.0,
        FRONT_CENTER[1],
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
    # Attach at the bore's TOP, not its 3 o'clock: the symbol is asked for
    # straight above the bore, and a datum tag on a CIRCULAR edge slides its
    # attachment to the circle point nearest the symbol. Picking the 3 o'clock
    # while asking for a 12 o'clock symbol made SolidWorks re-attach at the top
    # and clamp the box down beside it -- it landed at y~0.222, inside the view,
    # straddling the annulus and the vertical centerline. Pick and symbol now
    # agree (the draw_pivot_bushing spelling), so the +0.037 is honored and the
    # box clears the view's 0.229 top.
    add_datum_feature(
        adapter,
        front,
        edge_xy=bore_top,
        symbol_xy=(FRONT_CENTER[0], FRONT_CENTER[1] + 0.037),
        datum="A",
        label="bushing bore axis",
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
        edge_xy=outer_edge,
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
    # Sits just right of the front view, level with the bore. From (0.160, 0.225)
    # the leader ran ~70 mm diagonally back across the whole ring to reach the
    # bore, tangling with the Ø12.00 and Ø6.50 dimension lines that already meet
    # at the centre. The symbol draws UP and RIGHT of its anchor (roughly
    # x+0.039, y+0.019) and the leader leaves the anchor itself, so anchoring
    # just above/right of the bore keeps the leader short and the body in the
    # empty band between the views: clear of the Ø6.50 callout below (it ends at
    # y=0.205), the runout frame above (y=0.251) and the OD-runout leader that
    # drops down x~0.104..0.115.
    add_surface_finish(
        adapter,
        front,
        edge_xy=bore_edge,
        symbol_xy=(0.120, 0.212),
        roughness_ra="1.6",
        label="bushing bore finish",
    )

    # x=0.020: the DRAWN border rule is at 0.0159, not the 0.0127 zone margin the
    # sheet declares, and the anchor is the text's left edge -- 0.014 put the ink
    # at 0.0141, printing through the rule. The audit bounds notes by the declared
    # margin, so it cannot see this; eye-verified.
    add_property_linked_note(adapter, "Manufacturing Notes", 0.020, 0.095)
    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Lever Bushing Manufacturing Drawing",
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
