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

# Nominal geometry lives in the drawing-FREE ``column_clamp_front_geom`` module so
# the assemblies can import ``ARC_DEPTH`` without pulling this file's drawing
# contract (notes / marked-dimension map) into their build-recipe closure.
# Re-exported here unchanged for the drawing-side consumers and the lockstep test.
from column_clamp_front_geom import (  # noqa: F401
    ARC_DEPTH,
    ARC_HEIGHT,
    ARC_WIDTH,
    BORE_RADIUS,
    COLUMN_BORE,
    EAR_HOLE_DIA,
    EAR_HOLE_Z,
    EAR_SPACING,
)

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


# Manufacturing GD&T limits consumed by the part's drawing projection.
GEOMETRIC_TOLERANCES_MM: dict[str, str] = {
    "ear-hole position": "0.25",
    "mating-face parallelism": "0.10",
}
