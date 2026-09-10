r"""Create the curated machinist drawing for the cylinder-arbor pedestal."""

from __future__ import annotations

import argparse
import sys
from typing import Any, Literal


import _telemetry
from _common import CAD_ROOT, _early_bound, check, run_build
from _drawing_common import (
    DrawingOutputs,
    add_attached_note,
    add_surface_finish,
    add_native_hole_callout,
    curate_view_dimensions,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    set_arc_endpoints_to_center,
    set_arc_endpoints_to_max,
    set_dimension_callouts,
    set_dimension_precision,
    set_hidden_lines_removed,
    set_hidden_lines_visible,
    set_reference_dimension,
    stamp_drawing_summary,
    visible_view_entities,
)
from _surface_finish import surface_finish_by_key
from _drawing_registry import DRAWINGS_BY_NAME
from arbor_pedestal_spec import (
    BORE_DIA,
    BORE_HEIGHT,
    FOOT_DEPTH,
    FOOT_HEIGHT,
    FOOT_WIDTH,
    SCREW_HOLE_DIA,
    STRAP_T,
    TAPER_ANGLE_DEG,
    TAPER_TANGENT_X,
    TAPER_TANGENT_Y,
    SURFACE_FINISHES,
    TOP_RADIUS,
)
from solidworks_mcp.adapters.solidworks.drawing import (
    auto_center_marks,
    dimension_name,
    place_view,
    view_name,
)


SPEC = DRAWINGS_BY_NAME["arbor_pedestal"]
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

SHEET_SCALE = (2.0, 1.0)  # 49.718 mm tall; 2:1 keeps the strap and bore legible
_S = SHEET_SCALE[0] / 1000.0  # sheet meters per model mm

# The casting spans model y 0 (foot seat) to 49.718 (dome top); centre the
# front elevation on that midpoint. Third-angle projection keeps the plan
# aligned above the elevation; the isometric balances the aligned view group
# from the right.
_PART_MID_Y = (
    BORE_HEIGHT + TOP_RADIUS
) / 2.0  # foot 0 .. dome top (bore + dome radius)
FRONT_CENTER = (0.135, 0.125)
TOP_CENTER = (FRONT_CENTER[0], 0.215)
ISO_CENTER = (0.335, 0.140)


def _front_y(model_y: float) -> float:
    """Sheet Y of a model-Y point in the front view (foot seat at model y=0)."""
    return FRONT_CENTER[1] + (model_y - _PART_MID_Y) * _S


# Front elevation carries the foot, fitted arbor bore, bore height, and the
# tangent concentric crown. The plan carries depth and foot-hole placement.
FRONT_KEEP = {
    "Width": (FRONT_CENTER[0], _front_y(0.0) - 0.006),
    "FootHt": (FRONT_CENTER[0] - 0.030, _front_y(FOOT_HEIGHT / 2.0)),
    "BoreDia": (FRONT_CENTER[0] + 0.050, _front_y(BORE_HEIGHT) - 0.004),
}
TOP_KEEP = {
    "Depth": (TOP_CENTER[0] - 0.070, TOP_CENTER[1] - 0.010),
}
DIMENSION_CALLOUTS = {
    "BoreDia": "REAM THRU; ON PART C/L",
}
DIMENSION_PRECISION = {
    "Width": 1,
    "Depth": 1,
    "FootHt": 1,
    "BoreDia": 2,
}


