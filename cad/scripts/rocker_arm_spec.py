r"""Rocker-arm dimensional contract -- the single source of truth shared by the
part build (``build_rocker_arm.py``) and its manufacturing drawing
(``draw_rocker_arm.py``).

PURE DATA, no SolidWorks/COM imports (see ``crank_arm_spec`` for the pattern).
Holds the nominal geometry (book ch. 14), the derived spans the drawing needs
for its view math, and the marked-dimension -> kept-dimension NAME map. The
part build marks EXACTLY ``DRAWING_DIMENSIONS``; the drawing keeps exactly their
union across its per-view ``keep`` maps -- the offline test
(``test_rocker_arm_drawing.py``) fails loud if the two drift.
"""

from __future__ import annotations

import math

# --- Nominal geometry (DIMENSIONS.md "Chapter 14"). These MUST match the
# constants in build_rocker_arm.py (the test cross-checks the load-bearing
# ones), so the drawing's view math reads the same solid the part builds. ---
CURVE_RADIUS = 800.0  # top-edge arc radius = amplitude-bar length (stated)
ARM_DEPTH = 16.0  # perpendicular top-to-bottom depth (p.29 callout)
ARM_THICKNESS = 2.5  # plate thickness, Z (p.27 callout)
TOP_ARC_LEN = 292.1  # top edge arc length = 11.5" (ch.30 back view)
BOT_ARC_LEN = 266.7  # bottom edge arc length = 10.5" (ch.30 back-view sketch)
TIP_FACE = 5.588  # 0.22" tip face, perpendicular to the top edge
PIVOT_HOLE_DIA = 6.5  # rides the 6.35 pivot shaft
ROD_HOLE_X = 127.3738  # rod pin near the +X (rod-side) tip
ROD_HOLE_ABOVE_BOTTOM = 5.3  # rod-pin hole centre above the arm's bottom edge

# --- Derived spans (equations of the primitives; mirror build_rocker_arm). ---
R_TOP = CURVE_RADIUS
R_BOTTOM = CURVE_RADIUS + ARM_DEPTH
CENTER_Y = CURVE_RADIUS + ARM_DEPTH

_ALPHA_TOP = (TOP_ARC_LEN / 2.0) / R_TOP
_ALPHA_BOT = (BOT_ARC_LEN / 2.0) / R_BOTTOM
TOP_END_X = R_TOP * math.sin(_ALPHA_TOP)
TOP_END_Y = CENTER_Y - R_TOP * math.cos(_ALPHA_TOP)
BOT_END_X = R_BOTTOM * math.sin(_ALPHA_BOT)

# Rod tip: the top-arc endpoint pushed out along the radius by the tip face.
_RAD_X = TOP_END_X / R_TOP
ROD_TIP_X = TOP_END_X + TIP_FACE * _RAD_X  # widest half-span (~146.25)

# Rod-pin hole Y (low in the strap, ch14 fan photo).
ROD_HOLE_Y = (CENTER_Y - math.sqrt(R_BOTTOM**2 - ROD_HOLE_X * ROD_HOLE_X)) + ROD_HOLE_ABOVE_BOTTOM


# --- Marked-dimension contract: feature -> the parametric dimension NAMES the
# print shows. build_rocker_arm marks exactly these; draw_rocker_arm keeps
# exactly their union across its per-view ``keep`` maps. ---
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "StrapProfile": {"TopRadius", "BottomRadius"},
    "PivotHoleProfile": {"PivotDia"},
}

# True free-text instructions only; geometry / datum structure / roughness live
# in native dimensions / datum tags / FCFs / surface symbols.
DRAWING_NOTES = "\n".join(
    (
        "1. SYMMETRIC MID-PIVOT SEESAW.",
        "2. STRAP 16 DEEP x 2.5 THICK.",
        "3. TOP EDGE R800, BOTTOM EDGE R816,",
        "   CONCENTRIC; CENTRE 808 ABOVE PIVOT.",
        "4. ARC LENGTHS 11.5 IN TOP / 10.5 IN",
        "   BOTTOM TAPER THE ENDS.",
        "5. EACH TIP: 0.22 IN FACE PERP TO TOP EDGE.",
        "6. PIVOT HOLE: REAM TO SUIT 6.35 SHAFT.",
        "7. ROD-PIN HOLE: #47 DRILL THRU.",
    )
)
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:4"
