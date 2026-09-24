r"""Geometry-only contract for the pinion engage lever."""

from __future__ import annotations

ROD_ROOT_DIA = 4.0
ROD_TIP_DIA = 6.0
ROD_LEN = 86.0
ROD_Y0 = 3.5
HUB_OD = 13.0
HUB_LEN = 10.0
BORE = 6.375  # mid-limit of the +0.05/0 slip on the 6.35 lift rod (U36)
WALL_T = 2.0
CAP_SAG = 1.5
CAP_RADIUS = ((HUB_OD / 2.0) ** 2 + CAP_SAG**2) / (2.0 * CAP_SAG)

# U36 (MHA-135): the retention pin crosses the hub at mid-engagement -- half the
# bore depth in from the mouth face, which also puts it half the rod's
# engagement in from the rod's front end (the rod seats on the bore floor).
# The pin runs along the hub's local X, 3 o'clock to the +Y grip.
PIN_HOLE_DIA = 25.4 / 16.0  # 1/16 in, match-drilled through hub and rod
BORE_DEPTH = HUB_LEN - WALL_T
PIN_HOLE_FROM_MOUTH = BORE_DEPTH / 2.0
PIN_HOLE_Z = HUB_LEN / 2.0 - PIN_HOLE_FROM_MOUTH  # hub-local station, +1.0
ROD_PIN_HOLE_FROM_END = BORE_DEPTH - PIN_HOLE_FROM_MOUTH  # on the lift rod