@_telemetry.traced("drawing.arbor.front_entity_scan")
def _front_entities(adapter: Any, view: Any) -> tuple[Any, Any, Any, Any]:
    """Return the foot-seat, arbor-bore, crown, and taper entities."""
    foot_candidates: list[tuple[float, Any]] = []
    bore_candidates: list[tuple[float, float, Any]] = []
    taper_candidates: list[tuple[float, Any]] = []
    for raw_edge in visible_view_entities(view, 1, label="pedestal front edges"):
        edge = _early_bound(raw_edge, "IEdge")
        curve = edge.GetCurve()
        if curve is not None:
            curve = _early_bound(curve, "ICurve")
            if curve.IsCircle():
                params = tuple(float(value) * 1000.0 for value in curve.CircleParams)
                bore_candidates.append((params[6], params[1], edge))
        start = edge.GetStartVertex()
        end = edge.GetEndVertex()
        if start is None or end is None:
            continue
        start = _early_bound(start, "IVertex")
        end = _early_bound(end, "IVertex")
        p0 = tuple(float(value) * 1000.0 for value in start.GetPoint())
        p1 = tuple(float(value) * 1000.0 for value in end.GetPoint())
        if abs(p0[1]) <= 0.01 and abs(p1[1]) <= 0.01:
            foot_candidates.append((abs(p1[0] - p0[0]), edge))
        endpoints = sorted(
            ((abs(p0[0]), p0[1]), (abs(p1[0]), p1[1])), key=lambda p: p[1]
        )
        root, tangent = endpoints
        taper_error = (
            abs(root[0] - FOOT_WIDTH / 2.0)
            + abs(root[1] - FOOT_HEIGHT)
            + abs(tangent[0] - TAPER_TANGENT_X)
            + abs(tangent[1] - TAPER_TANGENT_Y)
        )
        if taper_error <= 0.05:
            taper_candidates.append((taper_error, edge))
    if not foot_candidates:
        raise RuntimeError("front view has no model edge on the foot-seat plane")
    foot_span, foot_edge = max(foot_candidates, key=lambda item: item[0])
    if foot_span < FOOT_WIDTH - 0.1:
        raise RuntimeError(f"foot-seat edge span is only {foot_span:.3f} mm")
    if not bore_candidates:
        raise RuntimeError("front view has no circular model edges")
    radius, height, bore_edge = min(
        bore_candidates,
        key=lambda item: abs(item[0] - BORE_DIA / 2.0) + abs(item[1] - BORE_HEIGHT),
    )
    if abs(radius - BORE_DIA / 2.0) > 0.01 or abs(height - BORE_HEIGHT) > 0.01:
        raise RuntimeError(
            f"no circular edge matches arbor bore at {BORE_HEIGHT:.3f} mm"
        )
    dome_radius, dome_height, dome_edge = min(
        bore_candidates,
        key=lambda item: abs(item[0] - TOP_RADIUS) + abs(item[1] - BORE_HEIGHT),
    )
    if abs(dome_radius - TOP_RADIUS) > 0.01 or abs(dome_height - BORE_HEIGHT) > 0.01:
        raise RuntimeError("front view has no circular dome edge")
    if not taper_candidates:
        raise RuntimeError("front view has no edge matching the tangent side taper")
    taper_edge = min(taper_candidates, key=lambda item: item[0])[1]
    return foot_edge, bore_edge, dome_edge, taper_edge


def _top_depth_edge(adapter: Any, view: Any, z_mm: float, *, label: str) -> Any:
    """Return a plan-view edge at one modeled depth station."""
    candidates: list[tuple[float, Any]] = []
    for raw_edge in visible_view_entities(view, 1, label=f"{label} plan edges"):
        edge = _early_bound(raw_edge, "IEdge")
        start = edge.GetStartVertex()
        end = edge.GetEndVertex()
        if start is None or end is None:
            continue
        start = _early_bound(start, "IVertex")
        end = _early_bound(end, "IVertex")
        p0 = tuple(float(value) * 1000.0 for value in start.GetPoint())
        p1 = tuple(float(value) * 1000.0 for value in end.GetPoint())
        if abs(p0[2] - z_mm) <= 0.01 and abs(p1[2] - z_mm) <= 0.01:
            candidates.append((abs(p1[0] - p0[0]), edge))
    if not candidates:
        raise RuntimeError(f"plan view has no {label} edge at z={z_mm:.3f} mm")
    return max(candidates, key=lambda item: item[0])[1]


def _circle_entity(adapter: Any, view: Any, radius_mm: float, *, label: str) -> Any:
    candidates: list[tuple[float, Any]] = []
    for raw_edge in visible_view_entities(view, 1, label=f"{label} circles"):
        edge = _early_bound(raw_edge, "IEdge")
        curve = edge.GetCurve()
        if curve is None:
            continue
        curve = _early_bound(curve, "ICurve")
        if not curve.IsCircle():
            continue
        radius = float(curve.CircleParams[6]) * 1000.0
        candidates.append((abs(radius - radius_mm), edge))
    if not candidates or candidates[0][0] > 0.01:
        candidates.sort(key=lambda item: item[0])
    if not candidates or min(candidates, key=lambda item: item[0])[0] > 0.01:
        raise RuntimeError(f"{label} has no circle of radius {radius_mm:.3f} mm")
    return min(candidates, key=lambda item: item[0])[1]


