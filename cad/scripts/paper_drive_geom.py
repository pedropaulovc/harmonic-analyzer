"""Paper-feed law of the transgear train -- SolidWorks-free.

Net platen feed per CRANK revolution with the T12 crank / T24 knob removable
set mounted: chain (tooth ratio, ``transgear_removable_spec``) x
knob-shaft 12T/disc reduction x
feed-pinion pitch circumference on the module 0.8 PA20 rack. Every stage is a real mate in
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

MM_PER_IN = 25.4

# A roller chain advances one tooth per link on both sprockets, so the law is
# the TOOTH ratio (exactly 12:24), not the #25 pitch-diameter ratio (0.5043:
# PD = p / sin(180/N) is not linear in N).
_T12 = pd_transgear_removable_spec.TEETH["T12"]
_T24 = pd_transgear_removable_spec.TEETH["T24"]
CHAIN_RATIO = _T12 / _T24  # 0.5: knob turns per crank turn
GEAR_RATIO = pd_transgear_knob_shaft_spec.TEETH / pd_rack_pinion_spec.TEETH  # 12:120
FEED_PITCH_DIA = (
    pd_transgear_feed_pinion_spec.TEETH
    / pd_transgear_feed_pinion_spec.DIAMETRAL_PITCH
    * MM_PER_IN
)  # 9.6 mm reference pitch diameter; profile shift does not change rolling travel.
NET_RACK_TRAVEL_PER_CRANK_REV = (
    CHAIN_RATIO * GEAR_RATIO * math.pi * FEED_PITCH_DIA
)  # 1.507964 mm, 5.5118% less than the original DP30 feed.
ORIGINAL_RACK_TRAVEL_PER_CRANK_REV = CHAIN_RATIO * GEAR_RATIO * math.pi * (
    pd_transgear_feed_pinion_spec.TEETH * MM_PER_IN / 30.0
)
FEED_TRAVEL_CHANGE_PERCENT = 100.0 * (
    NET_RACK_TRAVEL_PER_CRANK_REV / ORIGINAL_RACK_TRAVEL_PER_CRANK_REV - 1.0
)
# Swapping the removables end for end (T24 crank / T12 knob) multiplies the feed
# by the inverse chain ratio squared.
COARSE_FEED_RATIO = (_T24 / _T12) ** 2  # 4.0
