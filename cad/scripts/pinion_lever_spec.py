r"""Pure-data dimensional contract shared by the pinion engage lever and its
manufacturing drawing.

PURE DATA, no SolidWorks/COM imports.  A hub seated over the lift rod, with a
tapered grip rod rising out of it -- turned steel.  The nominals drive the part's
named equation globals AND the drawing's coordinate math; the marked-dimension
map keeps the part marks and drawing keeps in lockstep
(``test_pinion_lever_drawing.py``).
"""

from __future__ import annotations

import math

from _surface_finish import SurfaceFinishControl
from pinion_lever_geometry import (
    BORE as BORE,
    CAP_RADIUS as CAP_RADIUS,
    CAP_SAG as CAP_SAG,
    HUB_LEN as HUB_LEN,
    HUB_OD as HUB_OD,
    ROD_LEN as ROD_LEN,
    ROD_ROOT_DIA as ROD_ROOT_DIA,
    ROD_TIP_DIA as ROD_TIP_DIA,
    ROD_Y0 as ROD_Y0,
    WALL_T as WALL_T,
)

# Symmetric band about the 6.3675 mid nominal: 6.375 MAX / 6.360 MIN (running
# fit on the Ø6.35 pivot shaft).  The blind bore is BORED, not reamed: the
# print asks for a flat bottom at full diameter, which a reamer cannot leave
# (machinist review 2026-09-02).
BORE_BAND = (0.0075, -0.0075)
BORE_DEPTH_BAND = (0.10, 0.00)
ROD_TIP_Y_TOLERANCE_MM = 0.25
ROD_TIP_DIAMETER_TOLERANCE_MM = 0.05
# The taper half-angle is 0.69 deg, so the title block's +/-1 deg would allow
# a reverse taper; a relaxed explicit band keeps the grip a grip without
# asking anyone to set a sine bar to 0.05 deg (machinist review 2026-09-02).
GRIP_HALF_ANGLE_TOLERANCE_DEG = 0.25
CAP_RADIUS_TOLERANCE_MM = 0.10
GRIP_HALF_ANGLE_DEG = math.degrees(
    math.atan((ROD_TIP_DIA - ROD_ROOT_DIA) / (2.0 * (ROD_LEN - ROD_Y0)))
)

DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "BarrelProfile": {"HubOd", "HubBore"},
    "Barrel": {"BoreDepth"},
    # The end wall is REFERENCE on the print: the bore depth and the hub
    # length are both measured from the flat end, so the wall is derived.
    "Wall": {"EndWall"},
    "RodProfile": {"RodTipY", "RodTipDia", "GripHalfAngle"},
    # The crown is a size on the views: its sphere radius and (REF) height.
    "CapProfile": {"CapR", "CapSagDim"},
}

# No roughness callouts: the hub turns WITH the lift rod (the lever is the
# rod's input), so nothing runs on the bore; the title block's Ra 3.2 covers
# every face (cad/docs/drawing-simplicity-policy.md rule 5).
SURFACE_FINISHES: tuple[SurfaceFinishControl, ...] = ()

# Notes: process facts only, never a size (policy rule 6).  The grip station,
# the hub length and the crown are dimensions on the views.
DRAWING_NOTES = "\n".join(
    (
        "BORE AND FACE THE HUB IN ONE SETUP; FLAT BORE BOTTOM, CORNER R0.15 MAX.",
        "GRIP AXIS 90 DEG TO THE BORE AXIS; AXES INTERSECT.",
    )
)
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:1"
