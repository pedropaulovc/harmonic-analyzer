r"""Create the curated machinist drawing for the pinion engage lever.

A turned hub slipped over the MHA-060 lift rod's front end, with a tapered grip
rod rising out of it; the MHA-135 pin (U36) match-drilled through hub and rod at
assembly carries the drive.  The 1:1 front view carries the hub and grip sizes,
the projected top view the crown, and a 3:1 detail of the side view the hub's
axial stations -- bore depth, end wall, grip axis and pin hole, all baselined
from the flat mouth face B.

Run with SolidWorks open::

    uv run python cad\scripts\draw_pinion_lever.py pinion-lever
"""

from __future__ import annotations

import argparse
import math
import sys
from typing import Any

import _telemetry
from _common import CAD_ROOT, _early_bound, _read_member, check, run_build
from _drawing_common import (
    DrawingOutputs,
    add_property_linked_note,
    assert_imported_precision,
    curate_view_dimensions,
    finalize_drawing,
    model_point_in_view,
    new_project_drawing,
    read_required_properties,
    set_dimension_callouts,
    set_hidden_lines_removed,
    stamp_drawing_summary,
    view_name,
)
from _drawing_registry import DRAWINGS_BY_NAME
from pinion_lever_spec import (
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    HUB_OD,
    LIFT_ROD_NUMBER,
    PIN_HOLE_CALLOUT,
    ROD_LEN,
)
from solidworks_mcp.adapters.com_variant import double_array
from solidworks_mcp.adapters.solidworks.drawing import (
    auto_center_marks,
    place_view,
)


SPEC = DRAWINGS_BY_NAME["pinion_lever"]
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
_S = SHEET_SCALE[0] / 1000.0

# Third-angle orthographic views stay aligned around the front view: the side
# view shares its Y station, the top view its X station.  The front view's box
# spans the hub's bottom (-HUB_OD/2) to the grip tip (ROD_LEN).
FRONT_BBOX_CY = (ROD_LEN - HUB_OD / 2.0) / 2.0
FRONT_CENTER = (0.070, 0.160)
SIDE_CENTER = (0.135, FRONT_CENTER[1])
TOP_CENTER = (FRONT_CENTER[0], 0.240)
ISO_CENTER = (0.355, 0.175)
DETAIL_CENTER = (0.245, 0.170)
DETAIL_SCALE = (3, 1)
DETAIL_RADIUS_MM = 9.0
# r7 eye-pass: at (0.228, 0.128) the label sat on the 8.0 FLAT BOTTOM text.
DETAIL_LABEL_XY = (0.300, 0.128)
_DS = DETAIL_SCALE[0] / 1000.0


def _front_y(model_y_mm: float) -> float:
    return FRONT_CENTER[1] + (model_y_mm - FRONT_BBOX_CY) * _S


ROD_ROOT_TEXT_Y = 20.0  # model height of the root-diameter text, clear of the hub


FRONT_KEEP = {
    "HubOd": (0.030, _front_y(-HUB_OD / 2.0) - 0.010),
    "HubBore": (0.105, _front_y(-HUB_OD / 2.0) - 0.014),
    "RodTipY": (0.035, FRONT_CENTER[1] + 0.010),
    "RodTipDia": (0.100, _front_y(ROD_LEN) + 0.012),
    "RodRootDia": (0.105, _front_y(ROD_ROOT_TEXT_Y)),
}
TOP_KEEP = {"CapR": (0.105, TOP_CENTER[1] + 0.012)}
# In the side view B (the mouth face, model z +5) is the LEFT end and the
# crown the right; the detail keeps that orientation at 3:1.
# r7 eye-pass: the GRIP AXIS and TO CROWN ROOT texts ran into each other, and
# the pin-hole callout sat across the hub outline.  The two top stations now
# spread apart, and the callout goes above them with its leader dropping
# between.
DETAIL_KEEP = {
    "GripFromB": (DETAIL_CENTER[0] - 0.020, DETAIL_CENTER[1] + 0.032),
    "EndWall": (DETAIL_CENTER[0] + 0.045, DETAIL_CENTER[1] + 0.032),
    "PinHoleFromB": (DETAIL_CENTER[0] - 3.0 * _DS, DETAIL_CENTER[1] - 0.031),
    "BoreDepth": (DETAIL_CENTER[0] - 1.0 * _DS, DETAIL_CENTER[1] - 0.041),
    "PinHoleDia": (DETAIL_CENTER[0] + 0.055, DETAIL_CENTER[1] + 0.075),
}
DIMENSION_CALLOUTS = {
    "HubBore": f"BORE OR REAM\nSLIP ON {LIFT_ROD_NUMBER}",
    "BoreDepth": "FLAT BOTTOM",
    "EndWall": "TO CROWN ROOT",
    "RodTipY": "FROM HUB AXIS",
    "RodTipDia": "AT TIP",
    "RodRootDia": "AT ROOT",
    "GripFromB": "GRIP AXIS",
    "PinHoleDia": PIN_HOLE_CALLOUT,
}


