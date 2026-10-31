"""Pure sections for the uniform-7 mm summing lever; lengths are millimetres.

The installed top face and spring row stay fixed. The matched bracket/receiver
row is located from that actual top by the joint contract. Each positive-X rib
flank is the common tangent of the origin-centred wrap and a concave R.040
runout into its coefficient-plate face. No tangent coordinate is a design knob.
Line/circle boundary integrals give exact areas and first moments: these are
ideal prismatic unions, excluding native cap-root and longitudinal body fillets.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import cached_property
from itertools import product
import math

from _printed_tolerance import printed_band_mm
import magnifying_bracket_joint_layout as joint
import sm_summing_lever_spec as spec

Point = tuple[float, float]

# PlateProfile.PlateTopY independently drives CoefficientTopY: unlike the old
# centred slab, it takes a whole band of its own, not half the thickness band.
# The sheet locates the top at .XXX from the knife ridge (.102) and the boss
# top (.275); the whole .XX row covers either .XXX band plus half the ridge's
# .XXX height band and their sub-.0002 rounding.
PLATE_TOP_Y_ALLOWANCE = printed_band_mm(2, unit=spec.UNIT)


@dataclass(frozen=True)
class SectionMoments:
    """Signed area and first moments integral(x dA), integral(y dA)."""

    area_mm2: float = 0.0
    x_mm3: float = 0.0
    y_mm3: float = 0.0

    def __add__(self, other: SectionMoments) -> SectionMoments:
        return SectionMoments(
            self.area_mm2 + other.area_mm2,
            self.x_mm3 + other.x_mm3,
            self.y_mm3 + other.y_mm3,
        )

    def __sub__(self, other: SectionMoments) -> SectionMoments:
        return self + other.scaled(-1.0)

    def scaled(self, factor: float) -> SectionMoments:
        return SectionMoments(
            self.area_mm2 * factor, self.x_mm3 * factor, self.y_mm3 * factor
        )


@dataclass(frozen=True)
class Line:
    start_xy: Point
    end_xy: Point

    def distance(self, x: float, y: float) -> float:
        ax, ay = self.start_xy
        dx, dy = self.end_xy[0] - ax, self.end_xy[1] - ay
        length2 = dx * dx + dy * dy
        t = max(0.0, min(1.0, ((x - ax) * dx + (y - ay) * dy) / length2))
        return math.hypot(x - ax - t * dx, y - ay - t * dy)

    def moments(self) -> SectionMoments:
        ax, ay = self.start_xy
        bx, by = self.end_xy
        return SectionMoments(
            (ax * by - bx * ay) / 2.0,
            (by - ay) * (ax * ax + ax * bx + bx * bx) / 6.0,
            -(bx - ax) * (ay * ay + ay * by + by * by) / 6.0,
        )


@dataclass(frozen=True)
class Arc:
    center_xy: Point
    radius: float
    start_angle: float
    sweep: float

    @property
    def start_xy(self) -> Point:
        return self.point(self.start_angle)

    @property
    def end_xy(self) -> Point:
        return self.point(self.start_angle + self.sweep)

    def point(self, angle: float) -> Point:
        return (
            self.center_xy[0] + self.radius * math.cos(angle),
            self.center_xy[1] + self.radius * math.sin(angle),
        )

    def distance(self, x: float, y: float) -> float:
        dx, dy = x - self.center_xy[0], y - self.center_xy[1]
        angle = math.atan2(dy, dx)
        progress = (
            (angle - self.start_angle) % math.tau if self.sweep >= 0.0
            else (self.start_angle - angle) % math.tau
        )
        if progress <= abs(self.sweep) + 1e-14:
            return abs(math.hypot(dx, dy) - self.radius)
        return min(math.dist((x, y), self.start_xy), math.dist((x, y), self.end_xy))

    def moments(self) -> SectionMoments:
        a, b = self.start_angle, self.start_angle + self.sweep
        cx, cy = self.center_xy
        r = self.radius
        cos1 = math.sin(b) - math.sin(a)
        sin1 = math.cos(a) - math.cos(b)
        cos2 = self.sweep / 2.0 + (math.sin(2.0 * b) - math.sin(2.0 * a)) / 4.0
        sin2 = self.sweep / 2.0 - (math.sin(2.0 * b) - math.sin(2.0 * a)) / 4.0
        cos3 = cos1 - (math.sin(b) ** 3 - math.sin(a) ** 3) / 3.0
        sin3 = sin1 + (math.cos(b) ** 3 - math.cos(a) ** 3) / 3.0
        return SectionMoments(
            (r * cx * cos1 + r * cy * sin1 + r * r * self.sweep) / 2.0,
            r * (cx * cx * cos1 + 2.0 * cx * r * cos2 + r * r * cos3) / 2.0,
            r * (cy * cy * sin1 + 2.0 * cy * r * sin2 + r * r * sin3) / 2.0,
        )


Boundary = tuple[Line | Arc, ...]


def _moments(boundary: Boundary) -> SectionMoments:
    result = SectionMoments()
    for segment in boundary:
        result += segment.moments()
    return result


def _polyline(points: tuple[Point, ...]) -> Boundary:
    return tuple(Line(a, b) for a, b in zip(points, points[1:]) if a != b)


@dataclass(frozen=True)
class Branch:
    wrap_xy: Point
    flank_xy: Point
    center_xy: Point
    normal_xy: Point
    end_xy: Point
    blend_radius: float

    @property
    def angle(self) -> float:
        return math.atan2(self.normal_xy[1], self.normal_xy[0])

    @property
    def line(self) -> Line:
        return Line(self.wrap_xy, self.flank_xy)

    @property
    def blend(self) -> Arc:
        # Both branches are traversed end -> flank here. The enclosing
        # counterclockwise boundary reverses the lower branch below.
        end_angle = -math.copysign(math.pi / 2.0, self.normal_xy[1])
        flank_angle = math.atan2(-self.normal_xy[1], -self.normal_xy[0])
        return Arc(self.center_xy, self.blend_radius, end_angle, flank_angle - end_angle)

    def height(self, x: float, wrap_radius: float) -> float:
        sign = math.copysign(1.0, self.normal_xy[1])
        if x <= self.wrap_xy[0]:
            return sign * math.sqrt(max(0.0, wrap_radius * wrap_radius - x * x))
        if x <= self.flank_xy[0]:
            nx, ny = self.normal_xy
            return (wrap_radius - nx * x) / ny
        cx, cy = self.center_xy
        return cy - sign * math.sqrt(max(0.0, self.blend_radius**2 - (x - cx) ** 2))


@dataclass(frozen=True)
class RibProfile:
    wrap_radius: float = spec.RIB_WRAP_R
    reach: float = spec.RIB_REACH
    blend_radius: float = spec.RIB_BLEND_R
    top_y: float = spec.COEFFICIENT_TOP_Y
    bottom_y: float = spec.COEFFICIENT_BOTTOM_Y
    cylinder_radius: float = spec.CYL_R
    plate_width: float = spec.PLATE_W

    def __post_init__(self) -> None:
        if not (
            0.0 <= self.blend_radius < self.wrap_radius
            and 0.0 < self.cylinder_radius < self.wrap_radius < self.reach < self.plate_width
            and -self.cylinder_radius < self.bottom_y < 0.0 < self.top_y < self.cylinder_radius
        ):
            raise ValueError("rib dimensions do not define the intended cylinder/plate union")
        if any(branch.flank_xy[0] <= branch.wrap_xy[0] for branch in (self.upper, self.lower)):
            raise ValueError("rib flank has no positive-X tangent run")

    def _branch(self, face_y: float, sign: float) -> Branch:
        center = (self.reach, face_y + sign * self.blend_radius)
        cx, cy = center
        length2 = cx * cx + cy * cy
        offset = self.wrap_radius + self.blend_radius
        if length2 <= offset * offset:
            raise ValueError("blend centre must stand outside the offset wrap circle")
        tangent = math.sqrt(length2 - offset * offset)
        nx = (offset * cx - sign * tangent * cy) / length2
        ny = (offset * cy + sign * tangent * cx) / length2
        return Branch(
            (self.wrap_radius * nx, self.wrap_radius * ny),
            (cx - self.blend_radius * nx, cy - self.blend_radius * ny),
            center, (nx, ny), (self.reach, face_y), self.blend_radius,
        )

    @cached_property
    def upper(self) -> Branch:
        return self._branch(self.top_y, 1.0)

    @cached_property
    def lower(self) -> Branch:
        return self._branch(self.bottom_y, -1.0)

    def rib_bounds(self, x: float) -> tuple[float, float]:
        """Closed sketch bounds, not a symmetric half-height approximation."""
        if not -self.wrap_radius <= x <= self.reach:
            raise ValueError(f"x={x} outside rib [-{self.wrap_radius}, {self.reach}]")
        return self.lower.height(x, self.wrap_radius), self.upper.height(x, self.wrap_radius)

    @cached_property
    def upper_boundary(self) -> Boundary:
        branch = self.upper
        return (
            Line((self.plate_width, self.top_y), branch.end_xy),
            branch.blend,
            Line(branch.flank_xy, branch.wrap_xy),
            Arc((0.0, 0.0), self.wrap_radius, branch.angle, math.pi / 2.0 - branch.angle),
        )

    @cached_property
    def lower_boundary(self) -> Boundary:
        branch = self.lower
        blend = branch.blend
        return (
            Arc((0.0, 0.0), self.wrap_radius, -math.pi / 2.0, branch.angle + math.pi / 2.0),
            branch.line,
            Arc(blend.center_xy, blend.radius, blend.start_angle + blend.sweep, -blend.sweep),
            Line(branch.end_xy, (self.plate_width, self.bottom_y)),
        )

    @cached_property
    def boundary(self) -> Boundary:
        """Actual external union: the end closure at reach is NOT a wall."""
        return (
            *self.upper_boundary,
            Arc((0.0, 0.0), self.wrap_radius, math.pi / 2.0, math.pi),
            *self.lower_boundary,
            Line((self.plate_width, self.bottom_y), (self.plate_width, self.top_y)),
        )

    def signed_boundary_distance(self, x: float, y: float) -> float:
        distance = min(segment.distance(x, y) for segment in self.boundary)
        inside = False
        if -self.wrap_radius <= x <= self.reach:
            lower, upper = self.rib_bounds(x)
            inside = lower <= y <= upper
        elif self.reach < x <= self.plate_width:
            inside = self.bottom_y <= y <= self.top_y
        return distance if inside else -distance

    def receiver_wall_margin(self, x: float, y: float, radius: float) -> float:
        """Signed profile distance outside a circle of the supplied radius."""
        if radius < 0.0:
            raise ValueError("receiver radius must be nonnegative")
        return self.signed_boundary_distance(x, y) - radius

    def section_moments(self) -> SectionMoments:
        return _moments(self.boundary)

    def base_section_moments(self) -> SectionMoments:
        """Cylinder union uniform plate, before an edge rib is added."""
        r, top, bottom, width = self.cylinder_radius, self.top_y, self.bottom_y, self.plate_width
        upper = (math.sqrt(r * r - top * top), top)
        lower = (math.sqrt(r * r - bottom * bottom), bottom)
        a = math.atan2(top, upper[0])
        b = math.atan2(bottom, lower[0]) + math.tau
        return _moments((
            *_polyline(((width, top), upper)),
            Arc((0.0, 0.0), r, a, b - a),
            *_polyline((lower, (width, bottom), (width, top))),
        ))

    def edge_rib_added_area_mm2(self) -> float:
        return (self.section_moments() - self.base_section_moments()).area_mm2


PROFILE = RibProfile()
UPPER = PROFILE.upper
LOWER = PROFILE.lower


def rib_bounds(x: float) -> tuple[float, float]:
    return PROFILE.rib_bounds(x)


def edge_rib_added_area_mm2() -> float:
    return PROFILE.edge_rib_added_area_mm2()


def receiver_wall_margin(x: float, y: float, radius: float) -> float:
    return PROFILE.receiver_wall_margin(x, y, radius)


@dataclass(frozen=True)
class ReceiverPilotWallBudget:
    """Longitudinal pilot wall bound, including diameter allowance and wander."""
    x_mm: float
    upper_mm: float
    lower_mm: float
    minimum_mm: float
    # Witness: wrap, reach, blend, width, top, thickness, tap-x error, tap-y error.
    upper_witness: tuple[float, ...]
    lower_witness: tuple[float, ...]
    minimum_witness: tuple[float, ...]


def receiver_pilot_wall_budget() -> tuple[ReceiverPilotWallBudget, ...]:
    """Pilot walls with ordinary shape bands and correlated receiver locations.

    Width, wrap, reach and thickness each take their printed limits
    (``spec.*_DEVIATIONS``). The R.040 MAX runout independently spans
    0..R.040. The independent PlateTopY takes PLATE_TOP_Y_ALLOWANCE. The
    receiver row is +/-POSITION_BAND from the ACTUAL top, just as each X
    station is from the ACTUAL free edge: their shifts
    are shared, not charged again as independent axis motion. The radius is
    the larger native/printed pilot plus its diameter allowance and deepest
    drill wander. These are longitudinal walls within a rib's span only;
    joint.receiver_pilot_material_wall_budget screens the continuation through
    the connected plate beyond that rib. Neither budget guarantees finished
    thread walls, native geometry or strength.
    """
    pilot_radius = joint.receiver_pilot_radius_max()
    pilot_wander = math.tan(math.radians(joint.DRILL_WANDER_DEG)) * (
        joint.DRILL_DEPTH_MAX + pilot_radius * joint.DRILL_POINT_H
    )
    radius = pilot_radius + pilot_wander
    points = joint.LEVER_HOLE_POINTS
    values = [[math.inf, math.inf, math.inf] for _ in points]
    witnesses = [[(), (), ()] for _ in points]

    def limit(nominal: float, deviations: tuple[float, float], side: float) -> float:
        return nominal + deviations[side > 0.0]

    for dr, dx, db, dw, dt, dh in product((-1.0, 1.0), repeat=6):
        top = spec.COEFFICIENT_TOP_Y + dt * PLATE_TOP_Y_ALLOWANCE
        thickness = limit(spec.COEFFICIENT_T, spec.COEFFICIENT_T_DEVIATIONS, dh)
        profile = RibProfile(
            wrap_radius=limit(spec.RIB_WRAP_R, spec.RIB_WRAP_R_DEVIATIONS, dr),
            reach=limit(spec.RIB_REACH, spec.RIB_REACH_DEVIATIONS, dx),
            blend_radius=spec.RIB_BLEND_R * (db + 1.0) / 2.0,
            plate_width=limit(spec.PLATE_W, spec.PLATE_W_DEVIATIONS, dw),
            top_y=top, bottom_y=top - thickness,
        )
        for index, (nominal_x, nominal_y, _) in enumerate(points):
            for ex, ey in product((-joint.POSITION_BAND, joint.POSITION_BAND), repeat=2):
                x = profile.plate_width - (spec.PLATE_W - nominal_x) + ex
                y = top - (spec.COEFFICIENT_TOP_Y - nominal_y) + ey
                clearances = (
                    min(segment.distance(x, y) for segment in profile.upper_boundary) - radius,
                    min(segment.distance(x, y) for segment in profile.lower_boundary) - radius,
                    profile.receiver_wall_margin(x, y, radius),
                )
                witness = (
                    profile.wrap_radius, profile.reach, profile.blend_radius,
                    profile.plate_width, top, thickness, ex, ey,
                )
                for side, clearance in enumerate(clearances):
                    if clearance < values[index][side]:
                        values[index][side] = clearance
                        witnesses[index][side] = witness
    return tuple(
        ReceiverPilotWallBudget(point[0], *value, *witness)
        for point, value, witness in zip(points, values, witnesses)
    )
