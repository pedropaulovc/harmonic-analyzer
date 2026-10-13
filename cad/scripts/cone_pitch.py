"""Pure cone/drum pitch geometry, independent of machine placement.

The cone gear's faced width is the shaft seat pitch. That pitch depends on the
train DP and nominal drum-seat length, not the channel count or station origin.
Keep this math below ``cone_line`` so a gear recipe does not inherit the line's
world datums, mesh fit or tip-block dependencies. Expressions moved verbatim
from ``cone_line``; the assembly and part therefore use the same values.
"""

from __future__ import annotations

import math

import _config

DP_TRAIN = _config.machine("gear_train", "diametral_pitch")
RADIUS_STEP = 3.0 * 25.4 / DP_TRAIN
_DRUM_SEAT_NOMINAL = _config.machine("cone_incline", "drum_seat_nominal_mm")
Z_PITCH = _DRUM_SEAT_NOMINAL * math.cos(math.asin(RADIUS_STEP / _DRUM_SEAT_NOMINAL))
SIN_I = RADIUS_STEP / Z_PITCH
COS_I = math.sqrt(1.0 - SIN_I * SIN_I)
TAN_I = SIN_I / COS_I
SEC_I = 1.0 / COS_I
INCLINE_DEG = math.degrees(math.asin(SIN_I))
SEAT_PITCH = Z_PITCH * COS_I
