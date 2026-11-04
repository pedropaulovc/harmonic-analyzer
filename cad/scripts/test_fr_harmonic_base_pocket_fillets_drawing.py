"""Offline proof for the harmonic base's underside-pocket corner fillets.

COORD ruling (a) on the fr_harmonic_base machinist review (clarity 4, rule 16
(design for the cutter)): every pocket corner still drawn sharp in the bottom
views gets a modelled fillet of ONE radius, printed "nX Rr MAX", the largest
standard radius up to R.23 (the boss-to-wall fillets' radius, the largest .XX
inch radius within the former R6) that keeps rule 17 (walls and webs) at the
worst case.

Scope: the VERTICAL concave edges -- rib to wall, rib to rib, and retained
cross-tap lug to wall or socket boss. The pocket's own four plan corners lie
inside socket bosses; PocketFillets rounds their eight wall junctions.
Horizontal root edges remain process geometry, not extra plan fillets.
All eleven round deck-seat islands and five rectangular pads are removed;
their former junctions must not survive in the corner census or volume.

Everything here is derived from the build's own plan shapes: the corner set,
each fillet's tangent points and plan section, the worst-case wall from every
deck seat, column socket and cross tap to every new fillet, and the pick
point the native feature selects each edge by. The build's own
_pocket_corner_fillets (PocketCornerFillets' picks, edge lengths and the
closed-form sections its volume check sums) must match this enumeration.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from functools import cache

import numpy as np
import pytest

from _hole_spec import TAP_DRILL_MM, THREAD_MAJOR_MM
from _inch_wall_limits import WALL_FLOOR_MM, WALL_TARGET_MM
from _printed_tolerance import drilled_oversize_mm
import build_fr_harmonic_base as base
import fr_harmonic_base_spec as spec
import fr_harmonic_base_fasteners as fasteners

# Standard casting-fillet radii, largest first, capped at the R.23 the
# socket-boss junctions already carry: .23, .19, .16, .12, .10, .08.
STANDARD_RADII = (5.842, 4.826, 4.064, 3.048, 2.54, 2.032)
LIGAMENT_FLOOR = WALL_FLOOR_MM  # rule 17 (walls and webs): hard floor

_BAND = base._general_band_mm()  # .XX: bounds every location term (.010)
# A cast outline moves by its location band plus half its size band.
_CAST_SHIFT = _BAND + _BAND / 2.0
# Two cast features can each run that far toward one another.
_RELATIVE_CAST_SHIFT = 2.0 * _CAST_SHIFT
_DRILL_OVERSIZE_R = drilled_oversize_mm(unit=spec.UNIT) / 2.0
_HOLE_SHIFT = math.hypot(_BAND, _BAND)  # both table coordinates against it
_CEILING = base.POCKET_CEILING_Y
_ARC_SAMPLES = 96
_PICK_TOLERANCE = 0.5  # _select_edges_geometric's default hit radius (mm)
_FACE_LOOKAHEAD = 20.0  # face run scanned past each tangent point (mm)

Point = tuple[float, float]


# --- Plan features: what hangs from the ceiling, and the wall around it. ---


@dataclass(frozen=True)
class Feature:
    """One plan shape standing from ``bottom_y`` up to the pocket ceiling.

    The pocket wall is the rect's complement: metal OUTSIDE the outline.
    """

    kind: str
    name: str
    shape: tuple
    bottom_y: float
    wall: bool = False

    def contains(self, x, z, eps: float = 1e-6):
        """True where (x, z) lies strictly inside this feature's metal
        (scalars or arrays)."""
        if self.wall:
            _k, x0, x1, z0, z1 = self.shape
            inside = (x >= x0 - eps) & (x <= x1 + eps) & (z >= z0 - eps)
            return np.logical_not(inside & (z <= z1 + eps))
        if self.shape[0] == "disc":
            _k, cx, cz, r = self.shape
            return np.hypot(x - cx, z - cz) < r - eps
        _k, x0, x1, z0, z1 = self.shape
        return (x > x0 + eps) & (x < x1 - eps) & (z > z0 + eps) & (z < z1 - eps)

    def clearance(self, pts: np.ndarray) -> np.ndarray:
        """Plan distance from each point to this feature's metal (0 inside)."""
        x, z = pts[:, 0], pts[:, 1]
        if self.wall:
            _k, x0, x1, z0, z1 = self.shape
            return np.maximum(0.0, np.minimum.reduce([x - x0, x1 - x, z - z0, z1 - z]))
        if self.shape[0] == "disc":
            _k, cx, cz, r = self.shape
            return np.maximum(0.0, np.hypot(x - cx, z - cz) - r)
        _k, x0, x1, z0, z1 = self.shape
        dx = np.maximum.reduce([x0 - x, np.zeros_like(x), x - x1])
        dz = np.maximum.reduce([z0 - z, np.zeros_like(z), z - z1])
        return np.hypot(dx, dz)


def _at(xz: tuple[float, float]) -> str:
    return f"({xz[0]:+.1f}, {xz[1]:+.1f})"


def _shape_label(shape: tuple) -> str:
    if shape[0] == "disc":
        return _at(shape[1:3])
    _k, x0, x1, z0, z1 = shape
    return _at(((x0 + x1) / 2.0, (z0 + z1) / 2.0))


