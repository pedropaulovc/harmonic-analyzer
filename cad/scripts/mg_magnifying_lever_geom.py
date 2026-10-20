"""Drawing-free lever pose, threaded bracket station and clamp travel.

The free tip and knife axis retain their current-main machine positions. Only
its threaded end grows to pass the thicker bracket; it is not a pivot pin.
"""

from __future__ import annotations

import _config
from mg_lever_thread_joint import (
    NECK_HALF_X,
    REQUIRED_FULL_ENGAGEMENT,
    ROD_LENGTH,
    ROD_LENGTH_TOL,
    NECK_THICKNESS_TOL,
    FULL_THREAD_START_MAX,
    full_thread_overlap,
)

KNIFE_LOCAL_X = 215.0
KNIFE_LOCAL_Y = 5.134
BRACKET_LOCAL_X = float(_config.machine("output", "magnifier_bracket_station_mm"))
CLAMP_LOCAL_X = float(_config.machine("output", "magnifier_clamp_station_mm"))
BRACKET_WINDOW_X = (BRACKET_LOCAL_X - NECK_HALF_X, BRACKET_LOCAL_X + NECK_HALF_X)
FULL_THREAD_OVERLAP_MIN = full_thread_overlap(BRACKET_LOCAL_X)
TIP_PROJECTION_MIN = ROD_LENGTH - ROD_LENGTH_TOL - (BRACKET_WINDOW_X[1] + NECK_THICKNESS_TOL / 2.0)
ROOT_RUNOUT_CLEARANCE_MIN = BRACKET_LOCAL_X - NECK_HALF_X - NECK_THICKNESS_TOL / 2.0 - FULL_THREAD_START_MAX
if ROOT_RUNOUT_CLEARANCE_MIN < 0.0:
    raise AssertionError("MG incomplete root runout enters the receiver")
if FULL_THREAD_OVERLAP_MIN < REQUIRED_FULL_ENGAGEMENT:
    raise AssertionError("MG installed lever loses 1.5D of FULL thread overlap")
if TIP_PROJECTION_MIN < 0.0:
    raise AssertionError("MG lever's threaded tip must reach the bracket's far face")


def clamp_radius_band(block_depth: float) -> tuple[float, float, float]:
    """Nominal permitted plain-body travel, working pose and free-tip limit.

    There is no invented positive stop: the fitter keeps the complete clamp
    bore on the plain body, outside the incomplete root runout/thread.
    """
    from mg_lever_thread_joint import THREAD_ROOT_X

    half = block_depth / 2.0
    nearest = min(BRACKET_WINDOW_X[0], THREAD_ROOT_X) - half
    farthest = half
    return (KNIFE_LOCAL_X - nearest, KNIFE_LOCAL_X - CLAMP_LOCAL_X, KNIFE_LOCAL_X - farthest)
