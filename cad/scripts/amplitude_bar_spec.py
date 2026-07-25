r"""Amplitude-bar dimensional contract -- the single source of truth shared by
the part build (``build_amplitude_bar.py``) and its manufacturing drawing
(``draw_amplitude_bar.py``).

PURE DATA, no SolidWorks/COM imports (see ``crank_arm_spec`` for the pattern).
The nominal geometry MUST match the constants in build_amplitude_bar.py.

The bar is ~813 mm long but only 6.35 mm square, so the print shows a 1:4
full-length front view (overall length + top pin hole), a right end view for the
square section, and carries the two small end notches in the notes.
"""

from __future__ import annotations

MM_PER_IN = 25.4

# --- Nominal geometry (DIMENSIONS.md "Chapter 15"). ---
BAR_LENGTH = 846.7  # 846.7: the bar hangs PLUMB from the base-anchored rocker arm to the top
# lever, so the 2026-07-24 frame re-anchor (+33.9 on the lever bank) grew it
# from the legacy 32" / 812.8. Still inside ch15's stated "~80 cm" (84.7).
BAR_WIDTH = 0.25 * MM_PER_IN  # 6.35 square section
BAR_DEPTH = 0.25 * MM_PER_IN  # 6.35
BOTTOM_NOTCH_WIDTH = 0.125 * MM_PER_IN  # 3.175
BOTTOM_NOTCH_HEIGHT = 0.09375 * MM_PER_IN  # 2.381
TOP_NOTCH_WIDTH = 0.125 * MM_PER_IN  # 3.175
TOP_NOTCH_HEIGHT = 0.5 * MM_PER_IN  # 12.7
TOP_PIN_DROP = 0.25 * MM_PER_IN  # 6.35 hole centre below the bar top

# --- Derived. ---
TOP_PIN_Y = BAR_LENGTH - TOP_PIN_DROP  # 806.45


# --- Marked-dimension contract.  The bar is far too long to dimension the tiny
# end notches on the 1:4 view, so only the overall length is a graphical marked
# dim; the notch sizes are dimensioned in the notes. ---
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "BarProfile": {"BarLength"},
}

# The title-block QTY cell owns the 20-off count; notch orientation and
# coplanarity are stated because no view resolves them at 1:4 (machinist
# round 1): both notches live in ONE profile sketch cut thru the full depth,
# so open-to-opposite-ends / common-plane / centred-on-width IS the model
# truth, and the pin hole runs thru the top-notch cheeks at mid-depth.
DRAWING_NOTES = "\n".join(
    (
        "1. BAR SECTION 6.35 SQUARE.",
        "2. BOTTOM NOTCH 3.18 W x 2.38 DEEP;",
        "   TOP NOTCH 3.18 W x 12.70 DEEP;",
        "   BOTH THRU THE FULL DEPTH, OPEN TO",
        "   OPPOSITE ENDS, CENTRED ON THE WIDTH",
        "   WITHIN 0.10, IN ONE COMMON PLANE;",
        "   ROOTS R0.40 MAX.",
        "3. TOP PIN HOLE #47 DRILL THRU BOTH",
        "   TOP-NOTCH CHEEKS AT MID-DEPTH,",
        "   6.35 BELOW THE BAR TOP.",
        "4. BOTTOM NOTCH FLOOR: Ra 0.8.",
        "5. DIMS APPLY AFTER PLATING.",
    )
)
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:8"
END_VIEW_NOTE = "END VIEW SCALE 4:1"
