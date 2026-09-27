r"""Geometry-only contract for the pinion cam-follower pin."""

from __future__ import annotations

# U27 (Main, 2026-09-23): a slip fit bonded with LOCTITE 638, not a press --
# the stud is cut from stock 4 mm drill rod (U6 drum-to-arbor precedent).
PIN_DIA = 4.0
PIN_LEN = 20.0  # U28: the lift rod moved out to 18.5 from the pivot; 16 proud
SEAT_LEN = 4.0
CAP_SAG = 0.8
CAP_RADIUS = ((PIN_DIA / 2.0) ** 2 + CAP_SAG**2) / (2.0 * CAP_SAG)
