"""Drawing-view visible edges and silhouette geometry.

Separate module so edits re-key only recipes that use this concern.
"""

from __future__ import annotations

from typing import Any
from typing import Mapping
from typing import Sequence
from _com import _com_invoke
from _com import _early_bound
import _telemetry
from dataclasses import dataclass
import math
from solidworks_mcp.adapters.solidworks.drawing import (
    visible_component_entities as visible_component_entities,
)
from _drawing_projection import model_points_in_view


def _edge_endpoint_key(adapter: Any, edge: Any) -> tuple[float, ...] | None:
    """Return one model edge's endpoints as a sortable key, or ``None``.

    The stable identity of an edge, for picking purposes. ``IEdge`` offers no
    usable id -- ``GetID`` is documented for IMPORTED bodies only, is not saved
    with the document, and any add-in may reassign it -- so geometry is what
    there is. ``GetCurveParams2`` returns
    ``(start xyz, end xyz, start/end u, 3 packed doubles)``; the first six are
    the endpoints in model space, which is enough to order the visible edges of
    one component totally and identically on every run.

    ``GetCurve()`` must precede it: SolidWorks does not retain the underlying
    curve, and ``GetCurveParams2`` reads what ``GetCurve`` generated.

    ``None`` when the geometry cannot be read, so an unreadable edge drops out
    of the running instead of failing the drawing -- the caller raises only if
    NO edge on the component yields a key.
    """
    edge = _early_bound(edge, "IEdge")
    if adapter._attempt(lambda e=edge: e.GetCurve(), default=None) is None:
        return None
    params = adapter._attempt(lambda e=edge: e.GetCurveParams2(), default=None)
    if not params or len(params) < 6:
        return None
    return tuple(float(value) for value in params[:6])


@_telemetry.traced("drawing.visible_entity_scan", label_param="label")
def visible_view_entities(view: Any, entity_kind: int, *, label: str) -> list[Any]:
    """All visible entities of ``entity_kind`` across the view's components.

    The GetVisibleComponents/GetVisibleEntities2 walk is the COM-expensive
    core of every per-sheet edge/face scanner — one traced chokepoint here so
    each scanner shows up as a named child span instead of an unspanned gap
    (observability invariant). ``entity_kind`` is swViewEntityType_e (1=edge,
    2=vertex, 3=face, 4=silhouette).

    **Every scanner must come through here, and three did not.**
    ``visible_circle_edge``, ``visible_tooth_tip_silhouette`` and spring-hook's
    ``_shank_silhouette`` each re-implemented this walk untraced, which is how
    43.8 min of 193.7 min of drawing build time sat inside ``drawing.build``
    covered by no child span. One spring_hook run took 724 s with every NAMED
    span fast (surface_finish 1.3 s, finalize 8.8 s) — 693 s with nothing to
    attribute it to, on a drawing that has also run 65 s.

    The cost is wildly kind-dependent, so the ``entity_kind`` attribute is not
    decoration: kind 1 returned 481 edges in 7.0 s, while kind 4 spends ~21 s
    deriving outline geometry and returns SIX. Do not reason about "a sweep" as
    one number.

    Nothing is memoised here, deliberately: a hidden cross-call cache would
    have to invalidate on any visibility change (``set_hidden_lines_removed``,
    the drive-train isolation walk), and a stale entity list picks the wrong
    edge SILENTLY. A recipe that picks MANY entities off one view -- top_frame
    swept its plan view four times in a row and Section A-A five times, 124 s
    of a 270 s build once the per-edge ``GetCurve``/``IsLine``/vertex reads
    were counted -- scans once with :func:`scan_view_edges` and picks off the
    :class:`ViewEdges` it returns, re-scanning EXPLICITLY after it changes the
    view's display. The staleness hazard then lives in one visible line of the
    recipe instead of in a cache nobody can see.
    """
    drawing_view = _early_bound(view, "IView")
    entities: list[Any] = []
    components = drawing_view.GetVisibleComponents() or []
    for component in components:
        entities.extend(
            visible_component_entities(drawing_view, component, entity_kind)
        )
    # The scan's SIZE, on the span itself. Duration alone cannot separate "this
    # view is huge" from "this seat is slow", and the callers that classify each
    # returned entity scale directly with this count.
    span = _telemetry.trace.get_current_span()
    span.set_attribute("components", len(components))
    span.set_attribute("entities", len(entities))
    span.set_attribute("entity_kind", entity_kind)
    return entities


_VIEW_ENTITY_SILHOUETTE = 4  # swViewEntityType_SilhouetteEdge


# How far a silhouette's projected line may pass from the sheet point it is
# asked for.  Projection is exact to ~1e-9 m, and the lines this separates are
# a cylinder's two flanks, a diameter apart on the sheet.
_SILHOUETTE_POINT_TOLERANCE_M = 1e-5


