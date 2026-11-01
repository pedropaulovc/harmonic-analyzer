r"""Pure-data dimensional contract shared by the crank pin and drawing.

Issue #290: the sheet prints decimal inch (``drawing_unit: in``).  The taper's
end diameters and length keep their millimetre nominals: the big end sizes the
inherited crank hub's cross-hole (dt_crank_hub_geometry), so they print rounded
at .XX, the model inside each band.  The cross-hole is a #45 drill on the
printed grid.
"""

from __future__ import annotations

import math

import _config
from _package_units import drawing_unit
from _printed_tolerance import drilled_oversize_mm, printed_band_mm
from _title_block_units import render_number

UNIT = drawing_unit("parts/dt-crank-pin", _config.parts("dt-crank-pin"))

PIN_LENGTH = 45.0
# CUSTOM 1:48 self-holding taper (0.9375 mm on diameter over the length),
# dimensioned by its two end diameters on the drawing -- NOT a standard No. 2
# taper pin (whose 0.193 in large end would not match these ends). The small
# end sits at the crank-hub cross-hole nominal; the big end is the small end
# plus the 1:48 on-diameter rise, so the drive-fit taper contacts along its
# whole length. The hub's cross-hole is taper-reamed with the shaft to the same
# 1:48 to suit this removable service pin at assembly.
SMALL_END_DIA = 5.0
BIG_END_DIA = SMALL_END_DIA + PIN_LENGTH / 48.0  # 5.9375
# Keeper-ring cross-hole through the big end (ch11 p.14 page002_img01: the
# brass ring hangs from a hole in the pin's head), perpendicular to the axis.
# A #45 drill, sized for the round ring's wire arc (dt_crank_pin_ring_spec
# asserts the air).
RING_HOLE_DIA = 2.0828  # .082
RING_HOLE_X = 3.81  # .15 from the big end: a ligament over the .080 target

# No roughness symbol: the taper is a pinned light drive fit that neither runs
# nor slides (drawing-guidelines.md rule 6 (roughness symbols only where a
# surface runs, slides or locates)); the Finish field covers the turned face.
SURFACE_FINISHES = ()

# The cross-hole prints natively: its Ø (a drilled hole: three places under
# the DRILLED HOLES row) and its station from the big-end face (two places),
# so no note restates either (drawing-guidelines.md rule 7).
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "PinProfile": {"Length"},
    "RingHoleProfile": {"RingHoleX", "RingHoleDia"},
}
# Two places on the length: the hand-fitted part's overall size, held to the
# general .XX band.
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "PinProfile": {"Length": 2},
    "RingHoleProfile": {"RingHoleX": 2, "RingHoleDia": 3},
}

# The cross-hole's thinnest wall to the pin surface at the printed worst
# case: the taper at the hole's .XX station, both at their adverse .XX limits,
# and the drilled hole at its DRILLED HOLES oversize. The big end's lower limit
# is the PRINTED .XX value's, not the mm model's (#290 review of 29af6f44d:
# from Ø.23 -.01 the web is .065, not the .067 the model's .2338 gave).
# Rounded DOWN: the sheet never states more web than the limits give.
_XX_BAND = printed_band_mm(2, unit=UNIT)
_DRILL_OVERSIZE = drilled_oversize_mm(unit=UNIT)
_TAPER_PER_MM = (BIG_END_DIA - SMALL_END_DIA) / PIN_LENGTH
BIG_END_DIA_PRINTED = round(BIG_END_DIA / 25.4, 2) * 25.4
PIN_DIA_AT_RING_HOLE_MIN = (
    BIG_END_DIA_PRINTED - _XX_BAND - _TAPER_PER_MM * (RING_HOLE_X + _XX_BAND)
)
CROSS_HOLE_WEB_MIN = round(
    math.floor(
        (PIN_DIA_AT_RING_HOLE_MIN - RING_HOLE_DIA - _DRILL_OVERSIZE) / 2.0 / 25.4 * 1000.0
    )
    / 1000.0
    * 25.4,
    6,
)
# The shortfall is stated under the hole's own Ø callout (rule 20), flagged
# where it applies (rule 7); the review files it as a non-gating shortfall.
# Owner ruling 2026-11-01 accepts it as minor exception RV-01 in
# dt-crank-pin.yaml (#989).
CROSS_HOLE_WEB_CALLOUT = (
    f"WEB {render_number(round(CROSS_HOLE_WEB_MIN / 25.4, 3), 'in', 3)} MIN"
)
DIMENSION_CALLOUTS: dict[str, str] = {
    "RingHoleDia": f"#45 DRILL THRU\n{CROSS_HOLE_WEB_CALLOUT}",
}

# The one note, flagged on the taper by a leader (rule 7): the taper ratio the
# end diameters' .XX bands do not control, and the matched fit with both
# mates by name and number (rule 4). Four lines, short enough to stand
# between the end diameters' callouts above the side view.
DRAWING_NOTES = "\n".join(
    (
        "1:48 TAPER ON DIAMETER, LIGHT DRIVE",
        "FIT IN THE CROSS-HOLE OF CRANK HUB",
        "MHA-DT-31 AND CRANKSHAFT MHA-DT-11,",
        "TAPER-REAMED TOGETHER AT ASSEMBLY",
    )
)
END_VIEW_NOTE = "END VIEW SCALE 4:1"
