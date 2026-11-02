r"""Amplitude bar (MHA-CH-01) drawing-only data: the marked-dimension and
precision contract and the dimension callouts.

Split OUT of ``ch_amplitude_bar_spec`` (the ``ch_rocker_arm_notes`` treatment,
codex #354): the channel kinematics, the rocker-bank layout, the rocker arm
and both pivot pins import the bar's geometry, so drawing data in that import
closure re-keyed them on every sheet edit. Imported ONLY by
``build_ch_amplitude_bar``, ``draw_ch_amplitude_bar`` and the offline tests.
"""

from __future__ import annotations

import math

import ch_amplitude_bar_spec as bar
from _inch_wall_limits import WALL_FLOOR_MM
from _printed_tolerance import printed_band_mm

# Mating parts the callouts name (test_ch_amplitude_bar_drawing pins each to
# the part registry).
TOP_PIN_NUMBER = "MHA-CH-11"  # pressed into the top pin hole
LEVER_NUMBER = "MHA-CH-02"  # the channel lever the top notch straddles
ROCKER_ARM_NUMBER = "MHA-CH-06"  # the rocker arm whose strap the foot notch rides

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
# Places the part authors on each printed dimension, in decimal inch (#290):
# the overall length, the top notch's depth, the pin's drop and the stock
# reference at the title block's .XX; both notch widths, both centring ledges
# and the foot notch's depth at three places with their own bands; the reamed
# hole at four. The hole's offset from the back face prints at three places:
# the .XXX band (+/-.005) holds the reamed hole's wall to the far face at .079
# on the narrowest stock (ch_bar_pivot_pin_spec.joint_budget
# hole_face_wall_min, MHA-CH-01 RV-06); at .XX it would fall to .074.
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "BarProfile": {
        "BarLength": 2,
        "BottomLeftLedge": 3,
        "BottomNotchHeight": 3,
        "BottomNotchWidth": 3,
        "TopNotchHeight": 2,
        "TopNotchWidth": 3,
        "TopRightLedge": 3,
    },
    "TopPinProfile": {
        "BarSection": 2,
        "TopPinX": 3,
        "TopPinDrop": 2,
        "TopPinDia": 4,
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


def inch_text(value_mm: float, places: int) -> str:
    """``value_mm`` as decimal-inch print text: ``.052``."""
    text = f"{value_mm / 25.4:.{places}f}"
    return text[1:] if text.startswith("0.") else text


# Each wall states its worst case at three places, rounded DOWN (in mm).
WALL_PLACES = 3


def _floor_inch(wall: float) -> float:
    """``wall`` (mm) floored to ``WALL_PLACES`` inch places, in mm."""
    scale = 10**WALL_PLACES
    return math.floor(round(wall / 25.4 * scale, 9)) / scale * 25.4


def _far_cheek_min(
    notch_width: float, band: tuple[float, float], ledge: float
) -> float:
    """The cheek opposite a notch's printed ledge at the worst case: the
    narrowest stock less the widest notch beside the widest ledge, floored to
    the three inch places it prints at."""
    upper, _lower = band
    wall = (
        (bar.BAR_WIDTH - bar.BAR_STOCK_UNDERSIZE)
        - (ledge + bar.NOTCH_OFFSET_TOLERANCE_MM)
        - (notch_width + upper)
    )
    return _floor_inch(wall)


# drawing-guidelines.md rule 20: the notch cheeks fall short of the .080 wall
# target and the .060 floor (#1038; the book's 1/4 bar straddling its .098
# rocker arm leaves cheeks under .076 nominal). The shortfall is stated at
# each notch's width (MHA-CH-01 RV-04).
# Owner ruling 2026-10-15 (#1293/#1038): the stated cheek walls are approved
# exceptions at or above 1.17 mm (top) and 1.21 mm (foot) MIN.
TOP_CHEEK_WALL_MIN = _far_cheek_min(
    bar.TOP_NOTCH_WIDTH, bar.TOP_NOTCH_WIDTH_BAND, bar.TOP_NOTCH_OFFSET
)
BOTTOM_CHEEK_WALL_MIN = _far_cheek_min(
    bar.BOTTOM_NOTCH_WIDTH, bar.BOTTOM_NOTCH_WIDTH_BAND, bar.BOTTOM_NOTCH_OFFSET
)
CHEEK_WALL_APPROVED_MIN = {"top": 1.17, "bottom": 1.21}
if (
    TOP_CHEEK_WALL_MIN < CHEEK_WALL_APPROVED_MIN["top"]
    or BOTTOM_CHEEK_WALL_MIN < CHEEK_WALL_APPROVED_MIN["bottom"]
):
    raise AssertionError("a notch cheek fell under its approved minimum")
# The near cheek is the printed ledge itself: .063 +/-.002 leaves .061, over
# the .060 floor and under the .080 target (MHA-CH-01 RV-05).
LEDGE_CHEEK_MIN = min(bar.TOP_NOTCH_OFFSET, bar.BOTTOM_NOTCH_OFFSET) - (
    bar.NOTCH_OFFSET_TOLERANCE_MM
)
if LEDGE_CHEEK_MIN < WALL_FLOOR_MM - 1e-9:
    raise AssertionError("a notch's ledge cheek fell under the .060 floor")


def _pin_hole_wall_min() -> float:
    """The reamed pin hole's wall to the nearer depth face at the worst case:
    its offset at either end of the band its TopPinX places print, the hole
    at its largest, on the narrowest stock; floored to three inch places. The
    tight location exists for this wall (machinist round 1, #1293: the
    three-place location read as a size with no function)."""
    location = printed_band_mm(
        DRAWING_PRECISION["TopPinProfile"]["TopPinX"], unit=bar.UNIT
    )
    hole_max = bar.TOP_PIN_HOLE_DIA + bar.TOP_PIN_HOLE_BAND[0]
    near = bar.BAR_DEPTH / 2.0 - location
    far = (bar.BAR_DEPTH - bar.BAR_STOCK_UNDERSIZE) - (bar.BAR_DEPTH / 2.0 + location)
    wall = min(near, far) - hole_max / 2.0
    return _floor_inch(wall)


# drawing-guidelines.md rule 17: the hole's wall holds the .060 floor; at .079
# it is under the .080 target (MHA-CH-01 RV-06, owner ruling 2026-11-01).
PIN_HOLE_WALL_MIN = _pin_hole_wall_min()
if PIN_HOLE_WALL_MIN < WALL_FLOOR_MM:
    raise AssertionError("the top pin hole's face wall fell under the .060 floor")

# "ROOTS R.015 MAX" is a Main-ruled exception (2026-09-27, R0.40 on the metric
# sheet, rounded down): it limits the cutter's corner at an unmodelled root,
# so it rides each notch's depth.
ROOT_CALLOUT = "ROOTS R.015 MAX"
# Each line stays within ~20 characters (~48 mm at the sheet's dimension
# font): the callouts sit between a notch's crop circle and its neighbours.
DIMENSION_CALLOUTS: dict[str, str] = {
    "TopNotchWidth": (
        f"STRADDLES {LEVER_NUMBER}\n"
        f"CHEEK WALL {inch_text(TOP_CHEEK_WALL_MIN, WALL_PLACES)} MIN"
    ),
    "BottomNotchWidth": (
        f"RIDES {ROCKER_ARM_NUMBER}\n"
        f"CHEEK WALL {inch_text(BOTTOM_CHEEK_WALL_MIN, WALL_PLACES)} MIN"
        f"\n{ROOT_CALLOUT}"
    ),
    "TopRightLedge": "CENTRES ON LEVER",
    "BottomLeftLedge": "CENTRES ON ROCKER",
    "TopNotchHeight": ROOT_CALLOUT,
    # The foot notch's roof seats the bar on the rocker's top edge; its
    # shallow-only band keeps the cheeks off the rocker hub (machinist r5).
    # One line over its value (a two-line callout above printed nothing, r1),
    # so the foot's ROOTS limit rides the width below.
    "BottomNotchHeight": f"SITS ON {ROCKER_ARM_NUMBER}",
    "TopPinDia": f"THRU, REAM\nPRESS FIT {TOP_PIN_NUMBER}",
    "TopPinX": f"HOLE WALL {inch_text(PIN_HOLE_WALL_MIN, WALL_PLACES)} MIN",
    "BarSection": "1/4 SQ STOCK",
}
if not set(DIMENSION_CALLOUTS) <= set(DRAWING_PRECISION_BY_NAME):
    raise AssertionError("a callout names a dimension the sheet does not print")

# No general note: the title-block QTY owns the count, the FINISH field the
# plating, and the views both notches' depth and common plane (machinist
# round 2, #1293: "BOTH END NOTCHES THRU THE FULL DEPTH, IN ONE COMMON PLANE"
# repeated what the front view and the isometrics show).
