r"""Create the arbor-pedestal manufacturing drawing under the simplicity policy.

Front elevation and plan, third-angle aligned, hidden lines on. Each view
dimensions from one origin: heights from the foot seat, depths from the strap's
flush (+Z) face, the hold-down hole from the foot's left side. The only
tolerance on the sheet is the reamed arbor bore's native fit band; the crown,
side taper and hold-down hole are ordinary dimensions, and the overall height
and taper angle are references (the crown radius and bore height fix both).
The pictorial is the part-owned rear isometric so the flange hole faces the
viewer instead of hiding behind the strap.

Run with SolidWorks open::

    uv run python cad\scripts\draw_arbor_pedestal.py arbor-pedestal
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
    add_native_hole_callout,
    add_surface_finish,
    curate_view_dimensions,
    dimension_name,
    finalize_drawing,
    model_point_in_view,
    new_project_drawing,
    read_required_properties,
    set_arc_endpoints_to_center,
    set_arc_endpoints_to_max,
    set_dimension_callouts,
    set_dimension_precision,
    set_hidden_lines_visible,
    set_high_quality_shaded_with_edges,
    set_reference_dimension,
    stamp_drawing_summary,
    view_name,
)
from _drawing_registry import DRAWINGS_BY_NAME
from _surface_finish import surface_finish_by_key
from arbor_pedestal_spec import (
    BORE_DIA,
    BORE_HEIGHT,
    FOOT_DEPTH,
    FOOT_HEIGHT,
    FOOT_WIDTH,
    PICTORIAL_VIEW,
    SCREW_HOLE_DIA,
    SCREW_Z,
    STRAP_T,
    SURFACE_FINISHES,
    TAPER_ANGLE_DEG,
    TAPER_TANGENT_X,
    TAPER_TANGENT_Y,
    TOP_RADIUS,
)
from solidworks_mcp.adapters.pywin32_adapter import null_callout
from solidworks_mcp.adapters.solidworks.drawing import auto_center_marks, place_view


SPEC = DRAWINGS_BY_NAME["arbor_pedestal"]
PART_STEM = SPEC.artifact_stem
SOURCE = CAD_ROOT / "out" / "sldprt" / f"{PART_STEM}.SLDPRT"
OUTPUTS = DrawingOutputs(
    slddrw=SPEC.outputs["slddrw"], pdf=SPEC.outputs["pdf"], png=SPEC.outputs["png"]
)
SLDDRW, PDF, PNG = OUTPUTS.slddrw, OUTPUTS.pdf, OUTPUTS.png
SHEET_SCALE = (2.0, 1.0)  # the casting is 50 mm tall; 2:1 keeps the bore legible

# Third-angle: the plan sits directly above the elevation; the pictorial fills
# the right half of the landscape sheet.
FRONT_CENTER = (0.135, 0.125)
TOP_CENTER = (FRONT_CENTER[0], 0.222)
ISO_CENTER = (0.335, 0.150)

# Native model dimensions the print keeps, by view, at their text positions.
FRONT_KEEP = {
    "FootHt": (0.100, 0.080),
    "BoreDia": (0.196, 0.140),
}
TOP_KEEP = {
    "Width": (TOP_CENTER[0], 0.252),
    "Depth": (0.196, TOP_CENTER[1]),
}
DIMENSION_CALLOUTS = {"BoreDia": "REAM THRU; ON C/L"}
DIMENSION_PRECISION = {"Width": 1, "Depth": 1, "FootHt": 1, "BoreDia": 2}
_SW_ARROWS_OUTSIDE = 1  # swDimensionArrowsSide_e.swDimArrowsOutside
_FLANK_MID_Y = (FOOT_HEIGHT + TAPER_TANGENT_Y) / 2.0
_FLANK_MID_X = (FOOT_WIDTH / 2.0 + TAPER_TANGENT_X) / 2.0
_CROWN_PICK_DEG = 60.0  # where the crown radius leader leaves the arc


def _point(
    adapter: Any, view: Any, xyz_mm: tuple[float, float, float]
) -> tuple[float, float]:
    return model_point_in_view(
        adapter,
        view,
        tuple(value / 1000.0 for value in xyz_mm),
        label="pedestal dimension pick",
    )


def _measured(display: Any) -> float:
    native = _early_bound(display, "IDisplayDimension")
    return float(_early_bound(native.GetDimension2(0), "IDimension").SystemValue)


def _checked_dimension(
    adapter: Any,
    view: Any,
    *,
    p0: tuple[float, float, float],
    p1: tuple[float, float, float],
    text_xy: tuple[float, float],
    label: str,
    expected_mm: float,
    orientation: str,
    precision: int,
    center: bool = False,
    maximum: bool = False,
) -> Any:
    """Dimension two picked model points and verify the native value."""
    display = add_edge_dimension(
        adapter,
        view,
        p0=_point(adapter, view, p0),
        p1=_point(adapter, view, p1),
        text_xy=text_xy,
        label=label,
        orientation=orientation,
    )
    if center:
        set_arc_endpoints_to_center(adapter, display, label=label)
    if maximum:
        set_arc_endpoints_to_max(adapter, display, label=label)
    measured_mm = _measured(display) * 1000.0
    if abs(measured_mm - expected_mm) > 1e-5:
        raise RuntimeError(
            f"{label}: measured {measured_mm:g}, expected {expected_mm:g} mm"
        )
    annotation = _early_bound(
        _early_bound(display, "IDisplayDimension").GetAnnotation(), "IAnnotation"
    )
    set_dimension_precision(
        adapter, [annotation], {dimension_name(adapter, annotation): precision}
    )
    return annotation


def _select_edge_at(
    adapter: Any,
    view: Any,
    xyz_mm: tuple[float, float, float],
    *,
    append: bool,
    label: str,
) -> None:
    draw = adapter.currentModel
    x, y = _point(adapter, view, xyz_mm)
    if not draw.Extension.SelectByID2(
        "", "EDGE", x, y, 0.0, append, 0, null_callout(), 0
    ):
        raise RuntimeError(f"failed to select {label} edge at sheet ({x:g}, {y:g})")


@_telemetry.traced("drawing.crown_radius")
def _add_crown_radius(adapter: Any, view: Any) -> None:
    """R10 on the dome, concentric with the bore; leader leaves the arc at 60 deg."""
    draw = adapter.currentModel
    ddoc = _early_bound(draw, "IDrawingDoc")
    if not ddoc.ActivateView(view_name(adapter, view)):
        raise RuntimeError("failed to activate the front view for the crown radius")
    draw.ClearSelection2(True)
    angle = math.radians(_CROWN_PICK_DEG)
    pick = (
        TOP_RADIUS * math.cos(angle),
        BORE_HEIGHT + TOP_RADIUS * math.sin(angle),
        FOOT_DEPTH / 2.0,
    )
    _select_edge_at(adapter, view, pick, append=False, label="crown arc")
    # Text on the same ray, clear of the plan view above and the bore finish
    # symbol to the right.
    x, y = _point(adapter, view, pick)
    reach = 0.020
    display = draw.AddRadialDimension2(
        x + reach * math.cos(angle), y + reach * math.sin(angle), 0.0
    )
    draw.ClearSelection2(True)
    if display is None:
        raise RuntimeError("failed to create the crown radius dimension")
    measured_mm = _measured(display) * 1000.0
    if abs(measured_mm - TOP_RADIUS) > 1e-5:
        raise RuntimeError(
            f"crown radius measured {measured_mm:g}, expected {TOP_RADIUS:g}"
        )
    display = _early_bound(display, "IDisplayDimension")
    display.SetText(4, "CONC W/ BORE")  # swDimensionTextCalloutBelow
    display.SetPrecision3(1, -1, -1, -1)
    # Default "extend to the opposite side" ran the leader through the bore.
    display.ArcExtensionLineOrOppositeSide = False
    if (
        str(display.GetText(4) or "") != "CONC W/ BORE"
        or int(display.GetPrimaryPrecision2()) != 1
        or bool(display.ArcExtensionLineOrOppositeSide)
    ):
        raise RuntimeError("crown radius annotation did not persist")
    draw.EditRebuild3()


@_telemetry.traced("drawing.taper_reference_angle")
def _add_taper_angle(adapter: Any, view: Any) -> None:
    """(3.27 deg) reference between the right flank and the foot's side face.

    The crown radius and bore height already fix the flank, so the angle is a
    reference for setting up the cut, never a control. SolidWorks measures the
    sector the text is dropped in: only the narrow wedge above the foot corner
    (between the vertical side, extended, and the flank) reads the taper, so
    the dimension is created there and its text then moved clear of the part.
    """
    draw = adapter.currentModel
    ddoc = _early_bound(draw, "IDrawingDoc")
    if not ddoc.ActivateView(view_name(adapter, view)):
        raise RuntimeError("failed to activate the front view for the taper angle")
    draw.ClearSelection2(True)
    half_root = FOOT_WIDTH / 2.0
    _select_edge_at(
        adapter,
        view,
        (_FLANK_MID_X, _FLANK_MID_Y, FOOT_DEPTH / 2.0),
        append=False,
        label="right flank",
    )
    _select_edge_at(
        adapter,
        view,
        (half_root, FOOT_HEIGHT / 2.0, FOOT_DEPTH / 2.0),
        append=True,
        label="foot right side",
    )
    corner = _point(adapter, view, (half_root, FOOT_HEIGHT, FOOT_DEPTH / 2.0))
    wedge_height = 0.030
    wedge = (
        corner[0] - 0.5 * wedge_height * math.tan(math.radians(TAPER_ANGLE_DEG)),
        corner[1] + wedge_height,
    )
    display = draw.AddDimension2(wedge[0], wedge[1], 0.0)
    draw.ClearSelection2(True)
    if display is None:
        raise RuntimeError("failed to create the taper reference angle")
    measured_deg = math.degrees(_measured(display))
    if abs(measured_deg - TAPER_ANGLE_DEG) > 1e-6:
        raise RuntimeError(
            f"taper angle measured {measured_deg:g}, expected {TAPER_ANGLE_DEG:g} deg"
        )
    native = _early_bound(display, "IDisplayDimension")
    annotation = _early_bound(native.GetAnnotation(), "IAnnotation")
    text_xy = (corner[0] + 0.022, corner[1] + 0.034)
    if not annotation.SetPosition2(text_xy[0], text_xy[1], 0.0):
        raise RuntimeError("failed to move the taper angle text off the flank")
    draw.EditRebuild3()
    moved_deg = math.degrees(_measured(display))
    if abs(moved_deg - TAPER_ANGLE_DEG) > 1e-6:
        raise RuntimeError(
            f"taper angle flipped to {moved_deg:g} deg when its text moved"
        )
    native.SetPrecision3(2, -1, -1, -1)
    if int(native.GetPrimaryPrecision2()) != 2:
        raise RuntimeError("taper angle precision did not persist")
    set_reference_dimension(adapter, annotation, label="taper reference angle")


@_telemetry.traced("drawing.bore_leader")
def _point_bore_leader_at_near_edge(adapter: Any, annotations: list[Any]) -> None:
    """Land the Ø leader on the bore's near edge instead of across it."""
    for raw in annotations:
        annotation = _early_bound(raw, "IAnnotation")
        if dimension_name(adapter, annotation) != "BoreDia":
            continue
        display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
        display.SetSecondArrow(False, False)
        display.ArrowSide = _SW_ARROWS_OUTSIDE
        if (
            bool(display.GetUseDocSecondArrow())
            or bool(display.GetSecondArrow())
            or int(display.ArrowSide) != _SW_ARROWS_OUTSIDE
        ):
            raise RuntimeError("bore diameter leader did not move to the near edge")
        adapter.currentModel.GraphicsRedraw2()
        return
    raise RuntimeError("BoreDia dimension not found in the front view")


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")
    check("open arbor-pedestal source", await adapter.open_model(str(SOURCE)))
    properties = (
        "Number",
        "Revision",
        "Title",
        "Material",
        "Material Specification",
        "Finish",
        "Quantity",
    )
    read_required_properties(
        adapter.currentModel,
        properties,
        required=tuple(
            name for name in properties if name not in {"Revision", "Title"}
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
            3: "arbor pedestal; ferrous stock or casting; reamed arbor clamp bore",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=SHEET_SCALE)
    top = place_view(adapter, str(SOURCE), "*Top", *TOP_CENTER, scale=SHEET_SCALE)
    for view, label in ((front, "front"), (top, "plan")):
        set_hidden_lines_visible(adapter, view)
        # The flank-to-crown tangency is not an edge a machinist cuts.
        view.SetDisplayTangentEdges2(0)
        if int(view.GetDisplayTangentEdges2()) != 0:
            raise RuntimeError(f"failed to hide {label}-view tangent edges")
        view.UpdateViewDisplayGeometry()
    pictorial = place_view(
        adapter, str(SOURCE), PICTORIAL_VIEW, *ISO_CENTER, scale=SHEET_SCALE
    )
    # A part-owned named view is not "*Isometric", so the finalizer's shaded
    # pass skips it; hold it to the same policy here.
    set_high_quality_shaded_with_edges(adapter, pictorial, label="rear isometric")

    front_annotations = curate_view_dimensions(
        adapter, front, keep=FRONT_KEEP, view_label="front"
    )
    top_annotations = curate_view_dimensions(
        adapter, top, keep=TOP_KEEP, view_label="plan"
    )
    annotations = [*front_annotations, *top_annotations]
    set_dimension_callouts(adapter, annotations, DIMENSION_CALLOUTS)
    set_dimension_precision(adapter, annotations, DIMENSION_PRECISION)
    _point_bore_leader_at_near_edge(adapter, front_annotations)
    for view, label in ((front, "front"), (top, "plan")):
        if not auto_center_marks(adapter, view, holes=True, size=0.0025):
            raise RuntimeError(f"failed to add centre marks to the {label} view")

    # Elevation: heights from the foot seat.
    seat = (-FOOT_WIDTH / 4.0, 0.0, FOOT_DEPTH / 2.0)
    _checked_dimension(
        adapter,
        front,
        p0=seat,
        p1=(0.0, BORE_HEIGHT - BORE_DIA / 2.0, FOOT_DEPTH / 2.0),
        text_xy=(0.078, FRONT_CENTER[1]),
        label="bore height from foot seat",
        expected_mm=BORE_HEIGHT,
        orientation="vertical",
        precision=2,
        center=True,
    )
    overall = _checked_dimension(
        adapter,
        front,
        p0=seat,
        p1=(0.0, BORE_HEIGHT + TOP_RADIUS, FOOT_DEPTH / 2.0),
        text_xy=(0.058, FRONT_CENTER[1]),
        label="overall height",
        expected_mm=BORE_HEIGHT + TOP_RADIUS,
        orientation="vertical",
        precision=1,
        maximum=True,
    )
    set_reference_dimension(adapter, overall, label="overall height")
    _add_crown_radius(adapter, front)
    _add_taper_angle(adapter, front)
    bore_upper_right = (
        BORE_DIA / 2.0 * math.cos(math.radians(30.0)),
        BORE_HEIGHT + BORE_DIA / 2.0 * math.sin(math.radians(30.0)),
        FOOT_DEPTH / 2.0,
    )
    add_surface_finish(
        adapter,
        front,
        edge_xy=_point(adapter, front, bore_upper_right),
        symbol_xy=(0.166, 0.160),
        control=surface_finish_by_key(SURFACE_FINISHES, "arbor_bore"),
        label="arbor bore finish",
        char_height=0.0025,
    )
    seat_attach = _point(adapter, front, (FOOT_WIDTH / 8.0, 0.0, FOOT_DEPTH / 2.0))
    add_surface_finish(
        adapter,
        front,
        edge_xy=seat_attach,
        symbol_xy=(seat_attach[0], seat_attach[1] - 0.022),
        control=surface_finish_by_key(SURFACE_FINISHES, "foot_seat"),
        label="foot seat finish",
        char_height=0.0025,
    )

    # Plan: depths from the strap's flush face, the hole from the left side.
    flush_face = (FOOT_WIDTH / 4.0, FOOT_HEIGHT, FOOT_DEPTH / 2.0)
    _checked_dimension(
        adapter,
        top,
        p0=flush_face,
        p1=(FOOT_WIDTH / 4.0, FOOT_HEIGHT, FOOT_DEPTH / 2.0 - STRAP_T),
        text_xy=(0.170, TOP_CENTER[1] - 0.006),
        label="strap depth",
        expected_mm=STRAP_T,
        orientation="vertical",
        precision=1,
    )
    hole_top = (0.0, FOOT_HEIGHT, SCREW_Z - SCREW_HOLE_DIA / 2.0)
    _checked_dimension(
        adapter,
        top,
        p0=flush_face,
        p1=hole_top,
        text_xy=(0.183, TOP_CENTER[1]),
        label="hold-down hole from flush face",
        expected_mm=FOOT_DEPTH / 2.0 - SCREW_Z,
        orientation="vertical",
        precision=2,
        center=True,
    )
    _checked_dimension(
        adapter,
        top,
        p0=(-FOOT_WIDTH / 2.0, FOOT_HEIGHT, 0.0),
        p1=hole_top,
        text_xy=(TOP_CENTER[0] - FOOT_WIDTH / 4.0 / 1000.0 * SHEET_SCALE[0], 0.244),
        label="hold-down hole from left side",
        expected_mm=FOOT_WIDTH / 2.0,
        orientation="horizontal",
        precision=1,
        center=True,
    )
    add_native_hole_callout(
        adapter,
        top,
        edge_xy=_point(adapter, top, hole_top),
        callout_xy=(0.072, TOP_CENTER[1] + 0.006),
        label="flange hold-down hole",
        process="DRILL",
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
