r"""Wheel-bar dimensional contract -- the single source of truth shared by the
part build (``build_mg_wheel_bar.py``) and its manufacturing drawing
(``draw_mg_wheel_bar.py``).

PURE DATA, no SolidWorks/COM imports.  The bar nominals live in the drawing-FREE
``mg_wheel_bar_geom`` module (the assembly imports the depth + clamp stations); they
are re-exported here for the drawing-side consumers and the offline lockstep
test, which asserts the part marks and the drawing keeps EXACTLY
``DRAWING_DIMENSIONS``.
"""

from __future__ import annotations

from mg_wheel_bar_geom import (  # noqa: F401 (re-export)
    AXLE_BORE_BAND,
    AXLE_BORE_DIA,
    AXLE_BORE_X,
    BAR_DEPTH,
    BAR_LENGTH,
    BAR_SIDE,
    CLAMP_HOLE_DIA,
    CLAMP_HOLE_SPEC,
    CLAMP_HOLE_X,
    PEN_HANGER_HOLE_DIA,
    PEN_HANGER_HOLE_SPEC,
    PEN_HANGER_MIN_END_WALL,
    PEN_HANGER_STATION_TOL,
    SCREW_HOLE_X,
)

# Bar is modelled centred on the origin, so the left end sits at -L/2; every
# hole station reads from that end.
_LEFT_END = -BAR_LENGTH / 2.0
AXLE_BORE_STATION = AXLE_BORE_X - _LEFT_END  # 61.0

# --- Marked-dimension contract: feature -> the parametric dimension NAMES the
# print shows.  The bar depth (9) is added on the sheet across the right-view
# section.  The reamed axle bore is a sketch-cut whose diameter (with its
# reamer band) and station from the left end are model dimensions; the three
# screw bores are native Hole Wizard clearance holes, quoted in the notes,
# never fake marked dimensions. ---
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "BarProfile": {"Length", "Side"},
    "AxleBoreProfile": {"AxleBoreDia", "AxleBoreStation"},
}
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "AxleBoreProfile": {"AxleBoreDia": 4, "AxleBoreStation": 2},
}

# The small clearance-hole circles are not dependable associative-callout
# picks at 1:1, so their stations ride the notes (computed from the geom
# constants, never duplicated as literals) + the front-view centre marks.
DRAWING_NOTES = "\n".join(
    (
        "ALL BORES THRU ON THE MID-HEIGHT CENTRELINE, SQUARE TO THE BACK FACE.",
        f"2X {CLAMP_HOLE_SPEC.size} {CLAMP_HOLE_SPEC.fit.upper()} CLEARANCE "
        f"Ø{CLAMP_HOLE_DIA:.3f} FOR THE COLUMN-CLAMP SCREWS (MHA-SH-002).",
        f"1X {PEN_HANGER_HOLE_SPEC.size} {PEN_HANGER_HOLE_SPEC.fit.upper()} "
        f"CLEARANCE Ø{PEN_HANGER_HOLE_DIA:.3f} FOR THE PEN-HANGER SCREW.",
        f"HOLE STATIONS FROM THE LEFT END: HANGER {SCREW_HOLE_X - _LEFT_END:.1f} "
        f"+/-{PEN_HANGER_STATION_TOL:.2f}; CLAMPS "
        f"{CLAMP_HOLE_X[0] - _LEFT_END:.1f} AND {CLAMP_HOLE_X[1] - _LEFT_END:.1f}.",
    )
)
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:2"
