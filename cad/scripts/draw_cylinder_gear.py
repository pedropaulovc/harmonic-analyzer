r"""Create the simplicity-policy manufacturing drawing for the cylinder gear.

The portrait sheet uses one aligned third-angle row: the cam-side front view
shows the eccentric follower, bore and phase notch, while the right view shows
the axial stack.  A standard isometric supplies pictorial clarity without
replacing those manufacturing views.
"""

from __future__ import annotations

import argparse
import math
import sys
from typing import Any

import _telemetry
from _common import CAD_ROOT, _early_bound, check, run_build
from _drawing_common import (
    DrawingOutputs,
    add_edge_dimension,
    add_property_linked_note,
    add_surface_finish,
    curate_view_dimensions,
    dimension_name,
    finalize_drawing,
    model_point_in_view,
    new_project_drawing,
    read_required_properties,
    set_dimension_callouts,
    set_dimension_precision,
    set_hidden_lines_visible,
    set_reference_dimension,
    set_reference_dimensions,
    stamp_drawing_summary,
    view_name,
)
from _drawing_registry import DRAWINGS_BY_NAME
from _gear_drawing_entities import visible_circle_edge
from _surface_finish import surface_finish_by_key
from cylinder_gear_spec import (
    BORE_DIA,
    BORE_FIT_CALLOUT,
    CAM_AXIAL_FIT_CALLOUT,
    CAM_DIA,
    CAM_THICKNESS,
    ECCENTRICITY,
    FACE_WIDTH,
    NOTCH_CENTER_X,
    NOTCH_FLOOR_RADIUS,
    OVERALL_THICKNESS,
    SURFACE_FINISHES,
    TIP_RADIUS,
)
from solidworks_mcp.adapters.com_variant import double_array
from solidworks_mcp.adapters.solidworks.drawing import auto_center_marks, place_view


SPEC = DRAWINGS_BY_NAME["cylinder_gear"]
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

# Portrait makes the 62.2 mm gear materially larger than the old landscape
# 1:1 layout.  The cam-side front view exposes every radial feature, so a
# redundant opposite face view would only consume the exterior dimension lanes.
SHEET_SCALE = (3.0, 2.0)
VIEW_SCALE = (3, 2)
FRONT_CENTER = (0.105, 0.270)
RIGHT_CENTER = (0.205, 0.270)
ISO_CENTER = (0.165, 0.145)
GEAR_DATA_POS = (0.015, 0.410)
MANUFACTURING_NOTES_POS = (0.015, 0.085)
NOTCH_DETAIL_CENTER = (0.060, 0.155)
NOTCH_DETAIL_SCALE = (6, 1)
NOTCH_DETAIL_RADIUS_MM = 4.0
NOTCH_DETAIL_DIMENSIONS = {
    "NotchWidth": (0.060, 0.188),
    "NotchDepth": (0.025, 0.155),
}

FRONT_KEEP = {
    "BoreDia": (0.065, 0.360),
    "CamDia": (0.175, 0.325),
    "CamCy": (0.175, 0.279),
}
RIGHT_KEEP = {
    "FaceWidth": (0.205, 0.220),
    "CamThickness": (0.205, 0.360),
}
DIMENSION_CALLOUTS = {
    "BoreDia": BORE_FIT_CALLOUT,
    "NotchWidth": "ALIGNMENT NOTCH",
    "NotchDepth": "FROM OD",
}
DIMENSION_PRECISION = {
    "BoreDia": 3,
    "CamDia": 2,
    "FaceWidth": 2,
    "CamCy": 3,
    "CamThickness": 1,
    "NotchWidth": 2,
    "NotchDepth": 1,
}


def _project_mm(
    adapter: Any,
    view: Any,
    xyz_mm: tuple[float, float, float],
    *,
    label: str,
) -> tuple[float, float]:
    return model_point_in_view(
        adapter,
        view,
        tuple(value / 1000.0 for value in xyz_mm),
        label=label,
    )


