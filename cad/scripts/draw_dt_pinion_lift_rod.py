r"""Create the curated machinist drawing for the pinion lift rod.

A plain 1/4 in bearing rod, crowned at its back end, with the MHA-DT-30 pin hole
match-drilled at assembly near its flat front end (U36).  The 1:1 side view
carries everything the lathe needs -- the bearing diameter and its mate, the
body length, the crown and the (overall) -- plus the bearing finish; a 5:1
detail of the front end carries the pin hole and its station from the front
face.  No end view: the diameter lives on the side view (drawing-guidelines.md
rule 11 (turned parts read like the lathe); machinist review r1, #1013).

Run with SolidWorks open::

    uv run python cad\scripts\draw_dt_pinion_lift_rod.py dt-pinion-lift-rod
"""

from __future__ import annotations

import argparse
import math
import sys
from typing import Any

from solidworks_mcp.adapters.com_variant import double_array
from solidworks_mcp.adapters.solidworks.drawing import (
    auto_center_marks,
    dimension_name,
    place_view,
    view_name,
)

from _check import check
from _com import _early_bound, _read_member
from _drawing_common import (
    DrawingOutputs,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    stamp_drawing_summary,
)
from _drawing_dimension_import import curate_view_dimensions
from _drawing_dimensions import (
    assert_imported_precision,
    set_dimension_callouts,
    set_reference_dimension,
)
from _drawing_finish import add_surface_finish
from _drawing_notes import add_property_linked_note
from _drawing_projection import model_point_in_view
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_view_display import set_hidden_lines_removed
from _machinist_review_mode import MachinistReviewMode
from _part_properties import part_drawing_unit
from _paths import CAD_ROOT
from _session import run_build
from _surface_finish import surface_finish_by_key
import _telemetry
from dt_pinion_lever_geometry import ROD_PIN_HOLE_FROM_END
from dt_pinion_lift_rod_spec import (
    CAP_SAG,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    DRAWING_REFERENCE_DIMENSIONS,
    PIN_HOLE_CALLOUT,
    ROD_DIA,
    ROD_DIA_CALLOUT,
    ROD_LEN,
    SURFACE_FINISHES,
)


# Cached machinist review leaf: a FIX or ERROR verdict fails the build.
MACHINIST_REVIEW = MachinistReviewMode.ENFORCE

SPEC = DRAWINGS_BY_NAME["dt_pinion_lift_rod"]
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
# The crown adds CAP_SAG past the nominal length, so the side view's bounding
# box (and its centre) span ROD_LEN + CAP_SAG.
HALF_SPAN = (ROD_LEN + CAP_SAG) / 2000.0
RIGHT_CENTER = (0.200, 0.215)
ISO_CENTER = (0.135, 0.125)
DETAIL_CENTER = (0.335, 0.132)
DETAIL_SCALE = (5, 1)
DETAIL_RADIUS_MM = 7.0
# The label anchors at its top centre. Above the circle it sat on the outline
# and crowded the pin-hole callout (r7 slice3 eye-pass), so it goes in the
# clear band between the circle (x <= 0.370) and the right border (0.419).
DETAIL_LABEL_XY = (0.391, 0.150)

# The rod's flank in the *Right view: the bearing finish leader drops onto it.
ROD_FLANK_Y = RIGHT_CENTER[1] + ROD_DIA * SHEET_SCALE[0] / 2000.0

