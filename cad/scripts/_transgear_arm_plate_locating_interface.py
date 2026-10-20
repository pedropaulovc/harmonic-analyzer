"""Arm/plate locating-dowel mating dimensions, independent of purchased stock.

The arm accepts a pressed dowel without bottoming; the plate slips over its
proud end. Catalogue stock and whole-joint checks stay in the pin spec.
"""

from __future__ import annotations

PRESS_HOLE_LIMITS_MM = (1.990, 2.000)
SLIP_HOLE_LIMITS_MM = (2.010, 2.020)
PROUD_MM = 1.70
PROUD_TOLERANCE_MM = 0.03
PROUD_LIMITS_MM = (PROUD_MM - PROUD_TOLERANCE_MM, PROUD_MM + PROUD_TOLERANCE_MM)
ARM_BLIND_DEPTH_MM = 4.80
ARM_BLIND_DEPTH_TOLERANCE_MM = 0.05
HOLE_MOUTH_BREAK_AXIAL_MAX_MM = 0.05
HOLE_MOUTH_BREAK_RADIAL_MAX_MM = 0.05
