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
        "1. TUBE <MOD-DIAM>16.00 +/-0.10 X 2.0 WALL; CUT ENDS",
        "   SQUARE.",
        "2. FORM CENTERLINE (R51 SHOWN IS THE CENTERLINE",
        "   RADIUS): 455 STRAIGHT LEG TO BEND TANGENT,",
        "   R51 90-DEG BEND, THEN 61 STRAIGHT ARM TO END.",
        "   LINEAR +/-0.5; RADIUS +/-0.5; ANGLE +/-1 DEG.",
        "   LEG + ARM CENTERLINES LIE IN ONE COMMON PLANE",
        "   (THE ELEVATION PLANE) WITHIN 1.0.",
        "3. LUG: AISI 1018 BLANK 5.50 ALONG ARM X 10.50",
        "   HIGH (BEFORE COPE) X 3.00 THICK NORMAL TO",
        "   ELEVATION, CENTERED ON THE TUBE CENTERLINE",
        "   PLANE +/-0.25. COPE TOP TO TUBE OD (FINISHED",
        "   HEIGHT GOVERNED BY THE COPE); BRAZE TO ARM",
        "   UNDERSIDE; FREE-END FACE 3.00 FROM ARM END.",
        "4. PIN: AISI 1018, <MOD-DIAM>4.00 +/-0.05 X 11.00.",
        "   AXIS PARALLEL TO ARM, 4.00 ABOVE LUG BOTTOM,",
        "   ON THE LUG MID-THICKNESS PLANE +/-0.25.",
        "   FREE-END FACE FLUSH WITH LUG; EXTEND TOWARD BEND.",
        "5. SILVER-BRAZE LUG + PIN BAg-7 PER AWS A5.8, EACH",
        "   JOINT: FULL FAYING-SURFACE PENETRATION; 1.0 MIN",
        "   LEG FILLET ALL ROUND; EXPOSED GAP 0.10 MAX;",
        "   TOTAL VOID LENGTH 0.50 MAX PER JOINT (VISUAL).",
        "6. BEND OVALITY 5% MAX; NO FLATS, KINKS OR CRACKS.",
        "7. PLATE ALL SURFACES; NO MASKING. DIMS PRE-PLATE.",
    )
)
ELEVATION_VIEW_NOTE = "ELEVATION SCALE 1:3"
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:4"
