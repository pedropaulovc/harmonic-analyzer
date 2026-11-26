"""The pinion rig's east-west locate on the base: a 3/32 rod tip to tip.

U28 (user, 2026-09-23) parks the pinion out on the level line of centres at
config ``alignment_pinion.disengaged_tip_gap_mm`` (the model's APINION_GAP).
The model parks the cluster with the follower pins a design air (0.10-0.25)
above the eccentric-down cams; on the bench the return spring swings it on
until the pins rest on the cams, so the gap at rest is wider than the
model's.  Owner ruling 2026-11-24, fit audit part 2 C8 ("Yes, a 3/32
rod."): the rig is slid in until a 3/32 rod is snug tooth tip to tooth tip at
the front and back stations, then clamped, and the base seats are spotted
through the blocks; the leaf stack and its acceptance window (an agent's)
are gone, and step 5C turns the lever until the teeth seat.

This module derives the rest gap from the rig's parked geometry (the pure
pinion_rig_park_geometry the assembly places the rig from) and proves the
rod: the parked pinion stays clear of every cylinder gear, and the cam still
swings the pinion past the standard centre, where the teeth seat.  Only
drawing steps and tests import it.
"""

from __future__ import annotations

import math

import pinion_rig_park_geometry as park
from cone_line import X_DRUM, Y_DRIVE
from dt_cylinder_gear_spec import MODULE_MM, OUTSIDE_DIA_BAND as DRUM_TIP_BAND
from dt_cylinder_gear_spec import TEETH as DRUM_TEETH
from dt_pinion_cam_geometry import CAM_OD
from dt_pinion_cam_geometry import ECC as CAM_ECC
from dt_pinion_cam_pin_geometry import PIN_DIA as FPIN_DIA


def _swung(point: tuple[float, float], psi: float) -> tuple[float, float]:
    """``point`` swung ``psi`` (CCW, toward mesh) about the strap pivot."""
    c, s = math.cos(psi), math.sin(psi)
    dx, dy = point[0] - park.PIVOT_X, point[1] - park.PIVOT_Y
    return (park.PIVOT_X + dx * c - dy * s, park.PIVOT_Y + dx * s + dy * c)


def _pin_air(psi: float, ecc: float = -CAM_ECC) -> float:
    """Follower pin to cam air with the cluster swung ``psi``, on the same
    skew-perpendicular metric the model's park gap uses: the cam eccentric
    down (``ecc`` negative) or up."""
    c, s = math.cos(psi), math.sin(psi)
    axis = park.SPR_N  # the pin's axis, parked
    n = (axis[0] * c - axis[1] * s, axis[0] * s + axis[1] * c)
    centre_y = park.LIFT_Y + ecc  # the cam axis
    return park.pin_line_dist(centre_y, c=_swung(park.FPIN_C, psi), n=n) - (
        FPIN_DIA + CAM_OD
    ) / 2.0


def _centre(psi: float, nearer: float = 0.0) -> float:
    """Pinion to cylinder-gear centre distance, swung ``psi``, the rig slid
    ``nearer`` toward the bank (along the level line of centres)."""
    x, y = _swung((park.APINION_X, park.APINION_Y), psi)
    return math.hypot(x - nearer - X_DRUM, y - Y_DRIVE)


def _tip_gap(psi: float) -> float:
    """Pinion tip to cylinder-gear tip on the line of centres, swung ``psi``."""
    return _centre(psi) - (park.TIP_DRUM120 + park.TIP_APINION)


def _rest_swing() -> float:
    """The disengaging (clockwise, negative) swing that sets the pins on the
    cams: bisected between the model's park and a swing past contact."""
    lo, hi = -0.2, 0.0
    if not _pin_air(lo) < 0.0 < _pin_air(hi):
        raise AssertionError("the rest swing is not bracketed")
    for _ in range(80):
        mid = (lo + hi) / 2.0
        if _pin_air(mid) > 0.0:
            hi = mid
        else:
            lo = mid
    return (lo + hi) / 2.0


MODEL_TIP_GAP = _tip_gap(0.0)
REST_TIP_GAP = _tip_gap(_rest_swing())
if not math.isclose(MODEL_TIP_GAP, park.APINION_GAP, abs_tol=1e-9):
    raise AssertionError("the parked pinion is off the level line of centres")
# Owner ruling C8: a 3/32 rod (drill rod or a drill's shank), read as a single
# limit within .0005 of its size.
TIP_GAP_ROD_TEXT = "3/32 ROD"
TIP_GAP_ROD = 25.4 * 3.0 / 32.0
TIP_GAP_ROD_TOLERANCE = 0.0127
# The rod is set on gears 0 and 19 as cut; any other cylinder gear may stand
# up to its tip band's width taller in radius, and the pinion is one drum, so
# at rest the pinion clears every gear by at least this.
PARKED_TIP_CLEARANCE_MIN = (
    TIP_GAP_ROD - TIP_GAP_ROD_TOLERANCE - (DRUM_TIP_BAND[0] - DRUM_TIP_BAND[1]) / 2.0
)
if PARKED_TIP_CLEARANCE_MIN <= 0.0:
    raise AssertionError("the 3/32 rod lets the parked pinion touch a cylinder gear")
# Set on the rod the rig stands REST_TIP_GAP - rod nearer the bank than the
# model's rest.  Step 5C turns the lever until the teeth seat: the cam, turned
# eccentric up, must still swing the pinion past the standard centre with
# lift to spare at either end of the rod's size (the cam's reach past first
# touch, on the pin-to-cam metric above).
STANDARD_CENTRE = (park.APINION_TEETH + DRUM_TEETH) * MODULE_MM / 2.0


def _reach_at_standard_centre(rod: float) -> float:
    nearer = REST_TIP_GAP - rod
    lo, hi = 0.0, 0.4
    if not _centre(lo, nearer) > STANDARD_CENTRE > _centre(hi, nearer):
        raise AssertionError("the standard centre is not bracketed by the swing")
    for _ in range(80):
        mid = (lo + hi) / 2.0
        if _centre(mid, nearer) > STANDARD_CENTRE:
            lo = mid
        else:
            hi = mid
    return -_pin_air((lo + hi) / 2.0, CAM_ECC)


CAM_REACH_AT_STANDARD_CENTRE_MIN = min(
    _reach_at_standard_centre(TIP_GAP_ROD + sign * TIP_GAP_ROD_TOLERANCE)
    for sign in (-1.0, 1.0)
)
if CAM_REACH_AT_STANDARD_CENTRE_MIN <= 0.0:
    raise AssertionError("on the 3/32 rod the cam no longer reaches the seated mesh")

__all__ = [
    "CAM_REACH_AT_STANDARD_CENTRE_MIN",
    "MODEL_TIP_GAP",
    "PARKED_TIP_CLEARANCE_MIN",
    "REST_TIP_GAP",
    "STANDARD_CENTRE",
    "TIP_GAP_ROD",
    "TIP_GAP_ROD_TEXT",
    "TIP_GAP_ROD_TOLERANCE",
]
