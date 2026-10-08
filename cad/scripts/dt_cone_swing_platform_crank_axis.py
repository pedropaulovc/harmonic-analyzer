r"""The crank axis the MHA-DT-020 cone swing platform carries.

PURE, SolidWorks-free. The restored post and the crank train share the fixed
frame axis. ``build_cone_swing_platform`` authors this reference and the drive
train mates the crank to it.
"""

from __future__ import annotations

from cone_line import COS_I as _COS_I, PIVOT_XZ, SIN_I as _SIN_I, X_CRANK, Y_BASE_TOP, Y_CRANK
from dt_cone_swing_platform_geometry import INCLINE_DEG

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
CRANK_AXIS_OFF = PIVOT_XZ[0] - X_CRANK
CRANK_AXIS_Y = Y_CRANK - Y_BASE_TOP
if CRANK_AXIS_OFF <= 0 or CRANK_AXIS_Y <= 0:
    raise AssertionError("swing platform crank axis must lie east and above the pivot")
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
