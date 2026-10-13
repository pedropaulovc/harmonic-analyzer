r"""Pure-data dimensional contract shared by the pen adjuster stud build and drawing.

The pen-height adjuster (engineerguy 4/4, 9:15-10:34): a turned brass stud
threaded into the pen rod's top face, locked by a brass jam nut
(``vn-pen-adjust-nut``) run down onto the rod top, with a cross-drilled eye
head the pen wire ties through. Screwing the stud in or out raises or lowers
the whole pen carriage against the wire without re-tying it.

Part frame: origin at the threaded end (bottom) on the axis; +Y up the axis;
the eye's cross hole runs along X. ``build_pn_pen_adjust_screw`` names the
stud axis Axis1 (Front Plane x Right Plane) for the assembly's coaxial mate.

Drawing contract: ``build_pn_pen_adjust_screw`` marks exactly
``DRAWING_DIMENSIONS`` and authors ``DRAWING_PRECISION`` natively on the part;
``draw_pn_pen_adjust_screw`` keeps exactly the same names, and
``test_pn_pen_adjust_screw_drawing`` fails the moment one side drifts. Every
marked dimension lives in a Right-plane sketch, so all of them import into
the *Right side view, where the eye is seen end-on. The eye's station rides
a hidden reference sketch (``EyeStationReference``): the Hole Wizard's
cylindrical placement sketch carries no printable dimension.
"""

from __future__ import annotations

from _hole_spec import HoleSpec, NUMBER_DRILL_MM, THREAD_MAJOR_MM
from pn_pen_rod_spec import STUD_ENGAGEMENT, STUD_THREAD
from mg_magnifying_wheel_geom import PEN_WIRE_DIA

THREAD = STUD_THREAD  # one source: the rod's top tap names the thread
THREAD_MAJOR = THREAD_MAJOR_MM[THREAD]
THREAD_LENGTH = 18.0  # rod engagement + jam nut + adjustment range
HEAD_DIA = 5.0
HEAD_HEIGHT = 5.0
EYE_SPEC = HoleSpec("drilled_number", "#54")  # wire tie-off cross hole
EYE_DIA = NUMBER_DRILL_MM[EYE_SPEC.size]
EYE_Y = THREAD_LENGTH + HEAD_HEIGHT / 2.0  # cross hole on the head's mid-height
OVERALL_LENGTH = THREAD_LENGTH + HEAD_HEIGHT

# Installed: the stud threads STUD_ENGAGEMENT into the rod; the rest of the
# thread stands above the rod top, under the jam nut and below the head.
EXPOSED_THREAD = THREAD_LENGTH - STUD_ENGAGEMENT

if EYE_DIA <= PEN_WIRE_DIA + 0.3:
    raise AssertionError("eye cross hole does not pass the pen wire")
if (HEAD_DIA - EYE_DIA) / 2.0 < 1.5 or (HEAD_HEIGHT - EYE_DIA) / 2.0 < 1.5:
    raise AssertionError(
        "eye head ligament is under drawing-guidelines.md rule 17 (walls and webs)"
    )
if HEAD_DIA <= THREAD_MAJOR:
    raise AssertionError("eye head must shoulder over the thread")

DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "StudProfile": {"ThreadDia", "ThreadLength", "HeadDia", "HeadHeight"},
    "EyeStationReference": {"EyeY"},
}
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "StudProfile": {"ThreadDia": 3, "ThreadLength": 1, "HeadDia": 1, "HeadHeight": 1},
    "EyeStationReference": {"EyeY": 1},
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

THREAD_CALLOUT = f"{THREAD} UNF"
DRAWING_NOTES = "EYE: SMOOTH BOTH ENDS - THE PEN WIRE BEARS ON THEM."
