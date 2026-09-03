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

from _surface_finish import SurfaceFinishControl
from magnifying_clamp_geom import (  # noqa: F401 (re-export)
    BLOCK_DEPTH,
    BLOCK_HEIGHT,
    BLOCK_WIDTH,
    LEVER_BORE_DIA,
    LEVER_BORE_Y,
    ROD_BORE_DIA,
    ROD_BORE_X,
)

# ANSI #4-40 tap-drill diameter (mirrors ``_holes.TAP_DRILL_MM``; the spec pulls
# in NO COM module, and the offline test pins the two equal).  The drawing
# picks the thumb-screw hole's drawn circle at this radius for its callout.
THUMB_SCREW_TAP_DRILL_DIA = 2.261

# No roughness callouts: the clamp is thumb-screwed to the lever rod in service
# and only slides along it when the magnification is set, so nothing runs on
# either bore -- the title block's Ra 3.2 covers every face
# (cad/docs/drawing-simplicity-policy.md rule 5).
SURFACE_FINISHES: tuple[SurfaceFinishControl, ...] = ()

# --- Marked-dimension contract: feature -> the parametric dimension NAMES the
# print shows.  The rod bore's depth station (RodBoreZ, 6 from the front face)
# locates the common rod-bore / tap centreline through the 12 thickness; the
# lever bore's width station (10 from the side face) is drawing-added on the
# front view (its sketch centre sits on the X axis, so no model dim exists).
# The block depth (12) is added across the right view; the #4-40 thumb-screw
# hole is a native Hole Wizard callout, never a fake marked dimension. ---
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "BlockProfile": {"Width", "Height"},
    "LeverBoreProfile": {"LeverBoreYDim", "LeverBoreDiaDim"},
    "RodBoreProfile": {"RodBoreXDim", "RodBoreZ", "RodBoreDiaDim"},
}

# Notes: the one fact the views cannot show -- what the two bores slip over
# (policy rule 6, a MATES WITH line).  The bore sizes and stations ride the
# dimensions; the tap direction rides its hole callout.
DRAWING_NOTES = "MATES WITH THE Ø6.0 LEVER ROD AND THE Ø5.0 VERTICAL ROD (SLIP FITS)."
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 2:1"
