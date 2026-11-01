"""Native supplier references for Y-axis dowels and X-axis spring pins.

Model-owned values, bands and witnesses remain read-only. Imported drawing
displays receive explicit presentation after independent source validation.
Nothing here sets a SystemValue or replaces numeric dimension text.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable
from typing import Any

from solidworks_mcp.adapters.solidworks.drawing import dimension_name, view_name

import _telemetry
from _com import _early_bound
from _drawing_edge_dimensions import add_edge_dimension, assert_dimension_measures
from _drawing_edges import ViewEdge, ViewEdges, scan_view_edges
from _drawing_hidden_sketches import curate_view_dimensions
from _drawing_projection import model_points_in_view
from _drawing_precision import _named_dimensions
from _supplier_dimensions import (
    assert_supplier_reference_dimension,
    sheet_units,
    supplier_reference_dimension,
)
from _supplier_pin_data import (
    DIAMETER_DIMENSION,
    MATING_HOLE_DIMENSION,
    REFERENCE_DIMENSIONS,
    WALL_DIMENSION,
    SupplierPinReference,
    declares_application_hole,
)
from _supplier_pin_model import _reference_contract, assert_supplier_pin_model_reference
from _supplier_text_shelf import assert_supplier_shelves, shelve_supplier_text


# Planned sheet-space lanes (left, bottom, right, top), before the first fit.
# Only annotated views are listed. The application diagram's extra geometry
# is <=38.05 mm right of the tube at the builder's maximum 8:1 scale.
DOWEL_SUPPLIER_MARGINS = {
    "*Front": (0.035, 0.006, 0.004, 0.006),
    "*Top": (0.003, 0.018, 0.075, 0.012),
}
# The spring pin's FRONT right lane holds its length text's shelf: about 21 mm
# of "(0.625 in)" plus the 2.2 mm shelf gap past the right end witness.
SPRING_PIN_SUPPLIER_MARGINS = {
    "*Front": (0.004, 0.024, 0.030, 0.004),
    "*Right": (0.040, 0.055, 0.095, 0.028),
}


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
            if int(annotation.Visible) != 1:
                raise RuntimeError(f"{label}: final supplier reference {name} is not visible")
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
    if source.diameter_band is not None:
        raise ValueError(f"{source.sku}: banded OD must be imported from its model owner")
    label = f"{source.sku} supplier diameter"
    edge = _outer_circle(circles, source.diameter_mm, label=label)
    display = _diameter_dimension(adapter, view, edge, text_xy, label=label)
    display = supplier_reference_dimension(
        adapter, display, label=label, units=source.units,
        precision=source.diameter_precision, expected_mm=source.diameter_mm,
        presentation="diameter",
    )

    def assert_diameter(current: Any) -> None:
        assert_supplier_reference_dimension(
            adapter, current, label=label, units=source.units,
            precision=source.diameter_precision, expected_mm=source.diameter_mm,
            presentation="diameter",
        )
        if int(current.Type2) != 6:
            raise RuntimeError(f"{label}: final reference is not a native diameter")
        _assert_attachments(adapter, current, (edge.edge,), label=label)
        _assert_no_band(current, label=label)

    return display, assert_diameter


def _supplier_length(
    adapter: Any, view: Any, circles: list[ViewEdge], source: SupplierPinReference,
    *, axis: int, stations: tuple[float, float],
) -> tuple[Any, Callable[[Any], None]]:
    label = f"{source.sku} supplier length"
    ends = tuple(_end_circle(circles, axis, station, label=label) for station in stations)
    # Each rim lies in a plane normal to the measured axis. Its axial
    # coordinate is constant, so this linear dimension measures the full
    # end-plane separation without applying an arc-length endpoint mode.
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
        if any(int(native.GetArcEndCondition(index)) != 0 for index in (1, 2)):
            raise RuntimeError(f"{label}: final end-rim conditions are not linear")
        assert_dimension_measures(
            adapter, current, expected_mm=source.length_mm, label=label,
            entities=(ends[0].edge, ends[1].edge),
        )
        _assert_no_band(current, label=label)

    assert_length(display)
    return display, assert_length


def _import_model_references(
    adapter: Any, view: Any, source: SupplierPinReference,
    keep: dict[str, tuple[float, float]],
) -> dict[str, tuple[Any, Callable[[Any], None]]]:
    model = view.ReferencedDocument
    if model is None or model == "":
        raise RuntimeError(f"{source.sku}: imported references have no source part")
    # The part wrote its reference suffix for source.sheet_unit.
    if sheet_units(adapter) != source.sheet_unit:
        raise RuntimeError(
            f"{source.sku}: sheet unit {sheet_units(adapter)} != source sheet_unit "
            f"{source.sheet_unit}"
        )
    owners = {name: feature for feature, names in REFERENCE_DIMENSIONS.items() for name in names}
    if set(keep) - owners.keys():
        raise ValueError(f"{source.sku}: unknown required model reference")
    source_displays = []
    for name in keep:
        feature_name = owners[name]
        feature = _early_bound(model, "IPartDoc").FeatureByName(feature_name)
        if feature is None:
            raise RuntimeError(f"{source.sku}: missing model reference {feature_name}")
        display, _ = _named_dimensions(adapter, feature_name, {name}, feature=feature)[name]
        source_displays.append((display, feature_name))

    def assert_sources() -> None:
        for display, feature in source_displays:
            assert_supplier_pin_model_reference(
                adapter, model, display, feature, source, view=None,
            )

    assert_sources()
    annotations = curate_view_dimensions(
        adapter, view, keep=keep, view_label=f"{source.sku} model-owned supplier references",
        dimensions_by_feature=REFERENCE_DIMENSIONS,
    )
    imported: dict[str, tuple[Any, Callable[[Any], None]]] = {}
    for raw in annotations:
        name = dimension_name(adapter, raw)
        if name not in keep or name in imported:
            raise RuntimeError(f"{source.sku}: unexpected/duplicate model reference {name!r}")
        display = _early_bound(
            _early_bound(raw, "IAnnotation").GetSpecificAnnotation(), "IDisplayDimension"
        )
        feature = owners[name]
        _, kwargs, band = _reference_contract(source, feature)
        display = supplier_reference_dimension(adapter, display, **kwargs)
        if band is not None and display.SetPrecision3(
            kwargs["precision"], -1, kwargs["precision"], -1,
        ) != 0:
            raise RuntimeError(f"{source.sku}: imported tolerance display precision was rejected")

        def assert_imported(current: Any, *, feature: str = feature) -> None:
            referenced = view.ReferencedDocument
            if referenced is None or int(adapter.swApp.IsSame(referenced, model)) != 1:
                raise RuntimeError(f"{source.sku}: imported reference changed its source part")
            assert_supplier_pin_model_reference(
                adapter, model, current, feature, source, view=view,
            )
            assert_sources()

        assert_imported(display)
        imported[name] = (display, assert_imported)
    if set(imported) != set(keep):
        raise RuntimeError(f"{source.sku}: required model-owned references are incomplete")
    return imported


@_telemetry.traced("drawing.supplier_pin_dowel_author")
def add_supplier_dowel_dimensions(
    adapter: Any, views: dict[str, Any], source: SupplierPinReference
) -> Callable[[], None]:
    """Import source-owned OD/band; author only the bandless end-rim length."""
    front = views["*Front"]
    circles = _axis_circles(scan_view_edges(front, label=f"{source.sku} dowel"), 1, label=source.sku)
    length, length_check = _supplier_length(
        adapter, front, circles, source, axis=1, stations=(0.0, source.length_mm),
    )
    top = views["*Top"]
    outline = tuple(float(value) for value in top.GetOutline())
    imported = _import_model_references(
        adapter, top, source,
        {DIAMETER_DIMENSION: (outline[2] + 0.033, (outline[1] + outline[3]) / 2.0)},
    )
    diameter, diameter_check = imported[DIAMETER_DIMENSION]
    return _settled_pin_check(
        adapter, views,
        [("*Top", diameter, diameter_check), ("*Front", length, length_check)],
        expected_count=2, label=source.sku,
    )


@_telemetry.traced("drawing.supplier_pin_spring_author")
def add_supplier_spring_pin_dimensions(
    adapter: Any, views: dict[str, Any], source: SupplierPinReference
) -> Callable[[], None]:
    """Import wall and any application hole read-only; author only bandless OD and length."""
    if source.wall_mm is None or source.wall_precision is None:
        raise ValueError(f"{source.sku}: incomplete spring-pin source references")
    application_hole = declares_application_hole(source)
    front = views["*Front"]
    circles = _axis_circles(scan_view_edges(front, label=f"{source.sku} spring pin"), 0, label=source.sku)
    right = views["*Right"]
    end_circles = _axis_circles(
        scan_view_edges(right, label=f"{source.sku} spring-pin end"), 0, label=source.sku
    )
    outline = tuple(float(value) for value in right.GetOutline())
    # Below left of the end view: the WALL text sits up-left with its line
    # over the rim and any mating hole's diagram and label sit right, so the
    # Ø leader crosses neither (machinist review of dt_vn_pinion_strap_pin:
    # up-right, it crossed the WALL line at its arrowhead).
    diameter, diameter_check = _supplier_diameter(
        adapter, right, end_circles, source,
        text_xy=(outline[0] - 0.015, outline[1] - 0.014),
    )
    length, length_check = _supplier_length(
        adapter, front, circles, source, axis=0,
        stations=(-source.length_mm / 2.0, source.length_mm / 2.0),
    )
    center = tuple(float(value) for value in right.Position)
    keep = {WALL_DIMENSION: (center[0] - 0.022, center[1] + 0.018)}
    if application_hole:
        keep[MATING_HOLE_DIMENSION] = (center[0] + 0.064, center[1] - 0.031)
    imported = _import_model_references(adapter, right, source, keep)
    wall, wall_check = imported[WALL_DIMENSION]
    references = [
        ("*Right", diameter, diameter_check), ("*Front", length, length_check),
        ("*Right", wall, wall_check),
    ]
    if application_hole:
        hole, hole_check = imported[MATING_HOLE_DIMENSION]
        references.append(("*Right", hole, hole_check))
    # Centred on its horizontal dimension line, the FRONT length text sits on
    # it and the line runs through the bottoms of its parentheses (machinist
    # review: the strap pin's "(.500)", the knob-cup pin's "(0.625 in)").
    # Shelve it right of its end witnesses, toward the open space before RIGHT.
    length_name = str(_early_bound(length.GetDimension2(0), "IDimension").FullName)
    shelved = {length_name: length}
    shelves = {length_name: (True, "right")}
    stations = shelve_supplier_text(adapter, shelved, shelves)
    settled = _settled_pin_check(
        adapter, views, references,
        expected_count=4 if application_hole else 3, label=source.sku,
    )

    def assert_settled() -> None:
        settled()
        assert_supplier_shelves(adapter, shelved, shelves, stations)

    return assert_settled
