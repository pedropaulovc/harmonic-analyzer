r"""Create the curated machinist drawing for the cylinder-arbor pedestal."""

from __future__ import annotations

import argparse
import sys
from typing import Any, Literal


import _telemetry
from _common import CAD_ROOT, _early_bound, check, run_build
from _drawing_common import (
    DrawingOutputs,
    add_surface_finish,
    add_native_hole_callout,
    assert_imported_precision,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    set_arc_endpoints_to_center,
    set_arc_endpoints_to_max,
    set_dimension_callouts,
    set_hidden_lines_removed,
    set_reference_dimension,
    stamp_drawing_summary,
    visible_view_entities,
)
from _drawing_hidden_sketches import curate_view_dimensions
from _surface_finish import surface_finish_by_key
from _drawing_registry import DRAWINGS_BY_NAME
from arbor_pedestal_spec import (
    BORE_DIA,
    BORE_HEIGHT,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    DRAWING_REFERENCE_PRECISION,
    FOOT_HEIGHT,
    FOOT_MID_Z,
    FOOT_NEAR_Z,
    FOOT_WIDTH,
    SCREW_HOLE_DIA,
    SCREW_Z,
    STRAP_INNER_Z,
    STRAP_ROOT_Z,
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

# The part spans model y 0 (foot seat) to 49.718 (dome top); centre the front
# elevation on that midpoint. Third-angle projection keeps the plan aligned
# above the elevation; the isometric balances the aligned group from the
# right. The elevation sits low so the 28-deep plan (56 on the sheet) clears
# the crown callout and still leaves a dimension lane above itself under the
# sheet border: lateral-location lane 0.055, elevation 0.065..0.165, crown
# text ~0.173, plan 0.182..0.238, hole lateral lane 0.246, foot-width lane
# 0.256.
_PART_MID_Y = (
    BORE_HEIGHT + TOP_RADIUS
) / 2.0  # foot 0 .. dome top (bore + dome radius)
FRONT_CENTER = (0.115, 0.115)
TOP_CENTER = (FRONT_CENTER[0], 0.210)
ISO_CENTER = (0.325, 0.155)


def _front_y(model_y: float) -> float:
    """Sheet Y of a model-Y point in the front view (foot seat at model y=0)."""
    return FRONT_CENTER[1] + (model_y - _PART_MID_Y) * _S


def _top_y(model_z: float) -> float:
    """Sheet Y of a model-Z station in the plan view.

    A ``*Top`` view placed above the elevation projects model +Z downward, so
    the foot's far face (+Z, where the strap is flush) is the plan's BOTTOM
    edge and the exposed hold-down ledge is at the top. The view is centred on
    its bounding box, and the foot runs -20..+8 about the part origin, so the
    sheet centre is the foot's mid-depth, not model z 0.
    """
    return TOP_CENTER[1] - (model_z - FOOT_MID_Z) * _S


# Lanes for the two lateral locations: below the seat in the elevation (the
# bore's centreline extends down through the part, crossing no other
# dimension's extension line), and between the plan and the foot-width lane.
BORE_LATERAL_XY = (FRONT_CENTER[0] - FOOT_WIDTH / 4.0 * _S, _front_y(0.0) - 0.010)
HOLE_LATERAL_XY = (TOP_CENTER[0] - FOOT_WIDTH / 4.0 * _S, _top_y(FOOT_NEAR_Z) + 0.008)

# The elevation carries the height chain off the foot seat plus the fitted
# bore; the plan carries the foot rectangle, the strap band and the hold-down
# hole. Nested left lanes work outward from the shortest span (foot height,
# journal axis, overall reference) off the one datum a machinist actually
# clamps to -- the seat.
FRONT_KEEP = {
    "FootHt": (FRONT_CENTER[0] - 0.034, _front_y(FOOT_HEIGHT / 2.0)),
    "BoreHeight": (FRONT_CENTER[0] - 0.046, _front_y(BORE_HEIGHT / 2.0)),
    "BoreDia": (FRONT_CENTER[0] + 0.043, _front_y(BORE_HEIGHT) - 0.010),
    "BoreLateral": BORE_LATERAL_XY,
    # Crown: printed radial (_show_crown_as_radius), up and right of the dome.
    "DomeDia": (0.178, _front_y(BORE_HEIGHT + TOP_RADIUS) + 0.008),
}
TOP_KEEP = {
    "Width": (TOP_CENTER[0], _top_y(FOOT_NEAR_Z) + 0.018),
    # Outer left lane; its text sits above the hold-down lane's text so the
    # two nested dimensions never read side by side.
    "Depth": (TOP_CENTER[0] - 0.048, _top_y(FOOT_NEAR_Z) - 0.012),
    # Both plan depths work off the foot's far face -- the one face the strap
    # is flush with, so a shop can set the whole Z chain from a single edge.
    "HoldDownLocation": (
        TOP_CENTER[0] - 0.036,
        _top_y((STRAP_INNER_Z + SCREW_Z) / 2.0),
    ),
    "StrapDepth": (
        TOP_CENTER[0] + 0.036,
        _top_y((STRAP_INNER_Z + STRAP_ROOT_Z) / 2.0),
    ),
    "HoleLateral": HOLE_LATERAL_XY,
}
# X on this part starts on a FEATURE, never the symmetry axis (policy rule 7):
# the bore in the elevation and the hold-down hole in the plan are both
# dimensioned from the foot's west side face, so the two views share one
# origin the shop can touch off.
DIMENSION_CALLOUTS = {
    "BoreDia": "REAM THRU",
}
CROWN_CALLOUT = "SIDES TANGENT FROM FOOT CORNERS"


def _set_reference_precision(display: Any, label: str) -> None:
    """Give a SHEET-derived dimension its PART-authored decimal places.

    Policy rule 2 puts display precision on the model, and every imported
    dimension here is read back by ``assert_imported_precision``. The strap
    band, the hold-down station and both lateral locations are owned by the
    part's hidden reference sketches, and the crown radius is the dome's own
    diameter printed radial (#810 Codex l4afp). What is left is the
    parenthesised overall height, a band-free restatement. Its places are
    still specification, so they come from the spec, never a literal.
    """
    places = DRAWING_REFERENCE_PRECISION[label]
    display = _early_bound(display, "IDisplayDimension")
    # -1: swDimensionPrecisionSettings_e do-not-change for the dual and both
    # tolerance places -- the part owns those too. The subscript is written
    # out again because _drawing_contract only accepts a spec lookup here.
    display.SetPrecision3(DRAWING_REFERENCE_PRECISION[label], -1, -1, -1)
    applied = int(display.GetPrimaryPrecision2())
    if applied != places:
        raise RuntimeError(
            f"{label}: sheet dimension prints {applied} decimal places, not {places}"
        )


@_telemetry.traced("drawing.arbor.front_entity_scan")
def _front_entities(adapter: Any, view: Any) -> tuple[Any, Any, Any]:
    """Return the foot-seat, arbor-bore and crown entities."""
    foot_candidates: list[tuple[float, Any]] = []
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
    return foot_edge, bore_edge, dome_edge


_ARROWS_OUTSIDE = 1  # swDimensionArrowsSide_e.swDimArrowsOutside


@_telemetry.traced("drawing.crown_radius")
def _show_crown_as_radius(adapter: Any, annotations: list[Any]) -> None:
    """Print the model's dome diameter as the crown RADIUS it is on the part.

    The dome is a full-circle boss in the model (DomeDia, part-owned places),
    but only its upper arc survives on the part, and a print gives an arc a
    radius. ``Diametric = False`` flips the imported diameter to its radial
    form -- same model dimension, same places, half the value -- so no sheet
    geometry restates it (#810 Codex l4afp, policy rule 2).
    """
    for raw_annotation in annotations:
        annotation = _early_bound(raw_annotation, "IAnnotation")
        if dimension_name(adapter, annotation) != "DomeDia":
            continue
        display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
        display.Diametric = False
        # The crown is what places the tapered flanks: each side runs from a
        # 24.0 foot corner up to tangency with this radius, whose centre is
        # the bore's (the shared centre mark says so). The Fable round-2
        # review could not tell where the flanks start, so the words name
        # both ends. Words only -- every digit on this sheet is a dimension.
        display.SetText(4, CROWN_CALLOUT)
        # The leader runs from the text toward the crown centre; with the
        # default "extend to the opposite side" it kept going through the bore
        # and crossed the Ø9.55 dimension at the centre. Stop it at the arc.
        display.ArcExtensionLineOrOppositeSide = False
        # Arrow OUTSIDE the arc (swDimArrowsOutside): the leader runs from the
        # text to the crown and stops there. Inside, the dimension line ran
        # from the arc to the centre, straight through the bore (810-l4afp-1
        # eye pass).
        display.ArrowSide = _ARROWS_OUTSIDE
        if (
            bool(display.Diametric)
            or str(display.GetText(4) or "") != CROWN_CALLOUT
            or bool(display.ArcExtensionLineOrOppositeSide)
            or int(display.ArrowSide) != _ARROWS_OUTSIDE
        ):
            raise RuntimeError("crown radius display did not persist")
        _telemetry.info(
            f"crown radius: DomeDia shown radial, text {display.GetText(1)!r}"
        )
        return
    raise RuntimeError("front view has no imported DomeDia to show as the crown radius")


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
    # Neither orthographic view needs hidden lines: the elevation shows the
    # arbor bore in true circle and the hold-down hole is a native callout on
    # the plan, so dashed outlines would only add crossings over the strap.
    for view in (front, top, iso):
        set_hidden_lines_removed(adapter, view)

    # The strap band, hold-down station and lateral locations are owned by
    # reference sketches the part saves blanked (arbor_pedestal_spec
    # REFERENCE_SKETCHES); the hidden-owner curate shows each in the one view
    # that dimensions it.
    front_annotations = curate_view_dimensions(
        adapter,
        front,
        keep=FRONT_KEEP,
        view_label="front",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    top_annotations = curate_view_dimensions(
        adapter,
        top,
        keep=TOP_KEEP,
        view_label="top",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    imported_annotations = [*front_annotations, *top_annotations]
    set_dimension_callouts(adapter, imported_annotations, DIMENSION_CALLOUTS)
    for view, label in ((front, "front"), (top, "plan")):
        view.SetDisplayTangentEdges2(0)
        if int(view.GetDisplayTangentEdges2()) != 0:
            raise RuntimeError(f"failed to hide {label}-view tangent edges")
        view.UpdateViewDisplayGeometry()
    _disable_diameter_second_arrow(
        adapter,
        front_annotations,
        dimension="BoreDia",
        label="arbor bore",
    )
    for view, label in ((front, "front"), (top, "plan")):
        if not auto_center_marks(adapter, view, holes=True, size=0.0025):
            raise RuntimeError(f"failed to add ASME center marks to {label} view")

    foot_entity, bore_entity, dome_entity = _front_entities(adapter, front)
    # Attach on the bore's 3 o'clock point and keep the symbol above that
    # height: left to itself the leader reached into the circle and crossed
    # the diameter dimension's line, which leaves the bore at 315 deg.
    add_surface_finish(
        adapter,
        front,
        symbol_xy=(FRONT_CENTER[0] + 0.037, _front_y(BORE_HEIGHT) + 0.010),
        control=surface_finish_by_key(SURFACE_FINISHES, "arbor_bore"),
        label="arbor bore finish",
        char_height=0.0025,
        entity=bore_entity,
        leader_attach_xy=(
            FRONT_CENTER[0] + BORE_DIA / 2.0 * _S,
            _front_y(BORE_HEIGHT),
        ),
    )
    # Below and right of the seat. The foot's width is dimensioned in the
    # plan, so nothing here owns a witness line the leader could cross: it
    # leaves the vee's left side, runs up-left to the seat's right quarter,
    # and the "Ra 3.2" text hangs right of the symbol into empty sheet.
    add_surface_finish(
        adapter,
        front,
        symbol_xy=(FRONT_CENTER[0] + 0.035, _front_y(0.0) - 0.010),
        control=surface_finish_by_key(SURFACE_FINISHES, "foot_seat"),
        label="foot seat finish",
        char_height=0.0025,
        entity=foot_entity,
        leader_attach_xy=(FRONT_CENTER[0] + FOOT_WIDTH * _S / 4.0, _front_y(0.0)),
    )
    overall = _add_entity_dimension(
        adapter,
        front,
        foot_entity,
        dome_entity,
        orientation="vertical",
        position=(FRONT_CENTER[0] - 0.058, FRONT_CENTER[1]),
        label="overall height",
        arc_endpoint="max",
    )
    set_reference_dimension(
        adapter,
        _early_bound(overall, "IDisplayDimension").GetAnnotation(),
        label="overall height",
    )
    _set_reference_precision(overall, "overall height")
    _show_crown_as_radius(adapter, front_annotations)
    adapter.currentModel.GraphicsRedraw2()
    _screw_r = SCREW_HOLE_DIA / 2.0 * _S
    # ``callout_xy`` is the text's CENTRE, and this callout's text is ~114 mm
    # wide at 2:1, so anchoring it near the view buried its left half in the
    # plan outline and the foot-width dimension. Centred a view-width to the
    # right it lands in open sheet between the plan and the isometric, and
    # its leader leaves the hole below the width witness lines.
    add_native_hole_callout(
        adapter,
        top,
        edge_xy=(TOP_CENTER[0] + _screw_r, _top_y(SCREW_Z)),
        callout_xy=(TOP_CENTER[0] + 0.120, _top_y(SCREW_Z) + 0.012),
        label="flange hold-down hole",
        process="DRILL",
    )
    # Re-assert the display mode now the last annotation has landed: an
    # annotation attached after placement can leave a view's edge set
    # unregenerated, and only a real mode change rebuilds it.
    for view in (front, top):
        set_hidden_lines_removed(adapter, view)
    # The part authored every imported dimension's decimal places; prove the
    # import kept them instead of falling back to the sheet's two-place
    # default (policy rule 2 -- the sheet may not rewrite them).
    assert_imported_precision(adapter, imported_annotations, DRAWING_PRECISION_BY_NAME)
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