@cache
def pocket_features() -> tuple[Feature, ...]:
    """The retained wall, four socket bosses, two ribs and four cross-tap lugs."""
    pocket = ("rect", -base.POCKET_HALF_X, base.POCKET_HALF_X)
    pocket += (-base.POCKET_HALF_Z, base.POCKET_HALF_Z)
    features = [Feature("pocket wall", "pocket wall", pocket, 0.0, wall=True)]
    features += [
        Feature("socket boss", f"socket boss {_shape_label(s)}", s, 0.0)
        for s in base.SOCKET_BOSS_SHAPES
    ]
    features += [
        Feature("long rib", "long rib", base.LONG_RIB_SHAPE, base.RIB_RELIEF),
        Feature("cross rib", "cross rib", base.CROSS_RIB_SHAPE, base.RIB_RELIEF),
    ]
    features += [
        Feature(
            "cross-tap lug",
            f"cross-tap lug {_shape_label(shape)}",
            shape,
            base.CROSS_TAP_LUG_BOTTOM_Y,
        )
        for shape in base.CROSS_TAP_LUG_SHAPES
    ]
    names = [f.name for f in features]
    if len(set(names)) != len(names):
        raise AssertionError(f"pocket feature names collide: {names}")
    return tuple(features)


# --- Boundary primitives and their crossings. ---


@dataclass(frozen=True)
class Line:
    """A straight plan face; ``normal`` points into the pocket's air."""

    feature: Feature
    start: Point
    end: Point
    normal: Point

    @property
    def length(self) -> float:
        return math.dist(self.start, self.end)

    @property
    def direction(self) -> np.ndarray:
        return (np.array(self.end) - np.array(self.start)) / self.length

    def param(self, p) -> float:
        return float(np.dot(np.array(p) - np.array(self.start), self.direction))


@dataclass(frozen=True)
class Circle:
    """A round boss's cylinder; the air lies outside it."""

    feature: Feature
    centre: Point
    radius: float


def _primitives(feature: Feature) -> tuple[Line | Circle, ...]:
    if feature.shape[0] == "disc":
        _k, cx, cz, r = feature.shape
        return (Circle(feature, (cx, cz), r),)
    _k, x0, x1, z0, z1 = feature.shape
    sign = -1.0 if feature.wall else 1.0
    return (
        Line(feature, (x0, z0), (x1, z0), (0.0, -sign)),
        Line(feature, (x1, z0), (x1, z1), (sign, 0.0)),
        Line(feature, (x1, z1), (x0, z1), (0.0, sign)),
        Line(feature, (x0, z1), (x0, z0), (-sign, 0.0)),
    )


def _on_segments(p, *lines: Line, eps: float = 1e-9) -> bool:
    """True when p lies on every segment; a crossing exactly at a segment's
    end (a face ending on another) is a contact this proof does not model."""
    params = [(line, line.param(p)) for line in lines]
    if not all(-eps <= t <= line.length + eps for line, t in params):
        return False
    for line, t in params:
        if min(abs(t), abs(t - line.length)) < 1e-6:
            raise AssertionError(
                f"{line.feature.name}: a face ends exactly on another at {_at(p)}"
            )
    return True


def _crossings(a: Line | Circle, b: Line | Circle) -> list[Point]:
    """Plan points where two features' faces cross."""
    if isinstance(a, Circle) and isinstance(b, Line):
        a, b = b, a
    if isinstance(a, Line) and isinstance(b, Line):
        da, db = a.direction, b.direction
        det = da[0] * -db[1] + db[0] * da[1]
        if abs(det) < 1e-12:
            offset = np.array(b.start) - np.array(a.start)
            if abs(float(np.dot(offset, a.normal))) < 1e-6 and (
                max(a.param(b.start), a.param(b.end)) > 1e-6
                and min(a.param(b.start), a.param(b.end)) < a.length - 1e-6
            ):
                raise AssertionError(
                    f"{a.feature.name} and {b.feature.name} share a face"
                )
            return []
        rhs = np.array(b.start) - np.array(a.start)
        s = (rhs[0] * -db[1] + db[0] * rhs[1]) / det
        p = tuple(np.array(a.start) + s * da)
        return [p] if _on_segments(p, a, b) else []
    if isinstance(a, Line):
        f = np.array(a.start) - np.array(b.centre)
        half_b = float(np.dot(f, a.direction))
        disc = half_b * half_b - (float(np.dot(f, f)) - b.radius**2)
        if disc <= 1e-12:
            return []
        points = []
        for t in (-half_b - math.sqrt(disc), -half_b + math.sqrt(disc)):
            p = tuple(np.array(a.start) + t * a.direction)
            if _on_segments(p, a):
                points.append(p)
        return points
    gap = math.dist(a.centre, b.centre)
    if gap < a.radius + b.radius:
        raise AssertionError(f"{a.feature.name} crosses {b.feature.name}")
    return []


# --- The corner set. ---


@dataclass(frozen=True)
class Corner:
    """One vertical reentrant edge: two features' faces crossing in plan."""

    face_a: Line | Circle
    face_b: Line | Circle
    point: Point
    y_lo: float
    y_hi: float

    @property
    def features(self) -> tuple[Feature, Feature]:
        return self.face_a.feature, self.face_b.feature

    @property
    def kind(self) -> tuple[str, str]:
        return tuple(sorted(f.kind for f in self.features))

    @property
    def name(self) -> str:
        a, b = self.features
        return f"{a.name} / {b.name} at {_at(self.point)}"

    @property
    def length(self) -> float:
        return self.y_hi - self.y_lo

    @property
    def existing(self) -> bool:
        """One of the eight socket-boss junctions PocketFillets rounds."""
        return self.kind == ("pocket wall", "socket boss")

    @property
    def pick(self) -> list[float]:
        """Mid-height point on the edge, for add_fillet's edge selection."""
        return [self.point[0], (self.y_lo + self.y_hi) / 2.0, self.point[1]]


