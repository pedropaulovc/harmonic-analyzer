r"""Rocker hub (MHA-CH-012): the turned hub of the built-up rocker arm, as supplied.

PURE DATA, no SolidWorks/COM imports. MHA-CH-006 may be built up
(``ch_rocker_arm_notes.BUILT_UP_PERMISSION_NOTE``): this hub is pressed into
the strap MHA-CH-013 (``ch_rocker_hub_fit``), then the joined part's bore is
reamed and its hub length faced to the MHA-CH-006 print. So this detail is
the hub as SUPPLIED to the joint: the land at its finished Ø with the r6
press band, the bore and the length left with stock (drawing-guidelines.md
rule 19: a supply size, finished later). The finished bore and length print on
MHA-CH-006 only; this sheet never repeats them.

Every size derives from ``ch_rocker_arm_spec``; the two stock allowances below
are the only new numbers.
"""

from __future__ import annotations

import math

import _config
from ch_rocker_arm_spec import (
    HUB_DIA,
    HUB_LENGTH,
    HUB_LENGTH_BAND,
    PIVOT_HOLE_BAND,
    PIVOT_HOLE_DIA,
    RULE12_WALL_FLOOR,
)
from ch_rocker_hub_fit import HUB_LAND_BAND

NUMBER = "MHA-CH-012"
STRAP_NUMBER = "MHA-CH-013"
ROCKER_NUMBER = "MHA-CH-006"

# The land: the finished hub O.D., pressed in the strap's H7 hole.
LAND_DIA = HUB_DIA

# Supply bore: drilled under the finished Ø6.50 ream by REAM_STOCK_DIA
# (diametral), which the title block's DRILLED HOLES +0.10/0 can eat only
# half of, so the ream always cleans up.
REAM_STOCK_DIA = 0.20
SUPPLY_BORE_DIA = round(PIVOT_HOLE_DIA - REAM_STOCK_DIA, 2)  # 6.30
DRILLED_PLUS = float(_config.title_block("drilled_hole")["plus_mm"])
if not SUPPLY_BORE_DIA + DRILLED_PLUS < PIVOT_HOLE_DIA + PIVOT_HOLE_BAND[1]:
    raise AssertionError("the largest supply bore leaves no stock for the Ø6.50 ream")

# Supply length: the finished length's top limit plus FACE_STOCK at each end.
# Each end is faced after the press, so this stock also takes up how far off
# centre the press leaves the hub in the strap (0.5 per end: a clean-up cut
# plus that offset). Printed as a single MIN limit (swTolMIN prints the
# nominal, so the nominal is the limit), rounded UP to its one place.
FACE_STOCK = 0.5
SUPPLY_LENGTH_PLACES = 1
_STEP = 10.0**-SUPPLY_LENGTH_PLACES
SUPPLY_LENGTH_MIN = round(
    math.ceil((HUB_LENGTH + HUB_LENGTH_BAND[0] + 2.0 * FACE_STOCK) / _STEP - 1e-9)
    * _STEP,
    SUPPLY_LENGTH_PLACES,
)  # 8.2
SUPPLY_LENGTH_TOL_TYPE = 5  # swTolType_e.swTolMIN: prints "8.2 MIN"

# Wall between the smallest land and the largest supply bore.
SUPPLY_WALL_MIN = (LAND_DIA + HUB_LAND_BAND[1] - (SUPPLY_BORE_DIA + DRILLED_PLUS)) / 2.0
if SUPPLY_WALL_MIN < RULE12_WALL_FLOOR:
    raise AssertionError(f"supply wall {SUPPLY_WALL_MIN:.3f} under the rule-17 floor")
