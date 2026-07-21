r"""Channel-lever dimensional contract -- the single source of truth shared by
the part build (``build_channel_lever.py``) and its manufacturing drawing
(``draw_channel_lever.py``).

PURE DATA, no SolidWorks/COM imports (see ``crank_arm_spec`` for the pattern).
The nominal geometry MUST match the constants in build_channel_lever.py (the
test cross-checks the load-bearing ones).
"""

from __future__ import annotations

# --- Nominal geometry (DIMENSIONS.md "Chapter 17"). ---
LEVER_SPRING_X = 177.8  # fulcrum -> spring-hole c2c, 7"
BAR_TALL = 9.5  # bar height
LEVER_THICKNESS = 3.0
PIVOT_HOLE_DIA = 6.5  # fulcrum bore riding the 6.35 fulcrum shaft
BAR_PIN_X = 127.0  # fulcrum -> bar-pin c2c, 5"
TAB_START_X = 169.0  # bar steps down to the end tab
TAB_HALF = 3.0  # tab 6.0 tall
TIP_RADIUS = 3.0  # rounded tab tip
TIP_ARC_CX = LEVER_SPRING_X + 5.0  # 182.8

# --- Derived spans. ---
NOSE_RADIUS = BAR_TALL / 2.0  # 4.75 fulcrum nose
TIP_END_X = TIP_ARC_CX + TIP_RADIUS  # 185.8 overall length


# --- Marked-dimension contract: feature -> the parametric dimension NAMES the
# print shows.  build_channel_lever marks exactly these. ---
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "LeverOutline": {"BarLength", "TipCentreX", "NoseRadius", "TipRadius"},
    "FulcrumProfile": {"FulcrumDia"},
}

DRAWING_NOTES = "\n".join(
    (
        "1. MACHINE FROM CONTINUOUS-CAST FLAT STOCK.",
        "2. INDICATED BROAD FACE ESTABLISHES DATUM A;",
        "   MACHINE OPPOSITE FACE TO 3.00 +/-0.10 OVERALL.",
        "3. DATUM B IS THE DERIVED AXIS OF THE FULCRUM BORE:",
        "   REAM DIA 6.50 +0.03/0 THRU, Ra 1.6.",
        "4. ALL HOLE AXES AND THE TIP R3 CENTRE",
        "   BASIC 4.75 FROM DATUM C.",
        "5. TIP R3 CENTRE BASIC 182.80 FROM B; SPRING-HOLE",
        "   CENTRE BASIC 177.80 FROM B; THEY ARE NOT CONCENTRIC.",
        "6. PROFILE FCF APPLIES ALL AROUND OUTER PERIMETER",
        "   EXCEPT DATUM C; STRAIGHTS TANGENT TO RADII.",
    )
)
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:4"
