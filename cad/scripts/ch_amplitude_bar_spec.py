r"""Amplitude-bar dimensional contract -- the single source of truth shared by
the part build (``build_ch_amplitude_bar.py``) and its manufacturing drawing
(``draw_ch_amplitude_bar.py``).

PURE DATA, no SolidWorks/COM imports (see ``dt_crank_arm_spec`` for the pattern).
The nominal geometry MUST match the constants in build_ch_amplitude_bar.py.

The print's marked-dimension contract and its prose live in
``ch_amplitude_bar_notes``: the channel, rocker-bank and pin closures import
this module, so drawing data here would re-key them on every sheet edit.
"""

from __future__ import annotations
import math

import _config
from _package_units import drawing_unit

# The top notch's plate.
from ch_channel_lever_spec import LEVER_THICKNESS, LEVER_THICKNESS_TOLERANCE


MM_PER_IN = 25.4

# #290: the sheet prints decimal inch (the row's ``drawing_unit``). Lengths
# stay millimetres, each fabricated one the exact decimal of its printed inch
# value; the 1/4 square stock is as bought, and the bar length, the foot
# notch's depth and the pin's drop close the rocker-bar-lever chain and stay
# exact.
UNIT = drawing_unit("parts/ch-amplitude-bar", _config.parts("ch-amplitude-bar"))

# --- The foot notch's plate, the rocker strap: a conservative envelope over
# ch_rocker_arm_spec's .098 +/-.001 strap (the former 2.50 at .XX), kept so the
# foot notch's stack (#1038) does not move; test_ch_amplitude_bar_drawing
# checks it covers the strap at maximum material. ---
STRAP_THICKNESS = 2.5
STRAP_THICKNESS_TOLERANCE = 0.508
STRADDLE_RUNNING_FLOOR = 0.10  # rocker_bank_layout.RUNNING_FLOOR, oiled steel faces


def _straddle_minimum(plate: float, tolerance: float) -> float:
    """A notch's least width: its plate at max material plus the running
    floor, rounded UP to an even thousandth of an inch so it is never
    narrower and its centring ledge (half the 1/4 stock less the notch) also
    lands on the print's three places."""
    least = (plate + tolerance + STRADDLE_RUNNING_FLOOR) / MM_PER_IN
    return math.ceil(round(least * 500.0, 9)) * 2.0 * MM_PER_IN / 1000.0


