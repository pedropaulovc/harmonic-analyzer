r"""Pure-data dimensional contract shared by the output fixture and its drawing.

PURE DATA, no SolidWorks/COM imports.  ``build_output_fixture`` imports the
marked-dimension NAME map + notes from here; ``draw_output_fixture`` imports the
same collar nominals for its view math and keeps exactly ``DRAWING_DIMENSIONS``
across its per-view ``keep`` maps, so the part-side marks and the drawing-side
keeps cannot silently drift.
"""

from __future__ import annotations


# Collar nominals (mirror build_output_fixture; a small brass collar that slides
# the trace's vertical placement on the Ø5 output rod).  Kept here so the drawing
# stays COM-free.
COLLAR_DIA = 10.0
COLLAR_HEIGHT = 8.0
ROD_BORE_DIA = 5.2
CROSS_HOLE_DIA = 2.261  # #4-40 tap drill (radial cross hole at mid-height)

# --- Marked-dimension contract: feature -> the parametric dimension NAMES the
# print shows.  The end view carries the two concentric diameters (collar OD +
# rod bore); the side view carries the cross-hole diameter and its mid-height
# station.  The collar HEIGHT and the slip-fit intent are in the notes (a tiny
# collar over-dimensioned would swamp the 3:1 sheet). ---
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "CollarProfile": {"CollarDiaDim"},
    "RodBoreProfile": {"RodBoreDiaDim"},
    "CrossHoleProfile": {"CrossHoleDiaDim"},
}

# Lines kept short (<~66 chars) so the left-anchored block stays clear of the
# title block (x >= 0.264 m); it grows DOWNWARD from its anchor.
DRAWING_NOTES = "\n".join(
    (
        "1. FINISHED COLLAR <MOD-DIAM>10.00 +/-0.05 X 8.00 +/-0.05 HIGH.",
        "2. ROD BORE <MOD-DIAM>5.20 +0.03/0.00 THRU; REAM. BORE + OD",
        "   CONCENTRIC WITHIN 0.05 TIR.",
        "3. RADIAL CROSS-HOLE AXIS 4.00 +/-0.05 FROM BOTTOM END.",
        "   DRILL <MOD-DIAM>2.26 THRU BOTH WALLS; TAP NEAR WALL ONLY",
        "   #4-40 UNC-2B THRU TO THE <MOD-DIAM>5.20 BORE.",
        "4. BREAK BORE + CROSS-HOLE EDGES 0.10 MAX.",
    )
)
END_VIEW_NOTE = "END VIEW SCALE 3:1"
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 2:1"
