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
import sh_vn_pivot_pin_spec as pin
from _inch_wall_limits import WALL_FLOOR_MM
from _printed_tolerance import printed_band_mm

# Mating parts the callouts name (test_ch_amplitude_bar_drawing pins each to
# the part registry).
TOP_PIN_NUMBER = "MHA-SH-VN-58"  # BarPin member, pressed into the top pin hole
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
# hole at four (the reamer's size, no band). The hole's offset from the back
# face prints at three places: the .XXX band (+/-.005) holds the reamed
# hole's wall to the far face at .078 on the narrowest stock, at the largest
# hole a bonded pin is accepted in (sh_vn_pivot_pin_bar_spec.joint_budget
# hole_face_wall_min, MHA-CH-01 RV-06); at .XX it would fall to .073.
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


# drawing-guidelines.md rule 20: both far cheeks fall short of the .080 wall
# target, and each states its worst case at its notch's width. The top
# notch's (.124 +.010 on the lever, #1038) also falls under the .060 floor:
# owner ruling 2026-10-15 (#1293/#1038) approves it at or above 1.17 mm MIN
# (MHA-CH-01 RV-04). The foot notch's (.104 +.006 on the .098 strap, #3114)
# holds the floor at .063 (MHA-CH-01 RV-05).
TOP_CHEEK_WALL_MIN = _far_cheek_min(
    bar.TOP_NOTCH_WIDTH, bar.TOP_NOTCH_WIDTH_BAND, bar.TOP_NOTCH_OFFSET
)
BOTTOM_CHEEK_WALL_MIN = _far_cheek_min(
    bar.BOTTOM_NOTCH_WIDTH, bar.BOTTOM_NOTCH_WIDTH_BAND, bar.BOTTOM_NOTCH_OFFSET
)
CHEEK_WALL_APPROVED_MIN = {"top": 1.17}
if TOP_CHEEK_WALL_MIN < CHEEK_WALL_APPROVED_MIN["top"]:
    raise AssertionError("the top notch's cheek fell under its approved minimum")
if BOTTOM_CHEEK_WALL_MIN < WALL_FLOOR_MM - 1e-9:
    raise AssertionError("the foot notch's cheek fell under the .060 floor")
# The near cheek is the printed ledge itself. The thinner is the top notch's:
# .063 +/-.002 leaves .061, over the .060 floor and under the .080 target
# (the foot's .073 +/-.002 leaves .071; MHA-CH-01 RV-05).
LEDGE_CHEEK_MIN = min(bar.TOP_NOTCH_OFFSET, bar.BOTTOM_NOTCH_OFFSET) - (
    bar.NOTCH_OFFSET_TOLERANCE_MM
)
if LEDGE_CHEEK_MIN < WALL_FLOOR_MM - 1e-9:
    raise AssertionError("a notch's ledge cheek fell under the .060 floor")


def _pin_hole_wall_min() -> float:
    """The reamed pin hole's wall to the nearer depth face at the worst case:
    its offset at either end of the band its TopPinX places print, the hole
    at the largest a bonded pin is accepted in (sh_vn_pivot_pin_spec.
    BOND_HOLE_MAX), on the narrowest stock; floored to three inch places. The
    tight location exists for this wall (machinist round 1, #1293: the
    three-place location read as a size with no function)."""
    location = printed_band_mm(
        DRAWING_PRECISION["TopPinProfile"]["TopPinX"], unit=bar.UNIT
    )
    hole_max = pin.BOND_HOLE_MAX
    near = bar.BAR_DEPTH / 2.0 - location
    far = (bar.BAR_DEPTH - bar.BAR_STOCK_UNDERSIZE) - (bar.BAR_DEPTH / 2.0 + location)
    wall = min(near, far) - hole_max / 2.0
    return _floor_inch(wall)


# drawing-guidelines.md rule 17: the hole's wall holds the .060 floor; at .078
# it is under the .080 target (MHA-CH-01 RV-06, owner ruling 2026-11-01).
PIN_HOLE_WALL_MIN = _pin_hole_wall_min()
if PIN_HOLE_WALL_MIN < WALL_FLOOR_MM:
    raise AssertionError("the top pin hole's face wall fell under the .060 floor")

# "ROOTS R.015 MAX" is a Main-ruled exception (2026-09-27, R0.40 on the metric
# sheet, rounded down): it limits the cutter's corner at an unmodelled root,
# so it rides each notch's depth.
ROOT_CALLOUT = "ROOTS R.015 MAX"
# Owner ruling 2026-11-24, fit audit question 3: the hole is reamed .0775
# and prints the reamer's size with no band (drawing-guidelines.md rule 4,
# form 3: reamed to the bought mate); the pin itself is the gauge, stated
# once in the numbered sheet note its callout links (rules 4 and 7): it
# presses in, it does not enter by hand. A pin that does enter by hand is
# bonded at MHA-CH-00, not a scrapped bar; no gauge pins.
TOP_PIN_NAME = "BAR PIVOT PIN"
PIN_FIT_NOTE_NUMBER = 1
DRAWING_NOTES = (
    f"{PIN_FIT_NOTE_NUMBER}. PRESS FIT ON {TOP_PIN_NAME} {TOP_PIN_NUMBER}:"
    "\n    THE PIN DOES NOT ENTER BY HAND."
)
# Each line stays within ~21 characters (~55 mm at the sheet's dimension
# font): the callouts sit between a notch's crop circle and its neighbours,
# DETAIL A's west of it beside the full-length view. A location dimension
# (each notch's centring ledge) carries its value and band only; each notch
# names its mate once, on its width, by the standard fit its running floor
# gives (rules 4 and 7; fan-out round 1: STRADDLES and RIDES are not fit
# names), the fit word then the mate's number.
DIMENSION_CALLOUTS: dict[str, str] = {
    "TopNotchWidth": (
        f"RUNNING FIT {LEVER_NUMBER}\n"
        f"CHEEK WALL {inch_text(TOP_CHEEK_WALL_MIN, WALL_PLACES)} MIN"
    ),
    "BottomNotchWidth": (
        f"RUNNING FIT {ROCKER_ARM_NUMBER}\n"
        f"CHEEK WALL {inch_text(BOTTOM_CHEEK_WALL_MIN, WALL_PLACES)} MIN"
    ),
    "TopNotchHeight": ROOT_CALLOUT,
    # One line over its value (a two-line callout above printed nothing, r1).
    "BottomNotchHeight": ROOT_CALLOUT,
    "TopPinDia": (
        f"REAM THRU\nSEE NOTE {PIN_FIT_NOTE_NUMBER}"
    ),
    "TopPinX": f"HOLE WALL {inch_text(PIN_HOLE_WALL_MIN, WALL_PLACES)} MIN",
    "BarSection": "1/4 SQ STOCK",
}
if not set(DIMENSION_CALLOUTS) <= set(DRAWING_PRECISION_BY_NAME):
    raise AssertionError("a callout names a dimension the sheet does not print")

# The one sheet note is the pin hole's matched fit. The title-block QTY owns
# the count, the FINISH field the finish, and the views both notches' depth
# and common plane (machinist round 2, #1293: "BOTH END NOTCHES THRU THE FULL
# DEPTH, IN ONE COMMON PLANE" repeated what the front view and the isometrics
# show).