@cache
def pocket_corners() -> tuple[Corner, ...]:
    """Every vertical concave edge in the pocket, with its exposed height.

    Two convex shapes whose faces cross make a reentrant corner on their
    union. It runs from the higher of the two bottoms up to the ceiling,
    less any height where a third feature (or the wall) swallows it.
    """
    features = pocket_features()
    corners = []
    for i, a in enumerate(features):
        for b in features[i + 1 :]:
            for face_a in _primitives(a):
                for face_b in _primitives(b):
                    for p in _crossings(face_a, face_b):
                        y_lo = max(a.bottom_y, b.bottom_y)
                        y_hi = min(
                            [_CEILING]
                            + [
                                c.bottom_y
                                for c in features
                                if c not in (a, b) and c.contains(*p)
                            ]
                        )
                        if y_hi - y_lo > 1e-6:
                            corners.append(Corner(face_a, face_b, p, y_lo, y_hi))
    return tuple(corners)


def new_corners() -> tuple[Corner, ...]:
    return tuple(c for c in pocket_corners() if not c.existing)


def existing_corners() -> tuple[Corner, ...]:
    return tuple(c for c in pocket_corners() if c.existing)


# --- One fillet's geometry. ---


def _arc_points(centre, radius: float, p0, p1, n: int = _ARC_SAMPLES) -> np.ndarray:
    c = np.array(centre)
    a0 = math.atan2(p0[1] - c[1], p0[0] - c[0])
    a1 = math.atan2(p1[1] - c[1], p1[0] - c[0])
    sweep = (a1 - a0 + math.pi) % (2.0 * math.pi) - math.pi
    angles = a0 + sweep * np.linspace(0.0, 1.0, n)
    return c + radius * np.column_stack([np.cos(angles), np.sin(angles)])


def _tangent(face: Line | Circle, centre: np.ndarray, r: float) -> np.ndarray:
    if isinstance(face, Line):
        return centre - r * np.array(face.normal)
    c = np.array(face.centre)
    return c + face.radius * (centre - c) / np.linalg.norm(centre - c)


def _air_side(face: Line | Circle, p: Point, q: np.ndarray) -> bool:
    """True when q lies in the air beside ``face`` (strictly)."""
    if isinstance(face, Line):
        return float(np.dot(q - np.array(p), face.normal)) > 1e-9
    return math.dist(q, face.centre) > face.radius + 1e-9


def _centres(a: Line | Circle, b: Line | Circle, r: float) -> list[np.ndarray]:
    """Points r clear of both faces on their air sides (offset crossings)."""
    if isinstance(a, Circle) and isinstance(b, Line):
        a, b = b, a
    if isinstance(a, Line) and isinstance(b, Line):
        normals = np.array([a.normal, b.normal])
        rhs = np.array(
            [
                np.dot(a.normal, a.start) + r,
                np.dot(b.normal, b.start) + r,
            ]
        )
        return [np.linalg.solve(normals, rhs)]
    if isinstance(a, Line):
        start = np.array(a.start) + r * np.array(a.normal)
        f = start - np.array(b.centre)
        half_b = float(np.dot(f, a.direction))
        disc = half_b * half_b - (float(np.dot(f, f)) - (b.radius + r) ** 2)
        if disc < 0.0:
            return []
        return [
            start + t * a.direction
            for t in (-half_b - math.sqrt(disc), -half_b + math.sqrt(disc))
        ]
    raise AssertionError(f"{a.feature.name} / {b.feature.name}: boss-to-boss corner")


@dataclass(frozen=True)
class Fillet:
    corner: Corner
    radius: float
    centre: np.ndarray
    tangent_a: np.ndarray
    tangent_b: np.ndarray

    @property
    def zone(self) -> np.ndarray:
        """The fillet's plan section as a closed polygon: corner, along face
        a to its tangent point, round the fillet arc, back along face b."""
        p = np.array(self.corner.point)
        legs = []
        for face, tangent in (
            (self.corner.face_a, self.tangent_a),
            (self.corner.face_b, self.tangent_b),
        ):
            if isinstance(face, Line):
                legs.append(np.array([p, tangent]))
            else:
                legs.append(_arc_points(face.centre, face.radius, p, tangent))
        arc = _arc_points(self.centre, self.radius, self.tangent_a, self.tangent_b)
        return np.vstack([legs[0], arc[1:], legs[1][::-1][1:]])

    @property
    def area(self) -> float:
        x, z = self.zone[:, 0], self.zone[:, 1]
        return 0.5 * abs(float(np.dot(x, np.roll(z, -1)) - np.dot(z, np.roll(x, -1))))

    def face_slack(self) -> list[tuple[float, str]]:
        """For each face: how far it runs on past the fillet's tangent point
        before it ends at a convex corner or a third feature takes it over.
        A fillet that ran off its face would eat the retained rib or lug."""
        p = np.array(self.corner.point)
        others = [c for c in pocket_features() if c not in self.corner.features]
        slacks = []
        for face, tangent in (
            (self.corner.face_a, self.tangent_a),
            (self.corner.face_b, self.tangent_b),
        ):
            if isinstance(face, Line):
                step = (tangent - p) / np.linalg.norm(tangent - p)
                need = float(np.linalg.norm(tangent - p))
                run = np.arange(0.05, need + _FACE_LOOKAHEAD, 0.05)
                pts = p + np.outer(run, step)
                t = (pts - np.array(face.start)) @ face.direction
                off_face = (t < -1e-9) | (t > face.length + 1e-9)
            else:
                c = np.array(face.centre)
                a0 = math.atan2(*(p - c)[::-1])
                a1 = math.atan2(*(tangent - c)[::-1])
                sweep = (a1 - a0 + math.pi) % (2.0 * math.pi) - math.pi
                need = abs(sweep) * face.radius
                run = np.arange(0.05, need + _FACE_LOOKAHEAD, 0.05)
                angles = a0 + math.copysign(1.0, sweep) * run / face.radius
                pts = c + face.radius * np.column_stack(
                    [np.cos(angles), np.sin(angles)]
                )
                off_face = np.zeros(len(pts), dtype=bool)
            first = len(pts)
            why = f"{face.feature.name} face runs on"
            if off_face.any():
                first = int(np.argmax(off_face))
                why = f"{face.feature.name} face ends"
            for other in others:
                hit = other.contains(pts[:first, 0], pts[:first, 1])
                if hit.any():
                    first = int(np.argmax(hit))
                    why = f"{face.feature.name} face meets {other.name}"
            slack = float(run[first]) - need if first < len(pts) else _FACE_LOOKAHEAD
            slacks.append((slack, why))
        return slacks


