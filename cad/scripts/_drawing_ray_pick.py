"""Geometric visibility of balloon anchor points in a drawing view (#1667).

A BOM balloon's leader must end on ink of its own part. The hit test that used
to prove that -- ``SelectByID2`` at a sheet point in the zoomed graphics window
-- is SolidWorks' interactive pick, and the API documents it as "prone to
failure if the model view is altered". On the farm it failed as a SEAT STATE:
for hours at a time one seat missed ink every other seat hit at the same sheet
point (same cache key, same geometry), every screen pick on that seat
degraded with it (the walk needed 2-3x the points, thin parts found none),
and a seat restart cleared it. Thirty days of ``drawing.pick_balloon_anchor``
spans, App Insights, 2026-10-22.

So the proof here never reads the window. A view is a parallel projection:
the ray from the viewer to a model point, cast against every shown
component's solid bodies at their exploded positions, says exactly what the
view draws in front of that point (``IModelDocExtension::RayIntersections``,
Parasolid, no raster), and the topology it hands back for a hit ON the point
is the edge the point lies on (``swRayPtsOptsTOPOLS``), mapped into the
instance's context (``IComponent2::GetCorrespondingEntity``) so it selects
through the view. Measured against the screen pick on 118 candidate points of
the summing exploded view (amet, 2026-10-22): 112 agree; the six that differ
are points the screen pick could not see on a healthy seat either.

Every body is read ONCE per view and every candidate point of every family is
one ray, so a whole balloon set costs one ``RayIntersections`` call per body
(10-200 ms each on the summing view's 16 bodies).
"""

from __future__ import annotations

from dataclasses import dataclass
import math
import time
from typing import Any, Sequence

from solidworks_mcp.adapters.com_variant import dispatch_array, double_array

from _com import _com_invoke, _early_bound
from _drawing_scan import _span_scan_attrs
import _telemetry


# swRayPtsOptsENTRY_EXIT | swRayPtsOptsTOPOLS | swRayPtsOptsNORMALS: with
# NORMALS every hit is a fixed nine doubles (body, ray, type, x, y, z, nx, ny,
# nz), and TOPOLS hands back one entity per hit in the same order.
_RAY_OPTIONS = 4 | 2 | 1
_HIT_WIDTH = 9
# A frozen anchor is written in whole micrometres (three decimals of a
# millimetre), so its point can sit up to 0.87 um off the edge it names: the
# frame base's (90.360, 50.800, -62.873) is 0.3 um from the edge at z
# -62.8727, which a 1 nm ray passed without reporting (amet, 2026-10-22). A
# 2 um ray reports the edge and is still far below the depth tolerance.
_RAY_RADIUS_M = 2e-6
_RAY_OFFSET_M = 1e-8
_SW_SOLID_BODY = 0  # swBodyType_e.swSolidBody
_EDGE_HIT = 4  # swRayPtsResults_e.swRayPtsResultsEDGE


# A hit closer to the viewer than the candidate by more than this is
# material in front of the point; a hit within it is the point itself (the
# edge, and the faces meeting at it). 10 um in model metres: far below any
# feature, far above Parasolid's 1e-8 m.
_DEPTH_TOLERANCE_M = 1e-5


# The ray origins sit on a plane this far in front of every body's extreme
# point along the view direction, so no ray starts inside material.
_ORIGIN_MARGIN_M = 0.01


@dataclass(frozen=True)
class RayPick:
    """What the view's bodies put on the ray from the viewer to one candidate.

    ``covered_by`` lists the instances with material strictly in front of the
    point, nearest first (the candidate's own instance when the point is on
    its far side). ``edges`` are the candidate's own instance's edges found
    AT the point, in the instance's context, each selectable through the
    view. A point is drawn as its part's ink exactly when nothing covers it
    and it lies on one of its edges: an extreme point of a dome or a cylinder
    is on a face, not an edge, and no leader can land on it.
    """

    covered_by: tuple[str, ...]
    edges: tuple[Any, ...]

    @property
    def visible(self) -> bool:
        return not self.covered_by and bool(self.edges)


