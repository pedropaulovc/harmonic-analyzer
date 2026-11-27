r"""Rocker hub (MHA-CH-12) drawing-only data: the marked-dimension and
precision contract, the callouts and the manufacturing note the part build
stamps into the SLDPRT.

Kept out of ``ch_rocker_hub_spec`` (the ``ch_rocker_arm_notes`` split), so a
wording edit never touches the supply sizes. Imported ONLY by
``build_ch_rocker_hub``, ``draw_ch_rocker_hub`` and the offline test.
"""

from __future__ import annotations

import math

from ch_rocker_hub_fit import BOND_CLEARANCE
from ch_rocker_hub_spec import NUMBER, ROCKER_NUMBER, STRAP_NUMBER, SUPPLY_WALL_MIN

# --- Drawing contract (drawing-simplicity-policy.md `How the repository
# implements the guidelines`: the PART owns places and bands). The land and the
# supply bore live on the Front-plane annulus (``HubProfile``); the supply
# length is the extrude's depth (``Hub``). The land prints its Ø.400 as a
# reference at three places (the stated bond clearance governs), the bore at
# three (a drill size; the title block's DRILLED HOLES row), the supply
# length as a single MIN limit at two.
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "HubProfile": {"LandDia", "SupplyBore"},
    "Hub": {"SupplyLength"},
}
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "HubProfile": {"LandDia": 3, "SupplyBore": 3},
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
# drawing-guidelines.md rule 4, made to fit: the land is turned to slide into
# the strap hole, so its Ø is a reference nominal and the stated diametral
# clearance in the named mate is the requirement, printed once, here, on the
# member made last (owner ruling 2026-11-24, fit audit question 2: "hub
# turned until it slides in (clearance .0005-.0030); bond").
REFERENCE_DIMENSIONS: dict[str, frozenset[str]] = {
    "HubProfile": frozenset({"LandDia"}),
}
REFERENCE_PREFIX = "(<MOD-DIAM>"
REFERENCE_SUFFIX = ")"


def _inch_text(value_mm: float) -> str:
    """``value_mm`` as four-place decimal-inch print text: ``.0005``."""
    return f"{value_mm / 25.4:.4f}".removeprefix("0")


CLEARANCE_TEXT = f"{_inch_text(BOND_CLEARANCE[0])}-{_inch_text(BOND_CLEARANCE[1])}"
BOND_NOTE_NUMBER = 2
LAND_CALLOUT = (
    f"TURN TO SLIDE INTO {STRAP_NUMBER} HOLE\n"
    f"{CLEARANCE_TEXT} CLEARANCE, SEE NOTE {BOND_NOTE_NUMBER}"
)
# rule 19: the bore and the length are supply sizes; the numbered note says
# where the finished ones are, and each supply size links it (rule 7). Rule
# 20: the supply wall is under the .080 target (owner ruling 2026-11-01,
# RV-01, restated for the bond's .0735), so the bore states it, rounded down.
SUPPLY_NOTE_NUMBER = 1
SUPPLY_NOTE_LINK = f"SEE NOTE {SUPPLY_NOTE_NUMBER}"
_SUPPLY_WALL_IN = math.floor(SUPPLY_WALL_MIN / 25.4 * 1000.0) / 1000.0
SUPPLY_WALL_TEXT = f"WALL {_SUPPLY_WALL_IN:.3f} MIN".replace("0.", ".", 1)
SUPPLY_BORE_CALLOUT = f"DRILL THRU\nSUPPLY SIZE, {SUPPLY_NOTE_LINK}\n{SUPPLY_WALL_TEXT}"
SUPPLY_LENGTH_PREFIX = "SUPPLY "
SUPPLY_LENGTH_CALLOUT = SUPPLY_NOTE_LINK

# drawing-guidelines.md rule 7: one line a machinist cannot read off the views.
# Rule 23 (a specified anaerobic bond is a fit): the bond prints its grade,
# the degrease, where the compound goes, how the joint is held square while
# it cures and the cure before the joined MHA-CH-06 is finished, with an
# acceptance; rule 4 form 1. Printed once, here, on the member made last
# (owner ruling 2026-11-24, fit audit question 2: "hub turned until it
# slides in (clearance .0005-.0030); bond"). A hub that turns once cured is
# not held, so it still pushes out and is bonded again; the cure is 24 h at
# room temperature (delegated ruling 2026-11-26 (Main), no precedent; owner
# review #2144 (D54); #3646).
DRAWING_NOTES = "\n".join(
    (
        f"{SUPPLY_NOTE_NUMBER}. BORE AND LENGTH ARE FINISHED AFTER JOINING TO"
        f" {STRAP_NUMBER}; SEE {ROCKER_NUMBER}.",
        f"{BOND_NOTE_NUMBER}. BONDED INTO {STRAP_NUMBER}, LOCTITE 638 ON THE LAND ONLY, LAND AND"
        " HOLE DEGREASED;",
        f"   HELD SQUARE UNTIL SET; 24 H CURE AT ROOM TEMPERATURE BEFORE {ROCKER_NUMBER} IS FINISHED.",
        "   A HUB THAT TURNS BY HAND IS PUSHED OUT, CLEANED TO BARE METAL AND BONDED AGAIN.",
    )
)
if NUMBER in DRAWING_NOTES:
    raise AssertionError("the note names the mates, not this part")
