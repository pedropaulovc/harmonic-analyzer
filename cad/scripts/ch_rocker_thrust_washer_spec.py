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
# Thickness band of the stock as supplied: A366/1008 cold-rolled sheet either
# side of 1/32 in holds +/-0.003 in (OnlineMetals cold-roll steel tolerances,
# sheet table, gauges 21 and 22; fetched 2026-10-10).
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
    f"1008 cold-rolled steel sheet, {_STOCK_FRACTION} in, ASTM A1008 CS"
)
# The title block's MATERIAL cell prints the registry row's ``material``: the
# ruled sheet, short enough for the cell (r743-4 eye pass: it printed the
# SolidWorks library name "Plain Carbon Steel", which only feeds the mass
# model). The thickness prints on the view ("1/32 (0.79) STOCK").
MATERIAL_TITLE = "1008 CR sheet, ASTM A1008 CS"

BORE_DIA = _BRACKET_BORE_DIA  # slips on the O6.35 pivot shaft
# Running clearance on the shaft: never under the bore. The sheet calls it
# DRILL THRU, so the title block's DRILLED HOLES row is its band and the model
# carries none (rule 1: a callout never restates the title block; PR #1317
# machinist review). The layout's wall and clearance stacks read this; the
# value is that row's (pinned to _config by the tests, so the rocker bank
# layout does not read the title block).
BORE_BAND = (0.10, 0.0)  # (upper, lower) deviations

# The wall floor: rule 12's 1.5 over the bore at its largest, with the OD at
# the bottom of the .XX band (machinist review, MHA-CH-009 round 1).
_OD_FLOOR = BORE_DIA + BORE_BAND[0] + 2.0 * RULE12_WALL_FLOOR + LINEAR_2PL
OD_MIN = math.ceil(round(_OD_FLOOR * 100.0, 9)) / 100.0  # 10.11
OD = HUB_DIA
if OD < OD_MIN:
    raise AssertionError(
        f"washer O{OD:.2f} is under its rule-12 wall floor O{OD_MIN:.2f}"
    )

# Marked model dimensions and the places the model authors on them
# (drawing-simplicity policy rule 2): the bore banded, the thickness printed
# as the stock callout.
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "RingProfile": {"DiscDia", "BoreDia"},
    "Disc": {"DiscThick"},
}
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "RingProfile": {"DiscDia": 2, "BoreDia": 2},
    "Disc": {"DiscThick": 2},
}
