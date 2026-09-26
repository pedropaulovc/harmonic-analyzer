r"""Amplitude-bar dimensional contract -- the single source of truth shared by
the part build (``build_amplitude_bar.py``) and its manufacturing drawing
(``draw_amplitude_bar.py``).

PURE DATA, no SolidWorks/COM imports (see ``crank_arm_spec`` for the pattern).
The nominal geometry MUST match the constants in build_amplitude_bar.py.

The bar is ~808 mm long but only 6.35 mm square, so the print shows a 1:4
full-length front view (overall length + top pin hole), a right end view for the
square section, and carries the two small end notches in the notes.
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


# --- Marked-dimension contract.  The bar is far too long to dimension the tiny
# end notches on the 1:4 view, so only the overall length is a graphical marked
# dim; the notch sizes are dimensioned in the notes. ---
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "BarProfile": {"BarLength"},
}

# Drawing prose (DRAWING_NOTES / view notes) and the notch-depth band live in
# amplitude_bar_notes.py -- see rocker_arm_notes for the rationale.
