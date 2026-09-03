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

# The relief slips on the O25.4 column: it may run over its 25.6 nominal but
# never under (the title block's .X row would let it read 24.8).  (upper,
# lower) deviations, applied to the model dimension by
# build_column_clamp_front after the shared builder's gated save.
COLUMN_BORE_BAND = (0.05, 0.00)

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

# The face the platen bar's back sits on, flagged from the view: the title
# block's finish field masks it, so the print has to say which face it is.
BAR_FACE_FLAG = "BAR FACE"

# Notes: part-specific process facts only, never a tolerance, never the
# title block (drawing-simplicity-policy.md rule 6).  Material, machining
# and paint/masking live in the title block.
DRAWING_NOTES = "BORE THE COLUMN RELIEF CLAMPED TO ITS BACK ARC AS A PAIR (MATES WITH MHA-106)."
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:1"
