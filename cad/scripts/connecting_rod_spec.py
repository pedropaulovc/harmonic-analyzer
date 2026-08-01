r"""Connecting-rod dimensional contract -- the single source of truth shared by
the part build (``build_connecting_rod.py``) and its manufacturing drawing
(``draw_connecting_rod.py``).

PURE DATA, no SolidWorks/COM imports (see ``crank_arm_spec`` for the pattern).
The nominal geometry here MUST match the constants in build_connecting_rod.py
(the test cross-checks the load-bearing ones); the marked-dimension -> kept map
is the drift alarm the offline test enforces.
"""

from __future__ import annotations

from _gtol_spec import CylinderFace
from _surface_finish import MACHINED_UM, SurfaceFinishControl

# --- Nominal geometry (DIMENSIONS.md "Chapter 13 - Connecting rods"). ---
CENTER_DISTANCE = 171.71800779906664  # sine-home closure (PR #458): level arm
# with the cam ring at MID-throw (cam_phase_spec.CAM_PHASE_DEG 88.5), so the
# rocker swings symmetrically +-~3.72 deg about level.  |pin_level - ring(88.5)|
# solved by build_channel_assembly's two-circle closure; the rod hangs plumb at
# the cos-mode home (ring top) and ~2.8 deg oblique at the authored sine rest.
# (Supersedes 163.1010 -- the fixed-post recenter paired level with ring TOP,
# a one-sided rod-side-down stroke.)
RING_BORE_DIA = 30.8  # strap bore riding the eccentric cam
RING_BORE_DIA_BAND = (0.10, 0.00)  # running bore; (upper, lower) deviations
RING_WALL = 5.0  # radial strap wall
RING_THICKNESS = 3.0
SHANK_WIDTH = 8.0
SHANK_THICKNESS = 2.5
HEAD_WIDTH = 10.0  # across the tombstone cheeks
HEAD_HEIGHT = 10.5  # crown top -> shoulder root
HEAD_CROWN_ABOVE_PIN = 2.4  # crown top above the pin centre
HEAD_THICKNESS = 2.5
PIN_HOLE_DIA = 1.994  # rocker pin hole = #47 number drill

# --- Derived spans (mirror build_connecting_rod). ---
RING_OUTER_RADIUS = RING_BORE_DIA / 2.0 + RING_WALL  # 20.4
HEAD_TOP_Y = CENTER_DISTANCE + HEAD_CROWN_ABOVE_PIN  # crown top (150.07)
RING_BOTTOM_Y = -RING_OUTER_RADIUS  # -20.4

SURFACE_FINISHES = (
    SurfaceFinishControl("strap_bore", MACHINED_UM, CylinderFace(RING_BORE_DIA)),
)


# --- Marked-dimension contract: feature -> the parametric dimension NAMES the
# print shows.  build_connecting_rod marks exactly these; draw_connecting_rod
# keeps exactly their union across its per-view ``keep`` maps. ---
# The marked-dimension contract moved to ``connecting_rod_notes`` with the rest
# of the drawing-only data (codex #354): it changes for drawing-only mark/keep
# updates, and ``build_channel_assembly`` imports this module.

# Drawing prose (DRAWING_NOTES / ISOMETRIC_VIEW_NOTE) lives in
# connecting_rod_notes.py so assemblies importing this spec never inherit a
# notes edit into their rebuild closure (codex #354).


# Manufacturing GD&T limits consumed by the part's drawing projection.
GEOMETRIC_TOLERANCES_MM: dict[str, str] = {
    "rocker pin hole position": "0.20",
}
