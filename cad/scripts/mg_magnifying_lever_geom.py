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
    """Nominal geometric plain-body range, working pose and free-end limit.

    This is not an accepted-part operating guarantee or a positive stop.
    Capacity/setup consumers use operating_clamp_radius_band instead; model
    visualization can retain these nominal dimensions. The complete bore
    excludes both the thread runout and the free hemisphere.
    """
    from mg_lever_thread_joint import ROD_DIA, THREAD_ROOT_X

    half = block_depth / 2.0
    nearest = min(BRACKET_WINDOW_X[0], THREAD_ROOT_X) - half
    farthest = ROD_DIA / 2.0 + half
    return (KNIFE_LOCAL_X - nearest, KNIFE_LOCAL_X - CLAMP_LOCAL_X, KNIFE_LOCAL_X - farthest)


def operating_clamp_radius_band() -> tuple[float, float, float]:
    """Conservative component travel for published capacity and setup.

    Station is the actual bottom rod/tap axis at its seat. A complete standard
    tapped hole with the ordinary policy wall floor puts that point INSIDE
    the finished body. The derived full-height HEX envelope bounds either
    bore end from that station without assuming centring. Do not divide it
    by two or add another locating-error allowance to it.

    The shortest rod/longest threaded extent owns the earliest plain-body
    boundary; that extent already includes incomplete root runout. The
    opposite stop excludes the largest accepted free hemisphere. The earliest
    bracket face is checked too. These are component/body bounds in the
    existing knife/free-tip frame, not an all-machine articulation proof:
    the minimum-pose native gate remains open. As-made inspection may admit
    more travel, but published capacity does not credit it.
    """
    from mg_lever_thread_joint import (
        NECK_THICKNESS,
        ROD_DIA,
        ROD_DIA_BAND,
        THREAD_LENGTH,
        THREAD_LENGTH_TOL,
    )
    from mg_magnifying_clamp_geom import STOCK_ENVELOPE_MAX, WALL_FLOOR

    if STOCK_ENVELOPE_MAX <= 0.0 or WALL_FLOOR <= 0.0:
        raise AssertionError("MG travel needs a bounded finished hex with its tap axis inside")
    earliest_runout = ROD_LENGTH - ROD_LENGTH_TOL - (THREAD_LENGTH + THREAD_LENGTH_TOL)
    earliest_bracket = BRACKET_LOCAL_X - (NECK_THICKNESS + NECK_THICKNESS_TOL) / 2.0
    nearest_station = min(earliest_runout, earliest_bracket) - STOCK_ENVELOPE_MAX
    farthest_station = (ROD_DIA + ROD_DIA_BAND[0]) / 2.0 + STOCK_ENVELOPE_MAX
    band = (
        KNIFE_LOCAL_X - nearest_station,
        KNIFE_LOCAL_X - CLAMP_LOCAL_X,
        KNIFE_LOCAL_X - farthest_station,
    )
    if not band[0] <= band[1] <= band[2]:
        raise AssertionError("MG built clamp station is outside its conservative component travel")
    return band