@dataclass(frozen=True)
class _CastBody:
    path: str
    component: Any
    body: Any
    # ``IMathTransform.ArrayData`` of the instance's pose plus its explode:
    # rotation (0-8, applied as x' = x*v0 + y*v3 + z*v6), translation (9-11),
    # scale (12).
    values: tuple[float, ...]


def _to_part(
    values: Sequence[float], point: Sequence[float]
) -> tuple[float, float, float]:
    """A model point in the body's own frame (inverse of the pose)."""
    scale = values[12]
    q = tuple((point[i] - values[9 + i]) / scale for i in range(3))
    return (
        q[0] * values[0] + q[1] * values[1] + q[2] * values[2],
        q[0] * values[3] + q[1] * values[4] + q[2] * values[5],
        q[0] * values[6] + q[1] * values[7] + q[2] * values[8],
    )


def _direction_to_part(
    values: Sequence[float], d: Sequence[float]
) -> tuple[float, float, float]:
    return (
        d[0] * values[0] + d[1] * values[1] + d[2] * values[2],
        d[0] * values[3] + d[1] * values[4] + d[2] * values[5],
        d[0] * values[6] + d[1] * values[7] + d[2] * values[8],
    )


def _to_model(
    values: Sequence[float], point: Sequence[float]
) -> tuple[float, float, float]:
    scale = values[12]
    x, y, z = point
    return (
        scale * (x * values[0] + y * values[3] + z * values[6]) + values[9],
        scale * (x * values[1] + y * values[4] + z * values[7]) + values[10],
        scale * (x * values[2] + y * values[5] + z * values[8]) + values[11],
    )


def view_normal(view: Any) -> tuple[float, float, float]:
    """The unit vector from the sheet toward the viewer, in model space.

    ``IView::ModelToViewTransform`` takes model points to sheet points with
    the sheet's z toward the viewer; the model direction it sends to +z is
    the transform's third column.
    """
    transform = _com_invoke(view, "IView", "ModelToViewTransform")
    values = [
        float(v) for v in (_com_invoke(transform, "IMathTransform", "ArrayData") or ())
    ]
    if len(values) < 13:
        raise RuntimeError("drawing view has no model-to-view transform")
    n = (values[2], values[5], values[8])
    length = math.sqrt(sum(c * c for c in n))
    if length <= 0.0:
        raise RuntimeError("drawing view transform has no view direction")
    return (n[0] / length, n[1] / length, n[2] / length)


def _dot(a: Sequence[float], b: Sequence[float]) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


