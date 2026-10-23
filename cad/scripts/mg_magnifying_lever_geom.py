"""Drawing-free lever pose, threaded bracket station and clamp travel.

The nominal free tip and knife retain their current-main machine positions.
Accepted rods are fitted by tip projection, so their free tips may move.
"""

from __future__ import annotations

import _config
from _printed_tolerance import printed_band_mm
from mg_lever_thread_joint import (
    NECK_HALF_X,
    NECK_THICKNESS,
    NECK_THICKNESS_TOL,
    REQUIRED_FULL_ENGAGEMENT,
    ROD_LENGTH,
    ROD_LENGTH_TOL,
    THREAD_LENGTH,
    THREAD_LENGTH_TOL,
    INCOMPLETE_THREAD_MAX,
    installation_full_overlap,
)

KNIFE_LOCAL_X = 215.0
KNIFE_LOCAL_Y = 5.134
BRACKET_LOCAL_X = float(_config.machine("output", "magnifier_bracket_station_mm"))
CLAMP_LOCAL_X = float(_config.machine("output", "magnifier_clamp_station_mm"))
BRACKET_WINDOW_X = (BRACKET_LOCAL_X - NECK_HALF_X, BRACKET_LOCAL_X + NECK_HALF_X)
# The fitter controls this nonzero projection, not the free tip's position.
# Keep its nominal frame here so assembly metadata does not become a geometry
# dependency (the assembly spec already imports this module).
THREAD_PROJECTION = ROD_LENGTH - BRACKET_LOCAL_X - NECK_HALF_X
THREAD_PROJECTION_TOL = printed_band_mm(2)
INSTALLED_FULL_ENGAGEMENT_MIN = installation_full_overlap(THREAD_PROJECTION, THREAD_PROJECTION_TOL)
INSTALLED_ROOT_CLEARANCE_MIN = (
    THREAD_LENGTH - THREAD_LENGTH_TOL
    - (NECK_THICKNESS + NECK_THICKNESS_TOL)
    - (THREAD_PROJECTION + THREAD_PROJECTION_TOL)
    - INCOMPLETE_THREAD_MAX
)
if INSTALLED_ROOT_CLEARANCE_MIN < 0.0:
    raise AssertionError("MG incomplete root runout enters the fitted receiver")
if INSTALLED_FULL_ENGAGEMENT_MIN < REQUIRED_FULL_ENGAGEMENT:
    raise AssertionError("MG fitted lever loses 1.5D of FULL thread overlap")
if THREAD_PROJECTION - THREAD_PROJECTION_TOL < 0.0:
    raise AssertionError("MG fitted threaded tip must reach the bracket's far face")


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

    The bracket and knife remain fixed relative to one another. The fitter
    sets the threaded tip's projection from the far face, so overall length,
    projection and neck thickness move the free tip. Compute both end stops
    in that same fitted frame; rod length cancels at the thread-root stop.
    These are component bounds, not an all-machine articulation proof.
    As-made inspection may admit more travel, but published capacity does
    not credit it.
    """
    from mg_lever_thread_joint import (
        ROD_DIA,
        ROD_DIA_BAND,
    )
    from mg_magnifying_clamp_geom import STOCK_ENVELOPE_MAX, WALL_FLOOR

    if STOCK_ENVELOPE_MAX <= 0.0 or WALL_FLOOR <= 0.0:
        raise AssertionError("MG travel needs a bounded finished hex with its tap axis inside")
    knife_to_bracket = KNIFE_LOCAL_X - BRACKET_LOCAL_X
    thick_min = NECK_THICKNESS - NECK_THICKNESS_TOL
    thick_max = NECK_THICKNESS + NECK_THICKNESS_TOL
    projection_min = THREAD_PROJECTION - THREAD_PROJECTION_TOL
    projection_max = THREAD_PROJECTION + THREAD_PROJECTION_TOL
    thread_stop = knife_to_bracket - thick_min / 2.0 - projection_min + THREAD_LENGTH + THREAD_LENGTH_TOL
    bracket_stop = knife_to_bracket + thick_max / 2.0
    knife_to_free_tip_min = knife_to_bracket - thick_max / 2.0 - projection_max + ROD_LENGTH - ROD_LENGTH_TOL
    band = (
        max(thread_stop, bracket_stop) + STOCK_ENVELOPE_MAX,
        KNIFE_LOCAL_X - CLAMP_LOCAL_X,
        knife_to_free_tip_min - (ROD_DIA + ROD_DIA_BAND[0]) / 2.0 - STOCK_ENVELOPE_MAX,
    )
    if not band[0] <= band[1] <= band[2]:
        raise AssertionError("MG built clamp station is outside its conservative component travel")
    return band
