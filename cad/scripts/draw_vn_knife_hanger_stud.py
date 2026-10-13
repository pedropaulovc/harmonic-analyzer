"""Create MHA-VN-024's modified-stock cut and inspection drawing."""

from __future__ import annotations

import argparse
import math
import sys
from typing import Any

from solidworks_mcp.adapters.solidworks.drawing import dimension_name, place_view

import _telemetry
from _check import check
from _com import _early_bound
from _drawing_common import (
    DrawingOutputs,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    stamp_drawing_summary,
)
from _drawing_dimensions import set_dimension_callouts
from _drawing_hidden_sketches import curate_view_dimensions
from _drawing_notes import add_property_linked_note, property_link
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_view_display import set_hidden_lines_removed, set_hidden_lines_visible
from _session import run_build
from _stock_trim_drawing import (
    TrimSheet,
    end_detail,
    position_detail_label,
    position_parent_detail_letter,
    verify_machining_controls,
)
from vn_knife_hanger_stud_spec import (
    CHAMFER_ANGLE,
    CHAMFER_ANGLE_TOLERANCE,
    CHAMFER_WIDTH,
    CHAMFER_WIDTH_TOLERANCE,
    DIMENSION_CALLOUTS,
    DIMENSION_PRECISION,
    DIMENSION_TOLERANCE_TYPES,
    DRAWING_DIMENSIONS,
    LENGTH,
    LENGTH_BAND,
    THREAD_LENGTH_MIN,
    TIP_Y,
)

SPEC = DRAWINGS_BY_NAME["vn_knife_hanger_stud"]
SOURCE = SPEC.source
OUTPUTS = DrawingOutputs(**SPEC.outputs)
SHEET_SCALE = (2.0, 1.0)
ISO_SCALE = (2.0, 1.0)
FRONT_CENTER = (0.095, 0.170)
ISO_CENTER = (0.340, 0.125)
FRONT_KEEP = {
    "CutLength": (0.030, 0.170),
    "ThreadLengthMin": (0.150, 0.135),
}
DETAIL_KEEP = {"ChamferWidth": (0.225, 0.080), "ChamferAngle": (0.310, 0.090)}
SHEET = TrimSheet(
    sheet_scale=SHEET_SCALE,
    detail_center=(0.260, 0.100),
    detail_scale=(10.0, 1.0),
    fence_radius_mm=2.8,
    cut_end_y_mm=TIP_Y,
    detail_offset_mm=0.5,
    detail_label_xy=(0.310, 0.073),
    parent_letter_offset=(0.013, -0.010),
)
EXPECTED_CONTROLS = {
    "CutLength": (LENGTH / 1000, LENGTH_BAND[1] / 1000, LENGTH_BAND[0] / 1000),
    "ChamferWidth": (
        CHAMFER_WIDTH / 1000,
        -CHAMFER_WIDTH_TOLERANCE / 1000,
        CHAMFER_WIDTH_TOLERANCE / 1000,
    ),
    "ChamferAngle": (
        math.radians(CHAMFER_ANGLE),
        -math.radians(CHAMFER_ANGLE_TOLERANCE),
        math.radians(CHAMFER_ANGLE_TOLERANCE),
    ),
    "ThreadLengthMin": (THREAD_LENGTH_MIN / 1000, 0.0, 0.0),
}


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")
    check("open modified knife-hanger bolt", await adapter.open_model(str(SOURCE)))
    required = (
        "Number",
        "Material Specification",
        "Finish",
        "Quantity",
        "Stock Name",
        "Supplier",
        "Supplier SKUs",
        "Isometric View Note",
        "Machining Route",
        "Modified-Part Inspection",
    )
    properties = read_required_properties(
        adapter.currentModel, required, required=required
    )
    draw, _sheet = new_project_drawing(
        adapter, property_view=SPEC.artifact_stem, scale=SHEET_SCALE, layout=SPEC.layout
    )
    stamp_drawing_summary(
        adapter,
        draw,
        {
            0: "Knife-Hanger Bolt — Modified Stock Drawing",
            1: "Cut length, restored end preparation and modified-part inspection",
            2: "Harmonic Analyzer Project",
            3: "MHA-VN-024; McMaster-Carr 92314A253",
            4: "Native cut length, chamfer and thread-tail controls",
        },
    )
    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=SHEET_SCALE)
    place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=ISO_SCALE)
    set_hidden_lines_removed(adapter, front)
    detail = end_detail(adapter, front, SHEET)
    set_hidden_lines_visible(adapter, detail)
    _early_bound(detail, "IView").UpdateViewDisplayGeometry()
    # The consumed deburr sketch imports into the real end detail; the hidden
    # thread-tail acceptance sketch is shown only in its orthographic view.
    annotations = []
    for view, keep, label in (
        (detail, DETAIL_KEEP, "cut end"),
        (front, FRONT_KEEP, "under-head length and inspected thread tail"),
    ):
        annotations.extend(
            curate_view_dimensions(
                adapter,
                view,
                keep=keep,
                view_label=label,
                dimensions_by_feature=DRAWING_DIMENSIONS,
            )
        )
    verify_machining_controls(
        adapter,
        annotations,
        expected=EXPECTED_CONTROLS,
        tolerance_types=DIMENSION_TOLERANCE_TYPES,
        precision=DIMENSION_PRECISION,
    )
    set_dimension_callouts(adapter, annotations, DIMENSION_CALLOUTS)
    for annotation in annotations:
        name = dimension_name(adapter, annotation)
        display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
        if str(display.GetText(4) or "").replace("\r", "") != DIMENSION_CALLOUTS.get(
            name, ""
        ):
            raise RuntimeError(
                f"{name}: modified-part acceptance callout did not persist"
            )
    add_property_linked_note(adapter, "Supplier", 0.016, 0.061, char_height=0.003)
    add_property_linked_note(adapter, "Supplier SKUs", 0.082, 0.061, char_height=0.003)
    add_property_linked_note(adapter, "Stock Name", 0.016, 0.049, char_height=0.003)
    for property_name, y in (
        ("Machining Route", 0.118),
        ("Modified-Part Inspection", 0.098),
    ):
        note = _early_bound(
            add_property_linked_note(
                adapter, property_name, 0.016, y, char_height=0.003
            ),
            "INote",
        )
        printed = str(note.GetText() or "").replace("\r", "")
        if str(note.PropertyLinkedText or "") != property_link(
            property_name
        ) or printed != properties[property_name].replace("\r", ""):
            raise RuntimeError(
                f"{property_name}: linked manufacturing note did not persist"
            )
    add_property_linked_note(adapter, "Isometric View Note", 0.315, 0.068)
    position_detail_label(adapter, detail, SHEET)
    position_parent_detail_letter(adapter, front, SHEET)
    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Knife-Hanger Bolt — Modified Stock Drawing",
        scale=SHEET_SCALE,
        layout=SPEC.layout,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[SPEC.artifact_stem])
    parser.parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
