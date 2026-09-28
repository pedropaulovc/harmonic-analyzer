r"""The crank axis the MHA-091 cone swing platform carries.

PURE, SolidWorks-free. The restored post and the crank train share the fixed
frame axis. ``build_cone_swing_platform`` authors this reference and the drive
train mates the crank to it.
"""

from __future__ import annotations

import math

from cone_swing_platform_geometry import INCLINE_DEG

_SIN_I = math.sin(math.radians(INCLINE_DEG))
_COS_I = math.cos(math.radians(INCLINE_DEG))

# --- crank axis (the machine-z crank line, carried BY the plate) -------------
# The merged column's crank bore is oblique geometry only; the KINEMATIC
# reference the crankshaft mates to is this named axis, so the crank rig
# swings with the plate. In the part-local frame the axis runs plan
# direction (-sin I, cos I) -- the direction the Ry(+INCLINE) placement maps
# to machine z (cf. cone-pivot-post) -- at height CRANK_AXIS_Y above the
# plate BOTTOM, passing the plan point (-CRANK_AXIS_OFF * cos I,
# -CRANK_AXIS_OFF * sin I) -- CRANK_AXIS_OFF is the distance the crank axis
# sits EAST of the pivot. This part-local separation is invariant under the
# v2 installation translation and is asserted against the live cone geometry
# in the assembly.
#
# Restored frame line: pivot.x - X_CRANK east, Y_CRANK - Y_BASE_TOP up.
CRANK_AXIS_OFF = 41.6536661190548
CRANK_AXIS_Y = 79.05
assert CRANK_AXIS_OFF > 0 and CRANK_AXIS_Y > 0, "user ruling 2026-09-28"
# Construction: a vertical REFERENCE AXIS through the crank axis's plan
# point (the foot of the pivot's perpendicular onto the axis line), built
# as the intersection of two principal-plane offsets -- name-selected and
# view-independent (a coordinate-picked model edge selects at the SCREEN
# projection and grabbed the notch rail's top edge instead of the vertical
# mouth edge, proven live). CrankAxisVert = "Right Plane" rotated INCLINE
# about that axis (so it CONTAINS the crank axis -- no offset step); the
# crank axis = that plane (x) the Top-offset plane at CRANK_AXIS_Y.
# CrankAxisSeat = "Front Plane" rotated the same way about the same axis,
# so it passes through CRANK_SEAT_ANCHOR -- the anchor the assembly's
# axial-distance mates reference (via _plate_local_to_machine; its machine
# point lands ON the crank axis, x = X_CRANK, asserted SolidWorks-free at
# assembly import). The angle's FLIP side is
# the one remaining EMPIRICAL sign -- flip on assembly crankshaft-mate
# verify failure.
CRANK_PLANE_ANGLE = INCLINE_DEG  # sign candidate (flip side)
CRANK_SEAT_ANCHOR = (-CRANK_AXIS_OFF * _COS_I, -CRANK_AXIS_OFF * _SIN_I)
assert math.isclose(math.hypot(*CRANK_SEAT_ANCHOR), CRANK_AXIS_OFF), "user ruling 2026-09-28"
