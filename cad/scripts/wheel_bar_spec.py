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
# section; the three bores are native Hole Wizard clearance holes, annotated by
# associative callouts + location dims, never fake marked dimensions. ---
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "BarProfile": {"Length", "Side"},
}

# Bar is modelled centred on the origin, so the left end sits at -L/2; the hole
# X-stations are quoted from that end in the notes (computed from the geom
# constants, never duplicated as literals) -- the small clearance-hole circles
# are not dependable associative-callout picks at 1:1, so they ride the notes +
# the front-view centre marks rather than fragile per-hole callouts/location dims.
_LEFT_END = -BAR_LENGTH / 2.0
DRAWING_NOTES = "\n".join(
    (
        "FINISHED BAR SECTION 10 x 9; SPANS ONE COLUMN (CLAMPED END 29 PAST THE",
        "WEST COLUMN LINE, FREE END JUST PAST THE PEN HANGER).",
        "ALL THREE BORES ON THE BAR MID-HEIGHT CENTRELINE, AXES NORMAL TO THE",
        "BACK SEATING FACE (DATUM A); DRILLED THRU FROM THE FRONT FACE.",
        f"2X CLAMP-SCREW {CLAMP_HOLE_SIZE} {CLAMP_HOLE_FIT.upper()} CLEARANCE "
        f"Ø{CLAMP_HOLE_DIA:.3f} HOLES NEAR THE CLAMPED END",
        "(COLUMN-CLAMP SCREWS, MHA-106): HEADS ON THE FRONT FACE.",
        f"1X PEN-HANGER {PEN_HANGER_HOLE_SIZE} {PEN_HANGER_HOLE_FIT.upper()} "
        f"CLEARANCE Ø{PEN_HANGER_HOLE_DIA:.3f} HOLE AT THE FREE END.",
        f"HOLE STATIONS FROM THE LEFT END: #6 AT {SCREW_HOLE_X - _LEFT_END:.1f}; "
        f"#8 PAIR AT {CLAMP_HOLE_X[0] - _LEFT_END:.1f} AND "
        f"{CLAMP_HOLE_X[1] - _LEFT_END:.1f}.",
    )
)
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:2"