def fillet(corner: Corner, r: float) -> Fillet:
    p = np.array(corner.point)
    a, b = corner.face_a, corner.face_b
    valid = []
    for centre in _centres(a, b, r):
        ta, tb = _tangent(a, centre, r), _tangent(b, centre, r)
        if _air_side(b, corner.point, ta) and _air_side(a, corner.point, tb):
            valid.append((float(np.linalg.norm(centre - p)), centre, ta, tb))
    if not valid:
        raise AssertionError(f"no R{r:g} fillet fits {corner.name}")
    _d, centre, ta, tb = min(valid, key=lambda v: v[0])
    return Fillet(corner, r, centre, ta, tb)


# --- Holes and their worst-case walls to a fillet. ---


@dataclass(frozen=True)
class VerticalHole:
    label: str
    centre: Point
    radius: float  # worst case: thread major, or drill + DRILLED HOLES band
    y_lo: float
    y_hi: float
    shift: float  # worst-case plan location error
    depth_band: float


@dataclass(frozen=True)
class CrossTap:
    label: str
    x: float
    y: float
    z_span: tuple[float, float]
    radius: float
    shift: float
    depth_band: float


def _seat_radius(size: str, drill_dia: float) -> float:
    return max(THREAD_MAJOR_MM[size] / 2.0, drill_dia / 2.0 + _DRILL_OVERSIZE_R)


@cache
def pocket_holes() -> tuple[VerticalHole | CrossTap, ...]:
    """All eighteen through deck seats, four sockets and four cross taps."""
    holes: list[VerticalHole | CrossTap] = []
    for tag, seat, stations, envelope in base.THROUGH_SEAT_GROUPS:
        for xz, material in zip(stations, base.THROUGH_SEAT_MATERIAL[tag], strict=True):
            bottom_depth = max(end for _start, end in material.nominal_segments_mm)
            holes.append(
                VerticalHole(
                    f"{tag} seat {_at(xz)}",
                    xz,
                    _seat_radius(seat.size, TAP_DRILL_MM[seat.size]),
                    base.STACK_HEIGHT - bottom_depth,
                    base.STACK_HEIGHT,
                    _HOLE_SHIFT + math.hypot(*envelope),
                    3.0 * _BAND,
                )
            )
    for xz in base.COLUMN_SOCKET_XZ:
        holes.append(
            VerticalHole(
                f"column socket {_at(xz)}",
                xz,
                base.COLUMN_SOCKET_MATCH_BORE_MAX / 2.0,
                base.GREEN_TOP - base.COLUMN_SOCKET_DEPTH,
                base.GREEN_TOP,
                _HOLE_SHIFT,
                _BAND,
            )
        )
    tap_radius = _seat_radius(
        base.BASE_CROSS_TAP_SPEC.size, base.BASE_CROSS_TAP_DRILL_DIA
    )
    for x, z in base.COLUMN_SOCKET_XZ:
        sign = math.copysign(1.0, z)
        span = sorted((sign * base.BASE_SCREW_SEAT_Z, sign * base.CROSS_TAP_TIP_Z))
        holes.append(
            CrossTap(
                f"cross tap {_at((x, z))}",
                x,
                base.BASE_SCREW_Y,
                tuple(span),
                tap_radius,
                _HOLE_SHIFT,
                _BAND,
            )
        )
    return tuple(holes)


def _inside(poly: np.ndarray, pts) -> np.ndarray:
    """Even-odd test of each point (rows of ``pts``) against ``poly``."""
    pts = np.atleast_2d(np.asarray(pts, dtype=float))
    x0, z0 = poly[:, 0], poly[:, 1]
    x1, z1 = np.roll(x0, -1), np.roll(z0, -1)
    x, z = pts[:, :1], pts[:, 1:]
    straddle = (z0 > z) != (z1 > z)
    with np.errstate(divide="ignore", invalid="ignore"):
        x_cross = x0 + (z - z0) * (x1 - x0) / (z1 - z0)
    return ((straddle & (x < x_cross)).sum(axis=1) % 2).astype(bool)


def _point_polygon_distance(poly: np.ndarray, pts: np.ndarray) -> np.ndarray:
    a = poly
    b = np.roll(poly, -1, axis=0)
    ab = b - a
    ap = pts[:, None, :] - a[None, :, :]
    t = np.clip(
        np.einsum("ijk,jk->ij", ap, ab)
        / np.maximum(np.einsum("jk,jk->j", ab, ab), 1e-18),
        0.0,
        1.0,
    )
    nearest = a[None, :, :] + t[:, :, None] * ab[None, :, :]
    return np.linalg.norm(pts[:, None, :] - nearest, axis=2).min(axis=1)


def _worst(plan: float, rise: float) -> float:
    """Worst-case wall from a plan gap and a vertical gap (each already
    reduced by its bands): the 3D distance where both are open."""
    if rise <= 0.0:
        return plan
    if plan <= 0.0:
        return rise
    return math.hypot(plan, rise)


