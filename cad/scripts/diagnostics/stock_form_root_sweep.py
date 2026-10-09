"""Continuous collision-only sweep of actual finite driven surfaces and caps.

FREE INNER is proved by continuous source-speed boxes. FREE OUTER is constrained
only by actual material points, never by fictitious radial-fan material. The
RootAngularDomain owns all translated-root, tangent and pitch-seam geometry.
Source/pose uncertainty is irreducible and separate from subdivision error.
Root arcs, floors, lobes and their joins supply no working coverage or TE.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
import sys
from typing import TYPE_CHECKING

from diagnostics.stock_form_root_angles import (
    RootAngularDomain,
    intersect_intervals,
    merge_intervals,
)

if TYPE_CHECKING:
    from typing import Protocol, Sequence

    class RootSearch(Protocol):
        """ContactSearch's pure geometry interface; no runtime engine import."""

        case: object
        placement: object
        gap: object
        phase: float
        seed: float
        pitch: float
        radial_error_mm: float
        axial_error_mm: float
        driven_teeth: tuple[int, ...]
        segments: Sequence[object]

        def point(self, segment, tooth: int, t: float, s: float): ...
        def second_speed(self, segment) -> float: ...
        def surface_member(self, segment, t: float, s: float) -> bool: ...
        def cap_removed(self, segment, t: float, s: float, rho: float) -> bool: ...


Intervals = tuple[tuple[float, float], ...]


@dataclass(frozen=True)
class RootMaterialWitness:
    """Material evidence for the source outer-profile solid, not native bores."""

    driven_tooth: int | None
    segment: str
    parameter: float | None
    second_parameter: float | None
    physical_station_mm: float
    world_point_mm: tuple[float, float, float]
    driver_local_point_mm: tuple[float, float, float]
    forbidden_offsets: Intervals
    collision_at_declared_phase: bool
    proof: str
    driven_actual_material_member: bool = True


@dataclass(frozen=True)
class RootEnclosureUncertainty:
    """A possible forbidden set, NOT an actual collision witness."""

    driven_tooth: int
    segment: str
    parameter_box: tuple[float, float, float, float]
    radial_interval_mm: tuple[float, float]
    axial_interval_mm: tuple[float, float]
    possible_forbidden_offsets: Intervals
    midpoint_is_actual_material: bool


@dataclass(frozen=True)
class RootSweepBounds:
    """Source outer-solid bounds; native holes are not invented or certified."""

    free_inner: Intervals
    free_outer: Intervals
    offset_domain_rad: tuple[float, float]
    angular_uncertainty_rad: float
    driver_pitch_displacement_uncertainty_mm: float
    geometric_uncertainty_mm: float
    radial_error_mm: float
    axial_error_mm: float
    required_root_air_mm: float
    root_air_lower_bound_mm: float | None
    root_max_radial_clearance_screen_mm: float | None
    witnesses: tuple[RootMaterialWitness, ...]
    enclosure_uncertainty: tuple[RootEnclosureUncertainty, ...]
    uncertain_boxes: int
    boxes: int
    status: str
    containment_proof: str
    reason: str = ""
    root_is_carrying: bool = False
    native_solid_certificate: bool = False


@dataclass(frozen=True)
class _Box:
    index: int
    tooth: int
    limits: tuple[float, float, float, float]
    possible: Intervals
    evidence: RootEnclosureUncertainty


def _difference(left: Intervals, right: Intervals, *, preserve_touching_points=False) -> Intervals:
    """Interval subtraction; OUTER retains shared endpoints of open exclusions."""
    result = []
    for lo, hi in left:
        cursor = lo
        for a, b in right:
            if b <= cursor:
                continue
            if a >= hi:
                break
            if a > cursor:
                result.append((cursor, min(a, hi)))
            elif preserve_touching_points and a == cursor and lo < cursor < hi:
                # OUTER may include extra forbidden offsets; a one-ULP outward
                # enclosure preserves the shared point without zero-width
                # components that downstream interval consumers discard.
                result.append((max(lo, math.nextafter(cursor, -math.inf)),
                               min(hi, math.nextafter(cursor, math.inf))))
            cursor = max(cursor, b)
            if cursor >= hi:
                break
        if cursor < hi:
            result.append((cursor, hi))
    return tuple(result)


