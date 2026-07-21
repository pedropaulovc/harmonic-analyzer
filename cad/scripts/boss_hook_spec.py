r"""Pure-data dimensional contract shared by the summing-lever boss hook and drawing.

PURE DATA, no SolidWorks/COM imports.  ``build_boss_hook`` imports the marked-
dimension NAME map + notes from here; ``draw_boss_hook`` imports the hook's wire
geometry from ``build_boss_hook`` for its view math and keeps exactly
``DRAWING_DIMENSIONS`` across its per-view keep maps.
"""

from __future__ import annotations


# --- Marked-dimension contract: feature -> the parametric dimension NAMES the
# print shows.  The J-hook is a single swept wire; its whole shape is three
# numbers -- the wire diameter (WireProfile), the straight rise and the arm run
# (HookPath).  The elbow radius (R3) and the seat/ring functions are relations or
# assembly context, so they ride the notes rather than duplicate-named imported
# dims. ---
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "WireProfile": {"RodDia"},
    "HookPath": {"Rise", "ArmRun"},
}

# Lines kept short (<~66 chars) so the left-anchored block stays clear of the
# title block (x >= 0.264 m); it grows DOWNWARD from its anchor.  <MOD-DIAM>
# renders as the diameter symbol.
DRAWING_NOTES = "\n".join(
    (
        "1. FINISHED WIRE <MOD-DIAM>3.00 +0.00/-0.05; ENDS SQUARE.",
        "2. FORM: 12 STRAIGHT RISE, 90 DEG ELBOW (R3 AT WIRE",
        "   CENTERLINE), THEN 3.5 ARM RUN; DIMS ARE STRAIGHT TANGENTS.",
        "3. R3 +/-0.20; RISE + ARM LENGTHS +/-0.20. LAY THE FULL",
        "   FORMED PROFILE ON A FLAT SURFACE PLATE; 0.25 MAX GAP.",
        "4. AT BEND CROWN, (MAX DIA - MIN DIA)/3.00 <= 0.05.",
        "5. NO CRACKS VISIBLE AT BEND UNDER 5X MAGNIFICATION.",
    )
)
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 2:1"
