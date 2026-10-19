"""Create the purchased reference drawing for the thumb screw."""

from __future__ import annotations

import argparse
import math
import sys
from typing import Any

import _telemetry
from _session import run_build
from _drawing_registry import DRAWINGS_BY_NAME
from _com import _early_bound
from _drawing_edge_dimensions import add_edge_dimension, assert_dimension_measures
from _drawing_edges import scan_view_edges, visible_view_entities
from _drawing_projection import model_points_in_view
import _mcmaster_91882a221 as thumb
from _purchased_fastener_drawing import build_purchased_fastener_drawing
from _supplier_dimensions import supplier_reference_dimension


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
            raise RuntimeError(f"{name}: missing actual upper/lower cylindrical envelope")
        result[name] = (sides[-1][1], sides[1][1])
    return result


def supplier_dimensions(adapter: Any, views_by_orientation: dict[str, Any]) -> None:
    """Six native geometric references and the supplier thread identification."""
    view = _early_bound(views_by_orientation["*Front"], "IView")
    view.UpdateViewDisplayGeometry()
    axis = model_points_in_view(
        adapter,
        view,
        [(x / 1000.0, 0.0, 0.0) for x in (
            0.0, thumb.HEAD_H, thumb.HEAD_STACK_LEN, thumb.OVERALL_LEN
        )],
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
    outline = (left - 0.020, center_y - radius - 0.014,
               right + 0.031, center_y + radius + 0.023)
    if outline[0] < 0.025 or outline[1] < 0.077 or outline[2] > 0.205 or outline[3] > 0.182:
        raise RuntimeError("thumb supplier annotation lanes do not fit; relayout without downscaling")
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
            adapter, view, p0=axis[start], p1=axis[end],
            text_xy=((axis[start][0] + axis[end][0]) / 2.0, y),
            label=name, orientation="horizontal", entities=entities,
        )
        assert_dimension_measures(
            adapter, display, expected_mm=value, label=name, entities=entities
        )
        supplier_reference_dimension(
            adapter, display, label=name, expected_mm=value, units=thumb.SUPPLIER_UNITS,
            precision=thumb.SUPPLIER_PRECISION[name],
        )
    flanks = _diameter_flanks(adapter, view, center_y=center_y)
    for name, value, x in (
        ("head_diameter", thumb.HEAD_DIA, left - 0.013),
        ("collar_diameter", thumb.COLLAR_DIA, right + 0.012),
        ("thread_diameter", thumb.SHANK_DIA, right + 0.027),
    ):
        entities = flanks[name]
        display = add_edge_dimension(
            adapter, view, p0=(x, center_y - value / 2000.0),
            p1=(x, center_y + value / 2000.0), text_xy=(x, center_y),
            label=name, orientation="vertical", entity_type="SILHOUETTE",
            entities=entities,
        )
        assert_dimension_measures(
            adapter, display, expected_mm=value, label=name,
            entities=entities, entity_types=("SILHOUETTE", "SILHOUETTE"),
        )
        supplier_reference_dimension(
            adapter, display, label=name, expected_mm=value, units=thumb.SUPPLIER_UNITS,
            precision=thumb.SUPPLIER_PRECISION[name], presentation="diameter",
            callout=thumb.SUPPLIER_THREAD if name == "thread_diameter" else None,
        )



async def build(adapter: Any) -> dict[str, str]:
    return await build_purchased_fastener_drawing(
        adapter, SPEC, item=ITEM, supplier_dimensions=supplier_dimensions
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[SPEC.artifact_stem])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
