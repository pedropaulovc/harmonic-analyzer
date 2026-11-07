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
from pd_rack_pinion_spec import inch_ceil_mm, inch_floor_mm, inch_text
from pd_transgear_arm_spec import (
    LATCH_PIN_NUMBER,
    LATCH_PIN_PRESS_PRINTED,
    LATCH_PIN_WALL_PRINTED,
    LOCATOR_PRESS_INTERFERENCE,
    PIN_PRESS_INTERFERENCE,
    PIVOT_BORE_DIAMETRAL_CLEARANCE,
    PIVOT_FIT_CLEARANCE_PLACES,
)


def _inch_range(limits: tuple[float, float], places: int = 4) -> str:
    """A clearance or interference range in inches, widened outward to
    ``places`` so it holds every part the two bands accept."""
    return (
        f"{inch_text(inch_floor_mm(min(limits), places), places)}-"
        f"{inch_text(inch_ceil_mm(max(limits), places), places)}"
    )


# Each fit callout keeps its size, its process and its mate; the fit's
# acceptance and anything else it needs stand once in a numbered note on
# this sheet, linked from the callout (rule 7: size and process lines plus at
# most two lines of words; rule 4: a fit names its mate and its standard
# name).  The counterbore is drawn in section A-A, so its Ø and floor carry
# no words of their own, only the link to the spring they seat and preload.
_PLATE = _config.parts("pd-transgear-arm-plate")
_SPRING = _config.parts("pd-vn-transgear-pivot-spring")
_PIVOT_SCREW = _config.parts("pd-vn-transgear-pivot-screw")
PIVOT_NOTE, LOCATOR_NOTE, LATCH_PIN_NOTE, SPRING_NOTE = 1, 2, 3, 4
NOTES = (
    f"{PIVOT_NOTE}. PIVOT BORE: RUNNING FIT ON PIVOT SCREW {_PIVOT_SCREW['number']}"
    " SHOULDER, REAMED TO\n"
    "   THE MEASURED SHOULDER (CLEARANCE "
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

PIVOT_BORE_CALLOUT = f"REAM, SEE NOTE {PIVOT_NOTE}"
PIN_BORE_CALLOUT = "\n".join((
    "REAM THRU",
    f"PRESS FIT ON PIN {PIN.PIN_NUMBER}",
    f"(INTERFERENCE {_inch_range(PIN_PRESS_INTERFERENCE)})",
))
LOCATOR_CALLOUT_TEXT = "\n".join((
    f"2X REAM THRU, DOWEL {LOCATOR_PIN.PART_NUMBER}",
    f"SEE NOTE {LOCATOR_NOTE}",
))
# Note 3 names the latch pin; the callout stays inside the right border
# (round 1: its mate line ran past it).
PIN_HOLE_CALLOUT = "\n".join((
    "BLIND FLAT-BOTTOM REAM",
    f"SEE NOTE {LATCH_PIN_NOTE}",
))
SPRING_CALLOUT = f"SEE NOTE {SPRING_NOTE}"
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
