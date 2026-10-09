"""Finite form-cutter geometry, in mm and radians; no CAD/config dependencies.

The master is a GAP about +X. Translation moves the tool, not an ideal-N
involute. Native equations use radians and normalized t; only their output
coordinates are scaled. ``contains_material`` has the same gap datum. The
additive sector instead centres a tooth on +X (gaps at +/- half a pitch).

A normal tool point v=(X, cos(beta)*Y) starts at z=-sin(beta)*Y.
A right-hand screw R(theta), z=w*theta reaches z=0 at theta=sin(beta)*Y/w.
Thus q=R(a*Y)v, a=sin(beta)/w, and
 det(q,q')=cos(beta)*(X*Y'-Y*X')+a*|v|^2*Y'.
This also fixes the sign for the 13-degree RH crank; reversing beta reverses
lead and the axial normal, but not this transverse section.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field


_STOCK_RANGES = ((8, 12, 13), (7, 14, 16), (6, 17, 20), (5, 21, 25),
                 (4, 26, 34), (3, 35, 54), (2, 55, 134), (1, 135, None))
_EPS = 2.220446049250313e-16


def _positive(value: float, name: str) -> None:
    if not math.isfinite(value) or value <= 0:
        raise ValueError(f"{name} must be finite and positive")


def _rotate(x: float, y: float, angle: float) -> tuple[float, float]:
    c, s = math.cos(angle), math.sin(angle)
    return c * x - s * y, s * x + c * y


def _normal_transform(X: float, Y: float, c: float, a: float) -> tuple[float, float]:
    return _rotate(X, c * Y, a * Y)


def _normal_transform_derivative(
    X: float, Y: float, dx: float, dy: float, c: float, a: float
) -> tuple[float, float]:
    return _rotate(dx - a * dy * c * Y, c * dy + a * dy * X, a * Y)


def _bisect(function, lo: float, hi: float) -> float:
    flo, fhi = function(lo), function(hi)
    if flo == 0:
        return lo
    if fhi == 0:
        return hi
    if flo * fhi > 0:
        raise ValueError("supported interval does not bracket the requested intersection")
    for _ in range(64):
        mid = (lo + hi) / 2
        if mid == lo or mid == hi:
            break
        fm = function(mid)
        if (fm > 0) == (flo > 0):
            lo, flo = mid, fm
        else:
            hi = mid
    return (lo + hi) / 2


class _TemplateGeometry:
    @property
    def module_mm(self) -> float:
        return 25.4 / self.diametral_pitch

    @property
    def pitch_radius_mm(self) -> float:
        return self.reference_teeth * self.module_mm / 2

    @property
    def base_radius_mm(self) -> float:
        return self.pitch_radius_mm * math.cos(math.radians(self.pressure_angle_deg))

    @property
    def flank_parameter_min(self) -> float:
        return math.sqrt(max(0.0, (self.root_radius_mm / self.base_radius_mm) ** 2 - 1))

    @property
    def flank_parameter_max(self) -> float:
        return math.sqrt((self.tip_radius_mm / self.base_radius_mm) ** 2 - 1)

    @property
    def half_space_base_angle_rad(self) -> float:
        pa = math.radians(self.pressure_angle_deg)
        return (math.pi / self.reference_teeth
                - self.pitch_tooth_thickness_mm / (2 * self.pitch_radius_mm)
                - (math.tan(pa) - pa))

    @property
    def root_half_angle_rad(self) -> float:
        u = self.flank_parameter_min
        return self.half_space_base_angle_rad + u - math.atan(u)

    def flank_point(self, u: float, side: int = 1) -> tuple[float, float]:
        """Untranslated reference flank; the one master-curve evaluator."""
        if side not in {-1, 1}:
            raise ValueError("flank side must be -1 or +1")
        if not self.flank_parameter_min <= u <= self.flank_parameter_max:
            raise ValueError("flank parameter exceeds finite reference support")
        rb, z = self.base_radius_mm, self.half_space_base_angle_rad + u
        return rb * (math.cos(z) + u * math.sin(z)), side * rb * (math.sin(z) - u * math.cos(z))

    def root_point(self, angle_rad: float) -> tuple[float, float]:
        if not -self.root_half_angle_rad <= angle_rad <= self.root_half_angle_rad:
            raise ValueError("root angle exceeds supported closing arc")
        return self.root_radius_mm * math.cos(angle_rad), self.root_radius_mm * math.sin(angle_rad)

    def _validate(self) -> None:
        _positive(self.diametral_pitch, "diametral pitch")
        if not math.isfinite(self.pressure_angle_deg) or not 0 < self.pressure_angle_deg < 45:
            raise ValueError("pressure angle must be between 0 and 45 degrees")
        _positive(self.root_radius_mm, "reference root radius")
        _positive(self.tip_radius_mm, "finite reference tip radius")
        if self.tip_radius_mm <= max(self.root_radius_mm, self.base_radius_mm):
            raise ValueError("finite tip must lie above reference root and base")
        if not 0 < self.pitch_tooth_thickness_mm < math.pi * self.module_mm:
            raise ValueError("reference pitch thickness must leave positive tooth and gap")
        if self.root_half_angle_rad <= 0:
            raise ValueError("reference flanks cross before the root")
        u = self.flank_parameter_max
        if self.half_space_base_angle_rad + u - math.atan(u) >= math.pi / self.reference_teeth:
            raise ValueError("reference finite tip has no material land")


@dataclass(frozen=True)
class CutterTemplate(_TemplateGeometry):
    """Stock-range master at its LOWEST supported tooth count."""

    reference_teeth: int
    diametral_pitch: float
    pressure_angle_deg: float

    def __post_init__(self) -> None:
        if type(self.reference_teeth) is not int or self.reference_teeth not in {
            row[1] for row in _STOCK_RANGES
        }:
            raise ValueError("stock reference must be a lowest range count: 12,14,17,21,26,35,55,135")
        self._validate()

    @property
    def root_radius_mm(self) -> float:
        return self.pitch_radius_mm - 1.25 * self.module_mm

    @property
    def tip_radius_mm(self) -> float:
        return self.pitch_radius_mm + self.module_mm

    @property
    def pitch_tooth_thickness_mm(self) -> float:
        return math.pi * self.module_mm / 2

    @property
    def cutter_number(self) -> int:
        return next(row[0] for row in _STOCK_RANGES if row[1] == self.reference_teeth)

    @property
    def teeth_range(self) -> tuple[int, int | None]:
        return next(row[1:] for row in _STOCK_RANGES if row[1] == self.reference_teeth)

    @property
    def name(self) -> str:
        return f"STOCK #{self.cutter_number} / {self.reference_teeth}T REFERENCE"

    @property
    def source(self) -> str:
        return "Lowest-count finite full-depth stock form; radial continuation below base"


@dataclass(frozen=True)
class CustomSixCutter(_TemplateGeometry):
    """Explicit finite DT6-FORM1 ground tool, never a stock-range selection."""

    diametral_pitch: float
    pressure_angle_deg: float
    root_radius_mm: float
    tip_radius_mm: float
    pitch_tooth_thickness_mm: float
    name: str
    source: str

    @property
    def reference_teeth(self) -> int:
        return 6

    @property
    def cutter_number(self) -> None:
        return None

    @property
    def teeth_range(self) -> tuple[int, int]:
        return 6, 6

    def __post_init__(self) -> None:
        if not self.name.strip() or not self.source.strip():
            raise ValueError("custom tool requires explicit name and source")
        self._validate()


def template_for_teeth(selection_teeth: float, dp: float, pa_deg: float) -> CutterTemplate:
    """Fractional virtual counts select ranges; they NEVER set pattern count.

    Ranges are continuous [lowest,next-lowest), including 13.5 in #8. #1
    has no upper selection limit, but its 135T master still has a finite tip.
    """
    if not math.isfinite(selection_teeth) or selection_teeth < 12:
        raise ValueError("stock cutters start at 12 teeth; six requires an explicit custom tool")
    for _, lo, _ in reversed(_STOCK_RANGES):
        if selection_teeth >= lo:
            return CutterTemplate(lo, dp, pa_deg)
    raise AssertionError("unreachable stock range")


def _supported_tangent_span_mm(
    teeth: int,
    template: CutterTemplate | CustomSixCutter,
    translation_mm: float,
    helix_angle_deg: float,
    teeth_spanned: int,
    parameter_min: float,
    parameter_max: float,
    normal_plane: bool,
) -> float:
    """One canonical span-contact calculation on explicit FINITE bounds.

    These are curve-domain bounds, not an implicit manufactured blank.
    A real profile passes its actual OD-clipped interval; inverse design
    passes the template's complete finite interval before sizing its OD.
    """
    if type(teeth_spanned) is not int or not 1 <= teeth_spanned < teeth:
        raise ValueError("span count must be a positive physical integer below tooth count")
    h = math.pi * teeth_spanned / teeth
    if helix_angle_deg == 0:
        u = h - template.half_space_base_angle_rad
        if not parameter_min <= u <= parameter_max:
            raise ValueError("span tangent contact leaves actual finite flank")
        return 2 * template.base_radius_mm * u + 2 * translation_mm * math.sin(h)
    beta = math.radians(helix_angle_deg)
    c = math.cos(beta)
    pitch = teeth * template.module_mm / (2 * c)
    w = pitch / math.tan(beta)
    a = math.sin(beta) * math.tan(beta) / pitch

    def tangent(u):
        x, y = template.flank_point(u)
        z = template.half_space_base_angle_rad + u
        return _normal_transform_derivative(
            x + translation_mm, y, math.cos(z), math.sin(z), c, a
        )

    u = _bisect(
        lambda z: math.atan2(*reversed(tangent(z))) - h,
        parameter_min,
        parameter_max,
    )
    xref, yref = template.flank_point(u)
    x, y = _normal_transform(xref + translation_mm, yref, c, a)
    span = 2 * (x * math.sin(h) - y * math.cos(h))
    if not normal_plane:
        return span
    dx, dy = tangent(u)
    nz = (x * dx + y * dy) / (math.hypot(dx, dy) * w)
    return span / math.sqrt(1 + nz * nz)


@dataclass(frozen=True)
class NativeSegment:
    """Exact normalized curve; strings scaled, evaluators and bounds in mm.

    ``speed_bound_mm`` bounds |dq/dt| and ``second_derivative_bound_mm``
    bounds |d2q/dt2|. A chord over h has Hausdorff error <= M2*h*h/8.
    """

    name: str
    kind: str
    x: str
    y: str
    _profile: object = field(repr=False, compare=False)
    _shape: str = field(repr=False)
    _a: float = field(repr=False)
    _b: float = field(repr=False)
    _side: int = field(default=1, repr=False)
    _rotate_rad: float = field(default=0.0, repr=False)
    _radius: float = field(default=0.0, repr=False)
    _line: tuple = field(default=(), repr=False)

    def _reference(self, t: float) -> tuple[float, float, float, float]:
        p = self._profile
        z = self._a if t == 0 else self._b if t == 1 else self._a + (self._b - self._a) * t
        step = self._b - self._a
        if self._shape == "flank":
            x, y = p._reference_flank(z, self._side)
            k = p.template.half_space_base_angle_rad + z
            rb = p.template.base_radius_mm
            return x + p.radial_translation_mm, y, rb * z * math.cos(k) * step, self._side * rb * z * math.sin(k) * step
        if self._shape == "radial":
            k = p.template.half_space_base_angle_rad
            return p.radial_translation_mm + z * math.cos(k), self._side * z * math.sin(k), math.cos(k) * step, self._side * math.sin(k) * step
        r = p.template.root_radius_mm
        return p.radial_translation_mm + r * math.cos(z), r * math.sin(z), -r * math.sin(z) * step, r * math.cos(z) * step

    def point(self, t: float) -> tuple[float, float]:
        if not 0 <= t <= 1:
            raise ValueError("native curve parameter must be in [0,1]")
        if self._shape == "circle":
            z = self._a + (self._b - self._a) * t
            q = self._radius * math.cos(z), self._radius * math.sin(z)
        elif self._shape == "line":
            x0, y0, x1, y1 = self._line
            q = x0 + (x1 - x0) * t, y0 + (y1 - y0) * t
        else:
            x, y, _, _ = self._reference(t)
            q = self._profile._transform(x, y)
        return _rotate(*q, self._rotate_rad)

    def derivative(self, t: float) -> tuple[float, float]:
        if not 0 <= t <= 1:
            raise ValueError("native curve parameter must be in [0,1]")
        if self._shape == "circle":
            z = self._a + (self._b - self._a) * t
            step = self._b - self._a
            q = -self._radius * math.sin(z) * step, self._radius * math.cos(z) * step
        elif self._shape == "line":
            x0, y0, x1, y1 = self._line
            q = x1 - x0, y1 - y0
        else:
            q = self._profile._transform_derivative(*self._reference(t))
        return _rotate(*q, self._rotate_rad)

    @property
    def start_mm(self) -> tuple[float, float]:
        return self.point(0)

    @property
    def end_mm(self) -> tuple[float, float]:
        return self.point(1)

    def _reference_bounds(self) -> tuple[float, ...]:
        h = abs(self._b - self._a)
        if self._shape == "line":
            return (max(math.hypot(*self._line[:2]), math.hypot(*self._line[2:])),
                    math.hypot(self._line[2] - self._line[0], self._line[3] - self._line[1]), 0, 0, 0, 0)
        if self._shape == "circle":
            return tuple(self._radius * h ** n for n in range(6))
        p = self._profile
        if self._shape == "root":
            r = p.template.root_radius_mm
            return (abs(p.radial_translation_mm) + r,) + tuple(r * h ** n for n in range(1, 6))
        if self._shape == "radial":
            return abs(p.radial_translation_mm) + max(self._a, self._b), h, 0, 0, 0, 0
        u = max(self._a, self._b)
        rb = p.template.base_radius_mm
        return (abs(p.radial_translation_mm) + rb * math.sqrt(1 + u * u),) + tuple(
            rb * math.sqrt(u * u + (n - 1) ** 2) * h ** n for n in range(1, 6)
        )

    @property
    def speed_bound_mm(self) -> float:
        v = self._reference_bounds()
        a = 0 if self._shape in {"line", "circle"} else abs(self._profile._helix_a)
        return v[1] * (1 + a * v[0])

    @property
    def second_derivative_bound_mm(self) -> float:
        v = self._reference_bounds()
        a = 0 if self._shape in {"line", "circle"} else abs(self._profile._helix_a)
        return v[2] + 2 * a * v[1] ** 2 + a * v[2] * v[0] + a * a * v[1] ** 2 * v[0]

    def _green_fourth_bound(self) -> float:
        v = self._reference_bounds()
        a = abs(self._profile._helix_a)
        # Leibniz, det(v,v') + a*Y'*dot(v,v); norms dominate components.
        result = sum(math.comb(4, j) * v[j] * v[5 - j] for j in range(5))
        for j in range(5):
            result += a * math.comb(4, j) * v[j + 1] * sum(
                math.comb(4 - j, k) * v[k] * v[4 - j - k] for k in range(5 - j)
            )
        return result

    def _green_integral(self) -> tuple[float, float]:
        if self._shape == "circle":
            return self._radius ** 2 * (self._b - self._a), 0.0
        if self._shape == "line":
            x0, y0, x1, y1 = self._line
            return x0 * y1 - y0 * x1, 0.0
        p, a, b = self._profile, self._a, self._b
        if p.helix_angle_deg == 0:
            T = p.radial_translation_mm
            if self._shape == "root":
                r = p.template.root_radius_mm
                value = r * r * (b - a) + T * r * (math.sin(b) - math.sin(a))
            elif self._shape == "radial":
                value = self._side * T * math.sin(p.template.half_space_base_angle_rad) * (b - a)
            else:
                rb, k = p.template.base_radius_mm, p.template.half_space_base_angle_rad
                def primitive(u):
                    return rb * rb * u ** 3 / 3 + T * rb * (-u * math.cos(k + u) + math.sin(k + u))
                value = self._side * (primitive(b) - primitive(a))
            return value, 64 * _EPS * self._reference_bounds()[0] ** 2
        # Composite Simpson with an analytic FOURTH derivative bound, not
        # order-agreement as a certificate. Bound includes conservative sums.
        tolerance = 1e-10
        bound = self._green_fourth_bound()
        n = max(2, int(math.ceil((bound / (180 * tolerance)) ** 0.25)))
        n += n % 2
        terms = []
        for i in range(n + 1):
            X, Y, dx, dy = self._reference(i / n)
            c, ahelix = p._helix_cos, p._helix_a
            value = c * (X * dy - Y * dx) + ahelix * (X * X + c * c * Y * Y) * dy
            terms.append(value * (1 if i in {0, n} else 4 if i % 2 else 2))
        value = math.fsum(terms) / (3 * n)
        v = self._reference_bounds()
        arithmetic = 128 * _EPS * (v[0] * v[1] + abs(p._helix_a) * v[0] ** 2 * v[1])
        return value, bound / (180 * n ** 4) + arithmetic


@dataclass(frozen=True)
class StockFormProfile:
    """Physical integer tooth pattern of one translated, finite cutter."""

    teeth: int
    template: CutterTemplate | CustomSixCutter
    blank_radius_mm: float
    radial_translation_mm: float
    helix_angle_deg: float = 0.0
    _tip_shape: str = field(init=False, repr=False)
    _tip_parameter: float = field(init=False, repr=False)
    _root_min: float = field(init=False, repr=False)
    _root_max: float = field(init=False, repr=False)
    _area: float = field(init=False, repr=False)
    _area_error: float = field(init=False, repr=False)

    def __post_init__(self) -> None:
        if type(self.teeth) is not int or self.teeth < 3:
            raise ValueError("physical pattern teeth must be an integer >=3")
        if not isinstance(self.template, (CutterTemplate, CustomSixCutter)):
            raise TypeError("template must be the declared stock or explicit custom cutter")
        _positive(self.blank_radius_mm, "blank radius")
        if not math.isfinite(self.radial_translation_mm):
            raise ValueError("radial translation must be finite")
        if not math.isfinite(self.helix_angle_deg) or abs(self.helix_angle_deg) >= 45:
            raise ValueError("helix angle must be finite and strictly between -45 and 45 degrees")
        # A positive-X, nonfolding tool branch is required. In particular no
        # cutter arc can pass through the actual axis or reverse the cut.
        if self.radial_translation_mm <= -min(self.template.root_radius_mm, self.template.base_radius_mm):
            raise ValueError("translated root intersects the axis or folds its supported branch")
        angles = [0.0, self.root_half_angle_rad]
        sb2 = math.sin(math.radians(self.helix_angle_deg)) ** 2
        if sb2:
            z = -self.radial_translation_mm / (self.template.root_radius_mm * sb2)
            if math.cos(self.root_half_angle_rad) < z < 1:
                angles.append(math.acos(z))
        radii = [math.hypot(*self.root_point(angle)) for angle in angles]
        object.__setattr__(self, "_root_min", min(radii))
        object.__setattr__(self, "_root_max", max(radii))
        if self.blank_radius_mm <= self.root_radius_max_mm + self.geometry_error_bound_mm:
            raise ValueError("blank must lie above the entire actual root envelope")
        support = self.support_radius_max_mm
        if self.blank_radius_mm > support + self.geometry_error_bound_mm:
            raise ValueError("blank tip exceeds FINITE cutter support; upper continuation is forbidden")
        if abs(self._helix_a) * self.blank_radius_mm / self._helix_cos >= 1:
            raise ValueError("normal sweep folds and has no unique transverse inverse")
        below_base = self.template.root_radius_mm < self.template.base_radius_mm
        base = math.hypot(*self.radial_point(self.template.base_radius_mm)) if below_base else None
        if base is not None and self.blank_radius_mm < base:
            shape = "radial"
            parameter = _bisect(lambda r: math.hypot(*self.radial_point(r)) - self.blank_radius_mm,
                                self.template.root_radius_mm, self.template.base_radius_mm)
        else:
            shape = "flank"
            parameter = _bisect(lambda u: math.hypot(*self.flank_point(u)) - min(self.blank_radius_mm, support),
                                self.template.flank_parameter_min, self.template.flank_parameter_max)
        object.__setattr__(self, "_tip_shape", shape)
        object.__setattr__(self, "_tip_parameter", parameter)
        # Root-lobe angular extent can exceed tip width after translation.
        root_angle = math.atan2(*reversed(self.root_point(self.root_half_angle_rad)))
        if max(root_angle, self.tip_half_angle_rad) >= math.pi / self.teeth:
            raise ValueError("adjacent physical gaps intersect or leave no material land")
        integrals = [segment._green_integral() for segment in self.gap_segments()]
        area = math.fsum(item[0] for item in integrals) / 2
        error = math.fsum(item[1] for item in integrals) / 2 + 128 * _EPS * self.blank_radius_mm ** 2
        if area <= error:
            raise ValueError("gap has no positive, resolved area")
        object.__setattr__(self, "_area", area)
        object.__setattr__(self, "_area_error", error)

    @property
    def _helix_cos(self) -> float:
        return math.cos(math.radians(self.helix_angle_deg))

    @property
    def _helix_a(self) -> float:
        beta = math.radians(self.helix_angle_deg)
        return math.sin(beta) * math.tan(beta) / self.pitch_radius_mm

    @property
    def lead_per_radian_mm(self) -> float:
        beta = math.radians(self.helix_angle_deg)
        return math.inf if beta == 0 else self.pitch_radius_mm / math.tan(beta)

    @property
    def pitch_radius_mm(self) -> float:
        return self.teeth * self.template.module_mm / (2 * self._helix_cos)

    @property
    def angular_pitch_rad(self) -> float:
        return 2 * math.pi / self.teeth

    @property
    def geometry_error_bound_mm(self) -> float:
        return 256 * _EPS * max(1.0, self.blank_radius_mm, abs(self.radial_translation_mm), self.template.tip_radius_mm)

    def _transform(self, X: float, Y: float) -> tuple[float, float]:
        return _normal_transform(X, Y, self._helix_cos, self._helix_a)

    def _transform_derivative(self, X: float, Y: float, dx: float, dy: float) -> tuple[float, float]:
        return _normal_transform_derivative(X, Y, dx, dy, self._helix_cos, self._helix_a)

    def normal_to_transverse(self, x_ref: float, y_ref: float) -> tuple[float, float]:
        return self._transform(x_ref + self.radial_translation_mm, y_ref)

    def transverse_to_normal(self, x_mm: float, y_mm: float) -> tuple[float, float]:
        r, theta = math.hypot(x_mm, y_mm), math.atan2(y_mm, x_mm)
        b = self._helix_a * r / self._helix_cos
        if abs(b) >= 1:
            raise ValueError("point lies outside the uniquely invertible normal sweep")
        phi = theta if b == 0 else _bisect(lambda z: z + b * math.sin(z) - theta, theta - abs(b), theta + abs(b))
        return r * math.cos(phi) - self.radial_translation_mm, r * math.sin(phi) / self._helix_cos

    def _reference_flank(self, u: float, side: int = 1) -> tuple[float, float]:
        return self.template.flank_point(u, side)

    @property
    def flank_parameter_min(self) -> float:
        return self.template.flank_parameter_min

    @property
    def flank_parameter_max(self) -> float:
        return self._tip_parameter if self._tip_shape == "flank" else self.flank_parameter_min

    def flank_point(self, u: float, side: int = 1) -> tuple[float, float]:
        return self.normal_to_transverse(*self._reference_flank(u, side))

    def flank_derivative(self, u: float, side: int = 1) -> tuple[float, float]:
        x, y = self._reference_flank(u, side)
        rb, z = self.template.base_radius_mm, self.template.half_space_base_angle_rad + u
        return self._transform_derivative(x + self.radial_translation_mm, y, rb * u * math.cos(z), side * rb * u * math.sin(z))

    def _flank_tangent(self, u: float, side: int = 1) -> tuple[float, float]:
        # At u=0 the involute derivative vanishes, but its limiting tangent
        # and normal exist; divide out the positive rb*u before transforming.
        x, y = self._reference_flank(u, side)
        z = self.template.half_space_base_angle_rad + u
        return self._transform_derivative(x + self.radial_translation_mm, y, math.cos(z), side * math.sin(z))

    def flank_normal(self, u: float, side: int = 1) -> tuple[float, float]:
        dx, dy = self._flank_tangent(u, side)
        length = math.hypot(dx, dy)
        return side * dy / length, -side * dx / length

    def radial_point(self, radius_mm: float, side: int = 1) -> tuple[float, float]:
        if side not in {-1, 1}:
            raise ValueError("radial side must be -1 or +1")
        if not self.template.root_radius_mm <= radius_mm <= self.template.base_radius_mm:
            raise ValueError("radial parameter exceeds real below-base connector")
        k = self.template.half_space_base_angle_rad
        return self.normal_to_transverse(radius_mm * math.cos(k), side * radius_mm * math.sin(k))

    def radial_derivative(self, radius_mm: float, side: int = 1) -> tuple[float, float]:
        self.radial_point(radius_mm, side)
        k = self.template.half_space_base_angle_rad
        return self._transform_derivative(self.radial_translation_mm + radius_mm * math.cos(k), side * radius_mm * math.sin(k), math.cos(k), side * math.sin(k))

    @property
    def root_half_angle_rad(self) -> float:
        return self.template.root_half_angle_rad

    def root_point(self, angle_rad: float) -> tuple[float, float]:
        return self.normal_to_transverse(*self.template.root_point(angle_rad))

    def root_derivative(self, angle_rad: float) -> tuple[float, float]:
        self.template.root_point(angle_rad)
        r = self.template.root_radius_mm
        return self._transform_derivative(self.radial_translation_mm + r * math.cos(angle_rad), r * math.sin(angle_rad), -r * math.sin(angle_rad), r * math.cos(angle_rad))

    def tip_point(self, angle_rad: float) -> tuple[float, float]:
        return self.blank_radius_mm * math.cos(angle_rad), self.blank_radius_mm * math.sin(angle_rad)

    def tip_derivative(self, angle_rad: float) -> tuple[float, float]:
        return -self.blank_radius_mm * math.sin(angle_rad), self.blank_radius_mm * math.cos(angle_rad)

    @property
    def root_radius_min_mm(self) -> float:
        return self._root_min

    @property
    def root_radius_max_mm(self) -> float:
        return self._root_max

    @property
    def support_radius_max_mm(self) -> float:
        return math.hypot(*self.flank_point(self.template.flank_parameter_max))

    @property
    def tip_half_angle_rad(self) -> float:
        q = self.flank_point(self._tip_parameter) if self._tip_shape == "flank" else self.radial_point(self._tip_parameter)
        return math.atan2(q[1], q[0])

    @property
    def tip_land_mm(self) -> float:
        return self.blank_radius_mm * (self.angular_pitch_rad - 2 * self.tip_half_angle_rad)

    def require_tip_land(self, minimum_mm: float) -> None:
        if not math.isfinite(minimum_mm) or minimum_mm < 0:
            raise ValueError("minimum tip land must be finite and nonnegative")
        if self.tip_land_mm - 2 * self.geometry_error_bound_mm < minimum_mm:
            raise ValueError("actual finite-form tip land is below caller minimum")

    @property
    def plunge_mm(self) -> float:
        """Radial plunge of the NORMAL tool at Y=0 (also transverse bisector)."""
        return self.blank_radius_mm - (self.radial_translation_mm + self.template.root_radius_mm)

    def _gap_angle_at_radius(self, radius: float) -> float:
        if radius <= self.root_radius_max_mm or radius > self.support_radius_max_mm:
            raise ValueError("inspection circle is outside whole-root/finite-flank support")
        rb = self.template.base_radius_mm
        if self.template.root_radius_mm < rb and radius < math.hypot(*self.radial_point(rb)):
            r = _bisect(lambda z: math.hypot(*self.radial_point(z)) - radius, self.template.root_radius_mm, rb)
            q = self.radial_point(r)
        else:
            u = _bisect(lambda z: math.hypot(*self.flank_point(z)) - radius, self.template.flank_parameter_min, self.template.flank_parameter_max)
            q = self.flank_point(u)
        return math.atan2(q[1], q[0])

    @property
    def pitch_tooth_thickness_mm(self) -> float:
        return self.pitch_radius_mm * (self.angular_pitch_rad - 2 * self._gap_angle_at_radius(self.pitch_radius_mm))

    @property
    def gap_area_mm2(self) -> float:
        return self._area

    @property
    def gap_area_error_bound_mm2(self) -> float:
        return self._area_error

    def contains_material(self, x_mm: float, y_mm: float, rotate_rad: float = 0.0) -> bool:
        """Analytic periodic gap membership, including off-centre floor lobes.

        Invert the screw section then test the actual reference arc/radial/
        involute, rather than using a polygon or an ideal actual-N notch.
        Boundary points belong to the closed material body.
        """
        if not all(math.isfinite(z) for z in (x_mm, y_mm, rotate_rad)):
            raise ValueError("material query coordinates and phase must be finite")
        radius = math.hypot(x_mm, y_mm)
        eps = self.geometry_error_bound_mm
        if radius > self.blank_radius_mm + eps:
            return False
        if radius < self.root_radius_min_mm - eps:
            return True
        angle = (math.atan2(y_mm, x_mm) - rotate_rad + self.angular_pitch_rad / 2) % self.angular_pitch_rad - self.angular_pitch_rad / 2
        x, y = self.transverse_to_normal(radius * math.cos(angle), radius * math.sin(angle))
        rref = math.hypot(x, y)
        if rref <= self.template.root_radius_mm + eps:
            return True
        if x <= 0:
            return True
        if rref < self.template.base_radius_mm:
            width = self.template.half_space_base_angle_rad
        else:
            u = min(self.template.flank_parameter_max, math.sqrt(max(0.0, (rref / self.template.base_radius_mm) ** 2 - 1)))
            width = self.template.half_space_base_angle_rad + u - math.atan(u)
        return abs(math.atan2(y, x)) >= width - eps / max(rref, eps)

    def tangent_span_mm(self, teeth_spanned: int, normal_plane: bool = True) -> float:
        """Parallel tangent-plane separation on the ACTUAL manufactured flanks.

        For helix, contact tangent is transformed before solving its angle;
        the 3D screw normal is (ny,-nx,-n2.Jq/w), not pitch-helix cosine.
        """
        if self._tip_shape != "flank":
            raise ValueError("span has no supported involute tangent")
        return _supported_tangent_span_mm(
            self.teeth, self.template, self.radial_translation_mm, self.helix_angle_deg,
            teeth_spanned, self.flank_parameter_min, self.flank_parameter_max, normal_plane,
        )

    def _segment(self, name, kind, shape, a, b, *, side=1, rotation=0.0, scale=1.0, radius=0.0, line=()) -> NativeSegment:
        _positive(scale, "unit scale")
        z = f"({a:.17g}+({b - a:.17g})*t)"
        if shape == "circle":
            x, y = f"{radius:.17g}*cos({z})", f"{radius:.17g}*sin({z})"
        elif shape == "line":
            x0, y0, x1, y1 = line
            x, y = f"({x0:.17g}+({x1-x0:.17g})*t)", f"({y0:.17g}+({y1-y0:.17g})*t)"
        else:
            T = f"({self.radial_translation_mm:.17g})"
            if shape == "root":
                r = f"({self.template.root_radius_mm:.17g})"
                X, Y = f"({T}+{r}*cos({z}))", f"({r}*sin({z}))"
            elif shape == "radial":
                k = f"({self.template.half_space_base_angle_rad:.17g})"
                X, Y = f"({T}+{z}*cos({k}))", f"({side}*{z}*sin({k}))"
            else:
                rb = f"({self.template.base_radius_mm:.17g})"
                phase = f"({self.template.half_space_base_angle_rad:.17g}+{z})"
                X = f"({T}+{rb}*(cos({phase})+{z}*sin({phase})))"
                Y = f"({side}*{rb}*(sin({phase})-{z}*cos({phase})))"
            if self.helix_angle_deg:
                c, delta = f"({self._helix_cos:.17g})", f"(({self._helix_a:.17g})*{Y})"
                x, y = f"({X}*cos({delta})-{c}*{Y}*sin({delta}))", f"({X}*sin({delta})+{c}*{Y}*cos({delta}))"
            else:
                x, y = X, Y
        if rotation:
            c, s = math.cos(rotation), math.sin(rotation)
            x, y = f"(({c:.17g})*({x})-({s:.17g})*({y}))", f"(({s:.17g})*({x})+({c:.17g})*({y}))"
        return NativeSegment(name, kind, f"({scale:.17g})*({x})", f"({scale:.17g})*({y})", self, shape, a, b, side, rotation, radius, line)

    def _branch_segments(self, side, outward, *, scale=1.0, rotation=0.0):
        rb, root = self.template.base_radius_mm, self.template.root_radius_mm
        pieces = []
        label = "Upper" if side == 1 else "Lower"
        if root < rb:
            end = self._tip_parameter if self._tip_shape == "radial" else rb
            if end > root:
                pieces.append(self._segment(f"{label}BelowBase", "radial", "radial", root, end, side=side, scale=scale, rotation=rotation))
        if self._tip_shape == "flank" and self._tip_parameter > self.flank_parameter_min:
            pieces.append(self._segment(f"{label}FiniteFlank", "flank", "flank", self.flank_parameter_min, self._tip_parameter, side=side, scale=scale, rotation=rotation))
        if outward:
            return pieces
        return [self._segment(s.name, s.kind, s._shape, s._b, s._a, side=side, scale=scale, rotation=rotation) for s in reversed(pieces)]

    def gap_segments(self, unit_scale: float = 1.0) -> tuple[NativeSegment, ...]:
        """Closed, counter-clockwise IN-BLANK gap boundary."""
        alpha, tip = self.root_half_angle_rad, self.tip_half_angle_rad
        return tuple([
            self._segment("RootArc", "root_arc", "root", alpha, -alpha, scale=unit_scale),
            *self._branch_segments(-1, True, scale=unit_scale),
            self._segment("TipArc", "tip_arc", "circle", -tip, tip, scale=unit_scale, radius=self.blank_radius_mm),
            *self._branch_segments(1, False, scale=unit_scale),
        ])

    def native_segments(self, unit_scale: float = 1 / 25.4, clearance_radius_mm: float | None = None) -> tuple[NativeSegment, ...]:
        """Exact cut loop; closing rays/arc lie strictly outside the blank."""
        clearance = self.blank_radius_mm + self.template.module_mm if clearance_radius_mm is None else clearance_radius_mm
        if not math.isfinite(clearance) or clearance <= self.blank_radius_mm + self.geometry_error_bound_mm:
            raise ValueError("native clearance arc must lie strictly outside the blank")
        alpha, tip = self.root_half_angle_rad, self.tip_half_angle_rad
        lo, hi = self.tip_point(-tip), self.tip_point(tip)
        outer_lo = clearance * math.cos(tip), -clearance * math.sin(tip)
        outer_hi = clearance * math.cos(tip), clearance * math.sin(tip)
        return tuple([
            self._segment("RootArc", "root_arc", "root", alpha, -alpha, scale=unit_scale),
            *self._branch_segments(-1, True, scale=unit_scale),
            self._segment("LowerClosingRay", "closing_ray", "line", 0, 1, scale=unit_scale, line=(*lo, *outer_lo)),
            self._segment("ClearanceArc", "clearance_arc", "circle", -tip, tip, scale=unit_scale, radius=clearance),
            self._segment("UpperClosingRay", "closing_ray", "line", 0, 1, scale=unit_scale, line=(*outer_hi, *hi)),
            *self._branch_segments(1, False, scale=unit_scale),
        ])

    def gap_polygon(self, samples_per_segment: int = 128) -> tuple[tuple[float, float], ...]:
        if type(samples_per_segment) is not int or samples_per_segment < 1:
            raise ValueError("samples per segment must be a positive integer")
        return tuple(s.point(i / samples_per_segment) for s in self.gap_segments() for i in range(samples_per_segment))

    def gap_polygon_error_bound_mm(self, samples_per_segment: int = 128) -> float:
        if type(samples_per_segment) is not int or samples_per_segment < 1:
            raise ValueError("samples per segment must be a positive integer")
        return max(s.second_derivative_bound_mm for s in self.gap_segments()) / (8 * samples_per_segment ** 2) + self.geometry_error_bound_mm

    def material_sector_segments(self, unit_scale: float = 1 / 25.4, embed_radius_mm: float | None = None, rotate_rad: float = 0.0) -> tuple[NativeSegment, ...]:
        """Whole pitch of material, retaining both off-centre floor lobes.

        The embed arc is below the TRUE root minimum, not below T+root.
        Normal helical sectors use the same transformed root and flank curves;
        the complete sector has area pi*(blank^2-embed^2)/N-gap_area.
        """
        embed = self.root_radius_min_mm / 2 if embed_radius_mm is None else embed_radius_mm
        _positive(embed, "embed radius")
        if embed >= self.root_radius_min_mm - self.geometry_error_bound_mm:
            raise ValueError("embed radius must lie below true root minimum")
        if not math.isfinite(rotate_rad):
            raise ValueError("sector rotation must be finite")
        h, alpha, tip = self.angular_pitch_rad / 2, self.root_half_angle_rad, self.tip_half_angle_rad
        floor = self.root_point(0)
        left_floor, right_floor = _rotate(*floor, -h), _rotate(*floor, h)
        left_embed, right_embed = _rotate(embed, 0, -h), _rotate(embed, 0, h)
        return tuple([
            self._segment("LeftSeam", "seam", "line", 0, 1, scale=unit_scale, rotation=rotate_rad, line=(*left_embed, *left_floor)),
            self._segment("LeftHalfRootArc", "root_arc", "root", 0, alpha, scale=unit_scale, rotation=rotate_rad-h),
            *self._branch_segments(1, True, scale=unit_scale, rotation=rotate_rad-h),
            self._segment("MaterialTipLand", "tip_arc", "circle", -h+tip, h-tip, scale=unit_scale, rotation=rotate_rad, radius=self.blank_radius_mm),
            *self._branch_segments(-1, False, scale=unit_scale, rotation=rotate_rad+h),
            self._segment("RightHalfRootArc", "root_arc", "root", -alpha, 0, scale=unit_scale, rotation=rotate_rad+h),
            self._segment("RightSeam", "seam", "line", 0, 1, scale=unit_scale, rotation=rotate_rad, line=(*right_floor, *right_embed)),
            self._segment("EmbedArc", "embed_arc", "circle", h, -h, scale=unit_scale, rotation=rotate_rad, radius=embed),
        ])

    def external_boundary_segments(self, unit_scale: float = 1.0, rotate_rad: float = 0.0) -> tuple[NativeSegment, ...]:
        """One true MATERIAL tooth perimeter; no artificial embed sidewalls.

        Repeat by integer physical pitches. Start/end are the two adjacent
        gap bisector floors, so repetitions close without a synthetic chord.
        Datum is tooth-centred, as for material_sector_segments.
        """
        return tuple(
            segment for segment in self.material_sector_segments(unit_scale, rotate_rad=rotate_rad)
            if segment.kind not in {"seam", "embed_arc"}
        )


def translation_for_pitch_tooth_thickness(
    teeth: int,
    template: CutterTemplate | CustomSixCutter,
    target_mm: float,
    helix_angle_deg: float = 0.0,
) -> float:
    """Invert ACTUAL transverse circular pitch thickness to total tool T.

    No trial ideal-N profile or extrapolated master is introduced. At the
    operating pitch circle, X=sqrt(Rp²-c²Y²) and the exact gap angle is
    asin(cY/Rp)+aY. Invert that angle, then the real reference branch's Y.
    A pitch-radius support probe finally enforces rootMAX below the circle
    and finite support at it. Blank/tolerance support beyond pitch is still
    the caller's separate manufactured-corner responsibility.
    """
    if type(teeth) is not int or teeth < 3:
        raise ValueError("physical pattern teeth must be an integer >=3")
    if not isinstance(template, (CutterTemplate, CustomSixCutter)):
        raise TypeError("template must be the declared stock or explicit custom cutter")
    _positive(target_mm, "target pitch tooth thickness")
    if not math.isfinite(helix_angle_deg) or abs(helix_angle_deg) >= 45:
        raise ValueError("helix angle must be finite and strictly between -45 and 45 degrees")
    beta = math.radians(helix_angle_deg)
    c = math.cos(beta)
    pitch = teeth * template.module_mm / (2 * c)
    theta = (2 * math.pi / teeth - target_mm / pitch) / 2
    if theta <= 0:
        raise ValueError("target thickness leaves no positive pitch gap")
    a = math.sin(beta) * math.tan(beta) / pitch
    ymin = template.root_point(template.root_half_angle_rad)[1]
    ymax = min(
        template.flank_point(template.flank_parameter_max)[1],
        math.nextafter(pitch / c, 0.0),
    )
    if ymin > ymax:
        raise ValueError("reference branch cannot reach this physical pitch circle")

    def angle(Y):
        return math.asin(c * Y / pitch) + a * Y

    if not angle(ymin) <= theta <= angle(ymax):
        raise ValueError("target thickness exceeds supported reference pitch branch")
    Y = pitch * math.sin(theta) if beta == 0 else _bisect(
        lambda y: angle(y) - theta, ymin, ymax
    )
    k, rb = template.half_space_base_angle_rad, template.base_radius_mm
    if template.root_radius_mm < rb and Y < rb * math.sin(k):
        radius = Y / math.sin(k)
        xref = radius * math.cos(k)
    else:
        u = _bisect(
            lambda z: template.flank_point(z)[1] - Y,
            template.flank_parameter_min,
            template.flank_parameter_max,
        )
        xref = template.flank_point(u)[0]
    T = math.sqrt(max(0.0, pitch * pitch - c * c * Y * Y)) - xref
    StockFormProfile(teeth, template, pitch, T, helix_angle_deg)
    return T


def translation_for_tangent_span(
    teeth: int,
    template: CutterTemplate | CustomSixCutter,
    target_span_mm: float,
    teeth_spanned: int,
    helix_angle_deg: float = 0.0,
    *,
    translation_bounds_mm: tuple[float, float],
) -> float:
    """Invert the actual NORMAL-plane span within caller-owned tool bounds.

    Bounds represent the caller's physically declared corner family. This
    function neither expands that family nor extrapolates a contact branch.
    It uses the ONE canonical span evaluator on the complete finite master
    curve, without inventing a pitch-radius or full-cap manufactured blank.
    Spur inversion is analytic; helix brackets the exact normal screw span.
    Callers must size the real blank and validate tangent_span_mm at EVERY
    printed OD/tool corner before claiming manufactured qualification.
    """
    if type(teeth) is not int or teeth < 3:
        raise ValueError("physical pattern teeth must be an integer >=3")
    if not isinstance(template, (CutterTemplate, CustomSixCutter)):
        raise TypeError("template must be the declared stock or explicit custom cutter")
    _positive(target_span_mm, "target tangent span")
    if type(teeth_spanned) is not int or not 1 <= teeth_spanned < teeth:
        raise ValueError("span count must be a positive physical integer below tooth count")
    if not math.isfinite(helix_angle_deg) or abs(helix_angle_deg) >= 45:
        raise ValueError("helix angle must be finite and strictly between -45 and 45 degrees")
    if len(translation_bounds_mm) != 2:
        raise ValueError("translation bounds must contain lower and upper limits")
    lo, hi = translation_bounds_mm
    if not all(math.isfinite(z) for z in (lo, hi)) or lo > hi:
        raise ValueError("translation bounds must be finite and ordered")

    def span(T):
        return _supported_tangent_span_mm(
            teeth, template, T, helix_angle_deg, teeth_spanned,
            template.flank_parameter_min, template.flank_parameter_max, True,
        )

    lower_span, upper_span = span(lo), span(hi)
    if not min(lower_span, upper_span) <= target_span_mm <= max(lower_span, upper_span):
        raise ValueError("target tangent span is outside the caller translation bounds")
    if helix_angle_deg == 0:
        h = math.pi * teeth_spanned / teeth
        u = h - template.half_space_base_angle_rad
        T = (target_span_mm - 2 * template.base_radius_mm * u) / (2 * math.sin(h))
        if not lo <= T <= hi:
            # Cancellation at an exactly named endpoint must not turn into
            # an extrapolation. Return the endpoint only for exact equality.
            if target_span_mm == lower_span:
                T = lo
            elif target_span_mm == upper_span:
                T = hi
            else:
                raise ValueError("analytic span inverse leaves caller translation bounds")
    else:
        T = _bisect(lambda z: span(z) - target_span_mm, lo, hi)
    span(T)
    return T
