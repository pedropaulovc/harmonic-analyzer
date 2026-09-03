r"""Drawing-view annotations shared by the made-fastener sheets.

The fastener prints (cad/docs/drawing-simplicity-policy.md) put the thread
designation ON the view and add conventional crest linework around the
catalog's modeled thread-minor cylinder, mark the screw axis with a
centerline and the head rim with a compact center mark, end every end-view
diameter leader at the rim it names, expose a required occluded shank as a
hidden circle, and stack the true overall length as a parenthesised reference
outside the chained lengths.  The recipe
(``_fastener_drawing``) only hands its ``decorate`` hook the views, so these
helpers re-read what they need from the view and fail loud when a pick
misses.
"""

from __future__ import annotations

from typing import Any, Iterable

import _telemetry
from _common import _early_bound
from _drawing_common import (
    _select_view_entity,
    _sheet_to_view_sketch,
    add_attached_note,
    add_edge_dimension,
    model_point_in_view,
    set_reference_dimension,
    view_name,
)
from solidworks_mcp.adapters import sw_type_info as _sw_type_info
from solidworks_mcp.adapters.solidworks.drawing import dimension_name

_CENTER_MARK_SINGLE = 2  # swCenterMarkStyle_e.swCenterMark_Single
_ARROWS_OUTSIDE = 1  # swDimensionArrowsSide_e.swDimArrowsOutside
_LINE_CONTINUOUS = 0  # swLineStyles_e.swLineCONTINUOUS
_LINE_HIDDEN = 1  # swLineStyles_e.swLineHIDDEN
_LINE_WEIGHT_THIN = 0  # swLineWeights_e.swLW_THIN
_LINE_WEIGHT_THICK = 2  # swLineWeights_e.swLW_THICK
_COLOR_BLACK = 0  # COLORREF


def _unified_thread_geometry_mm(designation: str) -> tuple[float, int]:
    """Return the nominal major diameter and threads per inch."""
    fields = designation.strip().split()
    if len(fields) != 2 or fields[1].upper() not in {"UNC", "UNF", "UNEF"}:
        raise ValueError(f"unsupported Unified thread designation: {designation!r}")
    token = fields[0]
    try:
        size, tpi_text = token.rsplit("-", 1)
        tpi = int(tpi_text)
        if tpi <= 0:
            raise ValueError("thread pitch must be positive")
        if size.startswith("#"):
            gauge = int(size[1:])
            if gauge < 0:
                raise ValueError("thread gauge must be non-negative")
            diameter_in = 0.060 + 0.013 * gauge
        elif "/" in size:
            numerator, denominator = size.split("/", 1)
            diameter_in = float(numerator) / float(denominator)
        else:
            diameter_in = float(size)
    except (IndexError, ValueError, ZeroDivisionError) as exc:
        raise ValueError(
            f"unsupported Unified thread designation: {designation!r}"
        ) from exc
    if diameter_in <= 0.0:
        raise ValueError(f"thread diameter must be positive: {designation!r}")
    return (diameter_in * 25.4, tpi)


def _nominal_thread_major_diameter_mm(designation: str) -> float:
    """Return the Unified-thread nominal major diameter encoded in a callout."""
    return _unified_thread_geometry_mm(designation)[0]


def view_dimension_annotations(adapter: Any, view: Any) -> list[Any]:
    """Every display dimension currently on ``view``, as IAnnotation dispatches."""
    drawing_view = _early_bound(view, "IView")
    displays = drawing_view.GetDisplayDimensions() or []
    annotations: list[Any] = []
    for display in displays:
        display = _sw_type_info.early_bound_or_flag(
            display, "IDisplayDimension", "GetAnnotation"
        )
        annotation = display.GetAnnotation()
        if annotation is None:
            raise RuntimeError("a view display dimension has no annotation")
        annotations.append(
            _sw_type_info.early_bound_or_flag(
                annotation, "IAnnotation", "GetSpecificAnnotation"
            )
        )
    return annotations


@_telemetry.traced("drawing.thread_leader", label_param="label")
def add_thread_leader(
    adapter: Any,
    view: Any,
    *,
    designation: str,
    silhouette_xy: tuple[float, float],
    note_xy: tuple[float, float],
    label: str,
) -> Any:
    """Leader the catalog thread designation to the shank outline.

    The modeled shank is the catalog's interference-safe thread-minor
    cylinder, so its outline is a drawing SILHOUETTE, not a model edge; the
    leader lands on that outline exactly as a machinist expects a thread
    callout to.
    """
    return add_attached_note(
        adapter,
        view,
        text=designation,
        entity_xy=silhouette_xy,
        note_xy=note_xy,
        label=label,
        entity_type="SILHOUETTE",
    )


