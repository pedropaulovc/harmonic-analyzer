"""Discrete purchased ANSI #25 chain fit, independent of the native visual.

A fixed even pinned cycle has standard-pitch CHORDS, not pitch-circle arc
lengths. Seated links use the sprockets' exact pitch polygons; a straight
strand fixes the second wheel's free phase by circle intersection. The other
strand is a finite hinged catenary under gravity. Every roller is checked
against the complete analytic ANSI seat/working/flank/topping/tip boundary.

Wheel phases below are mathematical fit outputs. They never change the DT
park pose, drive pins, native belt mate, or inherited continuous-arc visual.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from functools import cache

import pd_transgear_removable_spec as sprocket
from _printed_tolerance import printed_deviations

Point = tuple[float, float]
_TAU = 2.0 * math.pi
_NUMERIC_MM = 1e-7


class ChainSearchUnqualified(ValueError):
    """Finite candidate/numerical refusal: NOT a physical infeasibility verdict."""


def source_nominal_chain_centres_mm() -> tuple[Point, Point]:
    """Actual source-selected axes at the common installed wheel plane.

    The canonical LOWER reader includes the real post/cone/pivot station and
    approved 7.5 extension; no historical cone_line XY or copied geometry.
    Default engaged P1 nominal has parallel world-Z axes. Manufacturing
    tilt and arbitrary P1 states need their own 3D proof, not this nominal one.
    """
    from dt_cone_support_pose import crank_axis_nominal_xy_mm
    from paper_drive_geom import KNOB_SHAFT_XY
    return KNOB_SHAFT_XY, crank_axis_nominal_xy_mm(sprocket.CHAIN_MID_Z)


def solve_source_nominal_chain_fit(*, taut_side: int = 1) -> ChainFit:
    """A source-qualified nominal candidate, fixed installed count and pitch."""
    knob, crank = source_nominal_chain_centres_mm()
    return solve_chain_fit(knob, crank, taut_side=taut_side)


class _NumericStrandError(ValueError):
    """A finite hinged-strand numeric bracket or closure failed."""


class _SpanModelError(ValueError):
    """This candidate lies outside the free suspended-strand model."""


@dataclass(frozen=True)
class ChainFit:
    knob_centre: Point
    crank_centre: Point
    knob_teeth: int
    crank_teeth: int
    knob_phase_rad: float
    crank_phase_rad: float
    pins: tuple[Point, ...]
    knob_seated: tuple[int, ...]
    crank_seated: tuple[int, ...]
    slack_pins: tuple[int, ...]
    taut_side: int
    gravity: Point
    sag_mm: float
    roller_air_mm: float
    plate_air_mm: float
    backbend_air_mm: float
    strand_air_mm: float
    envelope_mm: tuple[float, float, float, float]


def _cross(a: Point, b: Point) -> float:
    return a[0] * b[1] - a[1] * b[0]


def _sub(a: Point, b: Point) -> Point:
    return a[0] - b[0], a[1] - b[1]


def _dot(a: Point, b: Point) -> float:
    return a[0] * b[0] + a[1] * b[1]


def _angle_distance(a: float, b: float) -> float:
    return abs((a - b + math.pi) % _TAU - math.pi)


def _arc_contains(angle: float, start: float, end: float) -> bool:
    direction = 1.0 if end >= start else -1.0
    return (direction * (angle - start)) % _TAU <= abs(end - start) + 1e-12


def _arc_distance(point: Point, arc: tuple[float, ...]) -> float:
    cx, cy, radius, start, end = arc
    delta = point[0] - cx, point[1] - cy
    if _arc_contains(math.atan2(delta[1], delta[0]), start, end):
        return abs(math.hypot(*delta) - radius)
    return min(
        math.dist(point, (cx + radius * math.cos(a), cy + radius * math.sin(a)))
        for a in (start, end)
    )


def _line_distance(point: Point, line: tuple[Point, Point]) -> float:
    first, last = line
    direction = _sub(last, first)
    t = max(0.0, min(1.0, _dot(_sub(point, first), direction) / _dot(direction, direction)))
    return math.dist(point, (first[0] + t * direction[0], first[1] + t * direction[1]))


@cache
def _tooth_boundary(teeth: int, tip_deviation_mm: float = 0.0):
    geometry = dict(sprocket.gap_geometry(teeth))
    if not math.isfinite(tip_deviation_mm) or tip_deviation_mm < 0.0:
        raise ValueError("the maximum-metal OD deviation must be finite and nonnegative")
    corner = geometry["corner_x"], geometry["corner_y"]
    lines = ()
    if tip_deviation_mm:
        # Native ToothGapProfile closes K to q=(2*Ra,0), mirrored below.
        # The through-cut clips this line, not an extrapolated topping arc.
        actual_radius = geometry["ra"] + tip_deviation_mm / 2.0
        direction = _sub((2.0 * geometry["ra"], 0.0), corner)
        aa = _dot(direction, direction)
        bb = _dot(corner, direction)
        discriminant = bb * bb + aa * (actual_radius * actual_radius - _dot(corner, corner))
        parameter = (-bb + math.sqrt(discriminant)) / aa
        new_corner = corner[0] + parameter * direction[0], corner[1] + parameter * direction[1]
        new_angle = math.atan2(new_corner[1], new_corner[0])
        if not 0.0 < parameter < 1.0 or not 0.0 < new_angle < geometry["corner_angle"]:
            raise ValueError("the printed OD maximum exceeds the native gap's supported closing line")
        lines = ((corner, new_corner), tuple((x, -y) for x, y in (corner, new_corner)))
        geometry["ra"], geometry["corner_angle"] = actual_radius, new_angle
    arcs = (
        (geometry["rp"], 0.0, geometry["seat_r"], math.pi, geometry["seat_start"]),
        (geometry["working_cx"], geometry["working_cy"], geometry["working_r"],
         geometry["seat_start"], geometry["working_end"]),
        (geometry["topping_cx"], geometry["topping_cy"], geometry["topping_r"],
         geometry["topping_start"], geometry["topping_end"]),
    )
    arcs += tuple((cx, -cy, radius, -start, -end) for cx, cy, radius, start, end in arcs)
    # The land connects one gap's upper OD corner to the next gap's lower corner.
    arcs += ((0.0, 0.0, geometry["ra"], geometry["corner_angle"],
              _TAU / teeth - geometry["corner_angle"]),)
    line = ((geometry["flank_start_x"], geometry["flank_start_y"]),
            (geometry["flank_end_x"], geometry["flank_end_y"]))
    lines += (line, tuple((x, -y) for x, y in line))
    return geometry, arcs, lines


def _root_to_tip_radius(angle: float, teeth: int, tip_deviation_mm: float = 0.0) -> float:
    """Exact radial boundary of the nearest gap, not an OD/root annulus proxy."""
    geometry, arcs, lines = _tooth_boundary(teeth, tip_deviation_mm)
    if abs(angle) > geometry["corner_angle"] + 1e-12:
        return geometry["ra"]
    direction = math.cos(angle), math.sin(angle)
    radii = []
    for cx, cy, radius, start, end in arcs[:-1]:
        along = cx * direction[0] + cy * direction[1]
        discriminant = radius * radius - cx * cx - cy * cy + along * along
        if discriminant < -1e-10:
            continue
        root = math.sqrt(max(0.0, discriminant))
        for distance in (along - root, along + root):
            if distance <= 0.0:
                continue
            angle_on_arc = math.atan2(distance * direction[1] - cy, distance * direction[0] - cx)
            if _arc_contains(angle_on_arc, start, end):
                radii.append(distance)
    for first, last in lines:
        segment = _sub(last, first)
        divisor = _cross(direction, segment)
        if abs(divisor) <= 1e-14:
            continue
        distance = _cross(first, segment) / divisor
        t = _cross(first, direction) / divisor
        if distance > 0.0 and -1e-10 <= t <= 1.0 + 1e-10:
            radii.append(distance)
    if not radii:
        raise ValueError(f"T{teeth}: no supported root-to-tip boundary at {angle}")
    return min(radii)


def roller_air_mm(point: Point, centre: Point, teeth: int, phase: float, *,
                  tip_deviation_mm: float = 0.0) -> float:
    """Signed air against the analytic tooth and the catalogue .130 in roller.

    This is the stated nominal ANSI form, with optional native OD-max closing
    geometry; it does not certify an uncontrolled vendor tooth-profile grade.
    """
    delta = _sub(point, centre)
    radial = math.hypot(*delta)
    roller_radius = sprocket.ANSI_ROLLER_DIA / 2.0
    if (not math.isfinite(tip_deviation_mm) or tip_deviation_mm < 0.0
            or tip_deviation_mm / 2.0 >= roller_radius):
        raise ValueError("OD maximum must stay inside the supported thin-tip allowance")
    # Between the old and new OD corner a thin air wedge can have two radial
    # crossings. Conservatively classify it as metal: its entire thickness is
    # smaller than a roller radius, so it cannot contain a valid roller.
    tip_radius = (sprocket.outside_dia(teeth) + tip_deviation_mm) / 2.0
    if radial > tip_radius + roller_radius:
        return radial - tip_radius - roller_radius
    pitch_angle = _TAU / teeth
    relative = math.atan2(delta[1], delta[0]) - phase - math.pi / teeth
    gap_angle = (relative + pitch_angle / 2.0) % pitch_angle - pitch_angle / 2.0
    outside = radial >= _root_to_tip_radius(gap_angle, teeth, tip_deviation_mm)
    _, arcs, lines = _tooth_boundary(teeth, tip_deviation_mm)
    nearest = math.inf
    for tooth in range(teeth):
        angle = phase + math.pi / teeth + tooth * pitch_angle
        cosine, sine = math.cos(angle), math.sin(angle)
        local = delta[0] * cosine + delta[1] * sine, -delta[0] * sine + delta[1] * cosine
        nearest = min(nearest, *(_arc_distance(local, arc) for arc in arcs),
                      *(_line_distance(local, line) for line in lines))
    return (nearest if outside else -nearest) - roller_radius


def printed_tip_max_deviation_mm(teeth: int) -> float:
    """Upper OD deviation actually printed on this configuration's BlankDia."""
    return printed_deviations(
        sprocket.outside_dia(teeth), sprocket.DRAWING_PRECISION["BlankProfile"]["BlankDia"]
    )[1]


