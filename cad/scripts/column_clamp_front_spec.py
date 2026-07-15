r"""Column-clamp-front dimensional contract -- the single source of truth shared
by the part build (``build_column_clamp_front.py``) and its manufacturing
drawing (``draw_column_clamp_front.py``).

PURE DATA, no SolidWorks/COM imports (the ``<part>_spec.py`` split -- see
``crank_arm_spec.py`` for the pattern rationale).  The geometry itself is cut by
the SHARED semi-arc builder (``_clamp_arc.build_arc``), so the nominals here are
drawing-side mirrors of the builder's constants; the offline lockstep test
(``test_column_clamp_front_drawing.py``) asserts each one equals its
``_clamp_arc`` / ``_holes`` source, so a builder change that isn't mirrored here
fails before any SolidWorks build.
"""

from __future__ import annotations

# --- Nominal geometry (book ch. 21/22, ch30 p005; layout memory/paper-drive-
# rework.md E2).  Mirrors: ARC_DEPTH = build_column_clamp_front.DEPTH; the rest
# = _clamp_arc constants; EAR_HOLE_DIA = the #8-clearance normal-fit table
# diameter (_holes.CLEARANCE_MM). ---
ARC_DEPTH = 17.9  # bar back face to the column-axis plane
ARC_WIDTH = 48.0  # lateral span, ear tip to ear tip
ARC_HEIGHT = 16.0  # along the column (2 * _clamp_arc.ARC_HALF_H)
COLUMN_BORE = 25.6  # half-cylinder relief: slides on the O25.4 column
EAR_HOLE_Z = 17.5  # ear screw line flanks the column
EAR_HOLE_DIA = 4.978  # #8 clearance, normal fit (ANSI-inch wizard table)

# Derived spans (equations of the primitives above).
EAR_SPACING = 2.0 * EAR_HOLE_Z  # 35.0: ear-hole centre to centre
BORE_RADIUS = COLUMN_BORE / 2.0  # 12.8

# --- Marked-dimension contract: feature -> the parametric dimension NAMES the
# print shows.  ``build_column_clamp_front`` marks exactly these;
# ``draw_column_clamp_front`` keeps exactly their union across its per-view
# ``keep`` maps (the offline test enforces ``union(marks) == union(keeps)``).
# The EarHoles feature is a native Hole Wizard cut -- its size is annotated by
# an associative hole callout, never a fake marked dimension. ---
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "BlockProfile": {"Depth", "Width"},
    "BoreProfile": {"BoreDia"},
}

# True free-text instructions only.  Geometry, datum structure,
# form/orientation, and roughness live in native dimensions / datum tags /
# FCFs / surface symbols.  The part build stamps these strings into the SLDPRT;
# the drawing displays only $PRPSHEET links, so the print cannot silently
# diverge from its source model.
DRAWING_NOTES = "\n".join(
    (
        "UOS, DIMENSIONS IN MM: LINEAR +/-0.25; ANGLES +/-0.5 DEG.",
        "HOLE CENTRES +/-0.10; DRILLED DIAMETERS +/-0.10.",
        "DEBURR; BREAK EDGES 0.2 MAX.",
        "GRAY IRON CASTING; MACHINE ALL SURFACES SHOWN.",
        "EAR HOLES: #8 CLEARANCE DRILL THRU, 2 PLACES, AT MID-HEIGHT;",
        "PASS THE #8-32 CLAMP SCREWS (TAPPED IN BACK ARC, MHA-106).",
        "COLUMN RELIEF: FINISH-BORE <MOD-DIAM>25.6 CLAMPED TO BACK ARC",
        "MHA-106 AS A PAIR; SLIP FIT ON THE <MOD-DIAM>25.4 COLUMN.",
        "PAINT BLACK AFTER MACHINING; BORE, BAR FACE",
        "AND EAR HOLES MASKED.",
    )
)
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:1"
