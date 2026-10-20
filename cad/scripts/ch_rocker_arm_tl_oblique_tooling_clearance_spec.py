"""Measured installed tooling versus conservative full-sweep fixture prisms.

No installed spindle/toolholder envelope is supplied by the CAD dimensions.
Passing ``None`` therefore returns UNVERIFIED, never a cutter-radius fallback.
Callers must supply the actual stepped, coaxial tooling envelope in machine
coordinates and fixture prisms covering BOTH complete sweeps and rigid upset.

A positive separation proves only separation of those supplied geometric bounds.
A nonpositive result flags possible bounding-prism overlap, NOT an assertion of
physical collision. Neither outcome certifies strength, deflection, machining
forces, wire workmanship, or installed-machine acceptance.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from numbers import Real

Point = tuple[float, float]


def _finite(value: float, label: str) -> None:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ValueError(f"{label} must be a finite real dimension")
    try:
        finite = math.isfinite(value)
    except OverflowError:
        finite = False
    if not finite:
        raise ValueError(f"{label} must be a finite real dimension")


def _interval(z_min: float, z_max: float, label: str) -> None:
    _finite(z_min, f"{label} z_min")
    _finite(z_max, f"{label} z_max")
    if z_min >= z_max:
        raise ValueError(f"{label} needs a positive-height Z interval")


def _label(value: str, field: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must name a nonblank authority or fixture")


def _cross(a: Point, b: Point, c: Point) -> float:
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def _on_segment(a: Point, b: Point, p: Point) -> bool:
    return (
        _cross(a, b, p) == 0.0
        and min(a[0], b[0]) <= p[0] <= max(a[0], b[0])
        and min(a[1], b[1]) <= p[1] <= max(a[1], b[1])
    )


def _intersects(a: Point, b: Point, c: Point, d: Point) -> bool:
    ab_c, ab_d, cd_a, cd_b = _cross(a, b, c), _cross(a, b, d), _cross(c, d, a), _cross(c, d, b)
    return (
        ((ab_c < 0.0 < ab_d or ab_d < 0.0 < ab_c)
         and (cd_a < 0.0 < cd_b or cd_b < 0.0 < cd_a))
        or _on_segment(a, b, c) or _on_segment(a, b, d)
        or _on_segment(c, d, a) or _on_segment(c, d, b)
    )


def _polygon(xy: tuple[Point, ...]) -> None:
    if not isinstance(xy, tuple) or len(xy) < 3:
        raise ValueError("fixture xy must be an immutable polygon of at least three points")
    for point in xy:
        if not isinstance(point, tuple) or len(point) != 2:
            raise ValueError("fixture xy points must be immutable coordinate pairs")
        _finite(point[0], "fixture X")
        _finite(point[1], "fixture Y")
    if len(set(xy)) != len(xy):
        raise ValueError("fixture polygon must not repeat vertices")
    area_twice = sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(xy, xy[1:] + xy[:1]))
    if not math.isfinite(area_twice) or area_twice == 0.0:
        raise ValueError("fixture polygon must have a finite nonzero area")
    count = len(xy)
    for i in range(count):
        for j in range(i + 1, count):
            if j == i + 1 or (i == 0 and j == count - 1):
                continue
            if _intersects(xy[i], xy[(i + 1) % count], xy[j], xy[(j + 1) % count]):
                raise ValueError("fixture polygon must be simple, without crossing edges")
        # Adjacent edges may meet only at their shared vertex, not double back.
        a, b, c = xy[i - 1], xy[i], xy[(i + 1) % count]
        if _cross(a, b, c) == 0.0 and (_on_segment(a, b, c) or _on_segment(b, c, a)):
            raise ValueError("fixture polygon edges must not double back")


@dataclass(frozen=True)
class ToolingCylinder:
    """One measured coaxial step, around machine X=Y=0, in millimetres."""

    z_min: float
    z_max: float
    radius: float

    def __post_init__(self) -> None:
        _interval(self.z_min, self.z_max, "tooling step")
        _finite(self.radius, "tooling radius")
        if self.radius <= 0.0:
            raise ValueError("tooling radius must be positive")


@dataclass(frozen=True)
class InstalledToolingEnvelope:
    """Measured assembly authority; uncertainties expand every supplied step."""

    source: str
    radial_uncertainty: float
    axial_uncertainty: float
    steps: tuple[ToolingCylinder, ...]

    def __post_init__(self) -> None:
        _label(self.source, "installed tooling source")
        for name, value in (("radial uncertainty", self.radial_uncertainty), ("axial uncertainty", self.axial_uncertainty)):
            _finite(value, name)
            if value < 0.0:
                raise ValueError(f"{name} must be nonnegative")
        if not isinstance(self.steps, tuple) or not self.steps or not all(isinstance(step, ToolingCylinder) for step in self.steps):
            raise ValueError("installed tooling needs a nonempty immutable tuple of measured steps")
        for step in self.steps:
            for value in (step.radius + self.radial_uncertainty, step.z_min - self.axial_uncertainty, step.z_max + self.axial_uncertainty):
                _finite(value, "expanded tooling dimension")


@dataclass(frozen=True)
class FixtureEnvelope:
    """Conservative simple-polygon prism, including sweep/upset allowances."""

    label: str
    xy: tuple[Point, ...]
    z_min: float
    z_max: float

    def __post_init__(self) -> None:
        _label(self.label, "fixture label")
        _interval(self.z_min, self.z_max, "fixture")
        _polygon(self.xy)


@dataclass(frozen=True)
class ToolingClearanceReport:
    status: str
    min_clearance: float | None
    limiting_pair: tuple[str, int] | None
    authority: str | None


def _axis_distance(xy: tuple[Point, ...]) -> float:
    """Distance from the origin to the FILLED polygon, including concave ones."""
    inside = False
    closest = math.inf
    for a, b in zip(xy, xy[1:] + xy[:1]):
        if _on_segment(a, b, (0.0, 0.0)):
            return 0.0
        if (a[1] > 0.0) != (b[1] > 0.0):
            crossing_x = a[0] + (b[0] - a[0]) * (-a[1]) / (b[1] - a[1])
            if crossing_x > 0.0:
                inside = not inside
        dx, dy = b[0] - a[0], b[1] - a[1]
        length = math.hypot(dx, dy)
        ux, uy = dx / length, dy / length
        along = min(length, max(0.0, -(a[0] * ux + a[1] * uy)))
        closest = min(closest, math.hypot(a[0] + along * ux, a[1] + along * uy))
    return 0.0 if inside else closest


def tooling_clearance_report(
    envelope: InstalledToolingEnvelope | None,
    fixtures: tuple[FixtureEnvelope, ...],
) -> ToolingClearanceReport:
    """Signed conservative prism/cylinder separation; no nominal fallback.

    Each pair uses max(radial gap, axial interval gap). This is a conservative
    separation, not the Euclidean diagonal distance. Zero/touching is a possible
    conflict. The limiting pair stores (fixture label, zero-based tooling step).
    """
    if envelope is None:
        return ToolingClearanceReport("UNVERIFIED", None, None, None)
    if not isinstance(envelope, InstalledToolingEnvelope):
        raise ValueError("tooling envelope must carry measured installed authority")
    if not isinstance(fixtures, tuple) or not fixtures or not all(isinstance(fixture, FixtureEnvelope) for fixture in fixtures):
        raise ValueError("clearance requires a nonempty immutable fixture-envelope census")
    if len({fixture.label for fixture in fixtures}) != len(fixtures):
        raise ValueError("fixture labels must be unique for limiting-pair attribution")
    minimum = math.inf
    limiting = None
    for fixture in fixtures:
        distance = _axis_distance(fixture.xy)
        for index, step in enumerate(envelope.steps):
            radial_gap = distance - step.radius - envelope.radial_uncertainty
            axial_gap = max(
                fixture.z_min - (step.z_max + envelope.axial_uncertainty),
                step.z_min - envelope.axial_uncertainty - fixture.z_max,
            )
            clearance = max(radial_gap, axial_gap)
            if clearance < minimum:
                minimum, limiting = clearance, (fixture.label, index)
    status = "VERIFIED_GEOMETRY_ONLY" if minimum > 0.0 else "POTENTIAL_CONFLICT"
    return ToolingClearanceReport(status, minimum, limiting, envelope.source)
