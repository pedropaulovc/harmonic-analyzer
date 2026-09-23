r"""Create the curated machinist drawing for the pinion lift rod.

A plain 6.35 bearing rod, crowned at its back end, with the MHA-135 pin hole
match-drilled at assembly near its flat front end (U36).  The 2:1 end view
carries the bearing diameter; the 1:1 side view carries the length, the crown
and the bearing finish; a 5:1 detail of the front end carries the pin hole and
its station from the front face.

Run with SolidWorks open::

    uv run python cad\scripts\draw_pinion_lift_rod.py pinion-lift-rod
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
    add_surface_finish,
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
from _surface_finish import surface_finish_by_key
from pinion_lever_geometry import ROD_PIN_HOLE_FROM_END
from pinion_lift_rod_spec import (
    CAP_SAG,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    PIN_HOLE_CALLOUT,
    ROD_DIA,
    ROD_LEN,
    SURFACE_FINISHES,
)
from solidworks_mcp.adapters.com_variant import double_array
from solidworks_mcp.adapters.solidworks.drawing import (
    auto_center_marks,
    place_view,
)


SPEC = DRAWINGS_BY_NAME["pinion_lift_rod"]
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
END_VIEW_SCALE = 2.0
# The crown adds CAP_SAG past the nominal length, so the side view's bounding
# box (and its centre) span ROD_LEN + CAP_SAG.
HALF_SPAN = (ROD_LEN + CAP_SAG) / 2000.0
FRONT_CENTER = (0.045, 0.205)
RIGHT_CENTER = (
    FRONT_CENTER[0] + HALF_SPAN * SHEET_SCALE[0] + 0.040,
    FRONT_CENTER[1],
)
ISO_CENTER = (0.135, 0.125)
DETAIL_CENTER = (0.335, 0.132)
DETAIL_SCALE = (5, 1)
DETAIL_RADIUS_MM = 7.0
DETAIL_LABEL_XY = (0.312, 0.170)

# The rod's flank in the *Right view: the bearing finish leader drops onto it.
ROD_FLANK_Y = RIGHT_CENTER[1] + ROD_DIA * SHEET_SCALE[0] / 2000.0

FRONT_KEEP = {
    "RodDia": (
        FRONT_CENTER[0] - ROD_DIA * END_VIEW_SCALE / 1000.0 - 0.006,
        FRONT_CENTER[1] + 0.022,
    ),
}
# In the *Right view the part's +Z (crowned back end) points screen-left, so
# the flat front end (z 0) is the RIGHT silhouette edge.
RIGHT_KEEP = {
    "Depth": (RIGHT_CENTER[0], RIGHT_CENTER[1] - 0.022),
    "CapR": (RIGHT_CENTER[0] - HALF_SPAN - 0.012, RIGHT_CENTER[1] + 0.024),
}
DETAIL_KEEP = {
    # r7 eye-pass: above the detail the callout ran over the DETAIL A label
    # and past the right border; the open field left of the detail fits it.
    "PinHoleDia": (DETAIL_CENTER[0] - 0.090, DETAIL_CENTER[1] + 0.028),
    "PinHoleZ": (DETAIL_CENTER[0] + 0.004, DETAIL_CENTER[1] - 0.034),
}
DIMENSION_CALLOUTS = {
    "PinHoleDia": PIN_HOLE_CALLOUT,
    "PinHoleZ": "FROM FRONT END",
}


def _front_end_detail(adapter: Any, side: Any) -> Any:
    """A native 5:1 detail of the rod's front end, where the pin hole sits."""
    draw = adapter.currentModel
    drawing = _early_bound(draw, "IDrawingDoc")
    parent = _early_bound(side, "IView")
    if not drawing.ActivateView(view_name(adapter, side)):
        raise RuntimeError("failed to activate front-end detail parent")
    draw.ClearSelection2(True)
    center = model_point_in_view(
        adapter,
        side,
        (0.0, 0.0, ROD_PIN_HOLE_FROM_END / 1000.0),
        label="front-end detail centre",
    )
    radius = DETAIL_RADIUS_MM * SHEET_SCALE[0] / 1000.0
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
        raise RuntimeError("failed to create front-end detail fence")
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
        raise RuntimeError("failed to create front-end detail")
    detail = _early_bound(detail, "IView")
    detail.ScaleRatio = double_array([float(value) for value in DETAIL_SCALE])
    draw.ClearSelection2(True)
    draw.EditRebuild3()
    outline = tuple(float(value) for value in detail.GetOutline())
    position = tuple(float(value) for value in detail.Position)
    if len(outline) != 4 or len(position) != 2:
        raise RuntimeError("front-end detail has invalid bounds")
    target = [
        position[axis] + DETAIL_CENTER[axis] - (outline[axis] + outline[axis + 2]) / 2.0
        for axis in range(2)
    ]
    if not detail.SetViewPosition(double_array(target), False):
        raise RuntimeError("failed to position front-end detail")
    draw.EditRebuild3()
    notes = tuple(_read_member(detail, "GetNotes") or ())
    if len(notes) != 1:
        raise RuntimeError(f"expected one native detail label, found {len(notes)}")
    note = _early_bound(notes[0], "INote")
    annotation = _early_bound(_read_member(note, "GetAnnotation"), "IAnnotation")
    label_xyz = (*DETAIL_LABEL_XY, 0.0)
    if not annotation.SetPosition2(*label_xyz):
        raise RuntimeError("failed to position front-end detail label")
    draw.EditRebuild3()
    actual = tuple(float(value) for value in _read_member(annotation, "GetPosition"))
    if math.dist(actual, label_xyz) > 1e-8:
        raise RuntimeError(f"front-end detail label did not persist: {actual}")
    return detail


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open pinion-lift-rod source", await adapter.open_model(str(SOURCE)))
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
            "End View Note",
        ),
        required=(
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
            "Manufacturing Notes",
            "End View Note",
        ),
    )
    drawing_model, _sheet = new_project_drawing(
        adapter, property_view=PART_STEM, scale=SHEET_SCALE, layout=SPEC.layout
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Pinion Lift Rod Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "pinion lift rod; eccentric cam rod; turned steel",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=(2, 1))
    right = place_view(adapter, str(SOURCE), "*Right", *RIGHT_CENTER, scale=(1, 1))
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=(1, 2))
    for view in (front, right, iso):
        set_hidden_lines_removed(adapter, view)

    front_annotations = curate_view_dimensions(
        adapter,
        front,
        keep=FRONT_KEEP,
        view_label="rod end",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    right_annotations = curate_view_dimensions(
        adapter,
        right,
        keep=RIGHT_KEEP,
        view_label="rod side",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    detail = _front_end_detail(adapter, right)
    set_hidden_lines_removed(adapter, detail)
    detail_annotations = curate_view_dimensions(
        adapter,
        detail,
        keep=DETAIL_KEEP,
        view_label="front-end detail",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    annotations = [*front_annotations, *right_annotations, *detail_annotations]
    set_dimension_callouts(adapter, annotations, DIMENSION_CALLOUTS)
    assert_imported_precision(adapter, annotations, DRAWING_PRECISION_BY_NAME)
    # SolidWorks classifies a solid circular end silhouette under the same
    # AutoInsertCenterMarks2 "hole" bit as a bored circle.
    if not auto_center_marks(adapter, front, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center mark to rod end view")
    if not auto_center_marks(adapter, detail, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center mark to the pin hole")

    # Rule 5: the flank turns in the pivot blocks' bores -- the one running
    # surface.  A cylinder carries no model edge along its side, so the pick
    # is a SILHOUETTE entity.
    add_surface_finish(
        adapter,
        right,
        edge_xy=(RIGHT_CENTER[0] - 0.045, ROD_FLANK_Y),
        symbol_xy=(RIGHT_CENTER[0] - 0.045, 0.228),
        control=surface_finish_by_key(SURFACE_FINISHES, "bearing"),
        label="lift rod bearing finish",
        entity_type="SILHOUETTE",
        char_height=0.0025,  # the pivot-block size; the default read oversized
    )

    add_property_linked_note(adapter, "Manufacturing Notes", 0.020, 0.075)
    add_property_linked_note(adapter, "End View Note", 0.020, 0.170)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Pinion Lift Rod Manufacturing Drawing",
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