class ViewRayCaster:
    """The shown solid bodies of one drawing view, posed as the view draws them.

    ``leaves`` are the view's component leaves (``_drawing_balloons._view_component_leaves``)
    and ``pose(leaf)`` the ``ArrayData`` of each leaf's exploded pose. Every
    shown leaf must resolve its solid bodies: a lightweight or suppressed
    component would be drawn and yet cast no shadow, so it fails the view.
    """

    def __init__(
        self,
        adapter: Any,
        view: Any,
        leaves: Sequence[Any],
        pose: Any,
        *,
        label: str,
    ) -> None:
        self._adapter = adapter
        self._label = label
        self._model = _early_bound(
            _early_bound(view, "IView").ReferencedDocument, "IModelDoc2"
        )
        self._extension = _early_bound(self._model.Extension, "IModelDocExtension")
        self.normal = view_normal(view)
        self._bodies: list[_CastBody] = []
        for leaf in leaves:
            if not leaf.visible or leaf.component is None:
                continue
            component = _early_bound(leaf.component, "IComponent2")
            result = adapter._attempt(
                lambda c=component: c.GetBodies3(_SW_SOLID_BODY), default=None
            )
            bodies = (
                tuple(result[0] or ())
                if isinstance(result, tuple) and len(result) == 2
                else ()
            )
            if not bodies:
                raise RuntimeError(
                    f"{label}: shown component {leaf.path} resolves no solid body "
                    f"to cast balloon rays against"
                )
            values = tuple(float(v) for v in pose(leaf))
            if len(values) < 13:
                raise RuntimeError(f"{label}: {leaf.path} has no pose")
            self._bodies.extend(
                _CastBody(leaf.path, component, _early_bound(body, "IBody2"), values)
                for body in bodies
            )
        self._front = self._front_plane()

    def _front_plane(self) -> float:
        """Depth (along the normal) just in front of every body."""
        top = None
        for cast in self._bodies:
            direction = _direction_to_part(cast.values, self.normal)
            result = tuple(cast.body.GetExtremePoint(*direction) or ())
            if len(result) != 4 or not result[0]:
                raise RuntimeError(
                    f"{self._label}: {cast.path} has no extreme point along the view"
                )
            depth = _dot(_to_model(cast.values, result[1:4]), self.normal)
            top = depth if top is None else max(top, depth)
        if top is None:
            raise RuntimeError(f"{self._label}: the view shows no solid body")
        return top + _ORIGIN_MARGIN_M

    @property
    def bodies(self) -> int:
        return len(self._bodies)

    @_telemetry.traced("drawing.ray_pick", label_param="label")
    def probe(
        self, candidates: Sequence[tuple[str, Sequence[float]]], *, label: str
    ) -> list[RayPick]:
        """One :class:`RayPick` per ``(instance path, model point)`` candidate.

        One ``RayIntersections`` call per body, every candidate a ray from the
        front plane toward the viewer's far side. Topology comes back only for
        hits on a candidate's OWN instance at its own depth; a hit anywhere
        in front, on any body, covers the candidate.
        """
        if not candidates:
            return []
        normal = self.normal
        expected = [self._front - _dot(point, normal) for _path, point in candidates]
        if any(depth <= _DEPTH_TOLERANCE_M for depth in expected):
            raise RuntimeError(
                f"{label}: a candidate point lies in front of every body"
            )
        origins = [
            tuple(point[i] + normal[i] * depth for i in range(3))
            for (_path, point), depth in zip(candidates, expected)
        ]
        covered: list[list[tuple[float, str]]] = [[] for _ in candidates]
        edges: list[list[Any]] = [[] for _ in candidates]
        started = time.perf_counter()
        hits = 0
        for cast in self._bodies:
            starts: list[float] = []
            vectors: list[float] = []
            direction = _direction_to_part(cast.values, tuple(-c for c in normal))
            for origin in origins:
                starts.extend(_to_part(cast.values, origin))
                vectors.extend(direction)
            self._extension.RayIntersections(
                dispatch_array([cast.body]),
                double_array(starts),
                double_array(vectors),
                _RAY_OPTIONS,
                _RAY_RADIUS_M,
                _RAY_OFFSET_M,
                True,
            )
            raw = tuple(self._model.GetRayIntersectionsPoints() or ())
            topology = tuple(self._model.GetRayIntersectionsTopology() or ())
            if len(raw) % _HIT_WIDTH or len(topology) != len(raw) // _HIT_WIDTH:
                raise RuntimeError(
                    f"{label}: ray readback on {cast.path} is malformed: "
                    f"{len(raw)} doubles, {len(topology)} entities"
                )
            own = {
                index
                for index, (path, _point) in enumerate(candidates)
                if path.casefold() == cast.path.casefold()
            }
            for k in range(0, len(raw), _HIT_WIDTH):
                hits += 1
                ray = int(raw[k + 1])
                kind = int(raw[k + 2])
                start = starts[ray * 3 : ray * 3 + 3]
                distance = math.sqrt(
                    sum((float(raw[k + 3 + i]) - start[i]) ** 2 for i in range(3))
                )
                if distance < expected[ray] - _DEPTH_TOLERANCE_M:
                    covered[ray].append((distance, cast.path))
                elif (
                    abs(distance - expected[ray]) <= _DEPTH_TOLERANCE_M
                    and kind & _EDGE_HIT
                    and ray in own
                ):
                    edge = self._adapter._attempt(
                        lambda e=topology[k // _HIT_WIDTH], c=cast.component: (
                            c.GetCorrespondingEntity(e)
                        ),
                        default=None,
                    )
                    if edge is not None:
                        edges[ray].append(edge)
        _span_scan_attrs(
            bodies=len(self._bodies),
            rays=len(candidates),
            hits=hits,
            ray_ms=round((time.perf_counter() - started) * 1000.0),
        )
        return [
            RayPick(
                covered_by=tuple(path for _d, path in sorted(set(covered[i]))),
                edges=tuple(edges[i]),
            )
            for i in range(len(candidates))
        ]
