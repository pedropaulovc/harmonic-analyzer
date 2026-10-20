"""VN-75 purchased split cotter, shown with both prongs spread for installation.

Frame: cotter insertion +Z, clevis-hole centre at origin, eye below (-Z).
The eye/flat-prong envelope uses Huyett's width and diameter, not a solid pin.
Hand-formed prong ends are representative; inspect the installed bend and
replace the cotter whenever removed. No retention force is inferred from CAD.
"""
from __future__ import annotations

from ch_rocker_arm_tl_oblique_retention_hardware_spec import (
    COTTER_SKU as SKU, COTTER_SOURCE_URL as SOURCE_URL,
    COTTER_DIA, COTTER_WIDTH, COTTER_HEAD_DIA_MIN,
    COTTER_LENGTH, COTTER_PRONG_DIFFERENCE_MIN, CLEVIS_DIA,
)

QUANTITY = 2
CALLOUT = "1/16 X 1/2 SPLIT COTTER; SPREAD BOTH PRONGS"
AXIS_NAME = "ScrewAxis"  # stock wrapper's published axis; local +Z
EYE_OUTER_RADIUS = COTTER_HEAD_DIA_MIN / 2
EYE_INNER_RADIUS = EYE_OUTER_RADIUS - COTTER_DIA / 2
EYE_CENTER = -CLEVIS_DIA / 2 - EYE_OUTER_RADIUS - 0.15
PRONG_START = EYE_CENTER + EYE_OUTER_RADIUS * 0.5
PRONG_BEND = CLEVIS_DIA / 2 + 0.6
PRONG_GAP = 0.04
PRONG_THICK = (COTTER_DIA - PRONG_GAP) / 2
# Developed straight legs, measured from the neck; unequal supplied prongs.
LONG_TAIL = COTTER_LENGTH - (PRONG_BEND - PRONG_START)
SHORT_TAIL = LONG_TAIL - COTTER_PRONG_DIFFERENCE_MIN

# Nominal native installed envelope, relative to the clevis hole centre.
# These are not supplied-part tolerances or a collision-free tool envelope.
INSTALLED_Z_MAX = PRONG_BEND + PRONG_THICK
INSTALLED_Z_MIN = EYE_CENTER - EYE_OUTER_RADIUS
INSTALLED_X_MIN = -(PRONG_GAP / 2 + PRONG_THICK + SHORT_TAIL)
INSTALLED_X_MAX = PRONG_GAP / 2 + PRONG_THICK + LONG_TAIL
INSTALLED_Y_HALF_WIDTH = COTTER_WIDTH / 2
