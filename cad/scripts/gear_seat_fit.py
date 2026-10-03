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
  tight").  The flat carries the gear's clock, so its clearance is angular
  play: the gear turns clearance / half-chord on its land, and its channel's
  cam sees T/120 of that turn (error_budget.yaml cone_flat_play).

Its own small module so only its importers re-key.
"""

from __future__ import annotations

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
