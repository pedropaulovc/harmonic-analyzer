"""Topology helpers shared by the curated gear drawings.

Gear end views contain many closely spaced tooth edges.  A sheet-coordinate
pick at the bore's 12 o'clock point can therefore select a tooth silhouette
instead of the bore itself.  Resolve the circular model edge by its exact
radius and pass that entity to the drawing annotation helpers.
"""

from __future__ import annotations

from typing import Any

from _common import _early_bound


def visible_circle_edge(adapter: Any, view: Any, diameter_mm: float) -> Any:
    """Return the visible circular model edge matching ``diameter_mm``."""
    candidates: list[tuple[float, Any]] = []
    components = adapter._attempt(lambda: view.GetVisibleComponents(), default=()) or ()
    for component in components:
        edges = adapter._attempt(
            lambda c=component: view.GetVisibleEntities2(c, 1), default=()
        ) or ()
        for edge in edges:
            edge = _early_bound(edge, "IEdge")
            curve = _early_bound(edge.GetCurve(), "ICurve")
            if not curve.IsCircle():
                continue
            radius_mm = float(curve.CircleParams[6]) * 1000.0
            candidates.append((radius_mm, edge))

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