def hole_ligament(hole: VerticalHole | CrossTap, f: Fillet) -> float:
    """Worst-case metal between a hole and a fillet's whole plan section
    (corner to arc), so a smaller-than-max fillet is covered too."""
    zone = f.zone
    y_lo, y_hi = f.corner.y_lo, f.corner.y_hi
    if isinstance(hole, VerticalHole):
        if _inside(zone, hole.centre)[0]:
            return -math.inf
        plan = float(_point_polygon_distance(zone, np.array([hole.centre]))[0])
        plan -= hole.radius + hole.shift + _CAST_SHIFT
        rise = max(0.0, y_lo - hole.y_hi, hole.y_lo - y_hi)
        return _worst(plan, rise - hole.depth_band - _BAND)
    dense = np.vstack(
        [
            np.linspace(p0, p1, 16)
            for p0, p1 in zip(zone, np.roll(zone, -1, axis=0), strict=True)
        ]
    )
    dx = np.abs(dense[:, 0] - hole.x)
    z0, z1 = hole.z_span
    dz = np.maximum.reduce([dense[:, 1] - z1, np.zeros(len(dense)), z0 - dense[:, 1]])
    dz = np.maximum(0.0, dz - hole.depth_band)
    dy = abs(min(max(hole.y, y_lo), y_hi) - hole.y)
    gap = np.sqrt(dx**2 + dy**2 + dz**2) - hole.radius - hole.shift - _CAST_SHIFT
    return float(gap.min())


# --- The radius proof. ---


def _zone_gap(f: Fillet, g: Fillet) -> float:
    za, zb = f.zone, g.zone
    if _inside(zb, za).any() or _inside(za, zb).any():
        return -math.inf
    return float(
        min(
            _point_polygon_distance(zb, za).min(),
            _point_polygon_distance(za, zb).min(),
        )
    )


def _heights_overlap(a: Corner, b: Corner) -> bool:
    return min(a.y_hi, b.y_hi) - max(a.y_lo, b.y_lo) > 1e-6


@dataclass(frozen=True)
class Margin:
    value: float
    what: str


def radius_margins(r: float) -> dict[str, Margin]:
    """The tightest worst-case margin of each kind at radius r.

    - "ligament": hole wall to a new fillet's section, against the 1.5 floor;
    - "face run": face left past a tangent point before the face ends (a
      convex corner) or another feature takes it, against the relative cast
      shift -- a fillet must not run off a retained rib or lug face;
    - "feature gap": air between a new fillet and any third feature;
    - "fillet gap": air between two fillets (new or existing R6) that share
      height, so no fillet bridges into another at the worst case.
    """
    features = pocket_features()
    existing = [fillet(c, base.POCKET_CORNER_FILLET_R) for c in existing_corners()]
    new = [fillet(c, r) for c in new_corners()]
    margins: dict[str, Margin] = {}

    def keep(kind: str, value: float, what: str) -> None:
        if kind not in margins or value < margins[kind].value:
            margins[kind] = Margin(value, what)

    for f in new:
        others = [c for c in features if c not in f.corner.features]
        for slack, why in f.face_slack():
            keep(
                "face run",
                slack - _RELATIVE_CAST_SHIFT,
                f"{f.corner.name}: {why} {slack:.2f} past the tangent",
            )
        zone = f.zone
        for c in others:
            gap = float(c.clearance(zone).min()) - _RELATIVE_CAST_SHIFT
            keep("feature gap", gap, f"{f.corner.name} to {c.name}")
        for g in (*existing, *new):
            if g is f or not _heights_overlap(f.corner, g.corner):
                continue
            gap = _zone_gap(f, g) - _RELATIVE_CAST_SHIFT
            keep("fillet gap", gap, f"{f.corner.name} to {g.corner.name}")
        for hole in pocket_holes():
            keep("ligament", hole_ligament(hole, f), f"{hole.label} to {f.corner.name}")
    return margins


def radius_violations(r: float) -> list[str]:
    floors = {
        "ligament": LIGAMENT_FLOOR,
        "face run": 0.0,
        "feature gap": 0.0,
        "fillet gap": 0.0,
    }
    try:
        margins = radius_margins(r)
    except AssertionError as exc:
        return [str(exc)]
    return [
        f"R{r:g} {kind}: {m.value:.2f} < {floors[kind]:.2f} ({m.what})"
        for kind, m in margins.items()
        if m.value < floors[kind] - 1e-9
    ]


@cache
def chosen_radius() -> float:
    for r in STANDARD_RADII:
        if not radius_violations(r):
            return r
    raise AssertionError(
        "no standard radius >= R2 clears the pocket corners: "
        + "; ".join(radius_violations(STANDARD_RADII[-1]))
    )


def _skin_exit_clearances(
    seat,
    xz: Point,
    envelope: Point = (0.0, 0.0),
) -> dict[str, float]:
    """Independent full-footprint air gaps to every retained shape and fillet patch.

    Enclose the transfer rectangle in its circumscribed circle. Three printed
    .XX bands, their half-last-place rounding and the edge break bound each
    axial separating face; sqrt(2) encloses both adverse coordinate shifts.
    The native corner polygons need a chord allowance as well: an arc sample
    must never turn a touching bore into a clear one.
    """
    radius = _seat_radius(seat.size, TAP_DRILL_MM[seat.size])
    rounding = 0.05
    edge_break = fasteners.EDGE_BREAK_MAX_MM
    axial_shift = 3.0 * (_BAND + rounding) + edge_break
    reach = radius + math.hypot(*envelope) + math.sqrt(2.0) * axial_shift
    point = np.array([xz])
    gaps = {f.name: float(f.clearance(point)[0]) - reach for f in pocket_features()}
    chord = max(spec.SOCKET_BOSS_DIA / 2.0, spec.POCKET_CORNER_FILLET_R) * (
        1.0 - math.cos(math.pi / (2.0 * (_ARC_SAMPLES - 1)))
    )
    for corner in pocket_corners():
        zone = fillet(corner, spec.POCKET_CORNER_FILLET_R).zone
        gap = (
            0.0
            if _inside(zone, xz)[0]
            else float(_point_polygon_distance(zone, point)[0])
        )
        gaps[f"fillet {corner.name}"] = gap - reach - chord
    return gaps


