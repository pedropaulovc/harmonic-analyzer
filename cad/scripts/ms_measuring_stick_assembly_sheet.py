"""MHA-MS-000 fitter-drawing data: the BOM, the captions and the assembly text.

Drawing-only: nothing here reaches ms-measuring-stick.SLDASM, so no assembly
builder imports this module (``test_assembly_sheet_isolation`` pins it) and a
wording edit rebuilds the drawing alone. Every printed number interpolates a
symbol of ``ms_measuring_stick_assembly_spec`` or a part/vendor spec; none is
restated here.
"""

from __future__ import annotations

import textwrap
from fractions import Fraction

import ms_measuring_stick_assembly_spec as spec
import ms_stop_spec as stop
import _mcmaster_90114a124 as plate_screw
import _mcmaster_91882a221 as thumb

DRAWING_NUMBER = "MHA-MS-000"

BOM_ORDER = (spec.STICK, spec.BLOCK, spec.PLATE, spec.PLATE_SCREW, spec.THUMB_SCREW)


def _inch_fraction(length_mm: float) -> str:
    """A vendor's nominal inch length (``1/4``, ``7/16``) from its modeled mm."""
    inches = Fraction(length_mm / 25.4).limit_denominator(64)
    if abs(float(inches) * 25.4 - length_mm) > 1e-9:
        raise ValueError(f"{length_mm} mm is not a whole sixty-fourth of an inch")
    return str(inches)


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
DRAWING_DIMENSIONS = {spec.SETTING_FEATURE: {spec.SETTING_DIMENSION}}
SETTING_CRITERION = (
    f"NEAR BLOCK FACE {spec.SETTING_NEAR_FACE_MM:.1f} "
    f"±{spec.SETTING_TOLERANCE_MM:.2f} mm FROM LEFT STICK END"
)
SETTING_REFERENCE_DESCRIPTION = (
    f"{stop.STOP_MARK:.1f} GRADUATION ON THUMBSCREW AXIS (REF)"
)
# Components own material and finish; no assembly coating operation is required.
# The fitter's order; the explode (ms_measuring_stick_explode_spec) runs steps
# 2-5 backwards. Each line names the parts as the BOM's DESCRIPTION column
# does. The block and its cover are a match-drilled pair (step 1): neither is
# interchangeable.
ASSEMBLY_STEPS = (
    "1. PLATE IS MASTER: LAYOUT BOTH HOLES ON THE STOP COVER PLATE AT ITS OWN "
    f"±{stop.PLATE_HOLE_POSITION_TOLERANCE_MM:.2f} mm LOCATIONS. CLAMP PLATE "
    f"AND BLOCK WITH {stop.MATCH_DRILL_DATUM_ALIGNMENT}; PILOT FROM PLATE "
    f"DIA {stop.PLATE_TAP_DRILL_DIA:.2f} THROUGH INTO BLOCK TO "
    f"{stop.PLATE_TAP_DRILL_DEPTH:.1f} mm CYLINDRICAL DEPTH INTO BLOCK "
    "(DEPTH EXCLUDES PLATE). REMOVE PLATE; OPEN ITS HOLES TO "
    f"DIA {stop.PLATE_CLEARANCE_DIA:.1f}; BOTTOMING-TAP BLOCK "
    f"{plate_screw.THREAD} TO {stop.PLATE_TAP_THREAD_DEPTH:.1f} mm FULL THREAD "
    "DEPTH INTO BLOCK. MARK BLOCK AND PLATE AS A PAIR.",
    f"2. START THE {thumb.THREAD} KNURLED THUMBSCREW UP INTO THE STOP BLOCK FROM "
    "ITS UNDERSIDE; KEEP THE TIP BELOW THE WINDOW FLOOR.",
    "3. LAY THE GRADUATED STICK, GRADUATED FACE UP, INTO THE BLOCK WINDOW FROM "
    "ITS OPEN SIDE.",
    "4. FIT ITS OWN STOP COVER PLATE OVER THE WINDOW, PAIR MARKS TOGETHER; DRIVE "
    f"BOTH {plate_screw.THREAD} BRASS FILLISTER SCREWS UNTIL THE HEADS SEAT.",
    f"5. SET {SETTING_CRITERION}; THEN TURN THE THUMBSCREW IN BY HAND UNTIL "
    "ITS TIP CLAMPS THE STICK AGAINST THE ROOF.",
)
ASSEMBLY_CHECKS = (
    "CHECK: WITH THE THUMBSCREW BACKED OFF THE STICK SLIDES FREELY IN THE WINDOW.",
    "CHECK: CLAMPED, THE STOP DOES NOT SLIDE ALONG THE STICK.",
    "CHECK: BOTH SCREW HEADS SEAT ON THE COVER AND THE COVER LIES FLAT ON THE BLOCK.",
)
CLAMPED_SETUP_NOTE = (
    f"CLAMPED SETUP: SET {SETTING_CRITERION}; THEN CLAMP. "
    "GRADUATED FACE AGAINST THE ROOF; THUMBSCREW TIP ON THE STICK UNDERSIDE."
)

# Overall is pure reference; the near-face value is assembly acceptance only.
REFERENCE_OVERALL_LENGTH = spec.STICK_X_MAX - spec.STICK_X_MIN
# The dimension itself states the near-face criterion and the setup note
# repeats it in words; the callout carries only the graduation reference,
# wrapped narrow enough to sit between the dimension's extension lines.
STOP_POSITION_CALLOUT_WIDTH = 21  # characters
STOP_POSITION_CALLOUT = "\n".join(
    textwrap.wrap(SETTING_REFERENCE_DESCRIPTION, width=STOP_POSITION_CALLOUT_WIDTH)
)
DRAWING_REFERENCE_PRECISION = 1

assert sorted(spec.QUANTITIES) == sorted(BOM_ORDER)
