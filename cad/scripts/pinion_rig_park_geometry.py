"""Pure parked geometry of the alignment-pinion rig, in the machine x-y plane.

The pinion drum's parked station, the strap pivot it swings on, the strap's
lean and the follower pin's line, and the lift axis the eccentric cams turn
on.  build_drive_train_assembly places the rig from these, and the MHA-A03 fit-up
text (pinion_rig_tip_gap) derives the bench rest gap from the same numbers,
so neither reads the other and no library module reaches a build script (#880).

Placement only: no SolidWorks, no gates.  The assembly script keeps every
clearance and design-band assertion on these values.
"""

from __future__ import annotations

import math

import _config
from cone_line import DP_TRAIN, X_DRUM, Y_BASE_TOP, Y_DRIVE
from pinion_bracket_geometry import C2C as STRAP_C2C
from pinion_bracket_geometry import PIN_DROP as FPIN_DROP
from pinion_cam_geometry import CAM_OD, ECC as CAM_ECC
from pinion_cam_pin_geometry import PIN_DIA
from pinion_pivot_block_geometry import LIFT_BORE_RISE, LIFT_BORE_SPACING
from pinion_rig_layout import FEELER_LEAF_STEP

# --- alignment pinion (ch. 25): saved rest is live cam contact ---------------
# U28's level-centre construction fixes the block/pivot seats.  With the
# eccentric cam pointing down it left 0.161 mm of air at the follower; the
# return spring actually swings the rigid strap group clockwise onto that cam.
# Save that physical rest pose, not the construction pose.  The configured
# 2.2425 mm is the level-centre construction tip gap, NOT the saved tooth gap.
APINION_TEETH = int(_config.machine("alignment_pinion", "teeth"))
TIP_APINION = ((APINION_TEETH + 2.0) / DP_TRAIN) * 25.4 / 2.0
TIP_DRUM120 = (122.0 / DP_TRAIN) * 25.4 / 2.0
APINION_GAP = float(_config.machine("alignment_pinion", "disengaged_tip_gap_mm"))
_LEVEL_APINION = (X_DRUM + TIP_DRUM120 + TIP_APINION + APINION_GAP, Y_DRIVE)
PIVOT_Y = Y_BASE_TOP + 12.0
PIVOT_X = _LEVEL_APINION[0] + math.sqrt(
    STRAP_C2C**2 - (_LEVEL_APINION[1] - PIVOT_Y) ** 2
)
LIFT_X = PIVOT_X + LIFT_BORE_SPACING
LIFT_Y = PIVOT_Y + LIFT_BORE_RISE

_RADII = (CAM_OD + PIN_DIA) / 2.0
_LEVEL_LEAN = math.atan2(PIVOT_X - _LEVEL_APINION[0], _LEVEL_APINION[1] - PIVOT_Y)


def swung(point: tuple[float, float], angle: float) -> tuple[float, float]:
    """Rotate a machine XY point about the fixed strap pivot (angle in radians)."""
    c, s = math.cos(angle), math.sin(angle)
    x, y = point[0] - PIVOT_X, point[1] - PIVOT_Y
    return (PIVOT_X + x * c - y * s, PIVOT_Y + x * s + y * c)


def _pin_frame(angle: float) -> tuple[tuple[float, float], tuple[float, float]]:
    th = -_LEVEL_LEAN - angle  # (sin th, cos th) turns by -delta-th
    u = (math.sin(th), math.cos(th))
    n = (-math.cos(th), math.sin(th))
    return (PIVOT_X - FPIN_DROP * u[0], PIVOT_Y - FPIN_DROP * u[1]), n


def pin_line_dist(
    centre_y: float,
    c: tuple[float, float] | None = None,
    n: tuple[float, float] | None = None,
    centre_x: float | None = None,
) -> float:
    """Perpendicular distance from a cam OD axis to the pin shank axis."""
    c = FPIN_C if c is None else c
    n = SPR_N if n is None else n
    x = LIFT_X if centre_x is None else centre_x
    dx, dy = x - c[0], centre_y - c[1]
    return abs(dx * (-n[1]) - dy * (-n[0]))


def pin_contact_station(cam_angle: float, swing: float) -> float:
    """Cam-axis projection along the follower pin from the strap centreline, mm.

    This is the closest station of the two perpendicular cylinder axes, not
    the pin's crossing of the fixed lift-rod x plane.
    """
    c, n = _pin_frame(REST_SWING_RAD + swing)
    dx = LIFT_X + CAM_ECC * math.sin(cam_angle) - c[0]
    dy = LIFT_Y - CAM_ECC * math.cos(cam_angle) - c[1]
    return -(dx * n[0] + dy * n[1])


def cam_pin_gap(cam_angle: float, swing: float) -> float:
    """Signed OD-to-shank air; cam and swing angles are radians from rest."""
    c, n = _pin_frame(REST_SWING_RAD + swing)
    return pin_line_dist(
        LIFT_Y - CAM_ECC * math.cos(cam_angle),
        c=c,
        n=n,
        centre_x=LIFT_X + CAM_ECC * math.sin(cam_angle),
    ) - _RADII


def _construction_air(swing: float) -> float:
    c, n = _pin_frame(swing)
    return pin_line_dist(LIFT_Y - CAM_ECC, c=c, n=n) - _RADII


# The negative root is the first touch as the spring swings the drum OUT of
# mesh.  It is derived from the same skew-perpendicular metric as the mate and
# the A03 feeler.  A hardcoded rotation would silently drift when a pin changes.
_lo, _hi = -0.2, 0.0
if not _construction_air(_lo) < 0.0 < _construction_air(_hi):
    raise AssertionError("cam-to-pin rest contact is not bracketed")
for _ in range(80):
    mid = (_lo + _hi) / 2.0
    if _construction_air(mid) > 0.0:
        _hi = mid
    else:
        _lo = mid
REST_SWING_RAD = (_lo + _hi) / 2.0
APINION_X, APINION_Y = swung(_LEVEL_APINION, REST_SWING_RAD)
STRAP_LEAN_DEG = math.degrees(_LEVEL_LEAN + REST_SWING_RAD)
FPIN_C, SPR_N = _pin_frame(REST_SWING_RAD)
SPR_U = (SPR_N[1], -SPR_N[0])
REST_TIP_GAP = math.hypot(APINION_X - X_DRUM, APINION_Y - Y_DRIVE) - (
    TIP_DRUM120 + TIP_APINION
)

# Bench locate and finished acceptance share this one geometry/feeler interval.
# Build gates consume it without importing print-facing rig-fitup contracts.
TIP_GAP_FEELER = round(round(REST_TIP_GAP / FEELER_LEAF_STEP) * FEELER_LEAF_STEP, 2)
TIP_GAP_ACCEPT_BAND = 0.2
TIP_GAP_ACCEPT = (
    round(TIP_GAP_FEELER - TIP_GAP_ACCEPT_BAND, 2),
    round(TIP_GAP_FEELER + TIP_GAP_ACCEPT_BAND, 2),
)
if abs(cam_pin_gap(0.0, 0.0)) > 1e-10:
    raise AssertionError("saved cam-to-pin rest pose is not tangent")
