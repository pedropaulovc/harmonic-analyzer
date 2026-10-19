"""Create the purchased reference drawing for the thumb screw."""

from __future__ import annotations

import argparse
import math
import sys
from typing import Any

from solidworks_mcp.adapters.solidworks.drawing import iter_views

import _telemetry
from _session import run_build
from _drawing_registry import DRAWINGS_BY_NAME
from _com import _early_bound
from _drawing_edge_dimensions import add_edge_dimension, assert_dimension_measures
from _drawing_edges import scan_view_edges, visible_view_entities
from _drawing_projection import model_points_in_view
import _mcmaster_91882a221 as thumb
from _purchased_fastener_drawing import build_purchased_fastener_drawing
from _supplier_dimensions import (
    assert_supplier_reference_dimension,
    supplier_reference_dimension,
)
import vn_thumb_screw_spec as supplier


SPEC = DRAWINGS_BY_NAME["vn_thumb_screw"]
# The footer's ITEM row: the catalogue designation in plain text.
ITEM = "#4-40 x 7/16 RAISED KNURLED-HEAD THUMB SCREW"


def _station_circle(edges: Any, station_mm: float, *, label: str) -> Any:
    """A physical rim in a finished axial face, including a chamfered rim.

    All fragments in the selected plane share the same axial station; the
    largest remaining circle avoids small thread/knurl cutter intersections.
    Its radius is not used as a nominal diameter.
    """
    circles = [
        item
        for item in edges.circles
        if abs(item.circle[0] - station_mm) < 1e-5
        and abs(item.circle[1]) < 1e-5
        and abs(item.circle[2]) < 1e-5
        and abs(abs(item.circle[3]) - 1.0) < 1e-6
    ]
    if not circles:
        raise RuntimeError(f"{label}: no physical circular rim at X={station_mm:g} mm")
    return max(circles, key=lambda item: item.circle[6]).edge


def _diameter_flanks(
    adapter: Any, view: Any, *, center_y: float
) -> dict[str, tuple[Any, Any]]:
    """Measure actual cylindrical envelope flanks, not helical edge radii.

    The full-detail model retains narrow major-diameter thread crests and
    knurled head lands. Their analytic cylindrical silhouettes still measure
    the supplier envelopes. One native silhouette scan serves all three sizes.
    """
    radii = {
        "head_diameter": thumb.HEAD_DIA / 2000.0,
        "collar_diameter": thumb.COLLAR_DIA / 2000.0,
        "thread_diameter": thumb.SHANK_DIA / 2000.0,
    }
    candidates = []
    for raw in visible_view_entities(view, 4, label="thumb supplier envelope flanks"):
        silhouette = _early_bound(raw, "ISilhouetteEdge")
        face = silhouette.GetFace()
        if face is None:
            continue
        surface = _early_bound(face, "IFace2").GetSurface()
        if surface is None:
            continue
        surface = _early_bound(surface, "ISurface")
        if not surface.IsCylinder():
            continue
        radius = float(surface.CylinderParams[6])
        matches = [
            name for name, expected in radii.items() if abs(radius - expected) < 1e-8
        ]
        if not matches:
            continue
        curve = silhouette.GetCurve()
        if curve is None or not _early_bound(curve, "ICurve").IsLine():
            continue
        points = []
        for member in ("GetStartPoint", "GetEndPoint"):
            point = getattr(silhouette, member)()
            if point is None:
                raise RuntimeError("thumb supplier silhouette has no native endpoint")
            points.append(tuple(_early_bound(point, "IMathPoint").ArrayData))
        candidates.append((matches[0], raw, points))
    projected = model_points_in_view(
        adapter,
        view,
        [point for _name, _entity, points in candidates for point in points],
        label="thumb supplier flank endpoints",
    )
    ratio = tuple(float(value) for value in view.ScaleRatio)
    scale = ratio[0] / ratio[1]
    flanks: dict[str, dict[int, tuple[float, Any]]] = {name: {} for name in radii}
    for index, (name, entity, _points) in enumerate(candidates):
        first, second = projected[2 * index : 2 * index + 2]
        y = (first[1] + second[1]) / 2.0
        if abs(first[1] - second[1]) > 1e-7:
            continue
        if abs(abs(y - center_y) - radii[name] * scale) > 1e-7:
            continue
        side = 1 if y > center_y else -1
        length = math.dist(first, second)
        previous = flanks[name].get(side)
        if previous is None or length > previous[0]:
            flanks[name][side] = (length, entity)
    result = {}
    for name, sides in flanks.items():
        if set(sides) != {-1, 1}:
            raise RuntimeError(
                f"{name}: missing actual upper/lower cylindrical envelope"
            )
        result[name] = (sides[-1][1], sides[1][1])
    return result


