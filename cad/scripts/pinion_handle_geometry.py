r"""Geometry-only contract for the pinion turning handle."""

from __future__ import annotations

# 2026-09 photo re-derive (ch25 page002_img05/06/08, 4/4 v4_pinion_004):
# the grip is a ~O15 BALL on the arbor with the cross rod through it, not
# the O23 x 14 drum of the first pass -- a short O15 drum with a deep
# spherical crown keeps the turned-body/pressed-rod contract and reads as
# the ball; the cross rod is ~65 overall (each arm ~2 pinion diameters).
GRIP_DIA = 15.0
GRIP_LEN = 9.0
CAP_SAG = 3.0
# The cross rod is a separate press-fit component in the saved multibody part.
# Nominals sit at the centres of the released shaft/hole limit bands.
ROD_DIA = 6.0175
ROD_HOLE_DIA = 6.005
ROD_DOWN = 32.0
ROD_UP = 33.0
TUBE_OD = 10.5
TUBE_ID = 8.0
TUBE_LEN = 10.0
WALL_T = 2.0
CAP_RADIUS = ((GRIP_DIA / 2.0) ** 2 + CAP_SAG**2) / (2.0 * CAP_SAG)
ROD_SPAN = ROD_DOWN + ROD_UP
