r"""Pure-data dimensional contract shared by the gooseneck post and its drawing.

PURE DATA, no SolidWorks/COM imports.  ``build_gooseneck`` imports the marked-
dimension NAME map + notes from here; ``draw_gooseneck`` keeps exactly
``DRAWING_DIMENSIONS`` for its elevation-view import.
"""

from __future__ import annotations


# --- Marked-dimension contract: feature -> the parametric dimension NAMES the
# print shows.  The bend RADIUS (R51) and the horizontal ARM RUN are marked --
# both live on the Front-plane sweep-path sketch (BendPath), so they project
# cleanly to the elevation view.  The Ø16 tube, the vertical-leg length and the
# Ø4 spring cross-pin are carried in the notes: a diameter dim on a tube seen
# edge-on imports unreliably, and the leg length is an extrude offset (not a
# sketch dim). ---
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "BendPath": {"BendRadius", "ArmRun"},
}

# Lines kept short (<~60 chars) so the left-anchored block clears both the tall
# tube elevation and the title block (x >= 0.264 m); it grows DOWNWARD.
DRAWING_NOTES = "\n".join(
    (
        "1. POLISHED CHROME STEEL TUBE <MOD-DIAM>16; 90-DEG BEND,",
        "   R51 AT TUBE CENTERLINE.",
        "2. VERTICAL LEG ~455 LONG PASSES THROUGH THE TOP-FRAME",
        "   RAIL BORE; HORIZONTAL ARM REACHES OVER THE SUMMING",
        "   LEVER BOSS.",
        "3. ARM-END LUG CARRIES A <MOD-DIAM>4 CROSS-PIN FOR THE",
        "   COUNTER-SPRING TOP LOOP.",
        "4. NO FLATS, KINKS OR OVALITY AT THE BEND.",
    )
)
ELEVATION_VIEW_NOTE = "ELEVATION SCALE 1:3"
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:4"
