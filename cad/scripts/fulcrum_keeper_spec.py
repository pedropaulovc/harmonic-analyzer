r"""Fulcrum-keeper dimensional contract -- the single source of truth shared by
the part build (``build_fulcrum_keeper.py``) and its manufacturing drawing
(``draw_fulcrum_keeper.py``).

PURE DATA, no SolidWorks/COM imports: the nominal geometry (the "editable
knobs"), the screw-hole layout the drawing needs for its view math, the fit
bands on the two bores, and the marked-dimension -> kept-dimension NAME map
(see ``guide_lock_spec.py`` for the pattern's build-graph rationale).

The keeper is the black shaft-end bracket of the top-lever fulcrum bank
(book ch. 17 p. 40 bottom-left closeup; ch. 30 top view + p008): an upright
round-topped lug sockets a bright steel ball on the fulcrum-shaft end, and
the bracket's foot is screwed down into the top-frame rail top face with one
slotted #10-24 cheese-head screw (frame-side-screw, MHA-117) in a
counterbore. 2 required, one per shaft end (the second is the same part
flipped Ry180 by the assembly).

Part frame: +X = along the shaft, OUTBOARD (toward the near shaft end);
+Y up from the foot seat; +Z across the width. The lug mid-plane (= ball
centre) is x = 0; the foot reaches inboard (-X).
"""

from __future__ import annotations

import math


# --- Nominal geometry (mm). Derived against the 2026-08-02 top-frame
# contract: rail top face y=1036.2, fulcrum shaft axis y=1061.4 (+25.2),
# corner boss Ø52.2 proud +4.5 of the face. ---
FOOT_REACH = 23.0  # lug mid-plane -> inboard end of the foot (-X extent)
PAD_END_X = 6.5  # on-face pad stops here (x -23..-6.5); outboard of this the
# underside is relieved so nothing lands on the frame's proud corner-boss land
FOOT_H = 8.0  # foot/pad height; the bracket seats on y=0
RELIEF_H = 4.8  # relieved underside plane: 0.3 above the 4.5-proud boss land
LUG_HALF_T = 3.0  # lug half-thickness along X (lug 6.0 thick)
KEEPER_WIDTH = 14.0  # across Z (machine X when placed); extrudes symmetric
SHAFT_AXIS_H = 25.2  # ball/socket/bore centre above the foot seat
CROWN_DIA = 14.0  # full-round lug top, concentric with the shaft axis
BALL_DIA = 9.5  # bright steel ball pressed in the lug's through-socket
BORE_DIA = 6.5  # shaft clearance bore through the ball (shaft is Ø6.35)

# The reamed bore takes the ball's poles with it, so the ball's proud extreme
# along X is the bore/sphere intersection circle, not the pole: the part's
# true outboard extent (the sheet's overall length runs to this edge).
BALL_EDGE_X = math.sqrt((BALL_DIA / 2.0) ** 2 - (BORE_DIA / 2.0) ** 2)  # 3.464
OVERALL_LEN = FOOT_REACH + BALL_EDGE_X  # 26.46

# --- Fit bands (upper, lower), the _fit_limits convention; the build splats
# them through ``deviations`` onto the named model dimensions. ---
# Ball seat: a Ø9.500 hardened ball pressed into the mild-steel lug on its
# equator ring -- a firm interference (0.010 .. 0.025) the ball cannot shake
# out of (machinist review 2026-09-02: an untoleranced Ø9.50 ranged from
# clearance to excessive interference).
SOCKET_DIA_BAND = (-0.010, -0.025)
# Shaft bore through the ball: reamed, H7 for the 6-10 range (+0.015 / 0);
# the Ø6.35 shaft end floats in it with the standard clearance.
BORE_DIA_BAND = (0.015, 0.000)

# Screw hole: one #10 clearance drill + cheese-head counterbore in the pad
# centre. The under-head plane sits at FOOT_H - CBORE_DEPTH.
SCREW_X = -14.75  # pad centre: (-23 + -6.5) / 2
HOLE_DIA_MM = 5.105  # #10 close-clearance drill (0.201 in = the #7 drill)
CBORE_DIA_MM = 9.5  # seats the MHA-117 slotted cheese head (Ø7 x 3), flush
CBORE_DEPTH_MM = 3.0
# Hole-axis location in the pad, dimensioned on the plan view (the wizard
# hole is not a marked dimension, so the sheet dimensions it by entity).
HOLE_FROM_PAD_END = SCREW_X + FOOT_REACH  # 8.25 from the inboard end
HOLE_FROM_SIDE = KEEPER_WIDTH / 2.0  # 7.00 from either side face

# --- Marked-dimension contract: feature -> the parametric dimension NAMES the
# print shows. The envelope (foot reach, pad length, the relief height,
# width, shaft-axis height, crown) and the two bores at the lug; the wizard
# screw hole ships as the native hole callout, not a marked dim. ---
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "FootProfile": {"FootReach", "PadLen", "ReliefRise"},
    "Foot": {"Depth"},
    "LugCrownProfile": {"ShaftAxisH", "CrownDia"},
    "SocketProfile": {"SocketDia"},
    "BoreProfile": {"BoreDia"},
}

# Flagged from the socket rim in the lug end view: the complete concentric
# feature sequence stays with the circles it governs.  The seat and ream bands
# remain on their model dimensions; the flag supplies the actual ball size and
# the order that cannot be inferred from the finished views.
BALL_CALLOUT = "\n".join(
    (
        "BORE BALL SEAT THRU ON THE SHAFT AXIS;",
        f"PRESS Ø{BALL_DIA:.3f} HARDENED STEEL BALL, CENTRED;",
        "REAM SHAFT BORE THRU AFTER PRESSING.",
    )
)

# One permitted cross-part note remains in the remote block.  All machining
# numbers and the bore/press/ream sequence are owned by views.
DRAWING_NOTES = "MATES WITH FULCRUM SHAFT."
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:1"

# No GD&T: a screwed-down bracket is not on the allowlist
# (cad/docs/drawing-simplicity-policy.md rule 3).
