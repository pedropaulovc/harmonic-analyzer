"""Words MHA-PD-19's sheet prints: the locating holes' numbered note and the
short dimension callouts (the locating holes', the screw holes' and the hub
station's).

Kept out of the drawing script (drawing scripts own placement, not
manufacturing values) and out of the widely imported spec, so the wording
re-keys only this sheet.
"""

from __future__ import annotations

import math
import textwrap

from pd_paper_drive_assembly_steps import knob_setting_ref
from pd_transgear_arm_plate_geometry import (
    CSK_ANGLE_DEG,
    CSK_DIA,
    CSK_DIA_PLACES,
    LOCATOR_SITES_MM,
    SCREW_HOLES,
)
from pd_transgear_arm_plate_spec import (
    ARM_NUMBER,
    DOWEL_NUMBER,
    KNOB_SHAFT_NUMBER,
    SCREW_NUMBER,
    SPROCKET_NUMBER,
)
from pd_vn_transgear_arm_plate_locating_pin_spec import SLIP_DIAMETRAL_CLEARANCE_MM


def _clearance_ref_in(limits_mm: tuple[float, float]) -> str:
    """A diametral clearance range in inches, four places, rounded outward."""
    low, high = (value / 25.4 * 1e4 for value in limits_mm)
    return "-".join(
        f"{bound / 1e4:.4f}".removeprefix("0")
        for bound in (math.floor(low + 1e-9), math.ceil(high - 1e-9))
    )


# The locating holes' fit range and match-drilling: one numbered note, which
# their callout points at (rule 7: under the size and process a callout
# carries at most two lines of words; a note at most four lines).  The
# dowel's catalogue limits in the .0945 reamed hole leave a clearance that
# locates without press: a locational clearance fit (rule 4), its range from
# the dowel spec's own limits as REF.  The callout names the dowel, so the
# note does not repeat it.  The match-drill pointer names the MHA-PD-00 view
# whose native S-K dimension sets the pair (#1388 policy: the setting's
# value lives on the assembly sheet, not here).  The mouths take the title
# block's edge break (pd_transgear_arm_plate_geometry.LOCATOR_MOUTH_BREAK_MAX_MM).
LOCATOR_NOTE_NUMBER = 1
LOCATOR_NOTE_WIDTH = 30
LOCATOR_NOTE = "\n".join(textwrap.wrap(
    f"{LOCATOR_NOTE_NUMBER}. (CLEARANCE {_clearance_ref_in(SLIP_DIAMETRAL_CLEARANCE_MM)}). "
    f"MATCH-DRILL WITH ARM {ARM_NUMBER}, SET PER {knob_setting_ref()}.",
    width=LOCATOR_NOTE_WIDTH,
    subsequent_indent="   ",
    break_on_hyphens=False,
))
# The count above the size, as on the screw holes; the note pointer on the
# process line; the fit on the two lines of words under it (rule 7).  At
# most 21 characters a line, so the shelf under the block ends left of hole
# 1's witness line (round 1 layout audit on 41ad5cf: at 27 its shelf
# crossed it).
LOCATOR_COUNT_CALLOUT = f"{len(LOCATOR_SITES_MM)}X"
LOCATOR_CALLOUT = "\n".join((
    f"REAM THRU, SEE NOTE {LOCATOR_NOTE_NUMBER}",
    "LOCATIONAL CLEARANCE",
    f"FIT ON {DOWEL_NUMBER}",
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
# The hub face's station from face A sets the knob shaft (its integral 15T
# meshing the reducer disc) and, through the drive collar on the 15T's front
# face, the removable chain sprocket's plane (pd_transgear_arm_plate_spec.
# SPROCKET_NUMBER).  Two short lines between the dimension's own witness
# lines, naming both by drawing number.
HUB_STATION_CALLOUT = f"SETS {KNOB_SHAFT_NUMBER}\nAND {SPROCKET_NUMBER}"
