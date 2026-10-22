"""Import model-owned washer supplier bands; add only unbanded rim refs.

The part owns every banded dimension's native value, tolerance and supplier
specification. Imports get their drawing-local ink explicitly, without relying
on native import inheriting the part's display-unit flag.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any, Literal

from solidworks_mcp.adapters.solidworks.drawing import dimension_name, view_name

from _com import _early_bound
from _drawing_attachment import _is_same_attachment
from _drawing_edges import ViewEdges, scan_view_edges
from _drawing_hidden_sketches import curate_view_dimensions
from _supplier_dimensions import (
    assert_supplier_reference_dimension,
    supplier_reference_dimension,
)
from _supplier_washer_model import (
    BORE_DIAMETER,
    OUTER_DIAMETER,
    SOURCE_DIMENSIONS,
    THICKNESS,
    assert_supplier_washer_band,
    assert_supplier_washer_body,
    assert_supplier_washer_source_attachment,
    assert_supplier_washer_references,
)
import _telemetry


@dataclass(frozen=True)
class _WasherReference:
    view: Any
    selection_name: str
    full_name: str
    label: str
    expected_mm: float
    presentation: Literal["length", "diameter"]
    imported: bool
    callout: str | None = None


def _rim(
    edges: ViewEdges, *, axis: Literal["y", "z"], station_mm: float,
    diameter_mm: float, label: str,
) -> Any:
    center = (0.0, station_mm, 0.0) if axis == "y" else (0.0, 0.0, station_mm)
    normal = (0.0, 1.0, 0.0) if axis == "y" else (0.0, 0.0, 1.0)
    return edges.circle_at(
        center, diameter_mm / 2.0, axis=normal, label=label,
        center_tol_mm=1e-6, radius_tol_mm=1e-6,
    ).edge


def _assert_rim(adapter: Any, display: Any, rim: Any, *, label: str) -> None:
    annotation = _early_bound(display.GetAnnotation(), "IAnnotation")
    attached = list(annotation.GetAttachedEntities3() or ())
    if (
        len(attached) != 1 or attached[0] is None
        or not _is_same_attachment(adapter, attached[0], rim, "EDGE")
        or annotation.IsDangling() or int(annotation.Visible) != 1
    ):
        raise RuntimeError(f"{label}: native unbanded diameter lost its exact physical rim")


def _native_diameter(
    adapter: Any, view: Any, rim: Any, *, text_xy: tuple[float, float], label: str,
) -> Any:
    """The policy exception: an unbanded reference on an actual solid rim."""
    draw = adapter.currentModel
    if not _early_bound(draw, "IDrawingDoc").ActivateView(view_name(adapter, view)):
        raise RuntimeError(f"{label}: failed to activate drawing view")
    draw.ClearSelection2(True)
    manager = _early_bound(draw.SelectionManager, "ISelectionMgr")
    data = manager.CreateSelectData()
    data.View = view
    if _early_bound(rim, "IEntity").Select4(False, data) is not True:
        raise RuntimeError(f"{label}: failed to select physical rim")
    if (
        int(manager.GetSelectedObjectCount2(-1)) != 1
        or int(adapter.swApp.IsSame(manager.GetSelectedObject6(1, -1), rim)) != 1
    ):
        raise RuntimeError(f"{label}: selection is not the intended physical rim")
    display, status = _early_bound(draw.Extension, "IModelDocExtension").AddSpecificDimension(
        text_xy[0], text_xy[1], 0.0, 6, 0  # swDiameterDimension
    )
    draw.ClearSelection2(True)
    if display is None or int(status) != 0:
        raise RuntimeError(f"{label}: native diameter failed ({status})")
    display = _early_bound(display, "IDisplayDimension")
    _assert_rim(adapter, display, rim, label=label)
    return display


def _reference(
    display: Any, view: Any, label: str, expected_mm: float, *,
    imported: bool, callout: str | None = None,
) -> _WasherReference:
    selection_name = str(display.GetNameForSelection() or "")
    full_name = str(_early_bound(display.GetDimension2(0), "IDimension").FullName or "")
    if not selection_name or not full_name:
        raise RuntimeError(f"{label}: native dimension has no stable selection/full name")
    return _WasherReference(view, selection_name, full_name, label, expected_mm,
                            "length" if label == THICKNESS else "diameter", imported, callout)


def _visible_dimensions(view: Any) -> list[Any]:
    visible = []
    raw = _early_bound(view, "IView").GetFirstDisplayDimension5()
    while raw is not None:
        display = _early_bound(raw, "IDisplayDimension")
        if int(_early_bound(display.GetAnnotation(), "IAnnotation").Visible) == 1:
            visible.append(display)
        raw = display.GetNext5()
    return visible


@_telemetry.traced("drawing.assert_supplier_washer_dimensions")
def assert_supplier_washer_dimensions(
    adapter: Any, views: dict[str, Any], references: tuple[_WasherReference, ...], *,
    axis: Literal["y", "z"], bore_mm: float, outer_mm: float, thickness_mm: float,
    units: Literal["in", "mm"], precision: Mapping[str, int],
    bands: Mapping[str, tuple[float, float, str]],
) -> None:
    """Reacquire displays, source entities and final solid rims after rebuild."""
    if len(references) != 3 or {reference.label for reference in references} != {
        OUTER_DIAMETER, BORE_DIAMETER, THICKNESS,
    }:
        raise RuntimeError("supplier washer must export exactly OD, bore and thickness")
    face = views["*Top" if axis == "y" else "*Front"]
    side = views["*Front" if axis == "y" else "*Top"]
    model = _early_bound(face, "IView").ReferencedDocument
    if model is None:
        raise RuntimeError("supplier washer drawing has no referenced source part")
    assert_supplier_washer_body(model, axis=axis, bore_mm=bore_mm,
                               outer_mm=outer_mm, thickness_mm=thickness_mm)
    face_edges = scan_view_edges(face, label="settled supplier washer face rims")
    side_edges = scan_view_edges(side, label="settled supplier washer axial rims")
    # Body-backed proof remains independent of construction-sketch attachments.
    face_rims = {
        label: _rim(face_edges, axis=axis, station_mm=thickness_mm,
                    diameter_mm=diameter, label=label)
        for label, diameter in ((OUTER_DIAMETER, outer_mm), (BORE_DIAMETER, bore_mm))
    }
    for station in (0.0, thickness_mm):
        _rim(side_edges, axis=axis, station_mm=station, diameter_mm=outer_mm, label=THICKNESS)
    current: dict[str, Any] = {}
    for orientation, view in views.items():
        expected = [reference for reference in references
                    if int(adapter.swApp.IsSame(reference.view, view)) == 1]
        visible = _visible_dimensions(view)
        required_count = 2 if orientation == ("*Top" if axis == "y" else "*Front") else (
            1 if orientation == ("*Front" if axis == "y" else "*Top") else 0
        )
        if len(expected) != required_count or len(visible) != required_count:
            raise RuntimeError(f"supplier washer {orientation} exports {len(visible)} dimensions, expected {required_count}")
        for reference in expected:
            matches = [display for display in visible
                       if str(display.GetNameForSelection() or "") == reference.selection_name]
            if len(matches) != 1:
                raise RuntimeError(f"{reference.label}: settled native display census failed")
            display = matches[0]
            native = _early_bound(display.GetDimension2(0), "IDimension")
            if str(native.FullName or "") != reference.full_name:
                raise RuntimeError(f"{reference.label}: settled display resolves to another native dimension")
            current[reference.label] = display
    for reference in references:
        display = current[reference.label]
        assert_supplier_reference_dimension(
            adapter, display, label=reference.label, units=units,
            precision=precision[reference.label], expected_mm=reference.expected_mm,
            presentation=reference.presentation, callout=reference.callout,
        )
        if reference.imported:
            assert_supplier_washer_source_attachment(
                adapter, model, display, label=reference.label, axis=axis,
                bore_mm=bore_mm, outer_mm=outer_mm, thickness_mm=thickness_mm,
                view=reference.view,
            )
        else:
            _assert_rim(adapter, display, face_rims[reference.label], label=reference.label)
        assert_supplier_washer_band(
            display, nominal_mm=reference.expected_mm, band=bands.get(reference.label),
            precision=precision[reference.label], label=reference.label,
        )
    assert_supplier_washer_references(
        adapter, model, axis=axis, bore_mm=bore_mm, outer_mm=outer_mm,
        thickness_mm=thickness_mm, units=units, precision=precision,
        bands=bands, bore_callout=next(
            reference.callout for reference in references if reference.label == BORE_DIAMETER
        ),
    )


@_telemetry.traced("drawing.supplier_washer_dimensions")
def supplier_washer_dimensions(
    adapter: Any, views: dict[str, Any], *, axis: Literal["y", "z"],
    bore_mm: float, outer_mm: float, thickness_mm: float, units: Literal["in", "mm"],
    precision: Mapping[str, int], bands: Mapping[str, tuple[float, float, str]],
    bore_callout: str | None = None,
) -> Callable[[], None]:
    """Import every banded size; author only bandless OD/ID physical refs."""
    if set(bands) not in ({THICKNESS}, {OUTER_DIAMETER, BORE_DIAMETER, THICKNESS}):
        raise ValueError("unsupported washer supplier band coverage")
    # The purchased-sheet source checkpoint has already proved this view's
    # referenced document/path against the original read-only source.
    model = _early_bound(views["*Front"], "IView").ReferencedDocument
    if model is None:
        raise RuntimeError("supplier washer drawing has no referenced source part")
    assert_supplier_washer_body(
        model, axis=axis, bore_mm=bore_mm, outer_mm=outer_mm, thickness_mm=thickness_mm,
    )
    assert_supplier_washer_references(
        adapter, model, axis=axis, bore_mm=bore_mm, outer_mm=outer_mm,
        thickness_mm=thickness_mm, units=units, precision=precision,
        bands=bands, bore_callout=bore_callout,
    )
    face = views["*Top" if axis == "y" else "*Front"]
    side = views["*Front" if axis == "y" else "*Top"]
    bounds = tuple(float(value) for value in face.GetOutline())
    center_y = (bounds[1] + bounds[3]) / 2.0
    positions = {
        OUTER_DIAMETER: (bounds[2] + 0.012, center_y + 0.012),
        BORE_DIAMETER: (bounds[2] + 0.012, center_y - 0.012),
    }
    side_bounds = tuple(float(value) for value in side.GetOutline())
    positions[THICKNESS] = (side_bounds[2] + 0.014, (side_bounds[1] + side_bounds[3]) / 2.0)
    values = {OUTER_DIAMETER: outer_mm, BORE_DIAMETER: bore_mm, THICKNESS: thickness_mm}
    references: list[_WasherReference] = []
    for view, labels in ((face, (OUTER_DIAMETER, BORE_DIAMETER)), (side, (THICKNESS,))):
        imported_labels = tuple(label for label in labels if label in bands)
        if not imported_labels:
            continue
        annotations = curate_view_dimensions(
            adapter, view,
            keep={SOURCE_DIMENSIONS[label][1]: positions[label] for label in imported_labels},
            view_label="supplier washer face" if view is face else "supplier washer thickness",
            dimensions_by_feature={
                SOURCE_DIMENSIONS[label][0]: tuple(SOURCE_DIMENSIONS[item][1]
                                                  for item in imported_labels
                                                  if SOURCE_DIMENSIONS[item][0] == SOURCE_DIMENSIONS[label][0])
                for label in imported_labels
            },
        )
        named = {dimension_name(adapter, annotation): annotation for annotation in annotations}
        for label in imported_labels:
            annotation = named[SOURCE_DIMENSIONS[label][1]]
            display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
            # Import uses drawing-local display settings. Dress that display,
            # never its source value or tolerance; recheck both part and import.
            supplier_reference_dimension(
                adapter, display, label=label, units=units, precision=precision[label],
                expected_mm=values[label], presentation="length" if label == THICKNESS else "diameter",
                callout=bore_callout if label == BORE_DIAMETER else None,
            )
            references.append(_reference(display, view, label, values[label], imported=True,
                                         callout=bore_callout if label == BORE_DIAMETER else None))
            assert_supplier_washer_band(
                display, nominal_mm=values[label], band=bands[label],
                precision=precision[label], label=label,
            )
    assert_supplier_washer_references(
        adapter, model, axis=axis, bore_mm=bore_mm, outer_mm=outer_mm,
        thickness_mm=thickness_mm, units=units, precision=precision,
        bands=bands, bore_callout=bore_callout,
    )
    unbanded = tuple(label for label in (OUTER_DIAMETER, BORE_DIAMETER) if label not in bands)
    if unbanded:
        edges = scan_view_edges(face, label="supplier washer unbanded face rims")
        for label in unbanded:
            rim = _rim(edges, axis=axis, station_mm=thickness_mm,
                       diameter_mm=values[label], label=label)
            display = _native_diameter(adapter, face, rim, text_xy=positions[label], label=label)
            display = supplier_reference_dimension(
                adapter, display, label=label, units=units, precision=precision[label],
                expected_mm=values[label], presentation="diameter",
                callout=bore_callout if label == BORE_DIAMETER else None,
            )
            references.append(_reference(display, face, label, values[label], imported=False,
                                         callout=bore_callout if label == BORE_DIAMETER else None))

    def settled_check() -> None:
        assert_supplier_washer_dimensions(
            adapter, views, tuple(references), axis=axis, bore_mm=bore_mm,
            outer_mm=outer_mm, thickness_mm=thickness_mm, units=units,
            precision=precision, bands=bands,
        )

    return settled_check
