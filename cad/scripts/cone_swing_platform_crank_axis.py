r"""The crank axis the MHA-091 cone swing platform carries.

PURE, SolidWorks-free.  Kept apart from ``cone_swing_platform_geometry``
because it reads the crank mesh stack: the harmonic base imports the plate
geometry, and the stack (with the fit classes it reads) must stay out of the
frame's recipe.  ``build_cone_swing_platform`` authors the axis from these
numbers and the drive train places the crank train on it.
"""

from __future__ import annotations

import math

from cone_swing_platform_geometry import INCLINE_DEG
from crank_mesh_stack import FITUP_AXIS_DX, FITUP_AXIS_DY

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
# The axis is the crank's NOMINAL FIT-UP line, not the frame's: the eccentric
# bushing throws the crank off the post bore to set the mesh backlash, and the
# crank train mates here (user ruling R1, 2026-09-26, #906).  The frame line
# is pivot.x - X_CRANK east and Y_CRANK 129.85 - Y_BASE_TOP 50.8 up; the fit-up
# moves it by crank_mesh_stack's FITUP_AXIS_DX/DY (machine +x is west).
_CRANK_AXIS_OFF_FRAME = 41.6536661190548
_CRANK_AXIS_Y_FRAME = 79.05
CRANK_AXIS_OFF = _CRANK_AXIS_OFF_FRAME - FITUP_AXIS_DX
CRANK_AXIS_Y = _CRANK_AXIS_Y_FRAME + FITUP_AXIS_DY
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
# point lands ON the crank axis, x = X_CRANK_FIT, asserted SolidWorks-free at
# assembly import). The angle's FLIP side is
# the one remaining EMPIRICAL sign -- flip on assembly crankshaft-mate
# verify failure.
CRANK_PLANE_ANGLE = INCLINE_DEG  # sign candidate (flip side)
CRANK_SEAT_ANCHOR = (-CRANK_AXIS_OFF * _COS_I, -CRANK_AXIS_OFF * _SIN_I)
