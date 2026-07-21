r"""Magnifying-clamp dimensional contract -- the single source of truth shared by
the part build (``build_magnifying_clamp.py``) and its manufacturing drawing
(``draw_magnifying_clamp.py``).

PURE DATA, no SolidWorks/COM imports.  The block/bore nominals live in the
drawing-FREE ``magnifying_clamp_geom`` module (the assembly imports them); they
are re-exported here for the drawing-side consumers and the offline lockstep
test, which asserts the part marks and the drawing keeps EXACTLY
``DRAWING_DIMENSIONS``.
"""

from __future__ import annotations

from magnifying_clamp_geom import (  # noqa: F401 (re-export)
    BLOCK_DEPTH,
    BLOCK_HEIGHT,
    BLOCK_WIDTH,
    LEVER_BORE_DIA,
    LEVER_BORE_Y,
    ROD_BORE_DIA,
    ROD_BORE_X,
)

# --- Marked-dimension contract: feature -> the parametric dimension NAMES the
# print shows.  The block depth (12) is added on the sheet across the right-view
# section; the #4-40 thumb-screw hole is a native Hole Wizard callout, never a
# fake marked dimension. ---
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "BlockProfile": {"Width", "Height"},
    "LeverBoreProfile": {"LeverBoreYDim", "LeverBoreDiaDim"},
    "RodBoreProfile": {"RodBoreXDim", "RodBoreDiaDim"},
}

DRAWING_NOTES = "\n".join(
    (
        "LEVER BORE Ø6.2 THRU (ALONG DEPTH), ON THE BLOCK VERTICAL CENTRELINE",
        "(CENTRED IN THE 20.00 WIDTH): SLIP FIT ON THE Ø6 MAGNIFYING LEVER.",
        "ROD BORE Ø5.2 THRU (VERTICAL), SKEW 6.5 FROM THE LEVER BORE SO THE",
        "TWO RODS PASS WITHOUT TOUCHING: SLIP FIT ON THE Ø5 VERTICAL ROD.",
        "THUMB-SCREW HOLE #4-40 UNC-2B, TAPPED FROM THE TOP FACE, BREAKING",
        "INTO THE LEVER BORE (FULL THREADS TO THE BORE); THE SCREW CLAMPS",
        "THE BLOCK AT THE SET MAGNIFICATION.",
    )
)
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 2:1"
