r"""Rocker hub (MHA-CH-12): the turned hub of the built-up rocker arm, as supplied.

PURE DATA, no SolidWorks/COM imports. MHA-CH-06 may be built up
(``ch_rocker_arm_notes.BUILT_UP_PERMISSION_NOTE``): this hub is pressed into
the strap MHA-CH-13 (``ch_rocker_hub_fit``), then the joined part's bore is
reamed and its hub length faced to the MHA-CH-06 print. So this detail is
the hub as SUPPLIED to the joint: the land at its finished Ø with its
press band, the bore and the length left with stock (drawing-guidelines.md
rule 19: a supply size, finished later). The finished bore and length print on
MHA-CH-06 only; this sheet never repeats them.

Every size derives from ``ch_rocker_arm_spec``; the two stock allowances below
are the only new numbers.
"""

from __future__ import annotations

import math

import _config
from _inch_wall_limits import WALL_FLOOR_MM
from _package_units import drawing_unit
from _printed_tolerance import drilled_oversize_mm
from ch_rocker_arm_spec import (
    HUB_DIA,
    HUB_LENGTH,
    HUB_LENGTH_BAND,
    PIVOT_HOLE_BAND,
    PIVOT_HOLE_DIA,
)
from ch_rocker_hub_fit import HUB_LAND_BAND

NUMBER = "MHA-CH-12"
STRAP_NUMBER = "MHA-CH-13"
ROCKER_NUMBER = "MHA-CH-06"

# #290: the registry row's drawing_unit (in) is this sheet's unit.
UNIT = drawing_unit("parts/ch-rocker-hub", _config.parts("ch-rocker-hub"))

# The land: the finished hub O.D., pressed in the strap's reamed hole.
LAND_DIA = HUB_DIA

# Supply bore: a letter-D drill under the finished pivot ream, leaving .010
# diametral stock, which the title block's DRILLED HOLES +.004/0 can eat only
# part of, so the ream always cleans up.
SUPPLY_BORE_DIA = 6.2484  # .246, letter D
DRILLED_PLUS = drilled_oversize_mm(unit=UNIT)
if not SUPPLY_BORE_DIA + DRILLED_PLUS < PIVOT_HOLE_DIA + PIVOT_HOLE_BAND[1]:
    raise AssertionError("the largest supply bore leaves no stock for the pivot ream")

# Supply length: the finished length's top limit plus FACE_STOCK at each end.
# Each end is faced after the press, so this stock also takes up how far off
# centre the press leaves the hub in the strap (.020 per end: a clean-up cut
# plus that offset). Printed as a single MIN limit (swTolMIN prints the
# nominal, so the nominal is the limit), rounded UP on its two-place inch grid.
FACE_STOCK = 0.508  # .020
SUPPLY_LENGTH_PLACES = 2
_STEP = 25.4 * 10.0**-SUPPLY_LENGTH_PLACES
SUPPLY_LENGTH_MIN = round(
    math.ceil((HUB_LENGTH + HUB_LENGTH_BAND[0] + 2.0 * FACE_STOCK) / _STEP - 1e-9)
    * _STEP,
    6,
)  # 8.128, .32
SUPPLY_LENGTH_TOL_TYPE = 5  # swTolType_e.swTolMIN: prints ".32 MIN"

# Wall between the smallest land and the largest supply bore: .0754 against
# the .060 floor (under the .080 target; the joined part reams it thinner).
SUPPLY_WALL_MIN = (LAND_DIA + HUB_LAND_BAND[1] - (SUPPLY_BORE_DIA + DRILLED_PLUS)) / 2.0
if SUPPLY_WALL_MIN < WALL_FLOOR_MM:
    raise AssertionError(f"supply wall {SUPPLY_WALL_MIN:.3f} under the rule-17 floor")
