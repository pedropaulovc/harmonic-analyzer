r"""Geometry-only contract for the pinion engage lever."""

from __future__ import annotations

ROD_ROOT_DIA = 4.0
ROD_TIP_DIA = 6.0
ROD_LEN = 86.0
ROD_Y0 = 3.5
HUB_OD = 13.0
HUB_LEN = 10.0
BORE = 6.3675
WALL_T = 2.0
CAP_SAG = 1.5
CAP_RADIUS = ((HUB_OD / 2.0) ** 2 + CAP_SAG**2) / (2.0 * CAP_SAG)
