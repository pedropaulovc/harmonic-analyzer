"""MHA-CH-07 fulcrum keeper: the print's words.

The callout rows and the notes live here, apart from ch_fulcrum_keeper_spec
(the ch_rocker_arm_notes split), so a wording change re-keys only the
keeper's own part and drawing, not the frame, shaft and assemblies that
import the spec's geometry. The spec keeps the band-bearing caption its own
walls are computed with (BORE_CENTRE_CALLOUT).

Each callout keeps its size first and at most two rows of words
(drawing-guidelines rule 7); each mate is named on the feature it serves
(rule 4). Assembly instructions (staking, step numbers) stay in MHA-CH-00.
"""

from __future__ import annotations

from _hole_spec import drill_process
from ch_fulcrum_keeper_spec import BORE_HOLE_SPEC

# Each keeper is finished alone to this print (#2338: no at-assembly pair
# ream). The bore is drilled F at the DRILLED HOLES row (owner ruling
# 2026-11-24, fit audit question 1): the callout names the drill (rule 7)
# and the shaft it slides on (rule 4), and prints no number of its own.
BORE_CALLOUT = f"{drill_process(BORE_HOLE_SPEC)} THRU\nSLIDING CLEARANCE ON MHA-CH-04"
# The crown is a full round tangent to both side faces (owner ruling Q10-B),
# centred on the bore (ch_fulcrum_keeper_spec).
CROWN_CALLOUT = "FULL R"
# The stepped .227 foot height prints at three places (#3744 Panel F) and
# states the engagement it sets in MHA-FR-02 (rules 3 and 4).
FOOT_RISE_CALLOUT = "SETS SCREW ENGAGEMENT\nIN MHA-FR-02"
# The foot-to-lug inside corner R.02 MAX (#3744 Panel F), tighter than the
# title block's INSIDE CORNERS R.040 MAX, names the screw head it clears.
CORNER_CALLOUT = "CLEARS HEAD OF\nMHA-CH-VN-52"
# The crown tap's rows under its native size and TO BORE extents: its mate.
# Rows of at most 24 characters keep the block between the front view and
# the plan.
SET_SCREW_QUALIFIER = "FOR MHA-CH-VN-55\nSET SCREW"
# The foot hole's row under its native through size: the frame tap it is
# transferred to (the reason for the .275's three places, RV-02); MHA-CH-VN-52
# is already named on CornerRadius.
FOOT_HOLE_MATE = "CENTERS MHA-FR-02 TAP"
# True free-text facts only; the material and finish are the title block's.
# Note 1 is the quantity and that the two are one part, not handed; where
# each goes and how the second is turned is MHA-CH-00's (machinist r1: that
# placement on a part sheet is assembly narration). The foot hole stays
# located off the foot tip (owner ruling 2026-10-28, RV-03), and with the
# counterbore retired (#3744) its tip wall exceeds .080 with no RV-04 note.
DRAWING_NOTES = "1. 2 REQUIRED, IDENTICAL."
