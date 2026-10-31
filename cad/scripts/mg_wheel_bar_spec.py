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
from _fit_deviations import deviations
from _inch_wall_limits import WALL_FLOOR_MM, WALL_TARGET_MM
from _printed_tolerance import (
    edge_break_chamfer_mm,
    edge_break_radius_mm,
    printed_deviations,
)
from mg_wheel_bar_geom import (  # noqa: F401 (re-export)
    AXLE_BORE_BAND,
    AXLE_BORE_DIA,
    AXLE_BORE_PLACES,
    AXLE_BORE_X,
    BAR_DEPTH_BAND,
    BAR_DEPTH_PLACES,
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
    UNIT,
)

# Bar is modelled centred on the origin along X, so the left end sits at -L/2;
# every hole station reads from that end.
AXLE_BORE_STATION = AXLE_BORE_X - LEFT_END_X  # 61.0

# Height grown downward from the photographed 10 (owner ruling 2026-10-24).
# It prints .XX: at the title block's .X (+/-.1) the walls under the bores
# would fail the floor.
BAR_SIDE_PLACES = 2
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
# +/-.007 at .XXX (0.503 + 0.283 = 0.786). The clamp row and both clamp
# stations carry it. A literal, so the clamp's geometry stays out of this
# part's recipe (test_mg_wheel_bar_drawing derives it from the clamp's own
# modules). Drill wander is not charged, as on the support bar (#1988).
CLAMP_POSITION_BAND = 0.1778  # .007
CLAMP_POSITION_PLACES = 3

# drawing-guidelines.md rule 17 (walls and webs), at the FULL worst case:
# - the locating bands: each row at its band from the top face, the stations
#   at theirs from the left end, the bar at its title-block least height;
# - each bore at its largest (DRILLED HOLES +.004, the reamer's +.0005);
# - 0.3 deg drill run-off over the deepest bar (its printed depth's maximum):
#   every hole is drilled or reamed on the mill into faces cut in an earlier
#   setup;
# - the title block's edge break on both exposed edges of each wall, the
#   hole's rim and the bar's edge at the face.
# The row and the stations keep millimetre nominals other parts read, so each
# is judged at the limits its rounded inch value prints. No tap on this bar,
# so no tap-major term.
# The run-off term is the repo's 0.3 deg drilling process allowance
# (sh_column_clamp_fit.EAR_DRILL_WANDER_DEG). The title block's general
# ANGULAR +/-1 deg does not govern the drilled-axis squareness of a plain hole
# (owner ruling 2026-10-27, #2000), so it is not charged here.
DRILL_RUNOFF_DEG = 0.3
# The title block's BREAK SHARP EDGES row, its larger of radius and chamfer.
EDGE_BREAK = max(edge_break_radius_mm(unit=UNIT), edge_break_chamfer_mm(unit=UNIT))
BAR_DEPTH_MAX = (
    BAR_DEPTH
    + printed_deviations(
        BAR_DEPTH, BAR_DEPTH_PLACES, deviations(BAR_DEPTH_BAND), unit=UNIT
    )[1]
)
DRILL_RUNOFF = BAR_DEPTH_MAX * math.tan(math.radians(DRILL_RUNOFF_DEG))
_WALL_LOSSES = DRILL_RUNOFF + 2.0 * EDGE_BREAK
BAR_SIDE_MIN = BAR_SIDE + printed_deviations(BAR_SIDE, BAR_SIDE_PLACES, unit=UNIT)[0]
_ROW = printed_deviations(BORE_ROW_FROM_TOP, BORE_ROW_PLACES, unit=UNIT)
_CLAMP_ROW = printed_deviations(
    BORE_ROW_FROM_TOP,
    CLAMP_POSITION_PLACES,
    (-CLAMP_POSITION_BAND, CLAMP_POSITION_BAND),
    unit=UNIT,
)
BORE_BANDS = {
    "axle bore": ((AXLE_BORE_DIA + AXLE_BORE_BAND[0]) / 2.0, _ROW),
    "hanger hole": ((PEN_HANGER_HOLE_DIA + DRILLED_HOLE_PLUS) / 2.0, _ROW),
    "clamp holes": ((CLAMP_HOLE_DIA + DRILLED_HOLE_PLUS) / 2.0, _CLAMP_ROW),
}  # bore -> (largest radius, the row's printed (lower, upper) deviations)
BORE_ROW_WALLS = {
    **{
        f"{bore} top": BORE_ROW_FROM_TOP + low - radius - _WALL_LOSSES
        for bore, (radius, (low, _high)) in BORE_BANDS.items()
    },
    **{
        f"{bore} bottom": BAR_SIDE_MIN
        - (BORE_ROW_FROM_TOP + high)
        - radius
        - _WALL_LOSSES
        for bore, (radius, (_low, high)) in BORE_BANDS.items()
    },
    "hanger hole end": HANGER_STATION
    - PEN_HANGER_STATION_TOL
    - BORE_BANDS["hanger hole"][0]
    - _WALL_LOSSES,
}  # top .0745 / .0760 / .0680, bottom all over .080, hanger hole end .0760 in
for _wall, _value in BORE_ROW_WALLS.items():
    if _value < WALL_FLOOR_MM:
        raise AssertionError(
            f"wheel-bar {_wall} wall {_value / 25.4:.4f} in < .060 floor"
        )
# The top walls and the hanger end wall fall under the .080 target: owner
# ruling 2026-10-26 (#1532) accepts each as a minor
# (cad/config/parts/mg-wheel-bar.yaml machinist_exceptions, one per wall). They
# are bound by the interfaces (the strap's top flush with the bar top, the
# row at the axle, wheel and taps' height, the strap's screw line off the
# free end); the sheet states each hole's least wall, floored to .001 in, on
# its callout.
MINOR_WALLS = {
    wall: value for wall, value in BORE_ROW_WALLS.items() if value < WALL_TARGET_MM
}
WALL_CALLOUT_MIN_IN = {
    bore: math.floor(
        min(value for wall, value in MINOR_WALLS.items() if wall.startswith(bore))
        / 25.4
        * 1000
        + 1e-9
    )
    / 1000
    for bore in BORE_BANDS
}  # axle bore .074, hanger hole .076, clamp holes .068

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
# The length prints .X (no stack reads it); the height, the axle and hanger
# row and the bore and hanger stations .XX; the depth and the clamp row and
# stations .XXX for their bands; the reamed bore .XXXX for its +.0005.
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "BarProfile": {"Length": 1, "Side": BAR_SIDE_PLACES},
    "Bar": {"BarDepth": BAR_DEPTH_PLACES},
    "AxleBoreProfile": {"AxleBoreDia": AXLE_BORE_PLACES, "AxleBoreStation": 2},
    "BoreRowReference": {
        "BoreRowFromTop": BORE_ROW_PLACES,
        "ClampRowFromTop": CLAMP_POSITION_PLACES,
        "HangerStation": PEN_HANGER_STATION_PLACES,
        "ClampStation1": CLAMP_POSITION_PLACES,
        "ClampStation2": CLAMP_POSITION_PLACES,
    },
}

ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:2"
