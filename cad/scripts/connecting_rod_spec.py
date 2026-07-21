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
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "RingDiscProfile": {"RingOuterDia"},
    "StrapBoreProfile": {"StrapBoreDia"},
    "ShankProfile": {"ShankWidthDim"},
}

DRAWING_NOTES = "\n".join(
    (
        "1. STRAP BORE MACHINED FOR THE",
        "   30.6 ECCENTRIC CAM, 0.1 CLR/SIDE.",
        "2. ROD HANGS PLUMB; RING CENTRE TO",
        "   ROCKER PIN 147.67.",
        "3. RING 3.0 THICK; SHANK AND HEAD",
        "   2.5 THICK.",
        "4. HEAD 10.0 W x 10.5 HIGH, R5.0",
        "   CROWN; 1.2 SHOULDER TAPER FROM",
        "   8.0 SHANK. PIN C/L 2.40 BELOW CROWN.",
        "5. ROCKER PIN HOLE: #47 DRILL THRU.",
    )
)
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:2"
