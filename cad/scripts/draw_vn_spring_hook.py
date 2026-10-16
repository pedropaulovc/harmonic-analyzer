"""Create the manufacturing drawing for the modified McMaster 9489T111 anchor.

The anchor is purchased by SKU but is NOT installed as supplied: the captive
hex nut is discarded (the MHA-CH-012 round jam nut locks it) and the shank is cut to
cross the summing-lever plate and carry that nut, so the sheet carries the
same two cutting controls as the counter anchor (``draw_boss_hook``) -- the
finished overall length to the eye crown and the restored 45 deg deburr at the
new end. The length band is the title block's; ``vn_spring_hook_spec`` shows
the shortest in-band part still keeps two full threads past the nut.

Run with SolidWorks open::

    uv run python cad\\scripts\\draw_vn_spring_hook.py vn-spring-hook
"""

from __future__ import annotations

import argparse
import math
import sys
from typing import Any

from solidworks_mcp.adapters.solidworks.drawing import place_view

from _check import check
from _com import _early_bound
from _drawing_common import (
    DrawingOutputs,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    stamp_drawing_summary,
)
from _drawing_dimension_import import curate_view_dimensions
from _drawing_dimensions import set_dimension_precision
from _drawing_notes import add_property_linked_note
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_view_display import set_hidden_lines_visible
from _session import run_build
import _stock_trim_drawing as trim_drawing
from _stock_trim_drawing import TrimSheet
import _telemetry
from vn_spring_hook_spec import (
    CHAMFER_ANGLE_DEG,
    CHAMFER_ANGLE_TOLERANCE_DEG,
    CHAMFER_WIDTH_MM,
    CHAMFER_WIDTH_TOLERANCE_MM,
    DIMENSION_PRECISION,
    DIMENSION_TOLERANCE_TYPES,
    FINISHED_OVERALL_MM,
    FINISHED_OVERALL_TOLERANCE_MM,
    TRIM,
)

SPEC = DRAWINGS_BY_NAME["vn_spring_hook"]
SOURCE = SPEC.source
OUTPUTS = DrawingOutputs(**SPEC.outputs)
# The finished part is 28.8 x 12.7 mm since its shank carries the MHA-CH-012
# jam nut under the plate: 5:1 keeps the front view inside the counter
# anchor's 4:1 sheet band, raised so the cut end clears the notes, and the
# Ø3.5 shank end needs 20:1 to carry a readable 0.46 deburr.
SHEET_SCALE = (5.0, 1.0)
ISO_SCALE = (3.0, 1.0)
FRONT_CENTER = (0.100, 0.172)
ISO_CENTER = (0.310, 0.213)
FRONT_KEEP = {"FinishedOverall": (0.042, 0.172)}
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
            3: "MHA-VN-012; McMaster-Carr 9489T111",
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
