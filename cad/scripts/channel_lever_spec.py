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
# Reamed running bore: (upper, lower) deviations on the model dimension -- the
# same +0.03/0 band as the rocker arm's pivot bore on the same 6.35 shaft
# (drawing-simplicity-policy.md rule 2: the band rides the dimension).
PIVOT_HOLE_BAND = (0.03, 0.00)
BAR_PIN_X = 127.0  # fulcrum -> bar-pin c2c, 5"
TAB_START_X = 169.0  # bar steps down to the end tab
TAB_HALF = 3.0  # tab 6.0 tall
TIP_RADIUS = 3.0  # rounded tab tip
TIP_ARC_CX = LEVER_SPRING_X + 5.0  # 182.8

# --- Derived spans. ---
NOSE_RADIUS = BAR_TALL / 2.0  # 4.75 fulcrum nose
TIP_END_X = TIP_ARC_CX + TIP_RADIUS  # 185.8 tip extreme
OVERALL_LENGTH = TIP_END_X + NOSE_RADIUS  # 190.55 nose extreme to tip extreme


# --- Marked-dimension contract: feature -> the parametric dimension NAMES the
# print shows.  build_channel_lever marks exactly these. ---
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "LeverOutline": {"BarLength", "TipCentreX", "NoseRadius", "TipRadius"},
    "FulcrumProfile": {"FulcrumDia"},
}

# Notes: part-specific process facts only, never a tolerance, never the
# title block (drawing-simplicity-policy.md rule 6).  Hole sizes and
# processes ride the native callouts; every station -- the tip R3 centre
# included -- is a sheet dimension, so no note restates an offset.
DRAWING_NOTES = "\n".join(
    (
        "MACHINE FROM CONTINUOUS-CAST FLAT STOCK.",
        "HOLES AND TIP R3 CENTRE ON THE BAR MID-HEIGHT LINE.",
    )
)
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:4"
