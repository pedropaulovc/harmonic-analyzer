"""Words MHA-PD-18's sheet prints: the numbered fit notes and the short
dimension callouts that link to them.

Kept out of the drawing script (drawing scripts own placement, not
manufacturing values) and out of the widely imported spec, so the wording
re-keys only this sheet.
"""

from __future__ import annotations

import _config
import pd_transgear_pin_spec as PIN
import pd_vn_transgear_arm_plate_locating_pin_spec as LOCATOR_PIN
from pd_paper_drive_assembly_steps import knob_setting_ref
from pd_transgear_arm_geometry import (
    PIN_HOLE_DEPTH,
    PIN_HOLE_DEPTH_PLACES,
    PIVOT_BORE_DRILL,
)
from pd_rack_pinion_spec import inch_text
from pd_transgear_arm_spec import LATCH_PIN_NUMBER

# Each fit callout keeps its size, its process and its mate; a fit whose
# acceptance and reason do not fit two lines of words stands once in a
# numbered note, linked from the callout (rule 7: size and process lines
# plus at most two lines of words; rule 4: a fit names its mate and its
# standard name).  The notes stand on sheet 2 (on sheet 1 they ran through
# its lower border), so every link from sheet 1 names their sheet (round 4:
# a flag on sheet 1 pointed to no note on that sheet).  The pin bore and the
# counterbore's floor carry their two lines themselves and link no note
# (fit batch review r1: the pin bore's fit was stated at its callout and
# again in a note 5, with a second acceptance).
_PLATE = _config.parts("pd-transgear-arm-plate")
_SPRING = _config.parts("pd-vn-transgear-pivot-spring")
_PIVOT_SCREW = _config.parts("pd-vn-transgear-pivot-screw")
PIVOT_NOTE, LOCATOR_NOTE, LATCH_PIN_NOTE = 1, 2, 3
NOTES_SHEET = 2


def see_note(number: int) -> str:
    """A sheet-1 link to a numbered note, naming the notes' sheet."""
    return f"SEE NOTE {number}, SHEET {NOTES_SHEET}"


# Why the pin bore is reamed stands in the part's necessity file, not on
# the sheet (owner ruling 2026-11-24: "In the part's registry file, not on
# the sheet"; cad/config/necessity/pd-transgear-arm.yaml): a looser bore
# lets the bonded pin lean (paper_drive_arm_registration.
# S_AXIS_TILT_MAX_RAD, which takes no credit for the clamped head: the bore
# is what squares the pin); the lean is charged to the platen air, the
# reducer and rack meshes and the collar air, and the first to close as the
# gap opens is the MHA-PD-10 12T's full-depth teeth stopping inside the
# MHA-PD-26 rack's reach (build_pd_paper_drive_assembly's platen, rack and
# chain check; fit audit 2026-11-23 batch sweep; the rack's opposite-flank
# budget check is deleted, owner ruling 2026-11-24 on audit part 2).


NOTES = (
    # A drilled hole at the DRILLED HOLES row: the note names its mate and
    # prints no numbers (owner ruling 2026-11-24, fit audit question 6).
    f"{PIVOT_NOTE}. PIVOT BORE: RUNNING CLEARANCE ON PIVOT SCREW {_PIVOT_SCREW['number']}"
    " SHOULDER.",
    # Notes 2 and 3 (rule 4, form 3; the 1/8 dowels are the owner's ruling of
    # 2026-11-24 on fit audit question 9): a
    # hole reamed to a bought dowel prints its set reamer's size and no band;
    # the dowel tried in it is the gauge.  What fails if the hole is loose
    # (the plate must come back to the reducer mesh setting; the latch's
    # stop pin has no other fastener, owner 2026-10-27, #1379) is in
    # cad/config/necessity/pd-transgear-arm.yaml, not on the sheet (owner
    # ruling 2026-11-24).
    # The mouths break at the title block's row (fit batch review r1: "MOUTH
    # BREAKS .002 MAX FOR DOWEL GRIP" was a second reason with a dimension
    # in it; pd_transgear_arm_geometry.LOCATOR_MOUTH_BREAK_MAX_MM carries
    # the title block's break through the grip, the punch air and the walls).
    f"{LOCATOR_NOTE}. 2X DOWEL HOLES: PRESS FIT ON DOWEL {LOCATOR_PIN.PART_NUMBER},"
    " DOES NOT ENTER BY HAND.\n"
    f"   MATCH-DRILL WITH ARM PLATE {_PLATE['number']} AT ASSEMBLY, {knob_setting_ref()}.",
    f"{LATCH_PIN_NOTE}. LATCH-PIN HOLE: PRESS FIT ON LATCH PIN {LATCH_PIN_NUMBER},\n"
    "   DOES NOT ENTER BY HAND.",
)
NOTES_TEXT = "\n".join(NOTES)
# The sheet's numbered notes as export_features reads a declared part's
# DRAWING_NOTES; the drawing prints NOTES_TEXT.
DRAWING_NOTES = NOTES_TEXT

