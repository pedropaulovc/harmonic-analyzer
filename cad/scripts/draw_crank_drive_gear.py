r"""Create the curated manufacturing drawing for the crank-drive gear (64T).

Follows the batch gear-drawing pattern (see ``draw_cylinder_gear``). The helical
crossed-axis accommodation is stated in the GEAR DATA note (helix angle,
backlash, mating pinion).
"""

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
    add_property_linked_note,
    add_surface_finish,
    curate_view_dimensions,
    finalize_drawing,
    new_project_drawing,
    read_required_view_properties,
    set_dimension_callouts,
    set_dimension_precision,
    set_hidden_lines_removed,
    stamp_drawing_summary,
)
from _drawing_registry import DRAWINGS_BY_NAME
from _gear_drawing_entities import visible_circle_edge, visible_tooth_tip_silhouette
from crank_drive_gear_spec import BORE_DIA, FACE_WIDTH, OUTSIDE_DIA
from solidworks_mcp.adapters.solidworks.drawing import (
    auto_center_marks,
    place_view,
)


SPEC = DRAWINGS_BY_NAME["crank_drive_gear"]
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
FRONT_CENTER = (0.225, 0.175)
RIGHT_CENTER = (0.300, 0.175)
ISO_CENTER = (0.375, 0.205)
GEAR_DATA_POS = (0.025, 0.262)

HALF_OD = OUTSIDE_DIA * VIEW_SCALE[0] / 2000.0
FRONT_FACE_X = RIGHT_CENTER[0] - FACE_WIDTH * VIEW_SCALE[0] / 2000.0

FRONT_KEEP = {
    "BoreDia": (FRONT_CENTER[0] - 0.055, FRONT_CENTER[1] - 0.030),
}
DIMENSION_CALLOUTS = {
    # Reamed slip fit on the crankshaft journal (nominal-or-under, like the
    # arbor journals): min 0.03 diametral clearance, inside the project's
    # 0.025..0.075 shaft-in-bushing policy. Also settles which tolerance-block
    # row governs the bore (neither .XX +/-0.51 nor DRILLED +0.10/0 -- the
    # callout's own limits do).
    "BoreDia": "THRU - REAM\n+0.050/+0.030",
}
DIMENSION_PRECISION = {"BoreDia": 3}


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

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
            0: "Crank-Drive Gear Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "crank-drive gear; steel; 64T helical",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=VIEW_SCALE)
    read_required_view_properties(
        adapter,
        front,
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
        raise RuntimeError("failed to add ASME center mark to gear bore")
    bore_edge = visible_circle_edge(adapter, front, BORE_DIA)
    tooth_tip_silhouette = visible_tooth_tip_silhouette(adapter, right, OUTSIDE_DIA)

    add_datum_feature(
        adapter,
        front,
        entity=bore_edge,
        symbol_xy=(FRONT_CENTER[0] + 0.020, FRONT_CENTER[1] + 0.039),
        datum="A",
        label="crank-drive gear bore axis",
        shoulder=True,
        position_tolerance_m=0.080,
    )
    add_feature_control_frame(
        adapter,
        right,
        edge_xy=(FRONT_FACE_X, RIGHT_CENTER[1] + HALF_OD * 0.55),
        frame_xy=(FRONT_FACE_X - 0.034, RIGHT_CENTER[1] + HALF_OD + 0.010),
        characteristic="perpendicularity",
        tolerance="0.05",
        datums=("A",),
        quantity="2X AXIAL END FACES",
        label="gear end-face squareness to bore",
    )
    add_feature_control_frame(
        adapter,
        right,
        entity=tooth_tip_silhouette,
        frame_xy=(0.270, 0.260),
        characteristic="circular_runout",
        tolerance="0.05",
        datums=("A",),
        quantity="TOOTH TIPS",
        label="gear tooth-tip circular runout",
        entity_type="SILHOUETTE",
    )
    add_surface_finish(
        adapter,
        front,
        symbol_xy=(FRONT_CENTER[0] + 0.015, FRONT_CENTER[1] - 0.052),
        roughness_ra="1.6",
        label="crank-drive gear bore finish",
        entity=bore_edge,
        leader_attach_xy=(
            FRONT_CENTER[0],
            FRONT_CENTER[1] - BORE_DIA * VIEW_SCALE[0] / 2000.0,
        ),
    )

    add_property_linked_note(
        adapter, "Gear Data", *GEAR_DATA_POS, char_height=0.0025
    )
    add_property_linked_note(
        adapter, "Manufacturing Notes", 0.018, 0.102, char_height=0.0025
    )
    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Crank-Drive Gear Manufacturing Drawing",
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
