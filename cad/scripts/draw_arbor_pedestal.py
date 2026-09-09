r"""Create the curated machinist drawing for the cylinder-arbor pedestal."""

from __future__ import annotations

import argparse
import sys
from typing import Any, Literal


import _telemetry
from _common import CAD_ROOT, _early_bound, check, run_build
from _drawing_common import (
    DrawingOutputs,
    add_native_hole_callout,
    add_property_linked_note,
    add_surface_finish,
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
from _drawing_registry import DRAWINGS_BY_NAME
from _surface_finish import surface_finish_by_key
from arbor_pedestal_spec import (
    BORE_DIA,
    BORE_HEIGHT,
    FOOT_DEPTH,
    FOOT_HEIGHT,
    FOOT_WIDTH,
    SCREW_HOLE_DIA,
    STRAP_T,
    SURFACE_FINISHES,
    TOP_RADIUS,
)
from solidworks_mcp.adapters.solidworks.drawing import (
    auto_center_marks,
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
# front elevation on that midpoint. Third-angle: the 24x16 foot plan sits
# above the elevation, with the isometric to the right.
_PART_MID_Y = (
    BORE_HEIGHT + TOP_RADIUS
) / 2.0  # foot 0 .. dome top (bore + dome radius)
FRONT_CENTER = (0.100, 0.150)
TOP_CENTER = (0.100, 0.245)
ISO_CENTER = (0.335, 0.150)


def _front_y(model_y: float) -> float:
    """Sheet Y of a model-Y point in the front view (foot seat at model y=0)."""
    return FRONT_CENTER[1] + (model_y - _PART_MID_Y) * _S


# Front elevation carries the foot and flange, the 20 mm flank-end width,
# the fitted arbor bore, and a separate crown radius. The plan carries depth.
FRONT_KEEP = {
    "Width": (FRONT_CENTER[0], _front_y(0.0) + 0.032),
    "FootHt": (FRONT_CENTER[0] - 0.030, _front_y(FOOT_HEIGHT / 2.0)),
    "BoreDia": (FRONT_CENTER[0] + 0.068, _front_y(BORE_HEIGHT) - 0.004),
    "StrapTopWidth": (
        FRONT_CENTER[0],
        _front_y(BORE_HEIGHT + TOP_RADIUS) + 0.008,
    ),
}
TOP_KEEP = {
    "Depth": (TOP_CENTER[0] + 0.065, TOP_CENTER[1]),
}
DIMENSION_CALLOUTS = {
    "BoreDia": "REAM THRU",
}
# The 3/8 in journal establishes the nominal. The positive-only bore band is
# the finished running clearance, so the process note must not name a 3/8 reamer.
DIMENSION_PRECISION = {"BoreDia": 3}


@_telemetry.traced("drawing.arbor.front_entity_scan")
def _front_entities(adapter: Any, view: Any) -> tuple[Any, Any, Any, Any]:
    """Return the foot-seat, left-side, arbor-bore, and crown entities."""
    foot_candidates: list[tuple[float, Any]] = []
    side_candidates: list[tuple[float, Any]] = []
    bore_candidates: list[tuple[float, float, Any]] = []
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
        if (
            abs(p0[0] + FOOT_WIDTH / 2.0) <= 0.01
            and abs(p1[0] + FOOT_WIDTH / 2.0) <= 0.01
        ):
            side_candidates.append((abs(p1[1] - p0[1]), edge))
    if not foot_candidates:
        raise RuntimeError("front view has no model edge on the foot-seat plane")
    foot_span, foot_edge = max(foot_candidates, key=lambda item: item[0])
    if foot_span < FOOT_WIDTH - 0.1:
        raise RuntimeError(f"foot-seat edge span is only {foot_span:.3f} mm")
    if not side_candidates:
        raise RuntimeError("front view has no left foot-side edge")
    side_span, side_edge = max(side_candidates, key=lambda item: item[0])
    if side_span < FOOT_HEIGHT - 0.1:
        raise RuntimeError(f"left foot-side edge span is only {side_span:.3f} mm")
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
    return foot_edge, side_edge, bore_edge, dome_edge


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


@_telemetry.traced("drawing.arbor.bore_hidden_lines")
def _add_bore_hidden_lines(adapter: Any, view: Any) -> None:
    """Draw the bore's two derived hidden edges in the plan view."""
    draw = adapter.currentModel
    drawing = _early_bound(draw, "IDrawingDoc")
    if not drawing.ActivateView(view_name(adapter, view)):
        raise RuntimeError("failed to activate plan view for arbor bore hidden lines")
    sketch_manager = _early_bound(draw.SketchManager, "ISketchManager")
    # Once a drawing view is active, sketch coordinates are view-local model
    # meters rather than sheet coordinates.  Author the projected cylinder
    # generators from the same radius and strap depth stations as the part.
    bore_radius = BORE_DIA / 2.0 / 1000.0
    z0 = (FOOT_DEPTH / 2.0 - STRAP_T) / 1000.0
    z1 = FOOT_DEPTH / 2.0 / 1000.0
    for x in (-bore_radius, bore_radius):
        draw.ClearSelection2(True)
        segment = sketch_manager.CreateLine(x, z0, 0.0, x, z1, 0.0)
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
            "Material Specification",
            "Finish",
            "Quantity",
            "Manufacturing Notes",
        ),
        required=(
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
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
            0: "Cylinder-Arbor Pedestal Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "arbor pedestal; gray-iron casting; arbor clamp bore",
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
    set_dimension_precision(adapter, front_annotations, DIMENSION_PRECISION)
    for view, label in ((front, "front"), (top, "plan")):
        if not auto_center_marks(adapter, view, holes=True, size=0.0025):
            raise RuntimeError(f"failed to add ASME center marks to {label} view")
    _add_bore_hidden_lines(adapter, top)

    # Locate the bore from the left foot side and seat: one origin for both
    # coordinates, with ordinary dimensions governed by the title block.
    _bore_r = BORE_DIA / 2.0 * _S
    foot_entity, side_entity, bore_entity, dome_entity = _front_entities(adapter, front)
    _add_entity_dimension(
        adapter,
        front,
        side_entity,
        bore_entity,
        orientation="horizontal",
        position=(FRONT_CENTER[0], _front_y(BORE_HEIGHT + TOP_RADIUS) + 0.020),
        label="bore horizontal location",
        arc_endpoint="center",
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
    _add_radial_dimension(
        adapter,
        front,
        dome_entity,
        position=(0.150, _front_y(BORE_HEIGHT + TOP_RADIUS) + 0.002),
        label="crown radius",
    )
    finish = add_surface_finish(
        adapter,
        front,
        symbol_xy=(0.160, 0.125),
        control=surface_finish_by_key(SURFACE_FINISHES, "arbor_bore"),
        label="arbor bore finish",
        entity=bore_entity,
        leader_attach_xy=(FRONT_CENTER[0], _front_y(BORE_HEIGHT) - _bore_r),
    )
    finish_annotation = _early_bound(finish.GetAnnotation(), "IAnnotation")
    finish_text_format = finish_annotation.GetTextFormat(0)
    if finish_text_format is None:
        raise RuntimeError("arbor bore finish has no text format")
    finish_text_format.CharHeight = 0.003
    if not finish_annotation.SetTextFormat(0, False, finish_text_format):
        raise RuntimeError("failed to set arbor bore finish text height")
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
    _add_entity_dimension(
        adapter,
        top,
        far_face_entity,
        screw_entity,
        orientation="vertical",
        position=(0.060, TOP_CENTER[1]),
        label="hold-down hole depth location",
        arc_endpoint="center",
    )
    _add_entity_dimension(
        adapter,
        top,
        strap_near_entity,
        far_face_entity,
        orientation="vertical",
        position=(0.145, TOP_CENTER[1]),
        label="strap thickness",
    )
    _screw_r = SCREW_HOLE_DIA / 2.0 * _S
    add_native_hole_callout(
        adapter,
        top,
        edge_xy=(TOP_CENTER[0] + _screw_r, TOP_CENTER[1] + 0.010),
        callout_xy=(0.180, 0.260),
        label="flange hold-down hole",
        process="DRILL",
    )

    add_property_linked_note(
        adapter, "Manufacturing Notes", 0.020, 0.075, char_height=0.0025
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
