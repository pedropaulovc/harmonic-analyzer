r"""Geometry-only contract for the pinion cam-follower pin."""

from __future__ import annotations

from _inch import inch

# U27 (Main, 2026-09-23): a slip fit bonded with LOCTITE 638, not a press --
# the stud is cut from stock 5/32 in drill rod (U6 drum-to-arbor precedent).
PIN_DIA = inch(5, 32)  # 1/32: a 3/16 seat breaks the strap's 1.5 web (bracket spec)
PIN_LEN = inch(13, 16)  # U28: the lift rod moved out from the pivot; ~5/8 proud
SEAT_LEN = inch(3, 16)  # the MHA-DT-014 follower seat depth (PIN_SEAT)
CAP_SAG = inch(1, 32)  # 1/32: the 1/16 grid would double the 0.8 crown sag
CAP_RADIUS = ((PIN_DIA / 2.0) ** 2 + CAP_SAG**2) / (2.0 * CAP_SAG)
