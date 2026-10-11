r"""Magnifying lever -> bracket collar PRESS FIT: the CONFIG-free constant block
shared by ``build_mg_magnifying_lever`` (the rod and its press zone),
``build_mg_magnifying_bracket`` (the collar bore), ``_interference_contracts``
(the allowed press triple) and the offline tests.

PURE DATA: no SolidWorks/COM, no drawing and NO ``_config`` imports.  Kept
SEPARATE from ``mg_magnifying_lever_geom`` on purpose: that module reads the
collar and clamp STATIONS from cad/config/machine/output.yaml, so a shared
contract importing it would drag output.yaml into every recipe closure that
only needs the fit (check:graph's pen-assembly closure must stay free of the
output config).  The stations stay there; the fit lives here, and the lever
geom asserts its configured collar window IS this zone, the rod's tip flush
with the collar's outer face.

p.46 "firmly affixed to the summing lever" (user ruling 2026-10-11): the rod's
last PRESS_ZONE_LENGTH is PRESSED into the bracket collar's bore and retained
with Loctite 638 (soft solder or braze the alternative).  The rod is modelled
at its nominal diameter end to end; the press zone carries its own band
natively on the lever print (stock-select or lap), the collar bore its band on
the bracket print -- both (upper, lower) deviations for ``_fit_deviations``.
``_interference_contracts`` restates the triple
(PRESS_ZONE_DIA, COLLAR_BORE_DIA, COLLAR_ENGAGEMENT) as literals its test pins
to these names.
"""

from __future__ import annotations

# --- rod stock (DIMENSIONS.md ch20; Ø6 photo-scaled, low) ---------------------
ROD_DIA = 6.0  # round brass rod, modelled at nominal end to end

# --- press zone (the rod's east end) and the collar bore it enters -----------
PRESS_ZONE_LENGTH = 10.0  # the rod's last 10 = the collar's length
PRESS_ZONE_DIA = ROD_DIA  # the model's rod, 6.000
PRESS_ZONE_DIA_BAND = (0.0, -0.008)  # (upper, lower): select or lap the stock
COLLAR_BORE_DIA = 5.976  # bored to size on the bracket
COLLAR_BORE_BAND = (0.008, 0.0)  # (upper, lower)
# End-flush: the rod's east dome tip sits flush with the collar's outer face
# (mg_magnifying_lever_geom asserts its configured window ends there), so the
# rod's cylinder, which ends where that dome starts (ROD_DIA / 2 back from the
# tip), is gripped from the collar's inner face over this much STRAIGHT rod;
# the dome's shrinking diameter inside the collar bears nothing.
COLLAR_ENGAGEMENT = PRESS_ZONE_LENGTH - ROD_DIA / 2.0
# ANSI B4.1 table 8, class FN2 (medium drive fit) for the rod's size range
# 0.12..0.24 in: 0.2 .. 1.0 thou of diametral interference. The heaviest press
# this joint may reach at its tightest band corner.
MM_PER_IN = 25.4
_FN2_SIZE_RANGE_IN = (0.12, 0.24)
PRESS_INTERFERENCE_MAX_FN2 = 0.0010 * MM_PER_IN


def press_fit_budget() -> dict[str, float]:
    """Worst-case diametral interference of the collar press (mm) from the two
    printed bands, and the straight engagement that interference acts over.
    ``interference_min`` is the loosest corner (smallest rod in the largest
    bore); ``interference_max`` the tightest."""
    rod_max = PRESS_ZONE_DIA + PRESS_ZONE_DIA_BAND[0]
    rod_min = PRESS_ZONE_DIA + PRESS_ZONE_DIA_BAND[1]
    bore_max = COLLAR_BORE_DIA + COLLAR_BORE_BAND[0]
    bore_min = COLLAR_BORE_DIA + COLLAR_BORE_BAND[1]
    return {
        "interference_nominal": PRESS_ZONE_DIA - COLLAR_BORE_DIA,
        "interference_min": rod_min - bore_max,
        "interference_max": rod_max - bore_min,
        "engagement": COLLAR_ENGAGEMENT,
    }


PRESS_FIT_BUDGET = press_fit_budget()
if not (
    _FN2_SIZE_RANGE_IN[0] * MM_PER_IN < PRESS_ZONE_DIA <= _FN2_SIZE_RANGE_IN[1] * MM_PER_IN
):
    raise AssertionError("PRESS_INTERFERENCE_MAX_FN2 is the 0.12..0.24 in row")
if PRESS_FIT_BUDGET["interference_min"] <= 0.0:
    raise AssertionError("the collar press must interfere at its loosest band corner")
if PRESS_FIT_BUDGET["interference_max"] > PRESS_INTERFERENCE_MAX_FN2 + 1e-9:
    raise AssertionError("the collar press exceeds ANSI FN2 at its tightest band corner")
if COLLAR_ENGAGEMENT <= 0.0 or COLLAR_ENGAGEMENT >= PRESS_ZONE_LENGTH:
    raise AssertionError("the dome must start inside the collar, past its inner face")