def _supplier_name(name: str) -> str:
    return "Supplier" + "".join(word.title() for word in name.split("_"))


def _name_supplier_dimension(display: Any, name: str) -> None:
    native = _early_bound(
        _early_bound(display, "IDisplayDimension").GetDimension2(0), "IDimension"
    )
    native.Name = _supplier_name(name)
    if str(native.FullName).split("@", 1)[0] != _supplier_name(name):
        raise RuntimeError(f"{name}: supplier dimension name did not persist")


def _assert_physical_rims(display: Any, stations: tuple[float, float]) -> None:
    """Reacquire final attachments and prove their physical finished planes."""
    annotation = _early_bound(display.GetAnnotation(), "IAnnotation")
    attached = tuple(annotation.GetAttachedEntities3() or ())
    if len(attached) != 2:
        raise RuntimeError("thumb axial reference must retain two physical rims")
    actual = []
    for raw in attached:
        curve = _early_bound(raw, "IEdge").GetCurve()
        if curve is None:
            raise RuntimeError("thumb axial reference no longer attaches to a rim")
        curve = _early_bound(curve, "ICurve")
        if not curve.IsCircle():
            raise RuntimeError("thumb axial reference no longer attaches to a rim")
        values = tuple(float(value) for value in curve.CircleParams)
        if (
            abs(values[1]) > 1e-8
            or abs(values[2]) > 1e-8
            or abs(abs(values[3]) - 1.0) > 1e-6
        ):
            raise RuntimeError("thumb axial reference left its coaxial finished plane")
        actual.append(values[0] * 1000.0)
    if any(
        abs(value - expected) > 1e-5
        for value, expected in zip(sorted(actual), sorted(stations), strict=True)
    ):
        raise RuntimeError("thumb axial reference attaches to the wrong finished faces")


def _assert_physical_diameter(
    adapter: Any, view: Any, display: Any, expected_mm: float
) -> None:
    """Read fresh attached silhouettes, never reuse a pre-rebuild scan handle."""
    annotation = _early_bound(display.GetAnnotation(), "IAnnotation")
    attached = tuple(annotation.GetAttachedEntities3() or ())
    if len(attached) != 2:
        raise RuntimeError("thumb diameter must retain two physical silhouettes")
    points = []
    radius = expected_mm / 2000.0
    for raw in attached:
        silhouette = _early_bound(raw, "ISilhouetteEdge")
        face = silhouette.GetFace()
        surface = (
            _early_bound(face, "IFace2").GetSurface() if face is not None else None
        )
        if surface is None:
            raise RuntimeError("thumb diameter lost its physical cylindrical face")
        surface = _early_bound(surface, "ISurface")
        if (
            not surface.IsCylinder()
            or abs(float(surface.CylinderParams[6]) - radius) > 1e-8
        ):
            raise RuntimeError(
                "thumb diameter attaches to the wrong cylindrical surface"
            )
        for member in ("GetStartPoint", "GetEndPoint"):
            point = getattr(silhouette, member)()
            if point is None:
                raise RuntimeError("thumb diameter silhouette has no current endpoint")
            points.append(tuple(_early_bound(point, "IMathPoint").ArrayData))
    projected = model_points_in_view(
        adapter,
        view,
        [(0.0, 0.0, 0.0), *points],
        label="thumb settled physical diameter attachments",
    )
    center_y = projected[0][1]
    ratio = tuple(float(value) for value in view.ScaleRatio)
    height = radius * ratio[0] / ratio[1]
    offsets = []
    for first, second in ((projected[1], projected[2]), (projected[3], projected[4])):
        if abs(first[1] - second[1]) > 1e-7:
            raise RuntimeError(
                "thumb diameter no longer attaches to straight axial flanks"
            )
        offsets.append((first[1] + second[1]) / 2.0 - center_y)
    if any(
        abs(value - expected) > 1e-7
        for value, expected in zip(sorted(offsets), (-height, height), strict=True)
    ):
        raise RuntimeError("thumb diameter no longer spans opposite envelope flanks")


