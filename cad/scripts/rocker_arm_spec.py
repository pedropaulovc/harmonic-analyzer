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

from cone_pivot_post_installation import MECHANISM_X_SHIFT
from _gtol_spec import CylinderFace
from _surface_finish import MACHINED_UM, SurfaceFinishControl

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
# Reamed running bore: (upper, lower) deviations on the model dimension
# (the +0.03/0 that used to live in a note line).
PIVOT_HOLE_BAND = (0.03, 0.00)
ROD_HOLE_X = 127.3738 - MECHANISM_X_SHIFT
ROD_HOLE_ABOVE_BOTTOM = 5.53312035905  # preserves the level-pose pin Y after X shift

SURFACE_FINISHES = (
    SurfaceFinishControl("pivot_bore", MACHINED_UM, CylinderFace(PIVOT_HOLE_DIA)),
)

# --- Derived spans (equations of the primitives; mirror build_rocker_arm). ---
R_TOP = CURVE_RADIUS
R_BOTTOM = CURVE_RADIUS + ARM_DEPTH
CENTER_Y = CURVE_RADIUS + ARM_DEPTH

_ALPHA_TOP = (TOP_ARC_LEN / 2.0) / R_TOP
_ALPHA_BOT = (BOT_ARC_LEN / 2.0) / R_BOTTOM
TOP_END_X = R_TOP * math.sin(_ALPHA_TOP)
TOP_END_Y = CENTER_Y - R_TOP * math.cos(_ALPHA_TOP)
BOT_END_X = R_BOTTOM * math.sin(_ALPHA_BOT)

# Rod tip: the top-arc endpoint pushed out along the radius by the tip face
# (the corner where the radial tip face meets the tapered end face -- the
# widest point of the strap, so the tip-to-tip overall is 2 x ROD_TIP_X).
_RAD_X = TOP_END_X / R_TOP
_RAD_Y = (TOP_END_Y - CENTER_Y) / R_TOP
ROD_TIP_X = TOP_END_X + TIP_FACE * _RAD_X  # widest half-span (~146.25)
ROD_TIP_Y = TOP_END_Y + TIP_FACE * _RAD_Y  # tip corner height (~23.8)

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

# Integral pivot hub (2026-09-02 photo re-derive, ch14 p.28 page002_img02 +
# ch17 p.40): every arm carries its own round boss on both faces at the
# pivot; neighbouring hubs touch face to face and set the 7.0565 station
# pitch. The 19 `pivot-bushing` spacer parts are retired.
HUB_DIA = 10.0
HUB_LENGTH = 7.0565  # == machine channels.station_pitch_mm (asserted by the build)

# No GD&T: the rod-pin hole is a coordinate pair from the pivot bore that the
# block tolerance holds (cad/docs/drawing-simplicity-policy.md rule 3).
