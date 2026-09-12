r"""Rocker-arm dimensional contract -- the single source of truth shared by the
part build (``build_rocker_arm.py``) and its manufacturing drawing
(``draw_rocker_arm.py``).

PURE DATA, no SolidWorks/COM imports (see ``crank_arm_spec`` for the pattern).
Holds the nominal geometry (book ch. 14) and the derived spans the drawing
needs for its view math. Drawing-only mark, placement and prose metadata lives
in ``rocker_arm_notes`` so assembly import closures remain geometry-only.
"""

from __future__ import annotations

import math


from cone_pivot_post_installation import MECHANISM_X_SHIFT
from _gtol_spec import CylinderFace
from _surface_finish import MACHINED_UM, SurfaceFinishControl
from rod_pivot_spec import ROCKER_HOLE_SPEC, ROCKER_THICKNESS

# --- Nominal geometry (DIMENSIONS.md "Chapter 14"). These MUST match the
# constants in build_rocker_arm.py (the test cross-checks the load-bearing
# ones), so the drawing's view math reads the same solid the part builds. ---
CURVE_RADIUS = 800.0  # top-edge arc radius = amplitude-bar length (stated)
ARM_DEPTH = 16.0  # perpendicular top-to-bottom depth (p.29 callout)
ARM_THICKNESS = ROCKER_THICKNESS  # plate thickness, Z (p.27 callout)
TOP_ARC_LEN = 292.1  # top edge arc length = 11.5" (ch.30 back view)
BOT_ARC_LEN = 266.7  # bottom edge arc length = 10.5" (ch.30 back-view sketch)
TIP_FACE = 5.588  # 0.22" tip face, perpendicular to the top edge
PIVOT_HOLE_DIA = 6.5  # rides the 6.35 pivot shaft
ROD_HOLE_X = 127.3738 - MECHANISM_X_SHIFT
ROD_HOLE_ABOVE_BOTTOM = 5.53312035905  # preserves the level-pose pin Y after X shift
ROD_HOLE_SPEC = ROCKER_HOLE_SPEC

SURFACE_FINISHES = (
    SurfaceFinishControl("pivot_bore", MACHINED_UM, CylinderFace(PIVOT_HOLE_DIA)),
)

# Model-owned size tolerance projected by the manufacturing drawing.
PIVOT_BORE_DIA_BAND = (0.03, 0.00)  # (upper, lower) deviations

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
ROD_HOLE_Y = (
    CENTER_Y - math.sqrt(R_BOTTOM**2 - ROD_HOLE_X * ROD_HOLE_X)
) + ROD_HOLE_ABOVE_BOTTOM


# --- Marked-dimension contract: feature -> the parametric dimension NAMES the
# print shows. build_rocker_arm marks exactly these; draw_rocker_arm keeps
# exactly their union across its per-view ``keep`` maps. ---
# The marked-dimension contract moved to ``rocker_arm_notes`` with the rest of
# the drawing-only data (codex #354): it changes for drawing-only mark/keep
# updates, and assemblies import this module.

# The pivot bore rides at the strap mid-depth; assemblies place the arm off
# this (imported from here, never from build_rocker_arm, so drawing-only edits
# stay out of assembly rebuild closures -- codex #354).
PIVOT_MID_Y = ARM_DEPTH / 2.0  # 8.0

# Drawing prose (DRAWING_NOTES / ISOMETRIC_VIEW_NOTE) lives in
# rocker_arm_notes.py -- see connecting_rod_notes for the rationale.

# Integral central pivot hub (2026-09-02 photo re-derive, ch14 p.28
# page002_img02 + ch17 p.40): every arm carries the round boss on both faces.
# Its length equals the 7.0565 station pitch. OD stays at O10: at d = 0 the
# amplitude bar's foot cheeks pass 5.63 above the shaft axis, so OD < ~11.25.
HUB_DIA = 10.0
HUB_LENGTH = 7.0565  # == machine channels.station_pitch_mm (asserted by the build)

