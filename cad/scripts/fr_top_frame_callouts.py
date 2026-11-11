"""Callout text MHA-FR-02's sheets state from the model's own proofs.

Only the drawing imports this module, so a change of wording re-keys the
sheets and leaves the part's recipe alone.  The stated values are read off
the build module's proofs and are never typed here.
"""

from __future__ import annotations

import math

from _inch_wall_limits import WALL_TARGET_MM
from _title_block_units import render_number
from build_fr_top_frame import (
    KEEPER_TAP_DRILL_WALL_MARGIN,
    KEEPER_TAP_THREAD_WALL_MARGIN,
)
from ch_fulcrum_keeper_spec import KEEPER_TAP_SPEC
from fr_top_frame_spec import IN, UNIT

_WALL_PLACES = 3


def _floor_inches(value_mm: float, places: int) -> float:
    """A stated minimum in inches, never rounded up past the proved wall."""
    return math.floor(round(value_mm / IN * 10**places, 6)) / 10**places


# Owner ruling D4 (#2333): the added draft prints 2° +1°/-0, tighter than the
# title block's ±1°, because its 2° minimum is what leaves the MHA-CH-07
# keeper's tap its wall in the rail web.  drawing-guidelines.md rule 3 states
# such a wall once, with its value, on the dimension that holds it.  The value
# is the thinner of the tap drill's and the thread's proved walls at every
# printed limit, floored at three places.
KEEPER_TAP_WALL_HELD = min(KEEPER_TAP_DRILL_WALL_MARGIN, KEEPER_TAP_THREAD_WALL_MARGIN)
if KEEPER_TAP_WALL_HELD < WALL_TARGET_MM:
    raise AssertionError(
        "the added draft's 2° minimum no longer holds the keeper tap's wall target"
    )
ADDED_DRAFT_WALL_CALLOUT = (
    f"HOLDS {KEEPER_TAP_SPEC.size.lstrip('#')} TAP WALL "
    f"{render_number(_floor_inches(KEEPER_TAP_WALL_HELD, _WALL_PLACES), UNIT, _WALL_PLACES)}"
    " MIN"
)
