r"""Channel-lever drawing data -- the marked-dimension contract, the decimal
places the part authors on each printed dimension, the isometric label and
the two bar-to-hub root corners' printed limit.

Kept OUT of ``ch_channel_lever_spec``: assemblies and the error budget import
the spec for geometry, so drawing-only data living there would re-key
``assembly:ch_channel`` on every print edit.  Imported only by
``build_ch_channel_lever`` (which marks, places and stamps them), the drawing
and its offline test.
"""

from __future__ import annotations

import math

from _milled_corner_limit import (
    CORNER_PLACES,
    CORNER_R,
    CORNER_REASON,
    corner_prefix,
    corner_r_limits,
    line_circle_fillet_area,
)
from ch_channel_lever_spec import BAR_TALL, HUB_DIA, LEVER_THICKNESS, UNIT

# The two inside corners where the bar's straight edges run into the hub
# (the roots). Nothing seats in them: they are the outline cutter's own
# radius over the plate's thickness. Owner ruling 2026-11-23, tool audit Q9:
# "Print a local corner limit R.065 (.060-.070), cut with the 1/8 end mill;
# no 5/64 cutter" (_milled_corner_limit). The sheet prints 2X R.065 at the
# title block's .XXX, naming why it stands over INSIDE CORNERS R.040 MAX;
# the model carries the nominal as the RootCorners fillet. Kept here, not in
# the spec, so the limit re-keys only this part and its sheet.
ROOT_CORNER_R = CORNER_R  # .065
ROOT_CORNER_R_MIN, ROOT_CORNER_R_MAX = corner_r_limits(unit=UNIT)  # .060, .070
ROOT_CORNER_PREFIX = corner_prefix(2)
ROOT_CORNER_REASON = CORNER_REASON
# Each corner's fillet edge: where the bar's edge (|y| = BAR_TALL / 2, over
# the plate's thickness) meets the hub's round.
_HUB_R = HUB_DIA / 2.0
_HALF_BAR = BAR_TALL / 2.0
ROOT_CORNER_X = math.sqrt(_HUB_R**2 - _HALF_BAR**2)


def root_corner_volume(radius: float) -> float:
    """Metal both root corners add over the plate's thickness at ``radius``."""
    return 2.0 * line_circle_fillet_area(radius, _HUB_R, _HALF_BAR) * LEVER_THICKNESS


def root_corner_extent(radius: float) -> tuple[float, float]:
    """(x, |y|) reach of a root corner's metal from the fulcrum axis: its
    tangent point on the bar's edge stands furthest along the bar, its
    tangent point on the hub highest above the bar's centre line."""
    reach = _HUB_R + radius
    centre_x = math.sqrt(reach**2 - (_HALF_BAR + radius) ** 2)
    return centre_x, (_HALF_BAR + radius) * _HUB_R / reach


# At the printed greatest, R.070, each corner stays under the hub's top and
# short of its side: the hub's .48 still reads across its round with the
# calipers, and the corner metal lies inside the square the hub already
# fills in plan, in the plate's own thickness (nothing of a neighbour's lies
# there: the hubs between the plates, the keepers outboard of the end hubs).
ROOT_CORNER_REACH_X, ROOT_CORNER_REACH_Y = root_corner_extent(ROOT_CORNER_R_MAX)
ROOT_CORNER_HUB_TOP_MARGIN = _HUB_R - ROOT_CORNER_REACH_Y
if not (ROOT_CORNER_REACH_X < _HUB_R and ROOT_CORNER_HUB_TOP_MARGIN > 0.0):
    raise AssertionError("a root corner stands outside the hub's square at R.070")
# The bar's section at the root is its full depth at every radius in the
# band (a corner only adds metal there); the corner's metal on its bisector
# (the corner's air side runs ROOT_CORNER_ANGLE_DEG from the bar's edge to
# the hub's round) at the band's least, against the sharp corner the title
# block's R.040 MAX allowed, is what the root gains.
ROOT_CORNER_ANGLE_DEG = math.degrees(math.pi / 2.0 + math.atan2(_HALF_BAR, ROOT_CORNER_X))


def root_bisector_metal(radius: float) -> float:
    """Metal a root corner of ``radius`` stands on the corner's bisector."""
    tangent = (-_HALF_BAR / _HUB_R, ROOT_CORNER_X / _HUB_R)  # the hub's round
    bx, by = 1.0 + tangent[0], tangent[1]
    norm = math.hypot(bx, by)
    bx, by = bx / norm, by / norm
    reach = _HUB_R + radius
    cx = math.sqrt(reach**2 - (_HALF_BAR + radius) ** 2)
    fx, fy = ROOT_CORNER_X - cx, _HALF_BAR - (_HALF_BAR + radius)
    b = fx * bx + fy * by
    return -b - math.sqrt(b * b - (fx * fx + fy * fy - radius * radius))


# Every size, location and band prints from its native model dimension, and
# each tight band names its mate or function on its own callout
# (drawing-guidelines.md rules 4 and 7), so the sheet needs no note.
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    # Full-depth bar to the taper start, tapering to a full-round tip about
    # the spring hole.
    "LeverOutline": {"BarHeight", "TaperStartX", "TipRadius"},
    "LeverBody": {"LeverThick"},
    "HubProfile": {"HubDia"},
    "Hub": {"HubLength"},
    # The plate's near face from the hub face the levers stack on: a hidden
    # reference line (no metal) from the hub face to the plate face.
    "PlateOffsetReference": {"PlateOffset"},
    "FulcrumProfile": {"FulcrumDia"},
    # Both arms from the fulcrum bore (the part origin): the Hole Wizard
    # placement dimensions themselves.
    "BarPinHole": {"BarPinCx"},
    "SpringHole": {"SpringCx"},
    # One root corner stands for both (ROOT_CORNER_PREFIX).
    "RootCorners": {"RootCornerR"},
}

# Decimal places ARE the tolerance statement (drawing-simplicity-policy.md),
# in inches: two on the milled bar height, the taper start and the turned hub
# (the walls read them), three on the tip radius (at two the spring-hole wall
# falls under the target; the sheet states the wall it holds), the plate, the plate offset, the hub length (the
# station pitch's .300), both lever arms and the root corners (.060-.070),
# and the F-drilled fulcrum bore (the drill's .257; DRILLED HOLES row).
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "LeverOutline": {"BarHeight": 2, "TaperStartX": 2, "TipRadius": 3},
    "LeverBody": {"LeverThick": 3},
    "HubProfile": {"HubDia": 2},
    "Hub": {"HubLength": 3},
    "PlateOffsetReference": {"PlateOffset": 3},
    "FulcrumProfile": {"FulcrumDia": 3},
    "BarPinHole": {"BarPinCx": 3},
    "SpringHole": {"SpringCx": 3},
    "RootCorners": {"RootCornerR": CORNER_PLACES},
}
DRAWING_PRECISION_BY_NAME: dict[str, int] = {
    name: places
    for dimensions in DRAWING_PRECISION.values()
    for name, places in dimensions.items()
}
if set(DRAWING_PRECISION_BY_NAME) != set().union(*DRAWING_DIMENSIONS.values()):
    raise AssertionError("every marked dimension must state its decimal places")

ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:2"
