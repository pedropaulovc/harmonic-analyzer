"""Pure rocker profile and rod-pin interface, without part checks or tooling."""

from __future__ import annotations

import math

from _cone_axis_constants import MECHANISM_X_SHIFT

# The book's arc system (ch. 14): a top-edge arc of the amplitude-bar length
# (stated) and a bottom-edge arc the p.29 callout's 16.0 deeper, concentric.
# The arm-local frame keeps the book's origin, on the mirror axis at the book
# bottom edge, so the arcs' shared centre, the pivot bore and the rod pin
# stay where the channel assembly and the kinematics place them.
BOOK_TOP_RADIUS = 800.0
BOOK_DEPTH = 16.0
BOOK_BOTTOM_RADIUS = BOOK_TOP_RADIUS + BOOK_DEPTH
CENTER_Y = BOOK_BOTTOM_RADIUS  # 816

# Owner ruling 2026-11-08 (Pedro), #2144 item 10.3: the modelled edges sit at
# the middle of the profile zones the sheet used to state one-sided (top edge
# .020 wholly outside the R800 arc, lower outline .020 wholly inside the
# R816 one), so the print's zones are equal-bilateral about the nominal and
# the parts the zones admit are unchanged. Both edges move .010 up, about
# the same centre: the arcs shrink by that much.
PROFILE_MID_ZONE_SHIFT = 0.254  # .010
CURVE_RADIUS = BOOK_TOP_RADIUS - PROFILE_MID_ZONE_SHIFT  # 799.746, the bar foot's slide
R_BOTTOM = BOOK_BOTTOM_RADIUS - PROFILE_MID_ZONE_SHIFT  # 815.746
ARM_DEPTH = R_BOTTOM - CURVE_RADIUS  # 16.0, perpendicular top-to-bottom depth

ROD_HOLE_X = 127.3738 - MECHANISM_X_SHIFT
ROD_HOLE_ABOVE_BOTTOM = 5.53312035905  # over the book bottom arc: the level-pose pin Y after the X shift
# Rod-pin hole Y (low in the strap, ch14 fan photo), fixed in the frame.
ROD_HOLE_Y = (
    CENTER_Y - math.sqrt(BOOK_BOTTOM_RADIUS**2 - ROD_HOLE_X * ROD_HOLE_X)
) + ROD_HOLE_ABOVE_BOTTOM

# The pivot bore: the book strap's mid-depth, 8.254 under the top edge and
# 7.746 over the bottom one at mid-zone.
PIVOT_MID_Y = BOOK_DEPTH / 2.0  # 8.0
