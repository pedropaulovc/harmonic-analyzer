r"""Wheel-bar geometry and hanger registration shared by the part builds, their
drawing contracts and the magnifier/pen assemblies. The bar's fixed support
stations and the pen-guide body's photographic placement do not depend on the
hanger fastener station.

PURE PYTHON, no SolidWorks/COM and no drawing imports (the
``column_clamp_front_geom`` precedent): the assembly depends on whatever module
it imports geometry from, so the drawing contract must NOT live here.
"""

from __future__ import annotations

import _config
from _column_clamp_interface import BAR_FRONT_DEPTH
from _cone_axis_constants import FRAME_FRONT_COLUMN_Z
from frame_column_stations import COLUMN_X
from _hole_spec import HoleSpec, blind_cut_dia_mm
from _inch_wall_limits import WALL_TARGET_MM
from _package_units import drawing_unit
from _printed_tolerance import drilled_oversize_mm, printed_deviations

# #290: the bar's sheet prints decimal inch. The stations and the section's
# top other subsystems read keep their millimetre nominals and print rounded
# (mg_wheel_bar_spec judges every wall at those printed limits).
UNIT = drawing_unit("parts/mg-wheel-bar", _config.parts("mg-wheel-bar"))

# --- bar section + length (DIMENSIONS.md ch21; M6.8 ch30 8-view pass) ----------
# The top face stands BAR_TOP_ABOVE_ROW over the bore row: the pen-hanger
# strap's top is flush with it and the top assembly sets the bar by it. Below
# the row the bar runs to BAR_SIDE: the photographed 10 grew downward (owner
# ruling 2026-10-24) so the walls under the bores hold the floor
# (mg_wheel_bar_spec.BORE_ROW_WALLS); at .43 they meet the .080 target.
BAR_TOP_ABOVE_ROW = 5.0
BAR_SIDE = 10.922  # .43 tall (Y)
# BAR_DEPTH (deep, Z) is the support-bar stock's (_column_clamp_interface);
# the back face seats on the clamp arc.
# The front face in the machine frame: the column-axis plane less the clamp
# interface's BAR_FRONT_DEPTH (-138.9), the plane the platen's back face
# shares (build_mg_magnifier_assembly asserts it against the clamp chain). The
# wheel axle's press gauge and the axial stack on it read from here
# (mg_wheel_group).
BAR_FRONT_Z = FRAME_FRONT_COLUMN_Z - BAR_FRONT_DEPTH
BAR_LENGTH = 234.0  # clamped end 29 past the west column + free end (photo, med)

# --- hole stations (local X; the bores run along Z, the front-back axis) --------
SCREW_HOLE_X = -112.0  # pen-hanger screw hole: 5 mm from the fixed free end
COLUMN_LOCAL_X = 88.0  # the west column's line on the bar
CLAMP_HOLE_X = (70.5, 105.5)  # clamp-screw holes flanking the column line
# The print reads every station from the left end (the bar is modelled centred).
LEFT_END_X = -BAR_LENGTH / 2.0
HANGER_STATION = SCREW_HOLE_X - LEFT_END_X  # 5.0
CLAMP_STATIONS = tuple(x - LEFT_END_X for x in CLAMP_HOLE_X)  # (187.5, 222.5)
# Registration: the bar's column line sits on the west column, shared by the
# bar placement and hanger tap (build_pn_pen_hanger places its strap tap on
# this machine x).
WHEEL_BAR_X0 = COLUMN_X - COLUMN_LOCAL_X  # 109.0
WHEEL_BAR_Y = 575.7  # ch30 p002 re-anchor (was 565.0)
HANGER_SCREW_MACHINE_X = WHEEL_BAR_X0 + SCREW_HOLE_X

# Wheel-axle bore: reamed .1865 through at the wheel station (the owned .1865
# reamer, +.0005/0); the 3/16 mg-wheel-axle presses in to a gauge from the
# front face (mg_wheel_axle_spec), its back end near the back face.
WHEEL_X = 53.0  # magnifying-wheel centre, machine x
AXLE_BORE_X = WHEEL_X - WHEEL_BAR_X0  # -56
AXLE_BORE_DIA = 4.7371  # .1865
AXLE_BORE_BAND = (0.0127, 0.0)  # (upper, lower) deviations: +.0005/0, reamed
AXLE_BORE_PLACES = 4
# Printed depth band (+/-.004 on the .374 the 9.5 mm stock prints): with the
# axle's press gauge and shank it places the axle's back end in the bore
# (mg_wheel_axle_spec.BACK_END_SUNK_MIN / BACK_END_SUNK_MAX).
BAR_DEPTH_BAND = (0.1016, -0.1016)
BAR_DEPTH_PLACES = 3

# All four bores share one row, BAR_TOP_ABOVE_ROW under the top face; this is
# the row's height over the bottom face (the bar's underside below the axle).
BORE_ROW_HEIGHT = BAR_SIDE - BAR_TOP_ABOVE_ROW  # 6.0

# Native Hole Wizard clearance contracts shared by build, drawing, and assemblies.
PEN_HANGER_HOLE_SPEC = HoleSpec("clearance", "#8", fit="close")
PEN_HANGER_HOLE_DIA = blind_cut_dia_mm(PEN_HANGER_HOLE_SPEC)
CLAMP_HOLE_SPEC = HoleSpec("clearance", "#8")
CLAMP_HOLE_DIA = blind_cut_dia_mm(CLAMP_HOLE_SPEC)
DRILLED_HOLE_PLUS = drilled_oversize_mm(unit=UNIT)

# Finished material remaining between the clearance bore and the free end.
# This is a manufacturing ligament requirement, not a screw tear-out rating.
# The station is dimensioned directly from the finished end, so the overall
# length tolerance does not enter this stack.
PEN_HANGER_MIN_END_WALL = WALL_TARGET_MM
# The hanger station (5.0, read by the pen hanger's strap tap) prints .20 at
# the title block's .XX; its least printed station holds the end wall.
PEN_HANGER_STATION_PLACES = 2
PEN_HANGER_STATION_TOL = -printed_deviations(
    HANGER_STATION, PEN_HANGER_STATION_PLACES, unit=UNIT
)[0]


def require_hanger_end_wall(
    screw_hole_x: float, hole_dia: float, hole_dia_tolerance: float
) -> float:
    """Return nominal ligament; reject a tolerance-minimum wall below .080 in."""
    nominal = BAR_LENGTH / 2.0 - abs(screw_hole_x) - hole_dia / 2.0
    minimum = nominal - PEN_HANGER_STATION_TOL - hole_dia_tolerance / 2.0
    if minimum < PEN_HANGER_MIN_END_WALL:
        raise AssertionError(
            f"hanger clearance leaves {minimum:.3f} mm minimum bar end wall; "
            f"requires {PEN_HANGER_MIN_END_WALL:.3f} mm"
        )
    return nominal