@_telemetry.traced("drawing.external_thread_depiction", label_param="label")
def add_external_thread_depiction(
    adapter: Any,
    view: Any,
    *,
    axis_start_xy: tuple[float, float],
    axis_end_xy: tuple[float, float],
    model_diameter_sheet: float,
    sheet_scale_per_mm: float,
    designation: str,
    label: str,
) -> tuple[Any, Any]:
    """Draw a conventional external-thread profile over the modeled core.

    The part stays the catalog's interference-safe thread-minor cylinder.
    Hide its two longitudinal silhouettes, then replace them with thin lines
    that stop one pitch short. Thick lines form the nominal Unified-thread
    major envelope and chamfer into the visible minor-diameter free-end edge.
    """
    if model_diameter_sheet <= 0.0:
        raise ValueError(f"{label}: thread model diameter must be positive")
    if sheet_scale_per_mm <= 0.0:
        raise ValueError(f"{label}: sheet scale per mm must be positive")
    dx = axis_end_xy[0] - axis_start_xy[0]
    dy = axis_end_xy[1] - axis_start_xy[1]
    length = (dx * dx + dy * dy) ** 0.5
    if length <= 0.0:
        raise ValueError(f"{label}: thread axis must have nonzero length")

    nx, ny = -dy / length, dx / length
    major_diameter_mm, tpi = _unified_thread_geometry_mm(designation)
    major_diameter_sheet = major_diameter_mm * sheet_scale_per_mm
    if major_diameter_sheet <= model_diameter_sheet:
        raise ValueError(
            f"{label}: nominal thread major diameter must exceed the modeled core"
        )
    major_radius = major_diameter_sheet / 2.0
    pitch_sheet = 25.4 / tpi * sheet_scale_per_mm
    if pitch_sheet >= length:
        raise ValueError(f"{label}: thread length must exceed one pitch")

    draw = adapter.currentModel
    ddoc = _early_bound(draw, "IDrawingDoc")
    sketch_manager = _early_bound(draw.SketchManager, "ISketchManager")
    if not ddoc.ActivateView(view_name(adapter, view)):
        raise RuntimeError(f"{label}: failed to activate thread-profile view")
    draw.ClearSelection2(True)

    minor_radius = model_diameter_sheet / 2.0
    axis_midpoint = (
        (axis_start_xy[0] + axis_end_xy[0]) / 2.0,
        (axis_start_xy[1] + axis_end_xy[1]) / 2.0,
    )
    # The modeled core silhouettes are object-weight geometry. Hide them, then
    # replace them with supported drawing-sketch segments at the conventional
    # thin-minor/thick-major thread weights. The modeled free-end edge remains
    # as the minor-diameter closure between the two added chamfers.
    for side in (-1.0, 1.0):
        minor_pick = (
            axis_midpoint[0] + side * nx * minor_radius,
            axis_midpoint[1] + side * ny * minor_radius,
        )
        _select_view_entity(
            adapter,
            view,
            "SILHOUETTE",
            minor_pick,
            label=f"{label} minor-diameter line",
        )
        ddoc.HideEdge()
        draw.ClearSelection2(True)

    ux, uy = dx / length, dy / length
    minor_axis_end = (
        axis_end_xy[0] - ux * pitch_sheet,
        axis_end_xy[1] - uy * pitch_sheet,
    )
    chamfer_length = major_radius - minor_radius
    major_axis_end = (
        axis_end_xy[0] - ux * chamfer_length,
        axis_end_xy[1] - uy * chamfer_length,
    )
    segments: dict[str, list[Any]] = {}
    for kind, radius, line_end, weight in (
        ("minor", minor_radius, minor_axis_end, _LINE_WEIGHT_THIN),
        ("major", major_radius, major_axis_end, _LINE_WEIGHT_THICK),
    ):
        pair: list[Any] = []
        for side in (-1.0, 1.0):
            start_sheet = (
                axis_start_xy[0] + side * nx * radius,
                axis_start_xy[1] + side * ny * radius,
            )
            end_sheet = (
                line_end[0] + side * nx * radius,
                line_end[1] + side * ny * radius,
            )
            start = _sheet_to_view_sketch(adapter, view, start_sheet, label=label)
            end = _sheet_to_view_sketch(adapter, view, end_sheet, label=label)
            segment = sketch_manager.CreateLine(
                float(start[0]),
                float(start[1]),
                0.0,
                float(end[0]),
                float(end[1]),
                0.0,
            )
            if segment is None:
                raise RuntimeError(f"{label}: failed to create {kind} thread line")
            segment = _early_bound(segment, "ISketchSegment")
            segment.Color = _COLOR_BLACK
            segment.Style = _LINE_CONTINUOUS
            segment.Width = weight
            if int(segment.Color) != _COLOR_BLACK:
                raise RuntimeError(f"{label}: {kind} thread line is not black")
            if int(segment.Style) != _LINE_CONTINUOUS:
                raise RuntimeError(f"{label}: {kind} thread line is not continuous")
            if int(segment.Width) != weight:
                raise RuntimeError(f"{label}: {kind} thread line has wrong weight")
            pair.append(segment)
        segments[kind] = pair

    for side in (-1.0, 1.0):
        chamfer_start_sheet = (
            major_axis_end[0] + side * nx * major_radius,
            major_axis_end[1] + side * ny * major_radius,
        )
        chamfer_end_sheet = (
            axis_end_xy[0] + side * nx * minor_radius,
            axis_end_xy[1] + side * ny * minor_radius,
        )
        chamfer_start = _sheet_to_view_sketch(
            adapter, view, chamfer_start_sheet, label=label
        )
        chamfer_end = _sheet_to_view_sketch(
            adapter, view, chamfer_end_sheet, label=label
        )
        chamfer = sketch_manager.CreateLine(
            float(chamfer_start[0]),
            float(chamfer_start[1]),
            0.0,
            float(chamfer_end[0]),
            float(chamfer_end[1]),
            0.0,
        )
        if chamfer is None:
            raise RuntimeError(f"{label}: failed to create thread free-end chamfer")
        chamfer = _early_bound(chamfer, "ISketchSegment")
        chamfer.Color = _COLOR_BLACK
        chamfer.Style = _LINE_CONTINUOUS
        chamfer.Width = _LINE_WEIGHT_THICK
        if int(chamfer.Color) != _COLOR_BLACK:
            raise RuntimeError(f"{label}: thread free-end chamfer is not black")
        if int(chamfer.Style) != _LINE_CONTINUOUS:
            raise RuntimeError(f"{label}: thread free-end chamfer is not continuous")
        if int(chamfer.Width) != _LINE_WEIGHT_THICK:
            raise RuntimeError(f"{label}: thread free-end chamfer has wrong weight")

    draw.ClearSelection2(True)
    draw.EditRebuild3()
    return (segments["major"][0], segments["major"][1])


