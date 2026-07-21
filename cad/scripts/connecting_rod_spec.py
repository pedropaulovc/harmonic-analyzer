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

# The strap-bore fit rides the Ø30.80 dimension callout (+0.10/0); the ring
# centre-to-pin distance is a BASIC sheet dimension.  Notes carry only what the
# sheet does not dimension natively, so no number appears in both places.
DRAWING_NOTES = "\n".join(
    (
        "1. STRAP BORE MACHINED; RUNS THE",
        "   30.60 ECCENTRIC CAM, 0.10 MIN CLR/SIDE.",
        "2. RING 3.00 THICK OVER ITS ANNULUS, STEP",
        "   AT THE RING OD; SHANK AND HEAD 2.50;",
        "   ALL CENTRED ON ONE MIDPLANE.",
        "3. RING WALL 5.00 NOM; 4.50 MIN AFTER",
        "   BORING.",
        "4. HEAD 10.00 W x 10.50 HIGH, R5.00 CROWN;",
        "   SHOULDERS RISE 1.20 WIDENING THE 8.00",
        "   SHANK. PIN C/L 2.40 BELOW CROWN.",
        "5. ROCKER PIN HOLE 1X.",
        "6. JUNCTION FILLETS R1.0 MAX, AS CAST OR",
        "   MACHINED; NO DRAFT REQUIRED.",
        "7. GENERAL Ra 3.2 APPLIES TO MACHINED",
        "   SURFACES; UNSPECIFIED SURFACES AS CAST.",
    )
)
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:2"
