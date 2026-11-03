"""MHA-MS-00 fitter-drawing data: the BOM, the captions and the assembly text.

Drawing-only: nothing here reaches ms-measuring-stick.SLDASM, so no assembly
builder imports this module (``test_assembly_sheet_isolation`` pins it) and a
wording edit rebuilds the drawing alone. Printed dimensions interpolate a
symbol of ``ms_measuring_stick_assembly_spec`` or a part/vendor spec; mate
drawing numbers come from the part registry.

The near-face setting is a native reference dimension of the saved clamped
pose, not an acceptance band; step 5 and the setup note name the
stick-mark/thumbscrew-axis indexing it shows without repeating its value.
Printed lengths are in the assembly contract's ``drawing_unit``.
"""

from __future__ import annotations

from fractions import Fraction

import _config
import ms_measuring_stick_assembly_spec as spec
import ms_stop_spec as stop
import _mcmaster_90114a124 as plate_screw
import sh_vn_thumb_screw_spec as thumb
from _assembly_contract import assembly_contract
from _title_block_units import LENGTH_UNITS, render_number

DRAWING_NUMBER = "MHA-MS-00"
PLATE_DRAWING_NUMBER = str(_config.parts("ms-stop-plate")["number"])
BLOCK_DRAWING_NUMBER = str(_config.parts("ms-stop-block")["number"])
UNIT = assembly_contract(spec.ASM_NAME).drawing_unit

BOM_ORDER = (spec.STICK, spec.BLOCK, spec.PLATE, spec.PLATE_SCREW, spec.THUMB_SCREW)


def _inch_fraction(length_mm: float) -> str:
    """A vendor's nominal inch length (``1/4``, ``7/16``) from its modeled mm."""
    inches = Fraction(length_mm / 25.4).limit_denominator(64)
    if abs(float(inches) * 25.4 - length_mm) > 1e-9:
        raise ValueError(f"{length_mm} mm is not a whole sixty-fourth of an inch")
    return str(inches)


def _hole(length_mm: float) -> str:
    """A stop hole length as the stop sheets' hole callouts print it."""
    return render_number(
        length_mm / LENGTH_UNITS[UNIT], UNIT, stop.HOLE_CALLOUT_PRECISION
    )


# BOM DESCRIPTION cells (the parts carry no Description property); the steps
# below name the parts the same way.
BOM_DESCRIPTIONS = {
    spec.STICK: "GRADUATED STICK",
    spec.BLOCK: "STOP BLOCK",
    spec.PLATE: "STOP COVER PLATE",
    spec.PLATE_SCREW: (
        f"{plate_screw.THREAD} X {_inch_fraction(plate_screw.LENGTH)} "
        "BRASS FILLISTER SCREW"
    ),
    spec.THUMB_SCREW: (
        f"{thumb.THREAD} X {_inch_fraction(thumb.SHANK_LEN)} KNURLED THUMBSCREW"
    ),
}

EXPLODED_CAPTION = "EXPLODED VIEW - ASSEMBLY SEQUENCE ON SHEET 3"
UNDERSIDE_CAPTION = "GRADUATED UNDERSIDE"
DRAWING_DIMENSIONS = {spec.SETTING_FEATURE: {spec.SETTING_DIMENSION}}
# Components own material and finish; no assembly coating operation is required.
# The fitter's order; the explode (ms_measuring_stick_explode_spec) runs steps
# 2-5 backwards. Each line names the parts as the BOM's DESCRIPTION column
# does. The block and its cover are a match-drilled pair (step 1): neither is
# interchangeable.
# The block's own tapped-hole callout states the drill and full-thread depths;
# step 1 points to it instead of restating them.
ASSEMBLY_STEPS = (
    "1. PLATE IS MASTER: LAY OUT STOP COVER PLATE HOLES PER "
    f"{PLATE_DRAWING_NUMBER}; LEAVE UNDRILLED. "
    f"CLAMP PLATE AND BLOCK WITH {stop.MATCH_DRILL_DATUM_ALIGNMENT}; PILOT "
    f"DIA {_hole(stop.PLATE_TAP_DRILL_DIA)} THROUGH PLATE INTO BLOCK TO THE "
    f"{BLOCK_DRAWING_NUMBER} TAP DRILL DEPTH (DEPTH EXCLUDES PLATE). REMOVE "
    f"PLATE; OPEN ITS HOLES TO DIA {_hole(stop.PLATE_CLEARANCE_DIA)}; "
    f"BOTTOMING-TAP BLOCK {plate_screw.THREAD} TO THE {BLOCK_DRAWING_NUMBER} "
    "FULL THREAD DEPTH. MARK BLOCK AND PLATE AS A PAIR.",
    f"2. START THE {thumb.THREAD} KNURLED THUMBSCREW DOWN INTO THE STOP BLOCK "
    "FROM ITS TAPPED FACE; KEEP THE TIP CLEAR OF THE WINDOW.",
    "3. LAY THE STICK IN THE OPEN WINDOW, GRADUATED FACE OPPOSITE THE THUMBSCREW.",
    "4. FIT ITS OWN STOP COVER PLATE OVER THE WINDOW, PAIR MARKS TOGETHER; DRIVE "
    f"BOTH {plate_screw.THREAD} BRASS FILLISTER SCREWS UNTIL THE HEADS SEAT.",
    "5. USE THE NEAR-FACE REFERENCE DIMENSION ON SHEET 1 FOR THE SHOWN POSE "
    f"(STICK GRADUATION {stop.STOP_MARK:.1f} ON THUMBSCREW AXIS); "
    "TURN THE THUMBSCREW IN BY HAND UNTIL ITS TIP CLAMPS THE PLAIN FACE; "
    "THUMBSCREW ABOVE THE STICK.",
)
ASSEMBLY_CHECKS = (
    "CHECK: WITH THE THUMBSCREW BACKED OFF THE STICK SLIDES FREELY IN THE WINDOW.",
    "CHECK: CLAMPED, THE STOP DOES NOT MOVE ALONG THE STICK.",
    "CHECK: BOTH SCREW HEADS SEAT ON THE COVER AND THE COVER LIES FLAT ON THE BLOCK.",
)
CLAMPED_SETUP_NOTE = (
    "CLAMPED SETUP: NEAR-FACE REFERENCE DIMENSION SHOWS THE SAVED POSE, "
    f"STICK GRADUATION {stop.STOP_MARK:.1f} ON THUMBSCREW AXIS. "
    "GRADUATED FACE AGAINST THE FIXED WINDOW WALL; THUMBSCREW ON THE PLAIN FACE."
)

# Both dimensions are reference: the assembly pose, not component sizes.
REFERENCE_OVERALL_LENGTH = spec.STICK_X_MAX - spec.STICK_X_MIN
DRAWING_REFERENCE_PRECISION = 1

assert sorted(spec.QUANTITIES) == sorted(BOM_ORDER)
