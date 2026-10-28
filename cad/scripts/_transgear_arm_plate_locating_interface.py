"""Arm/plate locating-dowel mating dimensions, independent of purchased stock.

The arm's reamed holes run through: the dowel presses in from the rear to
its proud set and punches out from the front; the plate slips over its
proud end. Catalogue stock and whole-joint checks stay in the pin spec.
"""

from __future__ import annotations

PRESS_HOLE_LIMITS_MM = (1.990, 2.000)
SLIP_HOLE_LIMITS_MM = (2.010, 2.020)
PROUD_MM = 1.70
PROUD_TOLERANCE_MM = 0.03
PROUD_LIMITS_MM = (PROUD_MM - PROUD_TOLERANCE_MM, PROUD_MM + PROUD_TOLERANCE_MM)
HOLE_MOUTH_BREAK_AXIAL_MAX_MM = 0.05
HOLE_MOUTH_BREAK_RADIAL_MAX_MM = 0.05
