"""Interval common-normal continuation of finite stock-form contact charts.

This is a pure DESIGN proof kernel, not a native or measured qualification.
A chart is one fixed physical stratum (side, tip joint, axial edge or corner).
Parametric Krawczyk inclusion proves a supported zero for *every* phase and
source realization in its cell. A point normal, optimizer success or phase
reserve is not an input certificate. Unknown active-set transitions are refused.

Handover compares roots using the SAME named source coordinates, including
body-fixed eccentricity and site-dependent rotations. First-contact coverage
and actual root-free INNER components are separately required from the shared
surface/root engine. Their absence is UNKNOWN, never physical infeasibility.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import math
from typing import Callable

import numpy as np


@dataclass(frozen=True)
class Interval:
    lower: float
    upper: float

    def __post_init__(self):
        if not all(math.isfinite(v) for v in (self.lower, self.upper)) or self.lower > self.upper:
            raise ValueError("interval endpoints must be finite and ordered")

    @classmethod
    def point(cls, value):
        return cls(float(value), float(value))

    @property
    def midpoint(self):
        return self.lower / 2 + self.upper / 2

    @property
    def magnitude(self):
        return max(abs(self.lower), abs(self.upper))

    @property
    def width(self):
        return math.nextafter(self.upper - self.lower, math.inf)

    def contains(self, other):
        other = _interval(other)
        return self.lower <= other.lower and other.upper <= self.upper

    def intersection(self, other):
        lo, hi = max(self.lower, other.lower), min(self.upper, other.upper)
        return Interval(lo, hi) if lo <= hi else None

    def __neg__(self):
        return Interval(-self.upper, -self.lower)

    def __add__(self, other):
        other = _interval(other)
        if other.lower == other.upper == 0:
            return self
        if self.lower == self.upper == 0:
            return other
        return _out(self.lower + other.lower, self.upper + other.upper)

    __radd__ = __add__

    def __sub__(self, other):
        other = _interval(other)
        if self.lower == self.upper == other.lower == other.upper:
            return Interval.point(0)
        return self + (-other)

    def __rsub__(self, other):
        return _interval(other) - self

    def __mul__(self, other):
        other = _interval(other)
        if self.lower == self.upper == 0 or other.lower == other.upper == 0:
            return Interval.point(0)
        if other.lower == other.upper == 1:
            return self
        if self.lower == self.upper == 1:
            return other
        values = (self.lower * other.lower, self.lower * other.upper,
                  self.upper * other.lower, self.upper * other.upper)
        return _out(min(values), max(values))

    __rmul__ = __mul__

    def __truediv__(self, other):
        other = _interval(other)
        if other.lower <= 0 <= other.upper:
            raise ArithmeticError("division interval contains zero")
        if other.lower == other.upper == 1:
            return self
        return self * _out(1 / other.upper, 1 / other.lower)

    def __rtruediv__(self, other):
        return _interval(other) / self

    def record(self):
        return [self.lower, self.upper]


def _interval(value):
    return value if isinstance(value, Interval) else Interval.point(value)


def _out(lo, hi):
    return Interval(math.nextafter(lo, -math.inf), math.nextafter(hi, math.inf))


def _trig(value, cosine=False):
    """Taylor enclosure, not an assumed libm error allowance.

    The stored lower/upper doubles enclose mathematical pi. Argument reduction
    pays that enclosure. Taylor's Lagrange remainder uses |sin^(n)|,|cos^(n)|<=1.
    """
    pi = Interval(3.141592653589793, 3.1415926535897936)
    if value.width >= 2 * pi.lower:
        return Interval(-1, 1)
    turns = round(value.midpoint / (2 * math.pi))
    reduced = value - (2 * turns) * pi
    squared = reduced * reduced
    term = Interval.point(1) if cosine else reduced
    total = term
    for k in range(1, 25):
        denominator = (2 * k - 1) * (2 * k) if cosine else (2 * k) * (2 * k + 1)
        term = -term * squared / denominator
        total += term
    degree = 49 if cosine else 50
    remainder = Interval.point(1)
    for k in range(1, degree + 1):
        remainder = remainder * reduced.magnitude / k
    return (total + Interval(-remainder.upper, remainder.upper)).intersection(Interval(-1, 1))


def sin_bounds(value: Interval):
    return _trig(value)


def cos_bounds(value: Interval):
    return _trig(value, True)


@dataclass(frozen=True)
class _Jet:
    value: Interval
    derivative: tuple[Interval, ...]

    @classmethod
    def constant(cls, value, size):
        return cls(_interval(value), (Interval.point(0),) * size)

    def _coerce(self, other):
        return other if isinstance(other, _Jet) else _Jet.constant(other, len(self.derivative))

    def __add__(self, other):
        other = self._coerce(other)
        return _Jet(self.value + other.value, tuple(a + b for a, b in zip(self.derivative, other.derivative)))

    __radd__ = __add__

    def __neg__(self):
        return _Jet(-self.value, tuple(-v for v in self.derivative))

    def __sub__(self, other):
        return self + (-self._coerce(other))

    def __rsub__(self, other):
        return self._coerce(other) - self

    def __mul__(self, other):
        other = self._coerce(other)
        return _Jet(self.value * other.value,
                    tuple(a * other.value + self.value * b for a, b in zip(self.derivative, other.derivative)))

    __rmul__ = __mul__

    def __truediv__(self, other):
        other = self._coerce(other)
        value = self.value / other.value
        return _Jet(value, tuple((a - value * b) / other.value
                                 for a, b in zip(self.derivative, other.derivative)))


def _sin(jet):
    return _Jet(_trig(jet.value), tuple(_trig(jet.value, True) * d for d in jet.derivative))


def _cos(jet):
    return _Jet(_trig(jet.value, True), tuple(-_trig(jet.value) * d for d in jet.derivative))


def _variables(values):
    n = len(values)
    return tuple(_Jet(_interval(v), tuple(Interval.point(int(i == j)) for j in range(n)))
                 for i, v in enumerate(values))


def _dot(a, b):
    return sum(x * y for x, y in zip(a, b))


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2],
            a[0] * b[1] - a[1] * b[0])


def _squared_norm(vector):
    """Correlated scalar squares: a straddling component never has x*x<0."""
    result = Interval.point(0)
    for value in vector:
        lower = 0.0 if value.lower <= 0 <= value.upper else min(abs(value.lower), abs(value.upper))
        upper = max(abs(value.lower), abs(value.upper))
        lo = (Interval.point(lower) * lower).lower
        hi = (Interval.point(upper) * upper).upper
        result += Interval(max(0.0, lo), hi)
    # Generic outward addition can take an exact zero lower sum one ULP
    # negative. The sum of these correlated squares is KNOWN nonnegative;
    # intersect only this proved domain, never weaken sqrt's input guard.
    return Interval(max(0.0,result.lower),result.upper)


def _matvec(matrix, vector):
    return tuple(_dot(row, vector) for row in matrix)


def _matmul(a, b):
    return tuple(tuple(_dot(row, column) for column in zip(*b)) for row in a)


def _rotate_xy(x, y, angle):
    c, s = _cos(angle), _sin(angle)
    return c * x - s * y, s * x + c * y


def _segment_jets(segment, parameter):
    """Exact NativeSegment point AND normalized-parameter tangent algebra."""
    p = segment._profile
    step = segment._b - segment._a
    u = segment._a + step * parameter
    shape = segment._shape
    if shape == "circle":
        x, y = segment._radius * _cos(u), segment._radius * _sin(u)
        dx, dy = -segment._radius * step * _sin(u), segment._radius * step * _cos(u)
    elif shape == "line":
        x0, y0, x1, y1 = segment._line
        x, y = x0 + (x1 - x0) * parameter, y0 + (y1 - y0) * parameter
        dx, dy = parameter * 0 + x1 - x0, parameter * 0 + y1 - y0
    else:
        k = p.template.half_space_base_angle_rad
        if shape == "flank":
            rb, angle = p.template.base_radius_mm, u + k
            x = p.radial_translation_mm + rb * (_cos(angle) + u * _sin(angle))
            y = segment._side * rb * (_sin(angle) - u * _cos(angle))
            dx, dy = rb * u * step * _cos(angle), segment._side * rb * u * step * _sin(angle)
        elif shape == "radial":
            c, s = _cos(parameter * 0 + k), _sin(parameter * 0 + k)
            x = p.radial_translation_mm + u * c
            y = segment._side * u * s
            dx, dy = parameter * 0 + c * step, parameter * 0 + segment._side * s * step
        elif shape == "root":
            r = p.template.root_radius_mm
            x, y = p.radial_translation_mm + r * _cos(u), r * _sin(u)
            dx, dy = -r * step * _sin(u), r * step * _cos(u)
        else:
            raise ValueError(f"unsupported native curve shape {shape!r}")
        # The normal-section finite cutter transform used by NativeSegment.
        a, c = p._helix_a, p._helix_cos
        dx, dy = _rotate_xy(dx - a * dy * c * y, c * dy + a * dy * x, a * y)
        x, y = _rotate_xy(x, c * y, a * y)
    rotation = parameter * 0 + segment._rotate_rad
    return _rotate_xy(x, y, rotation), _rotate_xy(dx, dy, rotation)


def _finite_equation_domain(segment, parameter, finite_master_extension):
    if Interval(0, 1).contains(parameter):
        return
    if not finite_master_extension or segment._shape not in ("flank", "radial"):
        raise ValueError("curve box leaves the actual finite segment")
    template = segment._profile.template
    u = segment._a + (segment._b - segment._a) * parameter
    lo = template.flank_parameter_min if segment._shape == "flank" else template.root_radius_mm
    hi = template.flank_parameter_max if segment._shape == "flank" else template.base_radius_mm
    if not Interval(lo, hi).contains(u):
        raise ValueError("derivative extension leaves the actual finite cutter master")


def segment_bounds(segment, parameter: Interval, *, finite_master_extension: bool = False):
    """Outward equation bounds, never an upper continuation of the cutter.

    Optional extension beyond a numerically stored trimmed-tip endpoint is
    ONLY for constrained Lagrangian derivatives. It remains inside the actual
    finite master, and does not make an extended point a material witness.
    """
    _finite_equation_domain(segment, parameter, finite_master_extension)
    point, tangent = _segment_jets(segment, _Jet.constant(parameter, 0))
    return tuple(v.value for v in point), tuple(v.value for v in tangent)


def segment_second_derivative_bounds(segment, parameter: Interval, *, finite_master_extension: bool = False):
    """Exact equation second derivative, including the normal-section map."""
    _finite_equation_domain(segment, parameter, finite_master_extension)
    _, tangent = _segment_jets(segment, _variables((parameter,))[0])
    return tuple(v.derivative[0] for v in tangent)


_SOURCE_SUFFIXES = ("dx_mm", "dy_mm", "dz_mm", "rx_rad", "ry_rad", "rz_rad",
                    "ecc_x_mm", "ecc_y_mm", "clock_rad")
_SOURCE_NAMES = frozenset(f"{body}_{suffix}" for body in ("driver", "driven") for suffix in _SOURCE_SUFFIXES)


@dataclass(frozen=True)
class SourcePose:
    axes: tuple[tuple[str, Interval], ...] = ()

    def __post_init__(self):
        names = tuple(name for name, _ in self.axes)
        if len(set(names)) != len(names) or not set(names) <= _SOURCE_NAMES:
            raise ValueError("source pose names must be unique supported physical coordinates")
        if any(not isinstance(value, Interval) for _, value in self.axes):
            raise TypeError("source pose axes require Interval bounds")

    def centre(self):
        return SourcePose(tuple((name, Interval.point(value.midpoint)) for name, value in self.axes))

    def record(self):
        return {name: value.record() for name, value in self.axes}


@dataclass(frozen=True)
class PhaseCell:
    driver_phase_rad: Interval
    source_pose: SourcePose = SourcePose()

    def centre(self):
        return PhaseCell(Interval.point(self.driver_phase_rad.midpoint), self.source_pose.centre())

    @property
    def parameter_names(self):
        return ("driver_phase_rad", *(name for name, _ in self.source_pose.axes))

    @property
    def parameter_bounds(self):
        return (self.driver_phase_rad, *(value for _, value in self.source_pose.axes))


@dataclass(frozen=True)
class BodyPoseBounds:
    origin_mm: tuple[Interval, ...]
    frame: tuple[tuple[Interval, ...], ...]
    axis: tuple[Interval, ...]
    inverse_frame: tuple[tuple[Interval, ...], ...]
    frame_determinant: Interval


def _frame_rows(frame):
    rows = tuple(tuple(_interval(value) for value in row) for row in frame)
    if len(rows) != 3 or any(len(row) != 3 for row in rows):
        raise ValueError("physical frame must have three Cartesian columns")
    return rows


def _frame_determinant(frame):
    rows = _frame_rows(frame)
    determinant = _dot(rows[0], _cross(rows[1], rows[2]))
    if determinant.lower <= 0:
        raise ArithmeticError("actual stored frame has no proved positive determinant")
    return determinant


def frame_inverse_bounds(frame):
    """True 3x3 inverse, not a transpose justified by approximate orthogonality."""
    rows = _frame_rows(frame)
    determinant = _frame_determinant(rows)
    columns = (_cross(rows[1], rows[2]), _cross(rows[2], rows[0]), _cross(rows[0], rows[1]))
    return tuple(tuple(value / determinant for value in row) for row in zip(*columns))


def operator_norm_upper(matrix):
    """Outward Euclidean operator bound from the actual interval Gram matrix."""
    rows = tuple(tuple(_interval(value) for value in row) for row in matrix)
    if not rows or not rows[0] or any(len(row) != len(rows[0]) for row in rows):
        raise ValueError("operator norm requires a nonempty rectangular matrix")
    size = len(rows[0])
    gram = tuple(tuple(sum(row[i]*row[j] for row in rows) for j in range(size))
                 for i in range(size))
    squared = max(sum(Interval.point(value.magnitude) for value in row).upper for row in gram)
    return sqrt_bounds(Interval.point(squared)).upper


def _body_pose(pair, body, source, actual_angle):
    p = pair.placement
    n = len(actual_angle.derivative)
    zero = _Jet.constant(0, n)
    def q(suffix):
        return source.get(f"{body}_{suffix}", zero)
    rx, ry, rz = q("rx_rad"), q("ry_rad"), q("rz_rad")
    cx, sx, cy, sy, cz, sz = _cos(rx), _sin(rx), _cos(ry), _sin(ry), _cos(rz), _sin(rz)
    rotation = ((cz * cy, cz * sy * sx - sz * cx, cz * sy * cx + sz * sx),
                (sz * cy, sz * sy * sx + cz * cx, sz * sy * cx - cz * sx),
                (-sy, cy * sx, cy * cx))
    nominal_frame = tuple(tuple(_Jet.constant(v, n) for v in row)
                          for row in getattr(p, f"{body}_frame"))
    frame = _matmul(nominal_frame, rotation)
    shift = _matvec(nominal_frame, (q("dx_mm"), q("dy_mm"), q("dz_mm")))
    ex, ey = _rotate_xy(q("ecc_x_mm"), q("ecc_y_mm"), actual_angle + q("clock_rad"))
    eccentricity = _matvec(frame, (ex, ey, zero))
    origin = tuple(_Jet.constant(v, n) + d + e for v, d, e in
                   zip(getattr(p, f"{body}_origin_mm"), shift, eccentricity))
    return origin, frame, rotation


def body_pose_bounds(pair, source_pose: SourcePose, driver_phase_rad: Interval,
                     driven_phase_rad: Interval, *, body: str):
    if body not in ("driver", "driven"):
        raise ValueError("body must be driver or driven")
    source = {name: _Jet.constant(value, 0) for name, value in source_pose.axes}
    angle = driver_phase_rad + pair.placement.driver_clocking_rad if body == "driver" else driven_phase_rad
    origin, frame, rotation = _body_pose(pair, body, source, _Jet.constant(angle, 0))
    nominal = getattr(pair.placement, f"{body}_frame")
    # Rz Ry Rx is an exact real rotation, so F^-1 = R^T F_nom^-1,
    # det(F)=det(F_nom). Do not invert an independent interval hull of R.
    rotation_transpose = tuple(tuple(value.value for value in column) for column in zip(*rotation))
    inverse = _matmul(rotation_transpose, frame_inverse_bounds(nominal))
    return BodyPoseBounds(tuple(v.value for v in origin), tuple(tuple(v.value for v in row) for row in frame),
                          tuple(row[2].value for row in frame), inverse, _frame_determinant(nominal))


@dataclass(frozen=True)
class ContactStratum:
    segment: object
    tooth: int
    t_fixed: float | None = None
    z_fixed: float | None = None
    incident_segments: tuple[tuple[object, float], ...] = ()
    radial_cap_radius_mm: float | None = None
    axial_cap_source: str = "face"

    @property
    def free_coordinates(self):
        return int(self.t_fixed is None and self.radial_cap_radius_mm is None) + int(self.z_fixed is None)

    @property
    def implicit_tip(self):
        return (self.radial_cap_radius_mm is not None or (
            self.t_fixed is not None and self.segment.kind in ("flank", "radial") and any(
                s.kind == "tip_arc" for s, _ in self.incident_segments)))

    @property
    def algebra_coordinates(self):
        return self.free_coordinates + int(self.implicit_tip)

    @property
    def normal_count(self):
        return 1 + len(self.incident_segments) + int(self.z_fixed is not None) + int(self.radial_cap_radius_mm is not None)

    @property
    def name(self):
        return (f"{self.tooth}:{self.segment.name}:t={self.t_fixed}:z={self.z_fixed}"
                f":radial_cap={self.radial_cap_radius_mm}:axial_cap={self.axial_cap_source}")

    @property
    def carrying(self):
        segments = (self.segment, *(s for s, _ in self.incident_segments))
        return all(s.kind in ("flank", "radial", "tip_arc") for s in segments)

    def record(self):
        return {"tooth": self.tooth, "segment": self.segment.name, "kind": self.segment.kind,
                "t_fixed": self.t_fixed, "z_fixed": self.z_fixed, "implicit_tip": self.implicit_tip,
                "radial_cap_radius_mm": self.radial_cap_radius_mm,
                "radial_cap_source": "Placement.driver_turned_radius_mm" if self.radial_cap_radius_mm is not None else None,
                "axial_cap_source": self.axial_cap_source,
                "incident_segments": [{"segment": s.name, "kind": s.kind, "parameter": t}
                                      for s, t in self.incident_segments]}


def contact_strata(pair, body: str, tooth: int):
    """Physical side/tip joint/end-edge charts; root junctions are not carrying.

    Adjacency comes from the authoritative ordered perimeter, not a nearby
    sampled point. The two periodic floor seams are roots, hence not charts.
    Pure axial/shoulder/cylinder interiors and the reentrant cut-law join are
    not carrying charts. Their exclusion is a first-contact prerequisite.
    The below-base/involute G1 join has a zero raw flank tangent; it is not a
    corner cone. A fixed chart crossing that join remains honest UNKNOWN.
    """
    if body not in ("driver", "driven"):
        raise ValueError("body must be driver or driven")
    profile = getattr(pair, body)
    if type(tooth) is not int or not 0 <= tooth < profile.teeth:
        raise ValueError("strata must identify a physical tooth")
    perimeter = profile.external_boundary_segments()
    face = getattr(pair.placement, f"{body}_face_mm")
    result = []
    for index, segment in enumerate(perimeter):
        if segment.kind not in ("flank", "radial", "tip_arc"):
            continue
        for z in (None, *face):
            result.append(ContactStratum(segment, tooth, z_fixed=z))
        if index + 1 < len(perimeter):
            adjacent = perimeter[index + 1]
            if adjacent.kind in ("flank", "radial", "tip_arc") and "tip_arc" in (segment.kind, adjacent.kind):
                for z in (None, *face):
                    if segment.kind == "tip_arc":
                        result.append(ContactStratum(adjacent, tooth, 0.0, z, ((segment, 1.0),)))
                    else:
                        result.append(ContactStratum(segment, tooth, 1.0, z, ((adjacent, 0.0),)))
    p = pair.placement
    if (body == "driver" and math.isfinite(p.driver_shoulder_z_mm)
            and math.isfinite(p.driver_turned_radius_mm)
            and face[0] < p.driver_shoulder_z_mm < face[1]
            and 0 < p.driver_turned_radius_mm < profile.blank_radius_mm):
        # Real cut law: material is retained if z<=S OR r<=Rt. Shoulder
        # edges outside Rt are convex; cylinder edges above S are convex.
        # Their mutual S/Rt join is REENTRANT, not a +radial/+axial cone.
        result.extend(ContactStratum(s.segment, tooth, s.t_fixed, p.driver_shoulder_z_mm,
                                     s.incident_segments, axial_cap_source="driver_shoulder")
                      for s in tuple(result) if s.z_fixed is None)
        for segment in perimeter:
            if segment.kind in ("flank", "radial"):
                for z in (None, face[1]):
                    result.append(ContactStratum(segment, tooth, z_fixed=z,
                                                 radial_cap_radius_mm=p.driver_turned_radius_mm))
    return tuple(result)


@dataclass(frozen=True)
class ChartEvaluation:
    residual: tuple[Interval, ...]
    jacobian: tuple[tuple[Interval, ...], ...]
    parameter_jacobian: tuple[tuple[Interval, ...], ...]
    margins: tuple[tuple[str, Interval], ...]
    driver_moment: Interval
    driven_moment: Interval
    cone_weights: tuple[tuple[Interval, ...], ...] = ()
    cone_generators_world: tuple[tuple[tuple[Interval, ...], ...], ...] = ()
    driven_surface_coordinates: tuple[Interval, ...] = ()


@dataclass(frozen=True)
class StockContactChart:
    pair: object
    driver_stratum: ContactStratum
    driven_stratum: ContactStratum
    unknown_box: tuple[Interval, ...]
    normal_pivot: int = 2

    def __post_init__(self):
        if self.normal_pivot not in (0, 1, 2):
            raise ValueError("normal pivot must select an actual Cartesian component")
        for body, stratum in (("driver", self.driver_stratum), ("driven", self.driven_stratum)):
            if not stratum.carrying or stratum.free_coordinates + stratum.normal_count != 3:
                raise ValueError("chart requires one real finite side/edge/corner stratum")
            if stratum.t_fixed not in (None, 0.0, 1.0):
                raise ValueError("fixed curve coordinate must be a physical endpoint")
            profile = getattr(self.pair, body)
            if stratum.segment._profile is not profile or not 0 <= stratum.tooth < profile.teeth:
                raise ValueError("contact stratum is not from the actual physical profile")
            perimeter = profile.external_boundary_segments()
            index = next((i for i, s in enumerate(perimeter) if s == stratum.segment), None)
            if index is None:
                raise ValueError("chart segment is not an authoritative material-perimeter segment")
            if stratum.t_fixed is not None and not stratum.incident_segments:
                raise ValueError("a curve endpoint requires its real incident material segment")
            for incident, endpoint in stratum.incident_segments:
                neighbour = index + 1 if stratum.t_fixed == 1.0 else index - 1
                opposite = 0.0 if stratum.t_fixed == 1.0 else 1.0
                if (incident._profile is not profile or not 0 <= neighbour < len(perimeter)
                        or perimeter[neighbour] != incident or endpoint != opposite
                        or "tip_arc" not in (stratum.segment.kind, incident.kind)):
                    raise ValueError("incident normal is not the actual adjacent finite tip endpoint")
            p = self.pair.placement
            if stratum.axial_cap_source not in ("face", "driver_shoulder"):
                raise ValueError("axial cap must name its actual physical source")
            if stratum.axial_cap_source == "driver_shoulder" and (
                    body != "driver" or stratum.z_fixed != p.driver_shoulder_z_mm
                    or not math.isfinite(p.driver_turned_radius_mm)
                    or not p.driver_face_mm[0] < stratum.z_fixed < p.driver_face_mm[1]):
                raise ValueError("shoulder stratum is not the actual internal Placement cut face")
            if stratum.radial_cap_radius_mm is not None and (
                    body != "driver" or stratum.segment.kind not in ("flank", "radial")
                    or stratum.radial_cap_radius_mm != p.driver_turned_radius_mm
                    or not 0 < stratum.radial_cap_radius_mm < profile.blank_radius_mm
                    or not p.driver_face_mm[0] < p.driver_shoulder_z_mm < p.driver_face_mm[1]
                    or stratum.t_fixed is not None or stratum.incident_segments
                    or stratum.axial_cap_source != "face"
                    or stratum.z_fixed not in (None, p.driver_face_mm[1])):
                raise ValueError("turned-cylinder stratum is not the actual retained Placement band")
        size = 5 + int(self.driver_stratum.implicit_tip) + int(self.driven_stratum.implicit_tip)
        if len(self.unknown_box) != size or any(v.lower == v.upper for v in self.unknown_box):
            raise ValueError(f"a contact chart requires {size} nondegenerate unknown intervals")

    @property
    def name(self):
        return f"{self.driver_stratum.name}|{self.driven_stratum.name}"

    @property
    def driven_tooth(self):
        return self.driven_stratum.tooth

    @property
    def offset_index(self):
        return self.driver_stratum.algebra_coordinates + self.driven_stratum.algebra_coordinates

    @property
    def driven_z_index(self):
        if self.driven_stratum.z_fixed is not None:
            return None
        return self.driver_stratum.algebra_coordinates + int(
            self.driven_stratum.t_fixed is None or self.driven_stratum.implicit_tip)


    @property
    def unknown_angle_coordinate(self):
        return "driven_material"

    @property
    def geometry_error_bound_mm(self):
        # Nominal frames are stored doubles, not assumed exact isometries.
        # Frobenius norms safely dominate their Euclidean operator norms.
        total = Interval.point(0)
        for body in ("driver", "driven"):
            frame = getattr(self.pair.placement, f"{body}_frame")
            norm = _sqrt_bounds(_squared_norm(tuple(Interval.point(float(v)) for row in frame for v in row)))
            total += norm * getattr(self.pair, body).geometry_error_bound_mm
        return total.upper

    def evaluate(self, cell: PhaseCell, unknowns: tuple[Interval, ...]):
        jets = _variables((*unknowns, *cell.parameter_bounds))
        count = len(unknowns)
        phase = jets[count]
        source = dict(zip((name for name, _ in cell.source_pose.axes), jets[count + 1:]))
        # Exact source-coordinate symmetry, not an asserted cancellation:
        # beta*=physical beta+driven clock. Both the screw and rotating
        # eccentric material origin depend only on beta*. Static pose does
        # not depend on clock. Keep the clock parameter in P but remove its
        # geometric column; physical roots/derivatives are mapped back below.
        source.pop("driven_clock_rad", None)
        beta = jets[self.offset_index]
        driver_angle = phase + self.pair.placement.driver_clocking_rad
        margins = []
        cursor = 0
        coordinates = []
        for body, stratum in (("driver", self.driver_stratum), ("driven", self.driven_stratum)):
            if stratum.t_fixed is None or stratum.implicit_tip:
                t = jets[cursor]
                cursor += 1
                if stratum.implicit_tip:
                    # Solve the REAL flank/radial-to-blank intersection. Do not
                    # mix normals from two numerically nearby endpoint points.
                    u = stratum.segment._a + (stratum.segment._b - stratum.segment._a) * t
                    template = getattr(self.pair, body).template
                    lo = template.flank_parameter_min if stratum.segment._shape == "flank" else template.root_radius_mm
                    hi = template.flank_parameter_max if stratum.segment._shape == "flank" else template.base_radius_mm
                    margins.extend(((f"{body}_finite_master_tip_lower", (u - lo).value),
                                    (f"{body}_finite_master_tip_upper", (hi - u).value)))
                    if stratum.radial_cap_radius_mm is not None:
                        margins.extend(((f"{body}_turned_cap_finite_t_lower", t.value),
                                        (f"{body}_turned_cap_finite_t_upper", (1 - t).value)))
                else:
                    margins.extend(((f"{body}_finite_t_lower", t.value), (f"{body}_finite_t_upper", (1 - t).value)))
            else:
                t = _Jet.constant(stratum.t_fixed, len(jets))
            face = getattr(self.pair.placement, f"{body}_face_mm")
            if stratum.z_fixed is None:
                z = jets[cursor]
                cursor += 1
                margins.extend(((f"{body}_finite_z_lower", (z - face[0]).value),
                                (f"{body}_finite_z_upper", (face[1] - z).value)))
            else:
                if stratum.z_fixed not in face and stratum.axial_cap_source != "driver_shoulder":
                    raise ValueError("fixed axial coordinate is not a physical face or shoulder")
                z = _Jet.constant(stratum.z_fixed, len(jets))
            coordinates.append((t, z))
        cursor += 1  # material driven angle beta*
        worlds, normals, active_equations = [], [], []
        cone_weights, cone_generators = [], []
        for (body, stratum), (t, z) in zip((("driver", self.driver_stratum), ("driven", self.driven_stratum)), coordinates):
            profile = getattr(self.pair, body)
            angle = driver_angle if body == "driver" else beta
            origin, frame, _ = _body_pose(self.pair, body, source, angle)
            angle += source.get(f"{body}_clock_rad", _Jet.constant(0, len(jets)))
            twist = 0.0 if math.isinf(profile.lead_per_radian_mm) else 1 / profile.lead_per_radian_mm
            sweep = angle + stratum.tooth * profile.angular_pitch_rad + z * twist
            point, tangent = _segment_jets(stratum.segment, t)
            x, y = _rotate_xy(*point, sweep)
            world = tuple(o + d for o, d in zip(origin, _matvec(frame, (x, y, z))))
            if stratum.implicit_tip:
                radius = stratum.radial_cap_radius_mm or profile.blank_radius_mm
                active_equations.append((_dot(point, point) - radius ** 2) / radius)
            physical_normals = []
            for segment, coordinate in ((stratum.segment, t), *((s, _Jet.constant(v, len(jets))) for s, v in stratum.incident_segments)):
                if stratum.implicit_tip and segment.kind == "tip_arc":
                    # The exact circle meets THIS finite master point. Cross
                    # its real world tangents, without assuming a floating
                    # placement matrix is an exact mathematical isometry.
                    circumferential = _matvec(frame, (-y, x, z * 0))
                    axial = _matvec(frame, (-twist * y, twist * x, z * 0 + 1))
                    physical_normals.append(_cross(circumferential, axial))
                else:
                    (px, py), (dx, dy) = _segment_jets(segment, coordinate)
                    px, py = _rotate_xy(px, py, sweep)
                    dx, dy = _rotate_xy(dx, dy, sweep)
                    tangent_world = _matvec(frame, (dx, dy, z * 0))
                    axial_world = _matvec(frame, (-twist * py, twist * px, z * 0 + 1))
                    physical_normals.append(_cross(tangent_world, axial_world))
            if stratum.radial_cap_radius_mm is not None:
                circumferential = _matvec(frame, (-y, x, z * 0))
                axial = _matvec(frame, (-twist * y, twist * x, z * 0 + 1))
                physical_normals.append(_cross(circumferential, axial))
            if stratum.z_fixed is not None:
                sign = -1 if stratum.axial_cap_source == "face" and stratum.z_fixed == getattr(self.pair.placement, f"{body}_face_mm")[0] else 1
                face_normal = _cross(tuple(row[0] for row in frame), tuple(row[1] for row in frame))
                physical_normals.append(tuple(sign * v for v in face_normal))
            weights = []
            for _ in physical_normals[:-1]:
                weight = jets[cursor]
                cursor += 1
                weights.append(weight)
            weights.append(_Jet.constant(1, len(jets)) - sum(weights))
            for index, weight in enumerate(weights):
                margins.append((f"{body}_normal_cone_weight_{index}", weight.value))
            normal = tuple(sum(w * n[j] for w, n in zip(weights, physical_normals)) for j in range(3))
            cone_weights.append(tuple(w.value for w in weights))
            cone_generators.append(tuple(tuple(v.value for v in n) for n in physical_normals))
            worlds.append(world)
            normals.append(normal)
        opposition = -_dot(normals[0], normals[1])
        pivot = normals[0][self.normal_pivot].value
        pivot_margin = Interval(min(abs(pivot.lower), abs(pivot.upper)), pivot.magnitude) if not pivot.lower <= 0 <= pivot.upper else Interval(0, pivot.magnitude)
        margins.extend((("opposed_nonzero_normal_cones", opposition.value), ("normal_cross_pivot_nonzero", pivot_margin)))
        # A turned-away region cannot be reinstated by a side chart.
        p = self.pair.placement
        if math.isfinite(p.driver_shoulder_z_mm) and math.isfinite(p.driver_turned_radius_mm):
            t, z = coordinates[0]
            point, _ = _segment_jets(self.driver_stratum.segment, t)
            below = (p.driver_shoulder_z_mm - z).value
            radial_air = (p.driver_turned_radius_mm ** 2 - _dot(point, point)).value
            if self.driver_stratum.radial_cap_radius_mm is not None:
                margins.append(("driver_turned_cap_above_actual_shoulder", (z - p.driver_shoulder_z_mm).value))
            elif self.driver_stratum.axial_cap_source == "driver_shoulder":
                margins.append(("driver_shoulder_edge_outside_actual_turned_radius", -radial_air))
            else:
                margins.append(("driver_retained_unturned_or_turned_material", below if below.lower > 0 else radial_air))
        cross = _cross(normals[0], normals[1])
        equations = (tuple(a - b for a, b in zip(worlds[0], worlds[1]))
                     + tuple(cross[j] for j in range(3) if j != self.normal_pivot)
                     + tuple(active_equations))
        # Total physical-angle derivatives include the rotating eccentric
        # material-origin velocity. They also differentiate the actual world
        # map rather than assuming exact orthogonality of stored frame doubles.
        common_normal = tuple(v.value for v in normals[1])
        moments = []
        for world, angle_index in zip(worlds, (count, self.offset_index)):
            velocity = tuple(v.derivative[angle_index] for v in world)
            moments.append(_dot(velocity, common_normal))
        return ChartEvaluation(tuple(v.value for v in equations),
                               tuple(v.derivative[:count] for v in equations),
                               tuple(v.derivative[count:] for v in equations), tuple(margins), *moments,
                               tuple(cone_weights), tuple(cone_generators),
                               tuple(v.value for v in coordinates[1]))


def chart_candidates(pair, contact, fixed_driver_phase_rad: float, driven_phase_rad: float, *,
                     unknown_radius_mm: float = 0.02, phase_radius_rad: float = 0.001):
    """Initialize real finite charts from a search witness, never certify it.

    Ordering is driver algebra t,z; driven algebra t,z; material beta*; driver
    independent cone weights; driven independent cone weights. Implicit tip
    charts include their finite master-curve t and radius-intersection equation.
    Bounded closest-point/NNLS fits select INITIAL boxes only. Every candidate
    must subsequently pass full interval support, root and first-contact proofs.
    Failure to initialize a chart is not evidence of physical infeasibility.
    """
    from scipy.optimize import minimize_scalar, nnls

    if not all(math.isfinite(v) and v > 0 for v in (unknown_radius_mm, phase_radius_rad)):
        raise ValueError("chart initialization radii must be finite and positive")
    if not all(math.isfinite(v) for v in (fixed_driver_phase_rad, driven_phase_rad)):
        raise ValueError("initial physical phases must be finite")
    if not isinstance(contact, dict):
        from dataclasses import asdict
        contact = asdict(contact)
    world = np.asarray(contact["world_point_mm"], dtype=float)
    placement = pair.placement
    local = (world - np.asarray(placement.driver_origin_mm)) @ placement.driver_frame
    angle = math.atan2(local[1], local[0]) - placement.driver_clocking_rad - fixed_driver_phase_rad
    tooth = round(angle / pair.driver.angular_pitch_rad) % pair.driver.teeth
    driver_teeth = tuple(sorted({(tooth + k) % pair.driver.teeth for k in (-1, 0, 1)}))

    def surface_seed(body, stratum):
        frame = getattr(placement, f"{body}_frame")
        point = (world - np.asarray(getattr(placement, f"{body}_origin_mm"))) @ frame
        z = float(point[2])
        if stratum.z_fixed is not None:
            if abs(z - stratum.z_fixed) > unknown_radius_mm:
                return None
            z = stratum.z_fixed
        profile = getattr(pair, body)
        phase = fixed_driver_phase_rad + placement.driver_clocking_rad if body == "driver" else driven_phase_rad
        twist = 0 if math.isinf(profile.lead_per_radian_mm) else 1 / profile.lead_per_radian_mm
        clock = phase + stratum.tooth * profile.angular_pitch_rad + z * twist
        c, s = math.cos(clock), math.sin(clock)
        xy = np.array([c * point[0] + s * point[1], -s * point[0] + c * point[1]])
        if stratum.t_fixed is None:
            fit = minimize_scalar(lambda t: float(np.sum((np.asarray(stratum.segment.point(float(t))) - xy) ** 2)),
                                  bounds=(0, 1), method="bounded", options={"xatol": 1e-13})
            if not fit.success:
                return None
            t = float(fit.x)
        else:
            t = stratum.t_fixed
        if np.linalg.norm(np.asarray(stratum.segment.point(t)) - xy) > unknown_radius_mm:
            return None
        return t, z

    def cone_seed(body, stratum, t, z):
        profile = getattr(pair, body)
        frame = getattr(placement, f"{body}_frame")
        phase = fixed_driver_phase_rad + placement.driver_clocking_rad if body == "driver" else driven_phase_rad
        twist = 0 if math.isinf(profile.lead_per_radian_mm) else 1 / profile.lead_per_radian_mm
        angle = phase + stratum.tooth * profile.angular_pitch_rad + z * twist
        c, s = math.cos(angle), math.sin(angle)
        rotate = np.array(((c, -s, 0), (s, c, 0), (0, 0, 1)))
        normals = []
        for segment, parameter in ((stratum.segment, t), *stratum.incident_segments):
            x, y = segment.point(parameter)
            dx, dy = segment.derivative(parameter)
            if stratum.implicit_tip and segment.kind == "tip_arc":
                x, y = stratum.segment.point(t)
                normal = np.array((x, y, 0))
            else:
                normal = np.cross((dx, dy, 0), (-twist * y, twist * x, 1))
            normals.append(frame @ rotate @ normal)
        if stratum.radial_cap_radius_mm is not None:
            x, y = stratum.segment.point(t)
            normals.append(frame @ rotate @ np.array((x, y, 0)))
        if stratum.z_fixed is not None:
            sign = -1 if stratum.axial_cap_source == "face" and stratum.z_fixed == getattr(placement, f"{body}_face_mm")[0] else 1
            normals.append(sign * frame[:, 2])
        matrix = np.column_stack(normals)
        target = np.asarray(contact[f"{body}_normal_world"], dtype=float)
        weights, _ = nnls(matrix, target)
        if np.sum(weights) <= 0:
            return None
        weights /= np.sum(weights)
        return weights, matrix @ weights

    drivers = [(s, seed) for tooth in driver_teeth for s in contact_strata(pair, "driver", tooth)
               if (seed := surface_seed("driver", s)) is not None]
    driven_tooth = contact["driven_tooth"]
    drivens = [(s, seed) for s in contact_strata(pair, "driven", driven_tooth)
               if (seed := surface_seed("driven", s)) is not None]
    result = []
    for a, seed_a in drivers:
        for b, seed_b in drivens:
            seeds = (cone_seed("driver", a, *seed_a), cone_seed("driven", b, *seed_b))
            if any(seed is None for seed in seeds):
                continue
            box = []
            for body, stratum, (t, z) in (("driver", a, seed_a), ("driven", b, seed_b)):
                if stratum.t_fixed is None or stratum.implicit_tip:
                    half = max(1e-6, unknown_radius_mm / max(stratum.segment.speed_bound_mm, 1e-12))
                    box.append(Interval(t - half, t + half))
                if stratum.z_fixed is None:
                    box.append(Interval(z - unknown_radius_mm, z + unknown_radius_mm))
            box.append(Interval(driven_phase_rad - phase_radius_rad, driven_phase_rad + phase_radius_rad))
            for weights, _ in seeds:
                for weight in weights[:-1]:
                    box.append(Interval(float(weight) - 0.1, float(weight) + 0.1))
            pivot = int(np.argmax(np.abs(seeds[0][1])))
            result.append(StockContactChart(pair, a, b, tuple(box), pivot))
    return tuple(result)


@dataclass(frozen=True)
class BranchProof:
    status: str
    reason: str
    chart_name: str
    driven_tooth: int
    cell: PhaseCell
    root_box: tuple[Interval, ...] = ()
    driven_phase_rad: Interval | None = None
    root_component_rad: Interval | None = None
    source_gradient_rad: tuple[Interval, ...] = ()
    contraction_upper: float | None = None
    unknown_domain: tuple[Interval, ...] = ()
    support_margins: tuple[tuple[str, Interval], ...] = ()
    common_normal_moments: tuple[Interval, ...] = ()
    normal_cone_weights: tuple[tuple[Interval, ...], ...] = ()
    normal_cone_generators_world: tuple[tuple[tuple[Interval, ...], ...], ...] = ()
    physical_strata: tuple[ContactStratum, ...] = ()
    driven_angle_unknown_index: int | None = None
    driven_station_unknown_index: int | None = None
    center_driven_phase_rad: Interval | None = None
    driven_material_phase_rad: Interval | None = None
    root_component_coordinate: str = "physical"
    geometry_error_bound_mm: float = 0.0
    center_root_box: tuple[Interval, ...] = ()
    center_contraction_upper: float | None = None
    driven_surface_root_box: tuple[Interval, ...] = ()

    def record(self):
        return {"status": self.status, "reason": self.reason, "chart": self.chart_name,
                "driven_tooth": self.driven_tooth, "phase_cell_rad": self.cell.driver_phase_rad.record(),
                "same_source_pose": self.cell.source_pose.record(),
                "driven_phase_enclosure_rad": self.driven_phase_rad.record() if self.driven_phase_rad else None,
                "root_free_component_rad": self.root_component_rad.record() if self.root_component_rad else None,
                "parameter_names": list(self.cell.parameter_names),
                "driven_phase_parameter_derivatives": [v.record() for v in self.source_gradient_rad],
                "contraction_upper": self.contraction_upper,
                "proof_schema": ("finite-stock-common-normal-continuation/1" if self.physical_strata
                                 else "finite-analytic-contact-continuation/1"),
                "unknown_domain": [v.record() for v in self.unknown_domain],
                "root_box": [v.record() for v in self.root_box],
                "driven_surface_root_box": [v.record() for v in self.driven_surface_root_box],
                "support_margins": {name: v.record() for name, v in self.support_margins},
                "common_normal_moments": [v.record() for v in self.common_normal_moments],
                "normal_cone_weights": [[v.record() for v in weights] for weights in self.normal_cone_weights],
                "normal_cone_generators_world": [[[v.record() for v in generator] for generator in body]
                                                 for body in self.normal_cone_generators_world],
                "physical_strata": {body: stratum.record() for body, stratum in
                                    zip(("driver", "driven"), self.physical_strata)},
                "driven_angle_unknown_index": self.driven_angle_unknown_index,
                "driven_station_unknown_index": self.driven_station_unknown_index,
                "unknown_angle_coordinate": "driven_material" if self.physical_strata else "physical",
                "root_component_coordinate": self.root_component_coordinate,
                "driven_material_phase_enclosure_rad": self.driven_material_phase_rad.record() if self.driven_material_phase_rad else None,
                "center_driven_phase_enclosure_rad": self.center_driven_phase_rad.record() if self.center_driven_phase_rad else None,
                "center_root_box": [v.record() for v in self.center_root_box],
                "center_contraction_upper": self.center_contraction_upper,
                "center_phase_cell_rad": self.cell.centre().driver_phase_rad.record(),
                "center_source_pose": self.cell.source_pose.centre().record(),
                "geometry_error_bound_mm": self.geometry_error_bound_mm,
                "required_support_margin_names": [name for name, _ in self.support_margins],
                "active_set_contract": "fixed physical stratum; unresolved zero-weight mode transitions refuse",
                "native_certificate": False}


def driven_station_bounds(chart: StockContactChart, proof: BranchProof):
    """OUTER station enclosure only; never count its width as supported row."""
    if proof.status != "PROVED" or proof.chart_name != chart.name:
        raise ValueError("station enclosure requires this chart's proved branch")
    index = chart.driven_z_index
    return Interval.point(chart.driven_stratum.z_fixed) if index is None else proof.root_box[index]


def _sqrt_bounds(value):
    if value.lower < 0:
        raise ArithmeticError("square-root interval is not nonnegative")
    if value.upper == 0:
        return Interval.point(0)
    lower_numerator, lower_denominator = value.lower.as_integer_ratio()
    upper_numerator, upper_denominator = value.upper.as_integer_ratio()
    lo = max(0.0, math.nextafter(math.sqrt(value.lower), -math.inf))
    hi = math.nextafter(math.sqrt(value.upper), math.inf)
    # Certify squares of the binary endpoints EXACTLY. An outward floating
    # product loses a whole subnormal square bin and can require quadrillions
    # of root-ULP steps despite an already valid endpoint.
    while lo:
        numerator, denominator = lo.as_integer_ratio()
        if numerator*numerator*lower_denominator <= lower_numerator*denominator*denominator:
            break
        lo = math.nextafter(lo, -math.inf)
    while True:
        numerator, denominator = hi.as_integer_ratio()
        if numerator*numerator*upper_denominator >= upper_numerator*denominator*denominator:
            break
        hi = math.nextafter(hi, math.inf)
    return Interval(lo, hi)


def sqrt_bounds(value: Interval):
    return _sqrt_bounds(value)


def constraint_covector_scales(chart: StockContactChart, body: str):
    """Actual world-generator/local-constraint scales AFTER the main generator."""
    if body not in ("driver", "driven"):
        raise ValueError("constraint scales require a physical body")
    stratum = getattr(chart, f"{body}_stratum")
    determinant = _frame_determinant(getattr(chart.pair.placement, f"{body}_frame"))
    factors = []
    for incident, _ in stratum.incident_segments:
        if incident.kind != "tip_arc" or not stratum.implicit_tip:
            raise ArithmeticError("noncanonical incident working-side constraint has no proved local covector scale")
        factors.append(determinant * getattr(chart.pair, body).blank_radius_mm)
    if stratum.radial_cap_radius_mm is not None:
        factors.append(determinant * stratum.radial_cap_radius_mm)
    if stratum.z_fixed is not None:
        factors.append(determinant)
    return tuple(factors)


def objective_kkt_multipliers(chart: StockContactChart, proof: BranchProof,
                              objective_gradient_world: tuple[Interval, ...]):
    """Normalize actual cone weights against real LOCAL-mm constraints.

    h=a(r)-direction*theta; c_tip=R-r, c_lowz=z-z0, c_highz=z1-z
    are native local-coordinate constraints, NOT unit-world signed distances.
    Their world covectors are F^-T grad_local(c). World tangent crosses obey
    cross(Fu,Fv)=det(F) F^-T cross(u,v), hence cap generator scale det(F)*R,
    face scale det(F). Each body's det is its OWN stored nominal determinant,
    since its real Euler rotations have det=1. The shared engine must enclose
    the actual working gradient using this inverse over the SAME domain.
    Generator order is main, native incidents, Placement radial cap, axial
    face/shoulder. Noncanonical incident working-side constraints refuse.
    """
    if chart.driver_stratum.segment.kind not in ("flank", "radial"):
        raise ArithmeticError("working-gap Lagrangian requires an actual flank/radial main generator")
    if proof.status != "PROVED" or proof.chart_name != chart.name:
        raise ValueError("KKT multipliers require this chart's proved branch")
    data = chart.evaluate(proof.cell, proof.root_box)
    weights, generators = data.cone_weights, data.cone_generators_world
    main = generators[0][0]
    alpha = _dot(objective_gradient_world, main) / _squared_norm(main)
    if alpha.lower <= 0 or weights[0][0].lower <= 0:
        raise ArithmeticError("objective gradient has no positive actual working-side scale")
    driver_scale = alpha / weights[0][0]
    normals = tuple(tuple(sum(w * n[j] for w, n in zip(body_weights, body_generators)) for j in range(3))
                    for body_weights, body_generators in zip(weights, generators))
    opposed_scale = -_dot(normals[0], normals[1]) / _squared_norm(normals[1])
    if opposed_scale.lower <= 0:
        raise ArithmeticError("opposed actual cone scale is unresolved")
    driven_scale = driver_scale * opposed_scale
    result = {}
    for body, scale, body_weights in zip(("driver", "driven"), (driver_scale, driven_scale), weights):
        factors = constraint_covector_scales(chart, body)
        if len(factors) != len(body_weights) - 1:
            raise ValueError("active physical constraint scales do not match actual cone generators")
        result[body] = tuple(scale * weight * factor for weight, factor in zip(body_weights[1:], factors))
    return result


def _matrix_product(a, b):
    return tuple(tuple(sum(x * y for x, y in zip(row, column)) for column in zip(*b)) for row in a)


def _krawczyk(evaluate: Callable, cell, box):
    """Uniform existence/uniqueness and implicit-derivative enclosure.

    The floating inverse is only a constant preconditioner. All products,
    residuals, inclusion and ||I-RJ|| tests are outward interval operations;
    correctness never depends on numpy's inverse being an exact inverse.
    """
    centre = tuple(Interval.point(v.midpoint) for v in box)
    whole = evaluate(cell, box)
    at_centre = evaluate(cell, centre)
    n = len(box)
    if len(whole.residual) != n or any(len(row) != n for row in whole.jacobian):
        raise ValueError("contact chart must have a square unknown Jacobian")
    midpoint = np.array([[v.midpoint for v in row] for row in whole.jacobian])
    inverse = np.linalg.inv(midpoint)
    r = tuple(tuple(Interval.point(float(v)) for v in row) for row in inverse)
    rj = _matrix_product(r, whole.jacobian)
    error = tuple(tuple(int(i == j) - rj[i][j] for j in range(n)) for i in range(n))
    norm = max(sum(Interval.point(v.magnitude) for v in row).upper for row in error)
    if norm >= 1:
        return None, None, norm, "Jacobian contraction is unresolved"
    delta = tuple(v - c for v, c in zip(box, centre))
    rf = _matvec(r, at_centre.residual)
    correction = _matvec(error, delta)
    image = tuple(c - f + d for c, f, d in zip(centre, rf, correction))
    if not all(x.lower < y.lower and y.upper < x.upper for x, y in zip(box, image)):
        return None, None, norm, "parametric Krawczyk image leaves the unknown-box interior"
    root_box = tuple(x.intersection(y) for x, y in zip(box, image))
    for _ in range(12):
        displacement = tuple(v - c for v, c in zip(root_box, centre))
        refined = tuple(c - f + d for c, f, d in zip(centre, rf, _matvec(error, displacement)))
        narrowed = tuple(a.intersection(b) for a, b in zip(root_box, refined))
        if any(v is None for v in narrowed):
            raise ArithmeticError("common-normal root enclosure is inconsistent")
        root_box = narrowed
    # -J^-1 Fp = -R Fp + (I-RJ) derivative. Neumann's uniform
    # infinity-norm bound seeds a verified fixed-point interval enclosure.
    rp = _matrix_product(r, whole.parameter_jacobian)
    columns = []
    for column in zip(*rp):
        rhs = tuple(-v for v in column)
        radius = (Interval.point(max(v.magnitude for v in rhs)) / (1 - Interval.point(norm))).upper
        derivative = (Interval(-radius, radius),) * n
        for _ in range(12):
            candidate = tuple(v + d for v, d in zip(rhs, _matvec(error, derivative)))
            narrowed = tuple(a.intersection(b) for a, b in zip(derivative, candidate))
            if any(v is None for v in narrowed):
                raise ArithmeticError("implicit-derivative enclosure is inconsistent")
            derivative = narrowed
        columns.append(derivative)
    gradient = tuple(tuple(column[i] for column in columns) for i in range(n))
    return root_box, gradient, norm, "parametric common-normal branch inclusion"


def prove_branch_cell(chart: StockContactChart, cell: PhaseCell, *, root_free_driven_components_rad,
                      root_free_coordinate: str = "physical"):
    """Prove one fixed active chart across a closed phase x source cell.

    root_free_driven_components_rad must be actual INNER components certified
    over the entire cell in the EXPLICIT root_free_coordinate. Stock chart
    unknowns use beta*=physical beta+driven clock; displayed roots and implicit
    derivatives map back to physical beta. A material component maps to a
    separate same-q physical component, never a marginal convex hull.
    """
    if root_free_coordinate not in ("physical", "driven_material"):
        raise ValueError("root component coordinate must be physical or driven_material")
    if root_free_coordinate == "driven_material" and not isinstance(chart, StockContactChart):
        raise ValueError("material-angle symmetry is only defined by the actual stock adapter")
    def unknown(reason, contraction=None):
        return BranchProof("UNKNOWN", reason, chart.name, chart.driven_tooth, cell, contraction_upper=contraction)
    try:
        root_box, gradient, norm, reason = _krawczyk(chart.evaluate, cell, chart.unknown_box)
        if root_box is None:
            return unknown(reason, norm)
        evaluated = chart.evaluate(cell, root_box)
        for name, margin in evaluated.margins:
            if margin.lower <= 0:
                return unknown(f"physical support/active-set margin unresolved: {name}", norm)
        a, b = evaluated.driver_moment, evaluated.driven_moment
        if (a.lower <= 0 <= a.upper or b.lower <= 0 <= b.upper or (a * b).upper >= 0):
            return unknown("opposite nonzero common-normal torque moments unresolved", norm)
        material = root_box[chart.offset_index]
        clock = dict(cell.source_pose.axes).get("driven_clock_rad", Interval.point(0))
        beta = material - clock if isinstance(chart, StockContactChart) else material
        membership = material if root_free_coordinate == "driven_material" else beta
        components = tuple(_interval(v) if isinstance(v, (Interval, int, float)) else Interval(*v)
                           for v in root_free_driven_components_rad)
        component = next((v for v in components if v.contains(membership)), None)
        if component is None:
            return unknown("full carrying-root enclosure is outside one actual root-free INNER component", norm)
        center_box, _, center_norm, center_reason = _krawczyk(chart.evaluate, cell.centre(), chart.unknown_box)
        if center_box is None:
            return unknown(f"center numerical enclosure is unresolved: {center_reason}", norm)
        center_clock = Interval.point(clock.midpoint)
        center_beta = center_box[chart.offset_index] - center_clock if isinstance(chart, StockContactChart) else center_box[chart.offset_index]
        physical_gradient = tuple(g - 1 if isinstance(chart, StockContactChart) and name == "driven_clock_rad" else g
                                  for name, g in zip(cell.parameter_names, gradient[chart.offset_index]))
        return BranchProof("PROVED", reason, chart.name, chart.driven_tooth, cell, root_box, beta, component,
                           physical_gradient, norm, chart.unknown_box, evaluated.margins,
                           (a, b), evaluated.cone_weights, evaluated.cone_generators_world,
                           (chart.driver_stratum, chart.driven_stratum) if isinstance(chart, StockContactChart) else (),
                           chart.offset_index, getattr(chart, "driven_z_index", None), center_beta,
                           material if isinstance(chart, StockContactChart) else None, root_free_coordinate,
                           chart.geometry_error_bound_mm if isinstance(chart, StockContactChart) else 0.0,
                           center_box, center_norm, evaluated.driven_surface_coordinates)
    except (ArithmeticError, ValueError, np.linalg.LinAlgError) as exc:
        return unknown(f"interval branch proof unresolved: {exc}")


@dataclass(frozen=True)
class ProofNeighbourhood:
    """Cell-bound full physical t/z rectangle and algebra/approach domains.

    Native normalized t and axial z_mm remain two physical coordinates even
    when a chart fixes either one and removes it from its algebra unknowns.
    Bounds on a point edge are not bounds on this material neighbourhood.
    """
    cell: PhaseCell
    unknown_domain: tuple[Interval, ...]
    approach_driven_phase_rad: Interval
    driven_surface_domain: tuple[Interval, Interval]
    angle_coordinate: str = "physical"

    def refusal(self, proof, approach, coordinate):
        if self.cell != proof.cell or self.angle_coordinate != coordinate:
            return "numeric geometry bound belongs to another phase/source/angle cell"
        if (len(self.unknown_domain) != len(proof.unknown_domain)
                or not all(a.contains(b) for a, b in zip(self.unknown_domain, proof.unknown_domain))):
            return "numeric geometry neighbourhood does not contain the certified chart domain"
        domain = self.driven_surface_domain
        if (not isinstance(domain, tuple) or len(domain) != 2
                or not all(isinstance(v, Interval) for v in domain)):
            return "numeric geometry bound lacks its actual driven t/z surface rectangle"
        if any(v.lower >= v.upper for v in domain):
            return "numeric geometry bound requires a full two-coordinate physical surface rectangle"
        root = proof.driven_surface_root_box
        if len(root) != 2 or not all(a.contains(b) for a, b in zip(domain, root)):
            return "numeric surface rectangle does not contain actual free/fixed driven root coordinates"
        if not self.approach_driven_phase_rad.contains(approach):
            return "numeric geometry bound does not contain the entire free-reference-to-root approach"
        return None

    def record(self):
        return {"phase_cell_rad": self.cell.driver_phase_rad.record(),
                "same_source_pose": self.cell.source_pose.record(),
                "unknown_domain": [v.record() for v in self.unknown_domain],
                "driven_surface_domain": [v.record() for v in self.driven_surface_domain]
                                         if isinstance(self.driven_surface_domain, tuple) else None,
                "driven_surface_coordinate_names": ["native_t", "z_mm"],
                "approach_driven_phase_rad": self.approach_driven_phase_rad.record(),
                "angle_coordinate": self.angle_coordinate}


@dataclass(frozen=True)
class ChartMinimumBound:
    """Numeric shared-engine sufficiency/exclusion on an entire neighbourhood.

    The tangent Hessian is that of the actual constrained loaded LAGRANGIAN
    h-sum(lambda*c), NOT the raw angular-gap objective at a clipped tip/edge.
    A full two-coordinate lower bound is required over the entire neighbourhood
    AND whole free-reference-to-root approach, even on a constrained corner.
    Strict cone multipliers in BranchProof pay one-sided active directions.
    Remainder air applies outside this neighbourhood, or outside the explicit
    PatchRemainderBound union when several charts occupy one physical patch.
    """
    chart_name: str
    tangent_dimension: int
    tangent_hessian_lower: float
    outside_neighbourhood_air_mm: Interval
    approach_derivative_magnitude_lower: float
    lagrangian_beta_derivative: Interval | None = None
    objective_direction: int = 0
    neighbourhood: ProofNeighbourhood | None = None
    objective_gradient_magnitude_upper_per_mm: float | None = None
    objective_gradient_padding_mm: float | None = None

    def refusal(self):
        if self.tangent_dimension != 2:
            return "a full two-coordinate Lagrangian minimum bound is required; declared zero dimension cannot bypass it"
        if not math.isfinite(self.tangent_hessian_lower) or self.tangent_hessian_lower <= 0:
            return "actual chart-neighbourhood local minimum is unproved"
        if self.outside_neighbourhood_air_mm.lower <= 0:
            return "selected finite patch has an unexcluded contact outside its chart neighbourhood"
        if not math.isfinite(self.approach_derivative_magnitude_lower) or self.approach_derivative_magnitude_lower <= 0:
            return "loaded first-contact transversality is unproved"
        if self.lagrangian_beta_derivative is None or self.objective_direction not in (-1, 1):
            return "signed whole-approach Lagrangian transversality evidence is absent"
        closing = self.lagrangian_beta_derivative if self.objective_direction == 1 else -self.lagrangian_beta_derivative
        if closing.lower <= 0 or self.approach_derivative_magnitude_lower > closing.lower:
            return "signed Lagrangian closing derivative/payment is unproved"
        return None

    def record(self):
        return {"chart": self.chart_name, "tangent_dimension": self.tangent_dimension,
                "neighbourhood": self.neighbourhood.record() if self.neighbourhood else None,
                "objective_gradient_magnitude_upper_per_mm": self.objective_gradient_magnitude_upper_per_mm,
                "objective_gradient_padding_mm": self.objective_gradient_padding_mm,
                "lagrangian_hessian_lower": self.tangent_hessian_lower,
                "outside_neighbourhood_air_mm": self.outside_neighbourhood_air_mm.record(),
                "approach_derivative_magnitude_lower": self.approach_derivative_magnitude_lower,
                "lagrangian_beta_derivative": self.lagrangian_beta_derivative.record() if self.lagrangian_beta_derivative else None,
                "objective_direction": self.objective_direction}


def physical_patch_root_coordinates(proof, patch_id):
    """Coordinates of THIS physical patch at the supported common root."""
    if not proof.physical_strata:
        return ("native_t","z_mm"),proof.driven_surface_root_box
    stratum = proof.physical_strata[1]
    suffix = next((value for value in (":end_face:-1",":end_face:+1") if patch_id.endswith(value)), "")
    side = patch_id[:-len(suffix)] if suffix else patch_id
    main = f"{stratum.tooth}:{stratum.segment.name}"
    if side == main:
        t = proof.driven_surface_root_box[0]
    else:
        incident = {f"{stratum.tooth}:{segment.name}":endpoint for segment,endpoint in stratum.incident_segments}
        if side not in incident:
            raise ValueError("patch is not an actual incident native surface")
        t = Interval.point(incident[side])
    if suffix:
        if stratum.z_fixed is None:
            raise ValueError("cap patch has no actual fixed face contact")
        return ("native_t","radial_fraction"),(t,Interval.point(1))
    return ("native_t","z_mm"),(t,proof.driven_surface_root_box[1])


def patch_domain_refusal(proof, patch_id, names, domain):
    try:
        expected,root = physical_patch_root_coordinates(proof,patch_id)
    except (ValueError,IndexError) as exc:
        return str(exc)
    if tuple(names) != expected or len(domain) != 2 or any(
            not isinstance(v,Interval) or v.lower >= v.upper for v in domain):
        return "physical patch lacks its own nondegenerate native parameter domain"
    if len(root) != 2 or any(not a.contains(b) for a,b in zip(domain,root)):
        return "physical patch parameter domain does not contain its actual incident/cap root"
    stratum = proof.physical_strata[1] if proof.physical_strata else None
    main = f"{stratum.tooth}:{stratum.segment.name}" if stratum else None
    side = patch_id.split(":end_face:")[0]
    master_extension = stratum is not None and stratum.implicit_tip and side == main
    # The exact blank/master intersection can straddle the rounded native
    # endpoint. Its proved neighbourhood may extend the MASTER equation;
    # outside-UNION excision still acts only on the finite physical [0,1].
    if ((domain[0].intersection(Interval(0,1)) is None if master_extension
         else not Interval(0,1).contains(domain[0]))
            or expected[1] == "radial_fraction" and not Interval(0,1).contains(domain[1])):
        return "physical patch neighbourhood has no bound finite native parameter range"
    return None


@dataclass(frozen=True)
class BoundarySeparation:
    """One-sided cap/incident-side separation next to a supported real edge.

    Its open noncarrying interior has infimum gap ZERO at that edge; it is
    not assigned a fictitious positive whole-patch air. An actual inward
    derivative bound on the entire local material neighbourhood plus positive
    air on its remainder excludes an intervening interior first contact.
    Root/floor/junction patches are never eligible for this certificate.
    """
    patch_id: str
    chart_name: str
    inward_gap_derivative_lower: float
    outside_neighbourhood_air_mm: Interval
    neighbourhood: ProofNeighbourhood | None = None
    patch_parameter_names: tuple[str,str] = ()
    patch_parameter_domain: tuple[Interval,Interval] = ()

    def refusal(self):
        if not math.isfinite(self.inward_gap_derivative_lower) or self.inward_gap_derivative_lower <= 0:
            return "actual inward edge-neighbourhood separating derivative is unproved"
        if self.outside_neighbourhood_air_mm.lower <= 0:
            return "noncarrying edge-neighbourhood remainder is not excluded"
        return None

    def record(self):
        return {"patch_id": self.patch_id, "chart": self.chart_name,
                "neighbourhood": self.neighbourhood.record() if self.neighbourhood else None,
                "patch_parameter_names":list(self.patch_parameter_names),
                "patch_parameter_domain":[v.record() for v in self.patch_parameter_domain],
                "inward_gap_derivative_lower": self.inward_gap_derivative_lower,
                "outside_neighbourhood_air_mm": self.outside_neighbourhood_air_mm.record()}


def lagrangian_approach_derivative(chart, proof, objective_gradient_world,
                                 surface_beta_velocity_world, driver_constraint_gradients_world):
    """Enclose partial_beta L, INCLUDING every actual active driver constraint.

    It is not raw partial_beta h at a clipped tip/face. The shared engine must
    check its chosen objective direction times this interval is strictly
    positive before claiming a closing first-contact approach.
    Active constraint gradient order is incident native segment(s), the
    Placement radial cap if present, then the axial face/shoulder. These are
    exactly the cone generators AFTER the main working-side generator.
    Gradients are actual world covectors F^-T grad_local(c) of LOCAL-mm
    radius/axial constraints, not generator vectors normalized to unit length.
    """
    multipliers = objective_kkt_multipliers(chart, proof, objective_gradient_world)["driver"]
    if len(multipliers) != len(driver_constraint_gradients_world):
        raise ValueError("Lagrangian approach lacks actual driver constraint gradients")
    gradient = tuple(g - sum(lam * c[j] for lam, c in zip(multipliers, driver_constraint_gradients_world))
                     for j, g in enumerate(objective_gradient_world))
    return _dot(gradient, surface_beta_velocity_world)


def boundary_inward_gap_derivative(chart, proof, objective_gradient_world,
                                  inward_tangent_world, driver_constraint_gradients_world):
    """Actual one-sided Lagrangian derivative over a local cap/edge domain.

    All supplied gradients/tangents must enclose the WHOLE material
    neighbourhood and common phase/source cell. Inward constraint gradients
    use the same physical order and native LOCAL-mm constraints as
    objective_kkt_multipliers: world gradients are inverse-transpose covectors.
    On feasible directions c>=0 the strictly positive driver multipliers
    cannot weaken this lower separating derivative.
    """
    derivative = lagrangian_approach_derivative(chart, proof, objective_gradient_world,
                                               inward_tangent_world, driver_constraint_gradients_world)
    if derivative.lower <= 0:
        raise ArithmeticError("actual cap/edge inward separation is unresolved")
    return derivative


@dataclass(frozen=True)
class PatchRemainderBound:
    """Real exclusion outside a UNION of neighborhoods on one physical patch."""
    patch_id: str
    chart_names: tuple[str, ...]
    outside_union_air_mm: Interval
    neighbourhoods: tuple[tuple[str, ProofNeighbourhood], ...] = ()
    patch_parameter_names: tuple[str,str] = ()
    patch_parameter_domains: tuple[tuple[str,tuple[Interval,Interval]], ...] = ()

    def record(self):
        return {"patch_id": self.patch_id, "charts": list(self.chart_names),
                "neighbourhoods": {name: domain.record() for name, domain in self.neighbourhoods},
                "patch_parameter_names":list(self.patch_parameter_names),
                "patch_parameter_domains":{name:[v.record() for v in domain]
                                           for name,domain in self.patch_parameter_domains},
                "outside_union_air_mm": self.outside_union_air_mm.record()}


@dataclass(frozen=True)
class FirstContactCover:
    """Shared-engine bounded exhaustive surface cover, not an assertion flag.

    Every finite search patch must appear either in charts (whose remaining
    contact zeros were excluded by the shared engine) or in a strictly positive
    clearance bound over the complete approach interval up to these roots.
    Root/floor/junction patches MUST be strictly excluded. A noncarrying open
    cap/incident-side neighbourhood touching a real supported edge instead
    requires a positive inward BoundarySeparation and excluded remainder.
    The inventory and each bound are supplied by the real complete-surface
    search; a selected-tooth list or optimizer incumbent is not this cover.
    """
    cell: PhaseCell
    root_free_driven_components_rad: tuple[Interval, ...]
    backlash_lower_mm: float
    approach_driven_phase_rad: Interval
    physical_patch_inventory: tuple[str, ...]
    chart_patch_ids: tuple[tuple[str, tuple[str, ...]], ...]
    excluded_patch_air_mm: tuple[tuple[str, Interval], ...]
    noncarrying_patch_ids: tuple[str, ...]
    required_root_air_mm: float
    chart_minimum_bounds: tuple[ChartMinimumBound, ...] = ()
    root_patch_ids: tuple[str, ...] = ()
    boundary_separations: tuple[BoundarySeparation, ...] = ()
    patch_remainder_bounds: tuple[PatchRemainderBound, ...] = ()
    free_reference_driven_phase_rad: Interval | None = None
    free_reference_air_mm: Interval | None = None
    closing_driven_sense: int = 0
    angle_coordinate: str = "physical"
    additional_geometry_error_mm: float = field(kw_only=True)

    def record(self):
        return {"proof_schema": "finite-stock-first-contact-cover/1",
                "phase_cell_rad": self.cell.driver_phase_rad.record(),
                "same_source_pose": self.cell.source_pose.record(),
                "root_free_driven_components_rad": [v.record() for v in self.root_free_driven_components_rad],
                "backlash_lower_mm": self.backlash_lower_mm,
                "approach_driven_phase_rad": self.approach_driven_phase_rad.record(),
                "physical_patch_inventory": list(self.physical_patch_inventory),
                "chart_patch_ids": {name: list(patches) for name, patches in self.chart_patch_ids},
                "excluded_patch_air_mm": {name: air.record() for name, air in self.excluded_patch_air_mm},
                "noncarrying_patch_ids": list(self.noncarrying_patch_ids),
                "required_root_air_mm": self.required_root_air_mm,
                "chart_minimum_bounds": [v.record() for v in self.chart_minimum_bounds],
                "root_patch_ids": list(self.root_patch_ids),
                "boundary_separations": [v.record() for v in self.boundary_separations],
                "patch_remainder_bounds": [v.record() for v in self.patch_remainder_bounds],
                "free_reference_driven_phase_rad": self.free_reference_driven_phase_rad.record() if self.free_reference_driven_phase_rad else None,
                "free_reference_air_mm": self.free_reference_air_mm.record() if self.free_reference_air_mm else None,
                "closing_driven_sense": self.closing_driven_sense,
                "angle_coordinate": self.angle_coordinate,
                "additional_geometry_error_mm":self.additional_geometry_error_mm,
                "native_certificate": False}

    def refusal(self, proofs):
        if self.angle_coordinate not in ("physical", "driven_material"):
            return "first-contact angle coordinate is undefined"
        if (type(self.additional_geometry_error_mm) not in (float,int)
                or not math.isfinite(self.additional_geometry_error_mm) or self.additional_geometry_error_mm < 0):
            return "first-contact additional geometry payment is missing, negative or nonfinite"
        proof_by_chart = {p.chart_name: p for p in proofs}
        if len(proof_by_chart) != len(proofs):
            return "carrying chart proofs are duplicated"
        if not math.isfinite(self.backlash_lower_mm) or self.backlash_lower_mm <= 0:
            return "positive physical backlash is unproved"
        if not math.isfinite(self.required_root_air_mm) or self.required_root_air_mm < 0:
            return "root-air requirement is invalid"
        reference = self.free_reference_driven_phase_rad
        if reference is None or self.free_reference_air_mm is None or self.free_reference_air_mm.lower <= 0:
            return "genuine common-source free-reference pose/positive-air anchor is unproved"
        if self.closing_driven_sense not in (-1, 1) or not self.approach_driven_phase_rad.contains(reference):
            return "loaded approach direction/reference domain is inconsistent"
        if not any(c.contains(self.approach_driven_phase_rad) for c in self.root_free_driven_components_rad):
            return "entire free-reference-to-root approach is outside one actual root-free INNER component"
        inventory = set(self.physical_patch_inventory)
        if not inventory or len(inventory) != len(self.physical_patch_inventory):
            return "complete finite-surface inventory is absent or duplicated"
        by_chart = dict(self.chart_patch_ids)
        if len(by_chart) != len(self.chart_patch_ids) or set(by_chart) != {p.chart_name for p in proofs}:
            return "exhaustive carrying chart cover does not match proven charts"
        included = {patch for patches in by_chart.values() for patch in patches}
        if any(len(set(patches)) != len(patches) or not patches for patches in by_chart.values()):
            return "physical chart neighbourhood inventory is absent or duplicated within one chart"
        patch_charts = {patch: {name for name, patches in by_chart.items() if patch in patches} for patch in included}
        exclusions = dict(self.excluded_patch_air_mm)
        if len(exclusions) != len(self.excluded_patch_air_mm):
            return "excluded surface inventory is duplicated"
        if included & set(exclusions) or included | set(exclusions) != inventory:
            return "finite-surface first-contact cover is incomplete or ambiguous"
        minima = {v.chart_name: v for v in self.chart_minimum_bounds}
        if len(minima) != len(self.chart_minimum_bounds) or set(minima) != set(by_chart):
            return "selected charts lack actual neighbourhood minimum/exclusion bounds"
        for minimum in minima.values():
            refusal = minimum.refusal()
            if refusal:
                return refusal
            if minimum.objective_direction != -self.closing_driven_sense:
                return "local first-contact objective direction differs from the genuine closing approach"
            proof = proof_by_chart[minimum.chart_name]
            if minimum.neighbourhood is None:
                return "numeric minimum has no bound phase/source/geometry neighbourhood"
            refusal = minimum.neighbourhood.refusal(proof, self.approach_driven_phase_rad, self.angle_coordinate)
            if refusal:
                return refusal
            gradient = minimum.objective_gradient_magnitude_upper_per_mm
            if gradient is None or not math.isfinite(gradient) or gradient <= 0:
                return "whole-neighbourhood objective Lipschitz bound for physical geometry error is absent"
            required_padding = (0.0 if proof.geometry_error_bound_mm == self.additional_geometry_error_mm == 0
                                else (Interval.point(proof.geometry_error_bound_mm)+self.additional_geometry_error_mm).upper)
            if required_padding > 0 and (
                    minimum.objective_gradient_padding_mm is None
                    or minimum.objective_gradient_padding_mm < required_padding):
                return "first-contact objective neighbourhood omits its additional geometry payment"
        shared = {patch: names for patch, names in patch_charts.items() if len(names) > 1}
        remainders = {v.patch_id: v for v in self.patch_remainder_bounds}
        if len(remainders) != len(self.patch_remainder_bounds) or set(remainders) != set(shared):
            return "shared physical patch lacks exact outside-UNION exclusion coverage"
        for patch, names in shared.items():
            remainder = remainders[patch]
            if len(set(remainder.chart_names)) != len(remainder.chart_names) or set(remainder.chart_names) != names:
                return "outside-UNION exclusion does not match all actual chart neighbourhoods"
            domains = dict(remainder.neighbourhoods)
            if len(domains) != len(remainder.neighbourhoods) or set(domains) != names:
                return "outside-UNION bound lacks its exact chart-neighbourhood domains"
            for name, domain in domains.items():
                refusal = domain.refusal(proof_by_chart[name], self.approach_driven_phase_rad, self.angle_coordinate)
                if refusal or domain != minima[name].neighbourhood:
                    return refusal or "outside-UNION bound refers to different physical neighbourhoods"
            patch_domains = dict(remainder.patch_parameter_domains)
            native = any(proof_by_chart[name].physical_strata for name in names)
            if native and (len(patch_domains) != len(remainder.patch_parameter_domains) or set(patch_domains) != names):
                return "outside-UNION bound lacks actual per-patch native parameter domains"
            for name,patch_domain in patch_domains.items():
                refusal = patch_domain_refusal(proof_by_chart[name],patch,remainder.patch_parameter_names,patch_domain)
                if refusal:
                    return refusal
                stratum = proof_by_chart[name].physical_strata[1]
                if patch == f"{stratum.tooth}:{stratum.segment.name}":
                    bound_domain = minima[name].neighbourhood.driven_surface_domain
                else:
                    boundary = next((v for v in self.boundary_separations
                                     if v.chart_name == name and v.patch_id == patch),None)
                    bound_domain = boundary.patch_parameter_domain if boundary else ()
                if patch_domain != bound_domain:
                    return "outside-UNION exclusion uses a different incident/cap parameter domain"
            if remainder.outside_union_air_mm.lower <= 0 or any(
                    minima[name].outside_neighbourhood_air_mm.lower > remainder.outside_union_air_mm.lower
                    for name in names):
                return "shared selected-patch remainder exclusion is unproved or inconsistent"
        noncarrying = set(self.noncarrying_patch_ids)
        roots = set(self.root_patch_ids)
        if not noncarrying or not noncarrying <= inventory or not roots or not roots <= noncarrying:
            return "actual noncarrying/root inventory is missing or inconsistent"
        if not roots <= set(exclusions):
            return "root/floor/junction material cannot use an edge-neighbourhood exception"
        boundaries = {(v.patch_id, v.chart_name): v for v in self.boundary_separations}
        expected = {(patch, name) for patch in noncarrying & included for name in patch_charts[patch]}
        expected |= {(patch,name) for name,patches in by_chart.items()
                     if proof_by_chart[name].physical_strata
                     for patch in patches
                     if patch != f"{proof_by_chart[name].physical_strata[1].tooth}:{proof_by_chart[name].physical_strata[1].segment.name}"}
        if len(boundaries) != len(self.boundary_separations) or set(boundaries) != expected:
            return "selected noncarrying edge neighbourhood lacks exact one-sided separation coverage"
        for boundary in boundaries.values():
            refusal = boundary.refusal()
            if refusal:
                return refusal
            if boundary.neighbourhood is None:
                return "one-sided boundary bound has no bound phase/source/geometry neighbourhood"
            refusal = boundary.neighbourhood.refusal(proof_by_chart[boundary.chart_name],
                                                      self.approach_driven_phase_rad, self.angle_coordinate)
            if refusal or boundary.neighbourhood != minima[boundary.chart_name].neighbourhood:
                return refusal or "one-sided boundary and minimum use different physical neighbourhoods"
            proof = proof_by_chart[boundary.chart_name]
            if proof.physical_strata:
                refusal = patch_domain_refusal(proof,boundary.patch_id,boundary.patch_parameter_names,
                                               boundary.patch_parameter_domain)
                if refusal:
                    return refusal
        for name, air in exclusions.items():
            required = self.required_root_air_mm if name in roots else 0.0
            if air.lower <= required:
                return f"first-contact/noncarrying exclusion unresolved: {name}"
        for proof in proofs:
            if proof.status != "PROVED" or proof.cell != self.cell:
                return "chart does not prove the entire common phase/source cell"
            if proof.root_component_coordinate != self.angle_coordinate:
                return "root and first-contact bounds use different angle coordinates"
            root = proof.driven_material_phase_rad if self.angle_coordinate == "driven_material" else proof.driven_phase_rad
            if root is None or not self.approach_driven_phase_rad.contains(root):
                return "contact root leaves the certified loaded approach interval"
            if not any(c.contains(root) for c in self.root_free_driven_components_rad):
                return "contact root is outside the certified root-free INNER components"
            if (self.closing_driven_sense == 1 and reference.upper >= root.lower
                    or self.closing_driven_sense == -1 and reference.lower <= root.upper):
                return "shared physical free reference is not strictly before the carrying roots"
        return None


def difference_from_branch_proofs(proof_a, proof_b):
    """Same-pose difference from actual numerical centres and uniform gradients."""
    if (proof_a.status != "PROVED" or proof_b.status != "PROVED" or proof_a.cell != proof_b.cell
            or proof_a.center_driven_phase_rad is None or proof_b.center_driven_phase_rad is None
            or len(proof_a.source_gradient_rad) != len(proof_a.cell.parameter_bounds)
            or len(proof_b.source_gradient_rad) != len(proof_b.cell.parameter_bounds)):
        raise ValueError("same-source difference requires bound centre and whole-cell branch proofs")
    difference = proof_b.center_driven_phase_rad - proof_a.center_driven_phase_rad
    for parameter, a, b in zip(proof_a.cell.parameter_bounds, proof_a.source_gradient_rad, proof_b.source_gradient_rad):
        difference += (b - a) * (parameter - Interval.point(parameter.midpoint))
    return difference


def branch_geometry_error_rad(proof, minimum, *, additional_geometry_error_mm):
    """Pay profile and explicit additional geometry through ONE transversality."""
    gradient = minimum.objective_gradient_magnitude_upper_per_mm
    if (gradient is None or not math.isfinite(gradient) or gradient <= 0
            or type(additional_geometry_error_mm) not in (float,int)
            or not math.isfinite(additional_geometry_error_mm) or additional_geometry_error_mm < 0):
        raise ValueError("physical position-error payment lacks finite geometry and objective bounds")
    profile = (Interval.point(proof.geometry_error_bound_mm)*gradient
               /minimum.approach_derivative_magnitude_lower).upper
    if additional_geometry_error_mm == 0:
        return profile
    additional = (Interval.point(additional_geometry_error_mm)*gradient
                  /minimum.approach_derivative_magnitude_lower).upper
    return (Interval.point(profile)+additional).upper


def correlated_root_difference(chart_a, chart_b, cell, *, root_free_driven_components_rad,
                               root_free_coordinate="physical", evidence=None):
    """Enclose beta_b-beta_a with one shared source realization.

    Centre root widths pay ONLY numerical interval solve widths. Manufacturing
    coordinates propagate through the DIFFERENCE of uniform implicit
    derivatives, not through a sum of two independently displaced roots.
    The derivative enclosures cover the WHOLE cell, including rotations,
    eccentricity, phase and changes of normal lever arm.
    """
    whole = tuple(prove_branch_cell(chart, cell, root_free_driven_components_rad=root_free_driven_components_rad,
                                   root_free_coordinate=root_free_coordinate) for chart in (chart_a, chart_b))
    if any(p.status != "PROVED" for p in whole):
        return None, whole, "common phase/source supported branch inclusion is unresolved"
    centre = tuple(prove_branch_cell(chart, cell.centre(), root_free_driven_components_rad=root_free_driven_components_rad,
                                    root_free_coordinate=root_free_coordinate) for chart in (chart_a, chart_b))
    if any(p.status != "PROVED" for p in centre):
        return None, whole, "centre numerical branch enclosure is unresolved"
    difference = centre[1].driven_phase_rad - centre[0].driven_phase_rad
    gradients = tuple(b - a for a, b in zip(whole[0].source_gradient_rad, whole[1].source_gradient_rad))
    for parameter, gradient in zip(cell.parameter_bounds, gradients):
        deviation = parameter - Interval.point(parameter.midpoint)
        difference += gradient * deviation
    if evidence is not None:
        evidence.update({"center_branch_proofs": [p.record() for p in centre],
                         "difference_parameter_derivatives": [v.record() for v in gradients],
                         "difference_parameter_names": list(cell.parameter_names),
                         "difference_parameter_bounds": [v.record() for v in cell.parameter_bounds],
                         "same_pose_driven_root_difference_rad": difference.record()})
    return difference, whole, "shared-source implicit-difference enclosure"


def prove_paid_handover(chart_a, chart_b, cell: PhaseCell, cover: FirstContactCover, *,
                        driven_pitch_radius_mm: float, maximum_jump_mm: float = 0.005,
                        driven_sense: int = 1, first_contact_branch_proofs=None):
    """Prove a supported first-contact exchange with a paid common-pose bound.

    Both branches exist over the common closed cell. Opposite endpoint signs
    FOR EVERY SAME source realization give an IVT crossing inside this cell.
    Exhaustive first-contact exclusions and one actual root-free component
    rule out an unsupported intervening collision. The reported displacement
    bound is the uniform same-pose root difference, NOT a proclaimed zero.
    A wide localization/source cell may refuse despite a continuous physical
    envelope; that is proof failure, not a physical no-solution certificate.
    """
    result = {"status": "UNKNOWN", "continuous": False, "physical_no_solution": False,
              "pair": [chart_a.driven_tooth, chart_b.driven_tooth],
              "phase_bracket_rad": cell.driver_phase_rad.record(),
              "same_source_pose": cell.source_pose.record(), "native_certificate": False,
              "first_contact_cover": cover.record()}
    if (not math.isfinite(driven_pitch_radius_mm) or driven_pitch_radius_mm <= 0
            or not math.isfinite(maximum_jump_mm) or not 0 < maximum_jump_mm <= 0.005):
        raise ValueError("actual radius must be positive; the paid limit cannot exceed the unchanged .005 mm")
    if driven_sense not in (-1, 1):
        raise ValueError("driven sense must be -1 or +1")
    difference, proofs, reason = correlated_root_difference(chart_a, chart_b, cell,
                                                           root_free_driven_components_rad=cover.root_free_driven_components_rad,
                                                           root_free_coordinate=cover.angle_coordinate,
                                                           evidence=result)
    result["branch_proofs"] = [p.record() for p in proofs]
    if difference is None:
        return {**result, "reason": reason}
    full = {p.chart_name:p for p in (proofs if first_contact_branch_proofs is None else first_contact_branch_proofs)}
    if first_contact_branch_proofs is not None and len(full) != len(first_contact_branch_proofs):
        return {**result,"reason":"first-contact handover proofs are duplicated"}
    for chart,actual in zip((chart_a,chart_b),proofs):
        supplied = full.get(chart.name)
        if supplied is None or supplied.cell != cell or supplied.unknown_domain != chart.unknown_box:
            return {**result,"reason":"handover pair is absent from its actual full-source first-contact cover"}
        full[chart.name] = actual
    result["first_contact_branch_proofs"] = [p.record() for p in full.values()]
    refusal = cover.refusal(tuple(full.values()))
    if refusal:
        return {**result, "reason": refusal}
    if driven_sense != cover.closing_driven_sense:
        return {**result, "reason": "handover closing sense differs from actual first-contact approach"}
    if proofs[0].root_component_rad != proofs[1].root_component_rad:
        return {**result, "reason": "handover branches are in different actual root-free components"}
    minima = {m.chart_name:m for m in cover.chart_minimum_bounds}
    competitors = []
    for competitor in full.values():
        if competitor.chart_name in (chart_a.name,chart_b.name):
            continue
        comparisons = []
        for selected in proofs:
            difference_to_competitor = driven_sense * difference_from_branch_proofs(selected,competitor)
            payment = (Interval.point(branch_geometry_error_rad(selected,minima[selected.chart_name],
                        additional_geometry_error_mm=cover.additional_geometry_error_mm))
                       + branch_geometry_error_rad(competitor,minima[competitor.chart_name],
                        additional_geometry_error_mm=cover.additional_geometry_error_mm))
            paid = difference_to_competitor - payment
            comparisons.append({"chart":selected.chart_name,
                                "closing_competitor_excess_rad":difference_to_competitor.record(),
                                "physical_geometry_error_payment_rad":payment.record(),
                                "paid_competitor_excess_lower_rad":paid.lower})
        competitors.append({"competitor_chart":competitor.chart_name,"pair_comparisons":comparisons})
        if max(v["paid_competitor_excess_lower_rad"] for v in comparisons) < 0:
            return {**result,"reason":"another physical root may intervene in the proposed first-contact exchange",
                    "full_cell_competitor_exclusions":competitors}
    result["full_cell_competitor_exclusions"] = competitors
    endpoints, endpoint_evidence = [], []
    for phase in (cell.driver_phase_rad.lower, cell.driver_phase_rad.upper):
        end = PhaseCell(Interval.point(phase), cell.source_pose)
        proof_evidence = {}
        delta, end_proofs, reason = correlated_root_difference(
            chart_a, chart_b, end, root_free_driven_components_rad=cover.root_free_driven_components_rad,
            root_free_coordinate=cover.angle_coordinate, evidence=proof_evidence)
        if delta is None:
            return {**result, "reason": f"endpoint crossing localization unresolved: {reason}"}
        endpoints.append(driven_sense * delta)
        endpoint_evidence.append({**proof_evidence, "phase_rad": phase,
                                  "branch_proofs": [p.record() for p in end_proofs],
                                  "closing_difference_rad": endpoints[-1].record()})
    result["endpoint_difference_proofs"] = endpoint_evidence
    # sense*delta >0 means a is encountered first in the loaded approach.
    minima = {m.chart_name: m for m in cover.chart_minimum_bounds}
    error_rad = sum(Interval.point(branch_geometry_error_rad(p,minima[p.chart_name],
                    additional_geometry_error_mm=cover.additional_geometry_error_mm)) for p in proofs)
    if endpoints[0].lower <= error_rad.upper or endpoints[1].upper >= -error_rad.upper:
        return {**result, "reason": "same-source supported first-contact exchange is not uniformly bracketed after geometry payment",
                "physical_geometry_error_payment_rad": error_rad.record(),
                "endpoint_difference_enclosures_rad": [v.record() for v in endpoints]}
    jump = (Interval.point(driven_pitch_radius_mm) * (Interval.point(difference.magnitude) + error_rad)).upper
    result.update({"same_pose_driven_root_difference_rad": difference.record(),
                   "pitch_displacement_jump_upper_mm": jump,
                   "physical_geometry_error_payment_rad": error_rad.record(),
                   "root_component_coordinate": cover.angle_coordinate,
                   "endpoint_difference_enclosures_rad": [v.record() for v in endpoints],
                   "root_free_component_rad": proofs[0].root_component_rad.record(),
                   "bound_definition": "same physical phase and same source coordinates; numerical centre roots plus uniform difference sensitivities"})
    if jump > maximum_jump_mm:
        return {**result, "reason": "correlated common-pose localization payment exceeds the unchanged handover limit"}
    return {**result, "status": "PROVED", "continuous": True,
            "reason": "compact supported first-contact charts exchange inside one actual root-free component with paid same-source bound"}


def retained_phase_coverage(phase_cells, *, driver_pitch_rad: float,
                            driven_pitch_radius_mm: float, maximum_jump_mm: float = 0.005):
    """Integrate certified supported-tooth union spans, including phase seams.

    Each item is (PhaseCell, tuple[BranchProof,...], FirstContactCover). All
    cells must use the SAME full physical source domain, not corner counts or
    independently narrowed source boxes. Distinct teeth count once per phase;
    a side/tip/edge chart change is not an extra tooth. No point reserves enter.
    This helper deliberately does not manufacture supported-row or paid-handover
    certificates. Full supported span does NOT alone prove carrying continuity.
    """
    if not math.isfinite(driver_pitch_rad) or driver_pitch_rad <= 0:
        raise ValueError("driver pitch must be finite and positive")
    if (not math.isfinite(driven_pitch_radius_mm) or driven_pitch_radius_mm <= 0
            or not math.isfinite(maximum_jump_mm) or not 0 < maximum_jump_mm <= 0.005):
        raise ValueError("coverage requires actual driven radius and a paid limit no larger than .005 mm")
    items = tuple(phase_cells)
    if not items:
        return {"status": "UNKNOWN", "continuous_carrying_contact": False,
                "stock_form_coverage_lower": 0.0, "uncovered_phase_rad": driver_pitch_rad,
                "reason": "no full-source supported phase cells"}
    source = items[0][0].source_pose
    spans, carrier_records = [], []
    for cell, proofs, cover in items:
        refusal = cover.refusal(proofs)
        if refusal or cell.source_pose != source or cover.cell != cell:
            return {"status": "UNKNOWN", "continuous_carrying_contact": False,
                    "reason": refusal or "phase/source cell label differs from the actual certified cover"}
        lo, hi = cell.driver_phase_rad.lower, cell.driver_phase_rad.upper
        if lo < 0 or hi > driver_pitch_rad or lo >= hi:
            return {"status": "UNKNOWN", "continuous_carrying_contact": False,
                    "reason": "phase cell leaves the declared closed whole-pitch domain"}
        minima = {m.chart_name: m for m in cover.chart_minimum_bounds}
        admissible, comparisons = set(), []
        for candidate in proofs:
            candidate_comparisons = []
            eligible = True
            for competitor in proofs:
                if competitor.chart_name == candidate.chart_name:
                    continue
                try:
                    difference = cover.closing_driven_sense * difference_from_branch_proofs(competitor, candidate)
                    error = (Interval.point(branch_geometry_error_rad(candidate,minima[candidate.chart_name],
                              additional_geometry_error_mm=cover.additional_geometry_error_mm))
                             + branch_geometry_error_rad(competitor,minima[competitor.chart_name],
                              additional_geometry_error_mm=cover.additional_geometry_error_mm))
                    excess_mm = (Interval.point(driven_pitch_radius_mm)
                                 * (Interval.point(difference.upper) + error)).upper
                except (ArithmeticError, ValueError):
                    eligible = False
                    break
                candidate_comparisons.append({"competitor_chart": competitor.chart_name,
                                              "closing_root_excess_rad": difference.record(),
                                              "difference_parameter_derivatives": [
                                                  (cover.closing_driven_sense * (a - b)).record()
                                                  for a, b in zip(candidate.source_gradient_rad, competitor.source_gradient_rad)],
                                              "difference_parameter_names": list(cell.parameter_names),
                                              "physical_geometry_error_payment_rad": error.record(),
                                              "pitch_excess_upper_mm": excess_mm})
                if excess_mm > maximum_jump_mm:
                    eligible = False
            comparisons.append({"chart": candidate.chart_name, "driven_tooth": candidate.driven_tooth,
                                "eligible": eligible, "same_pose_comparisons": candidate_comparisons})
            if eligible:
                admissible.add(candidate.driven_tooth)
        spans.append((lo, hi, frozenset(admissible)))
        carrier_records.append({"phase_cell_rad": cell.driver_phase_rad.record(),
                                "branch_proofs": [p.record() for p in proofs],
                                "first_contact_cover": cover.record(),
                                "counted_teeth": sorted(admissible), "carrier_comparisons": comparisons})
    cuts = sorted({0.0, driver_pitch_rad, *(v for lo, hi, _ in spans for v in (lo, hi))})
    integral, uncovered = Interval.point(0), Interval.point(0)
    for lo, hi in zip(cuts, cuts[1:]):
        supported = set().union(*(teeth for a, b, teeth in spans if a <= lo and hi <= b))
        width = Interval.point(hi) - Interval.point(lo)
        integral += len(supported) * width
        if not supported:
            uncovered += width
    seam_supported = any(lo == 0 and teeth for lo, _, teeth in spans) and any(hi == driver_pitch_rad and teeth for _, hi, teeth in spans)
    resolved = uncovered.upper <= 0 and seam_supported
    # A mathematically exact zero sum has an exact zero interval; all nonzero
    # accumulated widths are rounded OUTWARD, so the reported lower stays safe.
    return {"status": "PROVED" if resolved else "UNKNOWN",
            "supported_no_gap": resolved,
            "continuous_carrying_contact": False,
            "handover_proof_required": True,
            "stock_form_coverage_lower": max(0.0, (integral / driver_pitch_rad).lower),
            "uncovered_phase_rad": max(0.0, uncovered.upper),
            "coverage_definition": "integral of distinct continuously supported finite tooth branches over one closed physical driver pitch",
            "carrier_cells": carrier_records,
            "driven_pitch_radius_mm": driven_pitch_radius_mm,
            "maximum_carrier_excess_mm": maximum_jump_mm,
            "same_source_pose": source.record(), "native_certificate": False,
            "reason": "full closed-phase supported cover" if resolved else "unsupported phase gap or periodic seam"}


def _periodicity_displacement_evidence(pair, source_pose):
    """Pay finite relabel defects through the complete joint tooth period."""
    true_turn = Interval(3.141592653589793, 3.1415926535897936) * 2
    axes = dict(source_pose.axes)
    bodies = {}
    total = Interval.point(0)
    joint_steps = math.lcm(pair.driver.teeth, pair.driven.teeth)
    for body, step in (("driver", 1), ("driven", -1)):
        profile = getattr(pair, body)
        pitch = profile.angular_pitch_rad
        if not math.isfinite(pitch) or pitch <= 0 or profile.teeth <= 0:
            raise ValueError("periodicity requires the actual positive finite tooth pitch")
        # The actual adapter evaluates tooth*pitch as a stored float. Bound
        # every relabel, including rounding of that product and the wrap.
        errors = []
        for tooth in range(profile.teeth):
            mapped = (tooth + step) % profile.teeth
            if step == 1:
                delta = Interval.point(pitch) + Interval.point(tooth * pitch) - Interval.point(mapped * pitch)
                if mapped == 0:
                    delta -= true_turn
            else:
                delta = Interval.point(pitch) + Interval.point(mapped * pitch) - Interval.point(tooth * pitch)
                if tooth == 0:
                    delta -= true_turn
            errors.append(delta)
        angle = Interval.point(max(v.magnitude for v in errors))
        c, s = cos_bounds(Interval.point(pitch)), sin_bounds(Interval.point(pitch))
        # Exact real R(p)R(-p)=I. Retain, rather than proclaim zero for, the
        # finite interval product enclosure used by the source relabelling.
        rotations = (((c, -s), (s, c)), ((c, s), (-s, c)))
        closure = _matrix_product(*rotations)
        closure_error = tuple(closure[i][j] - int(i == j) for i in range(2) for j in range(2))
        closure_norm = sqrt_bounds(_squared_norm(tuple(Interval.point(v.magnitude) for v in closure_error)))
        eccentricity = sqrt_bounds(_squared_norm(tuple(
            axes.get(f"{body}_ecc_{axis}_mm",Interval.point(0)) for axis in ("x","y"))))
        frame = _frame_rows(getattr(pair.placement, f"{body}_frame"))
        frame_norm = sqrt_bounds(_squared_norm(tuple(value for row in frame for value in row)))
        radius = Interval.point(profile.blank_radius_mm) + Interval.point(profile.geometry_error_bound_mm)
        one_step = frame_norm * (angle * (radius + eccentricity) + closure_norm * eccentricity)
        # Each exact local rotation has norm one. Successive relabel defects
        # therefore add, rather than disappearing at the first tooth seam.
        # lcm(Ndriver,Ndriven) steps restore BOTH physical tooth labels.
        displacement = Interval.point(joint_steps) * one_step
        total += Interval.point(displacement.upper)
        bodies[body] = {"tooth_relabel_angle_errors_rad": [v.record() for v in errors],
                        "rotation_product_error": [v.record() for v in closure_error],
                        "frame_operator_upper": frame_norm.upper,
                        "rectangular_eccentricity_radius_upper_mm": eccentricity.upper,
                        "joint_period_tooth_steps": joint_steps,
                        "one_step_displacement_upper_mm": one_step.upper,
                        "displacement_upper_mm": displacement.upper}
    return total.upper, bodies


def periodicity_displacement_bound_mm(pair, source_pose: SourcePose):
    """World-mm arc padding required IN ADDITION to actual profile geometry E."""
    return _periodicity_displacement_evidence(pair, source_pose)[0]


def _periodic_source_relabel(pair, source_pose, disks):
    """Validate real centred physical disks; never rotate a rectangle into itself."""
    if not isinstance(disks, dict) or set(disks) != {"driver", "driven"}:
        raise ValueError("periodic source requires both authenticated physical eccentricity disks")
    axes = dict(source_pose.axes)
    rotations = {}
    for body, sign in (("driver", 1), ("driven", -1)):
        disk = disks[body]
        if not isinstance(disk, dict) or disk.get("shape") != "closed_disk" or disk.get("centre_mm") != [0.0, 0.0]:
            raise ValueError("periodic eccentricity source must be a closed disk centred at zero")
        terms = disk.get("source_terms_mm")
        if (not isinstance(terms, dict) or not terms
                or any(not isinstance(name, str) or not name for name in terms)):
            raise ValueError("physical eccentricity disk lacks named source-grade radial terms")
        values = tuple(terms.values())
        radius = disk.get("radius_mm")
        if (not isinstance(radius, (int, float)) or not math.isfinite(radius) or radius < 0
                or any(not isinstance(v, (int, float)) or not math.isfinite(v) or v < 0 for v in values)
                or radius < sum((Interval.point(v) for v in values), Interval.point(0)).upper):
            raise ValueError("physical eccentricity radius does not enclose its outward source-term sum")
        for axis in ("x", "y"):
            if axes.get(f"{body}_ecc_{axis}_mm") != Interval(-radius, radius):
                raise ValueError("physical eccentricity disk is not authenticated by both symmetric source axes")
        angle = Interval.point(sign * getattr(pair, body).angular_pitch_rad)
        c, s = cos_bounds(angle), sin_bounds(angle)
        rotations[body] = ((c, -s), (s, c))
    return rotations


def correlated_periodic_branch_difference(start_proof, end_proof, pair, *, source_eccentricity_disks):
    """Same-realization endpoint difference beta_start(Tq)-p_driven-beta_end(q).

    This is a supported branch-difference bound, NOT first-contact or seam
    qualification. The certified rectangles enclose the physical disks.
    Their rotated corners need not fit: only disk points and their convex
    centre-to-point paths are used by the exact linear chain rule.
    """
    source = start_proof.cell.source_pose
    if (start_proof.status != "PROVED" or end_proof.status != "PROVED"
            or source != end_proof.cell.source_pose
            or not start_proof.physical_strata or not end_proof.physical_strata
            or start_proof.cell.driver_phase_rad != Interval.point(0)
            or end_proof.cell.driver_phase_rad != Interval.point(pair.driver.angular_pitch_rad)
            or start_proof.center_driven_phase_rad is None or end_proof.center_driven_phase_rad is None):
        raise ValueError("periodic branch comparison requires actual same-source endpoint/centre proofs")
    rotations = _periodic_source_relabel(pair, source, source_eccentricity_disks)
    names = tuple(name for name, _ in source.axes)
    if (len(start_proof.source_gradient_rad) != len(names) + 1
            or len(end_proof.source_gradient_rad) != len(names) + 1):
        raise ValueError("periodic branch sensitivities do not match the actual source coordinates")
    start_gradient = dict(zip(names, start_proof.source_gradient_rad[1:]))
    transformed = dict(start_gradient)
    for body, rotation in rotations.items():
        x, y = (f"{body}_ecc_{axis}_mm" for axis in ("x", "y"))
        transformed[x] = start_gradient[x] * rotation[0][0] + start_gradient[y] * rotation[1][0]
        transformed[y] = start_gradient[x] * rotation[0][1] + start_gradient[y] * rotation[1][1]
    derivatives = tuple(transformed[name] - value for name, value in zip(names, end_proof.source_gradient_rad[1:]))
    centre = start_proof.center_driven_phase_rad - pair.driven.angular_pitch_rad - end_proof.center_driven_phase_rad
    difference = centre
    for (_, parameter), derivative in zip(source.axes, derivatives):
        difference += derivative * (parameter - Interval.point(parameter.midpoint))
    return {"centre_difference_rad": centre.record(),
            "difference_parameter_names": list(names),
            "difference_parameter_derivatives": [v.record() for v in derivatives],
            "same_pose_driven_root_difference_rad": difference.record(),
            "source_relabel": {body: [[v.record() for v in row] for row in matrix]
                               for body, matrix in rotations.items()},
            "source_domain": "same physical centred disks within certified boxes; other axes unchanged",
            "native_certificate": False}


def physical_patch_inventory(pair):
    """Every physical driven perimeter and both finite radial-fan end caps."""
    perimeter = tuple(pair.driven.external_boundary_segments())
    inventory = tuple(f"{tooth}:{segment.name}{suffix}" for tooth in range(pair.driven.teeth)
                      for segment in perimeter for suffix in ("",":end_face:-1",":end_face:+1"))
    roots = tuple(f"{tooth}:{segment.name}{suffix}" for tooth in range(pair.driven.teeth)
                  for segment in perimeter if segment.kind not in ("flank","radial","tip_arc")
                  for suffix in ("",":end_face:-1",":end_face:+1"))
    root_set = set(roots)
    noncarrying = tuple(name for name in inventory if name in root_set or ":end_face:" in name)
    return inventory,roots,noncarrying


def _seam_stratum_key(stratum, tooth):
    return (stratum.segment, tooth, stratum.t_fixed, stratum.z_fixed,
            stratum.incident_segments, stratum.radial_cap_radius_mm, stratum.axial_cap_source)


def _seam_interval(value):
    return value if isinstance(value, Interval) else Interval(*value)


def _seam_record(value):
    if isinstance(value, Interval):
        return value.record()
    if isinstance(value, dict):
        return {key: _seam_record(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_seam_record(item) for item in value]
    return value


def prove_periodic_seam(start_charts, start_cell, start_cover, end_charts, end_cell, end_cover, *,
                        start_branch_proofs, end_branch_proofs, source_eccentricity_disks,
                        root_receipt, driven_root_material_receipt,
                        root_air_requirements_mm, driven_pitch_radius_mm: float,
                        maximum_jump_mm: float = 0.005):
    """Pay an actual supported first-contact min/max envelope over one pitch.

    All paired endpoint branches, not a guessed uniformly first branch, are
    compared under the same physical source relabelling. A bijection and
    exhaustive first-contact covers give |min a-min b| (or max) <= max|a-b|.
    Shared-engine root/exclusion/gradient bounds remain genuine prerequisites.
    """
    result = {"proof_schema": "finite-stock-periodic-seam/1", "status": "UNKNOWN", "continuous": False,
              "native_certificate": False, "physical_no_solution": False,
              "phase_endpoints_rad": [0.0, end_cell.driver_phase_rad.upper],
              "same_source_pose": start_cell.source_pose.record(),
              "source_eccentricity_disks": source_eccentricity_disks,
              "root_proof": _seam_record(root_receipt), "chart_pairs": [],
              "driven_root_material_proof":_seam_record(driven_root_material_receipt),
              "root_air_requirements_mm": root_air_requirements_mm,
              "start_endpoint_branch_proofs": [], "end_endpoint_branch_proofs": [],
              "start_full_cell_branch_proofs": [p.record() for p in start_branch_proofs],
              "end_full_cell_branch_proofs": [p.record() for p in end_branch_proofs],
              "start_first_contact_cover": start_cover.record(), "end_first_contact_cover": end_cover.record()}
    try:
        if (not math.isfinite(driven_pitch_radius_mm) or driven_pitch_radius_mm <= 0
                or not math.isfinite(maximum_jump_mm) or not 0 < maximum_jump_mm <= 0.005):
            raise ValueError("periodic seam uses the actual positive radius and unchanged .005 limit")
        if not start_charts or not end_charts or any(not isinstance(c, StockContactChart) for c in (*start_charts, *end_charts)):
            raise ValueError("periodic seam requires actual finite StockContactCharts")
        pair = start_charts[0].pair
        if any(c.pair is not pair for c in (*start_charts, *end_charts)) or driven_pitch_radius_mm != pair.driven.pitch_radius_mm:
            raise ValueError("periodic seam charts/radius do not belong to one actual physical pair")
        pitch, mate_pitch = pair.driver.angular_pitch_rad, pair.driven.angular_pitch_rad
        if (not isinstance(root_air_requirements_mm, dict) or set(root_air_requirements_mm) != {"driver", "driven"}
                or any(not isinstance(v, (int, float)) or not math.isfinite(v) or v < 0
                       for v in root_air_requirements_mm.values())):
            raise ValueError("periodic seam requires separate authenticated driver/driven root floors")
        if min(start_cover.required_root_air_mm, end_cover.required_root_air_mm) < root_air_requirements_mm["driven"]:
            raise ValueError("periodic first-contact covers do not pay the actual driven-root floor")
        result["phase_endpoints_rad"] = [0.0, pitch]
        if (start_cell.source_pose != end_cell.source_pose or not start_cell.driver_phase_rad.contains(0)
                or not end_cell.driver_phase_rad.contains(pitch)
                or start_cover.cell != start_cell or end_cover.cell != end_cell
                or start_cover.angle_coordinate != "driven_material" or end_cover.angle_coordinate != "driven_material"):
            raise ValueError("periodic seam lacks bound same-source endpoint cells/material covers")
        inventory,roots,noncarrying = physical_patch_inventory(pair)
        for charts, proofs, cell, cover in ((start_charts, start_branch_proofs, start_cell, start_cover),
                                           (end_charts, end_branch_proofs, end_cell, end_cover)):
            if (len({c.name for c in charts}) != len(charts) or len(proofs) != len(charts)
                    or {p.chart_name for p in proofs} != {c.name for c in charts}
                    or any(p.cell != cell or p.unknown_domain != next(c.unknown_box for c in charts if c.name == p.chart_name)
                           for p in proofs)):
                raise ValueError("periodic seam lacks every actual full-cell branch/domain proof")
            if (len(cover.physical_patch_inventory) != len(inventory)
                    or set(cover.physical_patch_inventory) != set(inventory)
                    or len(cover.root_patch_ids) != len(roots) or set(cover.root_patch_ids) != set(roots)
                    or len(cover.noncarrying_patch_ids) != len(noncarrying)
                    or set(cover.noncarrying_patch_ids) != set(noncarrying)):
                raise ValueError("periodic first-contact cover omits actual physical teeth/root/cap material")
            refusal = cover.refusal(proofs)
            if refusal:
                raise ValueError(refusal)
        if start_cover.closing_driven_sense != end_cover.closing_driven_sense:
            raise ValueError("periodic first-contact covers have different physical closing senses")
        result["closing_driven_sense"] = start_cover.closing_driven_sense
        _periodic_source_relabel(pair, start_cell.source_pose, source_eccentricity_disks)
        start_keys = {}
        for chart in start_charts:
            key = (_seam_stratum_key(chart.driver_stratum, chart.driver_stratum.tooth),
                   _seam_stratum_key(chart.driven_stratum, chart.driven_stratum.tooth))
            if key in start_keys:
                raise ValueError("periodic seam duplicates a physical start stratum")
            start_keys[key] = chart
        pairs = []
        used = set()
        for end in end_charts:
            key = (_seam_stratum_key(end.driver_stratum, (end.driver_stratum.tooth + 1) % pair.driver.teeth),
                   _seam_stratum_key(end.driven_stratum, (end.driven_stratum.tooth - 1) % pair.driven.teeth))
            start = start_keys.get(key)
            if start is None or start.name in used:
                raise ValueError("periodic seam does not biject ALL actual physical strata")
            pairs.append((start, end))
            used.add(start.name)
        if len(used) != len(start_charts):
            raise ValueError("periodic seam leaves an unpaired possible first-contact stratum")
        source = start_cell.source_pose
        endpoints = (PhaseCell(Interval.point(0), source), PhaseCell(Interval.point(pitch), source))
        endpoint_proofs = []
        for charts, cell, cover in ((start_charts, endpoints[0], start_cover), (end_charts, endpoints[1], end_cover)):
            proofs = {chart.name: prove_branch_cell(chart, cell,
                       root_free_driven_components_rad=cover.root_free_driven_components_rad,
                       root_free_coordinate="driven_material") for chart in charts}
            if any(p.status != "PROVED" for p in proofs.values()):
                raise ValueError("fresh physical periodic endpoint root/centre proof is unresolved")
            endpoint_proofs.append(proofs)
        result["start_endpoint_branch_proofs"] = [p.record() for p in endpoint_proofs[0].values()]
        result["end_endpoint_branch_proofs"] = [p.record() for p in endpoint_proofs[1].values()]
        inventory,_,_ = physical_patch_inventory(pair)
        if (not isinstance(root_receipt, dict) or root_receipt.get("status") != "PROVED"
                or root_receipt.get("native_certificate") is not False
                or root_receipt.get("angle_coordinate") != "driven_material"
                or root_receipt.get("phase_cell_rad") != endpoints[1].driver_phase_rad.record()
                or root_receipt.get("same_source_pose") != source.record()
                or list(root_receipt.get("physical_driven_teeth", ())) != list(range(pair.driven.teeth))
                or set(root_receipt.get("physical_patch_inventory", ())) != set(inventory)
                or len(root_receipt.get("physical_patch_inventory", ())) != len(inventory)
                or not isinstance(root_receipt.get("root_sweep"), dict)
                or root_receipt["root_sweep"].get("status") != "resolved"
                or root_receipt.get("physical_required_root_air_mm", -1) < root_air_requirements_mm["driver"]
                or not isinstance(root_receipt.get("physical_root_air_lower_bound_mm"), (int, float))
                or not math.isfinite(root_receipt["physical_root_air_lower_bound_mm"])
                or root_receipt["physical_root_air_lower_bound_mm"] <= 0
                or root_receipt["physical_root_air_lower_bound_mm"] < root_air_requirements_mm["driver"]):
            raise ValueError("periodic seam lacks actual all-tooth/cap same-source endpoint root receipt")
        root_domain = _seam_interval(root_receipt["driven_angle_domain_rad"])
        root_components = tuple(_seam_interval(v) for v in root_receipt["root_free_driven_components_rad"])
        displacement, displacement_evidence = _periodicity_displacement_evidence(pair, source)
        if (root_receipt.get("material_scope") != "driver_root_material"
                or root_receipt["root_sweep"].get("material_scope") != "driver_root_material"
                or root_receipt.get("additional_geometry_error_mm",-1) < displacement):
            raise ValueError("periodic root proof does not pay the full joint-period displacement")
        reverse = driven_root_material_receipt
        if (not isinstance(reverse,dict) or reverse.get("proof_schema") != "finite-stock-directed-root-material/1"
                or reverse.get("status") != "PROVED" or reverse.get("native_certificate") is not False
                or reverse.get("root_owner") != "driven" or reverse.get("other_material_owner") != "driver"
                or reverse.get("phase_cell_rad") != endpoints[1].driver_phase_rad.record()
                or reverse.get("same_source_pose") != source.record()
                or reverse.get("approach_driven_phase_rad") != root_domain.record()
                or reverse.get("required_root_air_mm") != root_air_requirements_mm["driven"]
                or not isinstance(reverse.get("root_air_lower_mm"),(float,int))
                or not math.isfinite(reverse["root_air_lower_mm"]) or reverse["root_air_lower_mm"] <= 0
                or reverse["root_air_lower_mm"] < root_air_requirements_mm["driven"]
                or reverse.get("material_sweep",{}).get("status") != "PROVED"
                or reverse.get("material_sweep",{}).get("additional_geometry_error_mm",-1) < displacement):
            raise ValueError("periodic seam lacks the complete directed driven-root material/containment proof")
        result["periodicity_displacement_evidence"] = displacement_evidence
        result["joint_period_tooth_steps"] = math.lcm(pair.driver.teeth,pair.driven.teeth)
        minima = ({m.chart_name: m for m in start_cover.chart_minimum_bounds},
                  {m.chart_name: m for m in end_cover.chart_minimum_bounds})
        maximum = 0.0
        for start, end in pairs:
            a, b = endpoint_proofs[0][start.name], endpoint_proofs[1][end.name]
            mapped_material = a.driven_material_phase_rad - mate_pitch
            if (not root_domain.contains(mapped_material) or not root_domain.contains(b.driven_material_phase_rad)
                    or not any(c.contains(mapped_material) and c.contains(b.driven_material_phase_rad) for c in root_components)):
                raise ValueError("periodic mapped material roots leave one actual finite root-free component")
            bounds = (minima[0][start.name], minima[1][end.name])
            geometry, arc = Interval.point(0), Interval.point(0)
            for proof, minimum in zip((a, b), bounds):
                padding = minimum.objective_gradient_padding_mm
                required = (Interval.point(proof.geometry_error_bound_mm) + Interval.point(displacement)).upper
                if padding is None or not math.isfinite(padding) or padding < required:
                    raise ValueError("periodic Lipschitz receipt does not bind full geometry-plus-arc padding")
                geometry += branch_geometry_error_rad(proof,minimum,additional_geometry_error_mm=0.0)
                arc += Interval.point(displacement) * minimum.objective_gradient_magnitude_upper_per_mm / minimum.approach_derivative_magnitude_lower
            record = correlated_periodic_branch_difference(a, b, pair, source_eccentricity_disks=source_eccentricity_disks)
            difference = _seam_interval(record["same_pose_driven_root_difference_rad"])
            jump = (Interval.point(driven_pitch_radius_mm) * (Interval.point(difference.magnitude) + geometry + arc)).upper
            record.update({"start_chart": start.name, "end_chart": end.name,
                           "physical_geometry_error_payment_rad": geometry.record(),
                           "periodicity_displacement_upper_mm": displacement,
                           "periodicity_error_payment_rad": arc.record(),
                           "pitch_displacement_jump_upper_mm": jump,
                           "mapped_start_material_root_rad": mapped_material.record(),
                           "end_material_root_rad": b.driven_material_phase_rad.record()})
            result["chart_pairs"].append(record)
            result["source_relabel"] = record["source_relabel"]
            maximum = max(maximum, jump)
        result["pitch_displacement_jump_upper_mm"] = maximum
        result["driven_pitch_radius_mm"] = driven_pitch_radius_mm
        result["maximum_jump_mm"] = maximum_jump_mm
        if maximum > maximum_jump_mm:
            raise ValueError("same-source periodic first-contact envelope exceeds the paid .005 limit")
        result.update({"status": "PROVED", "continuous": True,
                       "reason": "bijective actual supported min/max envelope; same-source disk relabel and paid periodicity",
                       "envelope_bound_definition": "max paired branch error bounds both min and max of all possible first roots"})
    except (ArithmeticError, ValueError, KeyError, TypeError) as exc:
        result["reason"] = f"periodic seam proof unresolved: {exc}"
    return result
