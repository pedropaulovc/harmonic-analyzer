r"""Amplitude-bar dimensional contract -- the single source of truth shared by
the part build (``build_amplitude_bar.py``) and its manufacturing drawing
(``draw_amplitude_bar.py``).

PURE DATA, no SolidWorks/COM imports (see ``crank_arm_spec`` for the pattern).
The nominal geometry MUST match the constants in build_amplitude_bar.py.

The bar is ~808 mm long but only 6.35 mm square, so the print shows a 1:4
full-length front view (overall length + top pin hole), a right end view for the
square section, and a native detail of each small end notch.
"""

from __future__ import annotations
from _hole_spec import HoleSpec


MM_PER_IN = 25.4

# --- Nominal geometry (DIMENSIONS.md "Chapter 15"). ---
BAR_LENGTH = 32.0 * MM_PER_IN - 4.5  # 808.3: legacy 32" (~80 cm) SHORTENED 4.5
# at the TOP by the 2026-08-02 top-frame rederive (fulcrum chain -4.5: bar top
# 1072.25 -> 1067.75, top pin 1065.9 -> 1061.4; the foot/arc contact at the
# rocker is UNCHANGED, preserving the level d=0 rest pose)
BAR_WIDTH = 0.25 * MM_PER_IN  # 6.35 square section
BAR_DEPTH = 0.25 * MM_PER_IN  # 6.35
BOTTOM_NOTCH_WIDTH = 0.125 * MM_PER_IN  # 3.175
BOTTOM_NOTCH_HEIGHT = 0.09375 * MM_PER_IN  # 2.381
TOP_NOTCH_WIDTH = 0.125 * MM_PER_IN  # 3.175
TOP_NOTCH_HEIGHT = 0.5 * MM_PER_IN  # 12.7
TOP_PIN_DROP = 0.25 * MM_PER_IN  # 6.35 hole centre below the bar top
TOP_PIN_HOLE_SPEC = HoleSpec("drilled_number", "#47")

# --- Derived. ---
TOP_PIN_Y = BAR_LENGTH - TOP_PIN_DROP  # 801.95


# The foot notch's roof rides the rocker's top edge, and at d = 0 the cheeks
# either side pass over the rocker hub; a deep notch drops them onto it one
# for one. So the depth is one-sided, shallow only (user ruling 2026-09-26):
# a shallow notch just lifts the bar at rest (rocker_arm_spec.TOP_EDGE_BAND
# states the lift budget and its effect on the channel). Policy rule 2
# (Codex #936 PRRT_kwDOPHDy386mWF0L): the band is the part's, native on
# BottomNotchHeight, never note text.
BOTTOM_NOTCH_DEPTH_BAND = (0.0, -0.50)  # (upper, lower) deviations

# --- Marked-dimension contract.  The bar is far too long to dimension the tiny
# end notches on the 1:4 view, so the overall length prints there and each
# notch's width and depth print in a native detail of its end. ---
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "BarProfile": {
        "BarLength",
        "BottomNotchHeight",
        "BottomNotchWidth",
        "TopNotchHeight",
        "TopNotchWidth",
    },
}
# Places the part authors on each printed dimension (policy rule 2).
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "BarProfile": {
        "BarLength": 2,
        "BottomNotchHeight": 2,
        "BottomNotchWidth": 2,
        "TopNotchHeight": 2,
        "TopNotchWidth": 2,
    },
}

# Drawing prose (DRAWING_NOTES / view notes) lives in amplitude_bar_notes.py
# -- see rocker_arm_notes for the rationale.
