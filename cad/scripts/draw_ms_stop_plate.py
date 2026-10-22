r"""Manufacturing drawing of the separate brass stop cover.

The cover face locates both clearance holes from one finished end and the
head-side edge. The aligned end view gives thickness; the native clearance
callout gives the decimal drill size, never merely a screw designation.
The shared millimetre hole-mouth coordinates convert to COM metres before
projection into the cover-side *Back view.
The model-owned pilot and finished drill callouts identify the matched block,
the physical registration edges and the web function of the absolute locations.
Their text is shelved to the right of the measured extension lines; the cover
thickness retains the screw-engagement stack and moves left of its witnesses.
The overall-height line stands clear of the hole-height text, and the finished
clearance callout explicitly separates the pair before drilling this plate.
Separate native chamfer size and angle retain their model-owned precision.
"""

from __future__ import annotations

import argparse
import math
import sys
from typing import Any

import _config
import _telemetry
import ms_stop_spec as part
from _check import check
from _com import _early_bound
from _paths import CAD_ROOT
from _session import run_build
from _drawing_common import (
    DrawingOutputs,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    rebuild_drawing,
    stamp_drawing_summary,
)
from _drawing_dimensions import offset_dimension_text, set_dimension_callouts
from _drawing_hole_callout import add_native_hole_callout
from _drawing_leaders import set_near_side_diameter
from _drawing_notes import add_property_linked_note
from _drawing_projection import model_point_in_view
from _drawing_view_display import set_hidden_lines_removed
from solidworks_mcp.adapters.solidworks.drawing import dimension_name
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
# Far enough right that the four-line pilot callout ends clear of this view.
RIGHT_CENTER = (0.345, FRONT_CENTER[1])
ISO_CENTER = (0.345, 0.090)
FRONT_KEEP = {
    "PlateLength": (0.175, 0.235), "PlateHeight": (0.090, 0.170),
    "RoofChamferSize": (0.247, 0.225), "RoofChamferAngle": (0.227, 0.205),
    "PlateLeftFromEnd": (0.175, 0.115),
    "PlateRightFromEnd": (0.175, 0.095),
    "PlateFromHeadFace": (0.115, 0.148),
    # The 81e native elbow was 54.8069 mm left and 13.9174 mm below
    # its text anchor. This lane clears the original chamfer dimensions
    # and raises that elbow above the 4.00 witness; native readback decides.
    "PilotDrillDiameter": (0.274, 0.176),
}
RIGHT_KEEP = {"PlateThickness": (RIGHT_CENTER[0], 0.225)}
THICKNESS_TEXT_OFFSET = {"PlateThickness": (0.285, 0.245)}
DIMENSION_CALLOUTS = {
    "PilotDrillDiameter": (
        f"MATCH-DRILL INTO MS-STOP-BLOCK {_config.parts('ms-stop-block')['number']}\n"
        + part.MATCH_DRILL_DATUM_ALIGNMENT.replace(" FLUSH IN ", " FLUSH\nIN ")
        + "; KEEPS BLOCK WEBS\n"
        "KEEP PAIR TOGETHER; NOT INTERCHANGEABLE"
    ),
    # The 0.9..1.1 thickness bounds the stock screw's penetration in the
    # block's blind full-thread depth; it is not an arbitrary sheet tolerance.
    "PlateThickness": (
        f"SCREW STACK: {_config.parts('ms-vn-stop-plate-screw')['number']}\n"
        f"IN MS-STOP-BLOCK {_config.parts('ms-stop-block')['number']}"
    ),
}


