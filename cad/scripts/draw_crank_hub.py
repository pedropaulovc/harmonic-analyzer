r"""Create the curated manufacturing drawing for through hub MHA-137."""

from __future__ import annotations

import argparse
import sys
from typing import Any

import _telemetry
from _common import CAD_ROOT, check, run_build
from _drawing_common import (
    DrawingOutputs,
    add_native_hole_callout,
    add_property_linked_note,
    add_view_centerline,
    assert_imported_precision,
    curate_view_dimensions,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    set_dimension_callouts,
    set_hidden_lines_removed,
    stamp_drawing_summary,
)
from _drawing_registry import DRAWINGS_BY_NAME
from _hole_spec import blind_cut_dia_mm, drill_process
from crank_hub_spec import (
    BORE_CALLOUT,
    CROSS_HOLE_CALLOUT,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    HUB_LENGTH,
    ISOMETRIC_VIEW_NOTE,
    SEAT_CALLOUT,
    SERVICE_PIN_HOLE_SPEC,
    SERVICE_PIN_STATION,
)
from solidworks_mcp.adapters.solidworks.drawing import auto_center_marks, place_view


SPEC = DRAWINGS_BY_NAME["crank_hub"]
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
FRONT_CENTER = (0.090, 0.155)  # outboard end view, looking inboard
RIGHT_CENTER = (0.225, 0.155)  # axial section/silhouette view
ISO_CENTER = (0.355, 0.215)
SIDE_BOTTOM = RIGHT_CENTER[1] - HUB_LENGTH * VIEW_SCALE[0] / 2000.0
SERVICE_PIN_CENTER = (
    RIGHT_CENTER[0],
    SIDE_BOTTOM + SERVICE_PIN_STATION * VIEW_SCALE[0] / 1000.0,
)
SERVICE_PIN_DIA = blind_cut_dia_mm(SERVICE_PIN_HOLE_SPEC)
# Pick the barrel's cylindrical face off-axis and above the MHA-024 cross-hole.
# The through hole is seen end-on here, so a pick inside its circle sees no
# face (run 20260923T023246758Z-97bfca38 picked 2 mm below its centre).
BARREL_FACE_PICK = (
    RIGHT_CENTER[0] + 0.012,
    SERVICE_PIN_CENTER[1] + SERVICE_PIN_DIA * VIEW_SCALE[0] / 2000.0 + 0.007,
)
# Every size and callout sits outside the silhouettes.  The bore callout
# stands above the end view.  The side view's three lengths share the faced
# outboard end as one baseline on the left; its diameters stand above (barrel)
# and below (seat), which leaves the right side clear for the cross-hole
# callout's leader.
SIDE_TOP = SIDE_BOTTOM + HUB_LENGTH * VIEW_SCALE[0] / 1000.0
FRONT_KEEP = {"BoreDia": (FRONT_CENTER[0], FRONT_CENTER[1] + 0.070)}
RIGHT_KEEP = {
    "SeatLength": (RIGHT_CENTER[0] - 0.036, SIDE_BOTTOM + 0.012),
    "ServicePinStation": (RIGHT_CENTER[0] - 0.050, SIDE_BOTTOM + 0.026),
    "HubLength": (RIGHT_CENTER[0] - 0.064, SIDE_BOTTOM + 0.045),
    "BarrelDia": (RIGHT_CENTER[0], SIDE_TOP + 0.012),
    "SeatDia": (RIGHT_CENTER[0] - 0.075, SIDE_BOTTOM - 0.014),
}
HOLE_CALLOUT_XY = (0.330, 0.140)
DIMENSION_CALLOUTS = {
    "BoreDia": BORE_CALLOUT,
    "SeatDia": SEAT_CALLOUT,
}


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open crank-hub source", await adapter.open_model(str(SOURCE)))
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
        adapter, property_view=PART_STEM, scale=SHEET_SCALE, layout=SPEC.layout
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Crank Through Hub Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "crank hub; through sleeve; matched shoulder fit; taper pin",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    front = place_view(adapter, str(SOURCE), "*Bottom", *FRONT_CENTER, scale=VIEW_SCALE)
    right = place_view(adapter, str(SOURCE), "*Right", *RIGHT_CENTER, scale=VIEW_SCALE)
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=(2, 1))
    for view in (front, right, iso):
        set_hidden_lines_removed(adapter, view)

    front_annotations = curate_view_dimensions(
        adapter,
        front,
        keep=FRONT_KEEP,
        view_label="outboard end",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    right_annotations = curate_view_dimensions(
        adapter,
        right,
        keep=RIGHT_KEEP,
        view_label="side",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    annotations = [*front_annotations, *right_annotations]
    set_dimension_callouts(adapter, annotations, DIMENSION_CALLOUTS)
    assert_imported_precision(adapter, annotations, DRAWING_PRECISION_BY_NAME)

    if not auto_center_marks(adapter, front, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center marks to crank-hub end view")
    if not auto_center_marks(adapter, right, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center marks to crank-hub side view")
    add_view_centerline(
        adapter,
        right,
        face_xy=BARREL_FACE_PICK,
        label="crank hub axis centerline",
    )
    add_native_hole_callout(
        adapter,
        right,
        edge_xy=(
            SERVICE_PIN_CENTER[0],
            SERVICE_PIN_CENTER[1] + SERVICE_PIN_DIA * VIEW_SCALE[0] / 2000.0,
        ),
        callout_xy=HOLE_CALLOUT_XY,
        label="MHA-024 hub pilot",
        process=f"{CROSS_HOLE_CALLOUT}\n{drill_process(SERVICE_PIN_HOLE_SPEC)}",
    )
    add_property_linked_note(adapter, "Manufacturing Notes", 0.016, 0.070)
    add_property_linked_note(adapter, "Isometric View Note", 0.325, 0.175)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Crank Through Hub Manufacturing Drawing",
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
