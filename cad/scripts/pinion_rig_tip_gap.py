"""The pinion rig's east-west locate on the base: the parked tip gap.

U28 (user, 2026-09-23) parks the pinion out on the level line of centres at
config ``alignment_pinion.disengaged_tip_gap_mm`` (the model's APINION_GAP).
The model parks the cluster with the follower pins a design air (0.10-0.25)
above the eccentric-down cams; on the bench the return spring swings it on
until the pins rest on the cams, so the gap a feeler reads at rest is wider
than the model's.  Main's U28 corollary: the rig is slid in until a feeler set
to that rest gap is snug tooth tip to tooth tip at the front and back
stations, then clamped, and the base seats are spotted through the blocks.

This module derives that rest gap from the rig's parked geometry (the pure
pinion_rig_park_geometry the assembly places the rig from), rounds it to the
feeler gauge's thousandth and makes it up from the same inch feeler gauge the
rig's other settings use (dt_feeler_leaves).  It is not a fit-up setting
(pinion_rig_fitup allows those one or two leaves); the tip gap is past the
three thickest leaves together, so it takes four.  Only drawing steps and
tests import it.
"""

from __future__ import annotations

import math

import dt_feeler_leaves
import pinion_rig_park_geometry as park
from cone_line import X_DRUM, Y_DRIVE
from dt_pinion_cam_geometry import CAM_OD
from dt_pinion_cam_geometry import ECC as CAM_ECC
from dt_pinion_cam_pin_geometry import PIN_DIA as FPIN_DIA
from dt_drive_train_assembly_sheet import FEELER_PLACES, inch_text
from dt_feeler_leaves import leaf_stack
from pinion_rig_layout import FEELER_LEAF_STEP


def _swung(point: tuple[float, float], psi: float) -> tuple[float, float]:
    """``point`` swung ``psi`` (CCW, toward mesh) about the strap pivot."""
    c, s = math.cos(psi), math.sin(psi)
    dx, dy = point[0] - park.PIVOT_X, point[1] - park.PIVOT_Y
    return (park.PIVOT_X + dx * c - dy * s, park.PIVOT_Y + dx * s + dy * c)


def _pin_air(psi: float) -> float:
    """Follower pin to eccentric-down cam air with the cluster swung ``psi``,
    on the same skew-perpendicular metric the model's park gap uses."""
    c, s = math.cos(psi), math.sin(psi)
    axis = park.SPR_N  # the pin's axis, parked
    n = (axis[0] * c - axis[1] * s, axis[0] * s + axis[1] * c)
    centre_y = park.LIFT_Y - CAM_ECC  # the cam axis, eccentric down
    return park.pin_line_dist(centre_y, c=_swung(park.FPIN_C, psi), n=n) - (
        FPIN_DIA + CAM_OD
    ) / 2.0


def _tip_gap(psi: float) -> float:
    """Pinion tip to cylinder-gear tip on the line of centres, swung ``psi``."""
    x, y = _swung((park.APINION_X, park.APINION_Y), psi)
    return math.hypot(x - X_DRUM, y - Y_DRIVE) - (park.TIP_DRUM120 + park.TIP_APINION)


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
# The gage sets whole thousandths, so the printed nominal is the rest gap to
# the nearest one.
TIP_GAP_FEELER = dt_feeler_leaves.thousandths(round(REST_TIP_GAP / FEELER_LEAF_STEP))
# Main's U28 corollary (2026-09-23): the rig is accepted within 0.2 of the
# feeler either way at both stations.
TIP_GAP_ACCEPT_BAND = 0.2
TIP_GAP_ACCEPT = (
    round(TIP_GAP_FEELER - TIP_GAP_ACCEPT_BAND, 4),
    round(TIP_GAP_FEELER + TIP_GAP_ACCEPT_BAND, 4),
)

TIP_GAP_LEAVES = leaf_stack(TIP_GAP_FEELER)
# The stack's own error and the rounding to the thousandth both sit inside
# the acceptance: a snug stack never sets a rig that check 7 would reject.
TIP_GAP_STACK_ERROR = dt_feeler_leaves.stack_error(TIP_GAP_FEELER)
if abs(TIP_GAP_FEELER - REST_TIP_GAP) + TIP_GAP_STACK_ERROR > TIP_GAP_ACCEPT_BAND:
    raise AssertionError("the tip-gap stack's error leaves the acceptance band")
# MHA-DT-00 prints decimal inch (#290): the setting to the thousandth; the
# drawing's sheet 16 row prints the acceptance, rounded inward.  Its leaves
# print once, by their etched inch size, in the drawing's feeler-stack table.
TIP_GAP_SETTING_TEXT = inch_text(TIP_GAP_FEELER, FEELER_PLACES)
TIP_GAP_FEELER_TEXT = f"{TIP_GAP_SETTING_TEXT} FEELER"

__all__ = [
    "MODEL_TIP_GAP",
    "REST_TIP_GAP",
    "TIP_GAP_ACCEPT",
    "TIP_GAP_ACCEPT_BAND",
    "TIP_GAP_FEELER",
    "TIP_GAP_FEELER_TEXT",
    "TIP_GAP_SETTING_TEXT",
    "TIP_GAP_LEAVES",
    "TIP_GAP_STACK_ERROR",
    "leaf_stack",
]