# --- Tests. ---

_RIB_H = base.POCKET_CEILING_Y - base.RIB_RELIEF
_LUG_H = base.POCKET_CEILING_Y - base.CROSS_TAP_LUG_BOTTOM_Y
# (kind pair) -> (count, edge length). A change to the pocket that adds,
# drops or re-heights a corner must revisit the build's _pocket_corner_fillets.
EXPECTED_NEW_CORNERS = {
    ("long rib", "pocket wall"): (4, _RIB_H),
    ("cross rib", "pocket wall"): (4, _RIB_H),
    ("cross rib", "long rib"): (4, _RIB_H),
    ("cross-tap lug", "pocket wall"): (4, _LUG_H),
    ("cross-tap lug", "socket boss"): (4, _LUG_H),
}


def test_corner_set_is_the_retained_twenty_plus_the_existing_eight() -> None:
    found: dict[tuple[str, str], list[Corner]] = {}
    for corner in new_corners():
        found.setdefault(corner.kind, []).append(corner)
    assert set(found) == set(EXPECTED_NEW_CORNERS), sorted(found)
    for kind, (count, length) in EXPECTED_NEW_CORNERS.items():
        corners = found[kind]
        assert len(corners) == count, (kind, [c.name for c in corners])
        for corner in corners:
            assert corner.length == pytest.approx(length), corner.name
            assert corner.y_hi == pytest.approx(_CEILING), corner.name
    assert len(new_corners()) == 20


def test_existing_corners_are_pocket_fillets_eight_junctions() -> None:
    corners = existing_corners()
    assert len(corners) == 8
    # End-wall junctions stop under the lug; side-wall ones run full depth.
    heights = sorted(c.y_hi for c in corners)
    assert heights == pytest.approx(
        [base.CROSS_TAP_LUG_BOTTOM_Y] * 4 + [base.POCKET_CEILING_Y] * 4
    )
    assert all(c.y_lo == 0.0 for c in corners)
    areas = sorted(fillet(c, base.POCKET_CORNER_FILLET_R).area for c in corners)
    assert areas == pytest.approx(sorted(base._pocket_fillet_areas()), rel=2e-3)


def test_pocket_plan_corners_lie_inside_the_socket_bosses() -> None:
    bosses = [f for f in pocket_features() if f.kind == "socket boss"]
    for sx in (-1.0, 1.0):
        for sz in (-1.0, 1.0):
            corner = (sx * base.POCKET_HALF_X, sz * base.POCKET_HALF_Z)
            assert any(b.contains(*corner) for b in bosses), (
                f"pocket plan corner {_at(corner)} is exposed and needs a fillet"
            )


def test_chosen_radius_is_the_largest_standard_one_that_clears() -> None:
    r = chosen_radius()
    assert r == base.POCKET_CORNER_FILLET_R, radius_violations(r)
    larger = [c for c in STANDARD_RADII if c > r]
    if larger:
        assert radius_violations(min(larger)), f"R{min(larger):g} also clears"
    else:
        assert r == max(STANDARD_RADII)


def test_every_hole_keeps_the_ligament_floor_to_every_modelled_max_fillet() -> None:
    fillets = [fillet(c, spec.POCKET_CORNER_FILLET_R) for c in pocket_corners()]
    worst = min(
        (hole_ligament(h, f), h.label, f.corner.name)
        for h in pocket_holes()
        for f in fillets
    )
    assert worst[0] >= LIGAMENT_FLOOR, (
        f"{worst[1]} keeps {worst[0]:.2f} to the R{base.POCKET_CORNER_FILLET_R:g} "
        f"fillet at {worst[2]} at the worst case, under {LIGAMENT_FLOOR}"
    )


def test_holes_cover_every_seat_group_socket_and_cross_tap() -> None:
    holes = pocket_holes()
    seats = sum(
        len(stations) for _tag, _seat, stations, _bounds in base.THROUGH_SEAT_GROUPS
    )
    assert seats == 18
    assert len(holes) == seats + 2 * len(base.COLUMN_SOCKET_XZ)
    assert {tag for tag, _seat, _stations, _bounds in base.THROUGH_SEAT_GROUPS} == {
        "SupportHoldDownSeats",
        "PivotSeat",
        "LockSeat",
        "StopSeat",
        "BlockScrewHoles",
        "FootScrewHoles",
        "PedestalSeats",
        "NameplateSeats",
    }


def test_through_seat_axis_material_matches_the_independent_retained_profile() -> None:
    """The cutting interval follows actual retained material, not a removed
    seat island or an assumed uniform skin. Fillet metal is included only
    where its independently enumerated added plan section contains the axis."""
    features = pocket_features()
    fillets = [fillet(c, base.POCKET_CORNER_FILLET_R) for c in pocket_corners()]
    for tag, _seat, stations, _bounds in base.THROUGH_SEAT_GROUPS:
        for xz, material in zip(stations, base.THROUGH_SEAT_MATERIAL[tag], strict=True):
            bottoms = [_CEILING]
            bottoms.extend(
                f.bottom_y
                for f in features
                if float(f.clearance(np.array([xz]))[0]) <= 1e-9
            )
            bottoms.extend(f.corner.y_lo for f in fillets if _inside(f.zone, xz)[0])
            expected_bottom = min(bottoms)
            assert len(material.nominal_segments_mm) == 1
            assert material.nominal_segments_mm[0] == pytest.approx(
                (0.0, base.STACK_HEIGHT - expected_bottom),
            ), (tag, xz)
    assert all(
        f.kind
        in {
            "pocket wall",
            "socket boss",
            "long rib",
            "cross rib",
            "cross-tap lug",
        }
        for f in features
    )


