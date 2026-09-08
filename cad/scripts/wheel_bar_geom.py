r"""Wheel-bar geometry and hanger registration shared by the part builds, their
drawing contracts and the magnifier/pen assemblies. The bar's fixed support
stations and the pen-guide body's photographic placement do not depend on the
hanger fastener station.

PURE PYTHON, no SolidWorks/COM and no drawing imports (the
``column_clamp_front_geom`` precedent): the assembly depends on whatever module
it imports geometry from, so the drawing contract must NOT live here.
"""

from __future__ import annotations

# --- bar section + length (DIMENSIONS.md ch21; M6.8 ch30 8-view pass) ----------
BAR_SIDE = 10.0  # tall (Y)
BAR_DEPTH = 9.0  # deep (Z) -- support-bar stock; back face seats on the clamp arc
BAR_LENGTH = 234.0  # clamped end 29 past the west column + free end (photo, med)

# --- hole stations (local X; the bores run along Z, the front-back axis) --------
SCREW_HOLE_X = -112.0  # pen-hanger screw hole: 5 mm from the fixed free end
CLAMP_HOLE_X = (70.5, 105.5)  # clamp-screw holes flanking the column line at +88

# Fixed photographic registration, shared by the bar placement and hanger tap.
# Moving the screw station must not move either the bar or the pen-guide body.
WHEEL_BAR_X0 = 109.0
HANGER_ORIGIN_X = 3.0
HANGER_STRAP_TOP_LEFT_X = -16.0
HANGER_SCREW_MACHINE_X = WHEEL_BAR_X0 + SCREW_HOLE_X
HANGER_SCREW_LOCAL_X = HANGER_SCREW_MACHINE_X - HANGER_ORIGIN_X

# Native Hole Wizard clearance contracts.  Keep the exact cut diameters beside
# the stations so the part and its note-based drawing cannot disagree about
# which clearance fit a machinist must drill.
PEN_HANGER_HOLE_SIZE = "#8"
PEN_HANGER_HOLE_FIT = "close"
PEN_HANGER_HOLE_DIA = 4.572
CLAMP_HOLE_SIZE = "#8"
CLAMP_HOLE_FIT = "normal"
CLAMP_HOLE_DIA = 4.978

# Finished material remaining between the clearance bore and the free end.
# This is a manufacturing ligament requirement, not a screw tear-out rating.
# The station is dimensioned directly from the finished end, so the overall
# length tolerance does not enter this stack.
PEN_HANGER_MIN_END_WALL = 2.0
PEN_HANGER_STATION_TOL = 0.05


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
