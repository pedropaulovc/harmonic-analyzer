r"""Bar pivot pin (MHA-CH-11) and the amplitude-bar-to-channel-lever joint it
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
(2026-10): the bar's 1.60 cheeks leave no bearing land under a countersink,
and a pressed pin drives out with a punch. The MHA-CH-10 rod-fork pin
(``ch_rod_pivot_pin_spec``) follows it (user ruling 2026-10-09, PR #1292
review F1).

Frame (part): pin axis = part X (Top ∩ Front, named Axis1), axial mid-plane =
Right Plane (x = 0), as build_ch_bar_pivot_pin revolves it; the
model is the INSTALLED pin -- a Ø PIN_DIA cylinder BAR_WIDTH long, flush with
both bar faces. The shop cuts the blank PIN_BLANK_LENGTH long; the drawing
prints that from the part's blanked BlankReference sketch.
"""

from __future__ import annotations

import math

import _config
import ch_amplitude_bar_spec as _bar
import ch_channel_lever_spec as _lever
from _hole_spec import NUMBER_DRILL_MM
from _inch_wall_limits import WALL_FLOOR_MM, WALL_TARGET_MM
from _package_units import drawing_unit
from _printed_tolerance import drilled_oversize_mm, printed_band_mm

MM_PER_IN = 25.4

# #290: this pin's sheet prints its row's unit (in); every other band below is
# read in the unit of the sheet that prints it.
UNIT = drawing_unit("parts/ch-bar-pivot-pin", _config.parts("ch-bar-pivot-pin"))
_BAR_UNIT = _bar.UNIT

# --- The lever sheet's drilled-hole band (its #47 bar-pin hole): a twist
# drill cuts on-size to oversize. ---
DRILLED_PLUS = drilled_oversize_mm(unit=_lever.UNIT)

# --- The pin: 5/64 drill rod (AISI O1/W1, used annealed as supplied; ground
# to +/-0.0002 in). ---
PIN_DIA = 5.0 / 64.0 * MM_PER_IN  # 1.984
PIN_DIA_TOLERANCE = 0.00508  # +/-.0002 in, drill-rod grind
PIN_INSTALLED_LENGTH = _bar.BAR_WIDTH  # dressed flush with both bar faces
# Cut length of the blank: the bar plus dressing stock at each end. Its one
# function is to stand proud of both faces before dressing (machinist round 1,
# #1305: tighter than a dress-flush blank needs is over-specified). On the
# inch sheet the .X band (+/-.1) would let the blank fall short of the bar,
# so it prints at two places under the title block's .XX: .30 keeps the
# shortest blank proud of the widest bar.
PIN_BLANK_LENGTH = 7.62  # .30
PIN_BLANK_LENGTH_PLACES = 2
PIN_BLANK_LENGTH_BAND = (
    printed_band_mm(PIN_BLANK_LENGTH_PLACES, unit=UNIT),
    -printed_band_mm(PIN_BLANK_LENGTH_PLACES, unit=UNIT),
)  # (upper, lower) deviations: .XX
# Dressed ends stand nothing proud of the bar faces: the top-notch stack
# below leaves 0.1065 against the 0.10 running floor (#1038, owner ruling
# 2026-10-15 option 2).
PIN_END_PROUD_MAX = 0.0

# --- The bar's reamed press hole (the bar spec owns it; restated here so the
# budget reads one place). ---
BAR_HOLE_DIA = _bar.TOP_PIN_HOLE_DIA
BAR_HOLE_BAND = _bar.TOP_PIN_HOLE_BAND
# 1/4 in cold-finished square bar (the bar spec owns the stock band). The
# bar's section prints only as the stock's reference size, so the stock band,
# not the title block's .XX, bounds it.
BAR_STOCK_UNDERSIZE = _bar.BAR_STOCK_UNDERSIZE  # 0.051
# The hole's offset from the bar's back face prints at three places on the
# bar sheet (ch_amplitude_bar_notes.DRAWING_PRECISION TopPinX): that sheet's
# .XXX band.
HOLE_LOCATION_TOLERANCE = printed_band_mm(3, unit=_BAR_UNIT)

# --- The joint's limits (the budget test_ch_bar_pivot_fit holds). ---
# The tightest press the cheeks take: ANSI B4.1-1967 (R1987) FN2 "medium
# drive fit, suitable for ordinary steel parts", nominal size 0-0.12 in:
# interference 0.2-0.85 thousandths of an inch. Its 0.85 thou maximum caps the
# press; the minimum only has to stay positive (the pin carries no axial load:
# the lever bears on it radially and the bar cheeks hold it square).
PRESS_INTERFERENCE_MAX = 0.00085 * MM_PER_IN  # 0.0216
# The amplitude bar's walls (its hole-to-face wall and cheeks), judged on the
# bar's own inch sheet: the .080 target and the .060 floor.
RULE12_WALL_TARGET = WALL_TARGET_MM  # drawing-guidelines.md rule 17 (walls and webs)
RULE12_WALL_FLOOR = WALL_FLOOR_MM
RUNNING_FLOOR = _bar.STRADDLE_RUNNING_FLOOR  # 0.10, oiled steel faces
# Each sheet's linear band: the lever's height prints at two places on the
# lever sheet, the bar's notch depth and pin drop at two on the bar sheet.
LEVER_LINEAR_2PL = printed_band_mm(2, unit=_lever.UNIT)
BAR_LINEAR_2PL = printed_band_mm(2, unit=_BAR_UNIT)
# The lever turns on the pin relative to the bar: |lever tilt - bar tilt| over
# a cam turn at every bar station up to the square preset's 80 mm (channels.yaml
# a_1), taking the rocker's solved swing in either sense; the loop solves
# 10.28 deg, restated rounded outward (test_ch_bar_pivot_fit re-solves it).
LEVER_BAR_SWING_DEG = 10.3


