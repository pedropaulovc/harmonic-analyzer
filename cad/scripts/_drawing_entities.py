"""Resolve drawing attachment roles from the referenced model's geometry.

Selectors use model millimetres, never sheet coordinates or pick tolerances.
Resolve all roles together after the source configuration has been selected and
before editing its geometry. The resolver owns one model-topology snapshot; do
not retain it across a model rebuild, configuration switch, or document close.

The returned edges/faces/vertices are passed to IView.SelectEntity. They need no visible
entity sweep and remain independent of the view's position, scale and camera.
Layout and leader coordinates belong in the drawing recipe, separately.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Iterable, Mapping

import _telemetry
from _common import _early_bound
from _gtol_spec import FaceSpec
from _part_pmi import _face_geometry, _face_matches


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
class ModelVertex:
    """A unique topological vertex at the specified model position."""

    point_mm: Point
    tolerance_mm: float = 0.01

    def __post_init__(self) -> None:
        if self.tolerance_mm <= 0 or not all(
            math.isfinite(value) for value in (*self.point_mm, self.tolerance_mm)
        ):
            raise ValueError("vertex selector must have finite geometry and positive tolerance")


@dataclass(frozen=True)
class FeatureFace:
    """Exact face geometry owned by one explicitly named source-model feature."""

    feature_name: str
    face: FaceSpec

    def __post_init__(self) -> None:
        if not self.feature_name.strip():
            raise ValueError("feature face requires a nonempty model feature name")


@dataclass(frozen=True)
class FaceBoundary:
    """Exact edge geometry on a resolved feature face, not the entire body."""

    face: FeatureFace
    edge: CircleEdge | LineEdge


@dataclass(frozen=True)
class EdgeAdjacentFace:
    """Exact face geometry immediately adjacent to a resolved boundary edge."""

    edge: FaceBoundary
    face: FaceSpec


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


def _edge_geometry(raw_edge: Any, *, kinds: frozenset[type]) -> _Circle | _Line | None:
    edge = _early_bound(raw_edge, "IEdge")
    curve = _early_bound(edge.GetCurve(), "ICurve")
    if CircleEdge in kinds and curve.IsCircle():
        params = tuple(curve.CircleParams)
        return _Circle(edge, tuple(v * 1000 for v in params[:3]), tuple(params[3:6]), params[6] * 1000)
    if LineEdge in kinds and curve.IsLine():
        start, end = edge.GetStartVertex(), edge.GetEndVertex()
        if start is None or end is None:
            return None
        start = _early_bound(start, "IVertex").GetPoint()
        end = _early_bound(end, "IVertex").GetPoint()
        return _Line(edge, tuple(v * 1000 for v in start), tuple(v * 1000 for v in end))
    return None


def _resolve_face_requests(faces: Iterable[Any], requests: Mapping[str, FaceSpec], *, scope: str) -> dict[str, Any]:
    matches: dict[str, list[Any]] = {key: [] for key in requests}
    with _telemetry.span("drawing.collect_faces", scope=scope, roles=len(requests)) as span:
        count = 0
        for face in faces:
            count += 1
            geometry = _face_geometry(face)
            if geometry is None:
                continue
            for key, spec in requests.items():
                if _face_matches(geometry, spec):
                    matches[key].append(geometry.face)
        span.set_attribute("faces", count)
    resolved = {}
    for key, candidates in matches.items():
        if len(candidates) != 1:
            raise RuntimeError(f"{key}: {scope} {requests[key]!r} matched {len(candidates)} faces; expected exactly one")
        resolved[key] = candidates[0]
    return resolved


def _model_faces(model: Any) -> Iterable[Any]:
    part = _early_bound(model, "IPartDoc")
    for raw_body in part.GetBodies2(0, False) or ():
        face = _early_bound(raw_body, "IBody2").GetFirstFace()
        while face is not None:
            yield face
            face = _early_bound(face, "IFace2").GetNextFace()


ScopedEntity = FeatureFace | FaceBoundary | EdgeAdjacentFace


class _ScopedEntities:
    """Resolve a small ownership chain; never fall back to a body traversal."""

    def __init__(self, model: Any):
        self.model = model
        self.resolved: dict[ScopedEntity, Any] = {}
        self.feature_faces: dict[str, tuple[Any, ...]] = {}

    def resolve(self, spec: ScopedEntity) -> Any:
        if spec not in self.resolved:
            self.resolved[spec] = self._resolve(spec)
        return self.resolved[spec]

    def _resolve(self, spec: ScopedEntity) -> Any:
        if isinstance(spec, FeatureFace):
            if spec.feature_name not in self.feature_faces:
                with _telemetry.span("drawing.feature_faces", feature=spec.feature_name) as span:
                    part = _early_bound(self.model, "IPartDoc")
                    feature = part.FeatureByName(spec.feature_name)
                    if feature is None:
                        raise RuntimeError(f"model feature {spec.feature_name!r} is missing")
                    self.feature_faces[spec.feature_name] = tuple(_early_bound(feature, "IFeature").GetFaces() or ())
                    span.set_attribute("faces", len(self.feature_faces[spec.feature_name]))
            return _resolve_face_requests(
                self.feature_faces[spec.feature_name], {"face": spec.face}, scope=f"feature {spec.feature_name}",
            )["face"]
        if isinstance(spec, EdgeAdjacentFace):
            edge = _early_bound(self.resolve(spec.edge), "IEdge")
            return _resolve_face_requests(
                (face for face in edge.GetTwoAdjacentFaces2() or () if face is not None),
                {"face": spec.face}, scope=f"adjacent to {spec.edge!r}",
            )["face"]
        face = _early_bound(self.resolve(spec.face), "IFace2")
        matches = []
        kinds = frozenset({type(spec.edge)})
        with _telemetry.span("drawing.collect_edges", scope=f"boundary of {spec.face!r}", roles=1) as span:
            edges = tuple(face.GetEdges() or ())
            span.set_attribute("edges", len(edges))
            for edge in edges:
                geometry = _edge_geometry(edge, kinds=kinds)
                if geometry is not None and geometry.matches(spec.edge):
                    matches.append(geometry.entity)
        if len(matches) != 1:
            raise RuntimeError(f"{spec!r} matched {len(matches)} edges; expected exactly one face boundary")
        return matches[0]


class ModelEntities:
    """A bounded, read-only entity index for one source model/configuration."""

    def __init__(self, model: Any):
        self.model = model

    @_telemetry.traced("drawing.resolve_model_entities")
    def resolve(self, roles: Mapping[str, CircleEdge | LineEdge | ModelVertex | FaceSpec | ScopedEntity]) -> dict[str, Any]:
        scoped = _ScopedEntities(self.model)
        scoped_roles = {key: spec for key, spec in roles.items() if isinstance(spec, (FeatureFace, FaceBoundary, EdgeAdjacentFace))}
        resolved = {key: scoped.resolve(spec) for key, spec in scoped_roles.items()}
        edge_roles = {key: spec for key, spec in roles.items() if isinstance(spec, (CircleEdge, LineEdge))}
        vertex_roles = {key: spec for key, spec in roles.items() if isinstance(spec, ModelVertex)}
        face_roles = {key: spec for key, spec in roles.items() if key not in edge_roles and key not in vertex_roles and key not in scoped_roles}
        if face_roles:
            resolved.update(_resolve_face_requests(_model_faces(self.model), face_roles, scope="model"))
        if not edge_roles and not vertex_roles:
            return resolved

        edge_kinds = frozenset(type(spec) for spec in edge_roles.values())
        matches: dict[str, list[Any]] = {key: [] for key in edge_roles}
        vertex_matches: dict[str, list[Any]] = {key: [] for key in vertex_roles}
        part = _early_bound(self.model, "IPartDoc")
        edge_count = 0
        vertex_count = 0
        for raw_body in part.GetBodies2(0, False) or ():
            body = _early_bound(raw_body, "IBody2")
            if vertex_roles:
                for raw_vertex in body.GetVertices() or ():
                    vertex_count += 1
                    vertex = _early_bound(raw_vertex, "IVertex")
                    point = tuple(v * 1000 for v in vertex.GetPoint())
                    for key, spec in vertex_roles.items():
                        if math.dist(point, spec.point_mm) <= spec.tolerance_mm:
                            vertex_matches[key].append(vertex)
            if not edge_roles:
                continue
            with _telemetry.span("drawing.collect_edges", scope="model body", roles=len(edge_roles)) as edge_span:
                raw_edges = tuple(body.GetEdges() or ())
                edge_count += len(raw_edges)
                edge_span.set_attribute("edges", len(raw_edges))
                for raw_edge in raw_edges:
                    geometry = _edge_geometry(raw_edge, kinds=edge_kinds)
                    if geometry is None:
                        continue
                    for key, spec in edge_roles.items():
                        if isinstance(spec, CircleEdge) and isinstance(geometry, _Circle) and geometry.matches(spec):
                            matches[key].append(geometry.entity)
                        if isinstance(spec, LineEdge) and isinstance(geometry, _Line) and geometry.matches(spec):
                            matches[key].append(geometry.entity)

        span = _telemetry.trace.get_current_span()
        span.set_attribute("roles", len(roles))
        span.set_attribute("model_edges", edge_count)
        span.set_attribute("model_vertices", vertex_count)
        for key, candidates in matches.items():
            if len(candidates) != 1:
                raise RuntimeError(
                    f"{key}: {edge_roles[key]!r} matched {len(candidates)} edges; "
                    "the model role must identify exactly one edge"
                )
            resolved[key] = candidates[0]
        for key, candidates in vertex_matches.items():
            if len(candidates) != 1:
                raise RuntimeError(
                    f"{key}: {vertex_roles[key]!r} matched {len(candidates)} vertices; "
                    "the model role must identify exactly one vertex"
                )
            resolved[key] = candidates[0]
        return resolved
