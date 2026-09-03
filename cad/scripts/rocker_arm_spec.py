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

# --- Nominal geometry (DIMENSIONS.md "Chapter 14"). ---
CURVE_RADIUS = 800.0  # top-edge radius = amplitude-bar length (stated)
ARM_DEPTH = 16.0
ARM_THICKNESS = 2.5
TOP_ARC_LEN = 292.1  # source master span used to locate the tail endpoint
BOT_ARC_LEN = 266.7
TAIL_TIP_FACE = 5.588  # the photographed/ch30 radial land survives only at tail
PIVOT_HOLE_DIA = 6.5
ROD_HOLE_X = 127.3738 - MECHANISM_X_SHIFT
ROD_HOLE_ABOVE_BOTTOM = 5.53312035905
ROD_STEP_FROM_PIN = 5.0
ROD_TONGUE_BEYOND_PIN = 6.0
ROD_TONGUE_DEPTH = 5.0

SURFACE_FINISHES = (
    SurfaceFinishControl("pivot_bore", MACHINED_UM, CylinderFace(PIVOT_HOLE_DIA)),
)

# --- Derived profile boundary (shared with build_rocker_arm). ---
R_TOP = CURVE_RADIUS
R_BOTTOM = CURVE_RADIUS + ARM_DEPTH
CENTER_Y = CURVE_RADIUS + ARM_DEPTH

_ALPHA_TOP = (TOP_ARC_LEN / 2.0) / R_TOP
_ALPHA_BOT = (BOT_ARC_LEN / 2.0) / R_BOTTOM
TOP_END_X = R_TOP * math.sin(_ALPHA_TOP)
TOP_END_Y = CENTER_Y - R_TOP * math.cos(_ALPHA_TOP)
BOT_END_X = R_BOTTOM * math.sin(_ALPHA_BOT)
BOT_END_Y = CENTER_Y - R_BOTTOM * math.cos(_ALPHA_BOT)

# Tail boundary: retain the old 5.588 mm radial land and tapered closure.
_TAIL_RAD_X = TOP_END_X / R_TOP
_TAIL_RAD_Y = (TOP_END_Y - CENTER_Y) / R_TOP
TAIL_TIP_X = -TOP_END_X - TAIL_TIP_FACE * _TAIL_RAD_X
TAIL_TIP_Y = TOP_END_Y + TAIL_TIP_FACE * _TAIL_RAD_Y

# Rod-side boundary: both concentric arcs terminate at one square full-depth
# shoulder, then step to a 5 mm tongue centred on the retained pin.  The square
# free-end face is 6 mm beyond the pin.
ROD_STEP_X = ROD_HOLE_X - ROD_STEP_FROM_PIN
ROD_STEP_TOP_Y = CENTER_Y - math.sqrt(R_TOP**2 - ROD_STEP_X**2)
ROD_STEP_BOTTOM_Y = CENTER_Y - math.sqrt(R_BOTTOM**2 - ROD_STEP_X**2)
ROD_HOLE_Y = (
    CENTER_Y - math.sqrt(R_BOTTOM**2 - ROD_HOLE_X * ROD_HOLE_X)
) + ROD_HOLE_ABOVE_BOTTOM
ROD_TONGUE_END_X = ROD_HOLE_X + ROD_TONGUE_BEYOND_PIN
ROD_TONGUE_TOP_Y = ROD_HOLE_Y + ROD_TONGUE_DEPTH / 2.0
ROD_TONGUE_BOTTOM_Y = ROD_HOLE_Y - ROD_TONGUE_DEPTH / 2.0


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
# pivot; neighbouring hubs touch face to face and SET the 7.0565 station
# pitch -- there are no loose spacer bushings (the 19 `pivot-bushing` parts
# are retired). OD kept at the old bushing's O10: at d = 0 the amplitude
# bar's foot cheeks pass 5.63 above the shaft axis, so OD < ~11.25.
HUB_DIA = 10.0
HUB_LENGTH = 7.0565  # == machine channels.station_pitch_mm (asserted by the build)

# Manufacturing GD&T limits consumed by the part's drawing projection.
GEOMETRIC_TOLERANCES_MM: dict[str, str] = {
    "rod-pin hole position": "0.20",
}
