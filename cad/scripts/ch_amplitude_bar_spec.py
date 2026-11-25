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

from top_frame_plane import FULCRUM_KEEPER_SEAT_Y
# The top notch's plate.
from ch_channel_lever_spec import LEVER_THICKNESS, LEVER_THICKNESS_BAND


MM_PER_IN = 25.4

# #290: the sheet prints decimal inch (the row's ``drawing_unit``). Lengths
# stay millimetres, each fabricated one the exact decimal of its printed inch
# value; the 1/4 square stock is as bought, and the bar length, the foot
# notch's depth and the pin's drop close the rocker-bar-lever chain and stay
# exact.
UNIT = drawing_unit("parts/ch-amplitude-bar", _config.parts("ch-amplitude-bar"))

# --- The foot notch's plate, the rocker strap: ch_rocker_arm_spec's .098
# +/-.001, restated (test_ch_amplitude_bar_drawing checks the two agree). ---
STRAP_THICKNESS = 2.4892  # .098
STRAP_THICKNESS_TOLERANCE = 0.0254  # +/-.001
STRADDLE_RUNNING_FLOOR = 0.10  # rocker_bank_layout.RUNNING_FLOOR, oiled steel faces


def _straddle_minimum(plate: float, tolerance: float) -> float:
    """A notch's least width: its plate at max material plus the running
    floor, rounded UP to an even thousandth of an inch so it is never
    narrower and its centring ledge (half the 1/4 stock less the notch) also
    lands on the print's three places."""
    least = (plate + tolerance + STRADDLE_RUNNING_FLOOR) / MM_PER_IN
    return math.ceil(round(least * 500.0, 9)) * 2.0 * MM_PER_IN / 1000.0


# --- Nominal geometry (DIMENSIONS.md "Chapter 15"). ---
# Legacy 32" (~80 cm) SHORTENED at the TOP by the fulcrum keepers' drop from
# the legacy frame top 1040.7 (the 2026-08-02 top-frame rederive: 4.5 to the
# 1036.2 keeper seat; #290 plane snap: 1036.1932, top_frame_plane). The foot/arc
# contact at the rocker is UNCHANGED, so the d=0 rest pose is preserved.
BAR_LENGTH = 32.0 * MM_PER_IN - (1040.7 - FULCRUM_KEEPER_SEAT_Y)  # 808.2932
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
# prints .118 +.002/-.004 and the notch takes its +.002 maximum, so the notch is .124 +.007/.000 (necessity register
# ch-amplitude-bar: +.010 leaves the bar-gap budget under a thousandth). The foot notch is
# .104 +.006/.000 on the .098 +/-.001 strap (#3114): the rocker arms float
# on their shaft, each following its own rod, so two neighbouring arms can
# close to their hubs' least length (ch_rocker_arm_spec.HUB_LENGTH_MIN), and
# the foot's float is what is left of that for the bars. Both floats, with
# both ledges' and both plate offsets' bands, leave the bar-to-bar side gap
# over its running floor at both ends (sh_vn_pivot_pin_bar_spec.joint_budget
# and ch_channel_assembly_spec.bar_gap_budget).
BOTTOM_NOTCH_WIDTH = _straddle_minimum(
    STRAP_THICKNESS, STRAP_THICKNESS_TOLERANCE
)  # 2.6416 (.104)
BOTTOM_NOTCH_HEIGHT = 0.09375 * MM_PER_IN  # 2.381 (.094), the foot's contact height
BOTTOM_NOTCH_WIDTH_BAND = (0.1524, 0.0)  # +.006/.000 (upper, lower) deviations, native
TOP_NOTCH_WIDTH = _straddle_minimum(LEVER_THICKNESS, LEVER_THICKNESS_BAND[0])  # .124
TOP_NOTCH_WIDTH_BAND = (0.1778, 0.0)  # +.007/.000 (upper, lower) deviations, native
# The top notch's depth only clears the lever: its roof must stay below the
# lever's lower edge with the lever turned on the pin relative to the bar
# (sh_vn_pivot_pin_bar_spec.joint_budget notch_roof_clearance_min). The legacy
# 1/2" (12.7) does not hold that at the printed bands (owner ruling
# 2026-10-15 deepened the lever), so the notch is cut .55 deep.
TOP_NOTCH_HEIGHT = 13.97  # .55
TOP_PIN_DROP = 0.25 * MM_PER_IN  # 6.35 (.25) hole centre below the bar top
# The MHA-SH-VN-58 bar pivot pin presses into this hole through both top-notch
# cheeks and runs in the lever's #47 hole (user ruling 2026-10, press fit;
# sh_vn_pivot_pin_bar_spec holds the fit budget). Owner ruling 2026-11-24,
# fit audit question 3: reamed with
# the .0775 reamer and printed with no band, the pin itself the gauge (it
# presses in, it does not enter by hand); a pin that enters by hand is bonded
# at MHA-CH-00. The model sits at the reamer's size, which the sheet prints.
# TOP_PIN_HOLE_LIMITS is the ANALYSIS band, what the reamer is modelled to
# cut (sh_vn_pivot_pin_spec.HOLE_REAMED_LIMITS), not a printed limit.
TOP_PIN_HOLE_LIMITS = (1.9685, 1.97866)  # .0775-.0779 in, the reamer's cut
TOP_PIN_HOLE_DIA = 1.9685  # .0775 in, the reamer
if TOP_PIN_HOLE_DIA != TOP_PIN_HOLE_LIMITS[0]:
    raise AssertionError("the top pin hole's model must be its reamer's size")

# --- Derived. ---
TOP_PIN_Y = BAR_LENGTH - TOP_PIN_DROP  # 801.9432
# Each notch is centred on the width, so each end has its own ledge.
BOTTOM_NOTCH_OFFSET = (BAR_WIDTH - BOTTOM_NOTCH_WIDTH) / 2.0  # 1.8542 (.073)
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
