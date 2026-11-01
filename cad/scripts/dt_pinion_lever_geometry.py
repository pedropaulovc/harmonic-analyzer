r"""Geometry-only contract for the pinion engage lever."""

from __future__ import annotations

import _config
from _package_units import drawing_unit

UNIT = drawing_unit("parts/dt-pinion-lever", _config.parts("dt-pinion-lever"))

# Straight, no taper: ch25 page002_img07 annotates the rod "6 mm" beside the
# hub, and equal-scale crops of its root and tip read the same width.  #290:
# every nominal snaps to the inch .XX grid the sheet prints.
ROD_DIA = 6.096  # .24
ROD_LEN = 86.106  # 3.39
ROD_Y0 = 3.5
HUB_OD = 12.954  # .51
HUB_LEN = 10.16  # .40
BORE = 6.35  # nominal; the REAM_SLIDE band (dt_pinion_lever_spec) opens it .0010-.0015
WALL_T = 2.032  # .08
# ENFORCE r1 of MHA-DT-16 (#1011): the end wall behind the blind bore now
# reads from two baselines on face B -- the bore depth and the overall
# length to the crown apex -- instead of a tight band of its own (rule 17:
# fix the wall with geometry, never a tighter band).  A .09 sagitta keeps the
# crown "slightly domed" and leaves the wall on the axis and at the floor's
# corner over the .080 target at the worst of both .XX bands
# (dt_pinion_lever_spec asserts both).
CAP_SAG = 2.286  # .09
CAP_RADIUS = ((HUB_OD / 2.0) ** 2 + CAP_SAG**2) / (2.0 * CAP_SAG)
OVERALL_FROM_B = HUB_LEN + CAP_SAG  # mouth face B to the crown apex, .49
# Printed places of the dimensions that station the grip on the lift rod (the
# rig layout books their bands; dt_pinion_lever_spec.DRAWING_PRECISION states them).
BORE_DEPTH_PLACES = 2  # BoreDepthFromB: mouth face B to the floor the rod seats on
OVERALL_FROM_B_PLACES = 2  # OverallFromB: mouth face B to the crown apex
GRIP_FROM_B_PLACES = 2  # GripFromB: the grip axis from face B
ROD_DIA_PLACES = 2  # RodDia

# U36 (MHA-DT-30): the retention pin crosses the hub at mid-engagement -- half the
# bore depth in from the mouth face, which also puts it half the rod's
# engagement in from the rod's front end (the rod seats on the bore floor).
# The pin runs along the hub's local X, 3 o'clock to the +Y grip.
# #290 fit F15: a .064 drilled hole (DRILLED HOLES +.004/0) through hub and
# rod, so the 1/16 drill rod pin (.0625 +/-.0003) always slips in before it is
# peened.
PIN_HOLE_DIA = 1.6256  # .064, match-drilled through hub and rod
# The drill dt_drive_train_assembly_sheet names in MHA-DT-00 LEVER PIN SET.
PIN_HOLE_DRILL = "#52"
BORE_DEPTH = HUB_LEN - WALL_T  # .32
PIN_HOLE_FROM_MOUTH = BORE_DEPTH / 2.0  # .16
PIN_HOLE_Z = HUB_LEN / 2.0 - PIN_HOLE_FROM_MOUTH  # hub-local station, .04
ROD_PIN_HOLE_FROM_END = BORE_DEPTH - PIN_HOLE_FROM_MOUTH  # on the lift rod, .16