# --- Nominal geometry (DIMENSIONS.md "Chapter 15"). ---
BAR_LENGTH = 32.0 * MM_PER_IN - 4.5  # 808.3 (31.82): legacy 32" (~80 cm) SHORTENED 4.5
# at the TOP by the 2026-08-02 top-frame rederive (fulcrum chain -4.5: bar top
# 1072.25 -> 1067.75, top pin 1065.9 -> 1061.4; the foot/arc contact at the
# rocker is UNCHANGED, preserving the level d=0 rest pose)
BAR_WIDTH = 0.25 * MM_PER_IN  # 6.35 square section, 1/4 in cold-finished bar
BAR_DEPTH = 0.25 * MM_PER_IN  # 6.35
# 1/4 in cold-finished square bar: ASTM A108/A29 size tolerance +0/-0.002 in.
# The section is the stock (printed as reference), so the stock band, not the
# title block's .XX, bounds the bar's width and depth.
BAR_STOCK_UNDERSIZE = 0.002 * MM_PER_IN  # 0.051
# Notch widths: one-sided bands (user ruling 2026-09-27, #1038). The legacy
# 1/8" (3.175) width left the top notch under the lever's max material. Each
# width's modelled nominal is its minimum -- the straddled plate at max
# material plus the running floor -- and the band sits all on the plus side,
# so a notch is never narrower than its plate. The 0.25 novice spare
# (rocker_bank_layout.MARGIN_SPARE) is deliberately left out.
# The top notch (owner ruling 2026-10-15, #1038 option 2): the lever plate
# prints .118 +/-.002, so the notch is .124 +.007/.000, and the bar-to-bar
# side gap (pitch 7.0565 - bar 6.35 = 0.7065) holds the running floor with
# this float, both ledges' and both plate offsets' bands in it
# (ch_bar_pivot_pin_spec.joint_budget). The foot notch keeps an interim
# +.010/.000 (the metric +0.30 narrowed so its widest notch and thinnest
# cheek are no worse than before); its stack is still #1038.
BOTTOM_NOTCH_WIDTH = _straddle_minimum(
    STRAP_THICKNESS, STRAP_THICKNESS_TOLERANCE
)  # 3.1496 (.124)
BOTTOM_NOTCH_HEIGHT = 0.09375 * MM_PER_IN  # 2.381 (.094), the foot's contact height
BOTTOM_NOTCH_WIDTH_BAND = (0.254, 0.0)  # +.010/.000 (upper, lower) deviations, native
TOP_NOTCH_WIDTH = _straddle_minimum(LEVER_THICKNESS, LEVER_THICKNESS_TOLERANCE)  # .124
TOP_NOTCH_WIDTH_BAND = (0.1778, 0.0)  # +.007/.000 (upper, lower) deviations, native
# The top notch's depth only clears the lever: its roof must stay below the
# lever's lower edge with the lever turned on the pin relative to the bar
# (ch_bar_pivot_pin_spec.joint_budget notch_roof_clearance_min). The legacy
# 1/2" (12.7) does not hold that at the printed bands (owner ruling
# 2026-10-15 deepened the lever), so the notch is cut .55 deep.
TOP_NOTCH_HEIGHT = 13.97  # .55
TOP_PIN_DROP = 0.25 * MM_PER_IN  # 6.35 (.25) hole centre below the bar top
# The MHA-CH-11 bar pivot pin presses into this hole through both top-notch
# cheeks and runs in the lever's #47 hole (user ruling 2026-10, press fit;
# ch_bar_pivot_pin_spec holds the fit budget). Reamed .077 +.0009/+.0005 in
# under the 5/64 drill rod: a purchased .0775 chucking reamer cuts inside it.
TOP_PIN_HOLE_DIA = 1.9558  # .077 in
TOP_PIN_HOLE_BAND = (0.02286, 0.0127)  # (upper, lower) deviations, reamed; native

# --- Derived. ---
TOP_PIN_Y = BAR_LENGTH - TOP_PIN_DROP  # 801.95
# Each notch is centred on the width, so each end has its own ledge.
BOTTOM_NOTCH_OFFSET = (BAR_WIDTH - BOTTOM_NOTCH_WIDTH) / 2.0  # 1.6002 (.063)
TOP_NOTCH_OFFSET = (BAR_WIDTH - TOP_NOTCH_WIDTH) / 2.0  # 1.6002 (.063)


# The foot notch's roof rides the rocker's top edge, and at d = 0 the cheeks
# either side pass over the rocker hub; a deep notch drops them onto it one
# for one. So the depth is one-sided, shallow only (user ruling 2026-09-26):
# a shallow notch just lifts the bar at rest (ch_rocker_arm_spec.TOP_EDGE_BAND
# states the lift budget and its effect on the channel). drawing-simplicity-policy.md `How the repository implements the guidelines`
# (Codex #936 PRRT_kwDOPHDy386mWF0L): the band is the part's, native on
# BottomNotchHeight, never note text.
BOTTOM_NOTCH_DEPTH_BAND = (0.0, -0.508)  # +.000/-.020 (upper, lower) deviations

# Each notch is centred on the bar's width by its Bottom/TopNotchOffset ledge,
# so the centring requirement rides natively on the ledge each detail prints (Main
# ruling A(a) 2026-09-27, Codex #936 PRRT_kwDOPHDy386mWF0L): the bottom-left
# ledge in DETAIL A, the top-right one in DETAIL B.
NOTCH_OFFSET_TOLERANCE_MM = 0.0508  # +/-.002, symmetric