def test_shifted_whole_rib_keeps_its_full_section_and_eight_real_connections() -> None:
    cross = next(f for f in pocket_features() if f.kind == "cross rib")
    left = spec.CROSS_RIB_CENTER_X - spec.RIB_THICKNESS / 2.0
    right = spec.CROSS_RIB_CENTER_X + spec.RIB_THICKNESS / 2.0
    assert (left, right) == pytest.approx((6.096, 16.002))  # .240, .630
    assert cross.shape == (
        "rect",
        left,
        right,
        -base.RIB_HALF_LENGTH_Z,
        base.RIB_HALF_LENGTH_Z,
    )
    assert cross.shape[4] - cross.shape[3] == pytest.approx(
        2.0 * spec.POCKET_HALF_Z + spec.POCKET_WALL,
    )
    assert cross.bottom_y == spec.RIB_RELIEF
    assert _CEILING - cross.bottom_y == pytest.approx(34.798)
    long = next(f for f in pocket_features() if f.kind == "long rib")
    wall = next(f for f in pocket_features() if f.wall)
    for x in (left + 0.1, spec.CROSS_RIB_CENTER_X, right - 0.1):
        assert cross.contains(x, 0.0) and long.contains(x, 0.0)
        for sign in (-1.0, 1.0):
            z = sign * (spec.POCKET_HALF_Z + spec.POCKET_WALL / 4.0)
            assert cross.contains(x, z) and wall.contains(x, z)
    corners = [c for c in pocket_corners() if "cross rib" in c.kind]
    assert {tuple(round(float(v), 9) for v in c.point) for c in corners} == {
        (round(x, 9), round(z, 9))
        for x in (left, right)
        for z in (
            -spec.POCKET_HALF_Z,
            -spec.RIB_THICKNESS / 2.0,
            spec.RIB_THICKNESS / 2.0,
            spec.POCKET_HALF_Z,
        )
    }
    assert len(corners) == 8
    for corner in corners:
        assert corner.y_lo == spec.RIB_RELIEF and corner.y_hi == _CEILING
        patch = fillet(corner, spec.POCKET_CORNER_FILLET_R).zone
        assert patch[:, 0].min() >= left - spec.POCKET_CORNER_FILLET_R - 1e-9
        assert patch[:, 0].max() <= right + spec.POCKET_CORNER_FILLET_R + 1e-9
        air = np.array(corner.face_a.normal) + np.array(corner.face_b.normal)
        sample = np.array(corner.point) + 0.1 * air
        assert fasteners.retained_material_segments_mm(
            *sample,
            fillet_radius_mm=0.0,
        ) == ((0.0, spec.POCKET_SKIN),)
        assert fasteners.retained_material_segments_mm(*sample) == (
            (0.0, spec.STACK_HEIGHT - spec.RIB_RELIEF),
        )
    # The former west-side junction is now open pocket, not a leftover root.
    assert fasteners.retained_material_segments_mm(
        -5.1,
        5.1,
    ) == ((0.0, spec.POCKET_SKIN),)


def test_all_eighteen_full_hole_envelopes_exit_only_the_skin_at_max_r6() -> None:
    checked = []
    for tag, seat, stations, envelope in base.THROUGH_SEAT_GROUPS:
        for xz, material in zip(stations, base.THROUGH_SEAT_MATERIAL[tag], strict=True):
            gaps = _skin_exit_clearances(seat, xz, envelope)
            assert len(gaps) == len(pocket_features()) + len(pocket_corners())
            tightest = min(gaps, key=gaps.__getitem__)
            assert gaps[tightest] > 0.0, (tag, xz, tightest, gaps[tightest])
            if tag == "BlockScrewHoles":
                assert gaps[tightest] >= WALL_TARGET_MM, (
                    tag,
                    xz,
                    tightest,
                    gaps[tightest],
                )
            pure = fasteners.through_seat_pocket_clearances_mm(
                seat,
                xz,
                envelope_xz=envelope,
            )
            index = stations.index(xz)
            assert base.THROUGH_SEAT_POCKET_CLEARANCES[tag][index] == pure
            assert min(pure.values()) > 0.0, (tag, xz, pure)
            if tag == "BlockScrewHoles":
                assert min(pure.values()) >= WALL_TARGET_MM, (tag, xz, pure)
            assert material.nominal_segments_mm == ((0.0, spec.POCKET_SKIN),)
            assert material.exit_depth_min_mm == pytest.approx(12.192)
            assert material.exit_depth_max_mm == pytest.approx(13.716)
            checked.append((tag, xz))
    assert len(checked) == len(set(checked)) == 18


def test_nominal_face_gaps_and_a_clear_axis_cannot_hide_a_max_r6_interruption() -> None:
    seat = base.BLOCK_SEAT_SPEC
    radius = _seat_radius(seat.size, TAP_DRILL_MM[seat.size])
    left = spec.CROSS_RIB_CENTER_X - spec.RIB_THICKNESS / 2.0
    top = spec.RIB_THICKNESS / 2.0
    centre = (left - radius - 0.1, top + radius + 0.1)
    # The entire circular footprint clears both sharp ribs nominally, and
    # even the axis clears the real fillet. Its circumference does not.
    for feature in pocket_features():
        if feature.kind in ("long rib", "cross rib"):
            assert float(feature.clearance(np.array([centre]))[0]) - radius > 0.0
    assert base.retained_material_segments_mm(*centre) == ((0.0, spec.POCKET_SKIN),)
    corner = next(
        c
        for c in pocket_corners()
        if c.kind == ("cross rib", "long rib") and c.point == pytest.approx((left, top))
    )
    zone = fillet(corner, spec.POCKET_CORNER_FILLET_R).zone
    assert not _inside(zone, centre)[0]
    assert float(_point_polygon_distance(zone, np.array([centre]))[0]) - radius < 0.0
    assert _skin_exit_clearances(seat, centre)[f"fillet {corner.name}"] < 0.0


