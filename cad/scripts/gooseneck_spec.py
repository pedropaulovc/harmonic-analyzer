r"""Pure-data dimensional contract shared by the gooseneck post and its drawing.

PURE DATA, no SolidWorks/COM imports.  ``build_gooseneck`` imports the marked-
dimension NAME map + notes from here; ``draw_gooseneck`` keeps exactly
``DRAWING_DIMENSIONS`` for its elevation-view import.
"""

from __future__ import annotations


# --- Marked-dimension contract: feature -> the parametric dimension NAMES the
# print shows.  The bend RADIUS (R51) and the horizontal ARM RUN are marked --
# both live on the Front-plane sweep-path sketch (BendPath), so they project
# cleanly to the elevation view.  The Ø16 tube, the vertical-leg length, the
# end plug and the axial spring screw are carried in the notes: a diameter dim
# on a tube seen edge-on imports unreliably, the leg length is an extrude
# offset (not a sketch dim), and the plug/screw are a brazed-then-tapped
# sub-operation the notes schedule in full. ---
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "BendPath": {"BendRadius", "ArmRun"},
}

# Notes: part-specific process facts only, never a tolerance, never the
# title block (drawing-simplicity-policy.md rule 6).  The end plug and the
# axial spring screw (book p.45; 2026-09-02 pass-3 re-derive) are a
# brazed-then-tapped sub-operation the notes schedule; the screw is set once
# and never removed, so the part model carries it integral (build_gooseneck).
DRAWING_NOTES = "\n".join(
    (
        "TUBE 16.00 OD X 2.0 WALL; R51 BEND, 442.3 LEG AND 44.25 ARM.",
        "END PLUG 12.00 DIA X 6.00 STEEL, LIGHT PRESS, BRAZED FLUSH.",
        "AFTER BRAZING, DRILL AND TAP #6-32 X 6.0 DEEP ON THE TUBE AXIS.",
        "SPRING SCREW #6-32 X 14 SLOTTED HEAD; 8.00 SHANK EXPOSED, LEFT IN.",
    )
)
ELEVATION_VIEW_NOTE = "ELEVATION SCALE 1:3"
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:4"