@_telemetry.traced("drawing.thumb_supplier_settled")
def _assert_supplier_dimensions(adapter: Any) -> None:
    """Prove the six final native references after the finalizer's last rebuild."""
    views = list(iter_views(adapter))
    fronts = [view for view in views if view.GetOrientationName() == "*Front"]
    if len(fronts) != 1:
        raise RuntimeError(
            "thumb supplier sheet must have exactly one final Front view"
        )
    view = _early_bound(fronts[0], "IView")
    found = {}
    for raw_view in views:
        current_view = _early_bound(raw_view, "IView")
        display = current_view.GetFirstDisplayDimension6()
        while display is not None:
            display = _early_bound(display, "IDisplayDimension")
            native = _early_bound(display.GetDimension2(0), "IDimension")
            name = str(native.FullName).split("@", 1)[0]
            if name in found or current_view.GetOrientationName() != "*Front":
                raise RuntimeError(
                    "thumb supplier references duplicated or changed owner"
                )
            found[name] = display
            display = display.GetNext5()
    axial = {
        "head_height": (thumb.HEAD_H, (0.0, thumb.HEAD_H)),
        "collar_height": (thumb.COLLAR_H, (thumb.HEAD_H, thumb.HEAD_STACK_LEN)),
        "thread_length": (thumb.SHANK_LEN, (thumb.HEAD_STACK_LEN, thumb.OVERALL_LEN)),
    }
    diameters = {
        "head_diameter": thumb.HEAD_DIA,
        "collar_diameter": thumb.COLLAR_DIA,
        "thread_diameter": thumb.SHANK_DIA,
    }
    if set(found) != {_supplier_name(name) for name in (*axial, *diameters)}:
        raise RuntimeError("thumb sheet lost or added a supplier dimension")
    for name in (*axial, *diameters):
        display = found[_supplier_name(name)]
        value = axial[name][0] if name in axial else diameters[name]
        assert_supplier_reference_dimension(
            adapter,
            display,
            label=name,
            expected_mm=value,
            units=supplier.SUPPLIER_UNITS,
            precision=supplier.SUPPLIER_PRECISION[name],
            presentation="length" if name in axial else "diameter",
            callout=supplier.SUPPLIER_THREAD if name == "thread_diameter" else None,
        )
        native = _early_bound(display.GetDimension2(0), "IDimension")
        if int(_early_bound(native.Tolerance, "IDimensionTolerance").Type) != 0:
            raise RuntimeError(f"{name}: supplier nominal acquired a fabrication band")
        if name in axial:
            _assert_physical_rims(display, axial[name][1])
        else:
            _assert_physical_diameter(adapter, view, display, value)


