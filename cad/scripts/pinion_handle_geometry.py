r"""Geometry-only contract for the pinion turning handle."""

from __future__ import annotations

GRIP_DIA = 23.0
GRIP_LEN = 14.0
CAP_SAG = 2.0
ROD_DIA = 6.0
ROD_DOWN = 42.0
ROD_UP = 43.0
TUBE_OD = 10.5
TUBE_ID = 8.0
TUBE_LEN = 10.0
WALL_T = 2.0
CAP_RADIUS = ((GRIP_DIA / 2.0) ** 2 + CAP_SAG**2) / (2.0 * CAP_SAG)
ROD_SPAN = ROD_DOWN + ROD_UP
