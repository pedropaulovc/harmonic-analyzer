r"""Pure-data dimensional contract shared by the crank pin and drawing."""

from __future__ import annotations

import math

from _gtol_spec import ConeFace
from _surface_finish import MACHINED_UM, SurfaceFinishControl

PIN_LENGTH = 45.0
# CUSTOM 1:48 self-holding taper (0.9375 on diameter over the 45 mm length),
# dimensioned by its two end diameters on the drawing -- NOT a standard No. 2
# taper pin (whose 0.193 in / Ø4.90 large end would not match these ends). The
# Ø5.0 small end sits at the crank-hub cross-hole nominal; the big end is the
# small end plus the 1:48 on-diameter rise, so the drive-fit taper contacts along
# its whole length. The hub's cross-hole is taper-reamed with the shaft to the
# same 1:48 to suit this removable service pin at assembly.
SMALL_END_DIA = 5.0
BIG_END_DIA = SMALL_END_DIA + PIN_LENGTH / 48.0  # 5.9375
# Keeper-ring cross-hole through the big end (ch11 p.14 page002_img01: the
# brass ring hangs from a hole in the pin's head), perpendicular to the axis.
# Sized for the round Ø10 ring's wire arc (dt_crank_pin_ring_spec asserts the air).
RING_HOLE_DIA = 2.1
RING_HOLE_X = 3.7  # from the big end: a 2.0 ligament at the worst-case band
TAPER_HALF_ANGLE_DEGREES = math.degrees(
    math.atan((BIG_END_DIA - SMALL_END_DIA) / (2.0 * PIN_LENGTH))
)

SURFACE_FINISHES = (
    SurfaceFinishControl(
        "taper_seat",
        MACHINED_UM,
        ConeFace(TAPER_HALF_ANGLE_DEGREES, contains_x_mm=PIN_LENGTH / 2.0),
    ),
)

DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "PinProfile": {"Length"},
}
# One place: the pin length is a hand-fitted part's overall size, held to the
# general .X band.
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "PinProfile": {"Length": 1},
}

# The cross-hole's thinnest wall to the pin surface at the printed worst
# case: the taper at the hole's .XX station, both at their adverse .XX limits,
# and the drilled hole at +0.10. Rounded DOWN: the sheet never states more web
# than the limits give.
_XX_BAND = 0.51
_DRILL_OVERSIZE = 0.10
_TAPER_PER_MM = (BIG_END_DIA - SMALL_END_DIA) / PIN_LENGTH
PIN_DIA_AT_RING_HOLE_MIN = (
    BIG_END_DIA - _XX_BAND - _TAPER_PER_MM * (RING_HOLE_X + _XX_BAND)
)
CROSS_HOLE_WEB_MIN = (
    math.floor((PIN_DIA_AT_RING_HOLE_MIN - RING_HOLE_DIA - _DRILL_OVERSIZE) / 2.0 * 100.0)
    / 100.0
)
# Named exception: MHA-DT-009 web (drawing-simplicity-policy.md, "Named exceptions").
CROSS_HOLE_WEB_NOTE = f"CROSS-HOLE WEB TO THE PIN SURFACE {CROSS_HOLE_WEB_MIN:.2f} MIN."

DRAWING_NOTES = "\n".join(
    (
        "CUSTOM 1:48 SELF-HOLDING TAPER (0.9375 ON DIA OVER 45.0) BETWEEN THE END "
        "DIAMETERS SHOWN; NO STEPS.",
        "HAND-FIT TO THE CRANK-HUB CROSS-HOLE, TAPER-REAMED WITH THE SHAFT AT "
        "ASSEMBLY TO THE SAME 1:48; LIGHT DRIVE FIT, REMOVABLE BY TAP ON SMALL END.",
        f"DRILL DIA {RING_HOLE_DIA:.2f} THRU ACROSS THE AXIS {RING_HOLE_X:.2f} FROM THE BIG END "
        "FOR THE BRASS KEEPER RING.",
        CROSS_HOLE_WEB_NOTE,
    )
)
END_VIEW_NOTE = "END VIEW SCALE 4:1"