@_telemetry.traced("drawing.center_mark", label_param="label")
def add_circle_center_mark(
    adapter: Any,
    view: Any,
    *,
    edge_xy: tuple[float, float],
    label: str,
) -> Any:
    """Insert one ASME center mark on the circular edge picked at ``edge_xy``.

    ``IView.AutoInsertCenterMarks2`` only marks holes, fillets and slots, so a
    screw head's rim (a boss, not a hole) never gets one; the single-mark
    ``IDrawingDoc.InsertCenterMark3`` on the selected rim edge does.
    """
    draw = adapter.currentModel
    ddoc = _early_bound(draw, "IDrawingDoc")
    _select_view_entity(adapter, view, "EDGE", edge_xy, label=label)
    mark = adapter._attempt(
        lambda: ddoc.InsertCenterMark3(_CENTER_MARK_SINGLE, False, False)
    )
    if mark is None:
        raise RuntimeError(f"failed to insert center mark ({label})")
    mark = _sw_type_info.early_bound_or_flag(
        mark, "ICenterMark", "UseDocDisplaySettings", "ShowLines"
    )
    mark.UseDocDisplaySettings = False
    if bool(mark.UseDocDisplaySettings):
        raise RuntimeError(f"center mark kept document display settings ({label})")
    mark.ShowLines = False
    if bool(mark.ShowLines):
        raise RuntimeError(f"center-mark extension lines stayed visible ({label})")
    draw.ClearSelection2(True)
    draw.EditRebuild3()
    return mark


@_telemetry.traced("drawing.hidden_shank_circle", label_param="label")
def add_hidden_shank_circle(
    adapter: Any,
    view: Any,
    *,
    center_xy: tuple[float, float],
    radius_sheet: float,
    label: str,
) -> Any:
    """Expose an occluded shank in an end view as one thin hidden circle."""
    if radius_sheet <= 0.0:
        raise ValueError(f"{label}: hidden shank radius must be positive")
    draw = adapter.currentModel
    ddoc = _early_bound(draw, "IDrawingDoc")
    sketch_manager = _early_bound(draw.SketchManager, "ISketchManager")
    if not ddoc.ActivateView(view_name(adapter, view)):
        raise RuntimeError(f"{label}: failed to activate shank end view")
    draw.ClearSelection2(True)
    center = _sheet_to_view_sketch(adapter, view, center_xy, label=label)
    rim = _sheet_to_view_sketch(
        adapter,
        view,
        (center_xy[0] + radius_sheet, center_xy[1]),
        label=label,
    )
    circle = sketch_manager.CreateCircle(
        float(center[0]),
        float(center[1]),
        0.0,
        float(rim[0]),
        float(rim[1]),
        0.0,
    )
    if circle is None:
        raise RuntimeError(f"{label}: failed to create hidden shank circle")
    circle = _early_bound(circle, "ISketchSegment")
    circle.Style = _LINE_HIDDEN
    circle.Width = _LINE_WEIGHT_THIN
    if int(circle.Style) != _LINE_HIDDEN:
        raise RuntimeError(f"{label}: shank circle is not hidden-line style")
    if int(circle.Width) != _LINE_WEIGHT_THIN:
        raise RuntimeError(f"{label}: shank circle is not thin")
    draw.ClearSelection2(True)
    draw.EditRebuild3()
    return circle


