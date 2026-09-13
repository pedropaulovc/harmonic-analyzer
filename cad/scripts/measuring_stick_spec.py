r"""Pure-data dimensional contract shared by the measuring stick and drawing.

PURE DATA, no SolidWorks/COM imports.  ``build_measuring_stick`` imports the
marked-dimension NAME map + notes from here; ``draw_measuring_stick`` imports the
bar's plan geometry from ``build_measuring_stick`` for its view math and keeps
exactly ``DRAWING_DIMENSIONS``.
"""

from __future__ import annotations


# --- Scale geometry (shared with build_measuring_stick and error_budget). ---
DIVISION_SPACING = 14.2  # ch16 page001_img02 (200 mm bar at 5.65 px/mm): the
# 0 and 10 numerals sit 805 px = 142 mm apart -- one half of the rocker arm's
# 292 mm working arc, as the text says (2026-09 re-derive; the old 80 mm was a
# misread of the 8 mm width callout).
DIVISION_COUNT = 11  # full ticks 0..10 (stated 0-10 scale)
MINOR_PER_DIVISION = 10  # tenths: 9 short ticks between full ticks (page001_img03)
MINOR_SPACING = DIVISION_SPACING / MINOR_PER_DIVISION  # 1.42


# --- Marked-dimension contract: feature -> the parametric dimension NAMES the
# print shows.  Only the bar's overall envelope (BodyProfile length + width) is
# marked; the 0-10 graduation swarm (11 ticks, 90 tenths + the longer 0.5 tick) is carried
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
        "   SHOWN. SCALE SPAN 142.00; THE 10 TICK 0.50 +/-0.25 FROM",
        "   THE FAR END.",
        "2. ENGRAVE 11 FULL TICKS (VALUES 0 THRU 10). THE 0 TICK",
        f"   IS THE DATUM: TICK N AT {DIVISION_SPACING:.2f} X N FROM THE 0 TICK,",
        "   EACH WITHIN +/-0.05 OF ITS OWN POSITION",
        f"   (NONCUMULATIVE; 0-TO-10 SPAN {10 * DIVISION_SPACING:.2f} REF). NINE MINOR",
        f"   TICKS PER DIVISION AT {MINOR_SPACING:.2f} PITCH, 1.80 +/-0.10 UP FROM",
        "   THE BOTTOM EDGE SHOWN, SAME SLOT SECTION.",
        "   SLOTS: SQUARE BOTTOM, 0.40 +/-0.05 WIDE, 0.50 +/-0.05",
        "   DEEP NORMAL TO THE RULED FACE; EACH FULL TICK RUNS",
        "   3.00 +/-0.10 UP FROM THE BOTTOM EDGE SHOWN. ONE",
        "   HALF-DIVISION TICK BETWEEN 0 + 1: SAME SLOT SECTION,",
        "   4.00 +/-0.10 UP FROM THE BOTTOM EDGE.",
        "3. ENGRAVE 2.00 +/-0.10 HIGH ASME Y14.2 VERTICAL GOTHIC",
        "   NUMERALS 0 THRU 10, STROKE WIDTH 0.30 +/-0.10, TURNED",
        "   90 DEG: DIGIT TOPS TOWARD THE 10 END (READ WITH THE",
        "   10 END UP). NUMERALS 0-9 START 0.60 +/-0.10 PAST THEIR",
        "   FULL TICK TOWARD 10; THE 10 NUMERAL ENDS 0.60 +/-0.10",
        "   SHORT OF ITS TICK. TICK-SIDE END OF EACH NUMERAL",
        "   3.60 +/-0.10 ABOVE THE BOTTOM EDGE SHOWN (0.60 BEYOND",
        "   THE FULL-TICK ENDS). DEPTH 0.50 +/-0.05, SAME SLOT",
        "   SECTION AS THE TICKS. BLACK-FILL ALL ENGRAVING: FLAT",
        "   BLACK ENAMEL WIPE-FILLED, CURED BEFORE FINAL POLISH.",
        "4. TICK VALUES ARE ALSO SHOWN OFFSET BELOW THE BAR FOR",
        "   LEGIBILITY; THE ENGRAVED NUMERALS ARE PER NOTE 3.",
        f"5. SCALE IS LINEAR IN STATION ({DIVISION_SPACING:.2f} PER DIVISION),",
        "   0 TICK AT THE ROCKER PIVOT AXIS. ORDINATE TABLE: READOUT.MD.",
    )
)
FRONT_VIEW_NOTE = "RULED FACE SCALE 1:1"
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:2"