def _notch_detail(adapter: Any, front: Any) -> Any:
    """Enlarge the actual kerf and its neighbouring teeth, without redrawing them."""
    draw = adapter.currentModel
    ddoc = _early_bound(draw, "IDrawingDoc")
    parent = _early_bound(front, "IView")
    if not ddoc.ActivateView(view_name(adapter, front)):
        raise RuntimeError("failed to activate notch-detail parent")
    draw.ClearSelection2(True)
    center = _project_mm(
        adapter,
        front,
        (NOTCH_CENTER_X, (TIP_RADIUS + NOTCH_FLOOR_RADIUS) / 2.0, 0.0),
        label="notch detail center",
    )
    radius = NOTCH_DETAIL_RADIUS_MM * VIEW_SCALE[0] / VIEW_SCALE[1] / 1000.0
    sketch = _early_bound(parent.GetSketch(), "ISketch")
    transform = _early_bound(sketch.ModelToSketchTransform, "IMathTransform")
    math_utility = _early_bound(adapter.swApp.GetMathUtility(), "IMathUtility")
    points = []
    for x, y in (center, (center[0] + radius, center[1])):
        point = _early_bound(
            math_utility.CreatePoint(double_array([x, y, 0.0])), "IMathPoint"
        )
        projected = _early_bound(point.MultiplyTransform(transform), "IMathPoint")
        points.append(tuple(float(value) for value in projected.ArrayData))
    sketch_manager = _early_bound(draw.SketchManager, "ISketchManager")
    if sketch_manager.CreateCircle(*points[0], *points[1]) is None:
        raise RuntimeError("failed to create notch-detail fence")
    detail = ddoc.CreateDetailViewAt4(
        *NOTCH_DETAIL_CENTER, 0.0,
        0,  # swDetViewSTANDARD
        *NOTCH_DETAIL_SCALE,
        "A",
        1,  # swDetCircleCIRCLE
        True, False, False, 5,
    )
    if detail is None:
        raise RuntimeError("failed to create native notch detail")
    detail = _early_bound(detail, "IView")
    detail.ScaleRatio = double_array([float(value) for value in NOTCH_DETAIL_SCALE])
    draw.ClearSelection2(True)
    draw.EditRebuild3()
    initial_outline = tuple(float(value) for value in detail.GetOutline())
    initial_position = tuple(float(value) for value in detail.Position)
    if len(initial_outline) != 4 or len(initial_position) != 2:
        raise RuntimeError(
            f"invalid native notch detail bounds: {initial_outline!r}, {initial_position!r}"
        )
    # A cropped view's Position is not its visible crop center. Translate the
    # native origin by the measured outline-center error, rather than assigning
    # the requested crop center directly to that origin.
    positioned_origin = tuple(
        initial_position[axis] + NOTCH_DETAIL_CENTER[axis]
        - (initial_outline[axis] + initial_outline[axis + 2]) / 2.0
        for axis in range(2)
    )
    if not detail.SetViewPosition(double_array(list(positioned_origin)), False):
        raise RuntimeError("failed to position notch detail")
    draw.EditRebuild3()
    ratio = tuple(float(value) for value in detail.ScaleRatio)
    final_outline = tuple(float(value) for value in detail.GetOutline())
    if len(final_outline) != 4:
        raise RuntimeError(f"invalid final notch detail bounds: {final_outline!r}")
    outline_center = (
        (final_outline[0] + final_outline[2]) / 2.0,
        (final_outline[1] + final_outline[3]) / 2.0,
    )
    if len(ratio) != 2 or not math.isclose(
        ratio[0] / ratio[1], NOTCH_DETAIL_SCALE[0] / NOTCH_DETAIL_SCALE[1]
    ):
        raise RuntimeError(f"notch detail scale did not persist: {ratio!r}")
    if math.dist(outline_center, NOTCH_DETAIL_CENTER) > 0.0001:
        raise RuntimeError(
            f"notch detail outline center did not persist: "
            f"initial_outline={initial_outline!r}, initial_position={initial_position!r}, "
            f"requested_origin={positioned_origin!r}, final_outline={final_outline!r}"
        )
    _telemetry.info(
        f"notch detail position: initial_outline={initial_outline!r}, "
        f"initial_position={initial_position!r}, origin={positioned_origin!r}, "
        f"final_outline={final_outline!r}, crop_center={outline_center!r}"
    )
    return detail


def _notch_dimension_state(dimension: Any) -> tuple[Any, ...]:
    """Snapshot the native model parameter, not formatted drawing text."""
    dimension = _early_bound(dimension, "IDimension")
    tolerance = _early_bound(dimension.Tolerance, "IDimensionTolerance")
    return (
        str(dimension.FullName),
        float(dimension.SystemValue),
        int(tolerance.Type),
        tolerance.GetMinValue2(),
        tolerance.GetMaxValue2(),
    )


