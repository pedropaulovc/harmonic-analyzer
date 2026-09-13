"""Paper-feed law of the transgear train -- SolidWorks-free.

Net platen feed per CRANK revolution with the T12 crank / T24 knob removable
set mounted: chain (pitch radii, ``_chain``) x third-pinion/disc reduction x
feed-pinion pitch circumference on the DP30 rack. Every stage is a real mate in
``build_paper_drive_assembly``; this module only states the law, from the same
pure-data spec modules the parts build from, so the assembly, the kinematics
probe and the offline error budget (``error_budget.py``) all read one source.
"""

from __future__ import annotations

import math

import rack_pinion_spec
import transgear_feed_pinion_spec
import transgear_pinion_spec
from _chain import PITCH_R_T12, PITCH_R_T24

MM_PER_IN = 25.4

CHAIN_RATIO = PITCH_R_T12 / PITCH_R_T24  # 0.5: knob turns per crank turn
GEAR_RATIO = transgear_pinion_spec.TEETH / rack_pinion_spec.TEETH  # 12:120
FEED_PITCH_DIA = (
    transgear_feed_pinion_spec.TEETH
    / transgear_feed_pinion_spec.DIAMETRAL_PITCH
    * MM_PER_IN
)  # 10.16 -- meshes the DP30 rack
NET_RACK_TRAVEL_PER_CRANK_REV = (
    CHAIN_RATIO * GEAR_RATIO * math.pi * FEED_PITCH_DIA
)  # 1.596
# Swapping the removables end for end (T24 crank / T12 knob) multiplies the feed
# by the inverse chain ratio squared.
COARSE_FEED_RATIO = (PITCH_R_T24 / PITCH_R_T12) ** 2  # 4.0
