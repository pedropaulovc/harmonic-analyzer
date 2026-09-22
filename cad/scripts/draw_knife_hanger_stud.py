"""Create the manufacturing drawing for the modified McMaster 91247A720 stud.

The vendor bolt is purchased by SKU and shortened at the threaded end before
installation. The finished under-head and restored end deburr are native model
controls; undimensioned purchased head/thread geometry is reference.
"""

from __future__ import annotations

import argparse
import math
import sys
from typing import Any

import _stock_trim_drawing as trim_drawing
import _telemetry
from _common import _early_bound, check, run_build
from _drawing_common import (
    DrawingOutputs,
    add_property_linked_note,
    curate_view_dimensions,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    set_hidden_lines_removed,
    set_hidden_lines_visible,
    stamp_drawing_summary,
)
from _drawing_registry import DRAWINGS_BY_NAME
from _stock_trim_drawing import TrimSheet
from build_knife_hanger_stud import SHANK_DIA, THREAD_TIP_Y_MM
from knife_hanger_stud_spec import (
    CHAMFER_ANGLE_DEG,
    CHAMFER_ANGLE_TOLERANCE_DEG,
    CHAMFER_WIDTH_MM,
    CHAMFER_WIDTH_TOLERANCE_MM,
    DIMENSION_PRECISION,
    DIMENSION_TOLERANCE_TYPES,
    DRAWING_DIMENSIONS,
    FINISHED_UNDERHEAD_MM,
    FINISHED_UNDERHEAD_TOLERANCE_MM,
)
from solidworks_mcp.adapters.solidworks.drawing import place_view

SPEC = DRAWINGS_BY_NAME["knife_hanger_stud"]
SOURCE = SPEC.source
OUTPUTS = DrawingOutputs(**SPEC.outputs)
SHEET_SCALE = (2.0, 1.0)
ISO_SCALE = (2.0, 1.0)
FRONT_CENTER = (0.120, 0.165)
ISO_CENTER = (0.350, 0.210)
FRONT_KEEP = {"FinishedOverall": (0.045, 0.165)}
DETAIL_KEEP = {"ChamferWidth": (0.235, 0.125), "ChamferAngle": (0.315, 0.155)}
SHEET = TrimSheet(
    sheet_scale=SHEET_SCALE,
    detail_center=(0.280, 0.145),
    detail_scale=(12.0, 1.0),
    fence_radius_mm=2.5,
    cut_end_y_mm=THREAD_TIP_Y_MM,
    detail_offset_mm=1.0,
    detail_label_xy=(0.330, 0.110),
    parent_letter_offset=(0.020, 0.014),
    detail_center_x_mm=SHANK_DIA / 2.0 - CHAMFER_WIDTH_MM / 2.0,
)
EXPECTED_CONTROLS = {
    "FinishedOverall": (
        FINISHED_UNDERHEAD_MM / 1000,
        -FINISHED_UNDERHEAD_TOLERANCE_MM / 1000,
        FINISHED_UNDERHEAD_TOLERANCE_MM / 1000,
    ),
    "ChamferWidth": (
        CHAMFER_WIDTH_MM / 1000,
        -CHAMFER_WIDTH_TOLERANCE_MM / 1000,
        CHAMFER_WIDTH_TOLERANCE_MM / 1000,
    ),
    "ChamferAngle": (
        math.radians(CHAMFER_ANGLE_DEG),
        -math.radians(CHAMFER_ANGLE_TOLERANCE_DEG),
        math.radians(CHAMFER_ANGLE_TOLERANCE_DEG),
    ),
}


def _verify_controls(adapter: Any, annotations: list[Any]) -> None:
    trim_drawing.verify_machining_controls(
        adapter,
        annotations,
        expected=EXPECTED_CONTROLS,
        tolerance_types=DIMENSION_TOLERANCE_TYPES,
        precision=DIMENSION_PRECISION,
    )


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")
    check("open modified stud", await adapter.open_model(str(SOURCE)))
    required = (
        "Number",
        "Material Specification",
        "Finish",
        "Quantity",
        "Stock Name",
        "Supplier",
        "Supplier SKUs",
        "Manufacturing Notes",
        "Isometric View Note",
    )
    read_required_properties(adapter.currentModel, required, required=required)
    draw, _sheet = new_project_drawing(
        adapter, property_view=SPEC.artifact_stem, scale=SHEET_SCALE, layout=SPEC.layout
    )
    stamp_drawing_summary(
        adapter,
        draw,
        {
            0: "Knife-Hanger Stud — Modified Stock Drawing",
            1: "Native controls for modified purchased stock",
            2: "Harmonic Analyzer Project",
            3: "MHA-119; McMaster-Carr 91247A720",
            4: "Finished under-head and cut-end deburr are native controls",
        },
    )
    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=SHEET_SCALE)
    place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=ISO_SCALE)
    set_hidden_lines_visible(adapter, front)
    detail = trim_drawing.end_detail(adapter, front, SHEET)
    set_hidden_lines_visible(adapter, detail)
    _early_bound(detail, "IView").UpdateViewDisplayGeometry()
    detail_annotations = curate_view_dimensions(
        adapter,
        detail,
        keep=DETAIL_KEEP,
        view_label="cut end detail",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    front_annotations = curate_view_dimensions(
        adapter,
        front,
        keep=FRONT_KEEP,
        view_label="finished under-head length",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    annotations = [*front_annotations, *detail_annotations]
    _verify_controls(adapter, annotations)
    add_property_linked_note(adapter, "Supplier", 0.016, 0.056, char_height=0.003)
    add_property_linked_note(adapter, "Supplier SKUs", 0.016, 0.047, char_height=0.003)
    add_property_linked_note(adapter, "Stock Name", 0.016, 0.038, char_height=0.003)
    add_property_linked_note(adapter, "Isometric View Note", 0.345, 0.145)
    add_property_linked_note(
        adapter, "Manufacturing Notes", 0.016, 0.085, char_height=0.003
    )
    for view in (front, detail):
        set_hidden_lines_removed(adapter, view)
    trim_drawing.position_detail_label(adapter, detail, SHEET)
    trim_drawing.position_parent_detail_letter(adapter, front, SHEET)
    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Knife-Hanger Stud — Modified Stock Drawing",
        scale=SHEET_SCALE,
        layout=SPEC.layout,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[SPEC.artifact_stem])
    parser.parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
