r"""Geometry-only contract for the pinion engage lever."""

from __future__ import annotations

# Straight, no taper: ch25 page002_img07 annotates the rod "6 mm" beside the
# hub, and equal-scale crops of its root and tip read the same width.
ROD_DIA = 6.0
ROD_LEN = 86.0
ROD_Y0 = 3.5
HUB_OD = 13.0
HUB_LEN = 10.0
BORE = 6.35  # nominal; the REAM_SLIDE band (dt_pinion_lever_spec) opens it 0.010-0.025
WALL_T = 2.0
# ENFORCE r1 of MHA-DT-16 (#1011): the end wall behind the blind bore now
# reads from two .X baselines on face B -- the bore depth and the overall
# length to the crown apex -- instead of a tight band of its own (rule 17:
# fix the wall with geometry, never a tighter band).  A 2.2 sagitta (was 1.5,
# a photo estimate) keeps the crown "slightly domed" and leaves the wall 2.6
# on the axis and 2.07 at the floor's corner at the worst of both bands
# (dt_pinion_lever_spec asserts both reach the 2.0 target; ENFORCE r5's
# minor read 1.9 at the corner on the former 2.0 sagitta).
CAP_SAG = 2.2
CAP_RADIUS = ((HUB_OD / 2.0) ** 2 + CAP_SAG**2) / (2.0 * CAP_SAG)
OVERALL_FROM_B = HUB_LEN + CAP_SAG  # mouth face B to the crown apex
# Printed places of the dimensions that station the grip on the lift rod (the
# rig layout books their bands; dt_pinion_lever_spec.DRAWING_PRECISION states them).
BORE_DEPTH_PLACES = 1  # BoreDepthFromB: mouth face B to the floor the rod seats on
OVERALL_FROM_B_PLACES = 1  # OverallFromB: mouth face B to the crown apex
GRIP_FROM_B_PLACES = 2  # GripFromB: the grip axis from face B
ROD_DIA_PLACES = 1  # RodDia

# U36 (MHA-DT-30): the retention pin crosses the hub at mid-engagement -- half the
# bore depth in from the mouth face, which also puts it half the rod's
# engagement in from the rod's front end (the rod seats on the bore floor).
# The pin runs along the hub's local X, 3 o'clock to the +Y grip.
PIN_HOLE_DIA = 25.4 / 16.0  # 1/16 in, match-drilled through hub and rod
BORE_DEPTH = HUB_LEN - WALL_T
PIN_HOLE_FROM_MOUTH = BORE_DEPTH / 2.0
PIN_HOLE_Z = HUB_LEN / 2.0 - PIN_HOLE_FROM_MOUTH  # hub-local station, +1.0
ROD_PIN_HOLE_FROM_END = BORE_DEPTH - PIN_HOLE_FROM_MOUTH  # on the lift rod
