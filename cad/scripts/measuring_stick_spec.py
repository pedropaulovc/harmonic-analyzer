r"""Pure-data dimensional contract shared by the measuring stick and drawing.

PURE DATA, no SolidWorks/COM imports.  ``build_measuring_stick`` imports the
marked-dimension NAME map + notes from here; ``draw_measuring_stick`` imports the
bar's plan geometry from ``build_measuring_stick`` for its view math and keeps
exactly ``DRAWING_DIMENSIONS``.
"""

from __future__ import annotations


# --- Marked-dimension contract: feature -> the parametric dimension NAMES the
# print shows.  Only the bar's overall envelope (BodyProfile length + width) is
# marked; the 0-10 graduation swarm (11 ticks + the longer 0.5 tick) is carried
# in the notes -- a ruled scale dimensioned tick-by-tick would swamp an 8 mm-tall
# bar, and the scale span / pitch fully define it. ---
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "BodyProfile": {"BodyLength", "BodyWidth"},
}

# Lines kept short (<~66 chars) so the left-anchored block stays clear of the
# title block (x >= 0.264 m); it grows DOWNWARD from its anchor.
DRAWING_NOTES = "\n".join(
    (
        "1. FINISHED BAR 200.00 X 8.00 X 3.00; RULE THE BROAD FACE",
        "   SHOWN. SCALE SPAN 80.00, CENTERED ON BAR LENGTH",
        "   +/-0.25.",
        "2. ENGRAVE 11 FULL TICKS (VALUES 0 THRU 10) AT 8.00",
        "   +/-0.05 PITCH, NONCUMULATIVE; 0-TO-10 SPAN (80.00) REF.",
        "   SLOTS: SQUARE BOTTOM, 0.40 +/-0.05 WIDE, 0.50 +/-0.05",
        "   DEEP NORMAL TO THE RULED FACE; EACH FULL TICK RUNS",
        "   3.00 +/-0.10 UP FROM THE BOTTOM EDGE SHOWN. ONE",
        "   HALF-DIVISION TICK BETWEEN 0 + 1: SAME SLOT SECTION,",
        "   4.00 +/-0.10 UP FROM THE BOTTOM EDGE.",
        "3. ENGRAVE 2.00 +/-0.10 HIGH ASME Y14.2 VERTICAL GOTHIC",
        "   NUMERALS, STROKE WIDTH 0.30 +/-0.10. CENTER EACH ON",
        "   ITS FULL TICK +/-0.20; NUMERAL BOTTOM 4.50 +/-0.10",
        "   ABOVE BOTTOM EDGE. DEPTH 0.20 +/-0.05. READ 0 THRU 10",
        "   LEFT TO RIGHT. BLACK-FILL ALL ENGRAVING.",
    )
)
FRONT_VIEW_NOTE = "RULED FACE SCALE 1:1"
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:2"