def _band(nominal: float, band: tuple[float, float]) -> tuple[float, float]:
    return nominal + band[1], nominal + band[0]


def joint_budget() -> dict[str, float]:
    """Worst-case values of every fit the joint must hold (all mm).

    Every term is at the worst case of its printed band (drawing-guidelines.md rule 17 (walls and webs)): the
    drill rod +/-.0002 in, the reamed cheek hole (the bar's TOP_PIN_HOLE_BAND),
    the lever's #47 hole at the lever sheet's DRILLED HOLES row, the lever
    thickness and plate offset at their bands, the top notch and its ledge, the
    bar stock +0/-0.051, the hole's offset from the back face at the bar
    sheet's .XXX band, the hubs that set the pitch never shorter than nominal,
    the lever's height at the lever sheet's .XX, the notch's depth and the
    pin's drop at the bar sheet's .XX, the blank at this sheet's .XX.
    """
    pin_min, pin_max = PIN_DIA - PIN_DIA_TOLERANCE, PIN_DIA + PIN_DIA_TOLERANCE
    hole_min, hole_max = _band(BAR_HOLE_DIA, BAR_HOLE_BAND)
    lever_hole_min = NUMBER_DRILL_MM[_lever.BAR_PIN_HOLE_SPEC.size]
    lever_hole_max = lever_hole_min + DRILLED_PLUS
    lever_min = _lever.LEVER_THICKNESS - _lever.LEVER_THICKNESS_TOLERANCE
    notch_min, notch_max = _band(_bar.TOP_NOTCH_WIDTH, _bar.TOP_NOTCH_WIDTH_BAND)
    w_min, w_max = _bar.BAR_WIDTH - BAR_STOCK_UNDERSIZE, _bar.BAR_WIDTH
    blank_min, blank_max = _band(PIN_BLANK_LENGTH, PIN_BLANK_LENGTH_BAND)
    pitch_min = _lever.HUB_LENGTH  # levers stack hub on hub at the pitch
    # Each bar floats on its lever by the notch's side clearance; bar j
    # leans north and bar j+1 south, each face carrying its dressed pin end.
    # Each notch sits on its ledge (printed from one bar face) and each plate
    # on its offset (printed from one hub face): one bar's ledge and plate at
    # one end of their bands, its neighbour's at the other, close the gap by
    # both bands twice.
    float_max = notch_max - lever_min
    neighbour = (
        pitch_min
        - w_max
        - float_max
        - 2.0 * _bar.NOTCH_OFFSET_TOLERANCE_MM
        - 2.0 * _lever.PLATE_OFFSET_TOLERANCE
        - 2.0 * PIN_END_PROUD_MAX
    )
    # The notch roof below the lever's lower edge: the roof's least depth
    # under the pin's lowest hole, against the tallest lever turned the full
    # relative swing (its corner at the bar's depth face) and dropped by the
    # pin's running clearance.
    swing = math.radians(LEVER_BAR_SWING_DEG)
    roof_below_pin_min = (_bar.TOP_NOTCH_HEIGHT - BAR_LINEAR_2PL) - (
        _bar.TOP_PIN_DROP + BAR_LINEAR_2PL
    )
    lever_reach_max = (
        (_lever.BAR_TALL + LEVER_LINEAR_2PL) / 2.0 * math.cos(swing)
        + _bar.BAR_DEPTH / 2.0 * math.sin(swing)
        + (lever_hole_max - pin_min) / 2.0
    )
    return {
        "interference_min": pin_min - hole_max,
        "interference_max": pin_max - hole_min,
        "running_clearance_min": lever_hole_min - pin_max,
        "running_clearance_max": lever_hole_max - pin_min,
        "neighbour_clearance_min": neighbour,
        "notch_roof_clearance_min": roof_below_pin_min - lever_reach_max,
        # The reamed hole's wall to the bar's front/back faces: its offset
        # from the back face at either end of its band, on the narrowest
        # stock (the far face is the nearer one when the offset runs long).
        "hole_face_wall_min": min(
            _bar.BAR_DEPTH / 2.0 - HOLE_LOCATION_TOLERANCE - hole_max / 2.0,
            w_min
            - (_bar.BAR_DEPTH / 2.0 + HOLE_LOCATION_TOLERANCE)
            - hole_max / 2.0,
        ),
        # The cheek the pin presses into. The printed ledge is the near-side
        # cheek; the far cheek is what the widest notch leaves of the
        # narrowest stock beside the widest ledge -- the owner-approved #1038
        # exception (1.17 MIN or better) the pin does not change.
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
if BUDGET["notch_roof_clearance_min"] < RUNNING_FLOOR - 1e-9:
    raise AssertionError("the lever's lower edge can reach the top notch's roof")
# The hole's far-face wall is .079 on the narrowest stock: under the .080
# target, over the .060 floor (MHA-CH-01 RV-06, owner ruling 2026-11-01).
if BUDGET["hole_face_wall_min"] < RULE12_WALL_FLOOR - 1e-9:
    raise AssertionError("reamed hole to bar face under the drawing-guidelines.md rule 17 (walls and webs) floor")
if BUDGET["blank_excess_min"] <= 0.0:
    raise AssertionError("pin blank too short to dress flush at both faces")
if PIN_INSTALLED_LENGTH != _bar.BAR_WIDTH:
    raise AssertionError("the installed pin must be flush with both bar faces")
if _bar.LEVER_THICKNESS != _lever.LEVER_THICKNESS:
    raise AssertionError("the bar's restated lever thickness drifted")
if not math.isclose(_lever.HUB_LENGTH, 7.0565):
    raise AssertionError("the station pitch moved; re-run the #1038 gap budget")