@_telemetry.traced("drawing.radial_dimension", label_param="label")
def _add_radial_dimension(
    adapter: Any,
    view: Any,
    entity: Any,
    *,
    position: tuple[float, float],
    label: str,
) -> Any:
    draw = adapter.currentModel
    drawing = _early_bound(draw, "IDrawingDoc")
    if not drawing.ActivateView(view_name(adapter, view)):
        raise RuntimeError(f"failed to activate view for {label}")
    draw.ClearSelection2(True)
    selection_manager = _early_bound(draw.SelectionManager, "ISelectionMgr")
    selection_data = selection_manager.CreateSelectData()
    selection_data.View = view
    if not _early_bound(entity, "IEntity").Select4(False, selection_data):
        raise RuntimeError(f"failed to select {label} entity")
    display = draw.AddRadialDimension2(*position, 0.0)
    draw.ClearSelection2(True)
    if display is None:
        raise RuntimeError(f"failed to create {label} radial dimension")
    draw.EditRebuild3()
    return display


@_telemetry.traced("drawing.diameter_second_arrow", label_param="label")
def _disable_diameter_second_arrow(
    adapter: Any,
    annotations: list[Any],
    *,
    dimension: str,
    label: str,
) -> None:
    """Remove a diameter dimension's optional arrow across the far side."""
    for raw_annotation in annotations:
        annotation = _early_bound(raw_annotation, "IAnnotation")
        if dimension_name(adapter, annotation) != dimension:
            continue
        display = annotation.GetSpecificAnnotation()
        if display is None:
            raise RuntimeError(f"dimension {dimension!r} has no display annotation")
        display = _early_bound(display, "IDisplayDimension")
        display.SetSecondArrow(False, False)
        if bool(display.GetUseDocSecondArrow()) or bool(display.GetSecondArrow()):
            raise RuntimeError(f"failed to disable {label} far-side arrow")
        adapter.currentModel.GraphicsRedraw2()
        return
    raise RuntimeError(f"dimension {dimension!r} not found for {label}")


@_telemetry.traced("drawing.arbor.bore_hidden_lines")
def _add_bore_hidden_lines(adapter: Any, view: Any) -> None:
    """Draw the bore's two derived hidden edges in the plan view."""
    draw = adapter.currentModel
    drawing = _early_bound(draw, "IDrawingDoc")
    if not drawing.ActivateView(view_name(adapter, view)):
        raise RuntimeError("failed to activate plan view for arbor bore hidden lines")
    sketch_manager = _early_bound(draw.SketchManager, "ISketchManager")
    # Once a drawing view is active, sketch coordinates are view-local model
    # metres. The Top view's local vertical axis is -model-Z, so reflect the
    # upright's modeled -2..+8 mm span into view-local -8..+2 mm.
    bore_radius = BORE_DIA / 2.0 / 1000.0
    z0 = -(FOOT_DEPTH / 2.0) / 1000.0
    z1 = -(FOOT_DEPTH / 2.0 - STRAP_T) / 1000.0
    midpoint = (z0 + z1) / 2.0
    # Start one hidden segment at each physical face. The dash pattern then
    # visibly reaches both boundaries instead of leaving an apparent short stop.
    for x in (-bore_radius, bore_radius):
        for start_z, end_z in ((z0, midpoint), (z1, midpoint)):
            draw.ClearSelection2(True)
            segment = sketch_manager.CreateLine(x, start_z, 0.0, x, end_z, 0.0)
            if segment is None:
                raise RuntimeError("failed to create an arbor bore hidden line")
            segment = _early_bound(segment, "ISketchSegment")
            segment.Style = 1  # swLineHIDDEN
            if int(segment.Style) != 1:
                raise RuntimeError("arbor bore line did not retain hidden line style")
    draw.ClearSelection2(True)
    draw.EditRebuild3()


