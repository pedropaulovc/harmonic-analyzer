r"""Pure-data dimensional contract shared by the pen adjuster stud build and drawing.

The pen-height adjuster (engineerguy 4/4, 9:15-10:34): a turned brass stud
threaded into the pen rod's top face, locked by a brass jam nut
(``pn-vn-pen-adjust-nut``) run down onto the rod top, with a cross-drilled eye
head the pen wire ties through. Screwing the stud in or out raises or lowers
the whole pen carriage against the wire without re-tying it.

Part frame: origin at the threaded end (bottom) on the axis; +Y up the axis;
the eye's cross hole runs along X. ``build_pn_pen_adjust_screw`` names the
stud axis Axis1 (Front Plane x Right Plane) for the assembly's coaxial mate.

Dimension scheme (drawing-guidelines.md rules 10/11): the overall length from
the faced threaded end to the faced head end, the head's height and the eye's
station from the head's own faced end, and the usable full-thread length from
the threaded end. The plain shank between the thread's end and the head is
what is left in length: the die's run-out (rule 16), never dimensioned. Its
diameter is the thread's basic major, printed once as a reference so the
plain section is not left without a size. A projected split line rings the
shank at the thread limit, so the side view shows where the thread stops.
The shoulder's internal corner is a modelled fillet (``ShoulderFillet``)
printed as a single MAX radius at the title block's INSIDE CORNERS limit.

Drawing contract: ``build_pn_pen_adjust_screw`` marks exactly
``DRAWING_DIMENSIONS`` and authors ``DRAWING_PRECISION`` natively on the part;
``draw_pn_pen_adjust_screw`` keeps exactly the same names, and
``test_pn_pen_adjust_screw_drawing`` fails the moment one side drifts. Every
marked dimension lives in a Right-plane sketch, so all of them import into
the *Right side view, where the eye is seen end-on. The eye's station rides
a hidden reference sketch (``EyeStationReference``): the Hole Wizard's
cylindrical placement sketch carries no printable dimension. The plain
shank's diameter (``PlainDia``) is a StudProfile dimension on the plain
shank's own profile segment, driven by ThreadDia and printed as a
parenthesised reference (``REFERENCE_DIMENSIONS``).

Issue #290: the sheet prints decimal inch (``drawing_unit: in``). Lengths stay
physical millimetres, each the exact decimal of the inch value it prints.
Exempt from the grid: the #0-80 thread and the #54 eye (vendor sizes), and
the 26.0 overall length, which sets the stud head's height on the carriage
(``pn_pen_carriage_geom.STUD_HEAD_TOP_REST_Y``, read by the pen-wire and
top-level assemblies); it prints 1.02 at the title block's .XX, which holds
it: the fitter sets the head by the stud's measured length
(``pn_pen_assembly_spec``, code review C05), so no stack reads the band.
"""

from __future__ import annotations

import _config
from _hole_spec import HoleSpec, NUMBER_DRILL_MM, THREAD_MAJOR_MM
from _inch_wall_limits import WALL_TARGET_MM
from _package_units import drawing_unit
from _printed_tolerance import (
    drilled_oversize_mm,
    inside_corner_radius_mm,
    printed_band_mm,
    printed_deviations,
)
from pn_pen_rod_spec import STUD_ENGAGEMENT, STUD_TAP_SPEC, STUD_THREAD
from _mg_wheel_rim_geometry import PEN_WIRE_DIA
import pn_vn_pen_adjust_nut_spec as jam_nut

# The registry row's drawing_unit (in) is this sheet's unit.
UNIT = drawing_unit("parts/pn-pen-adjust-screw", _config.parts("pn-pen-adjust-screw"))

