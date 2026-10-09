"""Finite stock-form planar contact, not an ideal-tooth contact-ratio formula.

There are two deliberately separate computations.  ``supported_branch_coverage``
counts the existence of a supported same-side external common-normal branch,
including genuine finite below-base radial flanks and tip normal cones, before
considering any other tooth pair. Root-floor arcs are never working branches.
``analyse_planar_mesh`` finds the free rotational component of the COMPLETE
repeated material boundary.  Its endpoints are the two physical first contacts.
An occluded secondary branch belongs to coverage, but never carries the load.

The material calculation uses chord enclosures, not an unqualified point grid.
All polygon contact events are solved analytically (circle/line intersections),
and angular uncertainty is charged through a lower bound on the contact moment
arm.  Phase sampling has a separately charged motion enclosure.  Singular or
unresolved contacts are refused, never replaced by ideal-ratio motion.  These
are rigid transverse results; in particular they do not certify crossed gears.

Support certification keeps smooth-edge tangent intervals separate from finite
vertex normal cones: each cone belongs to its endpoint, not its entire adjacent
chord. Swept boxes are only a broad phase; finite-segment distances must also
permit contact. Ambiguous support cells refine their phase and witnessed driven
bracket. Unresolved cells remain refused at the subdivision limit.
``uncovered_phase_rad`` is a conservative uncertified-cell measure, NOT a measured
physical gap. ``support_uncertain_phase_rad`` identifies cells with supported
sample contacts but unresolved swept support; ``unsupported_contact_samples_rad``
lists actual sampled unsupported contacts, not an inferred interval of failure.

Coordinates: driver centre (0, 0), driven centre (C, 0), both canonical gaps +X.
A positive driver input drives the mate negatively.  The datum is the supplied
clocking, with the driven gap facing the driver's tooth at driver input zero:
``pi - driven_pitch/2 + driven_clocking``.  No median or mean TE is subtracted.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from functools import cached_property
from math import acos, atan2, ceil, cos, floor, hypot, isfinite, pi, radians, sin, sqrt, tan
from typing import Any

import numpy as np
from scipy.optimize import brentq

from stock_form_cutter import StockFormProfile


class MeshCertificationError(ValueError):
    """The requested enclosure could not be established; not a passing mesh."""


@dataclass(frozen=True)
class CoverageReport:
    value: float
    lower_bound: float
    upper_bound: float
    phase_intervals_rad: tuple[tuple[float, float], ...]
    numerical_error_rad: float


@dataclass(frozen=True)
class PhaseContact:
    driver_phase_rad: float
    driven_phase_rad: float
    reverse_driven_phase_rad: float
    backlash_mm: float
    feature_ids: tuple[str, str]
    supported: bool
    phase_error_rad: float
    moment_arm_lower_mm: float
    other_pair_normal_gap_mm: float
    contact_point_mm: tuple[float, float]
    normal_angle_rad: float = 0.0


@dataclass(frozen=True)
class MeshReport:
    coverage: float
    uncovered_phase_rad: float
    tight_backlash_mm: float
    loose_backlash_mm: float
    root_air_mm: float
    transmission_error_driver_rad: tuple[float, ...]
    transmission_error_driven_rad: tuple[float, ...]
    driver_phase_samples_rad: tuple[float, ...]
    driven_phase_samples_rad: tuple[float, ...]
    handover_kinds: tuple[str, ...]
    numerical_error_bounds: dict[str, float]
    is_conjugate: bool
    handover_jump_mm: float
    phase_reserves_rad: tuple[float, ...]
    max_other_pair_normal_gap_mm: float
    contact_feature_ids: tuple[tuple[str, str], ...]
    root_interference: bool
    qualified_continuous_contact: bool
    coverage_interval: tuple[float, float]
    driver_period_rad: float
    driven_period_rad: float
    _engine: Any = field(repr=False, compare=False)
    handover_phase_reserves_rad: tuple[tuple[float, float], ...] = ()
    smooth_flank_coverage: float = float("nan")
    smooth_flank_coverage_interval: tuple[float, float] = (float("nan"), float("nan"))
    corner_inclusive_coverage: float = float("nan")
    corner_inclusive_coverage_interval: tuple[float, float] = (float("nan"), float("nan"))
    corner_carrying_phase_fraction: float = 0.0
    corner_normal_angle_range_rad: tuple[float, float] | None = None
    support_uncertain_phase_rad: float = 0.0
    unsupported_contact_samples_rad: tuple[float, ...] = ()

    def contact_at(self, driver_phi_rad: float) -> PhaseContact:
        """Re-solve first contact at arbitrary input, including signed periods."""
        return self._engine.contact_at(driver_phi_rad)

    def driven_phase_at(self, driver_phi_rad: float) -> float:
        """Actual absolute driven phase, not interpolation of a TE sample grid."""
        return self.contact_at(driver_phi_rad).driven_phase_rad

    def transmission_error_at(self, driver_phi_rad: float) -> float:
        """Signed driven TE relative to the stated mechanical clocking datum."""
        return self.driven_phase_at(driver_phi_rad) - self._engine.datum(driver_phi_rad)


def _rotate(p: np.ndarray, angle: float) -> np.ndarray:
    c, s = cos(angle), sin(angle)
    return np.asarray(p) @ np.array(((c, s), (-s, c)))


def _cross(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    return a[..., 0] * b[..., 1] - a[..., 1] * b[..., 0]


def _merge(intervals: list[tuple[float, float]]) -> list[tuple[float, float]]:
    result: list[tuple[float, float]] = []
    for lo, hi in sorted(intervals):
        if hi <= lo:
            continue
        if result and lo <= result[-1][1] + 1e-13:
            result[-1] = (result[-1][0], max(hi, result[-1][1]))
        else:
            result.append((lo, hi))
    return result


def _measure(intervals: list[tuple[float, float]]) -> float:
    return sum(hi - lo for lo, hi in _merge(intervals))


def _product(a: tuple[float, float], b: tuple[float, float]) -> tuple[float, float]:
    values = (a[0] * b[0], a[0] * b[1], a[1] * b[0], a[1] * b[1])
    return min(values), max(values)


def _dot_box(a: np.ndarray, b: np.ndarray) -> tuple[float, float]:
    terms = [_product(tuple(a[j]), tuple(b[j])) for j in range(2)]
    return sum(x[0] for x in terms), sum(x[1] for x in terms)


def _norm_box(box: np.ndarray) -> tuple[float, float]:
    low = [0.0 if a <= 0 <= b else min(abs(a), abs(b)) for a, b in box]
    high = [max(abs(a), abs(b)) for a, b in box]
    return hypot(*low), hypot(*high)


def _angle_box(box: np.ndarray) -> tuple[float, float]:
    if _norm_box(box)[0] == 0:
        return -pi, pi
    centre = atan2(float(box[1].mean()), float(box[0].mean()))
    angles = [centre + (atan2(y, x) - centre + pi) % (2 * pi) - pi
              for x in box[0] for y in box[1]]
    return min(angles), max(angles)


@dataclass(frozen=True)
class _NormalFeature:
    profile: StockFormProfile
    kind: str

    @cached_property
    def u_range(self) -> tuple[float, float]:
        return self.profile.flank_parameter_min, self.profile.flank_parameter_max

    @cached_property
    def radial_segment(self):
        # Core gap traversal reverses the upper branch (actual tip toward root).
        return next((segment for segment in self.profile.gap_segments()
                     if segment.kind == "radial" and segment.name.startswith("Upper")), None)

    def state(self, t: float) -> tuple[np.ndarray, float, np.ndarray]:
        """Normal-frame point, outward normal angle, derivative in normalized t."""
        p = self.profile
        u0, u1 = self.u_range
        if self.kind == "radial":
            segment = self.radial_segment
            if segment is None:
                raise ValueError("Profile has no genuine finite below-base radial flank")
            point = np.asarray(segment.point(1 - t))
            dp = -np.asarray(segment.derivative(1 - t))
            angle = atan2(-dp[0], dp[1])
            return _rotate(point, -angle), angle, _rotate(dp, -angle)
        if self.kind == "flank":
            u = u0 if t == 0 else u1 if t == 1 else u0 + t * (u1 - u0)
            point = np.asarray(p.flank_point(u), dtype=float)
            normal = p.flank_normal(u)
            angle = atan2(normal[1], normal[0])
            dp = np.asarray(p.flank_derivative(u)) * (u1 - u0)
            q = _rotate(point, -angle)
            dq = _rotate(dp, -angle) - np.array((-q[1], q[0])) * (u1 - u0)
            return q, angle, dq
        point = np.asarray(p.tip_point(p.tip_half_angle_rad), dtype=float)
        if u1 > u0:
            normal = p.flank_normal(u1)
        else:
            segment = self.radial_segment
            if segment is None:
                raise ValueError("Finite tip has no supported working branch")
            dx, dy = -np.asarray(segment.derivative(0.0))
            normal = (dy, -dx)
        start = atan2(normal[1], normal[0])
        end = atan2(point[1], point[0])
        sweep = (end - start + pi) % (2 * pi) - pi
        angle = start + t * sweep
        q = _rotate(point, -angle)
        return q, angle, -np.array((-q[1], q[0])) * sweep

    @cached_property
    def second_bound(self) -> float:
        p = self.profile
        u0, u1 = self.u_range
        if self.kind == "radial":
            # Spur radial continuation is a translated straight line, with a
            # constant outward normal; no invented involute below the base.
            return 0.0
        if self.kind == "tip_corner":
            a0, a1 = self.state(0)[1], self.state(1)[1]
            return p.blank_radius_mm * (a1 - a0) ** 2
        rb = p.template.base_radius_mm
        # d²[R(-a)p]/du² = R(-a)(p''-2Jp'-p), a'=1.
        return (rb * sqrt(1 + u1 * u1) + 2 * rb * u1
                + abs(p.radial_translation_mm) + p.template.tip_radius_mm) * (u1 - u0) ** 2

    def bounds(self, lo: float, hi: float) -> tuple[np.ndarray, np.ndarray, tuple[float, float]]:
        mid, half = (lo + hi) / 2, (hi - lo) / 2
        q, _, dq = self.state(mid)
        pad = 128 * np.finfo(float).eps * (1 + self.profile.blank_radius_mm + self.second_bound)
        derivative = np.stack((dq - self.second_bound * half - pad,
                               dq + self.second_bound * half + pad), axis=1)
        travel = np.maximum(abs(derivative[:, 0]), abs(derivative[:, 1])) * half
        point = np.stack((q - travel - pad, q + travel + pad), axis=1)
        angles = self.state(lo)[1], self.state(hi)[1]
        return point, derivative, (min(angles), max(angles))


def _branch_enclosures(a: _NormalFeature, b: _NormalFeature, centre: float,
                       angular_tolerance: float) -> tuple[list, list]:
    """Interval isolation of |qA+qB|=C, independently of material occlusion.

    Fixed signs of both implicit partials prove a connected branch in a box.
    Along it, sign[d(thetaA)/du] is the sign of
    (cross(qA',qB') - a' dot(qA+qB,qB')) / dot(qA+qB,qB').
    A fixed sign therefore permits exact endpoint extrema without a fine grid.
    Stationary/tangent boxes pay their entire outward angle enclosure.
    """
    pending = [(0.0, 1.0, 0.0, 1.0)]
    outer, inner = [], []
    visited = 0
    angle_rate = a.state(1)[1] - a.state(0)[1]
    while pending:
        u0, u1, v0, v1 = pending.pop()
        visited += 1
        if visited > 1_000_000:
            raise MeshCertificationError("Common-normal interval isolation did not converge")
        qa, dqa, aa = a.bounds(u0, u1)
        qb, dqb, _ = b.bounds(v0, v1)
        total = qa + qb
        distance = _norm_box(total)
        if centre < distance[0] or centre > distance[1]:
            continue
        arg = _angle_box(total)
        angle_interval = (-arg[1] - aa[1], -arg[0] - aa[0])
        da, db = _dot_box(total, dqa), _dot_box(total, dqb)
        connected = not (da[0] <= 0 <= da[1] or db[0] <= 0 <= db[1])
        xy = _product(tuple(dqa[0]), tuple(dqb[1]))
        yx = _product(tuple(dqa[1]), tuple(dqb[0]))
        rate = _product((angle_rate, angle_rate), db)
        turning = (xy[0] - yx[1] - rate[1], xy[1] - yx[0] - rate[0])
        monotone = connected and not (turning[0] <= 0 <= turning[1])
        narrow = angle_interval[1] - angle_interval[0] <= angular_tolerance
        if not monotone and not narrow:
            if u1 - u0 >= v1 - v0:
                um = (u0 + u1) / 2
                pending.extend(((u0, um, v0, v1), (um, u1, v0, v1)))
            else:
                vm = (v0 + v1) / 2
                pending.extend(((u0, u1, v0, vm), (u0, u1, vm, v1)))
            continue
        points, errors = [], []
        if connected:
            def residual(u: float, v: float) -> float:
                q = a.state(u)[0] + b.state(v)[0]
                return float(q @ q) - centre * centre

            for fixed, low, high, swap in ((u0, v0, v1, False), (u1, v0, v1, False),
                                           (v0, u0, u1, True), (v1, u0, u1, True)):
                def f(t: float) -> float:
                    return residual(t, fixed) if swap else residual(fixed, t)
                fl, fh = f(low), f(high)
                if fl * fh > 0:
                    continue
                root = low if fl == 0 else high if fh == 0 else brentq(f, low, high, xtol=1e-14)
                u, v = (root, fixed) if swap else (fixed, root)
                q, angle, _ = a.state(u)
                q = q + b.state(v)[0]
                points.append(-atan2(q[1], q[0]) - angle)
                partial = da if swap else db
                minimum_partial = 2 * min(abs(partial[0]), abs(partial[1]))
                rounding = 256 * np.finfo(float).eps * (1 + distance[1] ** 2 + centre ** 2)
                parameter_error = 2e-14 + rounding / minimum_partial
                derivative = dqa if swap else dqb
                speed = hypot(*(np.maximum(abs(derivative[:, 0]), abs(derivative[:, 1]))))
                theta_speed = speed / max(distance[0], centre / 2) + (abs(angle_rate) if swap else 0)
                errors.append(parameter_error * theta_speed + 128 * np.finfo(float).eps)
        if monotone:
            if len(points) >= 2:
                outer.append((min(p - e for p, e in zip(points, errors)),
                              max(p + e for p, e in zip(points, errors))))
                inner.append((min(p + e for p, e in zip(points, errors)),
                              max(p - e for p, e in zip(points, errors))))
        else:
            outer.append(angle_interval)
            if len(points) >= 2:
                inner.append((min(p + e for p, e in zip(points, errors)),
                              max(p - e for p, e in zip(points, errors))))
    return outer, inner


def _validate(driver: StockFormProfile, driven: StockFormProfile, centre: float,
              error: float) -> None:
    if not isfinite(centre) or centre <= 0 or not isfinite(error) or error <= 0:
        raise ValueError("Positive finite centre distance and error budget required")
    if driver.helix_angle_deg or driven.helix_angle_deg:
        raise ValueError("Planar contact cannot certify a helical/crossed mesh")
    if centre <= max(driver.blank_radius_mm, driven.blank_radius_mm):
        raise ValueError("External separated-axis gears required; not an internal pair")


def _certify_isolated_pair(driver, driven, centre):
    """Prove common-normal candidates cannot self-overlap their OWN tooth pair.

    Remove each concave root arc below the chord joining its two flank feet.
    The remaining working tooth is convex: both involutes, radial connectors,
    and OD land turn counterclockwise, and the exact endpoint tangent sequence
    below has only convex joins.  A common outward support normal therefore
    separates those two complete working teeth, not merely their local flanks.
    The removed root material lies within rootMAX; blank/root envelopes prove
    that it cannot interfere at ANY of the candidate poses.  Other tooth pairs
    are deliberately excluded from this proof and from named coverage.
    """
    air = min(centre - driver.blank_radius_mm - driven.root_radius_max_mm,
              centre - driven.blank_radius_mm - driver.root_radius_max_mm)
    error = driver.geometry_error_bound_mm + driven.geometry_error_bound_mm
    if air <= error:
        raise MeshCertificationError("Isolated-pair root envelope is not clear; coverage cannot certify root contact")
    for profile in (driver, driven):
        k = profile.template.half_space_base_angle_rad
        low = k + profile.flank_parameter_min
        high = k + profile.flank_parameter_max
        tip, pitch = profile.tip_half_angle_rad, profile.angular_pitch_rad
        angles = (low, high, tip + pi / 2, pitch - tip + pi / 2,
                  pi + pitch - high, pi + pitch - low,
                  pitch / 2 + 3 * pi / 2, low + 2 * pi)
        if any(b - a < -128 * np.finfo(float).eps or b - a > pi
               for a, b in zip(angles, angles[1:])):
            raise MeshCertificationError("Working tooth is not certified convex; own-pair overlap is unresolved")


def _supported_features(profile):
    features = []
    if profile.flank_parameter_max > profile.flank_parameter_min:
        features.append("flank")
    if _NormalFeature(profile, "radial").radial_segment is not None:
        features.append("radial")
    if features:
        features.append("tip_corner")
    return tuple(features)


def supported_branch_coverage(driver: StockFormProfile, driven: StockFormProfile,
                              centre_distance_mm: float, *,
                              maximum_error_mm: float = 0.001) -> CoverageReport:
    """Supported one-pair branch span / physical driver pitch, NOT carrier duty.

    Genuine core-owned below-base radial flanks and finite tip-corner normal
    cones are included. Reducing blank diameter is not by itself a monotonic
    coverage certificate: the new finite tip has a different corner cone.
    """
    _validate(driver, driven, centre_distance_mm, maximum_error_mm)
    features_a, features_b = _supported_features(driver), _supported_features(driven)
    if not features_a or not features_b:
        return CoverageReport(0.0, 0.0, 0.0, (), 0.0)
    _certify_isolated_pair(driver, driven, centre_distance_mm)
    pitch = driver.angular_pitch_rad
    requested = maximum_error_mm / max(driver.blank_radius_mm, driven.blank_radius_mm)
    tolerance = requested / 4
    for _ in range(8):
        outer, inner = [], []
        for ka in features_a:
            for kb in features_b:
                if ka == kb and ka in {"tip_corner", "radial"}:
                    # Two fixed vertices, or two flat faces with fixed local
                    # normals, meet only at isolated physical driver angles.
                    continue
                high, low = _branch_enclosures(_NormalFeature(driver, ka),
                                               _NormalFeature(driven, kb),
                                               centre_distance_mm, tolerance)
                outer.extend(high)
                inner.extend(low)
        upper, lower = _measure(outer), _measure(inner)
        if upper - lower <= requested:
            return CoverageReport((upper + lower) / (2 * pitch), lower / pitch,
                                  upper / pitch, tuple(_merge(outer)), (upper - lower) / 2)
        tolerance /= 2
    raise MeshCertificationError("Coverage projection uncertainty exceeds requested bound")


def supported_flank_coverage(driver: StockFormProfile, driven: StockFormProfile,
                             centre_distance_mm: float, *,
                             maximum_error_mm: float = 0.001) -> CoverageReport:
    """Diagnostic involute/involute span only; no radial flanks or tip cones."""
    _validate(driver, driven, centre_distance_mm, maximum_error_mm)
    _certify_isolated_pair(driver, driven, centre_distance_mm)
    if any(p.flank_parameter_max <= p.flank_parameter_min for p in (driver, driven)):
        return CoverageReport(0.0, 0.0, 0.0, (), 0.0)
    requested = maximum_error_mm / max(driver.blank_radius_mm, driven.blank_radius_mm)
    tolerance = requested / 4
    for _ in range(8):
        outer, inner = _branch_enclosures(_NormalFeature(driver, "flank"),
                                         _NormalFeature(driven, "flank"),
                                         centre_distance_mm, tolerance)
        low, high = _measure(inner), _measure(outer)
        if high - low <= requested:
            pitch = driver.angular_pitch_rad
            return CoverageReport((low + high) / (2 * pitch), low / pitch, high / pitch,
                                  tuple(_merge(outer)), (high - low) / 2)
        tolerance /= 2
    raise MeshCertificationError("Smooth-flank coverage uncertainty exceeds requested bound")


@dataclass(frozen=True)
class _Boundary:
    points: np.ndarray
    names: tuple[str, ...]
    error_mm: float
    normal_error_rad: np.ndarray


def _one_pitch_boundary(profile: StockFormProfile, error: float) -> _Boundary:
    """Core-owned complete exterior, including the under-gap root lobes."""
    points, names, normals = [], [], []
    largest_error = 0.0
    segments = profile.external_boundary_segments(
        unit_scale=1.0, rotate_rad=profile.angular_pitch_rad / 2
    )
    for segment in segments:
        n = max(1, ceil(sqrt(segment.second_derivative_bound_mm / (8 * error))))
        for j in range(n):
            points.append(segment.point(j / n))
            name = segment.name.lower()
            if "tip" in name and "land" in name:
                name = "tip_land"
            if segment.kind == "radial":
                name = "radial_" + name
            names.append(name)
            velocity = np.linalg.norm(segment.derivative((j + 0.5) / n))
            derivative_error = segment.second_derivative_bound_mm / (2 * n)
            # Angle between a chord and ANY actual tangent in the cell.  A
            # stationary base cusp has no invented normal: its enclosure is pi.
            normals.append(min(pi, 2 * derivative_error / (velocity - derivative_error))
                           if velocity > derivative_error else pi)
        largest_error = max(largest_error, segment.second_derivative_bound_mm / (8 * n * n))
    return _Boundary(np.asarray(points), tuple(names),
                     largest_error + profile.geometry_error_bound_mm, np.asarray(normals))


def _repeat_boundary(one: _Boundary, profile: StockFormProfile) -> _Boundary:
    return _Boundary(np.concatenate([_rotate(one.points, k * profile.angular_pitch_rad)
                                     for k in range(profile.teeth)]),
                     tuple(f"tooth{k}:{name}" for k in range(profile.teeth) for name in one.names),
                     one.error_mm, np.tile(one.normal_error_rad, profile.teeth))


def _inside(point: np.ndarray, polygon: np.ndarray) -> bool:
    a, b = polygon, np.roll(polygon, -1, axis=0)
    selected = (a[:, 1] > point[1]) != (b[:, 1] > point[1])
    a, b = a[selected], b[selected]
    x = a[:, 0] + (point[1] - a[:, 1]) * (b[:, 0] - a[:, 0]) / (b[:, 1] - a[:, 1])
    return bool(np.count_nonzero(x > point[0]) % 2)


def _polygon_overlap(a: np.ndarray, b: np.ndarray) -> bool:
    """Proper crossings plus containment; not a vertices-only collision test."""
    a1, b1 = np.roll(a, -1, axis=0), np.roll(b, -1, axis=0)
    use_a = (np.maximum(a[:, 0], a1[:, 0]) >= b[:, 0].min()) & (np.minimum(a[:, 0], a1[:, 0]) <= b[:, 0].max())
    use_b = (np.maximum(b[:, 0], b1[:, 0]) >= a[:, 0].min()) & (np.minimum(b[:, 0], b1[:, 0]) <= a[:, 0].max())
    p, r = a[use_a], a1[use_a] - a[use_a]
    q, s = b[use_b], b1[use_b] - b[use_b]
    den = _cross(r[:, None, :], s[None, :, :])
    delta = q[None, :, :] - p[:, None, :]
    valid = abs(den) > 1e-15
    safe = np.where(valid, den, 1.0)
    t = _cross(delta, s[None, :, :]) / safe
    u = _cross(delta, r[:, None, :]) / safe
    if np.any(valid & (t > 0) & (t < 1) & (u > 0) & (u < 1)):
        return True
    return _inside(a[0], b) or _inside(b[0], a)


def _point_edge_distances(points: np.ndarray, edges: np.ndarray,
                          ends: np.ndarray, cap: float) -> np.ndarray:
    """Euclidean distance to every finite edge, clipped to a proven far bound."""
    if len(points) == 0:
        return np.empty(0)
    if len(edges) == 0:
        return np.full(len(points), cap)
    d = ends - edges
    den = np.sum(d * d, axis=1)
    relative = points[:, None, :] - edges[None, :, :]
    fraction = np.clip(np.sum(relative * d[None, :, :], axis=2)
                       / np.where(den > 0, den, 1)[None, :], 0, 1)
    delta = relative - fraction[:, :, None] * d[None, :, :]
    return np.minimum(cap, np.sqrt(np.min(np.sum(delta * delta, axis=2), axis=1)))


@dataclass(frozen=True)
class _Event:
    angle: float
    a_feature: str
    b_feature: str
    point: tuple[float, float]
    normal: tuple[float, float]
    moment_arm: float
    normal_error_rad: float
    normal_on_driven: bool


def _circle_edge_intersections(vertices: np.ndarray, edges: np.ndarray,
                               ends: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """All circle/finite-edge intersections, including tangencies and endpoints."""
    d = ends - edges
    aa = np.sum(d * d, axis=1)
    bb = 2 * np.sum(edges * d, axis=1)
    cc = np.sum(edges * edges, axis=1)[None, :] - np.sum(vertices * vertices, axis=1)[:, None]
    discriminant = bb[None, :] ** 2 - 4 * aa[None, :] * cc
    root = np.sqrt(np.maximum(discriminant, 0))
    found_v, found_e, found_t = [], [], []
    for sign in (-1, 1):
        t = (-bb[None, :] + sign * root) / (2 * np.where(aa > 0, aa, 1))[None, :]
        valid = (discriminant >= 0) & (aa[None, :] > 0) & (t >= 0) & (t <= 1)
        iv, ie = np.nonzero(valid)
        found_v.append(iv)
        found_e.append(ie)
        found_t.append(t[iv, ie])
    return np.concatenate(found_v), np.concatenate(found_e), np.concatenate(found_t)


def _working(name: str) -> bool:
    return "root" not in name and any(kind in name for kind in ("flank", "radial", "tip_corner"))


def _vertex_name(names: tuple[str, ...], index: int) -> str:
    before, after = names[(index - 1) % len(names)], names[index]
    if ("tip_land" in before and _working(after)) or (_working(before) and "tip_land" in after):
        return after.split(":")[0] + ":tip_corner" if ":" in after else "tip_corner"
    if "root" in before or "root" in after:
        return after.split(":")[0] + ":root_corner" if ":" in after else "root_corner"
    return after


def _support_primitives(boundary: _Boundary, points: np.ndarray,
                        edges: np.ndarray):
    """Finite smooth chords and separately located directed endpoint cones.

    Tangent angles suffice: outward normals share the same quarter-turn on the
    two consistently oriented exteriors. The shorter signed turn from incoming
    to outgoing tangent encloses a convex vertex's physical cone, not both
    directions around either adjacent edge. Concave vertices retain that arc
    conservatively; they cannot create a false support certificate.
    """
    ends = np.roll(points, -1, axis=0)
    tangent = ends - points
    angle = np.arctan2(tangent[:, 1], tangent[:, 0])
    vertices = np.unique(np.concatenate((edges, (edges + 1) % len(points))))
    before = (vertices - 1) % len(points)
    turn = (angle[vertices] - angle[before] + pi) % (2 * pi) - pi
    vertex_error = np.maximum(boundary.normal_error_rad[before],
                              boundary.normal_error_rad[vertices])
    return (
        np.concatenate((points[edges], points[vertices])),
        np.concatenate((ends[edges], points[vertices])),
        np.concatenate((angle[edges], angle[before] + turn / 2)),
        np.concatenate((boundary.normal_error_rad[edges],
                        np.minimum(pi, abs(turn) / 2 + vertex_error))),
        np.asarray([not _working(boundary.names[i]) for i in edges]
                   + [not _working(_vertex_name(boundary.names, i)) for i in vertices]),
    )


def _finite_segment_distances(a: np.ndarray, ae: np.ndarray,
                              b: np.ndarray, be: np.ndarray) -> np.ndarray:
    """Distance for paired finite segments, including point/segment primitives."""
    def endpoint_distance(point, start, end):
        edge = end - start
        length2 = np.sum(edge * edge, axis=1)
        t = np.clip(np.sum((point - start) * edge, axis=1)
                    / np.where(length2 > 0, length2, 1), 0, 1)
        return np.linalg.norm(point - start - t[:, None] * edge, axis=1)

    distances = np.minimum.reduce((
        endpoint_distance(a, b, be), endpoint_distance(ae, b, be),
        endpoint_distance(b, a, ae), endpoint_distance(be, a, ae),
    ))
    r, s, relative = ae - a, be - b, b - a
    denominator = _cross(r, s)
    safe = np.where(denominator != 0, denominator, 1)
    t, u = _cross(relative, s) / safe, _cross(relative, r) / safe
    crossing = (denominator != 0) & (t >= 0) & (t <= 1) & (u >= 0) & (u <= 1)
    return np.where(crossing, 0.0, distances)


def _shift_feature(name: str, shift: int, teeth: int) -> str:
    tooth, separator, feature = name.partition(":")
    if separator and tooth.startswith("tooth"):
        return f"tooth{(int(tooth[5:]) + shift) % teeth}:{feature}"
    return name


class _MaterialEngine:
    def __init__(self, driver: StockFormProfile, driven: StockFormProfile,
                 centre: float, driver_clocking: float, driven_clocking: float,
                 error: float):
        self.driver, self.driven, self.centre = driver, driven, centre
        self.driver_clocking, self.driven_clocking = driver_clocking, driven_clocking
        self.error = error
        self.ratio = driver.teeth / driven.teeth
        self.operating_radius = centre * driven.teeth / (driver.teeth + driven.teeth)
        # Geometry consumes a small part of the budget; phase sweep pays its own.
        self.one_a = _one_pitch_boundary(driver, error / 64)
        self.one_b = _one_pitch_boundary(driven, error / 64)
        self.a = _repeat_boundary(self.one_a, driver)
        self.b = _repeat_boundary(self.one_b, driven)
        self.geometry_error = (self.a.error_mm + self.b.error_mm
                               + 128 * np.finfo(float).eps * (1 + centre))

    def pose_margin(self, phi: float, psi: float) -> float:
        """Signed separation/penetration witness, after curve-enclosure error.

        Positive: all material boundaries separated by at least that distance.
        Negative: an exact sampled boundary point is inside the other material
        with at least that clearance.  Zero is unresolved, NEVER called free.
        The cap only drops edges proven farther away by blank-circle x bounds.
        """
        cap = max(self.error * 4, self.geometry_error * 16)
        a = _rotate(self.a.points, phi + self.driver_clocking)
        b = _rotate(self.b.points, psi) + (self.centre, 0)
        ae, be = np.roll(a, -1, axis=0), np.roll(b, -1, axis=0)
        keep_a = np.maximum(a[:, 0], ae[:, 0]) >= self.centre - self.driven.blank_radius_mm - cap
        keep_b = np.minimum(b[:, 0], be[:, 0]) <= self.driver.blank_radius_mm + cap
        points_a = a[a[:, 0] >= self.centre - self.driven.blank_radius_mm - cap]
        points_b = b[b[:, 0] <= self.driver.blank_radius_mm + cap]
        da = _point_edge_distances(points_a, b[keep_b], be[keep_b], cap)
        db = _point_edge_distances(points_b, a[keep_a], ae[keep_a], cap)
        if not _polygon_overlap(a, b):
            distance = min(float(da.min(initial=cap)), float(db.min(initial=cap)))
            return max(0.0, distance - self.geometry_error)
        penetration = 0.0
        for point, distance in zip(points_a, da):
            if distance > penetration and self.driven.contains_material(
                point[0] - self.centre, point[1], rotate_rad=psi
            ):
                penetration = max(penetration, float(distance) - self.b.error_mm)
        for point, distance in zip(points_b, db):
            if distance > penetration and self.driver.contains_material(
                point[0], point[1], rotate_rad=phi + self.driver_clocking
            ):
                penetration = max(penetration, float(distance) - self.a.error_mm)
        return -max(0.0, penetration - self.geometry_error)

    def bracket_margin(self, phi: float, row: PhaseContact, delta: float) -> float:
        """Witness both free-side and collision-side of both backlash endpoints."""
        lo, hi = row.reverse_driven_phase_rad, row.driven_phase_rad
        if hi - lo <= 2 * delta:
            return 0.0
        return min(self.pose_margin(phi, lo + delta),
                   self.pose_margin(phi, hi - delta),
                   -self.pose_margin(phi, lo - delta),
                   -self.pose_margin(phi, hi + delta))

    def unsupported_possible(self, phi: float, psi: float,
                             half_driver: float, half_driven: float) -> bool:
        """Enclose unsupported finite contact in a witnessed swept pose box.

        Neither overlapping AABBs nor a remote endpoint's normal cone imply
        contact. Each smooth edge and each endpoint has its own spatial bound
        and tangent interval; candidates must survive finite-distance exclusion.
        False means every unsupported candidate is separated or normal-ineligible.
        True remains UNKNOWN, not evidence of an actual unsupported carrier.
        """
        a = _rotate(self.a.points, phi + self.driver_clocking)
        b = _rotate(self.b.points, psi) + (self.centre, 0)
        ae, be = np.roll(a, -1, axis=0), np.roll(b, -1, axis=0)
        motion = (self.driver.blank_radius_mm * half_driver
                  + self.driven.blank_radius_mm * half_driven + self.geometry_error)
        ia = np.flatnonzero(np.maximum(a[:, 0], ae[:, 0]) >= self.centre - self.driven.blank_radius_mm - motion)
        ib = np.flatnonzero(np.minimum(b[:, 0], be[:, 0]) <= self.driver.blank_radius_mm + motion)
        if not len(ia) or not len(ib):
            return False
        ap, aq, aa, an, bad_a = _support_primitives(self.a, a, ia)
        bp, bq, ba, bn, bad_b = _support_primitives(self.b, b, ib)
        alo, ahi = np.minimum(ap, aq), np.maximum(ap, aq)
        blo, bhi = np.minimum(bp, bq), np.maximum(bp, bq)
        near = np.all((alo[:, None, :] <= bhi[None, :, :] + motion)
                      & (blo[None, :, :] <= ahi[:, None, :] + motion), axis=2)
        mismatch = abs((aa[:, None] - ba[None, :] + 2 * pi) % (2 * pi) - pi)
        normals = an[:, None] + bn[None, :] + half_driver + half_driven
        # Include roundoff in angle arithmetic; spatial roundoff is already
        # included in geometry_error and therefore in motion.
        normals += 128 * np.finfo(float).eps
        ca, cb = np.nonzero(near & (mismatch <= normals)
                           & (bad_a[:, None] | bad_b[None, :]))
        if not len(ca):
            return False
        distance = _finite_segment_distances(ap[ca], aq[ca], bp[cb], bq[cb])
        return bool(np.any(distance <= motion))

    def datum(self, phi: float) -> float:
        return pi - self.driven.angular_pitch_rad / 2 + self.driven_clocking - self.ratio * phi

    def transmission_error_at(self, phi: float) -> float:
        return self.contact_at(phi).driven_phase_rad - self.datum(phi)

    def _events(self, phi: float) -> list[_Event]:
        a = _rotate(self.a.points, phi + self.driver_clocking)
        aend = np.roll(a, -1, axis=0)
        offset = np.array((self.centre, 0.0))
        # Cull only outside the other blank; omitted edges cannot contact it.
        active = np.maximum(a[:, 0], aend[:, 0]) >= self.centre - self.driven.blank_radius_mm - self.geometry_error
        indices = np.flatnonzero(active)
        p, pend = a[indices] - offset, aend[indices] - offset
        q = self.one_b.points
        qend = np.concatenate((q[1:], _rotate(q[:1], self.driven.angular_pitch_rad)))
        events = []
        iv, ie, tt = _circle_edge_intersections(p, q, qend)
        for i, j, t in zip(iv, ie, tt):
            on_b = q[j] + t * (qend[j] - q[j])
            angle = atan2(p[i, 1], p[i, 0]) - atan2(on_b[1], on_b[0])
            tangent = _rotate(qend[j] - q[j], angle)
            normal = np.array((tangent[1], -tangent[0])) / np.linalg.norm(tangent)
            point = p[i] + offset
            tooth_b = floor(angle / self.driven.angular_pitch_rad) % self.driven.teeth
            events.append(_Event(angle % self.driven.angular_pitch_rad,
                                 _vertex_name(self.a.names, int(indices[i])), f"tooth{tooth_b}:{self.one_b.names[j]}",
                                 tuple(point), tuple(normal), abs(float(_cross(p[i], normal))),
                                 float(self.one_b.normal_error_rad[j]), True))
        iv, ie, tt = _circle_edge_intersections(q, p, pend)
        for i, j, t in zip(iv, ie, tt):
            on_a = p[j] + t * (pend[j] - p[j])
            angle = atan2(on_a[1], on_a[0]) - atan2(q[i, 1], q[i, 0])
            tangent = pend[j] - p[j]
            normal = np.array((tangent[1], -tangent[0])) / np.linalg.norm(tangent)
            tooth_b = floor(angle / self.driven.angular_pitch_rad) % self.driven.teeth
            events.append(_Event(angle % self.driven.angular_pitch_rad,
                                 self.a.names[indices[j]], f"tooth{tooth_b}:{_vertex_name(self.one_b.names, int(i))}",
                                 tuple(on_a + offset), tuple(normal), abs(float(_cross(on_a, normal))),
                                 float(self.a.normal_error_rad[indices[j]]), False))
        return sorted(events, key=lambda e: e.angle)

    def contact_at(self, phi: float) -> PhaseContact:
        row = self._polygon_contact_at(phi)
        delta = max(row.phase_error_rad, 128 * np.finfo(float).eps)
        for _ in range(12):
            if delta * self.driven.blank_radius_mm > self.error / 2:
                raise MeshCertificationError("First-contact curve enclosure exceeds requested phase error")
            if self.bracket_margin(phi, row, delta) > 0:
                return replace(row, phase_error_rad=delta)
            delta *= 2
        raise MeshCertificationError("First-contact free/collision brackets remain unresolved")

    def _polygon_contact_at(self, phi: float) -> PhaseContact:
        if not isfinite(phi):
            raise ValueError("Driver phase must be finite")
        cycles = floor(phi / self.driver.angular_pitch_rad)
        local = phi - cycles * self.driver.angular_pitch_rad
        events = self._events(local)
        if not events:
            raise MeshCertificationError("No first-contact event: gears have no carrying engagement")
        pitch = self.driven.angular_pitch_rad
        datum = self.datum(local)
        target = datum % pitch
        a = _rotate(self.a.points, local + self.driver_clocking)
        # Distinct contacts retain their feature records; only zero-width free
        # intervals are suppressed.  Search nearest the mechanical datum.
        candidates = []
        for i, event in enumerate(events):
            following = events[(i + 1) % len(events)]
            lo, hi = event.angle, following.angle + (pitch if i == len(events) - 1 else 0)
            if hi - lo <= 1e-12:
                continue
            mid = (lo + hi) / 2
            distance = abs((mid - target + pitch / 2) % pitch - pitch / 2)
            candidates.append((distance, lo, hi, event, following))
        for _, lo, hi, lower, upper in sorted(candidates, key=lambda row: row[0]):
            mid = (lo + hi) / 2
            b = _rotate(self.b.points, mid) + np.array((self.centre, 0.0))
            if _polygon_overlap(a, b):
                continue
            # Contact moment lower bound includes normal-cone and chord error.
            lever = min(lower.moment_arm, upper.moment_arm)
            normal_uncertainty = max(lower.normal_error_rad, upper.normal_error_rad)
            lever -= self.driven.blank_radius_mm * normal_uncertainty + 2 * self.geometry_error
            if lever <= 0:
                raise MeshCertificationError("First contact is singular: no positive driven moment bound")
            phase_error = 2 * self.geometry_error / lever
            # This is only a starting bracket width.  Public queries prove it
            # with geometric free/penetration witnesses, not local slope alone.
            if hi - lo <= 2 * phase_error:
                raise MeshCertificationError("Free backlash interval is smaller than geometric uncertainty")
            shift = round((datum - mid) / pitch) * pitch - cycles * pitch
            # Positive driver rotation pushes the mate toward decreasing phase;
            # the upper endpoint is the loaded flank encountered from free space.
            carry = upper
            contact_angle = hi + shift
            reverse_angle = lo + shift
            supported = _working(carry.a_feature) and _working(carry.b_feature)
            secondary = {}
            carrying_tooth = carry.a_feature.split(":")[0]
            for event in events:
                if not (_working(event.a_feature) and _working(event.b_feature)):
                    continue
                tooth = event.a_feature.split(":")[0]
                if tooth == carrying_tooth:
                    continue
                point = np.asarray(event.point)
                normal_a = np.asarray(event.normal) * (-1 if event.normal_on_driven else 1)
                # Same drive flank, not the mirror reverse-backlash branch.
                if _cross(point, normal_a) <= 0 or _cross(point - (self.centre, 0), -normal_a) <= 0:
                    continue
                delta = (event.angle - hi + pitch / 2) % pitch - pitch / 2
                if delta <= 0:
                    continue
                if tooth not in secondary or delta < secondary[tooth][0]:
                    secondary[tooth] = (delta, event, normal_a)
            other_gap = 0.0
            for delta, event, normal_a in secondary.values():
                q = np.asarray(event.point) - (self.centre, 0)
                displacement = _rotate(q, -delta) - q
                other_gap = max(other_gap, float(displacement @ normal_a))
            return PhaseContact(phi + self.driver_clocking, contact_angle, reverse_angle,
                                (hi - lo) * self.operating_radius,
                                (_shift_feature(carry.a_feature, -cycles, self.driver.teeth),
                                 _shift_feature(carry.b_feature, -round((contact_angle - carry.angle) / pitch), self.driven.teeth)),
                                supported, phase_error,
                                lever, other_gap, carry.point,
                                atan2(carry.normal[1], carry.normal[0]) + (pi if carry.normal_on_driven else 0))
        raise MeshCertificationError("Full repeated material has no collision-free rotational component")


class _ConjugateEngine:
    """Closed-form control ONLY for unshifted actual matching master involutes."""

    def __init__(self, driver, driven, centre, driver_clocking, driven_clocking):
        self.driver, self.driven = driver, driven
        self.ratio = driver.teeth / driven.teeth
        self.driver_clocking, self.driven_clocking = driver_clocking, driven_clocking
        self.operating_radius = centre / (1 + self.ratio)
        rb = driver.template.base_radius_mm + driven.template.base_radius_mm
        alpha = acos(rb / centre)
        nominal = radians(driver.template.pressure_angle_deg)
        self.half_backlash_angle = (1 + self.ratio) * (tan(alpha) - alpha - tan(nominal) + nominal)
        self.float_error = 128 * np.finfo(float).eps * (1 + centre)
        self.datum_shift = round((driven_clocking + self.ratio * driver_clocking)
                                 / driven.angular_pitch_rad) * driven.angular_pitch_rad
        self.centre, self.alpha = centre, alpha
        ra, rb = driver.template.base_radius_mm, driven.template.base_radius_mm
        length = sqrt(centre * centre - (ra + rb) ** 2)
        self.u_min = max(driver.flank_parameter_min,
                         (length - rb * driven.flank_parameter_max) / ra)

    def datum(self, phi):
        return pi - self.driven.angular_pitch_rad / 2 + self.driven_clocking - self.ratio * phi

    def transmission_error_at(self, phi):
        return self.contact_at(phi).driven_phase_rad - self.datum(phi)

    def contact_at(self, phi):
        if not isfinite(phi):
            raise ValueError("Driver phase must be finite")
        base = (pi - self.driven.angular_pitch_rad / 2
                - self.ratio * (phi + self.driver_clocking) + self.datum_shift)
        theta = phi + self.driver_clocking
        seed_u = theta + self.alpha - self.driver.template.half_space_base_angle_rad
        tooth = ceil((self.u_min - seed_u) / self.driver.angular_pitch_rad)
        u = seed_u + tooth * self.driver.angular_pitch_rad
        point = _rotate(self.driver.flank_point(u, side=-1),
                        theta + tooth * self.driver.angular_pitch_rad)
        driven_angle = base + self.half_backlash_angle
        mate_tooth = round((atan2(point[1], point[0] - self.centre) - driven_angle)
                           / self.driven.angular_pitch_rad)
        return PhaseContact(phi + self.driver_clocking, base + self.half_backlash_angle,
                            base - self.half_backlash_angle,
                            2 * self.half_backlash_angle * self.operating_radius,
                            (f"tooth{tooth % self.driver.teeth}:lowerfiniteflank",
                             f"tooth{mate_tooth % self.driven.teeth}:lowerfiniteflank"),
                            True, self.float_error,
                            self.driven.template.base_radius_mm, 0.0, tuple(point), pi / 2 - self.alpha)


def _conjugate_control(driver, driven, centre, driver_clocking, driven_clocking, error=0.001):
    """Return a theorem-backed control, never an ideal-N substitute for stock."""
    if not (
        driver.radial_translation_mm == driven.radial_translation_mm == 0
        and driver.template.reference_teeth == driver.teeth
        and driven.template.reference_teeth == driven.teeth
        and driver.template.module_mm == driven.template.module_mm
        and driver.template.pressure_angle_deg == driven.template.pressure_angle_deg
        and driver.template.pitch_tooth_thickness_mm == pi * driver.template.module_mm / 2
        and driven.template.pitch_tooth_thickness_mm == pi * driven.template.module_mm / 2
        and centre >= driver.pitch_radius_mm + driven.pitch_radius_mm
    ):
        return None
    ra, rb = driver.template.base_radius_mm, driven.template.base_radius_mm
    length = sqrt(max(0.0, centre * centre - (ra + rb) ** 2))
    lo = max(driver.flank_parameter_min,
             (length - rb * driven.flank_parameter_max) / ra)
    hi = min(driver.flank_parameter_max,
             (length - rb * driven.flank_parameter_min) / ra)
    coverage = max(0.0, hi - lo) / driver.angular_pitch_rad
    root_air = min(centre - driver.blank_radius_mm - driven.root_radius_max_mm,
                   centre - driven.blank_radius_mm - driver.root_radius_max_mm)
    if coverage <= 1 or root_air <= 0:
        return None
    engine = _ConjugateEngine(driver, driven, centre, driver_clocking, driven_clocking)
    phases = tuple(j * driver.angular_pitch_rad / 16 for j in range(17))
    rows = tuple(engine.contact_at(phi) for phi in phases)
    # Controls run the GENERAL branch/material implementations too.  The exact
    # theorem closes the zero-backlash limit which no finite Hausdorff polygon
    # approximation can certify as a nonempty open rotational interval.
    outer, inner = _branch_enclosures(_NormalFeature(driver, "flank"),
                                     _NormalFeature(driven, "flank"), centre,
                                     error / max(driver.blank_radius_mm, driven.blank_radius_mm))
    branch_low = _measure(inner) / driver.angular_pitch_rad
    branch_high = _measure(outer) / driver.angular_pitch_rad
    if not branch_low - engine.float_error <= coverage <= branch_high + engine.float_error:
        raise MeshCertificationError("General common-normal control disagrees with conjugate theorem")
    material = _MaterialEngine(driver, driven, centre, driver_clocking, driven_clocking, error)
    for phi, row in zip(phases, rows):
        if row.backlash_mm > error:
            actual = material.contact_at(phi)
            if abs(actual.driven_phase_rad - row.driven_phase_rad) > actual.phase_error_rad + row.phase_error_rad:
                raise MeshCertificationError("General first-contact control disagrees with conjugate theorem")
        else:
            events = material._events(phi)
            angular = 4 * material.geometry_error / driven.template.base_radius_mm
            pitch = driven.angular_pitch_rad
            distance = min((abs((event.angle - row.driven_phase_rad + pitch / 2) % pitch - pitch / 2)
                            for event in events), default=float("inf"))
            if distance > angular or material.pose_margin(phi, row.driven_phase_rad) < -4 * material.geometry_error:
                raise MeshCertificationError("General repeated material contradicts zero-backlash conjugate control")
    te = tuple(row.driven_phase_rad - engine.datum(phi) for phi, row in zip(phases, rows))
    eps = engine.float_error
    union = supported_branch_coverage(driver, driven, centre, maximum_error_mm=error)
    errors = {"coverage": eps, "uncovered_phase_rad": 0.0,
              "backlash_mm": eps * engine.operating_radius * 2, "root_air_mm": eps,
              "transmission_error_driver_rad": eps / engine.ratio,
              "transmission_error_driven_rad": eps, "handover_jump_mm": eps,
              "normal_gap_mm": eps, "boundary_mm": eps, "phase_sweep_rad": 0.0}
    # Overlap of consecutive exact contact intervals proves continuous support,
    # even for a zero-backlash control.  Reserve here is contact-phase overlap.
    reserve = (coverage - 1) * driver.angular_pitch_rad / 2
    return MeshReport(coverage, 0.0, rows[0].backlash_mm, rows[0].backlash_mm,
                      root_air, tuple(-x / engine.ratio for x in te), te,
                      tuple(row.driver_phase_rad for row in rows),
                      tuple(row.driven_phase_rad for row in rows),
                      ("flank->flank",), errors, True, 0.0,
                      tuple(reserve for _ in rows), 0.0,
                      tuple(row.feature_ids for row in rows), False, True,
                      (coverage - eps, coverage + eps), driver.angular_pitch_rad,
                      driven.angular_pitch_rad, engine,
                      smooth_flank_coverage=coverage,
                      smooth_flank_coverage_interval=(coverage - eps, coverage + eps),
                      corner_inclusive_coverage=union.value,
                      corner_inclusive_coverage_interval=(union.lower_bound, union.upper_bound))


def planar_contact(driver: StockFormProfile, driven: StockFormProfile,
                   centre_distance_mm: float, *, driver_clocking_rad: float = 0.0,
                   driven_clocking_rad: float = 0.0,
                   maximum_error_mm: float = 0.001):
    """Prepare direct signed first-contact queries without a whole-period study.

    ``contact_at(phi).phase_error_rad`` is the pointwise driven-phase enclosure.
    ``transmission_error_at(phi)`` subtracts only the explicit mechanical datum.
    Positive TE is driven lag relative to its negative operating direction.
    """
    _validate(driver, driven, centre_distance_mm, maximum_error_mm)
    if not isfinite(driver_clocking_rad) or not isfinite(driven_clocking_rad):
        raise ValueError("Clocking angles must be finite")
    control = _conjugate_control(driver, driven, centre_distance_mm,
                                driver_clocking_rad, driven_clocking_rad, maximum_error_mm)
    if control is not None:
        return control._engine
    return _MaterialEngine(driver, driven, centre_distance_mm,
                           driver_clocking_rad, driven_clocking_rad, maximum_error_mm)


def _handover_displacement(signed_te_rad, operating_radius_mm, phase_error_rad):
    """Conservative adjacent endpoint displacement, including the period seam.

    Smooth TE change over the cell is intentionally not subtracted.  A jump
    inside a cell is already enclosed by that cell's free/collision witnesses.
    """
    values = tuple(signed_te_rad)
    jumps = [abs(b - a) for a, b in zip(values, values[1:] + values[:1])]
    return max(jumps, default=0.0) * operating_radius_mm, 2 * phase_error_rad * operating_radius_mm


def _branch_reserve(coverage, driver, phi, feature, clocking):
    """Entry/exit reserve of the actual carrying tooth's supported branch."""
    tooth = int(feature.partition(":")[0][5:])
    # Positive drive loads the lower gap flank at the right of this material
    # tooth. Reflect the canonical upper-side branch, retaining tooth index.
    angle = phi + clocking + (tooth + 1) * driver.angular_pitch_rad
    angle = atan2(sin(angle), cos(angle))
    uncertainty = 2 * coverage.numerical_error_rad
    for lo, hi in coverage.phase_intervals_rad:
        lower, upper = -hi, -lo
        if lower <= angle <= upper:
            return angle - lower - uncertainty, upper - angle - uncertainty
    return -float("inf"), -float("inf")


def analyse_planar_mesh(driver: StockFormProfile, driven: StockFormProfile,
                        centre_distance_mm: float, *, driver_clocking_rad: float = 0.0,
                        driven_clocking_rad: float = 0.0,
                        maximum_error_mm: float = 0.001) -> MeshReport:
    """Measure finite actual external mesh, with explicit conservative errors.

    No acceptance threshold is hidden here.  Callers pay ``numerical_error_bounds``
    on the appropriate side of their source-owned floors/ceilings.  In particular
    coverage >= a caller's threshold does NOT imply continuous carrying contact.
    ``qualified_continuous_contact`` additionally requires supported first contact,
    a connected free-phase component, and an enclosed handover jump <= .005 mm.
    """
    _validate(driver, driven, centre_distance_mm, maximum_error_mm)
    if not isfinite(driver_clocking_rad) or not isfinite(driven_clocking_rad):
        raise ValueError("Clocking angles must be finite")
    control = _conjugate_control(driver, driven, centre_distance_mm,
                                driver_clocking_rad, driven_clocking_rad, maximum_error_mm)
    if control is not None:
        return control
    coverage = supported_branch_coverage(driver, driven, centre_distance_mm,
                                        maximum_error_mm=maximum_error_mm / 4)
    engine = _MaterialEngine(driver, driven, centre_distance_mm,
                             driver_clocking_rad, driven_clocking_rad, maximum_error_mm)
    period = driver.angular_pitch_rad
    # Four robust geometric witnesses bracket both contact endpoints.  Moving
    # the driver by h moves every material point by <= R*h.  Thus a witness
    # margin > R*h proves the entire phase cell, including unseen switches.
    # This does not infer a global Lipschitz constant from sampled derivatives.
    delta = maximum_error_mm / (2 * max(driven.blank_radius_mm, engine.operating_radius))
    count = max(32, ceil(period * driver.blank_radius_mm / (maximum_error_mm / 4)))
    cells = []
    pending = [(period * j / count, period * (j + 1) / count) for j in range(count)]
    while pending:
        lo, hi = pending.pop()
        phi, half = (lo + hi) / 2, (hi - lo) / 2
        row = engine._polygon_contact_at(phi)
        margin = engine.bracket_margin(phi, row, delta)
        if margin <= driver.blank_radius_mm * half:
            if hi - lo < period / 200_000:
                raise MeshCertificationError("Swept free/collision phase brackets could not be certified")
            pending.extend(((lo, phi), (phi, hi)))
            continue
        uncertain = engine.unsupported_possible(phi, row.driven_phase_rad, half, delta)
        support_delta = delta
        while row.supported and uncertain and support_delta > row.phase_error_rad:
            candidate_delta = support_delta / 2
            candidate_margin = engine.bracket_margin(phi, row, candidate_delta)
            if candidate_margin <= driver.blank_radius_mm * half:
                break
            # Narrowing is paid by the SAME four geometric witnesses. A local
            # derivative or the observed feature label is never a substitute.
            support_delta, margin = candidate_delta, candidate_margin
            uncertain = engine.unsupported_possible(
                phi, row.driven_phase_rad, half, support_delta
            )
        if row.supported and uncertain and hi - lo >= period / 200_000:
            pending.extend(((lo, phi), (phi, hi)))
            continue
        cells.append((lo, hi, phi, row, uncertain or not row.supported,
                      margin / driver.blank_radius_mm - half))
    cells.sort(key=lambda cell: cell[0])
    phases = [cell[2] for cell in cells]
    rows = [cell[3] for cell in cells]
    half_step = max((cell[1] - cell[0]) / 2 for cell in cells)
    phase_sweep = delta
    driven_error = delta + engine.ratio * half_step
    backlash_error = 2 * delta * engine.operating_radius
    te = tuple(row.driven_phase_rad - engine.datum(phi) for phi, row in zip(phases, rows))
    feature_ids = tuple(row.feature_ids for row in rows)
    handover, handover_error = _handover_displacement(te, engine.operating_radius, driven_error)
    unsupported = [cell[4] for cell in cells]
    uncovered = sum(cell[1] - cell[0] for cell in cells if cell[4])
    uncertain_support = sum(cell[1] - cell[0] for cell in cells
                            if cell[4] and cell[3].supported)
    unsupported_samples = tuple(cell[3].driver_phase_rad for cell in cells
                                if not cell[3].supported)
    support_reserves = [
        _branch_reserve(coverage, driver, phi, row.feature_ids[0], driver_clocking_rad)
        for phi, row in zip(phases, rows)
    ]
    reserves = tuple(min(pair) - (cell[1] - cell[0]) / 2
                     for pair, cell in zip(support_reserves, cells))
    handover_reserves = []
    for i in range(len(rows)):
        previous = rows[i - 1].feature_ids[0]
        incoming = rows[i].feature_ids[0]
        phi = cells[i][0]
        if i == 0:
            previous = _shift_feature(previous, 1, driver.teeth)
        if previous.partition(":")[0] != incoming.partition(":")[0]:
            entry = _branch_reserve(coverage, driver, phi, incoming, driver_clocking_rad)[0]
            exit_ = _branch_reserve(coverage, driver, phi, previous, driver_clocking_rad)[1]
            handover_reserves.append((entry, exit_))
    root_air = min(centre_distance_mm - driver.blank_radius_mm - driven.root_radius_max_mm,
                   centre_distance_mm - driven.blank_radius_mm - driver.root_radius_max_mm)
    conjugate = (driver.radial_translation_mm == 0 and driven.radial_translation_mm == 0
                 and driver.template.reference_teeth == driver.teeth
                 and driven.template.reference_teeth == driven.teeth
                 and driver.template.module_mm == driven.template.module_mm
                 and driver.template.pressure_angle_deg == driven.template.pressure_angle_deg
                 and all("flank" in a and "flank" in b for a, b in feature_ids))
    errors = {
        "coverage": (coverage.upper_bound - coverage.lower_bound) / 2,
        "uncovered_phase_rad": 0.0,
        "backlash_mm": backlash_error,
        "root_air_mm": driver.geometry_error_bound_mm + driven.geometry_error_bound_mm,
        "transmission_error_driver_rad": driven_error / engine.ratio,
        "transmission_error_driven_rad": driven_error,
        "handover_jump_mm": handover_error,
        # A secondary branch can enter/leave support inside a phase cell.  Do
        # not pretend its sampled maximum has the carrier's continuity bound.
        # This complete finite rotational-displacement bound is report-only;
        # no simultaneous-contact or small non-carrying-gap gate is implied.
        "normal_gap_mm": 2 * driven.blank_radius_mm * sin(driven.angular_pitch_rad / 4)
                         + 2 * engine.geometry_error,
        "boundary_mm": engine.geometry_error,
        "phase_sweep_rad": phase_sweep,
    }
    smooth = supported_flank_coverage(driver, driven, centre_distance_mm,
                                     maximum_error_mm=maximum_error_mm / 4)
    corner_cells = [cell for cell in cells if any("tip_corner" in name for name in cell[3].feature_ids)]
    corner_fraction = sum(cell[1] - cell[0] for cell in corner_cells) / period
    corner_angles = [atan2(sin(cell[3].normal_angle_rad), cos(cell[3].normal_angle_rad)) for cell in corner_cells]
    # Feature labels can change within a cell; these diagnostic sampled ranges
    # have complete conservative bounds, not a grid-only corner-duty claim.
    errors["corner_carrying_phase_fraction"] = max(corner_fraction, 1 - corner_fraction)
    errors["corner_normal_angle_rad"] = pi
    return MeshReport(
        coverage.value, uncovered, min(row.backlash_mm for row in rows),
        max(row.backlash_mm for row in rows), root_air,
        tuple(-value / engine.ratio for value in te), te,
        tuple(row.driver_phase_rad for row in rows), tuple(row.driven_phase_rad for row in rows),
        tuple(sorted({f"{a.split(':')[-1]}->{b.split(':')[-1]}" for a, b in feature_ids})),
        errors, conjugate, handover, reserves,
        max(row.other_pair_normal_gap_mm for row in rows), feature_ids,
        any("root" in a or "root" in b for a, b in feature_ids),
        not any(unsupported) and min(reserves) > 0 and handover + handover_error <= 0.005,
        (coverage.lower_bound, coverage.upper_bound), period, driven.angular_pitch_rad, engine,
        tuple(handover_reserves), smooth.value, (smooth.lower_bound, smooth.upper_bound),
        coverage.value, (coverage.lower_bound, coverage.upper_bound), corner_fraction,
        (min(corner_angles), max(corner_angles)) if corner_angles else None,
        uncertain_support, unsupported_samples,
    )