def _check_notch_dimensions(
    adapter: Any,
    front: Any,
    right: Any,
    detail: Any,
    original: dict[str, tuple[Any, ...]],
) -> list[Any]:
    """Require one native detail annotation matching each original part parameter."""
    target_name = view_name(adapter, detail)
    target_annotations = [
        _early_bound(item, "IAnnotation")
        for item in (_early_bound(detail, "IView").GetAnnotations() or ())
    ]
    target_names = [dimension_name(adapter, item) for item in target_annotations]
    other_names = {
        view_name(adapter, view): [
            dimension_name(adapter, _early_bound(item, "IAnnotation"))
            for item in (_early_bound(view, "IView").GetAnnotations() or ())
        ]
        for view in (front, right)
    }
    for name, text_xy in NOTCH_DETAIL_DIMENSIONS.items():
        matches = [
            item for item, item_name in zip(target_annotations, target_names, strict=True)
            if item_name == name
        ]
        if len(matches) != 1 or any(name in names for names in other_names.values()):
            raise RuntimeError(
                f"notch dimension {name} lacks unique detail authority: "
                f"other_views={other_names!r}; "
                f"target={target_name!r} names={target_names!r}"
            )
        display = _early_bound(matches[0].GetSpecificAnnotation(), "IDisplayDimension")
        state = _notch_dimension_state(display.GetDimension2(0))
        if state != original[name]:
            raise RuntimeError(
                f"native notch dimension {name} differs from source part: "
                f"source={original[name]!r}, detail={state!r}"
            )
        position = tuple(float(value) for value in matches[0].GetPosition())
        if math.dist(position[:2], text_xy) > 0.0001:
            raise RuntimeError(f"notch dimension {name} position did not persist")
    return [
        annotation for annotation, name in zip(target_annotations, target_names, strict=True)
        if name in NOTCH_DETAIL_DIMENSIONS
    ]


