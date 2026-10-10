r"""Manufacturing drawing of the separate brass stop cover.

The cover face locates both clearance holes from one finished end and the
head-side edge. The aligned end view gives thickness; the native clearance
callout gives the decimal drill size, never merely a screw designation.
The shared millimetre hole-mouth coordinates convert to COM metres before
projection into the cover-side *Back view.
Native callout positions centre their text; the full drill instruction and
the linked process notes stay inside the print border, clear of the title.
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

import _config
import _telemetry
import ms_stop_spec as part
from _common import CAD_ROOT, _early_bound, check, run_build
from _drawing_common import (
    DrawingOutputs, add_native_hole_callout, add_property_linked_note,
    dimension_name, finalize_drawing, model_point_in_view,
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
    "RoofChamferSize": (0.257, 0.229), "RoofChamferAngle": (0.236, 0.211),
    "PlateLeftFromEnd": (0.175, 0.115),
    "PlateRightFromEnd": (0.175, 0.095),
    "PlateFromHeadFace": (0.115, 0.148),
    "PilotDrillDiameter": (0.066, 0.245),
}
RIGHT_KEEP = {"PlateThickness": (0.310, 0.225)}
DIMENSION_CALLOUTS = {
    # Moving the native size to the right removes the full-width witness
    # line that looked like a long-edge bevel. Both native values stay live.
    "RoofChamferSize": "2 CORNERS",
    "PilotDrillDiameter": (
        "PILOT; MATCH-DRILL WITH\n"
        f"MS-STOP-BLOCK ({_config.parts('ms-stop-block')['number']})\n"
        "CLAMPED IN PLACE"
    ),
}


def _style_pilot_diameter(adapter: Any, annotations: list[Any]) -> None:
    """Keep the model diameter's leader on the concentric, earlier pilot step."""
    annotation = next(
        item for item in annotations
        if dimension_name(adapter, item) == "PilotDrillDiameter"
    )
    annotation = _early_bound(annotation, "IAnnotation")
    native = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
    if int(native.Type2) != 6:  # swDiameterDimension
        raise RuntimeError("match-drill pilot is not a native model diameter")
    # The importer shows this construction circle inside the opened clearance.
    # Its native diameter leader identifies the earlier PILOT step; THEN OPEN
    # below remains associated with the actual finished clearance edge.
    definition = str(native.GetText(5) or "")
    prefix = f"2X {definition}"
    native.SetText(1, prefix)
    if str(native.GetText(5) or "") != prefix:
        raise RuntimeError("native pilot quantity prefix did not persist")


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
    _style_pilot_diameter(adapter, annotations)
    edge = model_point_in_view(
        adapter, front, (
            (part.PLATE_HOLE_XS[1] + part.PLATE_CLEARANCE_DIA / 2.0) / 1000.0,
            part.PLATE_HOLE_Y / 1000.0, part.PLATE_Z_MIN / 1000.0,
        ), label="plate clearance mouth")
    # Left-sheet hole and upper-left text keep the leader clear of its mate,
    # the hole baselines, and the vertical overall-height dimension text.
    add_native_hole_callout(adapter, front, edge_xy=edge, callout_xy=(0.070, 0.215),
                           label="two cover clearance holes", process="THEN OPEN")
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
    add_property_linked_note(adapter, "Isometric View Note", ISO_CENTER[0] - 0.030, 0.124)
    add_property_linked_note(adapter, "Manufacturing Notes", 0.024, 0.036)
    return await finalize_drawing(adapter, OUTPUTS,
                                  pdf_title="Measuring Stick Stop Plate Manufacturing Drawing",
                                  scale=SHEET_SCALE, layout=SPEC.layout)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[PART_STEM])
    parser.parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
