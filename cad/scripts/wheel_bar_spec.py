r"""Wheel-bar dimensional contract -- the single source of truth shared by the
part build (``build_wheel_bar.py``) and its manufacturing drawing
(``draw_wheel_bar.py``).

PURE DATA, no SolidWorks/COM imports.  The bar nominals live in the drawing-FREE
``wheel_bar_geom`` module (the assembly imports the depth + clamp stations); they
are re-exported here for the drawing-side consumers and the offline lockstep
test, which asserts the part marks and the drawing keeps EXACTLY
``DRAWING_DIMENSIONS``.
"""

from __future__ import annotations

from wheel_bar_geom import (  # noqa: F401 (re-export)
    BAR_DEPTH,
    BAR_LENGTH,
    BAR_SIDE,
    CLAMP_HOLE_DIA,
    CLAMP_HOLE_FIT,
    CLAMP_HOLE_SIZE,
    CLAMP_HOLE_X,
    PEN_HANGER_HOLE_DIA,
    PEN_HANGER_HOLE_FIT,
    PEN_HANGER_HOLE_SIZE,
    SCREW_HOLE_X,
)

# --- Marked-dimension contract: feature -> the parametric dimension NAMES the
# print shows.  The bar depth (9) is added on the sheet across the right-view
# section; the three bores are native Hole Wizard clearance holes, so their
# sizes are native hole callouts and their stations drawing-native linears from
# the left end -- never fake marked dimensions. ---
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "BarProfile": {"Length", "Side"},
}

# Every hole size and station is on the front view, so the one note is the
# stock licence (cad/docs/drawing-simplicity-policy.md rule 6).
DRAWING_NOTES = f"{BAR_SIDE:.0f} X {BAR_DEPTH:.0f} BAR STOCK FACES OK AS RECEIVED."
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:2"
