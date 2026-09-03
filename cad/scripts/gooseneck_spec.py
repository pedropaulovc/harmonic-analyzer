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

# Lines kept short (<~60 chars) so the left-anchored block clears both the tall
# tube elevation and the title block (x >= 0.264 m); it grows DOWNWARD. The
# screw is the book's p.45 "slotted screw" in the arm end: the spring's top
# eye rides its exposed shank, so the screw is set once and never removed --
# the part model carries it integral (build_gooseneck), the notes carry it as
# the fastener it is.
DRAWING_NOTES = "\n".join(
    (
        "1. TUBE <MOD-DIAM>16.00 +/-0.10 X 2.0 WALL; CUT ENDS",
        "   SQUARE.",
        "2. FORM CENTERLINE (R51 = CENTERLINE RADIUS):",
        "   442.3 STRAIGHT LEG TO BEND TANGENT, R51 90-DEG",
        "   BEND, 44.25 STRAIGHT ARM TO END FACE. LINEAR",
        "   +/-0.5; RADIUS +/-0.5; ANGLE +/-1 DEG. LEG + ARM",
        "   CENTERLINES COPLANAR (ELEVATION PLANE) WITHIN 1.0.",
        "3. END PLUG: AISI 1018 <MOD-DIAM>12.00 (LIGHT PRESS IN",
        "   BORE) X 6.00, FLUSH WITH ARM END FACE +/-0.10.",
        "   SILVER-BRAZE BAg-7 PER AWS A5.8, FULL",
        "   FAYING-SURFACE PENETRATION; EXPOSED GAP 0.10 MAX.",
        "4. AFTER BRAZE: DRILL + TAP #6-32 UNC X 6.0 DEEP ON",
        "   THE TUBE AXIS +/-0.15, SQUARE TO THE END FACE.",
        "5. SPRING SCREW: AISI 1018 SLOTTED ROUND HEAD #6-32",
        "   X 14 UNDER HEAD; HEAD <MOD-DIAM>10.00 X 2.00.",
        "   DIAGONAL DRIVER SLOT 0.80 WIDE X 0.80 DEEP.",
        "   SEAT ON END FACE: 8.00",
        "   +/-0.25 SHANK EXPOSED (SPRING EYE RIDES HERE).",
        "   NOT REMOVED IN SERVICE; MODELED INTEGRAL.",
        "6. BEND OVALITY 5% MAX; NO FLATS, KINKS OR CRACKS.",
        "7. PLATE ALL SURFACES; NO MASKING. DIMS PRE-PLATE.",
    )
)
ELEVATION_VIEW_NOTE = "ELEVATION SCALE 1:3"
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:4"
