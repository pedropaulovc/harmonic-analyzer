"""Pure rocker profile and rod-pin interface, without part checks or tooling."""

from __future__ import annotations

import math

from dt_cone_pivot_post_installation import MECHANISM_X_SHIFT

CURVE_RADIUS = 800.0  # top-edge arc radius = amplitude-bar length (stated)
ARM_DEPTH = 16.0  # perpendicular top-to-bottom depth (p.29 callout)
R_BOTTOM = CURVE_RADIUS + ARM_DEPTH
CENTER_Y = CURVE_RADIUS + ARM_DEPTH

ROD_HOLE_X = 127.3738 - MECHANISM_X_SHIFT
ROD_HOLE_ABOVE_BOTTOM = 5.53312035905  # preserves the level-pose pin Y after X shift
# Rod-pin hole Y (low in the strap, ch14 fan photo).
ROD_HOLE_Y = (
    CENTER_Y - math.sqrt(R_BOTTOM**2 - ROD_HOLE_X * ROD_HOLE_X)
) + ROD_HOLE_ABOVE_BOTTOM

# The pivot bore rides at the strap mid-depth.
PIVOT_MID_Y = ARM_DEPTH / 2.0  # 8.0