@_telemetry.traced("drawing.leaders_to_rim", label_param="label")
def end_diameter_leaders_at_rim(
    adapter: Any, annotations: Iterable[Any], names: Iterable[str], *, label: str
) -> None:
    """End each named diameter leader at the nearest rim, never across it.

    SolidWorks' default extends a radial diameter line through the circle and
    driver slot.  Outside arrows, no second arrow and an explicitly disabled
    opposite-side arc extension leave one leader terminating at the named rim
    (drawing-simplicity-policy.md rule 8: a leader crosses nothing).
    """
    remaining = set(names)
    for annotation in annotations:
        annotation = _sw_type_info.early_bound_or_flag(
            annotation, "IAnnotation", "GetSpecificAnnotation"
        )
        name = dimension_name(adapter, annotation)
        if name not in remaining:
            continue
        display = _sw_type_info.early_bound_or_flag(
            annotation.GetSpecificAnnotation(),
            "IDisplayDimension",
            "ArrowSide",
            "ArcExtensionLineOrOppositeSide",
            "SetSecondArrow",
            "GetUseDocSecondArrow",
            "GetSecondArrow",
        )
        display.ArrowSide = _ARROWS_OUTSIDE
        display.ArcExtensionLineOrOppositeSide = False
        display.SetSecondArrow(False, False)
        if int(display.ArrowSide) != _ARROWS_OUTSIDE:
            raise RuntimeError(f"{label}: {name} arrows did not move outside")
        if bool(display.ArcExtensionLineOrOppositeSide):
            raise RuntimeError(f"{label}: {name} leader still crosses its end view")
        if bool(display.GetUseDocSecondArrow()) or bool(display.GetSecondArrow()):
            raise RuntimeError(f"{label}: {name} opposite-side arrow stayed visible")
        remaining.discard(name)
    if remaining:
        raise RuntimeError(
            f"{label}: diameter dimensions not found: {sorted(remaining)}"
        )
    adapter.currentModel.EditRebuild3()


@_telemetry.traced("drawing.overall_reference", label_param="label")
def add_overall_reference(
    adapter: Any,
    view: Any,
    *,
    end_points_mm: tuple[tuple[float, float, float], tuple[float, float, float]],
    entity_types: tuple[str, str],
    text_xy: tuple[float, float],
    orientation: str,
    label: str,
) -> Any:
    """Dimension the true overall length between the two end faces as (REF).

    Every fastener sheet chains its lengths from the under-head face (the
    head height and the under-head length are the extrude-depth model
    dimensions), so the overall is derived -- and the blind machinist review
    read the longer segment as the overall on nine sheets.  ASME reference
    notation (parenthesised, never toleranced) says "sum, not a third
    control" (drawing-simplicity-policy.md rule 7: the overall is real and
    conspicuous).

    ``end_points_mm`` are MODEL points, one on each end face, projected into
    the view (``model_point_in_view``, the pinion lift-rod pattern) rather
    than assumed from the view centre.  A turned end face is a circle seen
    EDGE-ON in the profile, which SolidWorks resolves as an EDGE at the
    projected point; a polygon head hands over a corner VERTEX instead.  Pick
    a round face inside its projected line, never at the extreme rim: a
    driver-face rim is broken by the slot and a reeded face is scalloped,
    but every edge on that line lies in the face plane, so a dimension
    pinned to the axis direction reads the same axial distance whichever
    edge the pick lands on.
    """
    if orientation not in ("horizontal", "vertical"):
        raise ValueError(
            f"{label}: overall must be pinned to the axis, not {orientation!r}"
        )
    picks = tuple(
        model_point_in_view(
            adapter,
            view,
            tuple(float(v) / 1000.0 for v in xyz),
            label=f"{label} end {index}",
        )
        for index, xyz in enumerate(end_points_mm)
    )
    dimension = add_edge_dimension(
        adapter,
        view,
        p0=picks[0],
        p1=picks[1],
        text_xy=text_xy,
        label=label,
        orientation=orientation,
        entity_types=entity_types,
    )
    set_reference_dimension(
        adapter,
        _early_bound(dimension, "IDisplayDimension").GetAnnotation(),
        label=label,
    )
    return dimension
