"""Topology helpers shared by the curated gear drawings.

Gear end views contain many closely spaced tooth edges.  A sheet-coordinate
pick at the bore's 12 o'clock point can therefore select a tooth silhouette
instead of the bore itself.  Resolve the circular model edge by its exact
radius and pass that entity to the drawing annotation helpers.
"""

from __future__ import annotations

import math
from typing import Any

import _telemetry
from _common import _early_bound


def _span_attrs(**attributes: float) -> None:
    """Attach aggregate scan counts to the CURRENT span.

    ``@traced`` owns the span, so there is no handle to set attributes on --
    reach for the active one. A no-op when nothing is recording, so callers
    never guard.
    """
    span = _telemetry.trace.get_current_span()
    for key, value in attributes.items():
        span.set_attribute(key, value)


@_telemetry.traced("drawing.pick_circle_edge")
def visible_circle_edge(adapter: Any, view: Any, diameter_mm: float) -> Any:
    """Return the visible circular model edge matching ``diameter_mm``.

    Costs ~5 COM round trips per visible edge (early-bind, GetCurve,
    early-bind, IsCircle, CircleParams), so a gear end view with hundreds of
    tooth edges makes this the most expensive step in its drawing. The counts go
    on the SPAN's own attributes, not just a span event: the profiling workflow
    reads span lines, where an event's attributes do not appear. The per-edge
    work stays inside ONE span rather than flooding the trace with leaves.
    """
    candidates: list[tuple[float, Any]] = []
    edge_count = 0
    components = adapter._attempt(lambda: view.GetVisibleComponents(), default=()) or ()
    for component in components:
        edges = adapter._attempt(
            lambda c=component: view.GetVisibleEntities2(c, 1), default=()
        ) or ()
        for edge in edges:
            edge_count += 1
            edge = _early_bound(edge, "IEdge")
            curve = _early_bound(edge.GetCurve(), "ICurve")
            if not curve.IsCircle():
                continue
            radius_mm = float(curve.CircleParams[6]) * 1000.0
            candidates.append((radius_mm, edge))

    _span_attrs(edges=edge_count, circles=len(candidates),
                diameter_mm=diameter_mm)
    target_radius = diameter_mm / 2.0
    if not candidates:
        raise RuntimeError("drawing view has no visible circular model edge")
    radius_mm, edge = min(candidates, key=lambda item: abs(item[0] - target_radius))
    if abs(radius_mm - target_radius) > 0.01:
        raise RuntimeError(
            f"no visible circle matches radius {target_radius:.4f} mm; "
            f"nearest is {radius_mm:.4f} mm"
        )
    return edge


@_telemetry.traced("drawing.pick_tooth_silhouette")
def visible_tooth_tip_silhouette(
    adapter: Any, view: Any, outside_diameter_mm: float
) -> Any:
    """Return the upper side-view silhouette at the specified tooth-tip radius."""
    target_radius_m = outside_diameter_mm / 2000.0
    candidates: list[tuple[float, Any]] = []
    components = adapter._attempt(lambda: view.GetVisibleComponents(), default=()) or ()
    for component in components:
        silhouettes = adapter._attempt(
            lambda c=component: view.GetVisibleEntities2(c, 4), default=()
        ) or ()
        for raw_silhouette in silhouettes:
            silhouette = _early_bound(raw_silhouette, "ISilhouetteEdge")
            start = adapter._attempt(lambda s=silhouette: s.GetStartPoint())
            end = adapter._attempt(lambda s=silhouette: s.GetEndPoint())
            if start is None or end is None:
                continue
            start_xyz = adapter._get_attr_or_call(start, "ArrayData")
            end_xyz = adapter._get_attr_or_call(end, "ArrayData")
            if not start_xyz or not end_xyz:
                continue
            start_radius = math.hypot(float(start_xyz[0]), float(start_xyz[1]))
            end_radius = math.hypot(float(end_xyz[0]), float(end_xyz[1]))
            if abs(start_radius - target_radius_m) > 0.00001:
                continue
            if abs(end_radius - target_radius_m) > 0.00001:
                continue
            mean_y = (float(start_xyz[1]) + float(end_xyz[1])) / 2.0
            candidates.append((mean_y, silhouette))

    _span_attrs(matched=len(candidates), outside_diameter_mm=outside_diameter_mm)
    if not candidates:
        raise RuntimeError(
            "no visible tooth-tip silhouette matches radius "
            f"{target_radius_m * 1000.0:.4f} mm"
        )
    return max(candidates, key=lambda candidate: candidate[0])[1]