def _checked_edge_dimension(
    adapter: Any,
    view: Any,
    *,
    p0: tuple[float, float],
    p1: tuple[float, float],
    text_xy: tuple[float, float],
    label: str,
    expected_mm: float,
    precision: int,
    orientation: str,
) -> Any:
    """Add one source-geometry dimension and verify its value and precision."""
    display = add_edge_dimension(
        adapter,
        view,
        p0=p0,
        p1=p1,
        text_xy=text_xy,
        label=label,
        orientation=orientation,
    )
    display = _early_bound(display, "IDisplayDimension")
    dimension = _early_bound(display.GetDimension2(0), "IDimension")
    measured_mm = abs(float(dimension.SystemValue) * 1000.0)
    if abs(measured_mm - expected_mm) > 1e-5:
        raise RuntimeError(
            f"{label}: measured {measured_mm:g}, expected {expected_mm:g} mm"
        )
    display.SetPrecision3(precision, -1, -1, -1)
    if int(display.GetPrimaryPrecision2()) != precision:
        raise RuntimeError(
            f"{label}: precision {display.GetPrimaryPrecision2()} != {precision}"
        )
    return display


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open cylinder-gear source", await adapter.open_model(str(SOURCE)))
    read_required_properties(
        adapter.currentModel,
        (
            "Number",
            "Revision",
            "Title",
            "Material Specification",
            "Finish",
            "Quantity",
            "Gear Data",
            "Manufacturing Notes",
        ),
        required=(
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
            "Gear Data",
            "Manufacturing Notes",
        ),
    )
    drawing_model, _sheet = new_project_drawing(
        adapter, property_view=PART_STEM, scale=SHEET_SCALE, layout=SPEC.layout
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Cylinder Gear Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "cylinder gear; integral eccentric cam; brass; 120T",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    front = place_view(
        adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=VIEW_SCALE
    )
    right = place_view(
        adapter, str(SOURCE), "*Right", *RIGHT_CENTER, scale=VIEW_SCALE
    )
    place_view(
        adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=VIEW_SCALE
    )
    for view in (front, right):
        set_hidden_lines_visible(adapter, view)

    detail = _notch_detail(adapter, front)
    set_hidden_lines_visible(adapter, detail)
    # HLV changes remain pending until Windows repaints. This documented view
    # barrier makes the new display geometry available synchronously to import.
    _early_bound(detail, "IView").UpdateViewDisplayGeometry()
    source_model = _early_bound(
        _early_bound(front, "IView").ReferencedDocument, "IModelDoc2"
    )
    original_notch = {
        name: _notch_dimension_state(source_model.Parameter(f"{name}@NotchProfile"))
        for name in NOTCH_DETAIL_DIMENSIONS
    }
    # Author the notch dimensions directly in their final view before any
    # parent-view import can claim them or leave deleted-display history.
    curate_view_dimensions(
        adapter, detail, keep=NOTCH_DETAIL_DIMENSIONS, view_label="notch detail"
    )
    front_annotations = curate_view_dimensions(
        adapter, front, keep=FRONT_KEEP, view_label="front"
    )
    right_annotations = curate_view_dimensions(
        adapter, right, keep=RIGHT_KEEP, view_label="right"
    )
    detail_annotations = _check_notch_dimensions(
        adapter, front, right, detail, original_notch
    )
    annotations = [*front_annotations, *right_annotations, *detail_annotations]
    set_dimension_callouts(adapter, annotations, DIMENSION_CALLOUTS)
    set_dimension_precision(adapter, annotations, DIMENSION_PRECISION)
    set_reference_dimensions(adapter, annotations, {"BoreDia"})
    cam_thickness_annotations = [
        annotation
        for annotation in right_annotations
        if dimension_name(adapter, annotation) == "CamThickness"
    ]
    if len(cam_thickness_annotations) != 1:
        raise RuntimeError("expected one cam thickness reference dimension")
    cam_thickness_display = set_reference_dimension(
        adapter, cam_thickness_annotations[0], label="cam thickness reference"
    )
    # Keep the fit with the nominal in the linear dimension's primary text.
    # Its callout-above slot did not render in the native export.
    cam_thickness_prefix = f"{CAM_AXIAL_FIT_CALLOUT}\n("
    cam_thickness_display.SetText(1, cam_thickness_prefix)

    if not auto_center_marks(adapter, front, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center marks to cam-side front view")

    # Face width is controlled; cam thickness is fitted to the connecting rod.
    # Show the measured nominal end-to-end stack as a checked REFERENCE overall.
    cam_bore_wall = CAM_DIA / 2.0 - ECCENTRICITY - BORE_DIA / 2.0
    overall_pick_y = -(BORE_DIA / 2.0 + cam_bore_wall / 2.0)
    overall = _checked_edge_dimension(
        adapter,
        right,
        p0=_project_mm(
            adapter,
            right,
            (0.0, overall_pick_y, 0.0),
            label="overall gear front edge",
        ),
        p1=_project_mm(
            adapter,
            right,
            (0.0, overall_pick_y, OVERALL_THICKNESS),
            label="overall cam rear edge",
        ),
        text_xy=(RIGHT_CENTER[0] + 0.020, 0.200),
        label="overall axial thickness",
        expected_mm=OVERALL_THICKNESS,
        precision=1,
        orientation="horizontal",
    )
    overall.ShowParenthesis = True
    if not overall.ShowParenthesis:
        raise RuntimeError("overall axial thickness was not shown as reference")

    bore_edge = visible_circle_edge(adapter, front, BORE_DIA)
    add_surface_finish(
        adapter,
        front,
        symbol_xy=(0.030, 0.310),
        control=surface_finish_by_key(SURFACE_FINISHES, "cylinder_gear_bore"),
        label="cylinder gear bore finish",
        entity=bore_edge,
        leader_attach_xy=_project_mm(
            adapter,
            front,
            (-BORE_DIA / (2.0 * math.sqrt(2.0)), BORE_DIA / (2.0 * math.sqrt(2.0)), 0.0),
            label="bore finish leader attachment",
        ),
        char_height=0.0025,
    )

    # The follower finish belongs on the cam's cylindrical flank.  The side
    # view exposes that surface without dragging a leader across the gear face.
    cam_flank = _project_mm(
        adapter,
        right,
        (
            0.0,
            ECCENTRICITY + CAM_DIA / 2.0,
            FACE_WIDTH + CAM_THICKNESS / 2.0,
        ),
        label="cam follower flank",
    )
    add_surface_finish(
        adapter,
        right,
        edge_xy=cam_flank,
        symbol_xy=(0.220, 0.310),
        control=surface_finish_by_key(SURFACE_FINISHES, "cam_follower"),
        label="cam follower finish",
        entity_type="SILHOUETTE",
        leader_attach_xy=cam_flank,
        char_height=0.0025,
    )

    add_property_linked_note(
        adapter, "Gear Data", *GEAR_DATA_POS, char_height=0.0025
    )
    add_property_linked_note(
        adapter,
        "Manufacturing Notes",
        *MANUFACTURING_NOTES_POS,
        char_height=0.0025,
    )
    # Check the complete native requirement after all annotation formatting.
    drawing_model.EditRebuild3()
    drawing_model.GraphicsRedraw2()
    if (
        str(cam_thickness_display.GetText(1) or "") != cam_thickness_prefix
        or str(cam_thickness_display.GetText(2) or "") != ")"
    ):
        raise RuntimeError("cam thickness reference/axial-fit text did not persist")
    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Cylinder Gear Manufacturing Drawing",
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
