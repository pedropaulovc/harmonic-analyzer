"""The cone shaft's plan incline, derived once from the gear-train config.

Every consumer of the incline -- the cone pivot post's journal, the swing
platform's mounting line and the drive-train assembly's ``ROT_Y_INCLINE`` --
imports it from here, so no module can carry a rounded literal that drifts from
the geometry the others build (the post and platform both hard-coded 12.5182
against the assembly's derived 12.518222...).

True-cone exact tracking (``cad/config/machine/cone_incline.yaml``): each
6-tooth step shrinks the pitch radius by ``RADIUS_STEP`` over one drum seat, so
``sin i = RADIUS_STEP / Z_PITCH``.  Pure data: no SolidWorks, no assembly
helpers, safe for any part script to import.
"""

from __future__ import annotations

import math

import _config

DP_TRAIN = _config.machine("gear_train", "diametral_pitch")  # 49.82
RADIUS_STEP = 3.0 * 25.4 / DP_TRAIN  # 1.5295: pitch-radius step per 6 teeth
DRUM_SEAT_NOMINAL = _config.machine("cone_incline", "drum_seat_nominal_mm")  # 7.2204
Z_PITCH = DRUM_SEAT_NOMINAL * math.cos(
    math.asin(RADIUS_STEP / DRUM_SEAT_NOMINAL)
)  # 7.0566: drum z-pitch
SIN_I = RADIUS_STEP / Z_PITCH  # 0.21675
COS_I = math.sqrt(1.0 - SIN_I * SIN_I)  # 0.97623
INCLINE_DEG = math.degrees(math.asin(SIN_I))  # 12.518222...