def _catenary(first: Point, last: Point, count: int, gravity: Point) -> tuple[Point, ...]:
    """Equal-weight hinges; each of the count links has the exact standard pitch."""
    pitch = sprocket.CHAIN_PITCH
    horizontal = -gravity[1], gravity[0]
    up = -gravity[0], -gravity[1]
    delta = _sub(last, first)
    dx, dy = _dot(delta, horizontal), _dot(delta, up)
    length = count * pitch
    if count < 2 or length <= math.hypot(dx, dy) + _NUMERIC_MM:
        raise _SpanModelError("free gravity strand is not longer than its endpoint separation")
    if abs(dx) <= pitch:
        raise _SpanModelError("free hinged-strand model requires horizontal projection greater than one pitch")
    target_x = abs(dx)
    sign_x = math.copysign(1.0, dx)
    slope_bound = abs(dy) / math.sqrt(length * length - dy * dy) + 2.0

    def forces(h: float):
        lo, hi = -count - h * slope_bound, count + h * slope_bound
        for _ in range(60):
            vertical = 0.5 * (lo + hi)
            height = sum(pitch * (vertical + j) / math.hypot(h, vertical + j) for j in range(count))
            if height < dy:
                lo = vertical
            else:
                hi = vertical
        vertical = 0.5 * (lo + hi)
        width = sum(pitch * h / math.hypot(h, vertical + j) for j in range(count))
        return width, vertical

    lo, hi = 1e-9, float(count)
    if forces(lo)[0] >= target_x:
        raise _NumericStrandError("gravity catenary has no positive horizontal-force bracket")
    for _ in range(64):
        if forces(hi)[0] > target_x:
            break
        hi *= 2.0
    else:
        raise _NumericStrandError("gravity catenary horizontal-force bracket exhausted")
    for _ in range(60):
        mid = 0.5 * (lo + hi)
        if forces(mid)[0] < target_x:
            lo = mid
        else:
            hi = mid
    h = 0.5 * (lo + hi)
    _, vertical = forces(h)
    points = [first]
    for j in range(count):
        norm = math.hypot(h, vertical + j)
        x, y = sign_x * pitch * h / norm, pitch * (vertical + j) / norm
        previous = points[-1]
        points.append((previous[0] + x * horizontal[0] + y * up[0],
                       previous[1] + x * horizontal[1] + y * up[1]))
    if math.dist(points[-1], last) > 1e-9:
        raise _NumericStrandError("numeric gravity-strand endpoint did not close at standard pitch")
    return tuple(points)


