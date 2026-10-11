r"""Magnifying-lever nominal geometry -- the drawing-FREE constant block shared
by the part build, its ``_spec`` (drawing contract), ``build_mg_magnifying_bracket``
(which imports the collar it presses onto) and ``build_mg_magnifier_assembly``
(which imports the knife-axis station).

PURE DATA, no SolidWorks/COM and no drawing imports.  Kept SEPARATE from
``magnifying_lever_spec`` on purpose (the ``column_clamp_front_geom`` precedent):
the assembly depends -- via ``_buildgraph.module_deps_of`` -- on whatever module
it imports a constant from, so the drawing contract (notes / marked-dimension
map) must NOT live here, else a print-note edit would move the assembly's recipe
digest and force a needless rebuild.  ``_spec`` re-exports these for its
drawing-side consumers and adds only the drawing data.
"""

from __future__ import annotations

import _config

# --- rod nominals (DIMENSIONS.md ch20; Ø6 photo-scaled, low) ------------------
ROD_LENGTH = 165.0  # calibrated p1, x -200..-35 (med; supersedes the 310 "4x" guess)
ROD_DIA = 6.0  # round brass rod (low)

# --- knife-edge pivot axis (KnifeAxis = Axis2) --------------------------------
# The lever does NOT spin in the bracket collar: it EXTENDS FROM the pivoted
# summing bar and pivots WITH it about the knife-edge ridge (engineerguy video
# 2/4 + 4/4; the tip draws a ~6 mm arc, and the clamp's position along the rod --
# the radius from this pivot -- is what sets the <=4x magnification). The ridge
# line runs along Z at machine (pre-mirror) (15, 984.834); in lever-local coords
# (assembly placement (-200, 979.7, -128.3), rod along +X) that is (215, 5.134).
# Duplicated literals -- build_mg_magnifier_assembly asserts them against
# build_sm_summing_assembly's KNIFE/KNIFE_CONTACT_Y and its own placement.
KNIFE_LOCAL_X = 215.0
KNIFE_LOCAL_Y = 5.134

# --- clamp travel along the rod = the magnification range ---------------------
# The sliding clamp (mg_magnifying_clamp_geom.BLOCK_DEPTH along the rod) rides the
# rod between its free west tip (local 0) and the bracket collar that carries
# the rod at its east end. Its radius from the knife axis, over the summing
# lever's spring-hook arm, is the magnification the operator sets (book p. 46:
# "up to 4x"); the reachable band is what cad/scripts/error_budget.py derives
# the pen scale and the ordinate-capacity rule from.
#
# The stations are OWNED by cad/config/machine/output.yaml (output.magnifier_*)
# -- the output chain's subsystem file, beside magnify_factor -- and this module
# is only the read point the part build, build_mg_magnifier_assembly (which
# derives its bracket/clamp placements from them, so a layout move fails loud
# there) and the offline error budget share, so none copies a literal.
# Lever-local x (rod along +X, knife at KNIFE_LOCAL_X).
COLLAR_LOCAL_X: float = float(
    _config.machine("output", "magnifier_collar_station_mm")
)  # bracket collar centre on the rod (machine x +40)
COLLAR_HALF_LEN: float = float(
    _config.machine("output", "magnifier_collar_half_len_mm")
)  # == build_mg_magnifying_bracket.COLLAR_HALF_LEN (asserted)
CLAMP_LOCAL_X: float = float(
    _config.machine("output", "magnifier_clamp_station_mm")
)  # as-built clamp centre (machine x +150, p.46/48 insets)

# --- bracket collar press fit (the MHA-MG-001 collar on this rod's east end) ---
# p.46 "firmly affixed to the summing lever" (user ruling 2026-10-11): the rod's
# last PRESS_ZONE_LENGTH is PRESSED into the bracket collar's bore and retained
# with Loctite 638 (soft solder or braze the alternative), its east dome tip
# flush with the collar's outer face. The rod is modelled at its nominal
# diameter end to end; the press zone carries its own band natively on the
# lever print (stock-select or lap), and the collar bore its band on the
# bracket print -- both (upper, lower) deviations for _fit_deviations. The
# bracket build imports the bore from HERE (as it does COLLAR_HALF_LEN) so the
# joint has ONE read point, and _interference_contracts restates the triple
# (PRESS_ZONE_DIA, COLLAR_BORE_DIA, COLLAR_ENGAGEMENT) as literals its test
# pins to these names.
PRESS_ZONE_DIA = ROD_DIA  # the model's rod, 6.000
PRESS_ZONE_DIA_BAND = (0.0, -0.008)  # (upper, lower): select or lap the stock
PRESS_ZONE_X = (COLLAR_LOCAL_X - COLLAR_HALF_LEN, COLLAR_LOCAL_X + COLLAR_HALF_LEN)
PRESS_ZONE_LENGTH = PRESS_ZONE_X[1] - PRESS_ZONE_X[0]  # the collar's length
COLLAR_BORE_DIA = 5.976  # bored to size on the bracket
COLLAR_BORE_BAND = (0.008, 0.0)  # (upper, lower)
# The rod's cylinder ends where its east dome starts (ROD_LENGTH - ROD_DIA / 2),
# so the collar grips this much STRAIGHT rod from its inner face; the dome's
# shrinking diameter inside the collar bears nothing.
COLLAR_ENGAGEMENT = (ROD_LENGTH - ROD_DIA / 2.0) - PRESS_ZONE_X[0]
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
if abs(ROD_LENGTH - PRESS_ZONE_X[1]) > 1e-9:
    raise AssertionError("the rod's east tip must end flush with the collar's outer face")
if COLLAR_ENGAGEMENT <= 0.0 or COLLAR_ENGAGEMENT >= PRESS_ZONE_LENGTH:
    raise AssertionError("the dome must start inside the collar, past its inner face")


def clamp_radius_band(block_depth: float) -> tuple[float, float, float]:
    """(min, as-built, max) knife -> clamp-centre radius, mm, for a clamp of
    ``block_depth`` along the rod: the block face against the collar face
    (minimum magnification), the as-built pose, the block flush with the rod
    tip (maximum -- a mechanical bound; the wire route past the as-built pose
    is not gated)."""
    half = block_depth / 2.0
    nearest = COLLAR_LOCAL_X - COLLAR_HALF_LEN - half
    farthest = half
    return (
        KNIFE_LOCAL_X - nearest,
        KNIFE_LOCAL_X - CLAMP_LOCAL_X,
        KNIFE_LOCAL_X - farthest,
    )
