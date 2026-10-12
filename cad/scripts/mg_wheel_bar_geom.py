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
from _printed_tolerance import printed_band_mm


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

# Wheel-axle bore: reamed .1865 through, on the mid-height line at the wheel
# station; the 3/16 mg-wheel-axle presses in to a gauge from the front face
# (mg_wheel_axle_spec), its back end near the back face.
WHEEL_X = 53.0  # magnifying-wheel centre, machine x
AXLE_BORE_X = WHEEL_X - WHEEL_BAR_X0  # -56
AXLE_BORE_DIA = round(0.1865 * 25.4, 6)  # 4.7371
AXLE_BORE_BAND = (0.010, 0.0)  # (upper, lower) deviations, reamed
# The bore's printed station off the mid-height centreline (bar note 1).
AXLE_BORE_POSITION_TOL = 0.10
# The height is bright square stock as supplied (cold-drawn h11 is 0/-0.09):
# minus-only, because its top limit sets the TIE 1 tail clearance
# (mg_wheel_group) and its bottom the axle-bore wall below.
BAR_SIDE_BAND = (0.0, -0.5)
# Printed depth band: with the axle's press gauge and .X shank it places the
# axle's back end on the back face (mg_wheel_axle_spec.BACK_END_PROUD_MAX).
BAR_DEPTH_BAND = (0.10, -0.10)
AXLE_BORE_MIN_WALL = 2.0  # drawing-simplicity rule 12 target, worst case
# Worst wall above or below the bore: the bar at its thinnest, the bore at its
# largest, shifted by its station tolerance toward one face.
AXLE_BORE_WALL = (
    (BAR_SIDE + BAR_SIDE_BAND[1]) / 2.0
    - AXLE_BORE_POSITION_TOL
    - (AXLE_BORE_DIA + AXLE_BORE_BAND[0]) / 2.0
)  # 2.276
if AXLE_BORE_WALL < AXLE_BORE_MIN_WALL:
    raise AssertionError(f"wheel-bar axle-bore wall {AXLE_BORE_WALL:.3f} < 2.0")

# Native Hole Wizard clearance contracts shared by build, drawing, and assemblies.
PEN_HANGER_HOLE_SPEC = HoleSpec("clearance", "#8", fit="close")
PEN_HANGER_HOLE_DIA = blind_cut_dia_mm(PEN_HANGER_HOLE_SPEC)
CLAMP_HOLE_SPEC = HoleSpec("clearance", "#8")
CLAMP_HOLE_DIA = blind_cut_dia_mm(CLAMP_HOLE_SPEC)

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
