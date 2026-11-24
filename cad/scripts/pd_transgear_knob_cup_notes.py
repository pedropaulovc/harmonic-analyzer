"""MHA-PD-16 knob cup: the sheet's spec-derived callout text.

Kept out of ``pd_transgear_knob_cup_spec`` so the part's native recipe does
not re-key on a callout-only change (the drawing does), as
``pd_guide_lock_notes``.
"""

from __future__ import annotations

import _config
from pd_rack_pinion_spec import inch_text
from pd_transgear_knob_cup_spec import WEB_MIN

# The head pocket's depth keeps its third place to hold the web between the
# pocket and the pilot at the .080 target (the spec's WEB_MIN, the worst
# case of the printed length, pilot depth and pocket depth), and says so at
# the dimension (drawing-guidelines.md rule 3; machinist review r11 of
# #2425, three runs: ".108" stated no function).
CBORE_DEPTH_CALLOUT = f"HOLDS WEB {inch_text(WEB_MIN, 3)} MIN"
# Each floor corner's R MAX is under the title block's inside corner because
# a mate seats past it (rule 16: the largest radius the corner accepts, and
# rule 4: the mate named by its number; machinist review 2026-11-23, two
# runs: neither radius named what it clears).  The MHA-PD-08 journal's end
# bears on the pilot's floor, its least rear chamfer clearing the corner;
# the MHA-PD-VN-71 screw's head lands flat on the pocket's floor inside the
# corner (the spec asserts both).
PILOT_CORNER_CALLOUT = f"SEATS {_config.parts('pd-transgear-knob-shaft')['number']} END"
POCKET_CORNER_CALLOUT = (
    f"SEATS {_config.parts('pd-vn-transgear-knob-cup-screw')['number']} HEAD"
)
