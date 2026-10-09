r"""Pure-data contract for the rocker-bank south thrust washer (MHA-CH-009).

One steel washer on the pivot shaft between rocker 0's hub and the south
pivot-bracket ear (issue #743 PR2). It shares the rocker hub's OD, so each
amplitude bar's foot passes over it as it does over the hubs. Each amplitude
bar straddles its arm plate and can reach past a thin hub face, so an ear or
a wide washer against hub 0 would meet the ch0 bar; the washer stands the
south ear off hub 0 (``rocker_bank_layout``, ``test_rocker_bank_layout``).

It is cut from 1/16 in steel stock (user ruling, 2026-09-26): the print states
the thickness as the stock's, so the mill's tolerance governs it rather than
a machined .XX band. The south ear is set off this washer by the MHA-VN-051
spring's set blade (#948 ruling R), so the thickness sits in no datum chain.
"""

from __future__ import annotations

import math
from fractions import Fraction

from ch_pivot_bracket_spec import BORE_DIA as _BRACKET_BORE_DIA
from ch_rocker_arm_spec import HUB_DIA, LINEAR_2PL, RULE12_WALL_FLOOR

MM_PER_IN = 25.4

STOCK_THICKNESS_IN = Fraction(1, 16)
STOCK_THICKNESS = float(STOCK_THICKNESS_IN) * MM_PER_IN  # 1.5875
# The model carries the stock at the print's two places.
THICKNESS = round(STOCK_THICKNESS, 2)  # 1.59
# Thickness band of the stock as supplied: A366/1008 cold-rolled sheet either
# side of 1/16 in holds +/-0.005 in (OnlineMetals cold-roll steel tolerances,
# sheet table, gauges 15 and 16; fetched 2026-09-26).
STOCK_THICKNESS_TOL_IN = 0.005
STOCK_THICKNESS_RANGE = (
    STOCK_THICKNESS - STOCK_THICKNESS_TOL_IN * MM_PER_IN,
    STOCK_THICKNESS + STOCK_THICKNESS_TOL_IN * MM_PER_IN,
)
_STOCK_FRACTION = f"{STOCK_THICKNESS_IN.numerator}/{STOCK_THICKNESS_IN.denominator}"
# The thickness dimension prints "1/16 (1.59) STOCK": prefix and suffix around
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
# model). The thickness prints on the view ("1/16 (1.59) STOCK").
MATERIAL_TITLE = "1008 CR sheet, ASTM A1008 CS"

BORE_DIA = _BRACKET_BORE_DIA  # slips on the O6.35 pivot shaft
# Running clearance on the shaft: never under the bore (drilled class).
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
