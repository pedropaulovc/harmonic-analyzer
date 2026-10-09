r"""Bar pivot pin (MHA-CH-011) and the amplitude-bar-to-channel-lever joint it
closes.

PURE DATA, no SolidWorks/COM imports (see ``dt_crank_arm_spec`` for the
pattern). The part build (``build_ch_bar_pivot_pin.py``), its drawing, the
channel assembly and ``test_ch_bar_pivot_fit`` import it; it reads only the
two parts it joins, so the pin never re-keys on bank layout or config.

The joint: each amplitude bar's top notch (``ch_amplitude_bar_spec``)
straddles its channel lever (``ch_channel_lever_spec``) at the lever's
bar-pin station, and one plain 5/64 drill-rod pin runs through both notch
cheeks and the lever's #47 bar-pin hole. The pin RUNS in the lever (the one
moving member) and is PRESSED into holes reamed through both cheeks, its ends
dressed flush with the bar's faces: the bar-to-bar side gap leaves no room
for anything proud (issue #1038). Press-fit retention is the user's choice
(2026-10): the #746 rod-fork joint peens its pin into countersinks, but the
bar's 1.575 cheeks leave no bearing land under a countersink, and a pressed
pin drives out with a punch.

Frame (part): pin axis = part Z, axial mid-plane = Front Plane (z = 0); the
model is the INSTALLED pin -- a Ø PIN_DIA cylinder BAR_WIDTH long, flush with
both bar faces. The shop cuts the blank PIN_BLANK_LENGTH long; the drawing
states that.
"""

from __future__ import annotations

import math

import ch_amplitude_bar_spec as _bar
import ch_channel_lever_spec as _lever
from _hole_spec import NUMBER_DRILL_MM

MM_PER_IN = 25.4

# --- Title-block drilled-hole band, restated (test_ch_bar_pivot_fit pins it to
# title_block.yaml): a twist drill cuts on-size to oversize. ---
DRILLED_PLUS = 0.10

# --- The pin: 5/64 drill rod (AISI O1/W1, used annealed as supplied; ground
# to +/-0.0002 in). ---
PIN_DIA = 5.0 / 64.0 * MM_PER_IN  # 1.984
PIN_DIA_TOLERANCE = 0.005  # +/-, drill-rod grind
PIN_INSTALLED_LENGTH = _bar.BAR_WIDTH  # dressed flush with both bar faces
# Cut length of the blank: the bar plus dressing stock at each end. 2-place,
# printed on the pin sheet with its band.
PIN_BLANK_LENGTH = 6.60
PIN_BLANK_LENGTH_BAND = (0.13, -0.13)  # (upper, lower) deviations
# Dressed ends stand nothing proud of the bar faces: the top-notch stack
# below leaves 0.1065 against the 0.10 running floor (#1038).
PIN_END_PROUD_MAX = 0.0

# --- The bar's reamed press hole (the bar spec owns it; restated here so the
# budget reads one place). ---
BAR_HOLE_DIA = _bar.TOP_PIN_HOLE_DIA
BAR_HOLE_BAND = _bar.TOP_PIN_HOLE_BAND
# 1/4 in cold-finished square bar: ASTM A108/A29 size tolerance +0/-0.002 in.
# The bar's width is never printed (it is the stock), so the stock band, not
# the title block's .XX, bounds it.
BAR_STOCK_UNDERSIZE = 0.002 * MM_PER_IN  # 0.051

# --- The joint's limits (the budget test_ch_bar_pivot_fit holds). ---
# The tightest press the cheeks take: ANSI B4.1-1967 (R1987) FN2 "medium
# drive fit, suitable for ordinary steel parts", nominal size 0-0.12 in:
# interference 0.2-0.85 thousandths of an inch. Its 0.85 thou maximum caps the
# press; the minimum only has to stay positive (the pin carries no axial load:
# the lever bears on it radially and the bar cheeks hold it square).
PRESS_INTERFERENCE_MAX = 0.00085 * MM_PER_IN  # 0.0216
RULE12_WALL_TARGET = 2.0  # drawing-simplicity policy rule 12
RULE12_WALL_FLOOR = 1.5
RUNNING_FLOOR = _bar.STRADDLE_RUNNING_FLOOR  # 0.10, oiled steel faces


def _band(nominal: float, band: tuple[float, float]) -> tuple[float, float]:
    return nominal + band[1], nominal + band[0]