def _merge_forbidden(intervals) -> Intervals:
    """Open certified exclusions may overlap, but touching endpoints stay FREE."""
    merged = []
    for lo, hi in sorted((float(a), float(b)) for a, b in intervals if a < b):
        if merged and lo < merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], hi))
        else:
            merged.append((lo, hi))
    return tuple(merged)


def _width(intervals: Intervals) -> float:
    return math.fsum(hi - lo for lo, hi in intervals)


def _angle_error(radius: float, error: float) -> float:
    # A ball containing the polar origin covers ALL angles, not asin(1).
    return math.pi if error >= radius else math.asin(error / radius)


def _cap(segment) -> bool:
    return segment.kind == "axial_face"


def _local(world, origin, frame) -> tuple[float, float, float]:
    return tuple(math.fsum((world[j] - origin[j]) * frame[j][i]
                           for j in range(3)) for i in range(3))


def _validate(search: RootSearch, maximum_error_mm: float, max_boxes: int,
              required_root_air_mm: float):
    if not math.isfinite(maximum_error_mm) or maximum_error_mm <= 0:
        raise ValueError("maximum_error_mm must be finite and positive")
    if type(max_boxes) is not int or max_boxes < 1:
        raise ValueError("max_boxes must be a positive integer")
    if not math.isfinite(required_root_air_mm) or required_root_air_mm < 0:
        raise ValueError("required_root_air_mm must be finite and nonnegative")
    driver, driven, p = search.case.driver, search.case.driven, search.placement
    for value in (search.pitch, driver.pitch_radius_mm, driver.root_radius_min_mm):
        if not math.isfinite(value) or value <= 0:
            raise ValueError("positive finite driver pitch and root required")
    for value in (search.phase, search.seed, *p.driver_origin_mm, *p.driven_origin_mm,
                  *p.driver_face_mm, *p.driven_face_mm):
        if not math.isfinite(value):
            raise ValueError("finite explicit placement and phase required")
    if search.pitch != driver.angular_pitch_rad:
        raise ValueError("search pitch must be the actual physical driver pitch")
    for value in (search.radial_error_mm, search.axial_error_mm,
                  driver.geometry_error_bound_mm, driven.geometry_error_bound_mm):
        if not math.isfinite(value) or value < 0:
            raise ValueError("source/radial/axial enclosures must be nonnegative finite")
    if (p.driver_face_mm[0] >= p.driver_face_mm[1]
            or p.driven_face_mm[0] >= p.driven_face_mm[1]):
        raise ValueError("nonempty actual face intervals required")
    if (math.isnan(p.driver_shoulder_z_mm) or p.driver_shoulder_z_mm == -math.inf
            or math.isnan(p.driver_turned_radius_mm) or p.driver_turned_radius_mm <= 0):
        raise ValueError("shoulder must be finite or +inf; turned radius positive or +inf")
    for frame in (p.driver_frame, p.driven_frame):
        for i in range(3):
            for j in range(3):
                product = math.fsum(frame[k][i] * frame[k][j] for k in range(3))
                if not math.isfinite(product) or abs(product - (i == j)) > 1e-12:
                    raise ValueError("explicit orthonormal frames required")
        determinant = math.fsum((
            frame[0][0] * (frame[1][1] * frame[2][2] - frame[1][2] * frame[2][1]),
            -frame[0][1] * (frame[1][0] * frame[2][2] - frame[1][2] * frame[2][0]),
            frame[0][2] * (frame[1][0] * frame[2][1] - frame[1][1] * frame[2][0]),
        ))
        if determinant < 0:
            raise ValueError("right-handed source frames required")
    if (len(search.driven_teeth) != driven.teeth
            or any(type(t) is not int for t in search.driven_teeth)
            or set(search.driven_teeth) != set(range(driven.teeth))):
        raise ValueError("root sweep requires ALL actual physical driven teeth")
    perimeter = driven.external_boundary_segments()
    expected = {(s.name, s.kind) for s in perimeter}
    actual = {(s.name, s.kind) for s in search.segments if not _cap(s)}
    if not expected or actual != expected or len(actual) != len(perimeter):
        raise ValueError("complete source-owned driven perimeter required")
    for source in perimeter:
        for station in p.driven_face_mm:
            fans = [s for s in search.segments if _cap(s)
                    and s.boundary.name == source.name and s.station_mm == station]
            if len(fans) != 1:
                raise ValueError("every real perimeter piece needs both actual material cap fans")
    if len(search.segments) != 3 * len(perimeter):
        raise ValueError("only the actual perimeter and its two material cap inventories are accepted")
    for segment in search.segments:
        for value in (segment.speed_bound_mm, search.second_speed(segment)):
            if not math.isfinite(value) or value < 0:
                raise ValueError("finite nonnegative source parameter speed bounds required")


