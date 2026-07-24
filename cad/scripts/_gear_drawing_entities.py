"""Topology helpers shared by the curated gear drawings.

Gear end views contain many closely spaced tooth edges.  A sheet-coordinate
pick at the bore's 12 o'clock point can therefore select a tooth silhouette
instead of the bore itself.  Resolve the circular model edge by its exact
radius and pass that entity to the drawing annotation helpers.
"""

from __future__ import annotations

import math
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


def visible_planar_face(adapter: Any, view: Any, *, label: str) -> Any:
    """Return the largest visible planar model face in ``view``."""
    candidates: list[tuple[float, Any]] = []
    components = adapter._attempt(lambda: view.GetVisibleComponents(), default=()) or ()
    for component in components:
        faces = adapter._attempt(
            lambda c=component: view.GetVisibleEntities2(c, 3), default=()
        ) or ()
        for raw_face in faces:
            face = _early_bound(raw_face, "IFace2")
            surface = _early_bound(face.GetSurface(), "ISurface")
            if surface.IsPlane():
                candidates.append((float(face.GetArea()), face))

    if not candidates:
        raise RuntimeError(f"{label} view has no visible planar model face")
    return max(candidates, key=lambda item: item[0])[1]


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

    if not candidates:
        raise RuntimeError(
            "no visible tooth-tip silhouette matches radius "
            f"{target_radius_m * 1000.0:.4f} mm"
        )
    return max(candidates, key=lambda candidate: candidate[0])[1]
