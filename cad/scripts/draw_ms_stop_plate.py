r"""Manufacturing drawing of the separate brass stop cover.

The cover face locates both clearance holes from one finished end and the
head-side edge. The aligned end view gives thickness; the native clearance
callout gives the decimal drill size, never merely a screw designation.
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

SPEC = DRAWINGS_BY_NAME["ms_stop_plate"]
PART_STEM = SPEC.artifact_stem
SOURCE = CAD_ROOT / "out" / "sldprt" / f"{PART_STEM}.SLDPRT"
OUTPUTS = DrawingOutputs(slddrw=SPEC.outputs["slddrw"], pdf=SPEC.outputs["pdf"], png=SPEC.outputs["png"])
SLDDRW, PDF, PNG = OUTPUTS.slddrw, OUTPUTS.pdf, OUTPUTS.png
SHEET_SCALE = (4.0, 1.0)
FRONT_CENTER = (0.175, 0.170)
RIGHT_CENTER = (0.310, FRONT_CENTER[1])
ISO_CENTER = (0.345, 0.090)
FRONT_KEEP = {
    "PlateLength": (0.175, 0.235), "PlateHeight": (0.105, 0.170),
    "RoofChamferSize": (0.110, 0.245), "RoofChamferAngle": (0.230, 0.245),
    "PlateLeftFromEnd": (0.175, 0.115),
    "PlateRightFromEnd": (0.175, 0.095),
    "PlateFromHeadFace": (0.245, 0.150),
}
RIGHT_KEEP = {"PlateThickness": (0.310, 0.225)}
DIMENSION_CALLOUTS = {"RoofChamferSize": "BOTH ROOF ENDS", "RoofChamferAngle": "BOTH ROOF ENDS"}


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source stop cover missing: {SOURCE}")
    check("open stop cover", await adapter.open_model(str(SOURCE)))
    properties = ("Number", "Revision", "Title", "Material Specification", "Finish", "Quantity")
    read_required_properties(adapter.currentModel, properties,
                             required=("Number", "Material Specification", "Finish", "Quantity"))
    drawing, _sheet = new_project_drawing(adapter, property_view=PART_STEM,
                                        scale=SHEET_SCALE, layout=SPEC.layout)
    stamp_drawing_summary(adapter, drawing, {
        0: "Measuring Stick Stop Plate Manufacturing Drawing",
        1: "Harmonic Analyzer hobby-machinist book drawing",
        2: "Harmonic Analyzer Project", 3: "brass stop plate; separate cover; clearance holes",
        4: "Generated from the project-owned ASME B drawing standard",
    })
    front = place_view(adapter, str(SOURCE), "*Back", *FRONT_CENTER, scale=SHEET_SCALE)
    right = place_view(adapter, str(SOURCE), "*Left", *RIGHT_CENTER, scale=SHEET_SCALE)
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=(2.0, 1.0))
    annotations = []
    for view, keep, label in ((front, FRONT_KEEP, "cover face"), (right, RIGHT_KEEP, "cover edge")):
        set_hidden_lines_removed(adapter, view)
        annotations += curate_view_dimensions(adapter, view, keep=keep, view_label=label,
                                               dimensions_by_feature=part.PLATE_DRAWING_DIMENSIONS)
    set_hidden_lines_removed(adapter, iso)
    set_dimension_callouts(adapter, annotations, DIMENSION_CALLOUTS)
    edge = model_point_in_view(
        adapter, front, (part.PLATE_HOLE_XS[0] + part.PLATE_CLEARANCE_DIA / 2.0,
                         part.PLATE_HOLE_Y, part.PLATE_Z_MIN), label="plate clearance mouth")
    add_native_hole_callout(adapter, front, edge_xy=edge, callout_xy=(0.030, 0.055),
                           label="two cover clearance holes", process="2X MATCH-DRILL; THEN OPEN")
    if not auto_center_marks(adapter, front, holes=True, size=0.0025):
        raise RuntimeError("stop clearance centre marks failed")
    assert_manufacturing_dimensions(
        adapter, annotations, part.PLATE_DRAWING_VALUES_BY_NAME,
        part.PLATE_DRAWING_PRECISION_BY_NAME,
        bands={
            "PlateThickness": (-part.PLATE_THICKNESS_TOLERANCE_MM, part.PLATE_THICKNESS_TOLERANCE_MM),
            **{name: (-part.PLATE_HOLE_POSITION_TOLERANCE_MM, part.PLATE_HOLE_POSITION_TOLERANCE_MM)
               for name in part.PLATE_LOCATION_DIMENSIONS},
        },
        angular=frozenset({"RoofChamferAngle"}),
    )
    for view in (front, right):
        set_hidden_lines_removed(adapter, view)
    add_property_linked_note(adapter, "Isometric View Note", 0.295, 0.055)
    add_property_linked_note(adapter, "Manufacturing Notes", 0.025, 0.023)
    return await finalize_drawing(adapter, OUTPUTS,
                                  pdf_title="Measuring Stick Stop Plate Manufacturing Drawing",
                                  scale=SHEET_SCALE, layout=SPEC.layout)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[PART_STEM])
    parser.parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