def _containment(search: RootSearch, full: Intervals, required_root_air_mm: float):
    """Exclude driver-inside-driven, or refuse it with a grounded axis witness.

    Nonfolding source RootArc material is connected through its positive inner
    disk, including the optional positive-radius shoulder band. An axis point
    outside the entire driven finite cylinder excludes its full containment.
    If the connected root set overlaps without being contained, the complete
    driven boundary must intersect it and the continuous sweep detects it.
    """
    driven, p = search.case.driven, search.placement
    # Directional errors are DRIVER-frame cylinder components. Containment
    # queries are in the DRIVEN frame, so crossing axes mixes axial/radial pay.
    cross = tuple(
        p.driver_frame[(j + 1) % 3][2] * p.driven_frame[(j + 2) % 3][2]
        - p.driver_frame[(j + 2) % 3][2] * p.driven_frame[(j + 1) % 3][2]
        for j in range(3)
    )
    sine = min(1.0, math.sqrt(math.fsum(c * c for c in cross)) + 64 * sys.float_info.epsilon)
    radial = (search.radial_error_mm + search.axial_error_mm * sine
              + driven.geometry_error_bound_mm)
    axial = (search.axial_error_mm + search.radial_error_mm * sine
             + driven.geometry_error_bound_mm)
    candidates = []
    for fraction in (0.0, 0.25, 0.5, 0.75, 1.0):
        z = p.driver_face_mm[0] + fraction * (p.driver_face_mm[1] - p.driver_face_mm[0])
        world = tuple(p.driver_origin_mm[j] + p.driver_frame[j][2] * z for j in range(3))
        q = _local(world, p.driven_origin_mm, p.driven_frame)
        arithmetic = 128 * sys.float_info.epsilon * (1 + sum(map(abs, world)) + sum(map(abs, q)))
        r = math.hypot(q[0], q[1])
        if (r > driven.blank_radius_mm + radial + arithmetic + required_root_air_mm
                or q[2] < p.driven_face_mm[0] - axial - arithmetic - required_root_air_mm
                or q[2] > p.driven_face_mm[1] + axial + arithmetic + required_root_air_mm):
            return "driver-root axis point outside paid driven finite cylinder", None
        # Inside the core's actual central material disk is an offset-invariant
        # collision. Neither an uncertain gap membership nor a fan is enough.
        if (p.driver_face_mm[0] < z < p.driver_face_mm[1]
                and r + radial + arithmetic < driven.root_radius_min_mm
                and p.driven_face_mm[0] + axial + arithmetic < q[2]
                < p.driven_face_mm[1] - axial - arithmetic
                and driven.contains_material(q[0], q[1])):
            candidates.append(RootMaterialWitness(
                None, "driver-axis containment", None, None, q[2], world,
                (0.0, 0.0, z), full, True,
                "driver root-axis interior lies inside the actual driven central material disk and faces for every paid pose",
            ))
    if candidates:
        return "offset-invariant interior material witness", candidates[0]
    return "driver-inside-driven containment not excluded; conservative refusal", None


