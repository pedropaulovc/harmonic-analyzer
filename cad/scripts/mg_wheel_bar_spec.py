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

from _printed_tolerance import printed_band_mm
from mg_wheel_bar_geom import (  # noqa: F401 (re-export)
    AXLE_BORE_BAND,
    AXLE_BORE_DIA,
    AXLE_BORE_X,
    BAR_LENGTH,
    BAR_SIDE,
    BAR_TOP_ABOVE_ROW,
    CLAMP_HOLE_DIA,
    CLAMP_HOLE_SPEC,
    CLAMP_HOLE_X,
    CLAMP_STATIONS,
    DRILLED_HOLE_PLUS,
    HANGER_STATION,
    LEFT_END_X,
    PEN_HANGER_HOLE_DIA,
    PEN_HANGER_HOLE_SPEC,
    PEN_HANGER_MIN_END_WALL,
    PEN_HANGER_STATION_PLACES,
    PEN_HANGER_STATION_TOL,
    SCREW_HOLE_X,
)

# Bar is modelled centred on the origin along X, so the left end sits at -L/2;
# every hole station reads from that end.
AXLE_BORE_STATION = AXLE_BORE_X - LEFT_END_X  # 61.0

# The height prints at .X under the title block: no mate bounds it.
BAR_SIDE_PLACES = 1
# The bore row reads from the TOP face, the face the pen-hanger strap's top is
# flush with and the top assembly sets the bar by.
BORE_ROW_FROM_TOP = BAR_TOP_ABOVE_ROW  # 5.0
# The clamp holes' position band, a fixed-fastener stack as on the support bar
# (build_pd_support_bar.CLAMP_POSITION_BAND): each #8-32 clamp screw stands in
# its MHA-SH-02 back-arc tap (+/-0.1 station and height, sh_column_clamp_fit)
# and passes this bar's #8 clearance hole, whose least size clears the screw
# major by 0.812. A +/-band on a hole's row height and station is a diametral
# zone of 2*sqrt(2)*band; with the taps' 0.283 it must stay inside the 0.812:
# +/-0.18 at .XX (0.509 + 0.283 = 0.792). The row and both clamp stations
# carry it. A literal, so the clamp's geometry stays out of this part's recipe
# (test_mg_wheel_bar_drawing derives it from the clamp's own modules).
CLAMP_POSITION_BAND = 0.18
CLAMP_POSITION_PLACES = 2

BORE_MIN_WALL = 2.0  # drawing-guidelines.md rule 17 (walls and webs) target, worst case
# Worst wall above and below each bore: the row at its band from the top face,
# the bar at its title-block least height, the bore at its largest.
BAR_SIDE_MIN = BAR_SIDE - printed_band_mm(BAR_SIDE_PLACES)  # 10.2
BORE_MAX_RADII = {
    "axle bore": (AXLE_BORE_DIA + AXLE_BORE_BAND[0]) / 2.0,
    "pen-hanger hole": (PEN_HANGER_HOLE_DIA + DRILLED_HOLE_PLUS) / 2.0,
    "clamp holes": (CLAMP_HOLE_DIA + DRILLED_HOLE_PLUS) / 2.0,
}
BORE_ROW_WALLS = {
    bore: min(
        BORE_ROW_FROM_TOP - CLAMP_POSITION_BAND - radius,
        BAR_SIDE_MIN - BORE_ROW_FROM_TOP - CLAMP_POSITION_BAND - radius,
    )
    for bore, radius in BORE_MAX_RADII.items()
}  # 2.446, 2.484, 2.281: every top wall governs
for _bore, _wall in BORE_ROW_WALLS.items():
    if _wall < BORE_MIN_WALL:
        raise AssertionError(f"wheel-bar {_bore} wall {_wall:.3f} < {BORE_MIN_WALL}")

# --- Marked-dimension contract: feature -> the parametric dimension NAMES the
# print shows.  The bar depth is the extrude's named depth, banded because it
# places the wheel axle's back end on the back face (mg_wheel_axle_spec).
# The reamed axle bore is a sketch-cut whose diameter (with its reamer band)
# and station from the left end are model dimensions.  The three screw bores
# are native Hole Wizard clearance holes (sizes on their native callouts);
# their stations from the left end and the row's drop from the top face
# ride the hidden BoreRowReference sketch, driven by the same equations as the
# Hole Wizard placement points. ---
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "BarProfile": {"Length", "Side"},
    "Bar": {"BarDepth"},
    "AxleBoreProfile": {"AxleBoreDia", "AxleBoreStation"},
    "BoreRowReference": {
        "BoreRowFromTop",
        "HangerStation",
        "ClampStation1",
        "ClampStation2",
    },
}
# The length and the height print .X; the depth, the row, the stations and
# the bore station .XX; the reamed bore .XXX.  The hanger station's .XX is the
# title block's row: at .X (+/-0.8) its end wall would fall to 1.86
# (mg_wheel_bar_geom.require_hanger_end_wall).
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "BarProfile": {"Length": 1, "Side": BAR_SIDE_PLACES},
    "Bar": {"BarDepth": 2},
    "AxleBoreProfile": {"AxleBoreDia": 3, "AxleBoreStation": 2},
    "BoreRowReference": {
        "BoreRowFromTop": CLAMP_POSITION_PLACES,
        "HangerStation": PEN_HANGER_STATION_PLACES,
        "ClampStation1": CLAMP_POSITION_PLACES,
        "ClampStation2": CLAMP_POSITION_PLACES,
    },
}

ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:2"
