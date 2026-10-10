"""The fit class for a gear slid onto its D-flat land on MHA-DT-004.

Every gear on the cone gear shaft -- the twenty cone gears and the 64T
crank-drive gear -- slides onto a D-flat land and bears on its neighbour.
None is bonded (user ruling 2026-09-28: D-flat shaft and D-bores, no keys,
no solder, no retaining compound).  Two clearances bound each seat, and both
bore bands derive from the land's published limits, so moving a land moves
its bores:

* Round, 0.025-0.105 diametral.  The 0.025 floor lets a novice's gear slide
  down its land to the stack.  The 0.105 ceiling bounds the gear's runout on
  the land (half of it, radially); test_cone_gear_mesh_design and
  crank_mesh_stack book that runout against the meshes.
* Across the flat, 0.01-0.03 (user ruling 2026-09-28, "interchangeable
  tight"). The flat carries clock; the exact connected-home width barrier
  below bounds its play. Clearance divided by half-chord is only a linear
  approximation, not an angular bound. A channel's cam sees T/120 of the turn.

Its own small module so only its importers re-key.
"""

from __future__ import annotations

import math

# (minimum, maximum) diametral clearance between a round bore and its land.
GEAR_SEAT_CLEARANCE = (0.025, 0.105)
# (minimum, maximum) clearance between a bore's across-flat and its land's.
FLAT_AF_CLEARANCE = (0.010, 0.030)


def _bore_band(
    land_band: tuple[float, float], clearance: tuple[float, float]
) -> tuple[float, float]:
    """(upper, lower) bore deviations that keep ``clearance`` on ``land_band``.

    Both share the land's nominal.  The smallest bore on the largest land keeps
    the minimum clearance, the largest bore on the smallest land the maximum.
    """
    land_upper, land_lower = land_band
    clearance_min, clearance_max = clearance
    return (
        round(land_lower + clearance_max, 6),
        round(land_upper + clearance_min, 6),
    )


def seat_bore_band(land_band: tuple[float, float]) -> tuple[float, float]:
    """(upper, lower) round-bore deviations for a land's (upper, lower) band."""
    return _bore_band(land_band, GEAR_SEAT_CLEARANCE)


def flat_bore_af_band(land_af_band: tuple[float, float]) -> tuple[float, float]:
    """(upper, lower) bore across-flat deviations for a land's across-flat band."""
    return _bore_band(land_af_band, FLAT_AF_CLEARANCE)


def connected_home_clock_angle_bound_rad(
    shaft_diameter_limits_mm: tuple[float, float],
    shaft_across_flat_limits_mm: tuple[float, float],
    bore_across_flat_limits_mm: tuple[float, float],
    *,
    edge_break_mm: float,
) -> float:
    """First connected-home free-clock OUTER including allowed C/R removal.

    Inputs are absolute printed (MIN,MAX). The bore must contain the retained
    round-backed D at home. This necessary width law is independent of rigid
    translation; it is not observed twist, torque seating or an INNER.

    With r=D/2, h=A-r and c=sqrt(A*(D-A)), a MAX C=e leaves a flat witness
    at y=c-e. A TRUE internal circular R=e tangent to the flat and round back
    leaves y=sqrt((A-2e)*(D-A)); its setback can exceed e. Pay the smaller
    witness and use W=r+h*cos(theta)+y*sin(theta). The untouched back-circle
    extremum supplies the opposite support up to the explicitly bounded arc.
    The first ascending W=B barrier disconnects home from later width fits.

    On that ascending branch W increases with r and A, so the largest first
    barrier uses DMIN, shaft AFMIN, bore AFMAX. If no retained witness/barrier
    is certified, report the universal wrapped-angle OUTER pi, never zero.
    """
    for limits in (shaft_diameter_limits_mm, shaft_across_flat_limits_mm,
                   bore_across_flat_limits_mm):
        if (len(limits) != 2
                or not all(math.isfinite(value) and value > 0 for value in limits)
                or limits[0] > limits[1]):
            raise ValueError("clock bound needs finite positive absolute MIN/MAX limits")
    if not math.isfinite(edge_break_mm) or edge_break_mm < 0:
        raise ValueError("clock bound needs a finite nonnegative edge break")
    dmin, dmax = shaft_diameter_limits_mm
    amin, amax = shaft_across_flat_limits_mm
    bmin, bmax = bore_across_flat_limits_mm
    if amin < dmax / 2 or amax >= dmin:
        raise ValueError("clock width law requires a proper round-backed D at every size corner")
    if bmin < amax:
        raise ValueError("AF limits do not guarantee connected-home assembly at every size corner")
    radius = dmin / 2
    edge = edge_break_mm
    if bmax >= dmin or edge >= amin / 2:
        return math.pi
    chord = math.sqrt(amin * (dmin - amin))
    retained = min(chord - edge, math.sqrt((amin - 2 * edge) * (dmin - amin)))
    if retained <= 0:
        return math.pi

    # Enclose the earliest removed round-back arc over ALL shaft-size corners.
    # For C its cut x is >=h-e. For R the circle tangency has
    # x=r*(h-e)/(r-e), decreasing with r and increasing with A when A>2e.
    largest_radius = dmax / 2
    smallest_offset = amin - largest_radius
    arc_cut = min(smallest_offset - edge,
                  largest_radius * (smallest_offset - edge) / (largest_radius - edge))
    arithmetic = 128 * math.ulp(1.0) * (1 + dmax + amax + bmax + edge)
    arc_cut = math.nextafter(arc_cut - arithmetic, -math.inf)
    if arc_cut <= -radius:
        return math.pi
    safe = math.pi / 2 if arc_cut >= 0 else math.acos(min(1.0, -arc_cut / radius))
    safe = math.nextafter(safe - 64 * math.ulp(math.pi), -math.inf)

    # Lower the necessary width, moving its first barrier outward. The guard
    # covers these elementary operations; final inverse-angle rounding is up.
    rlow = math.nextafter(radius - arithmetic, -math.inf)
    hlow = max(0.0, math.nextafter(amin - radius - arithmetic, -math.inf))
    ylow = math.nextafter(retained - arithmetic, -math.inf)
    if rlow <= 0 or ylow <= 0:
        return math.pi
    amplitude = math.hypot(hlow, ylow)
    ratio = math.nextafter((bmax - rlow) / amplitude, math.inf)
    if ratio >= 1:
        return math.pi
    angle = (math.asin(max(-1.0, ratio)) - math.atan2(hlow, ylow)
             + 128 * math.ulp(math.pi))
    angle = math.nextafter(max(0.0, angle), math.inf)
    if angle >= safe:
        return math.pi
    return min(math.pi, angle)
