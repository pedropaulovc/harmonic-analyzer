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
        "1. RULED BRASS BAR 200 X 8 X 3 (CDA 260, HALF-HARD).",
        "2. 0-10 SCALE: 10 DIVISIONS OVER AN 80 MM SPAN (8 PITCH),",
        "   CENTRED ON THE BAR LENGTH.",
        "3. GRADUATIONS ENGRAVED 0.5 DEEP, BLACK-FILLED; THE 0.5",
        "   TICK IS LONGER THAN ANY OTHER (HAND-STAMPED ORIGINAL).",
    )
)
FRONT_VIEW_NOTE = "RULED FACE SCALE 1:1"
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:2"