def _segment_distance(
    point: Sequence[float], start: Sequence[float], end: Sequence[float]
) -> float:
    """Distance on the sheet from ``point`` to the segment ``start``-``end``."""
    dx, dy = end[0] - start[0], end[1] - start[1]
    length_sq = dx * dx + dy * dy
    if length_sq == 0.0:
        return math.dist(point[:2], start[:2])
    t = ((point[0] - start[0]) * dx + (point[1] - start[1]) * dy) / length_sq
    t = min(1.0, max(0.0, t))
    return math.dist(point[:2], (start[0] + t * dx, start[1] + t * dy))


def _same_segment(first: Sequence[Any], second: Sequence[Any]) -> bool:
    """Whether two ``(entity, keys, start, end)`` lines draw the same segment."""
    a0, a1, b0, b1 = first[2], first[3], second[2], second[3]
    tol = _SILHOUETTE_POINT_TOLERANCE_M
    forward = math.dist(a0, b0) <= tol and math.dist(a1, b1) <= tol
    return forward or (math.dist(a0, b1) <= tol and math.dist(a1, b0) <= tol)


@_telemetry.traced("drawing.pick_face_silhouettes", label_param="label")
def face_silhouettes_through(
    adapter: Any,
    view: Any,
    picks: Mapping[str, tuple[Any, tuple[float, float]]],
    *,
    label: str,
) -> dict[str, Any]:
    """Resolve each pick to the one silhouette of its face drawn through its point.

    ``picks`` maps a key to ``(face spec, sheet point)``: the model face a
    silhouette must belong to (a ``_gtol_face.FaceSpec``, the one a
    ``SurfaceFinishControl`` carries) and a sheet point on the line it draws.
    A cylinder shows two flank silhouettes of one face; the point picks the
    flank.  Returns the silhouette entity per key, for the ``entity=`` path of
    the annotation helpers.

    This replaces ``SelectByID2`` at the sheet point.  That call hit-tests the
    seat's graphics window, so the same point on the same geometry can miss on
    one worker and hit on another: ``drawing:dt_pinion_arbor`` (key 870279bc)
    missed its front-journal flank at sheet (0.25355, 0.166) on
    swmaker00000a@10 and hit on swmaker000004@4, and missed on @10 again at
    the next commit.  The sweep then showed what sits under that point: the
    land's face returns its lower flank TWICE, as two coincident silhouettes,
    so the hit test had a tie to break.  The silhouettes and their faces come
    from the model, and coincident twins are taken as the one line they draw,
    so the pick reads the same on every seat.

    One ``GetVisibleEntities2(..., 4)`` sweep serves every pick (see
    :func:`visible_view_entities` for what a silhouette sweep costs); faces are
    matched before any endpoint is read, and the matched ends are projected in
    one batch.  Fails loud unless each key resolves to exactly one silhouette.
    """
    from _gtol_face_read import face_geometry

    silhouettes = visible_view_entities(view, _VIEW_ENTITY_SILHOUETTE, label=label)
    matched: list[
        tuple[Any, tuple[str, ...], tuple[float, ...], tuple[float, ...]]
    ] = []
    for silhouette in silhouettes:
        face = _com_invoke(silhouette, "ISilhouetteEdge", "GetFace")
        geometry = face_geometry(face) if face is not None else None
        if geometry is None:
            continue
        keys = tuple(
            key for key, (spec, _xy) in picks.items() if spec.matches(geometry)
        )
        if not keys:
            continue
        ends = []
        for member in ("GetStartPoint", "GetEndPoint"):
            point = _com_invoke(silhouette, "ISilhouetteEdge", member)
            values = (
                _com_invoke(point, "IMathPoint", "ArrayData")
                if point is not None
                else None
            )
            ends.append(tuple(float(v) for v in (values or ())[:3]))
        if all(len(end) == 3 for end in ends):
            matched.append((silhouette, keys, ends[0], ends[1]))
    projected = model_points_in_view(
        adapter,
        view,
        [end for _silhouette, _keys, start, stop in matched for end in (start, stop)],
        label=f"{label} silhouette ends",
    )
    lines = [
        (silhouette, keys, projected[2 * index], projected[2 * index + 1])
        for index, (silhouette, keys, _start, _stop) in enumerate(matched)
    ]
    _telemetry.annotate(silhouettes=len(silhouettes), face_matched=len(matched))
    resolved: dict[str, Any] = {}
    for key, (spec, xy) in picks.items():
        own = [line for line in lines if key in line[1]]
        hits = [
            line
            for line in own
            if _segment_distance(xy, line[2], line[3]) <= _SILHOUETTE_POINT_TOLERANCE_M
        ]
        # One drawn line can come back as several silhouettes of the same face:
        # the arbor's front-land lower flank read twice, (240.55, 166)-(260.55,
        # 166) mm both times, on swmaker000004@4 (run 20260929T224917539Z).
        # Coincident twins are one line; different lines through the point are
        # ambiguous.
        distinct = [
            line
            for index, line in enumerate(hits)
            if not any(_same_segment(line, other) for other in hits[:index])
        ]
        _telemetry.annotate(**{f"{key}_hits": len(hits), f"{key}_lines": len(distinct)})
        if len(distinct) == 1:
            hits = distinct
        if len(hits) != 1:
            drawn = "; ".join(
                f"({a[0] * 1000:.3f}, {a[1] * 1000:.3f})-({b[0] * 1000:.3f}, "
                f"{b[1] * 1000:.3f}) mm"
                for _silhouette, _keys, a, b in own
            )
            raise RuntimeError(
                f"{label}: {len(hits)} silhouettes of {key}'s face {spec!r} pass "
                f"through sheet ({xy[0] * 1000:.3f}, {xy[1] * 1000:.3f}) mm; want "
                f"exactly 1 of the {len(own)} that face draws: {drawn or 'none'} "
                f"({len(silhouettes)} silhouettes in the view)"
            )
        resolved[key] = hits[0][0]
    return resolved


