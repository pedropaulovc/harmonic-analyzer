"""The fit class for a gear slid onto its land on MHA-DT-04.

The gears on the cone gear shaft slide onto their lands (owner decision C1
keyed, 2026-11-09, PR #1992, superseding the user ruling 2026-09-28 "D-flat
shaft and D-bores, no keys, no solder, no retaining compound"; no D-flat
remains).  Land 1 (the 64T and T030..T120) is keyed: a 1/16 square key in a
keyseat drives keyway-broached bores (cone_land_key).  T024 is a bonded slip
fit on the round land 2 (LOCTITE 638, cone_tip_cluster).  Both bore bands
derive from the land's published limits, so moving a land moves its bores:

* Round, .0010-.0038 in diametral.  The .0010 floor lets a novice's gear
  slide down its land to the stack.  The .0038 ceiling bounds the gear's
  runout on the land (half of it, radially); test_cone_gear_mesh_design and
  crank_mesh_stack book that runout against the meshes.  On the land's
  0/-.0020 band the bore prints +.0018/+.0010, which the owned over reamer
  (.2510, .3760) cuts.  On land 1 the key carries clock (cone_land_key's
  side clearances); on land 2 the bond does.

Its own small module so only its importers re-key.
"""

from __future__ import annotations

# (minimum, maximum) diametral clearance between a round bore and its land:
# .0010-.0038 in.
GEAR_SEAT_CLEARANCE = (0.0254, 0.09652)


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