THREAD = STUD_THREAD  # one source: the rod's top tap names the thread
THREAD_MAJOR = THREAD_MAJOR_MM[THREAD]
THREAD_PITCH = 25.4 / int(THREAD.rsplit("-", 1)[1])  # #0-80: 80 TPI
# Head .24 x .32 with the eye on its mid-height: at the worst case of the
# printed bands every wall round the #54 eye clears the rule 17 target
# (asserted below).
HEAD_DIA = 6.096  # .24
HEAD_HEIGHT = 8.128  # .32
# Usable full thread from the threaded end; the die stops short of the head.
FULL_THREAD_LENGTH = 14.732  # .58
OVERALL_LENGTH = 26.0  # faced threaded end to head end; exempt, prints 1.02
SHANK_LENGTH = OVERALL_LENGTH - HEAD_HEIGHT  # threaded end to the shoulder
PLAIN_SHANK = SHANK_LENGTH - FULL_THREAD_LENGTH  # die run-out under the head
EYE_SPEC = HoleSpec("drilled_number", "#54")  # wire tie-off cross hole
EYE_DIA = NUMBER_DRILL_MM[EYE_SPEC.size]
EYE_FROM_HEAD_END = HEAD_HEIGHT / 2.0  # .16, cross hole on the head's mid-height
EYE_Y = OVERALL_LENGTH - EYE_FROM_HEAD_END

# Installed: the stud threads STUD_ENGAGEMENT into the rod and the jam nut
# sits on the rod top; the full thread above the nut is the pen-height
# adjustment the stud can back out by and still lock.
ADJUSTMENT_RANGE = 8.0
# Every length and head size prints the title block's .XX, the overall length
# too (OVERALL_DEVIATIONS: its printed 1.02 about the 26.0 closure).
_LENGTH_BAND = printed_band_mm(2, unit=UNIT)
OVERALL_PLACES = 2
OVERALL_DEVIATIONS = printed_deviations(OVERALL_LENGTH, OVERALL_PLACES, unit=UNIT)
_EYE_MAX_R = (EYE_DIA + drilled_oversize_mm(unit=UNIT)) / 2.0  # DRILLED HOLES +.004/0
_WALL_TARGET = WALL_TARGET_MM  # drawing-guidelines.md rule 17 (walls and webs)

# Rule 17 at the worst case of the printed bands: the eye's station from the
# head end and the head's height each off by the .XX band, the head's Ø small
# by it, the drill at its DRILLED HOLES maximum.
EYE_END_WALL_MIN = EYE_FROM_HEAD_END - _LENGTH_BAND - _EYE_MAX_R
EYE_SHOULDER_WALL_MIN = (
    (HEAD_HEIGHT - _LENGTH_BAND) - (EYE_FROM_HEAD_END + _LENGTH_BAND) - _EYE_MAX_R
)
EYE_SIDE_WALL_MIN = (HEAD_DIA - _LENGTH_BAND) / 2.0 - _EYE_MAX_R

if EYE_DIA <= PEN_WIRE_DIA + 0.3:
    raise AssertionError("eye cross hole does not pass the pen wire")
if min(EYE_END_WALL_MIN, EYE_SHOULDER_WALL_MIN, EYE_SIDE_WALL_MIN) < _WALL_TARGET:
    raise AssertionError(
        "a worst-case wall round the eye is under drawing-guidelines.md "
        "rule 17 (walls and webs): end "
        f"{EYE_END_WALL_MIN:.2f}, shoulder {EYE_SHOULDER_WALL_MIN:.2f}, "
        f"side {EYE_SIDE_WALL_MIN:.2f}"
    )
if HEAD_DIA <= THREAD_MAJOR:
    raise AssertionError("eye head must shoulder over the thread")
if (
    FULL_THREAD_LENGTH - _LENGTH_BAND
    < STUD_ENGAGEMENT + jam_nut.THICKNESS + ADJUSTMENT_RANGE
):
    raise AssertionError(
        "the shortest accepted full thread no longer covers the rod engagement, "
        "the jam nut and the pen-height adjustment"
    )
# Worst case of the three printed lengths (overall short, head and thread
# long): the die must still stop at least one pitch short of the shoulder
# (drawing-guidelines.md rule 16 (thread to a shoulder needs a relief)).
PLAIN_SHANK_MIN = (
    (OVERALL_LENGTH + OVERALL_DEVIATIONS[0])
    - (HEAD_HEIGHT + _LENGTH_BAND)
    - (FULL_THREAD_LENGTH + _LENGTH_BAND)
)
if PLAIN_SHANK_MIN < THREAD_PITCH:
    raise AssertionError("full thread runs into the head's shoulder")