def _style_pilot_diameter(adapter: Any, view: Any, annotations: list[Any]) -> None:
    """Keep a live native pilot dimension with one angled arrow on its own rim."""
    annotation = next(
        item for item in annotations
        if dimension_name(adapter, item) == "PilotDrillDiameter"
    )
    annotation = _early_bound(annotation, "IAnnotation")
    native = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
    if int(native.Type2) != 6:  # swDiameterDimension
        raise RuntimeError("match-drill pilot is not a native model diameter")
    dimension = _early_bound(native.GetDimension2(0), "IDimension")
    original_name = str(dimension.FullName)
    original_value = float(dimension.SystemValue)
    if (
        original_name.split("@")[:2] != ["PilotDrillDiameter", "PilotDrillReference"]
        or not math.isclose(original_value * 1000.0, part.PLATE_TAP_DRILL_DIA, abs_tol=1e-8)
    ):
        raise RuntimeError(f"pilot dimension has wrong model owner/value: {original_name}, {original_value}")
    # The importer shows this construction circle inside the opened clearance.
    # Both steps identify this same hole pair; their separate native dimensions
    # retain the pilot model value and the finished Hole Wizard value.
    definition = str(native.GetText(5) or "")
    prefix = f"2X {definition}"
    native.SetText(1, prefix)
    if str(native.GetText(5) or "") != prefix:
        raise RuntimeError("native pilot quantity prefix did not persist")
    # Native display styling, not IAnnotation's unsupported endpoint setters.
    # Keep the imported model dimension and let SolidWorks solve its own leader.
    set_near_side_diameter(annotation, "stop-plate match-drill pilot")
    x, y = FRONT_KEEP["PilotDrillDiameter"]
    if not annotation.SetPosition2(x, y, 0.0):
        raise RuntimeError("failed to position the native pilot shelf")
    rebuild_drawing(adapter, label="stop-plate pilot leader")
    position = tuple(float(value) for value in annotation.GetPosition())
    current = _early_bound(native.GetDimension2(0), "IDimension")
    if (
        len(position) != 3
        or math.dist(position, (x, y, 0.0)) > 1e-5
        or int(adapter.swApp.IsSame(dimension, current)) != 1
        or str(current.FullName) != original_name
        or not math.isclose(float(current.SystemValue), original_value, abs_tol=1e-12)
        or not bool(native.ShowDimensionValue)
        or bool(annotation.IsDangling())
    ):
        raise RuntimeError(f"pilot dimension identity/value/position did not persist: {original_name}, {position}")
    center = model_point_in_view(
        adapter, view, (part.PLATE_HOLE_XS[0] / 1000.0, part.PLATE_HOLE_Y / 1000.0, 0.0),
        label="pilot construction-circle center",
    )
    scale = SHEET_SCALE[0] / SHEET_SCALE[1] / 2000.0
    pilot_radius = part.PLATE_TAP_DRILL_DIA * scale
    finished_radius = part.PLATE_CLEARANCE_DIA * scale
    # A quarter of the native rims' separation discriminates the two carriers;
    # this is paper-ink checking, not a new hole-size or position tolerance.
    radius_air = abs(finished_radius - pilot_radius) / 4.0
    data = _early_bound(native.GetDisplayData(), "IDisplayData")
    arrows = [
        tuple(float(value) for value in data.GetArrowHeadAtIndex2(index))
        for index in range(int(data.GetArrowHeadCount()))
    ]
    if len(arrows) != 1 or len(arrows[0]) < 6 or not all(map(math.isfinite, arrows[0])):
        raise RuntimeError(f"pilot leader has no single readable arrow: {arrows!r}")
    arrow = arrows[0]
    radius = math.dist(arrow[:2], center)
    direction_length = math.hypot(arrow[3], arrow[4])
    if (
        abs(radius - pilot_radius) > radius_air
        or direction_length == 0.0
        or abs(arrow[4]) / direction_length < 0.2
    ):
        raise RuntimeError(
            "pilot arrow misses its sketch circle or overlays the hole-height witness: "
            f"center={center!r}, pilot_radius={pilot_radius}, "
            f"finished_radius={finished_radius}, arrows={arrows!r}"
        )


def _style_plate_chamfer(adapter: Any, annotations: list[Any]) -> None:
    """Keep two separate native dimensions, never a pseudo combined callout."""
    remaining = {"RoofChamferSize": "2X ", "RoofChamferAngle": ""}
    for annotation in annotations:
        prefix = remaining.pop(dimension_name(adapter, annotation), None)
        if prefix is None:
            continue
        native = _early_bound(
            _early_bound(annotation, "IAnnotation").GetSpecificAnnotation(),
            "IDisplayDimension",
        )
        # Prefix only: SetText(All) would suppress the model-owned value.
        definition = str(native.GetText(5) or "")
        revised = prefix + definition
        native.SetText(1, revised)
        if str(native.GetText(5) or "") != revised:
            raise RuntimeError("native plate chamfer prefix did not persist")
    if remaining:
        raise RuntimeError(f"missing native plate chamfer dimensions: {sorted(remaining)}")


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
    offset_dimension_text(adapter, annotations, THICKNESS_TEXT_OFFSET)
    _style_pilot_diameter(adapter, front, annotations)
    _style_plate_chamfer(adapter, annotations)
    edge = model_point_in_view(
        adapter, front, (
            (part.PLATE_HOLE_XS[0] - part.PLATE_CLEARANCE_DIA / 2.0) / 1000.0,
            part.PLATE_HOLE_Y / 1000.0, part.PLATE_Z_MIN / 1000.0,
        ), label="plate clearance mouth")
    # *Back reverses X: this is the right-sheet hole, concentric with the
    # imported pilot. Two adjacent native callouts avoid an unverified note
    # dimension-link format while keeping both 2X quantities and sizes live.
    # Both leaders stay right of the overall-height and hole-location lanes.
    add_native_hole_callout(
        adapter, front, edge_xy=edge, callout_xy=(0.285, 0.132),
        label="two cover clearance holes", process="SEPARATE PAIR;\nDRILL PLATE ONLY",
    )
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
    return await finalize_drawing(adapter, OUTPUTS,
                                  pdf_title="Measuring Stick Stop Plate Manufacturing Drawing",
                                  scale=SHEET_SCALE, layout=SPEC.layout)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[PART_STEM])
    parser.parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
