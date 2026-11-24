"""Callout text MHA-FR-02's sheets state from the package's own limits.

Only the drawing imports this module, so a change of wording re-keys the
sheets and leaves the part's recipe alone.  The stated values are read off
the package's limits and specs and are never typed here.
"""

from __future__ import annotations

from _title_block_units import render_number
from ch_fulcrum_keeper_spec import KEEPER_TAP_SPEC
from fr_top_frame_spec import IN, KEEPER_TAP_WALL_ACCEPTED_MM, UNIT

_WALL_PLACES = 3

# Owner ruling D4 (#2333): the added draft prints 2° +1°/-0, tighter than the
# title block's ±1°, because its 2° minimum is what leaves the MHA-CH-07
# keeper's tap its wall in the rail web.  drawing-guidelines.md rule 3 states
# such a wall once, with its value, on the dimension that holds it.  The value
# is the wall build_fr_top_frame proves the tap drill's and the thread's walls
# hold at every printed limit with the lug centre at MHA-CH-00's printed .114
# (KEEPER_TAP_DRILL_WALL_MARGIN: .0767 at the 2° minimum, .0596 a degree
# under it), stated as accepted under the .080 target (Main, by the owner's
# delegation of 2026-11-24, rulings.md D15; RV-14).
ADDED_DRAFT_WALL_CALLOUT = (
    f"HOLDS {KEEPER_TAP_SPEC.size.lstrip('#')} TAP WALL "
    f"{render_number(KEEPER_TAP_WALL_ACCEPTED_MM / IN, UNIT, _WALL_PLACES)} MIN"
)
