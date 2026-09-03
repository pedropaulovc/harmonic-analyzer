r"""Pure-data dimensional contract shared by the output fixture and its drawing.

PURE DATA, no SolidWorks/COM imports.  ``build_output_fixture`` imports the
marked-dimension NAME map + notes from here; ``draw_output_fixture`` imports the
same collar nominals for its view math and keeps exactly ``DRAWING_DIMENSIONS``
across its per-view ``keep`` maps, so the part-side marks and the drawing-side
keeps cannot silently drift.
"""

from __future__ import annotations


# Collar nominals -- the SINGLE source: ``build_output_fixture`` imports these
# to cut the part and ``draw_output_fixture`` reads them for its view math, so
# the print and the part cannot drift (codex review #361).  Kept literal here
# so the module stays pure data; the build pins CROSS_HOLE_DIA against
# ``_holes.TAP_DRILL_MM["#4-40"]`` and the offline drawing test re-asserts it.
COLLAR_DIA = 10.0
COLLAR_HEIGHT = 8.0
ROD_BORE_DIA = 5.2
ROD_BORE_BAND = (0.03, 0.00)  # (upper, lower) deviations: slip fit on the rod
CROSS_HOLE_DIA = 2.261  # #4-40 tap drill (radial cross hole at mid-height)
CROSS_HOLE_TAP = "#4-40"

# --- Marked-dimension contract: feature -> the parametric dimension NAMES the
# print shows.  The end view carries the two concentric diameters (collar OD +
# rod bore); the side view carries the collar length (the Collar extrude
# depth), the cross-hole diameter and its station from the faced bottom end
# (machinist review 2026-09-02: both were missing, so the part could not be
# made unique). ---
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "CollarProfile": {"CollarDiaDim"},
    "Collar": {"CollarHeightDim"},
    "RodBoreProfile": {"RodBoreDiaDim"},
    "CrossHoleProfile": {"CrossHoleDiaDim", "CrossHeight"},
}

# Notes: part-specific process facts only, never a tolerance (the rod-bore
# band rides the model dimension), never the title block
# (drawing-simplicity-policy.md rule 6).  The ream and the tap instructions
# ride the hole callouts on the view.
DRAWING_NOTES = "ROD BORE: SLIP FIT ON VERTICAL ROD MHA-044."
END_VIEW_NOTE = "END VIEW SCALE 3:1"
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 2:1"