def _segment_distance(first: tuple[Point, Point], second: tuple[Point, Point]) -> float:
    a, b = first
    c, d = second
    ab, cd = _sub(b, a), _sub(d, c)
    divisor = _cross(ab, cd)
    if abs(divisor) > 1e-14:
        t = _cross(_sub(c, a), cd) / divisor
        u = _cross(_sub(c, a), ab) / divisor
        if 0.0 <= t <= 1.0 and 0.0 <= u <= 1.0:
            return 0.0
    return min(_line_distance(a, second), _line_distance(b, second),
               _line_distance(c, first), _line_distance(d, first))


def _supported_turn(before: Point, pin: Point, after: Point, sense: int, limit: float) -> bool:
    """A tension-loaded seated junction must turn into, not out of, its wrap."""
    incoming, outgoing = _sub(pin, before), _sub(after, pin)
    pitch_squared = sprocket.CHAIN_PITCH * sprocket.CHAIN_PITCH
    signed = sense * _cross(incoming, outgoing) / pitch_squared
    angle = math.acos(max(-1.0, min(1.0, _dot(incoming, outgoing) / pitch_squared)))
    return signed >= -1e-10 and angle <= limit + 1e-8


def require_pinned_cycle(pins: tuple[Point, ...], *, link_count: int | None = None) -> float:
    """Refuse an open seam, stretched pitch, wrong count, or non-finite pin."""
    expected = sprocket.CHAIN_LINK_COUNT if link_count is None else link_count
    if type(expected) is not int or expected <= 0 or expected % 2:
        raise ValueError("the selected chain count must be a positive even integer")
    if len(pins) != expected or any(not all(math.isfinite(value) for value in pin) for pin in pins):
        raise ValueError(f"pinned cycle must contain exactly {expected} finite pins")
    error = max(abs(math.dist(pins[i], pins[(i + 1) % expected]) - sprocket.CHAIN_PITCH)
                for i in range(expected))
    if error > _NUMERIC_MM:
        raise ValueError(f"pinned cycle pitch/seam error {error:.9f} mm")
    return error


