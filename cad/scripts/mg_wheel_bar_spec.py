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

import math

from _column_clamp_interface import BAR_DEPTH
from _printed_tolerance import printed_band_mm
from mg_wheel_bar_geom import (  # noqa: F401 (re-export)
    AXLE_BORE_BAND,
    AXLE_BORE_DIA,
    AXLE_BORE_X,
    BAR_DEPTH_BAND,
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

# Height 10 -> 11, grown downward (owner ruling 2026-10-24): at the full worst
# case below, a 10 bar leaves the walls under the bores 0.77-0.93, under the
# 1.5 floor. The height prints at .X under the title block: no mate bounds it.
BAR_SIDE_PLACES = 1
# The bore row reads from the TOP face, the face the pen-hanger strap's top is
# flush with and the top assembly sets the bar by. It prints twice, from each
# end: the hanger hole and the axle bore at the title block's .XX, the clamp
# pair with the taps' band below.
BORE_ROW_FROM_TOP = BAR_TOP_ABOVE_ROW  # 5.0
BORE_ROW_PLACES = 2
# The clamp holes' position band, a fixed-fastener stack as on the support bar
# (build_pd_support_bar.CLAMP_POSITION_BAND): each #8-32 clamp screw stands in
# its MHA-SH-02 back-arc tap (+/-0.1 station and height, sh_column_clamp_fit)
# and passes this bar's #8 clearance hole, whose least size clears the screw
# major by 0.812. A +/-band on a hole's row height and station is a diametral
# zone of 2*sqrt(2)*band; with the taps' 0.283 it must stay inside the 0.812:
# +/-0.18 at .XX (0.509 + 0.283 = 0.792). The clamp row and both clamp
# stations carry it. A literal, so the clamp's geometry stays out of this
# part's recipe (test_mg_wheel_bar_drawing derives it from the clamp's own
# modules). Drill wander is not charged, as on the support bar (#1988).
CLAMP_POSITION_BAND = 0.18
CLAMP_POSITION_PLACES = 2

# drawing-guidelines.md rule 17 (walls and webs), at the FULL worst case:
# - the locating bands: each row at its band from the top face, the stations
#   at theirs from the left end, the bar at its title-block least height;
# - each bore at its largest (DRILLED HOLES +0.10, the reamer's +0.01);
# - 0.3 deg drill run-off over the deepest bar (9.50 +0.1): every hole is
#   drilled or reamed on the mill into faces cut in an earlier setup;
# - the title block's 0.25 edge break on both exposed edges of each wall, the
#   hole's rim and the bar's edge at the face.
# No tap on this bar, so no tap-major term.
WALL_TARGET = 2.0
WALL_FLOOR = 1.5
DRILL_RUNOFF_DEG = 0.3  # the repo allowance (sh_column_clamp_fit.EAR_DRILL_WANDER_DEG)
EDGE_BREAK = 0.25  # title block: BREAK SHARP EDGES R0.25 OR CHAMFER 0.25
BAR_DEPTH_MAX = BAR_DEPTH + BAR_DEPTH_BAND[0]  # 9.6
DRILL_RUNOFF = BAR_DEPTH_MAX * math.tan(math.radians(DRILL_RUNOFF_DEG))  # 0.050
_WALL_LOSSES = DRILL_RUNOFF + 2.0 * EDGE_BREAK
BAR_SIDE_MIN = BAR_SIDE - printed_band_mm(BAR_SIDE_PLACES)  # 10.2
_ROW_BAND = printed_band_mm(BORE_ROW_PLACES)  # 0.51
BORE_BANDS = {
    "axle bore": ((AXLE_BORE_DIA + AXLE_BORE_BAND[0]) / 2.0, _ROW_BAND),
    "hanger hole": ((PEN_HANGER_HOLE_DIA + DRILLED_HOLE_PLUS) / 2.0, _ROW_BAND),
    "clamp holes": ((CLAMP_HOLE_DIA + DRILLED_HOLE_PLUS) / 2.0, CLAMP_POSITION_BAND),
}  # bore -> (largest radius, row band)
BORE_ROW_WALLS = {
    **{
        f"{bore} top": BORE_ROW_FROM_TOP - band - radius - _WALL_LOSSES
        for bore, (radius, band) in BORE_BANDS.items()
    },
    **{
        f"{bore} bottom": BAR_SIDE_MIN
        - BORE_ROW_FROM_TOP
        - band
        - radius
        - _WALL_LOSSES
        for bore, (radius, band) in BORE_BANDS.items()
    },
    "hanger hole end": HANGER_STATION
    - PEN_HANGER_STATION_TOL
    - BORE_BANDS["hanger hole"][0]
    - _WALL_LOSSES,
}  # top 1.566 / 1.604 / 1.731, bottom 1.766 / 1.804 / 1.931, hanger hole end 1.604
for _wall, _value in BORE_ROW_WALLS.items():
    if _value < WALL_FLOOR:
        raise AssertionError(
            f"wheel-bar {_wall} wall {_value:.3f} < {WALL_FLOOR} floor"
        )
# Every wall is under the 2.0 target: owner ruling 2026-10-26 (#1532) accepts
# each as a minor (cad/config/parts/mg-wheel-bar.yaml machinist_exceptions,
# one per wall). The top walls are bound by the interfaces (the strap's top
# flush with the bar top, the row at the axle, wheel and taps' height); the
# sheet states each hole's least wall, floored, on its callout.
WALL_CALLOUT_MIN = {
    bore: math.floor(
        min(value for wall, value in BORE_ROW_WALLS.items() if wall.startswith(bore))
        * 100
    )
    / 100
    for bore in BORE_BANDS
}  # axle bore 1.56, hanger hole 1.60, clamp holes 1.73

# --- Marked-dimension contract: feature -> the parametric dimension NAMES the
# print shows.  The bar depth is the extrude's named depth, banded because it
# places the wheel axle's back end on the back face (mg_wheel_axle_spec).
# The reamed axle bore is a sketch-cut whose diameter (with its reamer band)
# and station from the left end are model dimensions.  The three screw bores
# are native Hole Wizard clearance holes (sizes on their native callouts);
# their stations from the left end and the two rows' drops from the top face
# ride the hidden BoreRowReference sketch, driven by the same equations as the
# Hole Wizard placement points. ---
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "BarProfile": {"Length", "Side"},
    "Bar": {"BarDepth"},
    "AxleBoreProfile": {"AxleBoreDia", "AxleBoreStation"},
    "BoreRowReference": {
        "BoreRowFromTop",
        "ClampRowFromTop",
        "HangerStation",
        "ClampStation1",
        "ClampStation2",
    },
}
# The length and the height print .X; the depth, the rows, the stations and
# the bore station .XX; the reamed bore .XXX.  The hanger station's .XX is the
# title block's row: at .X (+/-0.8) its end wall would fall to 1.86
# (mg_wheel_bar_geom.require_hanger_end_wall).
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "BarProfile": {"Length": 1, "Side": BAR_SIDE_PLACES},
    "Bar": {"BarDepth": 2},
    "AxleBoreProfile": {"AxleBoreDia": 3, "AxleBoreStation": 2},
    "BoreRowReference": {
        "BoreRowFromTop": BORE_ROW_PLACES,
        "ClampRowFromTop": CLAMP_POSITION_PLACES,
        "HangerStation": PEN_HANGER_STATION_PLACES,
        "ClampStation1": CLAMP_POSITION_PLACES,
        "ClampStation2": CLAMP_POSITION_PLACES,
    },
}

ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:2"
