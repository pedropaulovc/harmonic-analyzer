"""Words MHA-PD-19's sheet prints: the locating holes' numbered note and the
short hole callouts (the press hole's, the locating holes' and the screw
holes').

Kept out of the drawing script (drawing scripts own placement, not
manufacturing values) and out of the widely imported spec, so the wording
re-keys only this sheet.
"""

from __future__ import annotations

import textwrap

from pd_paper_drive_assembly_steps import knob_setting_ref
from pd_transgear_arm_plate_geometry import (
    CSK_ANGLE_DEG,
    CSK_DIA,
    CSK_DIA_PLACES,
    LOCATOR_SITES_MM,
    PRESS_HOLE_CHAMFER,
    PRESS_HOLE_CHAMFER_PLACES,
    SCREW_HOLES,
)
from pd_transgear_arm_plate_spec import (
    ARM_NUMBER,
    BUSH_NUMBER,
    DOWEL_NUMBER,
    SCREW_NUMBER,
)

# The press hole is reamed with the .4385 set reamer and prints that size
# with no band (fit audit 2026-11-23, pending owner confirmation): the
# MHA-PD-28 bush's press step is turned to this hole as measured, so the
# interference is the bush sheet's requirement, not this one's.  REAM, the
# face-A mouth's lead-in chamfer in the hole callout's size form (as the
# screw holes carry their countersink), the fit and the bush by drawing
# number, then what the press protects (rule 4's necessity test: the press
# alone holds knob axis K in the plate).  Two lines of words under the size
# and process (rule 7).
_PRESS_CHAMFER_TEXT = (
    f"{PRESS_HOLE_CHAMFER / 25.4:.{PRESS_HOLE_CHAMFER_PLACES}f}".removeprefix("0")
)
PRESS_HOLE_CALLOUT = "\n".join((
    "REAM THRU",
    f"{_PRESS_CHAMFER_TEXT} X 45\u00b0 AT FACE A",
    f"PRESS FIT FOR {BUSH_NUMBER}",
    "HOLDS KNOB AXIS, NO FASTENER",
))

# The locating holes: reamed with the .1260 set reamer, the size printed
# with no band; the callout names the dowel and the acceptance by the dowel
# itself, and one numbered note, which the callout points at, carries what
# the slip protects and the match-drilling (rule 7: under the size and
# process a callout carries at most two lines of words; a note at most four
# lines).  The match-drill pointer names the MHA-PD-00 view whose native S-K
# dimension sets the pair (#1388 policy: the setting's value lives on the
# assembly sheet, not here).  The mouths take the title block's edge break
# (pd_transgear_arm_plate_geometry.LOCATOR_MOUTH_BREAK_MAX_MM).
LOCATOR_NOTE_NUMBER = 1
LOCATOR_NOTE_WIDTH = 30
LOCATOR_NOTE = "\n".join(textwrap.wrap(
    f"{LOCATOR_NOTE_NUMBER}. KEEPS PLATE AT REDUCER MESH SETTING. "
    f"MATCH-DRILL WITH ARM {ARM_NUMBER}, SET PER {knob_setting_ref()}.",
    width=LOCATOR_NOTE_WIDTH,
    subsequent_indent="   ",
    break_on_hyphens=False,
))
# The sheet's only numbered note, for the feature export (export_features
# reads a declared part's DRAWING_NOTES); the drawing prints LOCATOR_NOTE.
DRAWING_NOTES = LOCATOR_NOTE
# The count above the size, as on the screw holes; the note pointer on the
# process line; the fit, its mate and the acceptance on the two lines of
# words under it (rule 7).  At most 21 characters a line, so the shelf under
# the block ends left of hole 1's witness line (round 1 layout audit on
# 41ad5cf: at 27 its shelf crossed it).
LOCATOR_COUNT_CALLOUT = f"{len(LOCATOR_SITES_MM)}X"
LOCATOR_CALLOUT = "\n".join((
    f"REAM THRU, SEE NOTE {LOCATOR_NOTE_NUMBER}",
    f"SLIP ON {DOWEL_NUMBER},",
    "SLIDES IN, NO SHAKE",
))
# One hole callout for the screw holes: the drill Ø, the process, through,
# and the countersink in symbol form on its own line at the model's diameter
# and angle; the head seat names the screw (its .XXX Ø bounds the walls
# beside it, pd_transgear_arm_plate_geometry.WALLS).  At most 18 characters
# a line, so the block ends left of hole 1's witness line (the .4281's; at
# 24 that line ran through the 82° and the screw's number: fan-out round 2,
# run 20261107T121559938Z).
_CSK_DIA_TEXT = f"{CSK_DIA / 25.4:.{CSK_DIA_PLACES}f}".removeprefix("0")
SCREW_HOLE_CALLOUT = "\n".join((
    "DRILL THRU",
    f"<HOLE-SINK><MOD-DIAM>{_CSK_DIA_TEXT} X {CSK_ANGLE_DEG:.0f}\u00b0",
    f"SCREW {SCREW_NUMBER}",
))
HOLE_COUNT_CALLOUT = f"{len(SCREW_HOLES)}X"
