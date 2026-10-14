r"""Geometry-only contract for the pinion engage lever."""

from __future__ import annotations

import math

from _inch import inch

# Straight, no taper: ch25 page002_img07 annotates the rod "6 mm" beside the
# hub, and equal-scale crops of its root and tip read the same width.
# All-inch: 1/4 in drill rod.
ROD_DIA = inch(1, 4)
ROD_LEN = inch(27, 8)  # 3-3/8 in, hub axis to the tip
ROD_Y0 = 3.5  # the rod's buried root inside the hub: a modelling station, not printed
HUB_OD = inch(1, 2)
HUB_LEN = inch(3, 8)
BORE = 6.35  # nominal; the REAM_SLIDE band (dt_pinion_lever_spec) opens it 0.010-0.025
# 1/32 (all-inch): the end wall keeps its 1.5 floor under its own +/-0.25
# band (dt_pinion_lever_spec.END_WALL_TOLERANCE_MM); 1/16 in would not.
WALL_T = inch(3, 32)
# The domed cap prints its sphere radius (CapR); the sagitta follows on the OD.
CAP_RADIUS = inch(9, 16)
CAP_SAG = CAP_RADIUS - math.sqrt(CAP_RADIUS**2 - (HUB_OD / 2.0) ** 2)
# Printed places of the dimensions that station the grip on the lift rod (the
# rig layout books their bands; dt_pinion_lever_spec.DRAWING_PRECISION states them).
BORE_DEPTH_PLACES = 1  # BoreDepth: mouth face B to the floor the rod seats on
GRIP_FROM_B_PLACES = 2  # GripFromB: the grip axis from face B
ROD_DIA_PLACES = 1  # RodDia

# U36 (MHA-DT-030): the retention pin crosses the hub at mid-engagement -- half the
# bore depth in from the mouth face, which also puts it half the rod's
# engagement in from the rod's front end (the rod seats on the bore floor).
# The pin runs along the hub's local X, 3 o'clock to the +Y grip.
PIN_HOLE_DIA = 25.4 / 16.0  # 1/16 in, match-drilled through hub and rod
BORE_DEPTH = HUB_LEN - WALL_T
PIN_HOLE_FROM_MOUTH = BORE_DEPTH / 2.0
PIN_HOLE_Z = HUB_LEN / 2.0 - PIN_HOLE_FROM_MOUTH  # hub-local station, +1.19
ROD_PIN_HOLE_FROM_END = BORE_DEPTH - PIN_HOLE_FROM_MOUTH  # on the lift rod
