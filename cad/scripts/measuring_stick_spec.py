r"""Pure-data dimensional contract shared by the measuring stick and drawing.

PURE DATA, no SolidWorks/COM imports.  ``build_measuring_stick`` imports the
marked-dimension NAME map + notes from here; ``draw_measuring_stick`` imports the
bar's plan geometry from ``build_measuring_stick`` for its view math and keeps
exactly ``DRAWING_DIMENSIONS``.
"""

from __future__ import annotations


# --- Marked-dimension contract: feature -> the parametric dimension NAMES the
# print shows.  Only the bar's overall envelope (BodyProfile length + width) is
# marked; the 0-10 graduation swarm (11 ticks, 90 tenths + the longer 0.5 tick) is carried
# in the notes -- a ruled scale dimensioned tick-by-tick would swamp an 8 mm-tall
# bar, and the scale span / pitch fully define it. ---
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "BodyProfile": {"BodyLength", "BodyWidth"},
}

# Notes: part-specific process facts only, never a tolerance, never the
# title block (drawing-simplicity-policy.md rule 6).
DRAWING_NOTES = "\n".join(
    (
        "ENGRAVE 0-10: 11 FULL TICKS AT 14.20 PITCH, 9 MINOR TICKS PER DIVISION,",
        "ONE HALF TICK BETWEEN 0 AND 1. SLOTS 0.40 WIDE X 0.50 DEEP, SQUARE BOTTOM;",
        "FULL 3.00 / HALF 4.00 / MINOR 1.80 LONG FROM THE BOTTOM EDGE SHOWN.",
        "NUMERALS 2.00 HIGH X 0.50 DEEP, TURNED 90 DEG, 0.60 PAST THEIR TICK; BLACK-FILL.",
    )
)
FRONT_VIEW_NOTE = "RULED FACE SCALE 1:1"
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:2"
