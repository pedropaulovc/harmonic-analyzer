r"""Geometry-only contract for the pinion cam-follower pin."""

from __future__ import annotations

import math

# U27 (Main, 2026-09-23): a slip fit bonded with LOCTITE 638, not a press --
# the stud is cut from stock drill rod (U6 drum-to-arbor precedent).  #290
# (owner ruling, 2026-10-30): 5/32 O1 drill rod, McMaster-Carr 8893K162, whose
# page states .1563 +/-.0005 in (read live 2026-10-31), so the model carries
# the page value, not an exact 5/32.
PIN_DIA = 3.97002  # .1563
PIN_LEN = 20.066  # .79; U28: the lift rod moved out to 18.5 from the pivot; 16 proud
SEAT_LEN = 4.064  # .16, the MHA-DT-14 seat depth
# The outer crown: its radius prints .XX, and the sagitta follows from it.
CAP_RADIUS = 3.048  # .12
CAP_SAG = CAP_RADIUS - math.sqrt(CAP_RADIUS**2 - (PIN_DIA / 2.0) ** 2)
