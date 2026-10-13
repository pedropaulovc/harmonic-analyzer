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
BAR_SIDE = 10.0  # tall (Y)
BAR_DEPTH = 9.0  # deep (Z) -- support-bar stock; back face seats on the clamp arc
BAR_LENGTH = 234.0  # clamped end 29 past the west column + free end (photo, med)

# --- hole stations (local X; the bores run along Z, the front-back axis) --------
SCREW_HOLE_X = -112.0  # pen-hanger screw hole: 5 mm from the fixed free end
CLAMP_HOLE_X = (70.5, 105.5)  # clamp-screw holes flanking the column line at +88
# The print reads every station from the left end (the bar is modelled centred).
LEFT_END_X = -BAR_LENGTH / 2.0
HANGER_STATION = SCREW_HOLE_X - LEFT_END_X  # 5.0
CLAMP_STATIONS = tuple(x - LEFT_END_X for x in CLAMP_HOLE_X)  # (187.5, 222.5)
CLAMP_STATION_PLACES = 1

# Fixed photographic registration, shared by the bar placement and hanger tap.
# Moving the screw station must not move either the bar or the pen-guide body.
WHEEL_BAR_X0 = 109.0
HANGER_ORIGIN_X = 3.0
HANGER_STRAP_TOP_LEFT_X = -16.0
HANGER_SCREW_MACHINE_X = WHEEL_BAR_X0 + SCREW_HOLE_X
HANGER_SCREW_LOCAL_X = HANGER_SCREW_MACHINE_X - HANGER_ORIGIN_X

# Wheel-axle bore: reamed .1865 through at the wheel station; the 3/16
# mg-wheel-axle presses in to a gauge from the front face (mg_wheel_axle_spec),
# its back end near the back face.
WHEEL_X = 53.0  # magnifying-wheel centre, machine x
AXLE_BORE_X = WHEEL_X - WHEEL_BAR_X0  # -56
AXLE_BORE_DIA = round(0.1865 * 25.4, 6)  # 4.7371
AXLE_BORE_BAND = (0.010, 0.0)  # (upper, lower) deviations, reamed
# The height is bright square stock as supplied (cold-drawn h11 is 0/-0.09):
# minus-only. Its top limit sets the TIE 1 tail clearance (mg_wheel_group); its
# bottom limit sets the walls over the bore row, which the print reads from the
# bottom face, so the whole band lands on the top wall. At -0.5 the clamp holes'
# top wall fell to 1.861; -0.3 holds 2.061.
BAR_SIDE_BAND = (0.0, -0.3)
# Printed depth band: with the axle's press gauge and .X shank it places the
# axle's back end on the back face (mg_wheel_axle_spec.BACK_END_PROUD_MAX).
BAR_DEPTH_BAND = (0.10, -0.10)

# All four bores share one row at mid-height. No long face seats on a mating
# part (the back face seats on the clamp arc), so the print reads the row from
# the bottom face, with an explicit band.
BORE_ROW_HEIGHT = BAR_SIDE / 2.0  # 5.0
BORE_ROW_HEIGHT_TOL = 0.10
BORE_ROW_HEIGHT_PLACES = 2
# The bar's faces from the row at their worst: the far face sets the TIE 1
# tail clearance (mg_wheel_group), the near face the walls below.
BORE_ROW_FAR_FACE = (
    max(BORE_ROW_HEIGHT, BAR_SIDE + BAR_SIDE_BAND[0] - BORE_ROW_HEIGHT)
    + BORE_ROW_HEIGHT_TOL
)  # 5.10
BORE_ROW_NEAR_FACE = (
    min(BORE_ROW_HEIGHT, BAR_SIDE + BAR_SIDE_BAND[1] - BORE_ROW_HEIGHT)
    - BORE_ROW_HEIGHT_TOL
)  # 4.60

# Native Hole Wizard clearance contracts shared by build, drawing, and assemblies.
PEN_HANGER_HOLE_SPEC = HoleSpec("clearance", "#8", fit="close")
PEN_HANGER_HOLE_DIA = blind_cut_dia_mm(PEN_HANGER_HOLE_SPEC)
CLAMP_HOLE_SPEC = HoleSpec("clearance", "#8")
CLAMP_HOLE_DIA = blind_cut_dia_mm(CLAMP_HOLE_SPEC)
DRILLED_HOLE_PLUS = drilled_oversize_mm()

BORE_MIN_WALL = 2.0  # drawing-guidelines.md rule 17 (walls and webs) target, worst case
# Worst wall above or below each bore: the bar at its thinnest, the row at its
# band, the bore at its largest.
BORE_ROW_WALLS = {
    "axle bore": BORE_ROW_NEAR_FACE - (AXLE_BORE_DIA + AXLE_BORE_BAND[0]) / 2.0,
    "pen-hanger hole": BORE_ROW_NEAR_FACE
    - (PEN_HANGER_HOLE_DIA + DRILLED_HOLE_PLUS) / 2.0,
    "clamp holes": BORE_ROW_NEAR_FACE - (CLAMP_HOLE_DIA + DRILLED_HOLE_PLUS) / 2.0,
}  # 2.226, 2.264, 2.061
for _bore, _wall in BORE_ROW_WALLS.items():
    if _wall < BORE_MIN_WALL:
        raise AssertionError(f"wheel-bar {_bore} wall {_wall:.3f} < {BORE_MIN_WALL}")

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
