r"""Settings-independent closed-profile authoring for the replica recipes.

WHY THIS MODULE EXISTS
----------------------
A profile drawn as a bare sequence of ``ISketchManager.CreateLine`` /
``Create3PointArc`` calls closes into an extrudable contour only because
SolidWorks' sketch INFERENCE engine merges the coincident endpoints while they
are being drawn.  Inference and automatic relations are per-seat USER
PREFERENCES (``swSketchInference`` / ``swSketchAutomaticRelations``), and farm
worker seats are not settings-normalized -- so such a profile extrudes on one
seat and returns ``None`` on the next.  Observed 2026-09-17 on
``swmaker000005`` as ``RuntimeError: logo ring extrude failed`` from
``diag_build_91247A720.py``, on a part that had published successfully twice
the same day from other seats.

Bit-exact input coordinates are not enough by themselves either: SolidWorks
re-fits a three-point arc, so the endpoint it REALISES can differ from the
endpoint that was passed in (the replica profiles' arc endpoints are only
concyclic to ~1e-17 mm because the arc centres are 6-decimal literals).

So closure here is always AUTHORED, by writing exact coordinates straight to
the sketch database under ``ISketchManager.AddToDB = True``.  A DB write is
not drawing: the inference engine never sees it, and two segment ends written
at bit-identical coordinates are coalesced into ONE sketch point at creation.
That is the mechanism ``_common.add_line_chain`` has always relied on -- it
authors zero closure relations and its loops close on every seat.  Arcs are
authored centre-based (:func:`minor_arc`) so the only quantity SolidWorks may
re-fit is an endpoint, and the endpoint each segment passes is the same double
its neighbour passes.

No ``swConstraintType_MERGEPOINTS`` relation is authored, deliberately: that
relation merges two DISTINCT points, and applied to a pair the DB has already
coalesced, ``ISketchRelationManager.AddRelation`` returns ``None`` without
raising -- indistinguishable from a refusal, which is how it surfaced as
"SolidWorks rejected 'merge' relation" on three workers (2026-09-18,
``part:pen_set_screw`` / ``part:knife_hanger_stud``).

Nothing in this module touches COM, so it is importable -- and testable --
without a SolidWorks seat.  :func:`endpoint_merges` is the offline invariant
that makes the weld provable: it pairs endpoints on EXACT float equality and
raises when a vertex is not shared by exactly two segment ends, which is the
latent defect a profile that leans on inference to bridge a 1-ULP gap would
carry on every seat.  A vertex it accepts is a vertex the DB welds.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

type Vertex = tuple[float, float]
type EndpointRef = tuple[int, str]
type Merge = tuple[EndpointRef, EndpointRef]

# The two ends every segment kind exposes, in a fixed order so the pairing and
# the relations it drives are emitted deterministically.
ENDS: tuple[str, str] = ("start", "end")


class OpenProfileError(ValueError):
    """A profile's endpoints do not pair up into closed loops.

    Raised instead of letting SolidWorks answer the same question as a bare
    ``None`` from ``FeatureExtrusion3`` several statements later.
    """


@dataclass(frozen=True, slots=True)
class Line:
    """A straight profile segment, in sketch millimetres."""

    start: Vertex
    end: Vertex


@dataclass(frozen=True, slots=True)
class Arc:
    """A circular profile segment, in sketch millimetres.

    ``start`` -> ``end`` runs COUNTER-CLOCKWISE about ``center``, which is the
    direction ``ISketchManager.CreateArc`` is called with (the adapter's
    ``add_arc`` passes direction ``1``).  Build one with :func:`minor_arc`
    rather than ordering the endpoints by hand.

    A centre-based arc is preferred over a three-point arc: the centre and the
    radius are exactly what was authored, so the only quantity SolidWorks may
    re-fit is the endpoint -- and the endpoint is the double the neighbouring
    segment passes too, which is what lets the sketch DB weld the pair.
    """

    center: Vertex
    start: Vertex
    end: Vertex


type Segment = Line | Arc


def _ccw_sweep_deg(center: Vertex, start: Vertex, end: Vertex) -> float:
    """Counter-clockwise sweep in degrees from ``start`` to ``end``, in [0, 360)."""
    a0 = math.atan2(start[1] - center[1], start[0] - center[0])
    a1 = math.atan2(end[1] - center[1], end[0] - center[0])
    return math.degrees(a1 - a0) % 360.0


def minor_arc(center: Vertex, first: Vertex, second: Vertex) -> Arc:
    """The arc about ``center`` between the two endpoints, sweeping < 180 deg.

    The endpoints are returned in counter-clockwise order, so the caller may
    author a loop in whichever direction reads best (the replica corner arcs
    run clockwise) without having to reason about ``CreateArc``'s direction
    flag.  The endpoint COORDINATES are passed through untouched -- reordering
    them cannot perturb a double -- which is what keeps the merge pairing in
    :func:`endpoint_merges` exact.

    This is one of the two OFFLINE gates that catch the failure mode the
    91247A720 logo ring is exposed to.  Inference's nearest wrong target there
    is an outer arc's own CENTRE, 0.400 mm from its endpoints, so a snap
    collapses the arc to zero radius; an endpoint that has arrived at the
    centre is refused here, by name, before any COM call.  (The other gate is
    :func:`endpoint_merges`, which refuses any vertex not shared by exactly two
    ends.)  ``diag_mcmaster_lib.assert_profile_closed`` reads the seat's
    OUTCOME afterwards, but that is FORENSICS: it raises only on a MEASURED
    zero-contour sketch, so a collapsed corner that still closes would pass it.
    This is where a degenerate corner is caught.

    Raises:
        OpenProfileError: when an endpoint coincides with ``center`` (zero
            radius), or when the span is degenerate or exactly semicircular and
            so has no unique minor arc.
    """
    for label, point in (("start", first), ("end", second)):
        if point == center:
            raise OpenProfileError(
                f"arc about {center}: its {label} endpoint IS the centre, so the "
                "arc has zero radius -- this is the shape an inference snap to "
                "an arc centre produces"
            )
    sweep = _ccw_sweep_deg(center, first, second)
    if sweep == 0.0 or sweep == 180.0:
        raise OpenProfileError(
            f"arc about {center} between {first} and {second} sweeps {sweep} deg: "
            "a degenerate or semicircular span has no unique minor arc"
        )
    return Arc(center, first, second) if sweep < 180.0 else Arc(center, second, first)


def arc_sweep_deg(arc: Arc) -> float:
    """Counter-clockwise sweep of ``arc`` in degrees."""
    return _ccw_sweep_deg(arc.center, arc.start, arc.end)


def arc_radii_mm(arc: Arc) -> tuple[float, float]:
    """Distance from ``arc.center`` to its start and end endpoints.

    These are NOT required to be exactly equal: replica arc centres are
    rounded decimal literals, so the two radii routinely differ by an ULP.
    ``CreateArc`` takes the centre and the start radius and projects the end
    point onto that circle, so the realised end point is SolidWorks' to
    choose -- which is why closure is proved by reading the sketch back
    (:func:`endpoint_merges` over what the DB welded) instead of by trusting
    the arithmetic that went in.
    """
    return (
        math.hypot(arc.start[0] - arc.center[0], arc.start[1] - arc.center[1]),
        math.hypot(arc.end[0] - arc.center[0], arc.end[1] - arc.center[1]),
    )


def endpoint_merges(segments: tuple[Segment, ...]) -> tuple[Merge, ...]:
    """Pair every endpoint with the one segment end it must coincide with.

    Vertices are grouped on EXACT float equality: two endpoints belong to the
    same vertex only when their coordinates are the identical doubles.  A
    profile whose "coincident" endpoints differ by a single ULP therefore
    fails here, offline, instead of depending on a seat's inference settings to
    bridge the gap.

    Raises:
        OpenProfileError: when a segment's two ends are the SAME vertex, or
            when any vertex is not shared by exactly two segment ends -- a
            dangling end, or three segments meeting at a point.
    """
    groups: dict[Vertex, list[EndpointRef]] = {}
    for index, segment in enumerate(segments):
        ends = tuple(getattr(segment, end) for end in ENDS)
        # A zero-length segment contributes BOTH of its ends to one vertex, so
        # it satisfies the degree-two test below by pairing with ITSELF, and
        # closed_loops then counts it as a loop of its own -- a "closed"
        # profile with no area, authored straight into add_line/add_arc.  It is
        # the one shape that passes the pairing while being unextrudable, and
        # it is exactly what a snap that collapses a segment produces, so it is
        # refused here beside the dangling-end case.  (minor_arc already
        # refuses the arc form at construction; this covers a Line, and an Arc
        # built without going through minor_arc.)
        if ends[0] == ends[1]:
            raise OpenProfileError(
                f"segment {index} starts and ends at {ends[0]}: a zero-length "
                "segment pairs with itself, so it would pass the degree-two "
                "test and be authored as a loop enclosing nothing"
            )
        for end, vertex in zip(ENDS, ends, strict=True):
            groups.setdefault(vertex, []).append((index, end))
    merges: list[Merge] = []
    for vertex, refs in groups.items():
        if len(refs) != 2:
            detail = ", ".join(f"segment {i} {end}" for i, end in refs)
            raise OpenProfileError(
                f"vertex {vertex} is shared by {len(refs)} segment ends "
                f"({detail or 'none'}), expected exactly 2: the profile is open, "
                "so no inference setting can make it extrude reliably"
            )
        merges.append((refs[0], refs[1]))
    return tuple(merges)


def closed_loops(segments: tuple[Segment, ...]) -> tuple[tuple[int, ...], ...]:
    """Group segment indices into loops connected through shared vertices.

    Call :func:`endpoint_merges` first: with every vertex of degree two, each
    group returned here is a closed loop.  The count is what the caller asserts
    (a ring profile is two loops, a plain region one).
    """
    parent = list(range(len(segments)))

    def find(node: int) -> int:
        while parent[node] != node:
            parent[node] = parent[parent[node]]
            node = parent[node]
        return node

    seen: dict[Vertex, int] = {}
    for index, segment in enumerate(segments):
        for end in ENDS:
            vertex = getattr(segment, end)
            other = seen.setdefault(vertex, index)
            root_a, root_b = find(index), find(other)
            if root_a != root_b:
                parent[root_b] = root_a
    loops: dict[int, list[int]] = {}
    for index in range(len(segments)):
        loops.setdefault(find(index), []).append(index)
    return tuple(tuple(group) for group in loops.values())