def solve_chain_fit(knob_centre: Point, crank_centre: Point, *,
                    knob_teeth: int | None = None, crank_teeth: int | None = None,
                    link_count: int | None = None, taut_side: int = 1,
                    gravity: Point = (0.0, -1.0)) -> ChainFit:
    """Find an exact-pitch free-phase cycle on a bounded deterministic search.

    A found cycle is checked at every pin. Exhausting the sampled phase and
    integer allocation window is not a proof of physical non-existence.
    Failure reports that search, numerical refusals and a necessary length
    bound; it never resizes the chain or substitutes a continuous arc.
    """
    na = sprocket.KNOB_TEETH if knob_teeth is None else knob_teeth
    nb = sprocket.CRANK_TEETH if crank_teeth is None else crank_teeth
    count = sprocket.CHAIN_LINK_COUNT if link_count is None else link_count
    if type(count) is not int or count <= 0 or count % 2:
        raise ValueError("the selected chain count must be a positive even integer")
    if na not in sprocket.TEETH.values() or nb not in sprocket.TEETH.values():
        raise ValueError("unregistered ANSI #25 sprocket tooth count")
    if taut_side not in (-1, 1):
        raise ValueError("taut side must identify one of the two external strands")
    if not all(math.isfinite(value) for point in (knob_centre, crank_centre, gravity) for value in point):
        raise ValueError("chain centres and gravity must be finite")
    gravity_length = math.hypot(*gravity)
    if gravity_length <= 0.0:
        raise ValueError("gravity direction must be nonzero")
    gravity = gravity[0] / gravity_length, gravity[1] / gravity_length
    delta = _sub(crank_centre, knob_centre)
    distance = math.hypot(*delta)
    ra, rb = sprocket.pitch_dia(na) / 2.0, sprocket.pitch_dia(nb) / 2.0
    pitch = sprocket.CHAIN_PITCH
    bound = 2.0 * max(0.0, distance - ra - rb)
    if distance <= ra + rb or count * pitch < bound:
        raise ValueError(f"selected {count} links cannot fit centres {knob_centre}, {crank_centre}; "
                         f"necessary taut-length lower bound {bound:.6f} mm, available {count * pitch:.6f} mm")
    if sprocket.ANSI_ROLLER_WIDTH <= sprocket.PLATE:
        raise ValueError("purchased chain inner plates cannot straddle the sprocket")
    tip_a = printed_tip_max_deviation_mm(na)
    tip_b = printed_tip_max_deviation_mm(nb)
    u = delta[0] / distance, delta[1] / distance
    n = -u[1], u[0]
    frame_angle = math.atan2(u[1], u[0])
    step_a, step_b = _TAU / na, _TAU / nb
    tangent_angle = taut_side * math.acos((ra - rb) / distance)
    wrap_a = math.pi + 2.0 * math.asin((ra - rb) / distance)
    wrap_b = _TAU - wrap_a
    nominal_a, nominal_b = round(wrap_a / step_a), round(wrap_b / step_b)
    nominal_taut = round(math.sqrt(distance * distance - (ra - rb) ** 2) / pitch)

    def world(x: float, y: float) -> Point:
        return knob_centre[0] + x * u[0] + y * n[0], knob_centre[1] + x * u[1] + y * n[1]

    def on_a(angle: float) -> Point:
        return world(ra * math.cos(angle), ra * math.sin(angle))

    def on_b(angle: float) -> Point:
        return world(distance + rb * math.cos(angle), rb * math.sin(angle))
    def air_at(point: Point, phase_a: float, phase_b: float) -> float:
        return min(roller_air_mm(point, knob_centre, na, phase_a, tip_deviation_mm=tip_a),
                   roller_air_mm(point, crank_centre, nb, phase_b, tip_deviation_mm=tip_b))

    # Sample one tooth either side of the tangent and neighbouring allocations.
    # This finite search reports its scope rather than claiming all phases.
    phase_offsets = [0.0]
    phase_offsets.extend(sign * step_a * j / 48.0 for j in range(1, 49) for sign in (-1.0, 1.0))
    best_air = -math.inf
    numerical_refusals = 0
    span_refusals = 0
    for offset in phase_offsets:
        alpha = tangent_angle + offset
        a_top = ra * math.cos(alpha), ra * math.sin(alpha)
        relative = a_top[0] - distance, a_top[1]
        separation = math.hypot(*relative)
        for tight in (nominal_taut, nominal_taut - 1, nominal_taut + 1):
            tight_length = tight * pitch
            if tight < 1 or not abs(separation - rb) <= tight_length <= separation + rb:
                continue
            cosine = (separation * separation + rb * rb - tight_length * tight_length) / (2.0 * separation * rb)
            if not -1.0 <= cosine <= 1.0:
                continue
            direction = math.atan2(relative[1], relative[0])
            betas = sorted((direction - math.acos(cosine), direction + math.acos(cosine)),
                           key=lambda value: _angle_distance(value, tangent_angle))
            for beta in betas:
                if _angle_distance(beta, tangent_angle) > step_b:
                    continue
                phase_a = frame_angle + alpha - math.pi / na
                phase_b = frame_angle + beta - math.pi / nb
                for seated_a in (nominal_a, nominal_a - 1, nominal_a + 1):
                    for seated_b in (nominal_b, nominal_b - 1, nominal_b + 1):
                        slack_count = count - tight - seated_a - seated_b
                        if min(seated_a, seated_b, slack_count) < 2:
                            continue
                        a_wrap = tuple(on_a(alpha + taut_side * j * step_a) for j in range(seated_a + 1))
                        b_wrap = tuple(on_b(beta - taut_side * (seated_b - j) * step_b) for j in range(seated_b + 1))
                        tight_points = tuple((b_wrap[-1][0] + (a_wrap[0][0] - b_wrap[-1][0]) * j / tight,
                                              b_wrap[-1][1] + (a_wrap[0][1] - b_wrap[-1][1]) * j / tight)
                                             for j in range(1, tight))
                        # Cheap complete-profile check before solving the suspended strand.
                        probe = a_wrap + b_wrap + tight_points
                        air = min(air_at(point, phase_a, phase_b) for point in probe)
                        best_air = max(best_air, air)
                        if air < -_NUMERIC_MM:
                            continue
                        try:
                            slack = _catenary(a_wrap[-1], b_wrap[0], slack_count, gravity)
                        except _NumericStrandError:
                            numerical_refusals += 1
                            continue
                        except _SpanModelError:
                            span_refusals += 1
                            continue
                        pins = a_wrap + slack[1:-1] + b_wrap + tight_points
                        try:
                            require_pinned_cycle(pins, link_count=count)
                        except ValueError:
                            numerical_refusals += 1
                            continue
                        air = min(air, *(air_at(point, phase_a, phase_b) for point in slack))
                        best_air = max(best_air, air)
                        if air < -_NUMERIC_MM:
                            continue
                        b_first = seated_a + slack_count
                        junctions = ((0, step_a), (seated_a, step_a),
                                     (b_first, step_b), (b_first + seated_b, step_b))
                        if any(not _supported_turn(pins[index - 1], pins[index],
                                                   pins[(index + 1) % count], taut_side, limit)
                               for index, limit in junctions):
                            continue
                        segments = tuple((pins[i], pins[(i + 1) % count]) for i in range(count))
                        clearances = tuple(
                            (min(j - i, count - (j - i)),
                             _segment_distance(segments[i], segments[j]) - sprocket.ANSI_PLATE_HEIGHT)
                            for i in range(count) for j in range(i + 2, count)
                            if min(j - i, count - (j - i)) >= 2
                        )
                        plate_air = min(air for _, air in clearances)
                        backbend_air = min(air for separation, air in clearances if separation == 2)
                        strand_air = min(
                            _segment_distance(segments[i], segments[j]) - sprocket.ANSI_PLATE_HEIGHT
                            for i in range(seated_a, b_first)
                            for j in range(b_first + seated_b, count)
                        )
                        if plate_air < -_NUMERIC_MM:
                            continue
                        horizontal = -gravity[1], gravity[0]
                        up = -gravity[0], -gravity[1]
                        start, end = slack[0], slack[-1]
                        span_x = _dot(_sub(end, start), horizontal)
                        span_y = _dot(_sub(end, start), up)
                        sag = max(_dot(_sub(point, start), horizontal) / span_x * span_y
                                  - _dot(_sub(point, start), up) for point in slack)
                        half_height = sprocket.ANSI_PLATE_HEIGHT / 2.0
                        return ChainFit(knob_centre, crank_centre, na, nb, phase_a, phase_b, pins,
                                        tuple(range(seated_a + 1)), tuple(range(b_first, b_first + seated_b + 1)),
                                        tuple(range(seated_a, b_first + 1)), taut_side, gravity, sag, air, plate_air,
                                        backbend_air, strand_air,
                                        (min(point[0] for point in pins) - half_height,
                                         min(point[1] for point in pins) - half_height,
                                         max(point[0] for point in pins) + half_height,
                                         max(point[1] for point in pins) + half_height))
    raise ChainSearchUnqualified(f"UNQUALIFIED: no {count}-link pinned cycle found on 97 phase samples "
                     "(alpha +/-1 knob pitch, step=knob pitch/48; beta +/-1 crank pitch; "
                     "tangent tight/wrap counts +/-1) "
                     f"for centres {knob_centre}, {crank_centre}; "
                     f"necessary taut-length lower bound {bound:.6f} mm, available {count * pitch:.6f} mm, "
                     f"best examined root-to-tip roller air {best_air:.6f} mm, "
                     f"numeric strand/cycle refusals {numerical_refusals}, span-model refusals {span_refusals}; "
                     "no count or pitch substitution")


def transform_cycle(pins: tuple[Point, ...], rotation: tuple[Point, Point], translation: Point) -> tuple[Point, ...]:
    """Right-handed rigid XY transform; refuse a mirror or stretched frame."""
    first, second = rotation
    if (not all(math.isfinite(value) for row in (*rotation, translation) for value in row)
            or abs(_dot(first, first) - 1.0) > 1e-10
            or abs(_dot(second, second) - 1.0) > 1e-10
            or abs(_dot(first, second)) > 1e-10
            or abs(_cross(first, second) - 1.0) > 1e-10):
        raise ValueError("chain frame must be a right-handed rigid rotation")
    return tuple((_dot(first, point) + translation[0], _dot(second, point) + translation[1]) for point in pins)
