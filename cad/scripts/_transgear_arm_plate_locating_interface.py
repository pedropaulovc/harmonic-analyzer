"""Arm/plate locating-dowel mating dimensions, independent of purchased stock.

The arm's reamed holes run through: the dowel presses in from the rear to
its proud set and punches out from the front; the plate slips over its
proud end. Catalogue stock and whole-joint checks stay in the pin spec.

Decimal inch (#290): the 3/32 dowel's press is .093 REAM_H7, the
``_sprocket_seat_geometry`` drive-pin press on the same purchased .0930
reamer; the plate's slip is .0945 REAM_H7 (.0945 reamer).
"""

from __future__ import annotations

from _fit_ream_h7 import REAM_H7

_PRESS_HOLE_DIA_MM = 2.3622  # .093
_SLIP_HOLE_DIA_MM = 2.4003  # .0945
PRESS_HOLE_LIMITS_MM = (_PRESS_HOLE_DIA_MM + min(REAM_H7), _PRESS_HOLE_DIA_MM + max(REAM_H7))
SLIP_HOLE_LIMITS_MM = (_SLIP_HOLE_DIA_MM + min(REAM_H7), _SLIP_HOLE_DIA_MM + max(REAM_H7))
PROUD_MM = 1.7018  # .067
# The proud set holds the title block's .XXX +/-.005 (#2630): no mate needs
# more.  Its one consumer, the punch-out air of the deepest insertion
# (pd_transgear_arm_spec.LOCATOR_PUNCH_AIR_MIN_MM), keeps over 1 mm, and
# the plate's slip holes take at least the .062 MIN proud and never more
# than the .072 MAX, well inside the plate's .197 over the arm.
PROUD_TOLERANCE_MM = 0.127  # .005
PROUD_LIMITS_MM = (PROUD_MM - PROUD_TOLERANCE_MM, PROUD_MM + PROUD_TOLERANCE_MM)
HOLE_MOUTH_BREAK_AXIAL_MAX_MM = 0.0508  # .002
HOLE_MOUTH_BREAK_RADIAL_MAX_MM = 0.0508  # .002