# Shoulder root (drawing-guidelines.md rules 11 and 16): the corner where the
# plain shank meets the head's underside is a modelled fillet whose radius
# prints, natively, as a single MAX limit (sharp is good, anything up to the
# limit is good).  Nothing seats on the head's underside (the jam nut bears on
# the rod top, and even with the stud run in to the bottom of its tap drill at
# the worst-case short shank the nut stands clear of the shoulder, asserted
# below), so no function tightens it past the title block's INSIDE CORNERS
# R.040 MAX: the printed limit IS that row, and the model stands at it.  At
# that limit the fillet must still leave the die a pitch of plain shank at the
# worst-case plain length, and end inside the head's underside.
SHOULDER_CORNER_R_MAX = inside_corner_radius_mm(unit=UNIT)  # R.040 MAX
SHOULDER_FILLET_R = SHOULDER_CORNER_R_MAX
# (upper, lower) deviations: the nominal IS the limit, down to sharp.
SHOULDER_FILLET_BAND = (0.0, -SHOULDER_FILLET_R)
SHOULDER_FILLET_TOL_TYPE = 6  # swTolType_e.swTolMAX: prints "R.040 MAX"
SHOULDER_FILLET_PLACES = 3
SHOULDER_FILLET_R_LIMIT = PLAIN_SHANK_MIN - THREAD_PITCH
if SHOULDER_FILLET_R > SHOULDER_FILLET_R_LIMIT:
    raise AssertionError("the shoulder radius eats the die's worst-case run-out")
if THREAD_MAJOR / 2.0 + SHOULDER_FILLET_R >= (HEAD_DIA - _LENGTH_BAND) / 2.0:
    raise AssertionError("shoulder fillet must end inside the head's underside")
# The shoulder's lowest station over the rod top: the shortest printed shank
# (overall short, head long) with the stud bottomed in the rod's tap drill.
SHOULDER_OVER_ROD_TOP_MIN = (
    (OVERALL_LENGTH + OVERALL_DEVIATIONS[0])
    - (HEAD_HEIGHT + _LENGTH_BAND)
    - STUD_TAP_SPEC.depth_mm
)
if SHOULDER_OVER_ROD_TOP_MIN <= jam_nut.THICKNESS:
    raise AssertionError("the jam nut can reach the head's shoulder")

DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "StudProfile": {
        "ThreadDia",
        "FullThreadLength",
        "HeadDia",
        "HeadHeight",
        "OverallLength",
        "PlainDia",
    },
    "EyeStationReference": {"EyeFromHeadEnd"},
    "ShoulderFillet": {"ShoulderRadius"},
}
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "StudProfile": {
        "ThreadDia": 3,
        "FullThreadLength": 2,
        "HeadDia": 2,
        "HeadHeight": 2,
        "OverallLength": OVERALL_PLACES,
        # A reference size carries no band; three places read the basic .060.
        "PlainDia": 3,
    },
    "EyeStationReference": {"EyeFromHeadEnd": 2},
    "ShoulderFillet": {"ShoulderRadius": SHOULDER_FILLET_PLACES},
}
DRAWING_PRECISION_BY_NAME: dict[str, int] = {
    name: places
    for dimensions in DRAWING_PRECISION.values()
    for name, places in dimensions.items()
}
if {
    feature: set(names) for feature, names in DRAWING_PRECISION.items()
} != DRAWING_DIMENSIONS:
    raise AssertionError("every marked adjuster dimension needs authored places")
# The plain shank is turned with the thread blank: its Ø prints once,
# parenthesised, (Ø.060), no band.
REFERENCE_DIMENSIONS = frozenset({"PlainDia"})
if not REFERENCE_DIMENSIONS <= DRAWING_DIMENSIONS["StudProfile"]:
    raise AssertionError("a printed reference must be a marked StudProfile dimension")

# The thread's major-diameter dimension prints as its designation (the
# title block's THREADS row owns the class), so the print never states the
# basic major as a plain size; the full-thread length says what it bounds.
THREAD_CALLOUT = f"{THREAD} UNF"
DIMENSION_TEXT = {"ThreadDia": THREAD_CALLOUT}
DIMENSION_CALLOUTS = {"FullThreadLength": "FULL THREAD"}
# Material, finish and edge breaks ride the title block; nothing else needs saying.
DRAWING_NOTES = ""