# In the *Right view the part's +Z (crowned back end) points screen-left, so
# the flat front end (z 0) is the RIGHT silhouette edge.  The diameter and its
# mate hang above the rod, right of the finish symbol and left of Detail A's
# circle, high enough that the callout lines clear the rod; the body length
# and the (overall) stack below it, the overall outermost (rule 10).
RIGHT_KEEP = {
    "RodDia": (RIGHT_CENTER[0] - 0.005, ROD_FLANK_Y + 0.026),
    "RodBody": (RIGHT_CENTER[0], RIGHT_CENTER[1] - 0.020),
    "RodOverall": (RIGHT_CENTER[0], RIGHT_CENTER[1] - 0.032),
    "CapR": (RIGHT_CENTER[0] - HALF_SPAN - 0.012, RIGHT_CENTER[1] + 0.024),
}
DETAIL_KEEP = {
    # r7 eye-pass: above the detail the callout ran over the DETAIL A label
    # and past the right border; the open field left of the detail fits it.
    "PinHoleDia": (DETAIL_CENTER[0] - 0.090, DETAIL_CENTER[1] + 0.028),
    # Below the fence (bottom y 0.0975) and OUTSIDE the witness lines (hole
    # axis 0.335, front end 0.355): between them the text was struck by both.
    "PinHoleZ": (DETAIL_CENTER[0] + 0.047, DETAIL_CENTER[1] - 0.045),
}
DIMENSION_CALLOUTS = {
    # Below the value: SolidWorks stores a multi-line ABOVE callout but prints
    # none of it (r2 layout audit text-unmatched; draw_dt_cone_gear_shaft).
    "RodDia": ROD_DIA_CALLOUT,
    # The match-drill and its mate only: MHA-DT-00 names the hole in its step.
    "PinHoleDia": PIN_HOLE_CALLOUT,
    # The rod has one flat end and one crowned end; "front" named nothing on
    # the sheet (machinist review r2).
    "PinHoleZ": "FROM FLAT END",
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
        point = _early_bound(
            utility.CreatePoint(double_array([x, y, 0.0])), "IMathPoint"
        )
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


def _show_as_reference(
    adapter: Any, annotations: list[Any], names: frozenset[str]
) -> None:
    """Parenthesize each named linear dimension: (199.5), a reference.

    Through the prefix/suffix channel: ShowParenthesis read back True on the
    r2 sheet yet printed a bare 199.5.  Each name must be on the view once.
    """
    for name in sorted(names):
        found = [a for a in annotations if dimension_name(adapter, a) == name]
        if len(found) != 1:
            raise RuntimeError(
                f"expected one {name} on the side view, found {len(found)}"
            )
        set_reference_dimension(adapter, found[0], label=f"MHA-DT-17 {name}")


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
            "Isometric View Note",
        ),
        required=(
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
            "Isometric View Note",
        ),
    )
    drawing_model, _sheet = new_project_drawing(
        adapter,
        property_view=PART_STEM,
        scale=SHEET_SCALE,
        layout=SPEC.layout,
        unit=part_drawing_unit(PART_STEM),
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

    right = place_view(adapter, str(SOURCE), "*Right", *RIGHT_CENTER, scale=(1, 1))
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=(1, 2))
    for view in (right, iso):
        set_hidden_lines_removed(adapter, view)

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
    annotations = [*right_annotations, *detail_annotations]
    set_dimension_callouts(adapter, annotations, DIMENSION_CALLOUTS)
    assert_imported_precision(adapter, annotations, DRAWING_PRECISION_BY_NAME)
    _show_as_reference(adapter, right_annotations, DRAWING_REFERENCE_DIMENSIONS)
    if not auto_center_marks(adapter, detail, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center mark to the pin hole")

    # drawing-guidelines.md rule 6 (roughness symbols only where a surface runs, slides or locates): the flank turns in the pivot blocks' bores -- the one running
    # surface.  A cylinder carries no model edge along its side, so the pick
    # is a SILHOUETTE entity.
    add_surface_finish(
        adapter,
        right,
        edge_xy=(RIGHT_CENTER[0] - 0.045, ROD_FLANK_Y),
        symbol_xy=(RIGHT_CENTER[0] - 0.045, ROD_FLANK_Y + 0.020),
        control=surface_finish_by_key(SURFACE_FINISHES, "bearing"),
        label="lift rod bearing finish",
        entity_type="SILHOUETTE",
        char_height=0.0025,  # the pivot-block size; the default read oversized
    )

    # Under the 1:2 isometric (x 0.098-0.172, bottom y ~0.104).
    add_property_linked_note(adapter, "Isometric View Note", 0.105, 0.097)

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
