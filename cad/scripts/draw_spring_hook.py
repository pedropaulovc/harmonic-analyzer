"""Create the manufacturing drawing for the modified McMaster 9489T111 anchor.

The anchor is purchased by SKU but is NOT installed as supplied: the captive
hex nut is discarded and the shank is cut back into the summing-lever plate it
threads into, so the sheet carries the same two cutting controls as the counter
anchor (``draw_boss_hook``) -- the finished overall length to the eye crown and
the restored 45 deg deburr at the new end. Both bands are the title block's;
see ``spring_hook_spec`` for why the 1/16 in recess absorbs them.

Run with SolidWorks open::

    uv run python cad\\scripts\\draw_spring_hook.py spring-hook
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
    set_dimension_precision,
    set_hidden_lines_visible,
    stamp_drawing_summary,
)
from _drawing_registry import DRAWINGS_BY_NAME
from _stock_trim_drawing import TrimSheet
from spring_hook_spec import (
    FINISHED_OVERALL_MM,
    FINISHED_OVERALL_TOLERANCE_MM,
    CHAMFER_WIDTH_MM,
    CHAMFER_WIDTH_TOLERANCE_MM,
    CHAMFER_ANGLE_DEG,
    CHAMFER_ANGLE_TOLERANCE_DEG,
    DIMENSION_PRECISION,
    DIMENSION_TOLERANCE_TYPES,
    TRIM,
)
from solidworks_mcp.adapters.solidworks.drawing import place_view

SPEC = DRAWINGS_BY_NAME["spring_hook"]
SOURCE = SPEC.source
OUTPUTS = DrawingOutputs(**SPEC.outputs)
# The finished part is 19.368 x 12.7 mm: 5:1 fills the same sheet area the
# counter anchor fills at 4:1, and the Ø3.5 shank end needs 20:1 to carry a
# readable 0.46 deburr.
SHEET_SCALE = (5.0, 1.0)
ISO_SCALE = (3.0, 1.0)
FRONT_CENTER = (0.100, 0.165)
ISO_CENTER = (0.310, 0.213)
FRONT_KEEP = {"FinishedOverall": (0.042, 0.165)}
DETAIL_KEEP = {"ChamferWidth": (0.235, 0.090), "ChamferAngle": (0.340, 0.115)}
SHEET = TrimSheet(
    sheet_scale=SHEET_SCALE,
    detail_center=(0.280, 0.115),
    detail_scale=(20.0, 1.0),
    fence_radius_mm=2.0,
    cut_end_y_mm=TRIM.shank_end_y_mm,
    detail_offset_mm=1.0,
    detail_label_xy=(0.360, 0.085),
    parent_letter_offset=(0.020, 0.014),
)
EXPECTED_CONTROLS = {
    "FinishedOverall": (
        FINISHED_OVERALL_MM / 1000,
        -FINISHED_OVERALL_TOLERANCE_MM / 1000,
        FINISHED_OVERALL_TOLERANCE_MM / 1000,
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
    check("open modified anchor", await adapter.open_model(str(SOURCE)))
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
            0: "Channel Spring Anchor — Modified Stock Drawing",
            1: "Manufacturing controls for modified purchased stock",
            2: "Harmonic Analyzer Project",
            3: "MHA-090; McMaster-Carr 9489T111",
            4: "Native dimension-driven trim and end deburr",
        },
    )
    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=SHEET_SCALE)
    place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=ISO_SCALE)
    set_hidden_lines_visible(adapter, front)
    detail = trim_drawing.end_detail(adapter, front, SHEET)
    set_hidden_lines_visible(adapter, detail)
    # Import against the new HLV geometry without waiting for a window repaint.
    _early_bound(detail, "IView").UpdateViewDisplayGeometry()
    # The detail claims its manufacturing dimensions before the parent import.
    detail_annotations = curate_view_dimensions(
        adapter, detail, keep=DETAIL_KEEP, view_label="cut end detail"
    )
    front_annotations = curate_view_dimensions(
        adapter, front, keep=FRONT_KEEP, view_label="finished overall"
    )
    annotations = [*front_annotations, *detail_annotations]
    set_dimension_precision(adapter, annotations, DIMENSION_PRECISION)
    _verify_controls(adapter, annotations)
    add_property_linked_note(adapter, "Supplier", 0.016, 0.060, char_height=0.003)
    add_property_linked_note(adapter, "Supplier SKUs", 0.080, 0.060, char_height=0.003)
    add_property_linked_note(adapter, "Stock Name", 0.016, 0.049, char_height=0.003)
    add_property_linked_note(adapter, "Isometric View Note", 0.275, 0.163)
    add_property_linked_note(
        adapter, "Manufacturing Notes", 0.016, 0.083, char_height=0.003
    )
    for view in (front, detail):
        set_hidden_lines_visible(adapter, view)
    trim_drawing.position_detail_label(adapter, detail, SHEET)
    trim_drawing.position_parent_detail_letter(adapter, front, SHEET)
    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Channel Spring Anchor — Modified Stock Drawing",
        scale=SHEET_SCALE,
        layout=SPEC.layout,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[SPEC.artifact_stem])
    parser.parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
