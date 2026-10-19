"""Native supplier references for Y-axis dowels and X-axis spring pins.

Nothing here sets a SystemValue or replaces numeric dimension text. Supplier
bands apply only to newly owned references; existing finished controls and
installation notes remain owned by the original model/drawing builders.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable
import math
from typing import Any

from solidworks_mcp.adapters.solidworks.drawing import dimension_name, view_name

import _telemetry
from _com import _early_bound
from _drawing_edge_dimensions import add_edge_dimension, assert_dimension_measures
from _drawing_edges import ViewEdge, ViewEdges, scan_view_edges
from _drawing_hidden_sketches import curate_view_dimensions
from _drawing_projection import model_points_in_view
from _supplier_dimensions import (
    assert_supplier_reference_dimension,
    supplier_reference_dimension,
)
from _supplier_pin_data import (
    MATING_HOLE_DIMENSION,
    REFERENCE_DIMENSIONS,
    WALL_DIMENSION,
    SupplierPinReference,
)


def _axis_circles(edges: ViewEdges, axis: int, *, label: str) -> list[ViewEdge]:
    circles = [
        edge for edge in edges.circles
        if abs(abs(edge.circle[axis + 3]) - 1.0) < 1e-6
        and all(abs(edge.circle[index]) < 1e-5 for index in range(3) if index != axis)
    ]
    if not circles:
        raise RuntimeError(f"{label}: no visible pin-axis circular edges")
    return circles


def _end_circle(
    circles: list[ViewEdge], axis: int, station: float, *, label: str
) -> ViewEdge:
    matches = [edge for edge in circles if abs(edge.circle[axis] - station) < 1e-5]
    if not matches:
        raise RuntimeError(f"{label}: no real end rim at {station:g} mm")
    # A tube has two concentric rims; the outer rim identifies the end face.
    return max(matches, key=lambda edge: edge.circle[6])


def _outer_circle(
    circles: list[ViewEdge], diameter_mm: float, *, label: str
) -> ViewEdge:
    matches = [edge for edge in circles if abs(2.0 * edge.circle[6] - diameter_mm) < 1e-5]
    if not matches:
        raise RuntimeError(f"{label}: no visible full-diameter rim for {diameter_mm:g} mm")
    # Chamfered dowels retain a full-diameter shoulder rather than a full-size
    # end rim. Choose it by measured radius, never the smaller end face.
    return min(matches, key=lambda edge: edge.circle[:3])


def _assert_attachments(
    adapter: Any, display: Any, expected: tuple[Any, ...], *, label: str
) -> None:
    annotation = _early_bound(display.GetAnnotation(), "IAnnotation")
    attached = tuple(annotation.GetAttachedEntities3() or ())
    if annotation.IsDangling() or not expected or len(attached) != len(expected):
        raise RuntimeError(f"{label}: native reference lost its required attachments")
    remaining = list(attached)
    for entity in expected:
        matches = [
            index for index, actual in enumerate(remaining)
            if actual is not None and int(adapter.swApp.IsSame(actual, entity)) == 1
        ]
        if len(matches) != 1:
            raise RuntimeError(f"{label}: native reference changed physical attachment")
        remaining.pop(matches[0])


def _diameter_dimension(
    adapter: Any, view: Any, edge: ViewEdge, text_xy: tuple[float, float], *, label: str
) -> Any:
    draw = _early_bound(adapter.currentModel, "IModelDoc2")
    if not _early_bound(draw, "IDrawingDoc").ActivateView(view_name(adapter, view)):
        raise RuntimeError(f"{label}: cannot activate drawing view")
    draw.ClearSelection2(True)
    if not _early_bound(view, "IView").SelectEntity(edge.edge, False):
        raise RuntimeError(f"{label}: cannot select exact full-diameter circle")
    display = draw.AddDiameterDimension2(*text_xy, 0.0)
    draw.ClearSelection2(True)
    if display is None:
        raise RuntimeError(f"{label}: no native diameter dimension created")
    display = _early_bound(display, "IDisplayDimension")
    if int(display.Type2) != 6:  # swDiameterDimension
        raise RuntimeError(f"{label}: native reference is not a diameter")
    _assert_attachments(adapter, display, (edge.edge,), label=label)
    return display


def _set_band(
    display: Any, *, lower_mm: float, upper_mm: float, limits: bool, places: int, label: str
) -> None:
    dimension = _early_bound(display.GetDimension2(0), "IDimension")
    tolerance = _early_bound(dimension.Tolerance, "IDimensionTolerance")
    kind = 3 if limits else 2  # swTolLIMIT / swTolBILAT
    tolerance.Type = kind
    lower_m, upper_m = lower_mm / 1000.0, upper_mm / 1000.0
    # Existing source-model tolerance helpers use this documented API because
    # SetValues2 rejects some supported native dimensions on SolidWorks 2026.
    if not tolerance.SetValues(lower_m, upper_m):
        raise RuntimeError(f"{label}: native supplier band was rejected")
    display.SetPrecision3(-1, -1, places, -1)
    _assert_band(display, lower_m, upper_m, kind, places, label=label)


def _assert_band(
    display: Any, lower_m: float, upper_m: float, kind: int, places: int, *, label: str
) -> None:
    tolerance = _early_bound(
        _early_bound(display.GetDimension2(0), "IDimension").Tolerance,
        "IDimensionTolerance",
    )
    if (
        int(tolerance.Type) != kind
        or not math.isclose(float(tolerance.GetMinValue()), lower_m, rel_tol=0.0, abs_tol=1e-12)
        or not math.isclose(float(tolerance.GetMaxValue()), upper_m, rel_tol=0.0, abs_tol=1e-12)
        or int(display.GetPrimaryTolPrecision2()) != places
    ):
        raise RuntimeError(f"{label}: native supplier tolerance values/type/precision changed")


def _assert_no_band(display: Any, *, label: str) -> None:
    tolerance = _early_bound(
        _early_bound(display.GetDimension2(0), "IDimension").Tolerance, "IDimensionTolerance"
    )
    if int(tolerance.Type) != 0:  # swTolNONE: no unsourced supplier band.
        raise RuntimeError(f"{label}: native reference gained an unsourced tolerance")


@_telemetry.traced("drawing.supplier_pin_final_readback")
def assert_supplier_pin_dimensions(
    adapter: Any, views: dict[str, Any],
    required: dict[str, tuple[str, Callable[[Any], None]]], *, label: str
) -> None:
    """Read the final view census and revalidate each owned native reference."""
    counts: Counter[str] = Counter()
    for orientation, view in views.items():
        for raw in _early_bound(view, "IView").GetAnnotationsByType(4) or ():
            annotation = _early_bound(raw, "IAnnotation")
            display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
            name = _early_bound(display.GetDimension2(0), "IDimension").FullName
            if name not in required:
                continue  # Existing finished/installation controls are not ours.
            expected_view, assertion = required[name]
            counts[name] += 1
            if orientation != expected_view:
                raise RuntimeError(f"{label}: {name} moved into {orientation}, expected {expected_view}")
            assertion(display)
    if any(counts[name] != 1 for name in required):
        raise RuntimeError(f"{label}: final supplier-reference census is {dict(counts)}, expected one each")


def _settled_pin_check(
    adapter: Any, views: dict[str, Any],
    references: list[tuple[str, Any, Callable[[Any], None]]],
    *, expected_count: int, label: str,
) -> Callable[[], None]:
    required: dict[str, tuple[str, Callable[[Any], None]]] = {}
    for orientation, display, assertion in references:
        name = _early_bound(display.GetDimension2(0), "IDimension").FullName
        if not isinstance(name, str) or not name or name in required:
            raise RuntimeError(f"{label}: missing or duplicate native dimension identity {name!r}")
        required[name] = (orientation, assertion)
    if len(required) != expected_count:
        raise RuntimeError(f"{label}: authored {len(required)} supplier references, expected {expected_count}")
    return lambda: assert_supplier_pin_dimensions(adapter, views, required, label=label)


def _supplier_diameter(
    adapter: Any, view: Any, circles: list[ViewEdge], source: SupplierPinReference,
    *, text_xy: tuple[float, float]
) -> tuple[Any, Callable[[Any], None]]:
    label = f"{source.sku} supplier diameter"
    edge = _outer_circle(circles, source.diameter_mm, label=label)
    display = _diameter_dimension(adapter, view, edge, text_xy, label=label)
    band = source.diameter_band
    limits = False
    if band is not None:
        limits = not math.isclose(
            source.diameter_nominal * source.unit_mm, source.diameter_mm,
            rel_tol=0.0, abs_tol=1e-8,
        )
        lower_mm = (source.diameter_nominal + band[0]) * source.unit_mm - source.diameter_mm
        upper_mm = (source.diameter_nominal + band[1]) * source.unit_mm - source.diameter_mm
        _set_band(
            display, lower_mm=lower_mm, upper_mm=upper_mm, limits=limits,
            places=source.diameter_precision, label=label,
        )
    callout = "SUPPLIER LIMITS" if limits else None
    display = supplier_reference_dimension(
        adapter, display, label=label, units=source.units,
        precision=source.diameter_precision, expected_mm=source.diameter_mm,
        presentation="diameter", callout=callout,
    )

    def assert_diameter(current: Any) -> None:
        assert_supplier_reference_dimension(
            adapter, current, label=label, units=source.units,
            precision=source.diameter_precision, expected_mm=source.diameter_mm,
            presentation="diameter", callout=callout,
        )
        if int(current.Type2) != 6:
            raise RuntimeError(f"{label}: final reference is not a native diameter")
        _assert_attachments(adapter, current, (edge.edge,), label=label)
        if band is not None:
            _assert_band(
                current, lower_mm / 1000.0, upper_mm / 1000.0,
                3 if limits else 2, source.diameter_precision, label=label,
            )
        else:
            _assert_no_band(current, label=label)

    return display, assert_diameter


def _supplier_length(
    adapter: Any, view: Any, circles: list[ViewEdge], source: SupplierPinReference,
    *, axis: int, stations: tuple[float, float]
) -> tuple[Any, Callable[[Any], None]]:
    label = f"{source.sku} supplier length"
    ends = tuple(_end_circle(circles, axis, station, label=label) for station in stations)
    # Project actual end-rim points in one batch. Center arc conditions below
    # make the span end-plane to end-plane, not a tangent-offset distance.
    points = []
    for edge in ends:
        point = list(edge.circle[:3])
        point[0 if axis == 1 else 1] += edge.circle[6]
        points.append(tuple(value / 1000.0 for value in point))
    p0, p1 = model_points_in_view(adapter, view, points, label=label)
    outline = tuple(float(value) for value in view.GetOutline())
    text_xy = (
        (outline[0] - 0.010, (p0[1] + p1[1]) / 2.0)
        if axis == 1 else ((p0[0] + p1[0]) / 2.0, outline[1] - 0.010)
    )
    display = _early_bound(add_edge_dimension(
        adapter, view, p0=p0, p1=p1, text_xy=text_xy, label=label,
        orientation="vertical" if axis == 1 else "horizontal",
        entities=(ends[0].edge, ends[1].edge),
    ), "IDisplayDimension")
    if int(display.Type2) not in (2, 11, 12):
        raise RuntimeError(f"{label}: end-plane reference is not a native length")
    dimension = _early_bound(display.GetDimension2(0), "IDimension")
    for index in (1, 2):
        if dimension.SetArcEndCondition(index, 1) != 0:  # swArcEndConditionCenter
            raise RuntimeError(f"{label}: cannot center native end-rim endpoint {index}")
    display = supplier_reference_dimension(
        adapter, display, label=label, units=source.units,
        precision=source.length_precision, expected_mm=source.length_mm,
    )

    def assert_length(current: Any) -> None:
        assert_supplier_reference_dimension(
            adapter, current, label=label, units=source.units,
            precision=source.length_precision, expected_mm=source.length_mm,
        )
        if int(current.Type2) not in (2, 11, 12):
            raise RuntimeError(f"{label}: final reference is not a native length")
        native = _early_bound(current.GetDimension2(0), "IDimension")
        if any(int(native.GetArcEndCondition(index)) != 1 for index in (1, 2)):
            raise RuntimeError(f"{label}: final end-rim endpoints are not centered")
        assert_dimension_measures(
            adapter, current, expected_mm=source.length_mm, label=label,
            entities=(ends[0].edge, ends[1].edge),
        )
        _assert_no_band(current, label=label)

    assert_length(display)
    return display, assert_length


@_telemetry.traced("drawing.supplier_pin_dowel_author")
def add_supplier_dowel_dimensions(
    adapter: Any, views: dict[str, Any], source: SupplierPinReference
) -> Callable[[], None]:
    """Author native dowel references and return their post-rebuild proof."""
    front = views["*Front"]
    circles = _axis_circles(scan_view_edges(front, label=f"{source.sku} dowel"), 1, label=source.sku)
    # Dimension the real circle normal to the view, not its edge-on projection.
    top = views["*Top"]
    end_circles = _axis_circles(
        scan_view_edges(top, label=f"{source.sku} dowel end"), 1, label=source.sku
    )
    outline = tuple(float(value) for value in top.GetOutline())
    diameter, diameter_check = _supplier_diameter(
        adapter, top, end_circles, source,
        text_xy=(outline[2] + 0.018, (outline[1] + outline[3]) / 2.0),
    )
    length, length_check = _supplier_length(
        adapter, front, circles, source, axis=1, stations=(0.0, source.length_mm)
    )
    return _settled_pin_check(
        adapter, views,
        [("*Top", diameter, diameter_check), ("*Front", length, length_check)],
        expected_count=2, label=source.sku,
    )


@_telemetry.traced("drawing.supplier_pin_spring_author")
def add_supplier_spring_pin_dimensions(
    adapter: Any, views: dict[str, Any], source: SupplierPinReference
) -> Callable[[], None]:
    """Author pin/wall/application references and return post-rebuild proof."""
    if (
        source.wall_mm is None or source.wall_precision is None
        or source.application_hole_limits is None or source.application_hole_precision is None
    ):
        raise ValueError(f"{source.sku}: incomplete spring-pin source references")
    front = views["*Front"]
    circles = _axis_circles(scan_view_edges(front, label=f"{source.sku} spring pin"), 0, label=source.sku)
    right = views["*Right"]
    end_circles = _axis_circles(
        scan_view_edges(right, label=f"{source.sku} spring-pin end"), 0, label=source.sku
    )
    outline = tuple(float(value) for value in right.GetOutline())
    diameter, diameter_check = _supplier_diameter(
        adapter, right, end_circles, source,
        text_xy=(outline[2] + 0.015, outline[3] + 0.014),
    )
    length, length_check = _supplier_length(
        adapter, front, circles, source, axis=0,
        stations=(-source.length_mm / 2.0, source.length_mm / 2.0),
    )
    references = [("*Right", diameter, diameter_check), ("*Front", length, length_check)]
    # Both sketches stay part-hidden and are shown only in this orthographic
    # end view. The hole circle is offset from the pin profile and labelled
    # explicitly; its limits never attach to a pin rim or become pin OD.
    center = tuple(float(value) for value in right.Position)
    annotations = curate_view_dimensions(
        adapter, right,
        keep={
            WALL_DIMENSION: (center[0] - 0.022, center[1] + 0.018),
            MATING_HOLE_DIMENSION: (center[0] + 0.029, center[1] - 0.031),
        },
        view_label=f"{source.sku} supplier wall and mating-hole references",
        dimensions_by_feature=REFERENCE_DIMENSIONS,
    )
    imported: dict[str, Any] = {}
    for annotation in annotations:
        name = dimension_name(adapter, annotation)
        if name not in (WALL_DIMENSION, MATING_HOLE_DIMENSION) or name in imported:
            raise RuntimeError(f"{source.sku}: unexpected/duplicate source reference {name!r}")
        imported[name] = _early_bound(
            _early_bound(annotation, "IAnnotation").GetSpecificAnnotation(), "IDisplayDimension"
        )
    if set(imported) != {WALL_DIMENSION, MATING_HOLE_DIMENSION}:
        raise RuntimeError(f"{source.sku}: wall/application source references are incomplete")

    wall_label = f"{source.sku} supplier wall"
    wall = supplier_reference_dimension(
        adapter, imported[WALL_DIMENSION], label=wall_label, units=source.units,
        precision=source.wall_precision, expected_mm=source.wall_mm, callout="WALL",
    )
    wall_entities = tuple(
        _early_bound(wall.GetAnnotation(), "IAnnotation").GetAttachedEntities3() or ()
    )

    def assert_wall(current: Any) -> None:
        assert_supplier_reference_dimension(
            adapter, current, label=wall_label, units=source.units,
            precision=source.wall_precision, expected_mm=source.wall_mm, callout="WALL",
        )
        if int(current.Type2) not in (2, 11, 12):
            raise RuntimeError(f"{wall_label}: wall witness lost native linear type")
        _assert_no_band(current, label=wall_label)
        _assert_attachments(adapter, current, wall_entities, label=wall_label)

    lower, upper = source.application_hole_limits
    hole_label = f"{source.sku} supplier mating-hole application"
    hole_callout = "MATING HOLE\nSUPPLIER APPLICATION ONLY"
    hole = supplier_reference_dimension(
        adapter, imported[MATING_HOLE_DIMENSION], label=hole_label, units=source.units,
        precision=source.application_hole_precision, expected_mm=lower * source.unit_mm,
        presentation="diameter", callout=hole_callout,
    )
    hole_entities = tuple(
        _early_bound(hole.GetAnnotation(), "IAnnotation").GetAttachedEntities3() or ()
    )

    def assert_hole(current: Any) -> None:
        assert_supplier_reference_dimension(
            adapter, current, label=hole_label, units=source.units,
            precision=source.application_hole_precision, expected_mm=lower * source.unit_mm,
            presentation="diameter", callout=hole_callout,
        )
        if int(current.Type2) != 6:
            raise RuntimeError(f"{hole_label}: application circle lost native diameter type")
        _assert_attachments(adapter, current, hole_entities, label=hole_label)
        _assert_band(
            current, 0.0, (upper - lower) * source.unit_mm / 1000.0,
            3, source.application_hole_precision, label=hole_label,
        )

    assert_wall(wall)
    assert_hole(hole)
    references.extend((("*Right", wall, assert_wall), ("*Right", hole, assert_hole)))
    return _settled_pin_check(adapter, views, references, expected_count=4, label=source.sku)
