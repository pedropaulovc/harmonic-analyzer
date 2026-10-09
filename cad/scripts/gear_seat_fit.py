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
    shaft_diameter_limits_mm: tuple[float,float],
    shaft_across_flat_limits_mm: tuple[float,float],
    bore_across_flat_limits_mm: tuple[float,float],
) -> float:
    """Translation-independent free-clock OUTER for the retained round-backed D.

    Inputs are absolute (MIN, MAX), not deviation (upper, lower) bands.
    The flat retains at least half the shaft at every size corner. For
    r=radius, a=AF-r and c=sqrt(r*r-a*a), its width normal to the bore flat
    is r+a*cos(theta)+c*abs(sin(theta)) until the whole circle supports.
    Translation cannot change width, so that width must be <= bore AF.
    The FIRST width barrier bounds the component connected to actual home;
    a later 180-degree width branch is not a route through that barrier.

    Bigger shaft radius or AF gives a superset (after translating the round
    back to x=0); a bigger bore AF relaxes the inequality. Therefore the
    maximum over all independent bands occurs at rMIN, shaft AFMIN, bore
    AFMAX. This is not observed material twist or proof of loaded seating.
    Full solid containment and physical loading may narrow this OUTER.
    """
    for limits in (shaft_diameter_limits_mm,shaft_across_flat_limits_mm,bore_across_flat_limits_mm):
        if len(limits)!=2 or not all(math.isfinite(value) and value>0 for value in limits) or limits[0]>limits[1]:
            raise ValueError("clock bound needs finite positive absolute MIN/MAX limits")
    dmin,dmax = shaft_diameter_limits_mm
    amin,amax = shaft_across_flat_limits_mm
    bmin,bmax = bore_across_flat_limits_mm
    if amin<dmax/2 or amax>=dmin:
        raise ValueError("clock width law requires a proper round-backed D at every size corner")
    if bmin<amax:
        raise ValueError("AF limits do not guarantee connected-home assembly at every size corner")
    radius = dmin/2
    if bmax>=2*radius:
        return math.pi  # No width barrier; the full wrapped-angle OUTER.
    lower = (amin-radius)/radius
    upper = (bmax-radius)/radius
    # Pay normalization and asin endpoint arithmetic outward; unlike the
    # clearance/chord linearization, this never knowingly rounds inward.
    error = 32*math.ulp(1.0)*(1+abs(lower)+abs(upper))
    lower = max(-1.0,math.nextafter(lower-error,-math.inf))
    upper = min(1.0,math.nextafter(upper+error,math.inf))
    angle = math.asin(upper)-math.asin(lower)+64*math.ulp(math.pi)
    return min(math.pi,math.nextafter(angle,math.inf))
