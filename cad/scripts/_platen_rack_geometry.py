"""Pure platen-rack dimensions and tooth-gap geometry.

Shared with assembly placement without importing the rack builder, so part
configuration derivation and saving do not enter assembly or drawing recipes.
"""

from __future__ import annotations

import math

IN = 25.4  # inch -> mm


# The platen recording rack-pinion is its OWN gear pair — ch23 measured it as DP 30
# ("the scale anchor of the chapter") — independent of the cone/cylinder drive train.
# It MUST match the pinion (build_pd_rack_pinion via _gear.build_fixed_gear, default
# dp=30) and the output assembly's PINION_PD_R (/30.0). Do NOT couple this to
# machine.yaml gear_train.diametral_pitch: the value-preserving _config migration
# (2bc0b10) tied them while both were 30, then the OD-62.2 re-anchor moved the train
# DP to 49.82 — silently shrinking the rack pitch to 1.60 mm against the DP-30 pinion
# (2.66 mm) so the mesh interfered (output interference gate, 8 hits ≤ 1.93 mm³).
DP = 30.0  # 1/in, DIMENSIONS.md ch23 (med — scale anchor of the chapter)
PA_DEG = 14.5  # period-typical, same as the gear train
BAR_LENGTH = 269.64  # ch30-p002 Pose Studio: equals resized platen width
BAR_HEIGHT = 12.0  # exposed band below the bottom guide rail (rework E3, low)
BAR_THICKNESS = 6.0  # DIMENSIONS.md ch22: edge-on photo (low)

PITCH = math.pi / DP * IN  # 2.660 mm
ADDENDUM = 1.0 / DP * IN  # 0.847 mm
DEDENDUM = 1.157 / DP * IN  # 0.980 mm -- 14.5 deg full-depth standard

PITCH_LINE_Y = BAR_HEIGHT - ADDENDUM  # 11.153 -- teeth crest at the bar top
ROOT_Y = PITCH_LINE_Y - DEDENDUM  # 28.174
CUT_TOP_Y = BAR_HEIGHT + 1.0  # opens past the top edge
TAN_PA = math.tan(math.radians(PA_DEG))

GAP_COUNT = int(BAR_LENGTH / PITCH)
FIRST_GAP_X = PITCH / 2.0  # 1.33 -- first gap centred half a pitch in


def half_width(y: float) -> float:
    """Gap half-width (mm) at height y: p/4 at the pitch line, 14.5 deg flanks."""
    return PITCH / 4.0 + (y - PITCH_LINE_Y) * TAN_PA


# Exact per-gap cross-section inside the bar (trapezoid clipped at the top).
GAP_AREA = (half_width(ROOT_Y) + half_width(BAR_HEIGHT)) * (BAR_HEIGHT - ROOT_Y)
