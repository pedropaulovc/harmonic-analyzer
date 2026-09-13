r"""Pure-data dimensional contract shared by the measuring stick and drawing.

PURE DATA, no SolidWorks/COM imports.  The engraved scale itself is NOT owned
here: it lives in ``cad/config/machine/amplitude.yaml`` and is read through
``measuring_stick_geom`` (re-exported below for the notes and the builder).
``build_measuring_stick`` imports the marked-dimension NAME map + notes from here; ``draw_measuring_stick`` imports the
bar's plan geometry from ``build_measuring_stick`` for its view math and keeps
exactly ``DRAWING_DIMENSIONS``.
"""

from __future__ import annotations

from measuring_stick_geom import (
    DIVISION_COUNT,
    DIVISION_SPACING,
    MINOR_PER_DIVISION,
    MINOR_SPACING,
    SCALE_SPAN,
)

# The engraved scale is CONFIG (amplitude.stick_*, read through
# measuring_stick_geom), so the note TEXT is derived from the same counts the
# build patterns: TOP is the highest engraved value, MINORS the tick count
# between two full ticks. A count edit rewrites these notes and fails
# check:numerals until the numerals DXF is regenerated -- it never leaves the
# sheet describing a scale the part does not carry.
TOP = DIVISION_COUNT - 1
MINORS = MINOR_PER_DIVISION - 1


# --- Marked-dimension contract: feature -> the parametric dimension NAMES the
# print shows.  Only the bar's overall envelope (BodyProfile length + width) is
# marked; the graduation swarm (DIVISION_COUNT ticks, MINORS per division + the
# longer 0.5 tick) is carried
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
        f"   SHOWN. SCALE SPAN {SCALE_SPAN:.2f}; THE {TOP} TICK 0.50 +/-0.25 FROM",
        "   THE FAR END.",
        f"2. ENGRAVE {DIVISION_COUNT} FULL TICKS (VALUES 0 THRU {TOP}). THE 0 TICK",
        f"   IS THE DATUM: TICK N AT {DIVISION_SPACING:.2f} X N FROM THE 0 TICK,",
        "   EACH WITHIN +/-0.05 OF ITS OWN POSITION",
        f"   (NONCUMULATIVE; 0-TO-{TOP} SPAN {SCALE_SPAN:.2f} REF). {MINORS} MINOR",
        f"   TICKS PER DIVISION AT {MINOR_SPACING:.2f} PITCH, 1.80 +/-0.10 UP FROM",
        "   THE BOTTOM EDGE SHOWN, SAME SLOT SECTION.",
        "   SLOTS: SQUARE BOTTOM, 0.40 +/-0.05 WIDE, 0.50 +/-0.05",
        "   DEEP NORMAL TO THE RULED FACE; EACH FULL TICK RUNS",
        "   3.00 +/-0.10 UP FROM THE BOTTOM EDGE SHOWN. ONE",
        "   HALF-DIVISION TICK BETWEEN 0 + 1: SAME SLOT SECTION,",
        "   4.00 +/-0.10 UP FROM THE BOTTOM EDGE.",
        "3. ENGRAVE 2.00 +/-0.10 HIGH ASME Y14.2 VERTICAL GOTHIC",
        f"   NUMERALS 0 THRU {TOP}, STROKE WIDTH 0.30 +/-0.10, TURNED",
        f"   90 DEG: DIGIT TOPS TOWARD THE {TOP} END (READ WITH THE",
        f"   {TOP} END UP). NUMERALS 0-{TOP - 1} START 0.60 +/-0.10 PAST THEIR",
        f"   FULL TICK TOWARD {TOP}; THE {TOP} NUMERAL ENDS 0.60 +/-0.10",
        "   SHORT OF ITS TICK. TICK-SIDE END OF EACH NUMERAL",
        "   3.60 +/-0.10 ABOVE THE BOTTOM EDGE SHOWN (0.60 BEYOND",
        "   THE FULL-TICK ENDS). DEPTH 0.50 +/-0.05, SAME SLOT",
        "   SECTION AS THE TICKS. BLACK-FILL ALL ENGRAVING: FLAT",
        "   BLACK ENAMEL WIPE-FILLED, CURED BEFORE FINAL POLISH.",
        "4. TICK VALUES ARE ALSO SHOWN OFFSET BELOW THE BAR FOR",
        "   LEGIBILITY; THE ENGRAVED NUMERALS ARE PER NOTE 3.",
    )
)
FRONT_VIEW_NOTE = "RULED FACE SCALE 1:1"
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:2"
