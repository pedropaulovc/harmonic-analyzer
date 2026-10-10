r"""Manufacturing drawing of the open-rebate brass stop block.

The cover-side view and end view show the rebate in solid lines. Standard
native Hole Wizard callouts define the orthogonal taps, including blind full
thread and drill depths. Every controlling dimension is imported unchanged.
Hole-mouth points convert the shared millimetre frame to COM metres before
projection; the cover-side *Back view reverses X, not the coordinate units.
Native callout positions centre their text; reserve the full two-line tap
instruction inside the print border and keep the thumb callout off the title.
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

import _telemetry
import ms_stop_spec as part
from _common import CAD_ROOT, check, run_build
from _drawing_common import (
    DrawingOutputs, add_native_hole_callout, add_property_linked_note,
    finalize_drawing, model_point_in_view,
    new_project_drawing, read_required_properties, set_dimension_callouts,
    set_hidden_lines_removed, stamp_drawing_summary,
)
from _drawing_hidden_sketches import curate_view_dimensions
from _drawing_registry import DRAWINGS_BY_NAME
from _ms_drawing_contract import assert_manufacturing_dimensions
from solidworks_mcp.adapters.solidworks.drawing import auto_center_marks, place_view

SPEC = DRAWINGS_BY_NAME["ms_stop_block"]
PART_STEM = SPEC.artifact_stem
SOURCE = CAD_ROOT / "out" / "sldprt" / f"{PART_STEM}.SLDPRT"
OUTPUTS = DrawingOutputs(slddrw=SPEC.outputs["slddrw"], pdf=SPEC.outputs["pdf"], png=SPEC.outputs["png"])
SLDDRW, PDF, PNG = OUTPUTS.slddrw, OUTPUTS.pdf, OUTPUTS.png
SHEET_SCALE = (4.0, 1.0)
FRONT_CENTER = (0.175, 0.185)
RIGHT_CENTER = (0.315, FRONT_CENTER[1])
BOTTOM_CENTER = (FRONT_CENTER[0], 0.080)
ISO_CENTER = (0.350, 0.085)
FRONT_KEEP = {
    "BlockLength": (0.175, 0.235), "BlockHeight": (0.105, 0.185),
    "RoofChamferSize": (0.112, 0.245), "RoofChamferAngle": (0.230, 0.245),
    "PlateLeftFromEnd": (0.175, 0.140),
    "PlateRightFromEnd": (0.175, 0.122),
    "PlateFromHeadFace": (0.240, 0.150),
}
RIGHT_KEEP = {
    "BlockDepth": (0.315, 0.235), "WindowWidth": (0.315, 0.130),
    "WindowHeight": (0.365, 0.198), "RoofThickness": (0.275, 0.215),
}
BOTTOM_KEEP = {
    "ThumbFromEnd": (0.175, 0.038), "ThumbFromPlate": (0.110, 0.080),
}
DIMENSION_CALLOUTS = {"RoofChamferSize": "BOTH ROOF ENDS", "RoofChamferAngle": "BOTH ROOF ENDS"}


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source stop block missing: {SOURCE}")
    check("open stop block", await adapter.open_model(str(SOURCE)))
    properties = ("Number", "Revision", "Title", "Material Specification", "Finish", "Quantity")
    read_required_properties(adapter.currentModel, properties,
                             required=("Number", "Material Specification", "Finish", "Quantity"))
    drawing, _sheet = new_project_drawing(adapter, property_view=PART_STEM,
                                        scale=SHEET_SCALE, layout=SPEC.layout)
    stamp_drawing_summary(adapter, drawing, {
        0: "Measuring Stick Stop Block Manufacturing Drawing",
        1: "Harmonic Analyzer hobby-machinist book drawing",
        2: "Harmonic Analyzer Project", 3: "brass stop block; open rebate; native taps",
        4: "Generated from the project-owned ASME B drawing standard",
    })
    front = place_view(adapter, str(SOURCE), "*Back", *FRONT_CENTER, scale=SHEET_SCALE)
    right = place_view(adapter, str(SOURCE), "*Left", *RIGHT_CENTER, scale=SHEET_SCALE)
    bottom = place_view(adapter, str(SOURCE), "*Bottom", *BOTTOM_CENTER, scale=SHEET_SCALE)
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=(2.0, 1.0))
    annotations = []
    for view, keep, label in ((front, FRONT_KEEP, "cover face"),
                              (right, RIGHT_KEEP, "open rebate end"),
                              (bottom, BOTTOM_KEEP, "thumbscrew face")):
        set_hidden_lines_removed(adapter, view)
        annotations += curate_view_dimensions(adapter, view, keep=keep, view_label=label,
                                               dimensions_by_feature=part.BLOCK_DRAWING_DIMENSIONS)
    set_hidden_lines_removed(adapter, iso)
    set_dimension_callouts(adapter, annotations, DIMENSION_CALLOUTS)
    plate_edge = model_point_in_view(
        adapter, front, (
            (part.PLATE_HOLE_XS[0] + part.PLATE_TAP_DRILL_DIA / 2.0) / 1000.0,
            part.PLATE_HOLE_Y / 1000.0, part.PLATE_Z_MAX / 1000.0,
        ), label="plate tap mouth")
    add_native_hole_callout(adapter, front, edge_xy=plate_edge, callout_xy=(0.125, 0.118),
                           label="two cover blind taps", process="2X MATCH-DRILL; THEN BOTTOMING TAP")
    thumb_edge = model_point_in_view(
        adapter, bottom, (
            (part.THUMB_AXIS_X + part.THUMB_TAP_DRILL / 2.0) / 1000.0,
            0.0, part.THUMB_AXIS_Z / 1000.0,
        ), label="thumb tap mouth")
    add_native_hole_callout(adapter, bottom, edge_xy=thumb_edge, callout_xy=(0.070, 0.050),
                           label="thumbscrew tap through floor")
    for view in (front, bottom):
        if not auto_center_marks(adapter, view, holes=True, size=0.0025):
            raise RuntimeError("stop tap centre marks failed")
    assert_manufacturing_dimensions(
        adapter, annotations, part.BLOCK_DRAWING_VALUES_BY_NAME,
        part.BLOCK_DRAWING_PRECISION_BY_NAME,
        bands={
            **{name: part.WINDOW_SIZE_TOLERANCE_MM for name in ("WindowWidth", "WindowHeight")},
            **{name: (-part.PLATE_HOLE_POSITION_TOLERANCE_MM, part.PLATE_HOLE_POSITION_TOLERANCE_MM)
               for name in part.PLATE_LOCATION_DIMENSIONS},
        },
        angular=frozenset({"RoofChamferAngle"}),
    )
    for view in (front, right, bottom):
        set_hidden_lines_removed(adapter, view)
    add_property_linked_note(adapter, "Isometric View Note", ISO_CENTER[0] - 0.030, 0.124)
    add_property_linked_note(adapter, "Manufacturing Notes", 0.024, 0.036)
    return await finalize_drawing(adapter, OUTPUTS,
                                  pdf_title="Measuring Stick Stop Block Manufacturing Drawing",
                                  scale=SHEET_SCALE, layout=SPEC.layout)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[PART_STEM])
    parser.parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
