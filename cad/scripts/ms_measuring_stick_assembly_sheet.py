"""MHA-MS-00 fitter-drawing data: the BOM, the captions and the assembly text.

Drawing-only: nothing here reaches ms-measuring-stick.SLDASM, so no assembly
builder imports this module (``test_assembly_sheet_isolation`` pins it) and a
wording edit rebuilds the drawing alone. Printed dimensions interpolate a
symbol of ``ms_measuring_stick_assembly_spec`` or a part/vendor spec; mate
drawing numbers come from the part registry.

The near-face setting remains a controlled native model dimension. Its
attached callout names the measured block face; step 5 explains the
stick-mark/thumbscrew-axis indexing purpose. STOP_MARK still owns the nominal
alignment, with no REF qualifier on the controlled setting.

Every printed length is in the package's unit (``spec.SETTING_UNIT``, held
to the assembly contract's ``drawing_unit`` by the builder), rendered as the
sheet prints it (ASME inch text has no leading zero and no unit word).
"""

from __future__ import annotations

from fractions import Fraction

import _config
import ms_measuring_stick_assembly_spec as spec
import ms_stop_spec as stop
import _mcmaster_90114a124 as plate_screw
import sh_vn_thumb_screw_spec as thumb
from _title_block_units import LENGTH_UNITS, render_number

DRAWING_NUMBER = "MHA-MS-00"
PLATE_DRAWING_NUMBER = str(_config.parts("ms-stop-plate")["number"])

BOM_ORDER = (spec.STICK, spec.BLOCK, spec.PLATE, spec.PLATE_SCREW, spec.THUMB_SCREW)

# Drill diameters print at three places; the match-drill depths at the stop
# sheets' own hole-callout places, so both drawings print one number.
DIAMETER_PLACES = 3
DEPTH_PLACES = stop.HOLE_CALLOUT_PRECISION
_UNIT = spec.SETTING_UNIT


def _inch_fraction(length_mm: float) -> str:
    """A vendor's nominal inch length (``1/4``, ``7/16``) from its modeled mm."""
    inches = Fraction(length_mm / 25.4).limit_denominator(64)
    if abs(float(inches) * 25.4 - length_mm) > 1e-9:
        raise ValueError(f"{length_mm} mm is not a whole sixty-fourth of an inch")
    return str(inches)


def _printed(length_mm: float, places: int) -> str:
    """A part's model length as the sheet prints it; a length off the
    ``places`` grid raises instead of printing a number the model is not."""
    return render_number(length_mm / LENGTH_UNITS[_UNIT], _UNIT, places)


def _printed_rounded(length_mm: float, places: int) -> str:
    """An exempt closure nominal as its native dimension shows it: rounded to
    ``places``, where the model keeps the exact value."""
    return render_number(round(length_mm / LENGTH_UNITS[_UNIT], places), _UNIT, places)


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
SETTING_CRITERION = (
    f"NEAR BLOCK FACE "
    f"{_printed_rounded(spec.SETTING_NEAR_FACE_MM, spec.SETTING_PRECISION)} "
    f"±{_printed(spec.SETTING_TOLERANCE_MM, spec.SETTING_TOLERANCE_PRECISION)} "
    "FROM LEFT STICK END"
)
# Components own material and finish; no assembly coating operation is required.
# The fitter's order; the explode (ms_measuring_stick_explode_spec) runs steps
# 2-5 backwards. Each line names the parts as the BOM's DESCRIPTION column
# does. The block and its cover are a match-drilled pair (step 1): neither is
# interchangeable.
ASSEMBLY_STEPS = (
    "1. PLATE IS MASTER: LAY OUT STOP COVER PLATE HOLES PER "
    f"{PLATE_DRAWING_NUMBER}; LEAVE UNDRILLED. "
    f"CLAMP PLATE AND BLOCK WITH {stop.MATCH_DRILL_DATUM_ALIGNMENT}; PILOT "
    f"DIA {_printed(stop.PLATE_TAP_DRILL_DIA, DIAMETER_PLACES)} THROUGH PLATE INTO BLOCK TO "
    f"{_printed(stop.PLATE_TAP_DRILL_DEPTH, DEPTH_PLACES)} CYLINDRICAL DEPTH INTO BLOCK "
    "(DEPTH EXCLUDES PLATE). REMOVE PLATE; OPEN ITS HOLES TO "
    f"DIA {_printed(stop.PLATE_CLEARANCE_DIA, DIAMETER_PLACES)}; BOTTOMING-TAP BLOCK "
    f"{plate_screw.THREAD} TO {_printed(stop.PLATE_TAP_THREAD_DEPTH, DEPTH_PLACES)} FULL THREAD "
    "DEPTH INTO BLOCK. MARK BLOCK AND PLATE AS A PAIR.",
    f"2. START THE {thumb.THREAD} KNURLED THUMBSCREW DOWN INTO THE STOP BLOCK "
    "FROM ITS TAPPED FACE; KEEP THE TIP CLEAR OF THE WINDOW.",
    "3. LAY THE STICK IN THE OPEN WINDOW, GRADUATED FACE OPPOSITE THE THUMBSCREW.",
    "4. FIT ITS OWN STOP COVER PLATE OVER THE WINDOW, PAIR MARKS TOGETHER; DRIVE "
    f"BOTH {plate_screw.THREAD} BRASS FILLISTER SCREWS UNTIL THE HEADS SEAT.",
    f"5. SET {SETTING_CRITERION}; THEN TURN THE THUMBSCREW IN BY HAND UNTIL "
    "ITS TIP CLAMPS THE PLAIN FACE; THUMBSCREW ABOVE THE STICK.",
)
ASSEMBLY_CHECKS = (
    "CHECK: WITH THE THUMBSCREW BACKED OFF THE STICK SLIDES FREELY IN THE WINDOW.",
    "CHECK: CLAMPED, THE STOP DOES NOT MOVE ALONG THE STICK.",
    "CHECK: BOTH SCREW HEADS SEAT ON THE COVER AND THE COVER LIES FLAT ON THE BLOCK.",
)
CLAMPED_SETUP_NOTE = (
    f"CLAMPED SETUP: SET {SETTING_CRITERION}; THEN CLAMP. "
    "GRADUATED FACE AGAINST THE FIXED WINDOW WALL; THUMBSCREW ON THE PLAIN FACE."
)

# Overall is pure reference; the near-face value is assembly acceptance only.
REFERENCE_OVERALL_LENGTH = spec.STICK_X_MAX - spec.STICK_X_MIN
# Name the measured face here; the setting from the left stick end is the
# whole acceptance (no view shows the division it puts on the thumbscrew axis).
STOP_POSITION_CALLOUT = "NEAR BLOCK FACE"
DRAWING_REFERENCE_PRECISION = 1

assert sorted(spec.QUANTITIES) == sorted(BOM_ORDER)
