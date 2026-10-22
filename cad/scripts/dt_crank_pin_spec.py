r"""Pure-data dimensional contract shared by the crank pin and drawing."""

from __future__ import annotations

import math

from _printed_drilled_tolerance import drilled_oversize_mm
from _printed_tolerance import printed_band_mm

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
# Sized for the round Ø12 ring's wire arc (dt_crank_pin_ring_spec asserts the air).
RING_HOLE_DIA = 2.1
RING_HOLE_X = 3.7  # from the big end: a 2.0 ligament at the worst-case band

# No roughness symbol: the taper is a pinned light drive fit that neither runs
# nor slides (drawing-guidelines.md rule 6 (roughness symbols only where a
# surface runs, slides or locates)); the Finish field covers the turned face.
SURFACE_FINISHES = ()

# The cross-hole prints natively: its Ø (a drilled hole: two places under the
# DRILLED HOLES row) and its station from the big-end face (two places), so
# no note restates either (drawing-guidelines.md rule 7).
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "PinProfile": {"Length"},
    "RingHoleProfile": {"RingHoleX", "RingHoleDia"},
}
# One place: the pin length is a hand-fitted part's overall size, held to the
# general .X band.
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "PinProfile": {"Length": 1},
    "RingHoleProfile": {"RingHoleX": 2, "RingHoleDia": 2},
}

# The cross-hole's thinnest wall to the pin surface at the printed worst
# case: the taper at the hole's .XX station, both at their adverse .XX limits,
# and the drilled hole at its DRILLED HOLES oversize. Rounded DOWN: the sheet
# never states more web than the limits give.
_XX_BAND = printed_band_mm(2)
_DRILL_OVERSIZE = drilled_oversize_mm()
_TAPER_PER_MM = (BIG_END_DIA - SMALL_END_DIA) / PIN_LENGTH
PIN_DIA_AT_RING_HOLE_MIN = (
    BIG_END_DIA - _XX_BAND - _TAPER_PER_MM * (RING_HOLE_X + _XX_BAND)
)
CROSS_HOLE_WEB_MIN = (
    math.floor((PIN_DIA_AT_RING_HOLE_MIN - RING_HOLE_DIA - _DRILL_OVERSIZE) / 2.0 * 100.0)
    / 100.0
)
# The shortfall is stated under the hole's own Ø callout (rule 20), flagged
# where it applies (rule 7); the review files it as a non-gating shortfall.
# Pending exception ruling: MHA-DT-09 cross-hole web (#989; the 2026-09-30
# acceptance from #1140 was reset to pending on 2026-10-11).
CROSS_HOLE_WEB_CALLOUT = f"WEB {CROSS_HOLE_WEB_MIN:.2f} MIN"
DIMENSION_CALLOUTS: dict[str, str] = {
    "RingHoleDia": f"DRILL THRU\n{CROSS_HOLE_WEB_CALLOUT}",
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
