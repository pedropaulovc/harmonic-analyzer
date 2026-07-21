r"""Create the curated machinist drawing for the cylinder-arbor pedestal."""

from __future__ import annotations

import argparse
import sys
from typing import Any

import _telemetry
from _common import CAD_ROOT, _early_bound, check, run_build
from _drawing_common import (
    DrawingOutputs,
    add_attached_note,
    add_datum_feature,
    add_feature_control_frame,
    add_native_hole_callout,
    add_property_linked_note,
    add_surface_finish,
    curate_view_dimensions,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    set_basic_dimension,
    set_dimension_callouts,
    set_dimension_precision,
    set_hidden_lines_removed,
    set_hidden_lines_visible,
    stamp_drawing_summary,
)
from _drawing_registry import DRAWINGS_BY_NAME
from arbor_pedestal_spec import (
    BORE_DIA,
    BORE_HEIGHT,
    FOOT_HEIGHT,
    FOOT_WIDTH,
    SCREW_CLEARANCE_DIA,
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
_PART_MID_Y = (BORE_HEIGHT + 10.0) / 2.0  # foot 0 .. dome top (bore + dome radius)
FRONT_CENTER = (0.100, 0.145)
TOP_CENTER = (0.100, 0.245)
ISO_CENTER = (0.335, 0.150)


def _front_y(model_y: float) -> float:
    """Sheet Y of a model-Y point in the front view (foot seat at model y=0)."""
    return FRONT_CENTER[1] + (model_y - _PART_MID_Y) * _S


# Front elevation carries the foot width + flange height, the arbor-bore station
# and diameter, and the dome diameter; the plan carries the 16 foot depth.
FRONT_KEEP = {
    "Width": (FRONT_CENTER[0], _front_y(0.0) - 0.014),
    "FootHt": (FRONT_CENTER[0] - 0.030, _front_y(FOOT_HEIGHT / 2.0)),
    "BoreDia": (FRONT_CENTER[0] + 0.068, _front_y(BORE_HEIGHT) - 0.004),
    "DomeDia": (FRONT_CENTER[0] + 0.066, _front_y(BORE_HEIGHT + 9.0)),
}
TOP_KEEP = {
    "Depth": (TOP_CENTER[0] + 0.040, TOP_CENTER[1]),
}
DIMENSION_CALLOUTS = {
    "BoreDia": "+0.055/+0.025 THRU",
    "DomeDia": "+/-0.10",
}
# 3/8 in = 9.525 exactly; show 3 places so the view matches the note (else the
# 2-decimal sheet default prints 9.53 against the DIA 9.525 the note cites).
DIMENSION_PRECISION = {"BoreDia": 3}


def _front_entities(adapter: Any, view: Any) -> tuple[Any, Any, Any, Any, Any]:
    """Return foot, side, left flank, bore, and dome front entities."""
    drawing_view = _early_bound(view, "IView")
    foot_candidates: list[tuple[float, Any]] = []
    side_candidates: list[tuple[float, Any]] = []
    flank_candidates: list[tuple[float, Any]] = []
    bore_candidates: list[tuple[float, float, Any]] = []
    for component in drawing_view.GetVisibleComponents() or []:
        for raw_edge in drawing_view.GetVisibleEntities2(component, 1) or []:
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
            start = _early_bound(start, "IVertex", "GetPoint")
            end = _early_bound(end, "IVertex", "GetPoint")
            p0 = tuple(float(value) * 1000.0 for value in start.GetPoint())
            p1 = tuple(float(value) * 1000.0 for value in end.GetPoint())
            if abs(p0[1]) <= 0.01 and abs(p1[1]) <= 0.01:
                foot_candidates.append((abs(p1[0] - p0[0]), edge))
            if (
                abs(p0[0] + FOOT_WIDTH / 2.0) <= 0.01
                and abs(p1[0] + FOOT_WIDTH / 2.0) <= 0.01
            ):
                side_candidates.append((abs(p1[1] - p0[1]), edge))
            ys = sorted((p0[1], p1[1]))
            if (
                abs(ys[0]) <= 0.01
                and abs(ys[1] - BORE_HEIGHT) <= 0.01
                and max(p0[0], p1[0]) < 0.0
            ):
                flank_candidates.append((abs(p1[1] - p0[1]), edge))
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
    if not flank_candidates:
        raise RuntimeError("front view has no left taper-flank edge")
    flank_span, flank_edge = max(flank_candidates, key=lambda item: item[0])
    if flank_span < BORE_HEIGHT - 0.1:
        raise RuntimeError(f"left taper-flank span is only {flank_span:.3f} mm")
    if not bore_candidates:
        raise RuntimeError("front view has no circular model edges")
    radius, height, bore_edge = min(
        bore_candidates,
        key=lambda item: abs(item[0] - BORE_DIA / 2.0)
        + abs(item[1] - BORE_HEIGHT),
    )
    if abs(radius - BORE_DIA / 2.0) > 0.01 or abs(height - BORE_HEIGHT) > 0.01:
        raise RuntimeError(
            f"no circular edge matches arbor bore at {BORE_HEIGHT:.3f} mm"
        )
    dome_radius, dome_height, dome_edge = min(
        bore_candidates,
        key=lambda item: abs(item[0] - TOP_RADIUS)
        + abs(item[1] - BORE_HEIGHT),
    )
    if abs(dome_radius - TOP_RADIUS) > 0.01 or abs(dome_height - BORE_HEIGHT) > 0.01:
        raise RuntimeError("front view has no circular dome edge")
    return foot_edge, side_edge, flank_edge, bore_edge, dome_edge


def _circle_entity(adapter: Any, view: Any, radius_mm: float, *, label: str) -> Any:
    drawing_view = _early_bound(view, "IView")
    candidates: list[tuple[float, Any]] = []
    for component in drawing_view.GetVisibleComponents() or []:
        for raw_edge in drawing_view.GetVisibleEntities2(component, 1) or []:
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


def _add_bore_basic(
    adapter: Any,
    view: Any,
    datum_entity: Any,
    bore_entity: Any,
    *,
    orientation: str,
    position: tuple[float, float],
) -> Any:
    draw = adapter.currentModel
    drawing = _early_bound(draw, "IDrawingDoc")
    if not drawing.ActivateView(view_name(adapter, view)):
        raise RuntimeError("failed to activate front view for bore X location")
    draw.ClearSelection2(True)
    selection_manager = _early_bound(draw.SelectionManager, "ISelectionMgr")
    for append, raw_entity in ((False, datum_entity), (True, bore_entity)):
        selection_data = selection_manager.CreateSelectData()
        selection_data.View = view
        entity = _early_bound(raw_entity, "IEntity")
        if not entity.Select4(append, selection_data):
            raise RuntimeError("failed to select bore X-location entity")
    if orientation == "horizontal":
        display = draw.AddHorizontalDimension2(*position, 0.0)
    elif orientation == "vertical":
        display = draw.AddVerticalDimension2(*position, 0.0)
    else:
        raise ValueError(f"unsupported bore-dimension orientation: {orientation}")
    draw.ClearSelection2(True)
    if display is None:
        raise RuntimeError(f"failed to create bore {orientation} location dimension")
    display = _early_bound(display, "IDisplayDimension")
    dimension = _early_bound(display.GetDimension(), "IDimension")
    arc_end_set = False
    for index in (1, 2):
        if int(dimension.GetArcEndCondition(index)) == 0:
            continue
        result = int(
            dimension.SetArcEndCondition(index, 1)  # swArcEndConditionCenter
        )
        if result != 0:
            raise RuntimeError(
                f"failed to set bore {orientation} endpoint {index} to arc center "
                f"(SolidWorks result {result})"
            )
        draw.GraphicsRedraw2()
        if int(dimension.GetArcEndCondition(index)) != 1:
            raise RuntimeError(
                f"bore {orientation} location did not retain center arc condition"
            )
        arc_end_set = True
    if not arc_end_set:
        raise RuntimeError(f"bore {orientation} dimension has no circular endpoint")
    return set_basic_dimension(adapter, display, label=f"bore {orientation} location")


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
    set_hidden_lines_removed(adapter, iso)
    # The elevation carries the arbor bore as a hidden circle and the flange
    # hold-down hole; the plan shows the foot with the bore + screw crossing it.
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

    # Datum A = the foot seat face (the base-seat datum the bore/dome heights
    # measure from). The arbor bore is toleranced parallel to it and carries the
    # clamp-fit finish.
    _bore_r = BORE_DIA / 2.0 * _S
    foot_edge = (FRONT_CENTER[0] + 0.006, _front_y(0.0))
    foot_entity, side_entity, flank_entity, bore_entity, dome_entity = (
        _front_entities(adapter, front)
    )
    _add_bore_basic(
        adapter,
        front,
        side_entity,
        bore_entity,
        orientation="horizontal",
        position=(FRONT_CENTER[0], _front_y(BORE_HEIGHT + TOP_RADIUS) + 0.010),
    )
    _add_bore_basic(
        adapter,
        front,
        foot_entity,
        bore_entity,
        orientation="vertical",
        position=(0.040, FRONT_CENTER[1]),
    )
    add_datum_feature(
        adapter,
        front,
        edge_xy=foot_edge,
        symbol_xy=(FRONT_CENTER[0] + 0.034, _front_y(0.0) - 0.006),
        datum="A",
        label="foot seat face",
        entity=foot_entity,
    )
    add_datum_feature(
        adapter,
        front,
        edge_xy=(FRONT_CENTER[0] - FOOT_WIDTH / 2.0 * _S, _front_y(2.5)),
        symbol_xy=(0.066, _front_y(2.5)),
        datum="B",
        label="left foot side",
        entity=side_entity,
    )
    # The two BASIC coordinates locate the bore axis from datum A and the left
    # foot side B. Position controls both location and axis orientation.
    add_feature_control_frame(
        adapter,
        front,
        edge_xy=(FRONT_CENTER[0] + _bore_r, _front_y(BORE_HEIGHT)),
        frame_xy=(0.180, _front_y(BORE_HEIGHT) + 0.027),
        characteristic="position",
        tolerance="0.10",
        datums=("A", "B"),
        diameter=True,
        label="arbor bore true position",
        entity=bore_entity,
    )
    add_feature_control_frame(
        adapter,
        front,
        edge_xy=(
            FRONT_CENTER[0] - TOP_RADIUS * _S * 0.70,
            _front_y(BORE_HEIGHT + TOP_RADIUS * 0.70),
        ),
        frame_xy=(0.020, _front_y(BORE_HEIGHT) + 0.030),
        characteristic="profile_surface",
        tolerance="0.10",
        datums=("A", "B"),
        label="dome surface profile",
        entity=dome_entity,
    )
    add_attached_note(
        adapter,
        front,
        text="2X 2.12<MOD-DEG> +/-0.10<MOD-DEG> FROM VERTICAL",
        edge_xy=(FRONT_CENTER[0] - 11.0 * _S, _front_y(BORE_HEIGHT / 2.0)),
        note_xy=(0.020, _front_y(BORE_HEIGHT / 2.0) + 0.015),
        label="taper flank angle",
        entity=flank_entity,
    )
    add_surface_finish(
        adapter,
        front,
        edge_xy=(FRONT_CENTER[0] + _bore_r, _front_y(BORE_HEIGHT)),  # bore right
        symbol_xy=(0.205, _front_y(BORE_HEIGHT) - 0.038),
        roughness_ra="1.6",
        label="arbor bore finish",
        entity=bore_entity,
    )
    screw_entity = _circle_entity(
        adapter,
        top,
        SCREW_CLEARANCE_DIA / 2.0,
        label="flange hold-down hole",
    )
    _screw_r = SCREW_CLEARANCE_DIA / 2.0 * _S
    add_native_hole_callout(
        adapter,
        top,
        edge_xy=(TOP_CENTER[0] + _screw_r, TOP_CENTER[1] + 0.010),
        callout_xy=(0.025, 0.255),
        label="flange hold-down hole",
    )
    add_attached_note(
        adapter,
        top,
        text=(
            "ON 24.00 WIDTH CL; 3.00 +/-0.10 FROM\n"
            "EXPOSED FLANGE EDGE"
        ),
        edge_xy=(TOP_CENTER[0] + _screw_r, TOP_CENTER[1] + 0.010),
        note_xy=(0.020, 0.220),
        label="flange-hole location",
        entity=screw_entity,
    )
    add_feature_control_frame(
        adapter,
        top,
        edge_xy=(TOP_CENTER[0] + SCREW_CLEARANCE_DIA / 2.0 * _S, TOP_CENTER[1]),
        frame_xy=(0.165, 0.250),
        characteristic="perpendicularity",
        tolerance="0.10",
        datums=("A",),
        diameter=True,
        label="flange-hole axis perpendicularity",
        entity=screw_entity,
    )

    # Ten lines occupy almost the full lower-left band. Keep the note above the
    # 12.7 mm zone margin; y=57 mm put its final line 0.8 mm through the border.
    add_property_linked_note(adapter, "Manufacturing Notes", 0.020, 0.064)

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
