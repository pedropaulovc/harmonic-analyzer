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
    BAR_LENGTH,
    BAR_SIDE,
    BORE_MIN_WALL,
    BORE_ROW_HEIGHT,
    BORE_ROW_HEIGHT_PLACES,
    BORE_ROW_HEIGHT_TOL,
    CLAMP_HOLE_DIA,
    CLAMP_HOLE_SPEC,
    CLAMP_HOLE_X,
    CLAMP_STATION_PLACES,
    CLAMP_STATIONS,
    HANGER_STATION,
    LEFT_END_X,
    PEN_HANGER_HOLE_DIA,
    PEN_HANGER_HOLE_SPEC,
    PEN_HANGER_MIN_END_WALL,
    PEN_HANGER_STATION_PLACES,
    PEN_HANGER_STATION_TOL,
    SCREW_HOLE_X,
)

# Bar is modelled centred on the origin, so the left end sits at -L/2; every
# hole station reads from that end.
AXLE_BORE_STATION = AXLE_BORE_X - LEFT_END_X  # 61.0

# --- Marked-dimension contract: feature -> the parametric dimension NAMES the
# print shows.  The bar depth is the extrude's named depth, banded because it
# places the wheel axle's back end on the back face (mg_wheel_axle_spec).
# The reamed axle bore is a sketch-cut whose diameter (with its reamer band)
# and station from the left end are model dimensions.  The three screw bores
# are native Hole Wizard clearance holes (sizes on their native callouts);
# their stations from the left end and the row's height from the bottom face
# ride the hidden BoreRowReference sketch, driven by the same equations as the
# Hole Wizard placement points. ---
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "BarProfile": {"Length", "Side"},
    "Bar": {"BarDepth"},
    "AxleBoreProfile": {"AxleBoreDia", "AxleBoreStation"},
    "BoreRowReference": {
        "BoreRowHeight",
        "HangerStation",
        "ClampStation1",
        "ClampStation2",
    },
}
# The length, the height and the clamp stations print .X; the depth, the
# row height and the bore station .XX; the reamed bore .XXX.  The hanger
# station keeps .XX: at .X (+/-0.8) its end wall falls to 1.86
# (mg_wheel_bar_geom.require_hanger_end_wall), so its callout states the wall.
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "BarProfile": {"Length": 1, "Side": 1},
    "Bar": {"BarDepth": 2},
    "AxleBoreProfile": {"AxleBoreDia": 3, "AxleBoreStation": 2},
    "BoreRowReference": {
        "BoreRowHeight": BORE_ROW_HEIGHT_PLACES,
        "HangerStation": PEN_HANGER_STATION_PLACES,
        "ClampStation1": CLAMP_STATION_PLACES,
        "ClampStation2": CLAMP_STATION_PLACES,
    },
}

# Instructions only: every size, station and band is a model dimension or a
# native hole callout on the sheet.
DRAWING_NOTES = "\n".join(
    (
        "ALL BORES THRU, SQUARE TO THE BACK FACE.",
        f"2X {CLAMP_HOLE_SPEC.size} {CLAMP_HOLE_SPEC.fit.upper()} CLEARANCE "
        "FOR COLUMN-CLAMP SCREWS (MHA-SH-02).",
        f"1X {PEN_HANGER_HOLE_SPEC.size} {PEN_HANGER_HOLE_SPEC.fit.upper()} "
        "CLEARANCE FOR THE PEN-HANGER SCREW.",
    )
)
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:2"
