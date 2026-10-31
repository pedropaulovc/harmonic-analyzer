r"""Wheel-bar geometry and hanger registration shared by the part builds, their
drawing contracts and the magnifier/pen assemblies. The bar's fixed support
stations and the pen-guide body's photographic placement do not depend on the
hanger fastener station.

PURE PYTHON, no SolidWorks/COM and no drawing imports (the
``column_clamp_front_geom`` precedent): the assembly depends on whatever module
it imports geometry from, so the drawing contract must NOT live here.
"""

from __future__ import annotations

from _hole_spec import HoleSpec, blind_cut_dia_mm
from _printed_tolerance import drilled_oversize_mm, printed_band_mm


# --- bar section + length (DIMENSIONS.md ch21; M6.8 ch30 8-view pass) ----------
# The top face stands BAR_TOP_ABOVE_ROW over the bore row: the pen-hanger
# strap's top is flush with it and the top assembly sets the bar by it. Below
# the row the bar runs to BAR_SIDE: the photographed 10 grew to 11, downward
# (owner ruling 2026-10-24), because at the full worst case a 10 bar leaves
# the walls under the bores below the 1.5 mm floor
# (mg_wheel_bar_spec.BORE_ROW_WALLS; the walls an 11 leaves are owner-ruled
# minors, 2026-10-26, #1532).
BAR_TOP_ABOVE_ROW = 5.0
BAR_SIDE = 11.0  # tall (Y)
# BAR_DEPTH (deep, Z) is the support-bar stock's (_column_clamp_interface);
# the back face seats on the clamp arc.
# The front face in the machine frame: the front clamp arc's front face
# (-129.4) less BAR_DEPTH, the plane the platen's back face shares
# (build_mg_magnifier_assembly asserts it against the clamp chain). The wheel
# axle's press gauge and the axial stack on it read from here (mg_wheel_group).
BAR_FRONT_Z = -138.9
BAR_LENGTH = 234.0  # clamped end 29 past the west column + free end (photo, med)

# --- hole stations (local X; the bores run along Z, the front-back axis) --------
SCREW_HOLE_X = -112.0  # pen-hanger screw hole: 5 mm from the fixed free end
# Clamp-screw holes flanking the column line at +88, on the column clamps'
# .689 ear stations (_clamp_arc.EAR_HOLE_Z, 17.5006).
CLAMP_HOLE_X = (70.4994, 105.5006)
# The print reads every station from the left end (the bar is modelled centred).
LEFT_END_X = -BAR_LENGTH / 2.0
HANGER_STATION = SCREW_HOLE_X - LEFT_END_X  # 5.0
CLAMP_STATIONS = tuple(x - LEFT_END_X for x in CLAMP_HOLE_X)  # (187.4994, 222.5006)

# Fixed photographic registration, shared by the bar placement and hanger tap
# (build_pn_pen_hanger places its strap tap on this machine x).
WHEEL_BAR_X0 = 109.0
WHEEL_BAR_Y = 575.7  # ch30 p002 re-anchor (was 565.0)
HANGER_SCREW_MACHINE_X = WHEEL_BAR_X0 + SCREW_HOLE_X

# Wheel-axle bore: reamed .1865 through at the wheel station; the 3/16
# mg-wheel-axle presses in to a gauge from the front face (mg_wheel_axle_spec),
# its back end near the back face.
WHEEL_X = 53.0  # magnifying-wheel centre, machine x
AXLE_BORE_X = WHEEL_X - WHEEL_BAR_X0  # -56
AXLE_BORE_DIA = round(0.1865 * 25.4, 6)  # 4.7371
AXLE_BORE_BAND = (0.010, 0.0)  # (upper, lower) deviations, reamed
# Printed depth band: with the axle's press gauge and .X shank it places the
# axle's back end on the back face (mg_wheel_axle_spec.BACK_END_PROUD_MAX).
BAR_DEPTH_BAND = (0.10, -0.10)

# All four bores share one row, BAR_TOP_ABOVE_ROW under the top face; this is
# the row's height over the bottom face (the bar's underside below the axle).
BORE_ROW_HEIGHT = BAR_SIDE - BAR_TOP_ABOVE_ROW  # 6.0

# Native Hole Wizard clearance contracts shared by build, drawing, and assemblies.
PEN_HANGER_HOLE_SPEC = HoleSpec("clearance", "#8", fit="close")
PEN_HANGER_HOLE_DIA = blind_cut_dia_mm(PEN_HANGER_HOLE_SPEC)
CLAMP_HOLE_SPEC = HoleSpec("clearance", "#8")
CLAMP_HOLE_DIA = blind_cut_dia_mm(CLAMP_HOLE_SPEC)
DRILLED_HOLE_PLUS = drilled_oversize_mm()

# Finished material remaining between the clearance bore and the free end.
# This is a manufacturing ligament requirement, not a screw tear-out rating.
# The station is dimensioned directly from the finished end, so the overall
# length tolerance does not enter this stack.
PEN_HANGER_MIN_END_WALL = 2.0
# The hanger station prints .XX: the title block's row holds the end wall
# (2.154 worst); at .X it would be 1.864, under the 2.0 target.
PEN_HANGER_STATION_PLACES = 2
PEN_HANGER_STATION_TOL = printed_band_mm(PEN_HANGER_STATION_PLACES)


def require_hanger_end_wall(
    screw_hole_x: float, hole_dia: float, hole_dia_tolerance: float
) -> float:
    """Return nominal ligament; reject a tolerance-minimum wall below 2 mm."""
    nominal = BAR_LENGTH / 2.0 - abs(screw_hole_x) - hole_dia / 2.0
    minimum = nominal - PEN_HANGER_STATION_TOL - hole_dia_tolerance / 2.0
    if minimum < PEN_HANGER_MIN_END_WALL:
        raise AssertionError(
            f"hanger clearance leaves {minimum:.3f} mm minimum bar end wall; "
            f"requires {PEN_HANGER_MIN_END_WALL:.3f} mm"
        )
    return nominal