@dataclass(frozen=True)
class ViewEdge:
    """One visible model edge of a drawing view with its geometry read ONCE.

    ``line`` is ``(start_mm, end_mm)`` for a straight edge; ``circle`` is
    ``(cx, cy, cz, nx, ny, nz, r)`` with the centre and radius in mm and the
    axis a unit vector, straight from ``ICurve::CircleParams``. Both are
    ``None`` for any other curve (an ellipse, a spline). ``vertices`` are the
    ``IVertex`` objects of a straight edge, in ``(start, end)`` order, for
    picks that dimension vertex-to-vertex.
    """

    edge: Any
    line: tuple[tuple[float, float, float], tuple[float, float, float]] | None
    circle: tuple[float, float, float, float, float, float, float] | None
    vertices: tuple[Any, Any] | None

    @property
    def midpoint_mm(self) -> tuple[float, float, float]:
        if self.line is None:
            raise ValueError("midpoint of a non-linear edge")
        start, end = self.line
        return tuple((a + b) / 2.0 for a, b in zip(start, end))

    @property
    def length_mm(self) -> float:
        if self.line is None:
            raise ValueError("length of a non-linear edge")
        return math.dist(*self.line)


@dataclass(frozen=True)
class ViewEdges:
    """Every visible edge of one view, classified, from ONE COM sweep.

    Holds the ``IEdge`` handles plus the geometry a picker reasons about, so
    picking N dimensions off one view costs one sweep and N pure-Python
    filters instead of N sweeps each re-reading every edge's curve and
    vertices over COM (5+ round trips per edge, 60-100 edges per view).

    **Valid only for the display state it was scanned in.** Changing the
    view's display mode, cropping it, or reversing a section's cut direction
    changes what ``GetVisibleEntities2`` returns; the recipe that made such a
    change calls :func:`scan_view_edges` again -- there is no implicit
    invalidation, by design (see ``visible_view_entities``).
    """

    label: str
    edges: tuple[ViewEdge, ...]

    @property
    def lines(self) -> tuple[ViewEdge, ...]:
        return tuple(item for item in self.edges if item.line is not None)

    @property
    def circles(self) -> tuple[ViewEdge, ...]:
        return tuple(item for item in self.edges if item.circle is not None)

    def exact_line_through(
        self, point_mm: tuple[float, float, float], *, label: str
    ) -> ViewEdge:
        """The straight visible edge whose segment passes through ``point_mm``.

        Exact (1e-8 mm^2 squared distance, within the segment's own span), so a
        point that is not ON a visible edge fails loud naming the five nearest
        segment ends -- a coordinate typo or a hidden edge can never resolve to
        the neighbour that happens to be closest.
        """
        matches = []
        for item in self.lines:
            start, end = item.line
            vector = tuple(b - a for a, b in zip(start, end))
            length_sq = sum(value * value for value in vector)
            if length_sq == 0.0:
                continue
            t = sum((p - a) * v for p, a, v in zip(point_mm, start, vector)) / length_sq
            if not -1e-6 <= t <= 1.0 + 1e-6:
                continue
            error = sum(
                (p - a - t * v) ** 2 for p, a, v in zip(point_mm, start, vector)
            )
            matches.append((error, item))
        if not matches or min(matches, key=lambda pair: pair[0])[0] > 1e-8:
            nearest = sorted(
                (
                    (
                        min(math.dist(point_mm, start), math.dist(point_mm, end)),
                        start,
                        end,
                    )
                    for start, end in (item.line for item in self.lines)
                ),
                key=lambda row: row[0],
            )[:5]
            raise RuntimeError(
                f"{label}: no exact visible line through {point_mm} in the "
                f"{self.label!r} scan; {len(self.lines)} visible lines, "
                f"nearest by endpoint={nearest}"
            )
        return min(matches, key=lambda pair: pair[0])[1]

    def exact_vertex_at(
        self, point_mm: tuple[float, float, float], *, label: str
    ) -> Any:
        """The ``IVertex`` of a visible straight edge sitting exactly at ``point_mm``."""
        best = None
        for item in self.lines:
            for point, vertex in zip(item.line, item.vertices):
                error = sum((a - b) ** 2 for a, b in zip(point_mm, point))
                if best is None or error < best[0]:
                    best = (error, vertex)
        if best is None or best[0] > 1e-8:
            raise RuntimeError(
                f"{label}: no exact visible vertex at {point_mm} in the "
                f"{self.label!r} scan"
            )
        return best[1]

    def circle_at(
        self,
        center_mm: tuple[float, float, float],
        radius_mm: float,
        *,
        axis: tuple[float, float, float] | None = None,
        label: str,
        center_tol_mm: float = 0.02,
        radius_tol_mm: float = 0.01,
    ) -> ViewEdge:
        """The visible circular edge nearest ``center_mm``/``radius_mm``.

        ``axis`` (a unit vector, either sign) pins the circle's plane so the
        two rims of one bore -- same centre in the view, opposite normals --
        cannot be confused. Fails loud past the tolerances with the nearest
        candidate's numbers, so a moved feature is a build error, never a
        dimension quietly hung on the wrong rim.
        """
        best = None
        for item in self.circles:
            cx, cy, cz, nx, ny, nz, r = item.circle
            center_error = sum(abs(a - b) for a, b in zip((cx, cy, cz), center_mm))
            radius_error = abs(r - radius_mm)
            axis_error = 0.0
            if axis is not None:
                dot = nx * axis[0] + ny * axis[1] + nz * axis[2]
                axis_error = 1.0 - abs(dot)
            score = center_error + radius_error + axis_error
            if best is None or score < best[0]:
                best = (score, center_error, radius_error, axis_error, item)
        if best is None:
            raise RuntimeError(f"{label}: the {self.label!r} scan has no circular edge")
        _score, center_error, radius_error, axis_error, item = best
        if (
            center_error > center_tol_mm
            or radius_error > radius_tol_mm
            or axis_error > 1e-6
        ):
            raise RuntimeError(
                f"{label}: no visible circle at {center_mm} r={radius_mm:g} mm in "
                f"the {self.label!r} scan; nearest centre error {center_error:.4g} mm, "
                f"radius error {radius_error:.4g} mm, axis error {axis_error:.2g}"
            )
        return item