def test_skin_exit_scan_refuses_nominal_only_and_transfer_envelope_counterexamples() -> (
    None
):
    seat = base.BLOCK_SEAT_SPEC
    radius = _seat_radius(seat.size, TAP_DRILL_MM[seat.size])
    left = spec.CROSS_RIB_CENTER_X - spec.RIB_THICKNESS / 2.0
    right = spec.CROSS_RIB_CENTER_X + spec.RIB_THICKNESS / 2.0
    nominal_only = (left - radius - 1.0, 50.0)
    assert left - nominal_only[0] - radius == pytest.approx(1.0)
    assert base.retained_material_segments_mm(*nominal_only) == (
        (0.0, spec.POCKET_SKIN),
    )
    assert _skin_exit_clearances(seat, nominal_only)["cross rib"] < 0.0
    transferred = (right + radius + 5.0, 50.0)
    assert _skin_exit_clearances(seat, transferred)["cross rib"] > 0.0
    assert _skin_exit_clearances(seat, transferred, (6.0, 0.0))["cross rib"] < 0.0


def test_pure_max_fillet_bounds_enclose_each_independently_enumerated_patch() -> None:
    bounds = fasteners._fillet_footprint_bounds_mm()
    assert len(bounds) == len(pocket_corners()) == 28
    covered = set()
    for corner in pocket_corners():
        zone = fillet(corner, spec.POCKET_CORNER_FILLET_R).zone
        matching = {
            index
            for index, (x0, x1, z0, z1, bottom) in enumerate(bounds)
            if bottom == corner.y_lo
            and np.all(zone[:, 0] >= x0 - 1e-9)
            and np.all(zone[:, 0] <= x1 + 1e-9)
            and np.all(zone[:, 1] >= z0 - 1e-9)
            and np.all(zone[:, 1] <= z1 + 1e-9)
        }
        assert matching, corner.name
        covered.update(matching)
    assert covered == set(range(len(bounds)))


def test_inner_block_gap_books_printed_location_size_rounding_and_edge_break() -> None:
    seat = base.BLOCK_SEAT_SPEC
    left = spec.CROSS_RIB_CENTER_X - spec.RIB_THICKNESS / 2.0
    radius = _seat_radius(seat.size, TAP_DRILL_MM[seat.size])
    inner = sorted(base.BLOCK_SCREW_XZ, key=lambda xz: abs(xz[0]))[:2]
    assert len(inner) == 2 and inner[0][1] * inner[1][1] < 0.0
    for xz in inner:
        nominal = left - xz[0] - radius
        conservative = nominal - 3.0 * _BAND
        edge_break = fasteners.EDGE_BREAK_MAX_MM
        printed = nominal - 3.0 * (_BAND + 0.05) - edge_break
        gap = fasteners.through_seat_pocket_clearances_mm(
            seat,
            xz,
        )["retained rectangle 1"]
        assert nominal > 8.56
        assert conservative > 6.16
        assert printed == pytest.approx(gap)
        assert printed > 5.76 > 2.0


@pytest.mark.parametrize("r", STANDARD_RADII)
def test_build_fillets_match_the_enumerated_corners(r: float) -> None:
    """PocketCornerFillets' picks, edge lengths and closed-form sections (the
    volume check's terms) are exactly the enumerated corners and their
    numerically integrated fillet sections."""
    built = {
        (round(pick[0], 6), round(pick[1], 6), round(pick[2], 6)): (length, area)
        for pick, length, area in base._pocket_corner_fillets(r)
    }
    assert len(built) == len(base._pocket_corner_fillets(r)), "duplicate picks"
    numeric = 0.0
    for corner in new_corners():
        key = tuple(round(v, 6) for v in corner.pick)
        assert key in built, f"build has no pick for {corner.name}"
        length, area = built.pop(key)
        section = fillet(corner, r).area
        assert length == pytest.approx(corner.length), corner.name
        assert area == pytest.approx(section, rel=2e-3), corner.name
        numeric += section * corner.length
    assert not built, f"build picks with no reentrant corner: {sorted(built)}"
    assert base._pocket_corner_fillet_volume(r) == pytest.approx(numeric, rel=2e-3)


def test_one_printed_count_covers_every_vertical_pocket_corner() -> None:
    assert base.POCKET_FILLET_COUNT == len(pocket_corners()) == 28
    assert base.POCKET_FILLET_TOL_TYPE == 6  # swTolType_e.swTolMAX


def test_each_pick_selects_exactly_its_own_edge() -> None:
    """add_fillet resolves each point to the body edge within 0.5 mm, so a
    pick must sit farther than that from every other edge it could hit: the
    other vertical corners (existing ones too) and its own edge's ends."""
    corners = pocket_corners()
    for corner in new_corners():
        x, y, z = corner.pick
        assert corner.length / 2.0 > 2.0 * _PICK_TOLERANCE, corner.name
        for other in corners:
            if other is corner:
                continue
            plan = math.dist((x, z), other.point)
            rise = max(0.0, other.y_lo - y, y - other.y_hi)
            assert math.hypot(plan, rise) > 2.0 * _PICK_TOLERANCE, (
                f"pick for {corner.name} is ambiguous with {other.name}"
            )
