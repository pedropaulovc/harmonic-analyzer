r"""Amplitude-bar dimensional contract -- the single source of truth shared by
the part build (``build_ch_amplitude_bar.py``) and its manufacturing drawing
(``draw_ch_amplitude_bar.py``).

PURE DATA, no SolidWorks/COM imports (see ``crank_arm_spec`` for the pattern).
The nominal geometry MUST match the constants in build_ch_amplitude_bar.py.

The bar is ~808 mm long but only 6.35 mm square, so the print shows a 1:4
full-length front view (overall length + top pin hole), a right end view for the
square section, and a native detail of each small end notch.
"""

from __future__ import annotations
import math

from _hole_spec import HoleSpec


MM_PER_IN = 25.4

# --- The plates the notches straddle (restated, not imported: the channel and
# rocker-bank closures import this module, so it reads no other part's spec;
# test_ch_amplitude_bar_drawing pins each to its source). ---
LEVER_THICKNESS = 3.0  # ch_channel_lever_spec.LEVER_THICKNESS (the top notch's)
LEVER_THICKNESS_TOLERANCE = 0.10  # channel-lever note 2: "3.00 +/-0.10 OVERALL"
STRAP_THICKNESS = 2.5  # ch_rocker_arm_spec.ARM_THICKNESS (the foot notch's)
STRAP_THICKNESS_TOLERANCE = 0.508  # ch_rocker_arm_spec.LINEAR_2PL: "STRAP 2.50" at .XX
STRADDLE_RUNNING_FLOOR = 0.10  # rocker_bank_layout.MIN_END_PLAY, oiled steel faces


def _straddle_minimum(plate: float, tolerance: float) -> float:
    """A notch's least width: its plate at max material plus the running
    floor, rounded UP to the print's 2 places so it is never narrower."""
    return (
        math.ceil(round((plate + tolerance + STRADDLE_RUNNING_FLOOR) * 100.0, 9))
        / 100.0
    )


# --- Nominal geometry (DIMENSIONS.md "Chapter 15"). ---
BAR_LENGTH = 32.0 * MM_PER_IN - 4.5  # 808.3: legacy 32" (~80 cm) SHORTENED 4.5
# at the TOP by the 2026-08-02 top-frame rederive (fulcrum chain -4.5: bar top
# 1072.25 -> 1067.75, top pin 1065.9 -> 1061.4; the foot/arc contact at the
# rocker is UNCHANGED, preserving the level d=0 rest pose)
BAR_WIDTH = 0.25 * MM_PER_IN  # 6.35 square section
BAR_DEPTH = 0.25 * MM_PER_IN  # 6.35
# Notch widths: interim one-sided bands (user ruling 2026-09-27, #1038). The
# legacy 1/8" (3.175) width left the top notch under the lever's 3.10 max
# material. Each width's modelled nominal is now its minimum -- the straddled
# plate at max material plus the running floor -- and the band sits all on the
# plus side, so a notch is never narrower than its plate. The 0.25 novice spare
# (rocker_bank_layout.MARGIN_SPARE) is deliberately left out: with it, and with
# the band's upper side, the bar-to-bar side gap (pitch 7.0565 - bar 6.35 =
# 0.7065) does not close. That stack, and the geometry change that fixes it,
# is #1038.
BOTTOM_NOTCH_WIDTH = _straddle_minimum(
    STRAP_THICKNESS, STRAP_THICKNESS_TOLERANCE
)  # 3.11
BOTTOM_NOTCH_HEIGHT = 0.09375 * MM_PER_IN  # 2.381
TOP_NOTCH_WIDTH = _straddle_minimum(LEVER_THICKNESS, LEVER_THICKNESS_TOLERANCE)  # 3.20
NOTCH_WIDTH_BAND = (0.30, 0.0)  # (upper, lower) deviations, native on both widths
TOP_NOTCH_HEIGHT = 0.5 * MM_PER_IN  # 12.7
TOP_PIN_DROP = 0.25 * MM_PER_IN  # 6.35 hole centre below the bar top
TOP_PIN_HOLE_SPEC = HoleSpec("drilled_number", "#47")

# --- Derived. ---
TOP_PIN_Y = BAR_LENGTH - TOP_PIN_DROP  # 801.95
# Each notch is centred on the width, so each end has its own ledge.
BOTTOM_NOTCH_OFFSET = (BAR_WIDTH - BOTTOM_NOTCH_WIDTH) / 2.0  # 1.62
TOP_NOTCH_OFFSET = (BAR_WIDTH - TOP_NOTCH_WIDTH) / 2.0  # 1.575


# The foot notch's roof rides the rocker's top edge, and at d = 0 the cheeks
# either side pass over the rocker hub; a deep notch drops them onto it one
# for one. So the depth is one-sided, shallow only (user ruling 2026-09-26):
# a shallow notch just lifts the bar at rest (ch_rocker_arm_spec.TOP_EDGE_BAND
# states the lift budget and its effect on the channel). Policy rule 2
# (Codex #936 PRRT_kwDOPHDy386mWF0L): the band is the part's, native on
# BottomNotchHeight, never note text.
BOTTOM_NOTCH_DEPTH_BAND = (0.0, -0.50)  # (upper, lower) deviations

# Each notch is centred on the bar's width by its Bottom/TopNotchOffset ledge,
# so the centring requirement rides natively on the ledge each detail prints (Main
# ruling A(a) 2026-09-27, Codex #936 PRRT_kwDOPHDy386mWF0L): the bottom-left
# ledge in DETAIL A, the top-right one in DETAIL B.
NOTCH_OFFSET_TOLERANCE_MM = 0.05  # symmetric

# --- Marked-dimension contract.  The bar is far too long to dimension the tiny
# end notches on the 1:4 view, so the overall length prints there and each
# notch's centring ledge, width and depth print in a native detail of its end. ---
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
}
# Places the part authors on each printed dimension (policy rule 2).
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "BarProfile": {
        "BarLength": 2,
        "BottomLeftLedge": 2,
        "BottomNotchHeight": 2,
        "BottomNotchWidth": 2,
        "TopNotchHeight": 2,
        "TopNotchWidth": 2,
        "TopRightLedge": 2,
    },
}

# Drawing prose (DRAWING_NOTES / view notes) lives in ch_amplitude_bar_notes.py
# -- see ch_rocker_arm_notes for the rationale.