def joint_budget() -> dict[str, float]:
    """Worst-case values of every fit the joint must hold (all mm).

    Every term is at the worst case of its printed band (policy rule 12): the
    drill rod +/-0.005, the reamed cheek hole +0.010/0, the lever's #47 hole
    +0.10/0, the lever 3.00 +/-0.10, the top notch 3.20 +0.30/0, its ledge
    1.575 +/-0.05, the bar stock +0/-0.051, the hubs that set the pitch never
    shorter than nominal.
    """
    pin_min, pin_max = PIN_DIA - PIN_DIA_TOLERANCE, PIN_DIA + PIN_DIA_TOLERANCE
    hole_min, hole_max = _band(BAR_HOLE_DIA, BAR_HOLE_BAND)
    lever_hole_min = NUMBER_DRILL_MM[_lever.BAR_PIN_HOLE_SPEC.size]
    lever_hole_max = lever_hole_min + DRILLED_PLUS
    lever_min = _lever.LEVER_THICKNESS - _bar.LEVER_THICKNESS_TOLERANCE
    notch_min, notch_max = _band(_bar.TOP_NOTCH_WIDTH, _bar.NOTCH_WIDTH_BAND)
    w_min, w_max = _bar.BAR_WIDTH - BAR_STOCK_UNDERSIZE, _bar.BAR_WIDTH
    blank_min, blank_max = _band(PIN_BLANK_LENGTH, PIN_BLANK_LENGTH_BAND)
    pitch_min = _lever.HUB_LENGTH  # levers stack hub on hub at the pitch
    # Each bar floats on its lever by the notch's side clearance; bar j
    # leans north and bar j+1 south, each face carrying its dressed pin end.
    float_max = notch_max - lever_min
    neighbour = pitch_min - w_max - float_max - 2.0 * PIN_END_PROUD_MAX
    return {
        "interference_min": pin_min - hole_max,
        "interference_max": pin_max - hole_min,
        "running_clearance_min": lever_hole_min - pin_max,
        "running_clearance_max": lever_hole_max - pin_min,
        "neighbour_clearance_min": neighbour,
        # Hole at mid-depth: the reamed hole's wall to the bar's front/back
        # faces on the narrowest stock.
        "hole_face_wall_min": (w_min - hole_max) / 2.0,
        # The cheek the pin presses into. The printed ledge is the near-side
        # cheek; the far cheek is what the widest notch leaves of the
        # narrowest stock beside the thinnest ledge -- a pre-existing #1038
        # shortfall the pin does not change (it fills the hole it presses).
        "tine_min_printed": _bar.TOP_NOTCH_OFFSET - _bar.NOTCH_OFFSET_TOLERANCE_MM,
        "tine_min_derived": w_min
        - (_bar.TOP_NOTCH_OFFSET + _bar.NOTCH_OFFSET_TOLERANCE_MM)
        - notch_max,
        "blank_excess_min": blank_min - w_max,
        "blank_excess_max": blank_max - w_min,
    }


BUDGET = joint_budget()
if BUDGET["interference_min"] <= 0.0:
    raise AssertionError("the loosest pin can slide out of the largest reamed hole")
if BUDGET["interference_max"] > PRESS_INTERFERENCE_MAX + 1e-9:
    raise AssertionError("the tightest press exceeds ANSI FN2 for the bar cheeks")
if BUDGET["running_clearance_min"] <= 0.0:
    raise AssertionError("pin can seize in the lever's bar-pin hole")
if BUDGET["neighbour_clearance_min"] < RUNNING_FLOOR - 1e-9:
    raise AssertionError("a pin end can close the bar-to-bar running gap")
if BUDGET["hole_face_wall_min"] < RULE12_WALL_TARGET - 1e-9:
    raise AssertionError("reamed hole to bar face under the rule-12 target")
if BUDGET["blank_excess_min"] <= 0.0:
    raise AssertionError("pin blank too short to dress flush at both faces")
if PIN_INSTALLED_LENGTH != _bar.BAR_WIDTH:
    raise AssertionError("the installed pin must be flush with both bar faces")
if _bar.LEVER_THICKNESS != _lever.LEVER_THICKNESS:
    raise AssertionError("the bar's restated lever thickness drifted")
if not math.isclose(_lever.HUB_LENGTH, 7.0565):
    raise AssertionError("the station pitch moved; re-run the #1038 gap budget")

# --- Drawing contract (policy rule 2: the PART owns places and bands). ---
# Both marked dimensions live on the revolve's half-profile (``PinProfile``),
# so both import into the side view beside each other (rule 7, turned part).
# The diameter carries the drill rod's own grind band natively at three
# places; the installed length is the bar's width, printed as REFERENCE (the
# bar's stock owns it). The blank cut length is a shop instruction in the notes.
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "PinProfile": {"PinDia", "PinLen"},
}
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "PinProfile": {"PinDia": 3, "PinLen": 2},
}
DRAWING_PRECISION_BY_NAME: dict[str, int] = {
    name: decimals
    for dimensions in DRAWING_PRECISION.values()
    for name, decimals in dimensions.items()
}
REFERENCE_DIMENSIONS = frozenset({"PinLen"})
if {name for names in DRAWING_DIMENSIONS.values() for name in names} != set(
    DRAWING_PRECISION_BY_NAME
):
    raise AssertionError("every marked pin dimension needs authored places")
