r"""The crank axis the MHA-DT-20 cone swing platform carries.

PURE, SolidWorks-free. The post and the crank train share the configured
frame axis. ``build_dt_cone_swing_platform`` authors this reference and the
drive train mates the crank to it.
"""

from __future__ import annotations

import math

from cone_line import (
    COS_I as _COS_I,
    PIVOT_XZ,
    POST_STATION,
    SIN_I as _SIN_I,
    X_CRANK,
    Y_BASE_TOP,
    Y_CRANK,
    cone_station,
)
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


def _swing(vector: tuple[float, float, float], angle_deg: float) -> tuple[float, float, float]:
    """Turn a machine-frame vector by the platform's P1 swing about machine y."""
    c, s = math.cos(math.radians(angle_deg)), math.sin(math.radians(angle_deg))
    return c * vector[0] + s * vector[2], vector[1], -s * vector[0] + c * vector[2]


def crank_axis_nominal_xy_mm(z_mm: float, angle_deg: float = 0.0) -> tuple[float, float]:
    """Nominal machine (x, y) of the crank axis at the machine-z plane z_mm.

    The axis passes the post station at Y_CRANK and runs along machine z;
    a P1 swing turns it with the platform about the pivot.
    """
    if not math.isfinite(z_mm) or not math.isfinite(angle_deg):
        raise ValueError("crank nominal axis requires finite Z and P1 angle")
    pivot = (PIVOT_XZ[0], Y_BASE_TOP, PIVOT_XZ[1])
    post = cone_station(POST_STATION)
    post[1] = Y_CRANK
    moved = _swing(tuple(post[i] - pivot[i] for i in range(3)), angle_deg)
    centre = tuple(pivot[i] + moved[i] for i in range(3))
    direction = _swing((0.0, 0.0, 1.0), angle_deg)
    if abs(direction[2]) < 1e-12:
        raise ValueError("nominal crank axis is parallel to the requested Z plane")
    t = (z_mm - centre[2]) / direction[2]
    return centre[0] + t * direction[0], centre[1] + t * direction[1]
