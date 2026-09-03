r"""Create the curated machinist drawing for the cylinder-arbor pedestal.

The print is deliberately plain (cad/docs/drawing-simplicity-policy.md): a
small bearing casting carries no datums, no feature-control frames and no
basic dimensions -- the title block's general tolerances govern everything
except the arbor bore, whose running-fit band rides the model dimension
and which, as the one surface a shaft turns in, keeps its roughness symbol.
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

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
    SCREW_CLEARANCE_DIA,
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

SHEET_SCALE = (2.0, 1.0)  # 64 mm tall casting -- 2:1 keeps the strap/bore legible
_S = SHEET_SCALE[0] / 1000.0  # sheet meters per model mm

# The casting spans model y 0 (foot seat) .. 64 (dome top); centre the front
# elevation on that midpoint. Third-angle: the 24x16 foot plan sits ABOVE the
# elevation, the isometric off to the right.
_PART_MID_Y = (
    BORE_HEIGHT + TOP_RADIUS
) / 2.0  # foot 0 .. dome top (bore + dome radius)
FRONT_CENTER = (0.100, 0.150)
TOP_CENTER = (0.100, 0.245)
ISO_CENTER = (0.335, 0.150)


def _front_y(model_y: float) -> float:
    """Sheet Y of a model-Y point in the front view (foot seat at model y=0)."""
    return FRONT_CENTER[1] + (model_y - _PART_MID_Y) * _S


def _top_y(model_z: float) -> float:
    """Sheet Y of a model-Z station in the plan (+Z is DOWN in a Top view)."""
    return TOP_CENTER[1] - model_z * _S


# Front elevation: the foot width BELOW the seat (so it terminates on the foot,
# not across the strap flanks), the bore station and diameter, the dome
# diameter (the strap flanks run up to its equator), and the flange height.
# Plan: the 16 foot depth and the strap thickness against the flush rear face.
FRONT_KEEP = {
    "Width": (FRONT_CENTER[0], _front_y(0.0) - 0.020),
    "FootHt": (FRONT_CENTER[0] - 0.030, _front_y(FOOT_HEIGHT / 2.0)),
    "BoreDia": (FRONT_CENTER[0] + 0.068, _front_y(BORE_HEIGHT) - 0.004),
    "DomeDia": (FRONT_CENTER[0] + 0.066, _front_y(BORE_HEIGHT) - 0.020),
}
TOP_KEEP = {
    "Depth": (TOP_CENTER[0] + 0.052, TOP_CENTER[1]),
}
DIMENSION_CALLOUTS = {
    "BoreDia": "BORE THRU",
    # The tapered strap sides are defined by the 24 foot width and this head:
    # they meet its circle at the bore height.
    "DomeDia": "STRAP SIDES RUN TO IT",
}
# The arbor bore is the one fitted feature (running-fit band on the model
# dimension): three decimals say "hold it"; everything else stays at the
# two-place block tolerance.
DIMENSION_PRECISION = {"BoreDia": 3}
# Left of the elevation, outside the bore height (0.060) and flange height
# (0.070) chain: the overall as a REFERENCE.
OVERALL_TEXT_X = 0.048
BORE_HEIGHT_TEXT_X = 0.060
# Below the foot seat, nested inside the foot width: the bore's offset from
# the left foot side (the second DRO coordinate).
BORE_OFFSET_TEXT_Y = _front_y(0.0) - 0.010
# Strap thickness (rear face flush with the foot): right of the plan, inside
# the foot-depth dimension.
STRAP_TEXT_XY = (TOP_CENTER[0] + 0.036, (_top_y(FOOT_DEPTH / 2.0 - STRAP_T) + _top_y(FOOT_DEPTH / 2.0)) / 2.0)
# Roughness symbol below-right of the bore, its leader to the bore's bottom
# so it passes under the head-diameter leader.
FINISH_SYMBOL_XY = (0.150, 0.140)
NOTES_XY = (0.020, 0.066)


@_telemetry.traced("drawing.front_entity_scan")
def _front_entities(adapter: Any, view: Any) -> tuple[Any, Any, Any]:
    """Return the foot-seat edge, the left foot-side edge and the bore circle.

    The bore location dimensions run from the first two to the third, so
    every one of them is entity-selected rather than sheet-picked.
    """
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
    if foot_span < 23.9:
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
    return foot_edge, side_edge, bore_edge


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
    if not candidates or min(candidates, key=lambda item: item[0])[0] > 0.01:
        raise RuntimeError(f"{label} has no circle of radius {radius_mm:.3f} mm")
    return min(candidates, key=lambda item: item[0])[1]


@_telemetry.traced("drawing.entity_dimension", label_param="label")
def _add_entity_dimension(
    adapter: Any,
    view: Any,
    base_entity: Any,
    target_entity: Any,
    *,
    orientation: str,
    position: tuple[float, float],
    label: str,
    arc: str | None = "center",
) -> Any:
    """Entity-selected dimension between two view entities.

    ``arc`` re-anchors a circular target: ``"center"`` for a hole location,
    ``"max"`` for an overall to an arc's far tangent, ``None`` for two
    straight edges.
    """
    draw = adapter.currentModel
    drawing = _early_bound(draw, "IDrawingDoc")
    if not drawing.ActivateView(view_name(adapter, view)):
        raise RuntimeError(f"failed to activate view for {label}")
    draw.ClearSelection2(True)
    selection_manager = _early_bound(draw.SelectionManager, "ISelectionMgr")
    for append, raw_entity in ((False, base_entity), (True, target_entity)):
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
        raise ValueError(f"unsupported dimension orientation: {orientation}")
    draw.ClearSelection2(True)
    if display is None:
        raise RuntimeError(f"failed to create {label} dimension")
    if arc == "center":
        set_arc_endpoints_to_center(adapter, display, label=label)
    elif arc == "max":
        set_arc_endpoints_to_max(adapter, display, label=label)
    elif arc is not None:
        raise ValueError(f"unsupported arc condition: {arc}")
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
        adapter, property_view=PART_STEM, scale=SHEET_SCALE
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
    # The hold-down hole sits behind the upright in this pictorial direction;
    # HLV keeps that manufactured feature visible instead of contradicting plan.
    set_hidden_lines_visible(adapter, iso)
    # The elevation carries the arbor bore as a hidden circle and the flange
    # hold-down hole; the plan shows the foot with the bore + screw crossing it.
    # Hidden lines stay ON in every orthographic view (policy rule 7).
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
    if not auto_center_marks(adapter, top, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center mark to the plan view")

    # Bore axis from the left foot side and the foot seat: the two coordinates
    # a machinist sets the DRO to (one origin per view).  The offset sits
    # under the foot, nested inside the foot width, so neither dimension
    # runs across the strap flanks.
    _bore_r = BORE_DIA / 2.0 * _S
    foot_entity, side_entity, bore_entity = _front_entities(adapter, front)
    _add_entity_dimension(
        adapter,
        front,
        side_entity,
        bore_entity,
        orientation="horizontal",
        position=(FRONT_CENTER[0], BORE_OFFSET_TEXT_Y),
        label="bore horizontal location",
    )
    _add_entity_dimension(
        adapter,
        front,
        foot_entity,
        bore_entity,
        orientation="vertical",
        position=(BORE_HEIGHT_TEXT_X, FRONT_CENTER[1]),
        label="bore vertical location",
    )
    # Overall height, foot seat to the dome's crown, as a REFERENCE beside
    # the controlling bore height: outermost on the left.
    dome_entity = _circle_entity(adapter, front, TOP_RADIUS, label="dome circle")
    overall = _add_entity_dimension(
        adapter,
        front,
        foot_entity,
        dome_entity,
        orientation="vertical",
        position=(OVERALL_TEXT_X, FRONT_CENTER[1]),
        label="overall height",
        arc="max",
    )
    # Add*Dimension2 hands back the IDisplayDimension (late-bound); bind it
    # before reading the IAnnotation the reference helper wants.
    set_reference_dimension(
        adapter,
        _early_bound(overall, "IDisplayDimension").GetAnnotation(),
        label="overall height",
    )
    add_surface_finish(
        adapter,
        front,
        symbol_xy=FINISH_SYMBOL_XY,
        control=surface_finish_by_key(SURFACE_FINISHES, "arbor_bore"),
        label="arbor bore finish",
        entity=bore_entity,
        leader_attach_xy=(FRONT_CENTER[0], _front_y(BORE_HEIGHT) - _bore_r),
    )
    screw_entity = _circle_entity(
        adapter,
        top,
        SCREW_CLEARANCE_DIA / 2.0,
        label="flange hold-down hole",
    )
    near_foot_entity = _top_depth_edge(
        adapter, top, -FOOT_DEPTH / 2.0, label="near foot edge"
    )
    # Hold-down hole from the near foot edge; its across-foot coordinate is
    # the bore's own (the views are projection-aligned, so a second 12.00
    # would print directly over the front view's).
    _add_entity_dimension(
        adapter,
        top,
        near_foot_entity,
        screw_entity,
        orientation="vertical",
        position=(0.060, TOP_CENTER[1]),
        label="flange-hole location from near foot edge",
    )
    # Upright (strap) thickness: its near face to the foot's rear edge, which
    # the strap's rear face is flush with.
    strap_face_entity = _top_depth_edge(
        adapter, top, FOOT_DEPTH / 2.0 - STRAP_T, label="strap near face"
    )
    rear_foot_entity = _top_depth_edge(
        adapter, top, FOOT_DEPTH / 2.0, label="rear foot edge"
    )
    _add_entity_dimension(
        adapter,
        top,
        rear_foot_entity,
        strap_face_entity,
        orientation="vertical",
        position=STRAP_TEXT_XY,
        label="strap thickness",
        arc=None,
    )
    _screw_r = SCREW_CLEARANCE_DIA / 2.0 * _S
    add_native_hole_callout(
        adapter,
        top,
        edge_xy=(TOP_CENTER[0] + _screw_r, TOP_CENTER[1] + 0.010),
        callout_xy=(0.180, 0.260),
        label="flange hold-down hole",
        # #4 normal clearance (3.264 = 0.1285 in) is exactly the #30 drill.
        process="#30 DRILL",
    )
    add_property_linked_note(adapter, "Manufacturing Notes", *NOTES_XY)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Cylinder-Arbor Pedestal Manufacturing Drawing",
        scale=SHEET_SCALE,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[PART_STEM])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
