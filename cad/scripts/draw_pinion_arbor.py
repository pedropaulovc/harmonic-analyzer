r"""Create the integral MHA-102 pinion-arbor manufacturing drawing."""

from __future__ import annotations

import argparse
import math
import sys
from typing import Any

import _telemetry
from _common import CAD_ROOT, _early_bound, _read_member, check, run_build
from _drawing_common import (
    DrawingOutputs,
    add_edge_dimension,
    add_property_linked_note,
    add_surface_finish,
    add_view_centerline,
    assert_imported_precision,
    curate_view_dimensions,
    dimension_name,
    finalize_drawing,
    model_point_in_view,
    new_project_drawing,
    read_required_properties,
    set_dimension_callouts,
    set_hidden_lines_removed,
    set_reference_dimension,
    set_reference_dimensions,
    stamp_drawing_summary,
    view_name,
)
from _drawing_registry import DRAWINGS_BY_NAME
from _surface_finish import surface_finish_by_key
from pinion_arbor_spec import (
    BACK_CAP_R,
    CROSS_HOLE_CALLOUT,
    DRAWING_PRECISION_BY_NAME,
    DRAWING_REFERENCE_PRECISION,
    HEAD_CENTER_Z,
    HEAD_DIA,
    HEAD_REAR_Z,
    NECK_DIA,
    NECK_END_Z,
    SHAFT_DIA,
    SURFACE_FINISHES,
)
from solidworks_mcp.adapters.com_variant import double_array
from solidworks_mcp.adapters.pywin32_adapter import null_callout
from solidworks_mcp.adapters.solidworks.drawing import (
    auto_center_marks,
    delete_view,
    iter_views,
    place_view,
)

SPEC = DRAWINGS_BY_NAME["pinion_arbor"]
PART_STEM = SPEC.artifact_stem
SOURCE = CAD_ROOT / "out" / "sldprt" / f"{PART_STEM}.SLDPRT"
OUTPUTS = DrawingOutputs(
    slddrw=SPEC.outputs["slddrw"], pdf=SPEC.outputs["pdf"], png=SPEC.outputs["png"]
)
SLDDRW, PDF, PNG = OUTPUTS.slddrw, OUTPUTS.pdf, OUTPUTS.png
SHEET_SCALE = (1.0, 1.0)
PRINCIPAL_CENTER = (0.200, 0.170)
ISO_CENTER = (0.365, 0.225)
DETAIL_CENTER = (0.165, 0.235)
DETAIL_SCALE = (2, 1)
DETAIL_RADIUS_MM = 15.0
DETAIL_LABEL_XY = (0.110, 0.195)
DONOR_KEEP = {
    "ShaftDia": (0.030, 0.145),
}
PRINCIPAL_KEEP = {
    "NeckLen": (0.325, 0.100),
    "BackRimFromHeadRear": (0.205, 0.095),
    "OverallLen": (0.205, 0.080),
    "BackCapSagDim": (0.055, 0.220),
}
DETAIL_KEEP = {
    "HeadLen": (0.165, 0.205),
    "HeadCapR": (0.195, 0.262),
    "HeadCapSagDim": (0.205, 0.210),
    "CrossHoleDia": (0.245, 0.245),
    "CrossHoleFromHeadRear": (0.155, 0.258),
}
DIAMETER_POSITIONS = {
    "HeadDia": (0.165, 0.215),
    "NeckDia": (0.125, 0.215),
    "ShaftDia": (0.235, 0.190),
}
DIMENSION_CALLOUTS = {
    "BackRimFromHeadRear": "FROM BACK CROWN ROOT TO HEAD SHOULDER",
    "OverallLen": "OVERALL",
    "BackCapSagDim": f"SR{BACK_CAP_R:.1f} BACK CROWN",
    "CrossHoleDia": CROSS_HOLE_CALLOUT,
}
SHAFT_FLANK_Y = PRINCIPAL_CENTER[1] + SHAFT_DIA / 2000.0