@_telemetry.traced("drawing.thumb_supplier_dimensions")
def supplier_dimensions(adapter: Any, views_by_orientation: dict[str, Any]) -> None:
    """Six native geometric references and the supplier thread identification."""
    view = _early_bound(views_by_orientation["*Front"], "IView")
    view.UpdateViewDisplayGeometry()
    axis = model_points_in_view(
        adapter,
        view,
        [
            (x / 1000.0, 0.0, 0.0)
            for x in (0.0, thumb.HEAD_H, thumb.HEAD_STACK_LEN, thumb.OVERALL_LEN)
        ],
        label="thumb supplier axial stations",
    )
    if max(point[1] for point in axis) - min(point[1] for point in axis) > 1e-7:
        raise RuntimeError("thumb Front view does not project its axis horizontally")
    center_y = axis[0][1]
    ratio = tuple(float(value) for value in view.ScaleRatio)
    radius = thumb.HEAD_DIA / 2000.0 * ratio[0] / ratio[1]
    left, right = min(point[0] for point in axis), max(point[0] for point in axis)
    # Explicit annotation lanes around the unchanged largest-fitting view.
    # The lower caption remains at its cell floor, not under the body.
    outline = (
        left - 0.034,
        center_y - radius - 0.014,
        right + 0.045,
        center_y + radius + 0.023,
    )
    if (
        outline[0] < 0.025
        or outline[1] < 0.077
        or outline[2] > 0.205
        or outline[3] > 0.182
    ):
        raise RuntimeError(
            "thumb supplier annotation lanes do not fit; relayout without downscaling"
        )
    edges = scan_view_edges(view, label="thumb supplier finished-face rims")
    stations = (0.0, thumb.HEAD_H, thumb.HEAD_STACK_LEN, thumb.OVERALL_LEN)
    rims = [
        _station_circle(edges, station, label=f"thumb station {station:g}")
        for station in stations
    ]
    for name, start, end, value, y in (
        ("head_height", 0, 1, thumb.HEAD_H, center_y + radius + 0.009),
        ("collar_height", 1, 2, thumb.COLLAR_H, center_y + radius + 0.020),
        ("thread_length", 2, 3, thumb.SHANK_LEN, center_y - radius - 0.010),
    ):
        entities = (rims[start], rims[end])
        display = add_edge_dimension(
            adapter,
            view,
            p0=axis[start],
            p1=axis[end],
            text_xy=((axis[start][0] + axis[end][0]) / 2.0, y),
            label=name,
            orientation="horizontal",
            entities=entities,
        )
        _name_supplier_dimension(display, name)
        assert_dimension_measures(
            adapter, display, expected_mm=value, label=name, entities=entities
        )
        supplier_reference_dimension(
            adapter,
            display,
            label=name,
            expected_mm=value,
            units=supplier.SUPPLIER_UNITS,
            precision=supplier.SUPPLIER_PRECISION[name],
        )
    flanks = _diameter_flanks(adapter, view, center_y=center_y)
    for name, value, x, text_y in (
        ("head_diameter", thumb.HEAD_DIA, left - 0.020, center_y),
        ("collar_diameter", thumb.COLLAR_DIA, right + 0.027, center_y + 0.013),
        ("thread_diameter", thumb.SHANK_DIA, right + 0.012, center_y - 0.014),
    ):
        entities = flanks[name]
        display = add_edge_dimension(
            adapter,
            view,
            p0=(x, center_y - value / 2000.0),
            p1=(x, center_y + value / 2000.0),
            text_xy=(x, text_y),
            label=name,
            orientation="vertical",
            entity_type="SILHOUETTE",
            entities=entities,
        )
        _name_supplier_dimension(display, name)
        assert_dimension_measures(
            adapter,
            display,
            expected_mm=value,
            label=name,
            entities=entities,
            entity_types=("SILHOUETTE", "SILHOUETTE"),
        )
        supplier_reference_dimension(
            adapter,
            display,
            label=name,
            expected_mm=value,
            units=supplier.SUPPLIER_UNITS,
            precision=supplier.SUPPLIER_PRECISION[name],
            presentation="diameter",
            callout=supplier.SUPPLIER_THREAD if name == "thread_diameter" else None,
        )


async def build(adapter: Any) -> dict[str, str]:
    checks = []

    def annotate(current_adapter: Any, views: dict[str, Any]) -> None:
        supplier_dimensions(current_adapter, views)
        checks.append(lambda: _assert_supplier_dimensions(current_adapter))

    return await build_purchased_fastener_drawing(
        adapter, SPEC, item=ITEM, supplier_dimensions=annotate, settled_checks=checks
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[SPEC.artifact_stem])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
