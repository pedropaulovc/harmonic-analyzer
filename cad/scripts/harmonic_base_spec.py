r"""Dimensional contract shared by the harmonic base and its drawing.

PURE DATA, no SolidWorks/COM imports (see ``crank_arm_spec`` for the reference
split). ``build_harmonic_base`` imports the plate nominal geometry + the
marked-dimension NAME map from here; ``draw_harmonic_base`` imports the same
geometry for its view math and keeps exactly ``DRAWING_DIMENSIONS`` across its
per-view ``keep`` maps, so the part-side marks and the drawing-side keeps cannot
silently drift.
"""

from __future__ import annotations


MM_PER_IN = 25.4

# --- Two-plate welded base (book ch. 6). Bottom slab + centred top plate, a
# 0.25 in reveal per long side. Legacy inch nominals, photo-confirmed footprint. ---
BOTTOM_LENGTH = 18.0 * MM_PER_IN  # 457.2 (46 cm callout)
BOTTOM_WIDTH = 11.0 * MM_PER_IN   # 279.4 (28 cm callout)
BOTTOM_THICKNESS = 0.5 * MM_PER_IN  # 12.7
TOP_LENGTH = 17.5 * MM_PER_IN   # 444.5 (0.25 in reveal per side)
TOP_WIDTH = 10.5 * MM_PER_IN    # 266.7
TOP_THICKNESS = 1.5 * MM_PER_IN  # 38.1
STACK_HEIGHT = BOTTOM_THICKNESS + TOP_THICKNESS  # 50.8

# --- Marked-dimension contract: feature -> the parametric dimension NAMES the
# print shows. ``build_harmonic_base`` marks exactly these; ``draw_harmonic_base``
# keeps exactly their union. Only the BOTTOM plate's plan footprint is a marked
# sketch dimension -- it is the overall envelope; the centred top plate is fixed
# by the reveal note (note 2), and the plate THICKNESSES are extrude-feature
# parameters (not sketch dims) carried in note 2 as well. Keeping the marked set
# to the two overalls avoids stacking four dimensions on a 457 mm plan that
# barely fits the sheet. ---
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "BottomProfile": {"BottomLen", "BottomWid"},
}

# Lines kept short (<~68 chars) so the left-anchored block stays clear of the
# title block (x >= 0.264 m); it grows DOWNWARD from its anchor.
DRAWING_NOTES = "\n".join(
    (
        "1. MACHINE FROM SOLID STOCK TO THE FINISHED PROFILE SHOWN; NO DRAFT.",
        "   PAD-TO-FLANGE ROOT R0.50 MAX; LOWER FLANGE 12.70 THICK;",
        "   TOTAL HEIGHT 50.80.",
        "2. UPPER PAD 444.50 X 266.70; NEAR LONG SIDE 6.35 +/-0.10 FROM B;",
        "   NEAR LEFT END 6.35 +/-0.10 FROM C.",
        "3. DATUM A = UNDERSIDE FACE; B = LONG-SIDE FACE; C = LEFT-END FACE;",
        "   HOLE-TABLE ORIGIN = B-C. LOCATIONS ARE BASIC.",
        "4. FOUR DIA 13.00 THRU / DIA 23.00 X 6.50 DEEP C'BORES OPEN FROM",
        "   UNDERSIDE. PLAN RIMS AT E1-E4 ARE THE DIA 13.00 THRU FEATURES.",
        "   C'BORE AXIS OFFSET FROM ASSOCIATED DIA 13.00 AXIS: 0.05 MAX.",
        "5. B1 IS UNTHREADED; A1/C1-C3/D1-D4 ARE BLIND TAPPED.",
        "6. DURING COATING, MASK DATUM A/B/C FACES, ALL BORES/THREADS AND",
        "   PAD TOP; COAT PAD SIDES AND ROOTS.",
    )
)
SIDE_VIEW_NOTE = "FRONT VIEW 1:4"
