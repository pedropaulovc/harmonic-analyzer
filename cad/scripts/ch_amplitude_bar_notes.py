r"""Amplitude bar (MHA-CH-001) drawing-only data: the marked-dimension and
precision contract, the manufacturing note and the dimension callouts.

Split OUT of ``ch_amplitude_bar_spec`` (the ``ch_rocker_arm_notes`` treatment,
codex #354): the channel kinematics, the rocker-bank layout, the rocker arm
and both pivot pins import the bar's geometry, so drawing data in that import
closure re-keyed them on every sheet edit. Imported ONLY by
``build_ch_amplitude_bar``, ``draw_ch_amplitude_bar`` and the offline tests.
"""

from __future__ import annotations

import math

import ch_amplitude_bar_spec as bar
from _printed_tolerance import printed_band_mm

# Mating parts the callouts name (test_ch_amplitude_bar_drawing pins each to
# the part registry).
TOP_PIN_NUMBER = "MHA-CH-011"  # pressed into the top pin hole
LEVER_NUMBER = "MHA-CH-002"  # the channel lever the top notch straddles
ROCKER_ARM_NUMBER = "MHA-CH-006"  # the rocker arm whose strap the foot notch rides

# --- Drawing contract (drawing-simplicity-policy.md `How the repository
# implements the guidelines`: the PART owns places and bands). ---
# BarProfile (the Front-plane outline): the overall length prints on the 1:4
# front view; each notch's centring ledge, width and depth in the 4:1 detail
# of its end. TopPinProfile (the Right-plane cut sketch): the pin hole, located
# from the bar's top edge, and that edge's length -- the 1/4 in square stock --
# print in the 4:1 right side view of the top end.
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "BarProfile": {
        "BarLength",
        "BottomLeftLedge",
        "BottomNotchHeight",
        "BottomNotchWidth",
        "TopNotchHeight",
        "TopNotchWidth",
        "TopRightLedge",
    },
    "TopPinProfile": {"BarSection", "TopPinX", "TopPinDrop", "TopPinDia"},
}
# Places the part authors on each printed dimension. The hole's offset from the
# back face prints at three places: the .XXX band (+/-0.13) holds the reamed
# hole's walls to both faces at the 2.0 target on the narrowest stock
# (ch_bar_pivot_pin_spec.joint_budget hole_face_wall_min); at .XX it would not.
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "BarProfile": {
        "BarLength": 1,
        "BottomLeftLedge": 2,
        "BottomNotchHeight": 2,
        "BottomNotchWidth": 2,
        "TopNotchHeight": 2,
        "TopNotchWidth": 2,
        "TopRightLedge": 2,
    },
    "TopPinProfile": {
        "BarSection": 2,
        "TopPinX": 3,
        "TopPinDrop": 2,
        "TopPinDia": 3,
    },
}
DRAWING_PRECISION_BY_NAME: dict[str, int] = {
    name: digits
    for names in DRAWING_PRECISION.values()
    for name, digits in names.items()
}
# The section is the stock: printed in parentheses, its band the mill's.
REFERENCE_DIMENSIONS = frozenset({"BarSection"})
if {name for names in DRAWING_DIMENSIONS.values() for name in names} != set(
    DRAWING_PRECISION_BY_NAME
):
    raise AssertionError("every marked bar dimension needs authored places")


def _far_cheek_min(notch_width: float, ledge: float) -> float:
    """The cheek opposite a notch's printed ledge at the worst case: the
    narrowest stock less the widest notch beside the widest ledge, floored to
    the two places it prints at."""
    upper, _lower = bar.NOTCH_WIDTH_BAND
    wall = (
        (bar.BAR_WIDTH - bar.BAR_STOCK_UNDERSIZE)
        - (ledge + bar.NOTCH_OFFSET_TOLERANCE_MM)
        - (notch_width + upper)
    )
    return math.floor(round(wall * 100.0, 9)) / 100.0


# drawing-guidelines.md rule 20: the notch cheeks fall short of the 2.0 wall
# target and the 1.5 floor (#1038; the book's 6.35 bar straddling its 2.5
# rocker arm leaves cheeks under 1.93 nominal). The shortfall is stated at
# each notch's width.
# Pending exception ruling: MHA-CH-001 cheek wall 1.17 MIN (#1293/#1038).
TOP_CHEEK_WALL_MIN = _far_cheek_min(bar.TOP_NOTCH_WIDTH, bar.TOP_NOTCH_OFFSET)
BOTTOM_CHEEK_WALL_MIN = _far_cheek_min(bar.BOTTOM_NOTCH_WIDTH, bar.BOTTOM_NOTCH_OFFSET)


def _pin_hole_wall_min() -> float:
    """The reamed pin hole's wall to the nearer depth face at the worst case:
    its offset at either end of the band its TopPinX places print, the hole
    at its largest, on the narrowest stock; floored to one place. The tight
    location exists for this wall (machinist round 1, #1293: the 3.175 read
    as a three-place size with no function)."""
    location = printed_band_mm(DRAWING_PRECISION["TopPinProfile"]["TopPinX"])
    hole_max = bar.TOP_PIN_HOLE_DIA + bar.TOP_PIN_HOLE_BAND[0]
    near = bar.BAR_DEPTH / 2.0 - location
    far = (bar.BAR_DEPTH - bar.BAR_STOCK_UNDERSIZE) - (bar.BAR_DEPTH / 2.0 + location)
    wall = min(near, far) - hole_max / 2.0
    return math.floor(round(wall * 10.0, 9)) / 10.0


# drawing-guidelines.md rule 17: the hole's wall holds the 2.0 target.
PIN_HOLE_WALL_MIN = _pin_hole_wall_min()
if PIN_HOLE_WALL_MIN < 2.0:
    raise AssertionError("the top pin hole's face wall fell under 2.0")

# "ROOTS R0.40 MAX" is a Main-ruled exception (2026-09-27): it limits the
# cutter's corner at an unmodelled root, so it rides each notch's depth.
ROOT_CALLOUT = "ROOTS R0.40 MAX"
# Each line stays within ~20 characters (~48 mm at the sheet's dimension
# font): the callouts sit between a notch's crop circle and its neighbours.
DIMENSION_CALLOUTS: dict[str, str] = {
    "TopNotchWidth": (
        f"STRADDLES {LEVER_NUMBER}\nCHEEK WALL {TOP_CHEEK_WALL_MIN:.2f} MIN"
    ),
    "BottomNotchWidth": (
        f"RIDES {ROCKER_ARM_NUMBER}\nCHEEK WALL {BOTTOM_CHEEK_WALL_MIN:.2f} MIN"
    ),
    "TopRightLedge": "CENTRES ON LEVER",
    "BottomLeftLedge": "CENTRES ON ROCKER",
    "TopNotchHeight": ROOT_CALLOUT,
    "BottomNotchHeight": ROOT_CALLOUT,
    "TopPinDia": f"THRU, REAM\nPRESS FIT {TOP_PIN_NUMBER}",
    "TopPinX": f"HOLE WALL {PIN_HOLE_WALL_MIN:.1f} MIN",
    "BarSection": "1/4 SQ STOCK",
}
if not set(DIMENSION_CALLOUTS) <= set(DRAWING_PRECISION_BY_NAME):
    raise AssertionError("a callout names a dimension the sheet does not print")

# The one thing no single view states: both notches lie in one plane, cut
# through the full depth (they share one profile sketch, so it IS the model).
# The title-block QTY owns the count and the FINISH field the plating.
DRAWING_NOTES = "1. BOTH END NOTCHES THRU THE FULL DEPTH,\n    IN ONE COMMON PLANE."
