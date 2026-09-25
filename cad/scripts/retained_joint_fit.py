"""The shared fit class for a gear bonded to its shaft land.

Every bonded gear-to-shaft joint in the machine (the 20 cone gears and the
64T crank-drive gear on MHA-014: solder, silver-braze or Loctite 638/648)
takes its bore band from the land under it through this one class, never a
per-part literal (Main ruling, 2026-09-25).

The diametral clearance window follows Henkel's retaining-compound data:
0.025-0.15 mm is the thin-product optimum and 0.15 mm is Loctite 648's
gap-fill limit.  The 0.025 floor lets a novice's gear start on its land and
leaves the compound (or solder) a gap to fill; the 0.105 ceiling stays well
inside the 0.15 cap.  Its own small module so only its importers re-key.
"""

from __future__ import annotations

# (minimum, maximum) diametral clearance between a bonded bore and its land.
RETAINED_JOINT_CLEARANCE = (0.025, 0.105)


def bonded_bore_band(land_band: tuple[float, float]) -> tuple[float, float]:
    """Return the (upper, lower) bore deviations that bond on ``land_band``.

    ``land_band`` is the land's (upper, lower) diameter deviations; both share
    the land's nominal.  The smallest bore on the largest land keeps the
    minimum clearance, the largest bore on the smallest land the maximum.
    """
    land_upper, land_lower = land_band
    clearance_min, clearance_max = RETAINED_JOINT_CLEARANCE
    return (
        round(land_lower + clearance_max, 6),
        round(land_upper + clearance_min, 6),
    )
