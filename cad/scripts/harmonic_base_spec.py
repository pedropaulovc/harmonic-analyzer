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

# --- Two-plate welded base (book ch. 6), centred on the part origin. ---
BOTTOM_LENGTH = 18.0 * MM_PER_IN  # 457.2 (46 cm callout)
FORMER_BOTTOM_WIDTH = 11.0 * MM_PER_IN  # 279.4 (28 cm callout)
BOTTOM_FRONT_Z = -FORMER_BOTTOM_WIDTH / 2.0
BOTTOM_REAR_Z = FORMER_BOTTOM_WIDTH / 2.0
BOTTOM_WIDTH = BOTTOM_REAR_Z - BOTTOM_FRONT_Z
BOTTOM_CENTER_Z = (BOTTOM_FRONT_Z + BOTTOM_REAR_Z) / 2.0
BOTTOM_THICKNESS = 0.5 * MM_PER_IN  # 12.7
TOP_LENGTH = 17.5 * MM_PER_IN  # 444.5 (0.25 in reveal per side)
FORMER_TOP_WIDTH = 10.5 * MM_PER_IN  # 266.7
TOP_FRONT_Z = -FORMER_TOP_WIDTH / 2.0
TOP_REAR_Z = FORMER_TOP_WIDTH / 2.0
TOP_WIDTH = TOP_REAR_Z - TOP_FRONT_Z
TOP_CENTER_Z = (TOP_FRONT_Z + TOP_REAR_Z) / 2.0
TOP_THICKNESS = 1.5 * MM_PER_IN  # 38.1
STACK_HEIGHT = BOTTOM_THICKNESS + TOP_THICKNESS  # 50.8

if abs(BOTTOM_CENTER_Z) > 1e-12 or abs(TOP_CENTER_Z) > 1e-12:
    raise AssertionError("base plates are not centred")

# --- Marked-dimension contract: feature -> the parametric dimension NAMES the
# print shows. ``build_harmonic_base`` marks exactly these; ``draw_harmonic_base``
# keeps exactly their union. Only the BOTTOM plate's plan footprint is a marked
# sketch dimension -- it is the overall envelope; the top plate is fixed by the
# side reveal note (note 2), and the plate THICKNESSES are
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
        "2. UPPER PAD 444.50 X 266.70;",
        "   NEAR LONG SIDE 6.35 +/-0.10 FROM B;",
        "   NEAR LEFT END 6.35 +/-0.10 FROM C.",
        "3. DATUM A = UNDERSIDE FACE; B = LONG-SIDE FACE; C = LEFT-END FACE;",
        "   HOLE-TABLE ORIGIN = B-C. LOCATIONS ARE BASIC.",
        "4. FOUR DIA 13.00 THRU / DIA 23.00 X 6.50 DEEP C'BORES OPEN FROM",
        "   UNDERSIDE. PLAN RIMS AT E1-E4 ARE THE DIA 13.00 THRU FEATURES.",
        "   C'BORE AND THRU-HOLE AXES: LEAST-SQUARES CYLINDER FITS OVER",
        "   FULL SURFACES; SEPARATION AT C'BORE MOUTH/BOTTOM: 0.05 MAX.",
        "5. A1/B1/C1-C3/D1-D4 ARE BLIND TAPPED.",
        "6. DURING COATING, MASK DATUM A/B/C FACES AND ALL BORES/THREADS;",
        "   COAT PAD SIDES, ROOTS AND RIM. DECK INSIDE THE RIM: BLACK",
        "   ENAMEL, SAME SYSTEM AND DFT AS THE FINISH CALLOUT.",
        "7. VERTICAL PLAN CORNERS: FLANGE R22.22, PAD AND RIM R15.88",
        "   (CONCENTRIC), RIM INNER CORNERS R8.88, ALL FULL HEIGHT.",
        "   FLANGE TOP RIM, RIM TOP AND UNDERSIDE RIM C1.59 X 45 DEG.",
        "8. RAISED RIM 7.00 WIDE X 2.50 HIGH ROUND THE PAD TOP, OUTER FACES",
        "   FLUSH WITH THE PAD SIDES AND CORNER FLATS; DECK STAYS AT 50.80.",
    )
)
SIDE_VIEW_NOTE = "FRONT VIEW 1:4"


# Manufacturing GD&T limits consumed by the part's drawing projection.
GEOMETRIC_TOLERANCES_MM: dict[str, str] = {
    "through-hole true position": "0.20",
    "tapped-hole true position": "0.50",
    "datum B perpendicularity to A": "0.10",
    "datum C perpendicularity to A and B": "0.10",
    "top-pad parallelism to A": "0.10",
}
