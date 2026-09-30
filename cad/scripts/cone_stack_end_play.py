"""End play of the cone gear stack on MHA-014, set by the tip block's feeler.

The stack (MHA-021, twenty MHA-013 and the MHA-096 tip bushing) is pushed onto
MHA-014's thrust collar at fit-up, and the MHA-092 tip block is slid onto one
TIP_BLOCK_FEELER leaf laid on the bushing's north face (user ruling
2026-09-28).  That gap is how far the stack can float north in service.  The
feeler follows the cylinder bank's rule (cylinder_bank_layout.BANK_END_FEELER):
the smallest 0.05 blade whose tightest setting keeps MIN_END_PLAY with
MARGIN_SPARE to spare.

Import-free on purpose: cone_line reads the feeler for the tip block's
station, and everything that imports cone_line must not pick up the gear
specs through it.
"""

from __future__ import annotations

import math

MIN_END_PLAY = 0.10  # running floor: the bushing's oiled brass face on the block
MARGIN_SPARE = 0.25  # novice spare over every floor (cylinder bank rule)
FEELER_STEP = 0.05  # blades of the metric gauge set
TIP_BLOCK_FEELER_BAND = 0.10  # set error: the block's hold-down re-set
TIP_BLOCK_FEELER = FEELER_STEP * math.ceil(
    round((MIN_END_PLAY + MARGIN_SPARE + TIP_BLOCK_FEELER_BAND) / FEELER_STEP, 9)
)  # 0.45
# (min, max) float of the stack north off the collar in service.
STACK_FLOAT = (
    TIP_BLOCK_FEELER - TIP_BLOCK_FEELER_BAND,
    TIP_BLOCK_FEELER + TIP_BLOCK_FEELER_BAND,
)