PIVOT_BORE_CALLOUT = f"{PIVOT_BORE_DRILL} DRILL THRU, {see_note(PIVOT_NOTE)}"
# The pin bore's callout (owner ruling 2026-11-24, fit audit question 4:
# the one-diameter pin is bonded in the reamed bore): size and process,
# then the mate and that it is made to this bore: MHA-PD-23 is turned
# last, so its sheet carries the bond's clearance and the trial, once (fit
# batch review r2: with the range here the pin's sheet printed none; r1: a
# linked note 5 repeated the mate and the bond with a second acceptance).
# The grade and the method stand in MHA-PD-00's pin step, and the set pin
# that checks the bore is the traveler's.  The fit is named (fit batch
# review r5: nothing on this sheet said the pin is bonded).
PIN_BORE_MATE_TEXT = f"{PIN.PIN_NUMBER} BONDED, TURNED TO THIS BORE"
PIN_BORE_CALLOUT = f"REAM THRU\n{PIN_BORE_MATE_TEXT}"
# Note 2 names the dowel and its press; the callout links it (round 2: the
# dowel named on both was named twice for one pattern).
LOCATOR_CALLOUT_TEXT = f"2X REAM THRU, {see_note(LOCATOR_NOTE)}"
# Size, process and depth at the callout (round 2: a depth is never deferred
# to a view); note 3 names the latch pin.  Round 3's "BLIND FLAT-BOTTOM REAM"
# row was so wide its leader cut the "B" of BLIND; the shorter row lets the
# text stand right of the hole, so the leader leaves its left end straight
# up.  #3124: the full-diameter depth is a MIN over a drill point, authored
# natively on PinHoleDepth@PinHole and printed by section A-A; the callout
# carries it as REF (drawing-guidelines Holes: "a depth printed as REF in the
# callout is complete when a controlling dimension on the views locates the
# floor").  MHA-PD-00 step 10 sets the pin's proud (an assembly instruction
# this part sheet does not repeat, rule 7).
PIN_HOLE_CALLOUT = "\n".join((
    f"REAM <HOLE-DEPTH> ({inch_text(PIN_HOLE_DEPTH, PIN_HOLE_DEPTH_PLACES)})",
    see_note(LATCH_PIN_NOTE),
))
# The counterbore is drawn in section A-A.  Its Ø is a clearance pocket at
# the title block's .XX and carries the counterbore symbol
# (pd_transgear_arm_spec.COUNTERBORE_PREFIX, authored on the part) and no
# words.  Its floor's row names the mate it seats.  The floor's band is
# under the title block's row for the spring's room (the room between the
# floor and the pivot screw's head is the MHA-PD-VN-63 spring's installed
# height: transgear_hanger_joints.SPRING_ROOM_MIN, .0003 over the working
# height at ±.002, .0027 under it at the title block's ±.005); that reason
# is in the part's necessity file.
FLOOR_CALLOUT = f"SEATS SPRING {_SPRING['number']}"
# Section D-D (sheet 2, with the notes) shows the rear mouth's chamfer.  Its
# face is named by the datum it faces away from (round 4: REAR was a direction
# word the sheet never defined); the minimum clears the pin's seat fillet
# (rule 4).
PIN_MOUTH_CALLOUT = "\n".join(
    ("X 45\u00b0 MOUTH OPPOSITE DATUM A", f"CLEARS {PIN.PIN_NUMBER} SEAT FILLET")
)
# The 8-32 plate taps carry no frame: they are spotted and drilled through
# MHA-PD-19's screw holes at assembly with the plate doweled on (delegated
# ruling 2026-11-07, Q2 L1), and the tap callout's last line says so.
PLATE_TAP_QUALIFIER = f"SPOT THROUGH {_PLATE['number']} AT ASSEMBLY"

DIMENSION_CALLOUTS = {
    "PivotBoreDia": PIVOT_BORE_CALLOUT,
    "PinBoreDia": PIN_BORE_CALLOUT,
    "FloorDepth": FLOOR_CALLOUT,
    "PinHoleDia": PIN_HOLE_CALLOUT,
    "LocatorDia1": LOCATOR_CALLOUT_TEXT,
}
