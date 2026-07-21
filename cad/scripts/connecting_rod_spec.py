r"""Connecting-rod dimensional contract -- the single source of truth shared by
the part build (``build_connecting_rod.py``) and its manufacturing drawing
(``draw_connecting_rod.py``).

PURE DATA, no SolidWorks/COM imports (see ``crank_arm_spec`` for the pattern).
The nominal geometry here MUST match the constants in build_connecting_rod.py
(the test cross-checks the load-bearing ones); the marked-dimension -> kept map
is the drift alarm the offline test enforces.
"""

from __future__ import annotations

# --- Nominal geometry (DIMENSIONS.md "Chapter 13 - Connecting rods"). ---
CENTER_DISTANCE = 147.6655  # cam ring centre -> rocker pin (vertical rod)
RING_BORE_DIA = 30.8  # strap bore riding the eccentric cam
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


# --- Marked-dimension contract: feature -> the parametric dimension NAMES the
# print shows.  build_connecting_rod marks exactly these; draw_connecting_rod
# keeps exactly their union across its per-view ``keep`` maps. ---
# The marked-dimension contract moved to ``connecting_rod_notes`` with the rest
# of the drawing-only data (codex #354): it changes for drawing-only mark/keep
# updates, and ``build_channel_assembly`` imports this module.

# Drawing prose (DRAWING_NOTES / ISOMETRIC_VIEW_NOTE) lives in
# connecting_rod_notes.py so assemblies importing this spec never inherit a
# notes edit into their rebuild closure (codex #354).
