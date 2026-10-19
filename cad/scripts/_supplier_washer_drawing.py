"""Native supplier reference dimensions on the five purchased washer sheets.

The source nominal and the representative solid are not always identical.
Limits are authored as native deviations about the unchanged measured solid;
no text or dimension-value override substitutes a supplier printed number.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
import math
from typing import Any, Literal

from solidworks_mcp.adapters.solidworks.drawing import view_name

from _com import _early_bound
from _drawing_attachment import _is_same_attachment
from _drawing_edge_dimensions import assert_dimension_measures
from _drawing_edges import ViewEdges, scan_view_edges
from _drawing_projection import model_points_in_view
from _supplier_dimensions import (
    assert_supplier_reference_dimension,
    supplier_reference_dimension,
)
import _telemetry


OUTER_DIAMETER = "supplier outer diameter"
BORE_DIAMETER = "supplier bore diameter"
THICKNESS = "supplier thickness"


@dataclass(frozen=True)
class _WasherReference:
    display: Any
    view: Any
    label: str
    expected_mm: float
    presentation: Literal["length", "diameter"]
    edges: tuple[Any, ...]
    callout: str | None = None


def _rim(
    edges: ViewEdges,
    *,
    axis: Literal["y", "z"],
    station_mm: float,
    diameter_mm: float,
    label: str,
) -> Any:
    center = (0.0, station_mm, 0.0) if axis == "y" else (0.0, 0.0, station_mm)
    normal = (0.0, 1.0, 0.0) if axis == "y" else (0.0, 0.0, 1.0)
    return edges.circle_at(
        center,
        diameter_mm / 2.0,
        axis=normal,
        label=label,
        center_tol_mm=1e-5,
        radius_tol_mm=1e-5,
    ).edge


def _assert_rims(
    adapter: Any, display: Any, edges: tuple[Any, ...], *, label: str
) -> None:
    annotation = _early_bound(display.GetAnnotation(), "IAnnotation")
    attached = list(annotation.GetAttachedEntities3() or ())
    for edge in edges:
        match = next(
            (
                index
                for index, item in enumerate(attached)
                if item is not None and _is_same_attachment(adapter, item, edge, "EDGE")
            ),
            None,
        )
        if match is None:
            raise RuntimeError(f"{label}: native dimension lost its requested rim")
        attached.pop(match)
    if attached or annotation.IsDangling() or int(annotation.Visible) != 1:
        raise RuntimeError(f"{label}: unexpected, hidden or dangling native attachments")


def _native_dimension(
    adapter: Any,
    view: Any,
    edges: tuple[Any, ...],
    *,
    text_xy: tuple[float, float],
    dimension_type: int,
    label: str,
    landings: list[tuple[float, float]] | None = None,
) -> Any:
    """Select actual rims by identity, not a graphics-window coordinate hit."""
    draw = adapter.currentModel
    if not _early_bound(draw, "IDrawingDoc").ActivateView(view_name(adapter, view)):
        raise RuntimeError(f"{label}: failed to activate drawing view")
    draw.ClearSelection2(True)
    manager = _early_bound(draw.SelectionManager, "ISelectionMgr")
    for index, edge in enumerate(edges, 1):
        data = manager.CreateSelectData()
        data.View = view
        if _early_bound(edge, "IEntity").Select4(index > 1, data) is not True:
            raise RuntimeError(f"{label}: failed to select rim {index}")
        selected = manager.GetSelectedObject6(index, -1)
        if (
            int(manager.GetSelectedObjectCount2(-1)) != index
            or int(adapter.swApp.IsSame(selected, edge)) != 1
        ):
            raise RuntimeError(f"{label}: selection is not the requested rim {index}")
        if landings is not None:
            x, y = landings[index - 1]
            if manager.SetSelectionPoint2(index, -1, x, y, 0.0) is not True:
                raise RuntimeError(f"{label}: failed to set rim landing {index}")
    # IModelDocExtension.AddSpecificDimension: early-bound [out] Error.
    display, status = _early_bound(draw.Extension, "IModelDocExtension").AddSpecificDimension(
        text_xy[0], text_xy[1], 0.0, dimension_type, 0
    )
    draw.ClearSelection2(True)
    if display is None or int(status) != 0:
        raise RuntimeError(f"{label}: native dimension failed ({status})")
    display = _early_bound(display, "IDisplayDimension")
    if len(edges) == 2:
        native = _early_bound(display.GetDimension2(0), "IDimension")
        for endpoint in (1, 2):
            # Measure the axial distance between rim centres, never the
            # nearest/farthest points chosen by automatic arc inference.
            if (
                int(native.SetArcEndCondition(endpoint, 1)) != 0
                or int(native.GetArcEndCondition(endpoint)) != 1
            ):
                raise RuntimeError(f"{label}: end {endpoint} is not rim-centred")
    _assert_rims(adapter, display, edges, label=label)
    return display


def _supplier_band(
    display: Any,
    *,
    nominal_mm: float,
    band: tuple[float, float, str],
    precision: int,
    label: str,
) -> None:
    """Preserve exact source limits in SI, independently of display precision."""
    lower_mm, upper_mm, style = band
    if not all(map(math.isfinite, (lower_mm, upper_mm))) or lower_mm >= upper_mm:
        raise ValueError(f"{label}: invalid supplier interval {band!r}")
    tolerance_type = {"bilateral": 2, "limits": 3, "symmetric": 4}[style]
    lower_m = (lower_mm - nominal_mm) / 1000.0
    upper_m = (upper_mm - nominal_mm) / 1000.0
    if style == "symmetric" and not math.isclose(
        -lower_m, upper_m, rel_tol=0.0, abs_tol=1e-12
    ):
        raise ValueError(f"{label}: symmetric band is not centred on its native value")
    native = _early_bound(display.GetDimension2(0), "IDimension")
    tolerance = _early_bound(native.Tolerance, "IDimensionTolerance")
    tolerance.Type = tolerance_type
    # The repository's exercised SetValues path stores deviations in metres.
    if not tolerance.SetValues(lower_m, upper_m):
        raise RuntimeError(f"{label}: native supplier tolerance values were rejected")
    display.SetPrecision3(-1, -1, precision, -1)
    _assert_supplier_band(
        display, nominal_mm=nominal_mm, band=band, precision=precision, label=label
    )


def _assert_supplier_band(
    display: Any,
    *,
    nominal_mm: float,
    band: tuple[float, float, str] | None,
    precision: int,
    label: str,
) -> None:
    native = _early_bound(display.GetDimension2(0), "IDimension")
    tolerance = _early_bound(native.Tolerance, "IDimensionTolerance")
    if band is None:
        if int(tolerance.Type) != 0:  # swTolNONE
            raise RuntimeError(f"{label}: unexpected native supplier tolerance")
        return
    lower_mm, upper_mm, style = band
    tolerance_type = {"bilateral": 2, "limits": 3, "symmetric": 4}[style]
    lower_m = (lower_mm - nominal_mm) / 1000.0
    upper_m = (upper_mm - nominal_mm) / 1000.0
    if (
        int(tolerance.Type) != tolerance_type
        or not math.isclose(
            float(tolerance.GetMinValue()), lower_m, rel_tol=0.0, abs_tol=1e-12
        )
        or not math.isclose(
            float(tolerance.GetMaxValue()), upper_m, rel_tol=0.0, abs_tol=1e-12
        )
        or int(display.GetPrimaryTolPrecision2()) != precision
    ):
        raise RuntimeError(f"{label}: native supplier tolerance readback differs from source")


@_telemetry.traced("drawing.assert_supplier_washer_dimensions")
def assert_supplier_washer_dimensions(
    adapter: Any,
    views: dict[str, Any],
    references: tuple[_WasherReference, ...],
    *,
    units: Literal["in", "mm"],
    precision: Mapping[str, int],
    bands: Mapping[str, tuple[float, float, str]],
) -> None:
    """Read only: prove the three exported references after the final rebuild."""
    if len(references) != 3:
        raise RuntimeError("supplier washer must export exactly OD, bore and thickness")
    for view in views.values():
        expected = [
            reference
            for reference in references
            if int(adapter.swApp.IsSame(reference.view, view)) == 1
        ]
        visible = []
        raw = _early_bound(view, "IView").GetFirstDisplayDimension5()
        while raw is not None:
            display = _early_bound(raw, "IDisplayDimension")
            if int(_early_bound(display.GetAnnotation(), "IAnnotation").Visible) == 1:
                visible.append(display)
            raw = display.GetNext5()
        if len(visible) != len(expected):
            raise RuntimeError(
                f"supplier washer {view_name(adapter, view)} exports "
                f"{len(visible)} dimensions, expected {len(expected)}"
            )
        for reference in expected:
            matches = sum(
                int(adapter.swApp.IsSame(display, reference.display)) == 1
                for display in visible
            )
            if matches != 1:
                raise RuntimeError(f"{reference.label}: exported dimension census failed")
    for reference in references:
        assert_supplier_reference_dimension(
            adapter,
            reference.display,
            label=reference.label,
            units=units,
            precision=precision[reference.label],
            expected_mm=reference.expected_mm,
            presentation=reference.presentation,
            callout=reference.callout,
        )
        _assert_rims(
            adapter, reference.display, reference.edges, label=reference.label
        )
        _assert_supplier_band(
            reference.display,
            nominal_mm=reference.expected_mm,
            band=bands.get(reference.label),
            precision=precision[reference.label],
            label=reference.label,
        )
        if reference.label == THICKNESS:
            native = _early_bound(reference.display.GetDimension2(0), "IDimension")
            if any(int(native.GetArcEndCondition(end)) != 1 for end in (1, 2)):
                raise RuntimeError("supplier thickness lost its rim-centre conditions")


@_telemetry.traced("drawing.supplier_washer_dimensions")
def supplier_washer_dimensions(
    adapter: Any,
    views: dict[str, Any],
    *,
    axis: Literal["y", "z"],
    bore_mm: float,
    outer_mm: float,
    thickness_mm: float,
    units: Literal["in", "mm"],
    precision: Mapping[str, int],
    bands: Mapping[str, tuple[float, float, str]],
    bore_callout: str | None = None,
) -> Callable[[], None]:
    """Dimension the actual bore/OD rims and the two physical axial end rims."""
    face = views["*Top" if axis == "y" else "*Front"]
    side = views["*Front" if axis == "y" else "*Right"]
    face_edges = scan_view_edges(face, label="supplier washer end face")
    side_edges = scan_view_edges(side, label="supplier washer thickness")
    references: list[_WasherReference] = []
    bounds = tuple(float(value) for value in face.GetOutline())
    center_y = (bounds[1] + bounds[3]) / 2.0
    for label, diameter, offset in (
        (OUTER_DIAMETER, outer_mm, 0.012),
        (BORE_DIAMETER, bore_mm, -0.012),
    ):
        rim = _rim(
            face_edges, axis=axis, station_mm=thickness_mm,
            diameter_mm=diameter, label=label,
        )
        display = _native_dimension(
            adapter, face, (rim,),
            text_xy=(bounds[2] + 0.012, center_y + offset),
            dimension_type=6,  # swDiameterDimension
            label=label,
        )
        display = supplier_reference_dimension(
            adapter, display, label=label, units=units,
            precision=precision[label], expected_mm=diameter,
            presentation="diameter",
            callout=bore_callout if label == BORE_DIAMETER else None,
        )
        if label in bands:
            _supplier_band(
                display, nominal_mm=diameter, band=bands[label],
                precision=precision[label], label=label,
            )
        references.append(
            _WasherReference(
                display, face, label, diameter, "diameter", (rim,),
                bore_callout if label == BORE_DIAMETER else None,
            )
        )
    rims = tuple(
        _rim(
            side_edges, axis=axis, station_mm=station,
            diameter_mm=outer_mm, label=THICKNESS,
        )
        for station in (0.0, thickness_mm)
    )
    # Points are on each actual outer circle; in the side projection both lie
    # on the same flank. The explicit selection points prevent arc-centre/tangent
    # inference from turning the end-to-end distance into a different dimension.
    points_mm = (
        [(outer_mm / 2.0, station, 0.0) for station in (0.0, thickness_mm)]
        if axis == "y"
        else [(0.0, -outer_mm / 2.0, station) for station in (0.0, thickness_mm)]
    )
    landings = model_points_in_view(
        adapter, side,
        [tuple(value / 1000.0 for value in point) for point in points_mm],
        label=THICKNESS,
    )
    horizontal = abs(landings[1][0] - landings[0][0]) > abs(
        landings[1][1] - landings[0][1]
    )
    side_bounds = tuple(float(value) for value in side.GetOutline())
    display = _native_dimension(
        adapter, side, rims,
        text_xy=(side_bounds[2] + 0.014, (side_bounds[1] + side_bounds[3]) / 2.0),
        dimension_type=11 if horizontal else 12,  # native horizontal/vertical length
        label=THICKNESS,
        landings=landings,
    )
    assert_dimension_measures(
        adapter, display, expected_mm=thickness_mm, label=THICKNESS, entities=rims,
    )
    display = supplier_reference_dimension(
        adapter, display, label=THICKNESS, units=units,
        precision=precision[THICKNESS], expected_mm=thickness_mm,
    )
    if THICKNESS in bands:
        _supplier_band(
            display, nominal_mm=thickness_mm, band=bands[THICKNESS],
            precision=precision[THICKNESS], label=THICKNESS,
        )
    references.append(
        _WasherReference(display, side, THICKNESS, thickness_mm, "length", rims)
    )

    def settled_check() -> None:
        assert_supplier_washer_dimensions(
            adapter,
            views,
            tuple(references),
            units=units,
            precision=precision,
            bands=bands,
        )

    return settled_check
