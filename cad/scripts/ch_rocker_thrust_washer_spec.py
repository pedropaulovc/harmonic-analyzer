r"""Pure-data contract for the rocker-bank thrust washers (MHA-CH-009, 2 used).

One steel washer on the pivot shaft at each end of the rocker stack (issue
#743 PR2; north one added 2026-10-10 when the shaft's shoulder went): between
hub 19 and the north pivot-bracket ear, and between hub 0 and the preload
spring at the south ear. It shares the rocker hub's OD, so each amplitude
bar's foot passes over it as it does over the hubs. Each amplitude bar
straddles its arm plate and can reach past a thin hub face, so an ear or a
wide washer against an end hub would meet the end bar; the washers stand the
ears off the end hubs (``rocker_bank_layout``, ``test_rocker_bank_layout``).

It is cut from 1/32 in steel stock (user, 2026-10-10; was 1/16, user ruling
2026-09-26, thinned so the south bracket's foot keeps room for its centred
hold-down beside the 8-thick ear): the print states the thickness as the
stock's, so the mill's tolerance governs it rather than a machined .XX band.
The south ear is set off its washer by the MHA-VN-053 spring's set blade
(#948 ruling R); the north washer's measured deviation offsets the datum
ear's DRO target (``rocker_bank_layout.MIC_RESIDUAL``), so neither thickness
sits in a datum chain.
"""

from __future__ import annotations

import math
from fractions import Fraction

from ch_pivot_bracket_spec import BORE_DIA as _BRACKET_BORE_DIA
from ch_rocker_arm_spec import HUB_DIA, LINEAR_2PL, RULE12_WALL_FLOOR

MM_PER_IN = 25.4

STOCK_THICKNESS_IN = Fraction(1, 32)
STOCK_THICKNESS = float(STOCK_THICKNESS_IN) * MM_PER_IN  # 0.79375
# The model carries the stock at the print's two places.
THICKNESS = round(STOCK_THICKNESS, 2)  # 0.79
# Thickness band of the stock as supplied: low-carbon cold-rolled sheet
# either side of 1/32 in holds +/-0.003 in (OnlineMetals cold-roll steel
# tolerances, sheet table, gauges 21 and 22; fetched 2026-10-10). Steel shim
# stock, the title block's alternative, rolls tighter, so the sheet's band is
# the one every stack reads.
STOCK_THICKNESS_TOL_IN = 0.003
STOCK_THICKNESS_RANGE = (
    STOCK_THICKNESS - STOCK_THICKNESS_TOL_IN * MM_PER_IN,
    STOCK_THICKNESS + STOCK_THICKNESS_TOL_IN * MM_PER_IN,
)
_STOCK_FRACTION = f"{STOCK_THICKNESS_IN.numerator}/{STOCK_THICKNESS_IN.denominator}"
# The thickness dimension prints "1/32 (0.79) STOCK": prefix and suffix around
# the imported model value, which the parentheses mark as reference.
STOCK_TEXT_PREFIX = f"{_STOCK_FRACTION} ("
STOCK_TEXT_SUFFIX = ") STOCK"
# The registry row carries this text verbatim (test_ch_rocker_thrust_washer_drawing).
MATERIAL_SPECIFICATION = (
    f"low-carbon cold-rolled steel sheet or steel shim stock, {_STOCK_FRACTION} in"
)
# The title block's MATERIAL cell prints the registry row's ``material``.
# drawing-guidelines.md rule 2 (the title block is the general specification): a thrust washer between
# oiled steel faces needs no one grade, so the cell names the acceptable
# families as alternatives (Opus #1022 baseline over-specification: it named
# 1008 to ASTM A1008 CS). The thickness prints on the view ("1/32 (0.79) STOCK").
MATERIAL_TITLE = "LOW-CARBON STEEL SHEET OR SHIM STOCK"

BORE_DIA = _BRACKET_BORE_DIA  # slips on the O6.35 pivot shaft
# Running clearance on the shaft: never under the bore. The sheet calls it
# DRILL THRU, so the title block's DRILLED HOLES row is its band and the model
# carries none (drawing-guidelines.md rule 2 (the title block is the general specification): a callout never restates the title block; PR #1317
# machinist review). The layout's wall and clearance stacks read this; the
# value is that row's (pinned to _config by the tests, so the rocker bank
# layout does not read the title block).
BORE_BAND = (0.10, 0.0)  # (upper, lower) deviations

# The wall floor: drawing-guidelines.md rule 17 (walls and webs)'s 1.5 over the bore at its largest, with the OD at
# the bottom of the .XX band (machinist review, MHA-CH-009 round 1).
_OD_FLOOR = BORE_DIA + BORE_BAND[0] + 2.0 * RULE12_WALL_FLOOR + LINEAR_2PL
OD_MIN = math.ceil(round(_OD_FLOOR * 100.0, 9)) / 100.0  # 10.11
OD = HUB_DIA
if OD < OD_MIN:
    raise AssertionError(
        f"washer O{OD:.2f} is under its drawing-guidelines.md rule 17 (walls and webs) wall floor O{OD_MIN:.2f}"
    )

# The worst-case wall the sheet states (drawing-guidelines.md rule 20 (state a known shortfall as a plain fact)): the
# OD at the bottom of its printed .XX band less the DRILLED HOLES top, rounded
# DOWN. Rule 17 (walls and webs)'s 2.0 target needs a nominal OD of about
# 11.11, past the amplitude-bar foot cheeks' ceiling that holds the shared
# hub/washer O10.20 (test_rocker_bank_layout), so the washer states 1.54.
# Pending exception ruling: MHA-CH-009 wall 1.54 MIN (#1022).
_PRINTED_2PL = round(LINEAR_2PL, 2)  # the title block prints the .XX class as +/-0.51
_WALL_WORST = (round(OD, 2) - _PRINTED_2PL - (round(BORE_DIA, 2) + BORE_BAND[0])) / 2.0
WALL_MIN = math.floor(_WALL_WORST * 100.0 + 1e-9) / 100.0
WALL_NOTE = f"WALL {WALL_MIN:.2f} MIN"
# Manufacturing Notes (drawing-guidelines.md rule 7 (notes: few, flagged, never a method)): only the stated shortfall.
DRAWING_NOTES = WALL_NOTE

# Marked model dimensions and the places the model authors on them
# (drawing-simplicity-policy.md `How the repository implements the guidelines`): the bore banded, the thickness printed
# as the stock callout.
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "RingProfile": {"DiscDia", "BoreDia"},
    "Disc": {"DiscThick"},
}
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "RingProfile": {"DiscDia": 2, "BoreDia": 2},
    "Disc": {"DiscThick": 2},
}