def _hub_detail(adapter: Any, side: Any) -> Any:
    """A native 3:1 detail of the hub in the side view."""
    draw = adapter.currentModel
    drawing = _early_bound(draw, "IDrawingDoc")
    parent = _early_bound(side, "IView")
    if not drawing.ActivateView(view_name(adapter, side)):
        raise RuntimeError("failed to activate hub-detail parent")
    draw.ClearSelection2(True)
    center = model_point_in_view(adapter, side, (0.0, 0.0, 0.0), label="hub centre")
    radius = DETAIL_RADIUS_MM * _S
    sketch = _early_bound(parent.GetSketch(), "ISketch")
    transform = _early_bound(sketch.ModelToSketchTransform, "IMathTransform")
    utility = _early_bound(adapter.swApp.GetMathUtility(), "IMathUtility")
    points = []
    for x, y in (center, (center[0] + radius, center[1])):
        point = _early_bound(utility.CreatePoint(double_array([x, y, 0.0])), "IMathPoint")
        projected = _early_bound(point.MultiplyTransform(transform), "IMathPoint")
        points.append(tuple(float(value) for value in projected.ArrayData))
    manager = _early_bound(draw.SketchManager, "ISketchManager")
    if manager.CreateCircle(*points[0], *points[1]) is None:
        raise RuntimeError("failed to create hub-detail fence")
    detail = drawing.CreateDetailViewAt4(
        *DETAIL_CENTER,
        0.0,
        0,  # swDetViewSTANDARD
        *DETAIL_SCALE,
        "A",
        1,  # swDetCircleCIRCLE
        True,
        False,
        False,
        5,
    )
    if detail is None:
        raise RuntimeError("failed to create hub detail")
    detail = _early_bound(detail, "IView")
    detail.ScaleRatio = double_array([float(value) for value in DETAIL_SCALE])
    draw.ClearSelection2(True)
    draw.EditRebuild3()
    outline = tuple(float(value) for value in detail.GetOutline())
    position = tuple(float(value) for value in detail.Position)
    if len(outline) != 4 or len(position) != 2:
        raise RuntimeError("hub detail has invalid bounds")
    target = [
        position[axis] + DETAIL_CENTER[axis] - (outline[axis] + outline[axis + 2]) / 2.0
        for axis in range(2)
    ]
    if not detail.SetViewPosition(double_array(target), False):
        raise RuntimeError("failed to position hub detail")
    draw.EditRebuild3()
    notes = tuple(_read_member(detail, "GetNotes") or ())
    if len(notes) != 1:
        raise RuntimeError(f"expected one native detail label, found {len(notes)}")
    note = _early_bound(notes[0], "INote")
    annotation = _early_bound(_read_member(note, "GetAnnotation"), "IAnnotation")
    label_xyz = (*DETAIL_LABEL_XY, 0.0)
    if not annotation.SetPosition2(*label_xyz):
        raise RuntimeError("failed to position hub detail label")
    draw.EditRebuild3()
    actual = tuple(float(value) for value in _read_member(annotation, "GetPosition"))
    if math.dist(actual, label_xyz) > 1e-8:
        raise RuntimeError(f"hub detail label position did not persist: {actual}")
    return detail


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open pinion-lever source", await adapter.open_model(str(SOURCE)))
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
            0: "Pinion Engage Lever Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "pinion engage lever; pinned hub; tapered grip rod",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )
    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=(1, 1))
    side = place_view(adapter, str(SOURCE), "*Right", *SIDE_CENTER, scale=(1, 1))
    top = place_view(adapter, str(SOURCE), "*Top", *TOP_CENTER, scale=(1, 1))
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=(1, 1))
    # Rule 7: the pin hole shows true in the side view and its detail, and the
    # blind bore's depth and wall are dimensioned there to its visible end
    # faces -- no feature needs a hidden line.
    for view in (front, side, top, iso):
        set_hidden_lines_removed(adapter, view)

    front_annotations = curate_view_dimensions(
        adapter,
        front,
        keep=FRONT_KEEP,
        view_label="lever front",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    top_annotations = curate_view_dimensions(
        adapter,
        top,
        keep=TOP_KEEP,
        view_label="lever top",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    detail = _hub_detail(adapter, side)
    set_hidden_lines_removed(adapter, detail)
    detail_annotations = curate_view_dimensions(
        adapter,
        detail,
        keep=DETAIL_KEEP,
        view_label="hub detail",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    annotations = [*front_annotations, *top_annotations, *detail_annotations]
    set_dimension_callouts(adapter, annotations, DIMENSION_CALLOUTS)
    assert_imported_precision(adapter, annotations, DRAWING_PRECISION_BY_NAME)
    if not auto_center_marks(adapter, front, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center marks to front view")
    if not auto_center_marks(adapter, detail, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center mark to the pin hole")

    add_property_linked_note(adapter, "Manufacturing Notes", 0.020, 0.075)
    add_property_linked_note(adapter, "Isometric View Note", 0.335, 0.105)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Pinion Engage Lever Manufacturing Drawing",
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
