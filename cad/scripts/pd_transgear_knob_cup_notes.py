"""MHA-PD-16 knob cup: the sheet's spec-derived callout text.

Kept out of ``pd_transgear_knob_cup_spec`` so the part's native recipe does
not re-key on a callout-only change (the drawing does), as
``pd_guide_lock_notes``.
"""

from __future__ import annotations

from pd_rack_pinion_spec import inch_text
from pd_transgear_knob_cup_spec import WEB_MIN

# The head pocket's depth keeps its third place to hold the web between the
# pocket and the pilot at the .080 target (the spec's WEB_MIN, the worst
# case of the printed length, pilot depth and pocket depth), and says so at
# the dimension (drawing-guidelines.md rule 3; machinist review r11 of
# #2425, three runs: ".108" stated no function).
CBORE_DEPTH_CALLOUT = f"HOLDS WEB {inch_text(WEB_MIN, 3)} MIN"
