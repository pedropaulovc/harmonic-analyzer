r"""Geometry-only contract for the pinion cam-follower pin."""

from __future__ import annotations

PIN_DIA = 4.016
PIN_LEN = 15.0
SEAT_LEN = 4.0
CAP_SAG = 0.8
CAP_RADIUS = ((PIN_DIA / 2.0) ** 2 + CAP_SAG**2) / (2.0 * CAP_SAG)