def _move_dimension(
    adapter: Any,
    annotation: Any,
    target: Any,
    text_xy: tuple[float, float],
    *,
    source_view: Any,
) -> Any:
    """Move a native model dimension and verify its new drawing-view owner."""
    name = dimension_name(adapter, annotation)
    draw = adapter.currentModel
    drawing = _early_bound(draw, "IDrawingDoc")
    if not drawing.ActivateView(view_name(adapter, source_view)):
        raise RuntimeError(f"{name}: failed to activate source dimension view")
    draw.ClearSelection2(True)
    display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
    selection_name = str(display.GetNameForSelection() or "")
    if not selection_name or not draw.Extension.SelectByID2(
        selection_name,
        "DIMENSION",
        0.0,
        0.0,
        0.0,
        False,
        0,
        null_callout(),
        0,
    ):
        raise RuntimeError(f"failed to select model dimension {name}: {selection_name!r}")
    drawing.DragModelDimension(view_name(adapter, target), 2, text_xy[0], text_xy[1], 0.0)
    draw.ClearSelection2(True)
    draw.EditRebuild3()
    matches = [
        _early_bound(item, "IAnnotation")
        for item in (_early_bound(target, "IView").GetAnnotations() or ())
        if dimension_name(adapter, _early_bound(item, "IAnnotation")) == name
    ]
    if len(matches) != 1:
        raise RuntimeError(f"{name}: native dimension did not move into target view")
    return matches[0]


def _head_detail(adapter: Any, parent_view: Any) -> Any:
    """Create an enlarged native detail of the crowded turned head."""
    draw = adapter.currentModel
    drawing = _early_bound(draw, "IDrawingDoc")
    parent = _early_bound(parent_view, "IView")
    if not drawing.ActivateView(view_name(adapter, parent_view)):
        raise RuntimeError("failed to activate integral-arbor detail parent")
    draw.ClearSelection2(True)
    center = model_point_in_view(
        adapter,
        parent_view,
        (0.0, 0.0, HEAD_CENTER_Z / 1000.0),
        label="integral-arbor head detail centre",
    )
    radius = DETAIL_RADIUS_MM / 1000.0
    sketch = _early_bound(parent.GetSketch(), "ISketch")
    transform = _early_bound(sketch.ModelToSketchTransform, "IMathTransform")
    utility = _early_bound(adapter.swApp.GetMathUtility(), "IMathUtility")
    points = []
    for x, y in (center, (center[0] + radius, center[1])):
        point = _early_bound(
            utility.CreatePoint(double_array([x, y, 0.0])), "IMathPoint"
        )
        projected = _early_bound(
            point.MultiplyTransform(transform), "IMathPoint"
        )
        points.append(tuple(float(value) for value in projected.ArrayData))
    manager = _early_bound(draw.SketchManager, "ISketchManager")
    if manager.CreateCircle(*points[0], *points[1]) is None:
        raise RuntimeError("failed to create integral-arbor detail fence")
    detail = drawing.CreateDetailViewAt4(
        *DETAIL_CENTER,
        0.0,
        0,
        *DETAIL_SCALE,
        "A",
        1,
        True,
        False,
        False,
        5,
    )
    if detail is None:
        raise RuntimeError("failed to create integral-arbor head detail")
    detail = _early_bound(detail, "IView")
    detail.ScaleRatio = double_array([float(value) for value in DETAIL_SCALE])
    draw.ClearSelection2(True)
    draw.EditRebuild3()
    outline = tuple(float(value) for value in detail.GetOutline())
    position = tuple(float(value) for value in detail.Position)
    if len(outline) != 4 or len(position) != 2:
        raise RuntimeError("integral-arbor head detail has invalid bounds")
    target = [
        position[axis]
        + DETAIL_CENTER[axis]
        - (outline[axis] + outline[axis + 2]) / 2.0
        for axis in range(2)
    ]
    if not detail.SetViewPosition(double_array(target), False):
        raise RuntimeError("failed to position integral-arbor head detail")
    draw.EditRebuild3()
    return detail


