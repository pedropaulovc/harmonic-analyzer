"""Paper-feed law of the transgear train -- SolidWorks-free.

Net platen feed per CRANK revolution with the T12 crank / T24 knob removable
set mounted: chain (tooth ratio, ``transgear_removable_spec``) x
knob-shaft 12T/disc reduction x
feed-pinion reference pitch circumference on the 32DP rack. Every stage is a real mate in
``build_paper_drive_assembly``; this module only states the law, from the same
pure-data spec modules the parts build from, so the assembly, the kinematics
probe and the offline error budget (``error_budget.py``) all read one source.
"""

from __future__ import annotations

import math

import pd_rack_pinion_spec
import pd_transgear_feed_pinion_spec
import pd_transgear_knob_shaft_spec
import pd_transgear_removable_spec
import pd_support_bar_spec as bar
import pd_transgear_arm_geometry as arm
from pd_latch_hook_bracket_geometry import BAR_CENTRE_Y

MM_PER_IN = 25.4

# A roller chain advances one tooth per link on both sprockets, so the law is
# the TOOTH ratio (exactly 12:24), not the #25 pitch-diameter ratio (0.5043:
# PD = p / sin(180/N) is not linear in N).
_T12 = pd_transgear_removable_spec.TEETH["T12"]
_T24 = pd_transgear_removable_spec.TEETH["T24"]
CHAIN_RATIO = _T12 / _T24  # 0.5: knob turns per crank turn
GEAR_RATIO = pd_transgear_knob_shaft_spec.TEETH / pd_rack_pinion_spec.TEETH  # 12:120
FEED_PITCH_DIA = pd_transgear_feed_pinion_spec.PITCH_DIA
# Profile shift changes mounting distance, not the reference rolling pitch.
NET_RACK_TRAVEL_PER_CRANK_REV = (
    CHAIN_RATIO * GEAR_RATIO * math.pi * FEED_PITCH_DIA
)
# Swapping the removables end for end (T24 crank / T12 knob) multiplies the feed
# by the inverse chain ratio squared.
COARSE_FEED_RATIO = (_T24 / _T12) ** 2  # 4.0

# Keep the existing pivot/latch/stud pose. Mount the stock rack and backer at
# the shifted feed pitch line; relocate only the reducer's knob bearing.
PLATEN_BOTTOM_Y = 273.234
PIVOT_XY = (bar.PIVOT_TAP_X, BAR_CENTRE_Y + bar.HANGER_TAP_Y)
STUD_XY = (
    arm.STUD_MACHINE_X,
    PIVOT_XY[1] + arm.PIN_STATION * arm.ARM_U[1],
)
KNOB_SHAFT_XY = (
    PIVOT_XY[0] + arm.KNOB_BORE_STATION * arm.ARM_U[0]
    + arm.KNOB_BORE_OFFSET * arm.ARM_N[0],
    PIVOT_XY[1] + arm.KNOB_BORE_STATION * arm.ARM_U[1]
    + arm.KNOB_BORE_OFFSET * arm.ARM_N[1],
)
RACK_PITCH_Y = STUD_XY[1] + pd_transgear_feed_pinion_spec.RACK_AXIS_DISTANCE
RACK_TIP_Y = RACK_PITCH_Y - pd_transgear_feed_pinion_spec.MODULE_MM
RACK_CREST_DROP = PLATEN_BOTTOM_Y - RACK_TIP_Y
