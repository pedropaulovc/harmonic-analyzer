r"""Create the curated machinist drawing for the pinion return leaf spring.

NOT a coil spring: a bent phosphor-bronze leaf.  A 0.5 blank -- a 5.0 strip
with a square screw pad at its free end -- formed as a flat screw-down foot, an
R2 bend up to a blade leaning back over the foot's bend, then an R1.5 crest
turning 25 deg out to a short free flat.  The solid is the installed shape;
the front view also shows the part's hidden FreeForm reference sketch as the
phantom free form, and the free crest and tip are baselined from the foot's
free end on it.  The projected top view carries the blank's pad, strip width
and hole; a 5:1 detail carries the crest.

Run with SolidWorks open::

    uv run python cad\scripts\draw_pinion_spring.py pinion-spring
"""

from __future__ import annotations

import argparse
import math
import sys
from typing import Any

import _drawing_hidden_sketches as hidden_sketches
import _telemetry
from _common import CAD_ROOT, _early_bound, _read_member, check, run_build
from _drawing_common import (
    DrawingOutputs,
    add_native_hole_callout,
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
from pinion_spring_geometry import (
    BEND_CX,
    FLAT_TIP,
    FOOT_END,
    FOOT_TAN,
    FREE_FLAT_TIP,
    FREE_KINK_START,
    HOLE_DIA,
    HOLE_FROM_END,
    KINK_C,
    PAD_LEN,
    R_KINK,
    THICK,
)
from pinion_spring_spec import DRAWING_DIMENSIONS, DRAWING_PRECISION_BY_NAME
from solidworks_mcp.adapters.com_variant import double_array
from solidworks_mcp.adapters.solidworks.drawing import (
    auto_center_marks,
    place_view,
)


SPEC = DRAWINGS_BY_NAME["pinion_spring"]
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

SHEET_SCALE = (2.0, 1.0)
_S = SHEET_SCALE[0] / 1000.0

# Front view (XY): the profile -- the foot along the bottom running right to
# its free end, the blade rising at the left and leaning back over the bend.
# Views centre on their bounding boxes; the profile spans the crest's outer
# face to the foot's free end and the foot's underside to the free tip.
_PROFILE_MIN_X = KINK_C[0] - (R_KINK + THICK)
FRONT_BBOX_CX = (_PROFILE_MIN_X + FOOT_END[0]) / 2.0
FRONT_BBOX_CY = (FLAT_TIP[1] + THICK) / 2.0
FRONT_CENTER = (0.110, 0.118)
# Third-angle projection: the top view sits ABOVE the front and shares its X
# station (both views span the same model x range), so the pad and hole read
# straight up from the profile's free end.
TOP_CENTER = (FRONT_CENTER[0], 0.210)
ISO_CENTER = (0.350, 0.150)
DETAIL_CENTER = (0.240, 0.195)
DETAIL_SCALE = (5, 1)
# The kink detail's fence: centred between the kink centre and the free tip,
# large enough to take the whole R1.5 arc and the flat.
DETAIL_FOCUS = (
    (KINK_C[0] + FLAT_TIP[0]) / 2.0,
    (KINK_C[1] + FLAT_TIP[1]) / 2.0,
)
DETAIL_RADIUS_MM = 3.5
DETAIL_LABEL_XY = (0.222, 0.160)
# The parent fence's native "A" goes WEST of the fence, level with its centre:
# SolidWorks sets it above the fence, on the FREE, TO KINK TANGENT row
# (stacktop-dbe47ae3 and spring-r1 both printed it there).  West of the fence
# is open sheet; the free-form phantom runs on the fence's west edge.
PARENT_LETTER_OFFSET = (-(DETAIL_RADIUS_MM * _S + 0.005), 0.0)


def _front_x(model_x_mm: float) -> float:
    return FRONT_CENTER[0] + (model_x_mm - FRONT_BBOX_CX) * _S


def _front_y(model_y_mm: float) -> float:
    return FRONT_CENTER[1] + (model_y_mm - FRONT_BBOX_CY) * _S


_FOOT_MID_X = (FOOT_END[0] + FREE_KINK_START[0]) / 2.0
_PROFILE_TOP = _front_y(max(FLAT_TIP[1], FREE_FLAT_TIP[1]))
FRONT_KEEP = {
    "FootLen": (_front_x((FOOT_TAN[0] + FOOT_END[0]) / 2.0), _front_y(0.0) - 0.010),
    "BendR": (_front_x(BEND_CX) - 0.032, _front_y(0.0) - 0.004),
    # The free locations, on the FreeForm phantom.
    "FreeKinkV": (_front_x(FOOT_END[0]) + 0.016, _front_y(FREE_KINK_START[1] / 2.0)),
    # Clear of the kink fence's native "A" label, which SolidWorks sets just
    # above the fence (spring-r1 put the 15.0 text on it), with a text gap
    # between the two and the top view lifted to make room.
    "FreeKinkH": (_front_x(_FOOT_MID_X), _PROFILE_TOP + 0.020),
    "FreeTipH": (_front_x(_FOOT_MID_X), _PROFILE_TOP + 0.038),
}
_PAD_EAST = _front_x(FOOT_END[0])
HOLE_END_TEXT_XY = (_front_x(FOOT_END[0] - HOLE_FROM_END / 2.0), TOP_CENTER[1] + 0.031)
HOLE_EDGE_TEXT_XY = (_PAD_EAST + 0.012, TOP_CENTER[1] + 0.004)
TOP_KEEP = {
    "PadLen": (_front_x(FOOT_END[0] - PAD_LEN / 2.0), TOP_CENTER[1] + 0.021),
    # Outboard of the hole-edge 4.75 (HOLE_EDGE_TEXT_XY) so the two stack apart.
    "PadWidth": (_PAD_EAST + 0.030, TOP_CENTER[1]),
    "StripWidth": (_front_x(_PROFILE_MIN_X) - 0.018, TOP_CENTER[1]),
    # The hole off the foot's free end and off the pad's lower edge: owned by
    # the part's hidden FootHoleReference sketch (#843 Codex aB7).
    "HoleFromEnd": HOLE_END_TEXT_XY,
    "HoleFromEdge": HOLE_EDGE_TEXT_XY,
}
DETAIL_KEEP = {
    # The flick turns right (east) in this view: the radius leader goes
    # upper-left of the fence, the flat's length to its right.
    "KinkR": (0.205, 0.232),
    "FlatLen": (0.282, 0.200),
}
DIMENSION_CALLOUTS = {
    "FootLen": "TO BEND TANGENT",
    "FreeKinkH": "FREE, TO KINK TANGENT",
    "FreeKinkV": "FREE, TO KINK TANGENT",
    "FreeTipH": "FREE, TO TIP",
}
# Below the pad: above it the leader crossed the 4.50 and 9.50 pad
# dimensions on its way down to the hole.  The note centres on this point, so
# it sits east of the pad, clear of the FREE, TO TIP text below the top view.
HOLE_CALLOUT_XY = (_PAD_EAST + 0.035, TOP_CENTER[1] - 0.019)
# The #4 normal clearance (3.264 mm = 0.1285 in) is a No. 30 drill; the shop
# reaches for the number, the native size compartment still prints the diameter.
HOLE_PROCESS = "#30 DRILL"


def _kink_detail(adapter: Any, front: Any) -> Any:
    """Enlarge the formed kink and the free flat in a native 5:1 detail."""
    draw = adapter.currentModel
    drawing = _early_bound(draw, "IDrawingDoc")
    parent = _early_bound(front, "IView")
    if not drawing.ActivateView(view_name(adapter, front)):
        raise RuntimeError("failed to activate kink-detail parent")
    draw.ClearSelection2(True)
    center = model_point_in_view(
        adapter,
        front,
        (DETAIL_FOCUS[0] / 1000.0, DETAIL_FOCUS[1] / 1000.0, 0.0),
        label="kink detail centre",
    )
    radius = DETAIL_RADIUS_MM * _S
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
        raise RuntimeError("failed to create kink-detail fence")
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
        raise RuntimeError("failed to create kink detail")
    detail = _early_bound(detail, "IView")
    detail.ScaleRatio = double_array([float(value) for value in DETAIL_SCALE])
    draw.ClearSelection2(True)
    draw.EditRebuild3()
    outline = tuple(float(value) for value in detail.GetOutline())
    position = tuple(float(value) for value in detail.Position)
    if len(outline) != 4 or len(position) != 2:
        raise RuntimeError("kink detail has invalid bounds")
    target = [
        position[axis] + DETAIL_CENTER[axis] - (outline[axis] + outline[axis + 2]) / 2.0
        for axis in range(2)
    ]
    if not detail.SetViewPosition(double_array(target), False):
        raise RuntimeError("failed to position kink detail")
    draw.EditRebuild3()
    notes = tuple(_read_member(detail, "GetNotes") or ())
    if len(notes) != 1:
        raise RuntimeError(f"expected one native detail label, found {len(notes)}")
    note = _early_bound(notes[0], "INote")
    annotation = _early_bound(_read_member(note, "GetAnnotation"), "IAnnotation")
    label_xyz = (*DETAIL_LABEL_XY, 0.0)
    if not annotation.SetPosition2(*label_xyz):
        raise RuntimeError("failed to position kink detail label")
    draw.EditRebuild3()
    actual = tuple(float(value) for value in _read_member(annotation, "GetPosition"))
    if math.dist(actual, label_xyz) > 1e-8:
        raise RuntimeError(f"kink detail label position did not persist: {actual}")
    # _stock_trim_drawing.position_parent_detail_letter's proven form.
    circles = tuple(_read_member(parent, "GetDetailCircles") or ())
    if len(circles) != 1:
        raise RuntimeError(f"expected one parent detail circle, found {len(circles)}")
    circle = _early_bound(circles[0], "IDetailCircle")
    letter = tuple(center[axis] + PARENT_LETTER_OFFSET[axis] for axis in range(2))
    circle.SetLabelPosition(*letter)
    draw.EditRebuild3()
    placed = tuple(float(value) for value in circle.GetLabelPosition())
    if len(placed) != 2 or math.dist(placed, letter) > 1e-8:
        raise RuntimeError(
            f"parent detail-circle label position did not persist: {placed}"
        )
    return detail


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open pinion-spring source", await adapter.open_model(str(SOURCE)))
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
            0: "Pinion Return Leaf Spring Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "pinion return spring; bent brass leaf; formed blank",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )
    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=(2, 1))
    top = place_view(adapter, str(SOURCE), "*Top", *TOP_CENTER, scale=(2, 1))
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=(1, 1))
    # Rule 7: nothing on this part is communicated by a hidden line -- the
    # hole is defined by its callout -- so every view is hidden-lines-removed.
    for view in (front, top, iso):
        set_hidden_lines_removed(adapter, view)

    # The front view imports the part-hidden FreeForm reference sketch, so it
    # takes the opt-in curation that shows it (the phantom) in this view only.
    # The kink detail is derived from it and is created while the part still
    # hides the sketch, so it shows the installed crest alone.
    front_annotations = hidden_sketches.curate_view_dimensions(
        adapter,
        front,
        keep=FRONT_KEEP,
        view_label="formed profile",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    # The hole locations come from the part-hidden FootHoleReference sketch,
    # shown in this view only by the same opt-in curation.
    top_annotations = hidden_sketches.curate_view_dimensions(
        adapter,
        top,
        keep=TOP_KEEP,
        view_label="blank top",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    detail = _kink_detail(adapter, front)
    set_hidden_lines_removed(adapter, detail)
    detail_annotations = curate_view_dimensions(
        adapter,
        detail,
        keep=DETAIL_KEEP,
        view_label="kink detail",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    annotations = [*front_annotations, *top_annotations, *detail_annotations]
    set_dimension_callouts(adapter, annotations, DIMENSION_CALLOUTS)
    assert_imported_precision(adapter, annotations, DRAWING_PRECISION_BY_NAME)

    if not auto_center_marks(adapter, top, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center marks to top view")
    hole_edge = model_point_in_view(
        adapter,
        top,
        (
            (FOOT_END[0] - HOLE_FROM_END) / 1000.0,
            THICK / 1000.0,
            HOLE_DIA / 2000.0,
        ),
        label="pad hole edge",
    )
    add_native_hole_callout(
        adapter,
        top,
        edge_xy=hole_edge,
        callout_xy=HOLE_CALLOUT_XY,
        label="spring pad clearance hole",
        process=HOLE_PROCESS,
    )

    add_property_linked_note(adapter, "Manufacturing Notes", 0.020, 0.058)
    add_property_linked_note(adapter, "Isometric View Note", 0.325, 0.115)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Pinion Return Leaf Spring Manufacturing Drawing",
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