def _position_detail_label(adapter: Any, detail: Any) -> None:
    """Keep the native detail label clear of the parent shaft."""
    drawing = _early_bound(adapter.currentModel, "IDrawingDoc")
    sheet = _early_bound(drawing.GetCurrentSheet(), "ISheet")
    if not sheet.SetScale(*SHEET_SCALE, False, False):
        raise RuntimeError("failed to pin sheet scale before positioning detail label")
    notes = tuple(_read_member(detail, "GetNotes") or ())
    if len(notes) != 1:
        raise RuntimeError(f"expected one native detail label, found {len(notes)}")
    note = _early_bound(notes[0], "INote")
    annotation = _early_bound(_read_member(note, "GetAnnotation"), "IAnnotation")
    target = (*DETAIL_LABEL_XY, 0.0)
    if not annotation.SetPosition2(*target):
        raise RuntimeError("failed to position native detail label")
    adapter.currentModel.EditRebuild3()
    actual = tuple(float(value) for value in _read_member(annotation, "GetPosition"))
    if math.dist(actual, target) > 1e-8:
        raise RuntimeError(f"native detail label position did not persist: {actual}")


def _detail_diameter(
    adapter: Any,
    detail: Any,
    *,
    station_z_mm: float,
    diameter_mm: float,
    dimension_name: str,
    text_xy: tuple[float, float],
    label: str,
) -> Any:
    """Create and verify one native diametric size across detail silhouettes."""
    picks = [
        model_point_in_view(
            adapter,
            detail,
            (sign * diameter_mm / 2000.0, 0.0, station_z_mm / 1000.0),
            label=f"{label} silhouette {sign:+g}",
        )
        for sign in (-1.0, 1.0)
    ]
    display = add_edge_dimension(
        adapter,
        detail,
        p0=picks[0],
        p1=picks[1],
        text_xy=text_xy,
        label=label,
        orientation="vertical",
        entity_type="SILHOUETTE",
    )
    display = _early_bound(display, "IDisplayDimension")
    dimension = _early_bound(display.GetDimension2(0), "IDimension")
    measured_mm = abs(float(dimension.SystemValue)) * 1000.0
    if abs(measured_mm - diameter_mm) > 1e-5:
        raise RuntimeError(
            f"{label}: measured {measured_mm:g} mm, expected {diameter_mm:g} mm"
        )
    display.SetText(1, "<MOD-DIAM>")
    if str(display.GetText(1) or "") != "<MOD-DIAM>":
        raise RuntimeError(f"{label}: diameter prefix did not persist")
    places = DRAWING_REFERENCE_PRECISION[dimension_name]
    display.SetPrecision3(DRAWING_REFERENCE_PRECISION[dimension_name], -1, -1, -1)
    if int(display.GetPrimaryPrecision2()) != places:
        raise RuntimeError(
            f"{label}: spec-owned {places}-place precision did not persist"
        )
    annotation = display.GetAnnotation()
    if annotation is None:
        raise RuntimeError(f"{label}: dimension has no drawing annotation")
    return _early_bound(annotation, "IAnnotation")


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open pinion-arbor source", await adapter.open_model(str(SOURCE)))
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
            0: "Integral Pinion Arbor Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "integral arbor and grip head; match-reamed crossrod hole",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    donor = place_view(adapter, str(SOURCE), "*Front", 0.030, 0.180, scale=(2, 1))
    # Looking along model Y presents the match-reamed cross-hole as a true
    # circle while retaining the entire turned profile in one horizontal view.
    principal = place_view(
        adapter, str(SOURCE), "*Top", *PRINCIPAL_CENTER, scale=SHEET_SCALE
    )
    native_principal = _early_bound(principal, "IView")
    native_principal.Angle = -math.pi / 2.0
    if abs(math.remainder(float(native_principal.Angle) + math.pi / 2.0, 2.0 * math.pi)) > 1e-9:
        raise RuntimeError("failed to orient the integral arbor horizontally")
    drawing_model.EditRebuild3()
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=(1, 2))
    for view in (donor, principal, iso):
        set_hidden_lines_removed(adapter, view)

    detail = _head_detail(adapter, principal)
    set_hidden_lines_removed(adapter, detail)
    donor_annotations = curate_view_dimensions(
        adapter, donor, keep=DONOR_KEEP, view_label="diameter donor"
    )
    principal_annotations = curate_view_dimensions(
        adapter, principal, keep=PRINCIPAL_KEEP, view_label="integral-arbor profile"
    )
    detail_annotations = curate_view_dimensions(
        adapter, detail, keep=DETAIL_KEEP, view_label="integral-arbor head detail"
    )
    moved_diameters = [
        _move_dimension(
            adapter,
            annotation,
            principal,
            DIAMETER_POSITIONS["ShaftDia"],
            source_view=donor,
        )
        for annotation in donor_annotations
    ]
    donor_name = view_name(adapter, donor)
    delete_view(adapter, donor)
    if any(view_name(adapter, view) == donor_name for view in iter_views(adapter)):
        raise RuntimeError("failed to delete the empty diameter donor view")
    derived_diameters = [
        _detail_diameter(
            adapter,
            detail,
            station_z_mm=HEAD_CENTER_Z,
            diameter_mm=HEAD_DIA,
            dimension_name="HeadDia",
            text_xy=DIAMETER_POSITIONS["HeadDia"],
            label="detail head diameter",
        ),
        _detail_diameter(
            adapter,
            detail,
            station_z_mm=(HEAD_REAR_Z + NECK_END_Z) / 2.0,
            diameter_mm=NECK_DIA,
            dimension_name="NeckDia",
            text_xy=DIAMETER_POSITIONS["NeckDia"],
            label="detail neck diameter",
        ),
    ]
    annotations = [
        *moved_diameters,
        *derived_diameters,
        *principal_annotations,
        *detail_annotations,
    ]
    set_dimension_callouts(adapter, annotations, DIMENSION_CALLOUTS)
    assert_imported_precision(adapter, annotations, DRAWING_PRECISION_BY_NAME)
    set_reference_dimensions(adapter, annotations, {"CrossHoleDia"})
    for name, label in {
        "HeadCapSagDim": "front-crown height reference",
        "BackCapSagDim": "back-crown descriptive reference",
        "OverallLen": "overall length reference",
    }.items():
        matches = [
            annotation
            for annotation in annotations
            if dimension_name(adapter, annotation) == name
        ]
        if len(matches) != 1:
            raise RuntimeError(f"expected one {label}")
        set_reference_dimension(adapter, matches[0], label=label)

    if not auto_center_marks(adapter, detail, holes=True, size=0.0025):
        raise RuntimeError("failed to add center mark to the detailed grip cross-hole")
    add_view_centerline(
        adapter,
        principal,
        face_xy=(PRINCIPAL_CENTER[0], PRINCIPAL_CENTER[1] + 0.001),
        label="pinion arbor turning axis",
    )
    add_surface_finish(
        adapter,
        principal,
        edge_xy=(PRINCIPAL_CENTER[0] + 0.025, SHAFT_FLANK_Y),
        symbol_xy=(0.265, 0.205),
        control=surface_finish_by_key(SURFACE_FINISHES, "bearing"),
        label="arbor bearing finish",
        entity_type="SILHOUETTE",
        char_height=0.0025,
    )
    add_property_linked_note(adapter, "Manufacturing Notes", 0.020, 0.060)
    add_property_linked_note(adapter, "Isometric View Note", 0.335, 0.255)
    _position_detail_label(adapter, detail)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Integral Pinion Arbor Manufacturing Drawing",
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
