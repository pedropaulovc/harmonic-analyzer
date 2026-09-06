"""Resolve drawing attachment roles from the referenced model's geometry.

Selectors use model millimetres, never sheet coordinates or pick tolerances.
Resolve all roles together after the source configuration has been selected and
before editing its geometry. The resolver owns one model-topology snapshot; do
not retain it across a model rebuild, configuration switch, or document close.

The returned edges/faces are passed to IView.SelectEntity. They need no visible
entity sweep and remain independent of the view's position, scale and camera.
Layout and leader coordinates belong in the drawing recipe, separately.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Mapping

import _telemetry
from _common import _early_bound
from _gtol_spec import FaceSpec
from _part_pmi import _resolve_faces


Point = tuple[float, float, float]


def _unit(vector: Point) -> Point:
    length = math.sqrt(sum(value * value for value in vector))
    if not math.isfinite(length) or length == 0:
        raise ValueError(f"entity direction must be finite and nonzero: {vector}")
    return tuple(value / length for value in vector)


def _parallel(first: Point, second: Point) -> bool:
    a, b = _unit(first), _unit(second)
    return abs(abs(sum(x * y for x, y in zip(a, b))) - 1.0) < 1e-8


@dataclass(frozen=True)
class CircleEdge:
    """Circle/arc with a specified radius, centre and unoriented normal."""

    radius_mm: float
    center_mm: Point
    axis: Point
    tolerance_mm: float = 0.01

    def __post_init__(self) -> None:
        _unit(self.axis)
        if self.radius_mm <= 0 or self.tolerance_mm <= 0:
            raise ValueError("circle radius and matching tolerance must be positive")
        if not all(math.isfinite(value) for value in (*self.center_mm, self.radius_mm, self.tolerance_mm)):
            raise ValueError("circle selector must contain finite model geometry")


@dataclass(frozen=True)
class LineEdge:
    """Finite straight edge containing a model point, with a given direction.

    The point is a point on the controlled model edge, derived from the part
    specification. It is not a nearest-point search: no match or two matches
    fails, including overlapping edges from different bodies.
    """

    point_mm: Point
    direction: Point
    tolerance_mm: float = 0.01

    def __post_init__(self) -> None:
        _unit(self.direction)
        if self.tolerance_mm <= 0 or not all(
            math.isfinite(value) for value in (*self.point_mm, self.tolerance_mm)
        ):
            raise ValueError("line selector must have finite geometry and positive tolerance")


@dataclass(frozen=True)
class _Circle:
    entity: Any
    center_mm: Point
    axis: Point
    radius_mm: float

    def matches(self, spec: CircleEdge) -> bool:
        return (
            abs(self.radius_mm - spec.radius_mm) <= spec.tolerance_mm
            and math.dist(self.center_mm, spec.center_mm) <= spec.tolerance_mm
            and _parallel(self.axis, spec.axis)
        )


@dataclass(frozen=True)
class _Line:
    entity: Any
    start_mm: Point
    end_mm: Point

    def matches(self, spec: LineEdge) -> bool:
        delta = tuple(b - a for a, b in zip(self.start_mm, self.end_mm))
        length_squared = sum(value * value for value in delta)
        if length_squared == 0 or not _parallel(delta, spec.direction):
            return False
        t = sum((p - a) * d for p, a, d in zip(spec.point_mm, self.start_mm, delta)) / length_squared
        nearest = tuple(a + min(1.0, max(0.0, t)) * d for a, d in zip(self.start_mm, delta))
        return math.dist(nearest, spec.point_mm) <= spec.tolerance_mm


class ModelEntities:
    """A bounded, read-only entity index for one source model/configuration."""

    def __init__(self, model: Any):
        self.model = model

    @_telemetry.traced("drawing.resolve_model_entities")
    def resolve(self, roles: Mapping[str, CircleEdge | LineEdge | FaceSpec]) -> dict[str, Any]:
        edge_roles = {key: spec for key, spec in roles.items() if isinstance(spec, (CircleEdge, LineEdge))}
        face_roles = {key: spec for key, spec in roles.items() if key not in edge_roles}
        resolved = _resolve_faces(self.model, face_roles) if face_roles else {}
        if not edge_roles:
            return resolved

        circles_needed = any(isinstance(spec, CircleEdge) for spec in edge_roles.values())
        lines_needed = any(isinstance(spec, LineEdge) for spec in edge_roles.values())
        matches: dict[str, list[Any]] = {key: [] for key in edge_roles}
        part = _early_bound(self.model, "IPartDoc")
        edge_count = 0
        for raw_body in part.GetBodies2(0, False) or ():
            body = _early_bound(raw_body, "IBody2")
            for raw_edge in body.GetEdges() or ():
                edge_count += 1
                edge = _early_bound(raw_edge, "IEdge")
                curve = _early_bound(edge.GetCurve(), "ICurve")
                geometry = None
                if circles_needed and curve.IsCircle():
                    params = tuple(curve.CircleParams)
                    geometry = _Circle(edge, tuple(v * 1000 for v in params[:3]), tuple(params[3:6]), params[6] * 1000)
                if geometry is None and lines_needed and curve.IsLine():
                    start, end = edge.GetStartVertex(), edge.GetEndVertex()
                    if start is None or end is None:
                        continue
                    start = _early_bound(start, "IVertex").GetPoint()
                    end = _early_bound(end, "IVertex").GetPoint()
                    geometry = _Line(edge, tuple(v * 1000 for v in start), tuple(v * 1000 for v in end))
                if geometry is None:
                    continue
                for key, spec in edge_roles.items():
                    if isinstance(spec, CircleEdge) and isinstance(geometry, _Circle) and geometry.matches(spec):
                        matches[key].append(edge)
                    if isinstance(spec, LineEdge) and isinstance(geometry, _Line) and geometry.matches(spec):
                        matches[key].append(edge)

        span = _telemetry.trace.get_current_span()
        span.set_attribute("roles", len(roles))
        span.set_attribute("model_edges", edge_count)
        for key, candidates in matches.items():
            if len(candidates) != 1:
                raise RuntimeError(
                    f"{key}: {edge_roles[key]!r} matched {len(candidates)} edges; "
                    "the model role must identify exactly one edge"
                )
            resolved[key] = candidates[0]
        return resolved