def root_free_intervals(
    search: RootSearch, *, maximum_error_mm: float = 0.001, max_boxes: int = 500000,
    required_root_air_mm: float = 0.0,
) -> RootSweepBounds:
    """Enclose FREE inverse driver offsets over the complete physical pitch.

    ``resolved`` means the continuous-box excess over uncertainty-paid material
    point domains is at most ``maximum_error_mm`` on the driver pitch circle.
    It does NOT mean that source/pose uncertainty vanished: the entire remaining
    INNER/OUTER gap is returned and paid. All other statuses have empty INNER.
    ``required_root_air_mm`` inflates the collision query by a 3D clearance ball,
    paying radial, angular and axial distances independently. Its guarantee is
    conditional on an offset in FREE INNER, not on a root-MAX disk screen.
    """
    full: Intervals = ()
    witnesses: list[RootMaterialWitness] = []
    leaves: list[_Box] = []
    count = 0
    proof = "not established"
    guaranteed: Intervals = ()
    reference: Intervals = ()
    has_nominal_collision = False
    radial_air = math.inf
    geometric = math.inf
    try:
        _validate(search, maximum_error_mm, max_boxes, required_root_air_mm)
        pitch, radius = search.pitch, search.case.driver.pitch_radius_mm
        full = ((-pitch / 2, pitch / 2),)
        domain = RootAngularDomain(search.case.driver, search.gap)
        proof, containment_witness = _containment(search, full, required_root_air_mm)
        if containment_witness is not None:
            witnesses.append(containment_witness)
            return RootSweepBounds(
                free_inner=(), free_outer=(), offset_domain_rad=full[0],
                angular_uncertainty_rad=0.0, driver_pitch_displacement_uncertainty_mm=0.0,
                geometric_uncertainty_mm=0.0, radial_error_mm=search.radial_error_mm,
                axial_error_mm=search.axial_error_mm, required_root_air_mm=required_root_air_mm,
                root_air_lower_bound_mm=None, root_max_radial_clearance_screen_mm=None,
                witnesses=tuple(witnesses), enclosure_uncertainty=(), uncertain_boxes=0,
                boxes=0, status="contained_collision", containment_proof=proof,
            )
        if proof.startswith("driver-inside-driven"):
            return RootSweepBounds(
                free_inner=(), free_outer=full, offset_domain_rad=full[0],
                angular_uncertainty_rad=pitch, driver_pitch_displacement_uncertainty_mm=radius * pitch,
                geometric_uncertainty_mm=math.inf, radial_error_mm=search.radial_error_mm,
                axial_error_mm=search.axial_error_mm, required_root_air_mm=required_root_air_mm,
                root_air_lower_bound_mm=None, root_max_radial_clearance_screen_mm=None,
                witnesses=(), enclosure_uncertainty=(), uncertain_boxes=0, boxes=0,
                status="containment_refused", containment_proof=proof,
                reason="surface noncrossing cannot prove absence of interior root overlap",
            )
        p = search.placement
        source_error = search.case.driven.geometry_error_bound_mm

        def point_domain(local, rho, air=required_root_air_mm):
            r = math.hypot(local[0], local[1])
            arithmetic = 128 * sys.float_info.epsilon * (1 + sum(map(abs, local)))
            radial = rho + search.radial_error_mm + source_error + arithmetic + air
            axial = rho + search.axial_error_mm + source_error + arithmetic + air
            rlo, rhi = max(0.0, r - radial), r + radial
            zlo, zhi = local[2] - axial, local[2] + axial
            if zhi < p.driver_face_mm[0] or zlo > p.driver_face_mm[1]:
                return None
            if zlo > p.driver_shoulder_z_mm:
                if rlo > p.driver_turned_radius_mm:
                    return None
                rhi = min(rhi, p.driver_turned_radius_mm)
            theta = math.atan2(local[1], local[0]) + search.seed - search.phase - pitch / 2
            bound = domain.offset_bounds(rlo, rhi, theta, _angle_error(r, radial), root_only=True)
            guaranteed_axial = (p.driver_face_mm[0] < zlo and zhi < p.driver_face_mm[1]
                                and (zhi <= p.driver_shoulder_z_mm
                                     or r + radial <= p.driver_turned_radius_mm))
            return bound, (zlo, zhi), guaranteed_axial, rlo - domain.root_max

        def actual_point(segment, tooth, t, s):
            world, local = search.point(segment, tooth, t, s)
            world, local = tuple(map(float, world)), tuple(map(float, local))
            if len(world) != 3 or len(local) != 3 or not all(map(math.isfinite, (*world, *local))):
                raise ValueError("source point must return finite actual world and driver-local triples")
            return world, local

        def record_material_point(segment, tooth, t, s, world, local):
            nonlocal guaranteed, reference, has_nominal_collision
            if not search.surface_member(segment, t, s):
                return
            midpoint = point_domain(local, 0.0)
            if midpoint is None:
                return
            point_bound, _, admitted, _ = midpoint
            reference = merge_intervals((*reference, *_difference(full, point_bound.inner)))
            forbidden = _difference(full, point_bound.outer) if admitted else ()
            added = bool(_difference(forbidden, guaranteed))
            point_radius = math.hypot(local[0], local[1])
            theta = math.atan2(local[1], local[0]) + search.seed - search.phase - pitch / 2
            nominal = domain.offset_bounds(point_radius, point_radius, theta, 0.0, root_only=True)
            actual = (
                p.driver_face_mm[0] < local[2] < p.driver_face_mm[1]
                and (local[2] <= p.driver_shoulder_z_mm or point_radius <= p.driver_turned_radius_mm)
                and any(a < 0.0 < b for a, b in _difference(full, nominal.outer))
                and search.case.driver.contains_material(
                    local[0], local[1], rotate_rad=-search.seed + search.phase + pitch / 2)
            )
            if not added and not (actual and not has_nominal_collision):
                return
            guaranteed = _merge_forbidden((*guaranteed, *forbidden))
            has_nominal_collision = has_nominal_collision or actual
            witness_proof = (
                "actual driven material point; paid clearance-inflated root-only OUTER complement and strict axial/shoulder admission"
                if added else
                "actual nominal root-material collision at declared phase; paid pose-domain collision not certified"
            )
            witnesses.append(RootMaterialWitness(
                tooth, segment.name, t, s, segment.station_mm if _cap(segment) else s,
                world, local, forbidden, actual, witness_proof,
            ))

        def evaluate(index, tooth, limits, *, initial=False):
            nonlocal count, radial_air
            count += 1
            segment = search.segments[index]
            t0, t1, s0, s1 = limits
            t, s = (t0 + t1) / 2, (s0 + s1) / 2
            world, local = actual_point(segment, tooth, t, s)
            rho = segment.speed_bound_mm * (t1 - t0) / 2 + search.second_speed(segment) * (s1 - s0) / 2
            if search.cap_removed(segment, t, s, rho):
                return None
            enclosed = point_domain(local, rho)
            if enclosed is None:
                return None
            bound, axial, _, air = enclosed
            radial_air = min(radial_air, air)
            possible = _difference(full, bound.inner)
            if not possible:
                return None
            member = bool(search.surface_member(segment, t, s))
            record_material_point(segment, tooth, t, s, world, local)
            if initial:
                # Exact source joins/endpoints catch zero-T floor tangencies.
                # These are point constraints only; INNER still comes entirely
                # from continuous speed boxes, never from finite sampling.
                for a, b in ((t0, s0), (t0, s), (t0, s1), (t, s0),
                             (t, s1), (t1, s0), (t1, s), (t1, s1)):
                    point_world, point_local = actual_point(segment, tooth, a, b)
                    record_material_point(segment, tooth, a, b, point_world, point_local)
            return _Box(index, tooth, limits, possible, RootEnclosureUncertainty(
                tooth, segment.name, limits, bound.radial_interval_mm, axial, possible, member))

        for index, segment in enumerate(search.segments):
            station = (0.0, 1.0) if _cap(segment) else p.driven_face_mm
            for tooth in search.driven_teeth:
                if count >= max_boxes:
                    raise _BudgetExhausted("budget does not cover the complete initial driven surface/cap inventory")
                box = evaluate(index, tooth, (0.0, 1.0, *station), initial=True)
                if box is not None:
                    leaves.append(box)
        while True:
            possible = merge_intervals(interval for box in leaves for interval in box.possible)
            residual = _difference(possible, reference)
            geometric = radius * _width(residual)
            if geometric <= maximum_error_mm:
                status, reason = "resolved", ""
                break
            ranked = sorted(((_width(intersect_intervals(box.possible, residual)), i)
                             for i, box in enumerate(leaves)), reverse=True)
            selected = [i for width, i in ranked[:max(16, len(leaves) // 2)] if width > 0]
            if not selected or count + 2 > max_boxes:
                raise _BudgetExhausted("continuous root/cap enclosure remains wider than the geometric allowance")
            replacements = []
            removed = set()
            for i in selected:
                if count + 2 > max_boxes:
                    break
                box = leaves[i]
                segment = search.segments[box.index]
                t0, t1, s0, s1 = box.limits
                if segment.speed_bound_mm * (t1 - t0) >= search.second_speed(segment) * (s1 - s0):
                    middle = (t0 + t1) / 2
                    children = ((t0, middle, s0, s1), (middle, t1, s0, s1))
                    splittable = t0 < middle < t1
                else:
                    middle = (s0 + s1) / 2
                    children = ((t0, t1, s0, middle), (t0, t1, middle, s1))
                    splittable = s0 < middle < s1
                if not splittable:
                    continue
                removed.add(i)
                for limits in children:
                    child = evaluate(box.index, box.tooth, limits)
                    if child is not None:
                        replacements.append(child)
            if not removed:
                raise _BudgetExhausted("source parameter boxes cannot be refined further")
            leaves = [box for i, box in enumerate(leaves) if i not in removed] + replacements
        inner = _difference(full, possible)
    except _BudgetExhausted as error:
        status, reason, inner = "budget_exhausted", str(error), ()
    except (ValueError, TypeError, AttributeError, IndexError, OverflowError, ZeroDivisionError) as error:
        status, reason, inner = "invalid", str(error), ()
        # An invalid source cannot certify even the accumulated outer exclusions.
        guaranteed = ()
        witnesses.clear()
    outer = _difference(full, guaranteed, preserve_touching_points=True)
    uncertainty = _width(_difference(outer, inner)) if full else math.inf
    radius = getattr(getattr(getattr(search, "case", None), "driver", None), "pitch_radius_mm", math.inf)
    uncertain = [box for box in leaves if _difference(box.possible, guaranteed)]
    return RootSweepBounds(
        free_inner=inner, free_outer=outer, offset_domain_rad=full[0] if full else (0.0, 0.0),
        angular_uncertainty_rad=uncertainty,
        driver_pitch_displacement_uncertainty_mm=radius * uncertainty,
        geometric_uncertainty_mm=geometric,
        radial_error_mm=getattr(search, "radial_error_mm", math.inf),
        axial_error_mm=getattr(search, "axial_error_mm", math.inf),
        required_root_air_mm=required_root_air_mm,
        root_air_lower_bound_mm=required_root_air_mm if inner and status == "resolved" else None,
        root_max_radial_clearance_screen_mm=radial_air if math.isfinite(radial_air) else None,
        witnesses=tuple(witnesses),
        enclosure_uncertainty=tuple(box.evidence for box in uncertain[:32]),
        uncertain_boxes=len(uncertain), boxes=count, status=status,
        containment_proof=proof, reason=reason,
    )


class _BudgetExhausted(Exception):
    pass
