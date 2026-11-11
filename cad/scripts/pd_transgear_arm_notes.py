"""Words MHA-PD-18's sheet prints: the numbered fit notes and the short
dimension callouts that link to them.

Kept out of the drawing script (drawing scripts own placement, not
manufacturing values) and out of the widely imported spec, so the wording
re-keys only this sheet.
"""

from __future__ import annotations

import _config
import _transgear_arm_plate_locating_interface as LOCATING_PIN
import pd_transgear_pin_spec as PIN
import pd_vn_transgear_arm_plate_locating_pin_spec as LOCATOR_PIN
from pd_paper_drive_assembly_steps import knob_setting_ref
from pd_transgear_arm_geometry import (
    PIN_HOLE_DEPTH,
    PIN_HOLE_DEPTH_PLACES,
    PIVOT_BORE_DIAMETRAL_CLEARANCE,
    PIVOT_FIT_CLEARANCE_PLACES,
)
from pd_rack_pinion_spec import inch_ceil_mm, inch_floor_mm, inch_text
from pd_transgear_arm_spec import (
    LATCH_PIN_NUMBER,
    LATCH_PIN_PRESS_PRINTED,
    LATCH_PIN_WALL_PRINTED,
    LOCATOR_PRESS_INTERFERENCE,
    PIN_PRESS_INTERFERENCE,
)


def _inch_range(limits: tuple[float, float], places: int = 4) -> str:
    """A clearance or interference range in inches, widened outward to
    ``places`` so it holds every part the two bands accept."""
    return (
        f"{inch_text(inch_floor_mm(min(limits), places), places)}-"
        f"{inch_text(inch_ceil_mm(max(limits), places), places)}"
    )


# Each fit callout keeps its size, its process and its mate; the fit's
# acceptance and anything else it needs stand once in a numbered note,
# linked from the callout (rule 7: size and process lines plus at most two
# lines of words; rule 4: a fit names its mate and its standard name).  The
# notes stand on sheet 2 (on sheet 1 they ran through its lower border), so
# every link from sheet 1 names their sheet (round 4: a flag on sheet 1
# pointed to no note on that sheet).  The counterbore is drawn in section A-A,
# so its Ø and floor carry no words of their own, only the link to the spring
# they seat and preload.
_PLATE = _config.parts("pd-transgear-arm-plate")
_SPRING = _config.parts("pd-vn-transgear-pivot-spring")
_PIVOT_SCREW = _config.parts("pd-vn-transgear-pivot-screw")
PIVOT_NOTE, LOCATOR_NOTE, LATCH_PIN_NOTE, SPRING_NOTE = 1, 2, 3, 4
NOTES_SHEET = 2


def see_note(number: int) -> str:
    """A sheet-1 link to a numbered note, naming the notes' sheet."""
    return f"SEE NOTE {number}, SHEET {NOTES_SHEET}"


NOTES = (
    f"{PIVOT_NOTE}. PIVOT BORE: RUNNING FIT ON PIVOT SCREW {_PIVOT_SCREW['number']}"
    " SHOULDER\n"
    "   (CLEARANCE "
    f"{_inch_range(PIVOT_BORE_DIAMETRAL_CLEARANCE, PIVOT_FIT_CLEARANCE_PLACES)}).",
    f"{LOCATOR_NOTE}. 2X DOWEL HOLES: PRESS FIT ON DOWEL {LOCATOR_PIN.PART_NUMBER}"
    f" (INTERFERENCE {_inch_range(LOCATOR_PRESS_INTERFERENCE)}).\n"
    "   MOUTH BREAKS "
    f"{inch_text(inch_floor_mm(LOCATING_PIN.HOLE_MOUTH_BREAK_AXIAL_MAX_MM, 3), 3)}"
    f" MAX FOR DOWEL GRIP. MATCH-DRILL WITH ARM PLATE {_PLATE['number']}\n"
    f"   AT ASSEMBLY, {knob_setting_ref()}.",
    f"{LATCH_PIN_NOTE}. LATCH-PIN HOLE: PRESS FIT ON LATCH PIN {LATCH_PIN_NUMBER}\n"
    f"   (INTERFERENCE {_inch_range(LATCH_PIN_PRESS_PRINTED)})."
    f" PIN HOLE TO FACES {inch_text(LATCH_PIN_WALL_PRINTED, 3)} MIN.",
    f"{SPRING_NOTE}. COUNTERBORE Ø AND FLOOR: SEAT AND PRELOAD\n"
    f"   PIVOT SPRING {_SPRING['number']}.",
)
NOTES_TEXT = "\n".join(NOTES)

PIVOT_BORE_CALLOUT = f"REAM, {see_note(PIVOT_NOTE)}"
# The arm is reamed first; the pin's land is turned to the measured ream
# (MHA-PD-23 note 1), so the interference band is the matched fit's, not
# the two parts' printed limits (machinist review, run 20261111T201934013Z).
PIN_BORE_CALLOUT = "\n".join((
    "REAM THRU",
    f"PRESS FIT ON PIN {PIN.PIN_NUMBER},",
    "LAND TURNED TO MEASURED REAM",
    f"(INTERFERENCE {_inch_range(PIN_PRESS_INTERFERENCE)})",
))
# Note 2 names the dowel and its press; the callout links it (round 2: the
# dowel named on both was named twice for one pattern).
LOCATOR_CALLOUT_TEXT = f"2X REAM THRU, {see_note(LOCATOR_NOTE)}"
# Size, process and depth at the callout (round 2: a depth is never deferred
# to a view; section A-A keeps it as a reference); note 3 names the latch
# pin.  Round 3's "BLIND FLAT-BOTTOM REAM" row was so wide its leader cut the
# "B" of BLIND; the shorter row lets the text stand right of the hole, so the
# leader leaves its left end straight up.
PIN_HOLE_CALLOUT = "\n".join((
    f"REAM <HOLE-DEPTH> {inch_text(PIN_HOLE_DEPTH, PIN_HOLE_DEPTH_PLACES)} FLAT BOTTOM",
    see_note(LATCH_PIN_NOTE),
))
SPRING_CALLOUT = see_note(SPRING_NOTE)
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
    "SpotFaceDia": SPRING_CALLOUT,
    "FloorDepth": SPRING_CALLOUT,
    "PinHoleDia": PIN_HOLE_CALLOUT,
    "LocatorDia1": LOCATOR_CALLOUT_TEXT,
}
