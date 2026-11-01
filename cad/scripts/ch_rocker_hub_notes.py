r"""Rocker hub (MHA-CH-12) drawing-only data: the marked-dimension and
precision contract, the callouts and the manufacturing note the part build
stamps into the SLDPRT.

Kept out of ``ch_rocker_hub_spec`` (the ``ch_rocker_arm_notes`` split), so a
wording edit never touches the supply sizes. Imported ONLY by
``build_ch_rocker_hub``, ``draw_ch_rocker_hub`` and the offline test.
"""

from __future__ import annotations

import math

from ch_rocker_hub_fit import INTERFERENCE_TEXT
from ch_rocker_hub_spec import NUMBER, ROCKER_NUMBER, STRAP_NUMBER, SUPPLY_WALL_MIN

# --- Drawing contract (drawing-simplicity-policy.md `How the repository
# implements the guidelines`: the PART owns places and bands). The land and the
# supply bore live on the Front-plane annulus (``HubProfile``); the supply
# length is the extrude's depth (``Hub``). The land prints at four places
# with its press band, the bore at three (a drill size; the title block's
# DRILLED HOLES row), the supply length as a single MIN limit at two.
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "HubProfile": {"LandDia", "SupplyBore"},
    "Hub": {"SupplyLength"},
}
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "HubProfile": {"LandDia": 4, "SupplyBore": 3},
    "Hub": {"SupplyLength": 2},
}
DRAWING_PRECISION_BY_NAME: dict[str, int] = {
    name: decimals
    for dimensions in DRAWING_PRECISION.values()
    for name, decimals in dimensions.items()
}
if {name for names in DRAWING_DIMENSIONS.values() for name in names} != set(
    DRAWING_PRECISION_BY_NAME
):
    raise AssertionError("every marked hub dimension needs authored places")

# Below-text rows (SOLIDWORKS stores an ABOVE-compartment line break but never
# prints it, draw_pd_transgear_pin._printable_above_callouts).
# drawing-guidelines.md rule 4: the press band names its mate and the fit.
LAND_CALLOUT = f"PRESS FIT IN {STRAP_NUMBER} STRAP HOLE\n{INTERFERENCE_TEXT}"
# rule 19: the bore and the length are supply sizes; the note says where the
# finished ones are. Rule 20: the supply wall is under the .080 target (owner
# ruling 2026-11-01, RV-01), so the bore states it, rounded down.
_SUPPLY_WALL_IN = math.floor(SUPPLY_WALL_MIN / 25.4 * 1000.0) / 1000.0
SUPPLY_WALL_TEXT = f"WALL {_SUPPLY_WALL_IN:.3f} MIN".replace("0.", ".", 1)
SUPPLY_BORE_CALLOUT = f"DRILL THRU\nSUPPLY SIZE\n{SUPPLY_WALL_TEXT}"
SUPPLY_LENGTH_PREFIX = "SUPPLY "

# drawing-guidelines.md rule 7: one line a machinist cannot read off the views.
DRAWING_NOTES = f"1. BORE AND LENGTH ARE FINISHED AFTER JOINING TO {STRAP_NUMBER}; SEE {ROCKER_NUMBER}."
if NUMBER in DRAWING_NOTES:
    raise AssertionError("the note names the mates, not this part")
