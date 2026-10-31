"""Drawing-free vertical-rod sizes shared by its part, the magnifier assembly
and the fixture installation.

#1559: the rod's top end is a #4-40 thread turned down from the 7/32 in brass
rod, with a relief at the shoulder; it screws into the clamp's bottom-face tap
until the shoulder seats (``mg_rod_clamp_joint`` owns the thread and its
checks). The bottom end keeps its full hemisphere.

Part frame: rod axis local +X, origin at the thread tip on the axis; the
shoulder at x = SHOULDER_X, the bottom dome's tip at x = ROD_LENGTH. The
assembly turns local +X straight down (machine -Y).
"""

from __future__ import annotations

from mg_rod_clamp_joint import (
    RELIEF_DIA,
    RELIEF_WIDTH,
    ROD_THREAD_LEN,
    THREAD_BASIC_MINOR,
    THREAD_MAJOR,
)

MM_PER_IN = 25.4
# As-bought 7/32 in C36000 brass rod (owner ruling, #290): the body is never
# turned, so the sheet prints it as a REF fraction and the supplier's
# tolerance governs. +/-.005 in bounds 360 brass rounds (ASTM B16; Speedy
# Metals lists +/-.002-.005) for every worst case below and in the fixture.
ROD_DIA = 7.0 / 32.0 * MM_PER_IN
ROD_DIA_FRACTION_DENOMINATOR = 32
ROD_DIA_BAND = (0.127, -0.127)  # (upper, lower) supplier deviations
# Shoulder (the seating face) to the bottom dome's tip: the hanging length
# the output fixture slides along.
BODY_LENGTH = 124.968  # 4.92
SHOULDER_X = ROD_THREAD_LEN  # thread tip -> shoulder
ROD_LENGTH = ROD_THREAD_LEN + BODY_LENGTH  # overall, thread tip -> dome tip
DOME_R = ROD_DIA / 2.0  # full hemisphere at the bottom end
# Thread stations from the tip: the 45 deg tip chamfer down to the basic
# minor, the relief from its far edge to the shoulder.
TIP_CHAMFER = (THREAD_MAJOR - THREAD_BASIC_MINOR) / 2.0
RELIEF_START_X = SHOULDER_X - RELIEF_WIDTH

# The shoulder's seating land on the clamp's bottom face: the smallest rod and
# the largest tapped mouth, each with the title block's .010 edge break,
# leaves at least SEAT_LAND_MIN of flat land all round.
_TAP_MAJOR_OVERSIZE = 0.0508  # .002: a 2B tap's major runs over basic
_EDGE_BREAK = 0.254  # .010
SEAT_LAND_MIN = 0.508  # .020
SEAT_LAND_WORST = (
    (ROD_DIA + ROD_DIA_BAND[1] - 2.0 * _EDGE_BREAK)
    - (THREAD_MAJOR + _TAP_MAJOR_OVERSIZE + 2.0 * _EDGE_BREAK)
) / 2.0

if SEAT_LAND_WORST < SEAT_LAND_MIN - 1e-9:
    raise AssertionError(
        f"MHA-MG-04 shoulder land {SEAT_LAND_WORST:.3f} on the clamp face at worst, "
        f"under {SEAT_LAND_MIN}"
    )
if not RELIEF_DIA < THREAD_BASIC_MINOR < THREAD_MAJOR < ROD_DIA:
    raise AssertionError("MHA-MG-04 thread end does not step down from the bar")
if not 0.0 < TIP_CHAMFER < RELIEF_START_X < SHOULDER_X < ROD_LENGTH - DOME_R:
    raise AssertionError("MHA-MG-04 rod stations out of order")
