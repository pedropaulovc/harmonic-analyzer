"""Callout text MHA-FR-02's sheets state from the package's own limits.

Only the drawing imports this module, so a change of wording re-keys the
sheets and leaves the part's recipe alone.  The stated values are read off
the package's limits and specs and are never typed here.
"""

from __future__ import annotations

from _inch_wall_limits import WALL_TARGET_MM
from _title_block_units import render_number
from ch_fulcrum_keeper_spec import KEEPER_TAP_SPEC
from fr_top_frame_spec import IN, UNIT

_WALL_PLACES = 3

# Owner ruling D4 (#2333): the added draft prints 2° +1°/-0, tighter than the
# title block's ±1°, because its 2° minimum is what leaves the MHA-CH-07
# keeper's tap its wall in the rail web.  drawing-guidelines.md rule 3 states
# such a wall once, with its value, on the dimension that holds it.  The wall
# is the package's thin-wall target (rule 17), which build_fr_top_frame proves
# the tap drill's and the thread's walls hold at every printed limit
# (KEEPER_TAP_DRILL_WALL_MARGIN: .0807 at the 2° minimum, .0636 a degree
# under it).
ADDED_DRAFT_WALL_CALLOUT = (
    f"HOLDS {KEEPER_TAP_SPEC.size.lstrip('#')} TAP WALL "
    f"{render_number(WALL_TARGET_MM / IN, UNIT, _WALL_PLACES)} MIN"
)
