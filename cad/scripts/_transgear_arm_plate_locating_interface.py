"""Arm/plate locating-dowel mating dimensions, independent of purchased stock.

The arm's reamed holes run through: the dowel presses in from the rear to
its proud set and punches out from the front; the plate slips over its
proud end. Catalogue stock and whole-joint checks stay in the pin spec.

Fit audit 2026-11-23 (pending owner confirmation): the dowel is 1/8, so the
two holes are cut by the .1240 and .1260 members of the over/under reamer
set (cad/config/shop-equipment/tools-reamers-taps.toml), each printed as its
reamer's size with no band and accepted with the dowel itself: it does not
enter the arm's hole by hand and slides into the plate's with no shake.
What fails if either is .002 loose: the plate no longer returns to the
knob-axis setting of MHA-PD-00 step 12, which sets the reducer mesh's
centre distance (pd_rack_pinion_spec.CENTRE_DISTANCE_SET_BAND; the yaw of
the two-hole registration carries the slip to K about 2.4 times over).
"""

from __future__ import annotations

from _fit_ream_h7 import REAM_H7

_PRESS_HOLE_DIA_MM = 3.1496  # .1240
_SLIP_HOLE_DIA_MM = 3.2004  # .1260
# ANALYSIS bands, not printed limits: what each set reamer is modelled to
# cut (REAM_H7, +.0005/0 on its size), for the walls and the fit ranges.
PRESS_HOLE_LIMITS_MM = (_PRESS_HOLE_DIA_MM + min(REAM_H7), _PRESS_HOLE_DIA_MM + max(REAM_H7))
SLIP_HOLE_LIMITS_MM = (_SLIP_HOLE_DIA_MM + min(REAM_H7), _SLIP_HOLE_DIA_MM + max(REAM_H7))
# LOCTITE 638's diametral gap limit (its TDS; the value of
# dt_pinion_arbor_geometry.RETAINING_COMPOUND_MAX_GAP_MM and
# sm_gooseneck_spring_joint.LOCTITE_638_GAP_MAX): a dowel that slides into
# the arm by hand is bonded with it (MHA-PD-00's bond note).
BOND_GAP_LIMIT_MM = 0.25
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