@_telemetry.traced("drawing.entity_dimension", label_param="label")
def _add_entity_dimension(
    adapter: Any,
    view: Any,
    entity0: Any,
    entity1: Any,
    *,
    orientation: str,
    position: tuple[float, float],
    label: str,
    arc_endpoint: Literal["center", "max"] | None = None,
) -> Any:
    draw = adapter.currentModel
    drawing = _early_bound(draw, "IDrawingDoc")
    if not drawing.ActivateView(view_name(adapter, view)):
        raise RuntimeError(f"failed to activate view for {label}")
    draw.ClearSelection2(True)
    selection_manager = _early_bound(draw.SelectionManager, "ISelectionMgr")
    for append, raw_entity in ((False, entity0), (True, entity1)):
        selection_data = selection_manager.CreateSelectData()
        selection_data.View = view
        entity = _early_bound(raw_entity, "IEntity")
        if not entity.Select4(append, selection_data):
            raise RuntimeError(f"failed to select {label} entity")
    if orientation == "horizontal":
        display = draw.AddHorizontalDimension2(*position, 0.0)
    elif orientation == "vertical":
        display = draw.AddVerticalDimension2(*position, 0.0)
    else:
        raise ValueError(f"unsupported entity-dimension orientation: {orientation}")
    draw.ClearSelection2(True)
    if display is None:
        raise RuntimeError(f"failed to create {label} dimension")
    if arc_endpoint == "center":
        set_arc_endpoints_to_center(adapter, display, label=label)
    elif arc_endpoint == "max":
        set_arc_endpoints_to_max(adapter, display, label=label)
    elif arc_endpoint is not None:
        raise ValueError(f"unsupported arc endpoint: {arc_endpoint}")
    return display


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open arbor-pedestal source", await adapter.open_model(str(SOURCE)))
    read_required_properties(
        adapter.currentModel,
        (
            "Number",
            "Revision",
            "Title",
            "Material",
            "Material Specification",
            "Finish",
            "Quantity",
        ),
        required=(
            "Number",
            "Material",
            "Material Specification",
            "Finish",
            "Quantity",
        ),
    )
    drawing_model, _sheet = new_project_drawing(
        adapter, property_view=PART_STEM, scale=SHEET_SCALE, layout=SPEC.layout
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Cylinder-Arbor Pedestal Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "arbor pedestal; ferrous stock or casting; arbor clamp bore",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=(2, 1))
    top = place_view(adapter, str(SOURCE), "*Top", *TOP_CENTER, scale=(2, 1))
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=(2, 1))
    set_hidden_lines_removed(adapter, iso)
    # The elevation carries the arbor bore and flange hold-down hole; the plan
    # carries derived hidden lines for the through-bore plus the screw opening.
    for view in (front, top):
        set_hidden_lines_visible(adapter, view)

    front_annotations = curate_view_dimensions(
        adapter, front, keep=FRONT_KEEP, view_label="front"
    )
    top_annotations = curate_view_dimensions(
        adapter, top, keep=TOP_KEEP, view_label="top"
    )
    set_dimension_callouts(
        adapter, [*front_annotations, *top_annotations], DIMENSION_CALLOUTS
    )
    for view, label in ((front, "front"), (top, "plan")):
        view.SetDisplayTangentEdges2(0)
        if int(view.GetDisplayTangentEdges2()) != 0:
            raise RuntimeError(f"failed to hide {label}-view tangent edges")
        view.UpdateViewDisplayGeometry()
    set_dimension_precision(
        adapter, [*front_annotations, *top_annotations], DIMENSION_PRECISION
    )
    _disable_diameter_second_arrow(
        adapter,
        front_annotations,
        dimension="BoreDia",
        label="arbor bore",
    )
    for view, label in ((front, "front"), (top, "plan")):
        if not auto_center_marks(adapter, view, holes=True, size=0.0025):
            raise RuntimeError(f"failed to add ASME center marks to {label} view")
    _add_bore_hidden_lines(adapter, top)

    # Bore and foot hole are explicitly placed on the part centreline. This
    # avoids a long half-width witness line that visually merges with the taper.
    foot_entity, bore_entity, dome_entity, taper_entity = _front_entities(
        adapter, front
    )
    add_surface_finish(
        adapter,
        front,
        symbol_xy=(0.095, _front_y(BORE_HEIGHT) + 0.024),
        control=surface_finish_by_key(SURFACE_FINISHES, "arbor_bore"),
        label="arbor bore finish",
        entity=bore_entity,
    )
    # Right of the 24.0 width dimension (which ends at the foot's right
    # corner, x ~0.159) and level with it; the leader is pinned to the seat's
    # right quarter so it leaves the vee's LEFT side and runs up-left, clear
    # of the "Ra 3.2" text that hangs right of the anchor.
    add_surface_finish(
        adapter,
        front,
        symbol_xy=(FRONT_CENTER[0] + 0.036, _front_y(0.0) - 0.016),
        control=surface_finish_by_key(SURFACE_FINISHES, "foot_seat"),
        label="foot seat finish",
        entity=foot_entity,
        leader_attach_xy=(FRONT_CENTER[0] + FOOT_WIDTH * _S / 4.0, _front_y(0.0)),
    )
    _add_entity_dimension(
        adapter,
        front,
        foot_entity,
        bore_entity,
        orientation="vertical",
        position=(0.060, FRONT_CENTER[1]),
        label="bore height from foot seat",
        arc_endpoint="center",
    )
    overall = _add_entity_dimension(
        adapter,
        front,
        foot_entity,
        dome_entity,
        orientation="vertical",
        position=(0.035, FRONT_CENTER[1]),
        label="overall height reference",
        arc_endpoint="max",
    )
    set_reference_dimension(
        adapter,
        _early_bound(overall, "IDisplayDimension").GetAnnotation(),
        label="overall height reference",
    )
    radius_dimension = _add_radial_dimension(
        adapter,
        front,
        dome_entity,
        position=(0.195, _front_y(BORE_HEIGHT + TOP_RADIUS) + 0.005),
        label="crown radius",
    )
    radius_display = _early_bound(radius_dimension, "IDisplayDimension")
    radius_display.SetText(4, "TANGENT; CONC W/ BORE")
    radius_display.SetPrecision3(1, -1, -1, -1)
    # The leader runs from the text toward the crown centre; with the default
    # "extend to the opposite side" it kept going through the bore and crossed
    # the Ø9.55 dimension at the centre. Stop it at the crown arc.
    radius_display.ArcExtensionLineOrOppositeSide = False
    if (
        str(radius_display.GetText(4) or "") != "TANGENT; CONC W/ BORE"
        or int(radius_display.GetPrimaryPrecision2()) != 1
        or bool(radius_display.ArcExtensionLineOrOppositeSide)
    ):
        raise RuntimeError("crown radius annotation did not persist")
    adapter.currentModel.GraphicsRedraw2()
    add_attached_note(
        adapter,
        front,
        text=(
            f"UPRIGHT ROOT = {FOOT_WIDTH:.1f}; "
            f"TAPER {TAPER_ANGLE_DEG:.2f}<MOD-DEG>/SIDE (REF)"
        ),
        entity=taper_entity,
        note_xy=(0.200, _front_y(23.0)),
        label="side-taper reference angle",
    )
    screw_entity = _circle_entity(
        adapter,
        top,
        SCREW_HOLE_DIA / 2.0,
        label="flange hold-down hole",
    )
    strap_near_entity = _top_depth_edge(
        adapter,
        top,
        FOOT_DEPTH / 2.0 - STRAP_T,
        label="strap near-face",
    )
    far_face_entity = _top_depth_edge(
        adapter, top, FOOT_DEPTH / 2.0, label="foot and strap far-face"
    )
    hold_down_dimension = _add_entity_dimension(
        adapter,
        top,
        far_face_entity,
        screw_entity,
        orientation="vertical",
        position=(TOP_CENTER[0] - 0.045, TOP_CENTER[1]),
        label="hold-down hole depth location",
        arc_endpoint="center",
    )
    upright_dimension = _add_entity_dimension(
        adapter,
        top,
        strap_near_entity,
        far_face_entity,
        orientation="vertical",
        position=(TOP_CENTER[0] + 0.045, TOP_CENTER[1] + 0.010),
        label="upright depth",
    )
    for raw_dimension, label in (
        (hold_down_dimension, "hold-down hole depth location"),
        (upright_dimension, "upright depth"),
    ):
        display = _early_bound(raw_dimension, "IDisplayDimension")
        display.SetPrecision3(1, -1, -1, -1)
        if int(display.GetPrimaryPrecision2()) != 1:
            raise RuntimeError(f"{label} precision did not persist")
        if label == "upright depth":
            display.SetText(4, "UPRIGHT DEPTH")
            if str(display.GetText(4) or "") != "UPRIGHT DEPTH":
                raise RuntimeError("upright-depth callout did not persist")
    _screw_r = SCREW_HOLE_DIA / 2.0 * _S
    add_native_hole_callout(
        adapter,
        top,
        edge_xy=(TOP_CENTER[0] + _screw_r, TOP_CENTER[1] + 0.010),
        callout_xy=(TOP_CENTER[0] + 0.035, TOP_CENTER[1] + 0.035),
        label="flange hold-down hole",
        process="FOOT-FLANGE HOLE ON PART C/L: DRILL",
    )
    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Cylinder-Arbor Pedestal Manufacturing Drawing",
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
