r"""Pure-data dimensional contract shared by the crank pin and drawing.

Owner ruling 2026-11-20 (#2368, option B, in his words: "B"): MHA-DT-09 is a
bought ASME B18.8.2 No. 3 x 1-3/4 taper pin that the shop only cross-drills
for the keeper ring.  The pin's ends and length are the supplier's, so the
sheet dimensions none of them (undimensioned purchased geometry is
reference, the MHA-DT-39 form); it prints the cross-hole, a #45 drill on the
printed grid, from the as-bought big-end face.  Issue #290: decimal inch
(``drawing_unit: in``).
"""

from __future__ import annotations

import math

import _config
from _package_units import drawing_unit
from _printed_tolerance import drilled_oversize_mm, printed_band_mm
from _title_block_units import render_number

UNIT = drawing_unit("parts/dt-crank-pin", _config.parts("dt-crank-pin"))

MM_PER_IN = 25.4
# McMaster-Carr 98390A254 (read live 2026-11-20): No. 3 taper pin, 0.219 in
# large end, 1-3/4 in long, 0.183 in small end, 1:48 taper, 12L14 carbon
# steel, ASME B18.8.2, pack of 25.
SKU = "98390A254"
DESIGNATION = "No. 3 X 1-3/4 TAPER PIN"
STANDARD = "ASME B18.8.2"
PIN_LENGTH = 1.75 * MM_PER_IN  # 44.45
BIG_END_DIA = 0.219 * MM_PER_IN  # 5.5626
# The standard 1:48 taper on diameter (1/4 in per foot) over the length: the
# .1825 small end the catalogue rounds to .183.
SMALL_END_DIA = BIG_END_DIA - PIN_LENGTH / 48.0
# ASME B18.8.2 commercial taper pins hold the large end +.0013/-.0007 in (as
# published by Stanho, "Standard Steel Taper Pins", and on Grainger's ASME
# B18.8.2 No. 3 listing 2PZR2, both read 2026-11-20).  The cross-hole web
# and the keeper ring's air read this band, not a printed one.
BIG_END_DIA_BAND = (0.0013 * MM_PER_IN, -0.0007 * MM_PER_IN)
# Keeper-ring cross-hole through the big end (ch11 p.14 page002_img01: the
# brass ring hangs from a hole in the pin's head), perpendicular to the axis.
# A #45 drill, sized for the round ring's wire arc (dt_crank_pin_ring_spec
# asserts the air).  Its station prints at .XX from the as-bought big end's
# RIM.  ASME B18.8.2 taper pins have crowned ends; No. 3's end crown radius is
# .209-.229 in (RC Fastener "Commercial & Precision Classes Taper Pins",
# ASME B18.8.2-2000 table, read 2026-11-20), a crown about .03 in high over
# the .219 end.  The model's flat big end is that rim plane: the crown lies
# outboard of it, so it adds metal beyond the hole-to-end ligament and never
# takes any; measured from the crown's apex instead, the hole would sit .03
# nearer the end, so the station names the rim (dt_crank_pin_notes).
RING_HOLE_DIA = 2.0828  # .082
RING_HOLE_X = 3.81  # .15 from the big end: a ligament over the .080 target

# No roughness symbol: the taper is a pinned light drive fit that neither runs
# nor slides (drawing-guidelines.md rule 6 (roughness symbols only where a
# surface runs, slides or locates)); the pin's surface is as supplied.
SURFACE_FINISHES = ()

# The cross-hole prints natively: its Ø (a drilled hole: three places under
# the DRILLED HOLES row) and its station from the big-end face (two places),
# so no note restates either (drawing-guidelines.md rule 7).  The bought
# pin's length and end diameters are not dimensioned.
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "RingHoleProfile": {"RingHoleX", "RingHoleDia"},
}
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "RingHoleProfile": {"RingHoleX": 2, "RingHoleDia": 3},
}

# The cross-hole's thinnest wall to the pin surface at the worst case: the
# smallest catalogue big end, the hole at its .XX station's small-end limit
# and drilled at its DRILLED HOLES oversize.  Rounded DOWN: the sheet never
# states more web than the limits give.
RING_HOLE_X_BAND = printed_band_mm(2, unit=UNIT)
_DRILL_OVERSIZE = drilled_oversize_mm(unit=UNIT)
_TAPER_PER_MM = (BIG_END_DIA - SMALL_END_DIA) / PIN_LENGTH
PIN_DIA_AT_RING_HOLE_MIN = (
    BIG_END_DIA + BIG_END_DIA_BAND[1] - _TAPER_PER_MM * (RING_HOLE_X + RING_HOLE_X_BAND)
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
END_VIEW_NOTE = "END VIEW SCALE 4:1"

# The part's Manufacturing Notes property: the bought pin, the one added
# operation and the matched fit with both mates by name and number (rule 4).
DRAWING_NOTES = "\n".join(
    (
        f"McMASTER-CARR {SKU} {DESIGNATION}, {STANDARD};",
        "DRILL THE #45 RING HOLE ONLY. DRIVE FIT IN THE CROSS-HOLE",
        "OF CRANK HUB MHA-DT-31 AND CRANKSHAFT MHA-DT-11,",
        "TAPER-REAMED TOGETHER AT ASSEMBLY",
    )
)