@_telemetry.traced("drawing.view_edge_scan", label_param="label")
def scan_view_edges(view: Any, *, label: str) -> ViewEdges:
    """Sweep ``view``'s visible edges once and read each one's geometry once.

    The sweep is :func:`visible_view_entities` (kind 1, edges); the
    classification -- ``GetCurve``, ``IsLine``/``IsCircle``, the two vertices
    and their points, ``CircleParams`` -- is the part every picker used to
    repeat per dimension. Its size rides the span (``edges``/``lines``/
    ``circles``) so a slow scan reads as "this view is big", not "this seat
    is slow".
    """
    items: list[ViewEdge] = []
    for raw_edge in visible_view_entities(view, 1, label=label):
        edge = _early_bound(raw_edge, "IEdge")
        curve = edge.GetCurve()
        if curve is None:
            continue
        curve = _early_bound(curve, "ICurve")
        line = circle = vertices = None
        if curve.IsLine():
            raw_vertices = (edge.GetStartVertex(), edge.GetEndVertex())
            if all(vertex is not None for vertex in raw_vertices):
                bound = tuple(
                    _early_bound(vertex, "IVertex") for vertex in raw_vertices
                )
                start, end = (
                    tuple(float(value) * 1000.0 for value in vertex.GetPoint())
                    for vertex in bound
                )
                line, vertices = (start, end), bound
        elif curve.IsCircle():
            raw = tuple(float(value) for value in curve.CircleParams)
            circle = (
                raw[0] * 1000.0,
                raw[1] * 1000.0,
                raw[2] * 1000.0,
                raw[3],
                raw[4],
                raw[5],
                raw[6] * 1000.0,
            )
        items.append(ViewEdge(edge=edge, line=line, circle=circle, vertices=vertices))
    span = _telemetry.trace.get_current_span()
    span.set_attribute("edges", len(items))
    span.set_attribute("lines", sum(1 for item in items if item.line is not None))
    span.set_attribute("circles", sum(1 for item in items if item.circle is not None))
    return ViewEdges(label=label, edges=tuple(items))
