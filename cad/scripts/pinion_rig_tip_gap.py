"""The pinion rig's east-west locate on the base: the parked tip gap.

U28 (user, 2026-09-23) parks the pinion out on the level line of centres at
config ``alignment_pinion.disengaged_tip_gap_mm`` (the model's APINION_GAP).
The model parks the cluster with the follower pins a design air (0.10-0.25)
above the eccentric-down cams; on the bench the return spring swings it on
until the pins rest on the cams, so the gap a feeler reads at rest is wider
than the model's.  Main's U28 corollary: the rig is slid in until a feeler set
to that rest gap is snug tooth tip to tooth tip at the front and back
stations, then clamped, and the base seats are spotted through the blocks.

This module derives that rest gap from the drive-train model, rounds it to
the feeler gage's leaf step and makes it up from the same STARRETT 66MA the
rig's other settings use.  It is not a fit-up setting (pinion_rig_fitup
allows those one or two leaves); the tip gap takes three.  Only drawing
steps and tests import it.
"""

from __future__ import annotations

import math

import build_drive_train_assembly as drive
from pinion_rig_fitup import FEELER_GAGE_LEAVES_MM, FEELER_GAGE_NAME
from pinion_rig_layout import FEELER_LEAF_STEP


def _swung(point: tuple[float, float], psi: float) -> tuple[float, float]:
    """``point`` swung ``psi`` (CCW, toward mesh) about the strap pivot."""
    c, s = math.cos(psi), math.sin(psi)
    dx, dy = point[0] - drive.PIVOT_X, point[1] - drive.PIVOT_Y
    return (drive.PIVOT_X + dx * c - dy * s, drive.PIVOT_Y + dx * s + dy * c)


def _pin_air(psi: float) -> float:
    """Follower pin to eccentric-down cam air with the cluster swung ``psi``,
    on the same skew-perpendicular metric the model's park gap uses."""
    c, s = math.cos(psi), math.sin(psi)
    axis = drive._SPR_N  # the pin's axis, parked
    n = (axis[0] * c - axis[1] * s, axis[0] * s + axis[1] * c)
    centre_y = drive.LIFT_Y - drive.CAM_ECC  # the cam axis, eccentric down
    return drive._pin_line_dist(centre_y, c=_swung(drive._FPIN_C, psi), n=n) - (
        drive.FPIN_DIA + drive.CAM_OD
    ) / 2.0


def _tip_gap(psi: float) -> float:
    """Pinion tip to cylinder-gear tip on the line of centres, swung ``psi``."""
    x, y = _swung((drive.APINION_X, drive.APINION_Y), psi)
    return math.hypot(x - drive.X_DRUM, y - drive.Y_DRIVE) - (
        drive.TIP_DRUM120 + drive.TIP_APINION
    )


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
if not math.isclose(MODEL_TIP_GAP, drive.APINION_GAP, abs_tol=1e-9):
    raise AssertionError("the parked pinion is off the level line of centres")
# The gage sets whole leaf steps, so the printed nominal is the rest gap to
# the nearest step.
TIP_GAP_FEELER = round(round(REST_TIP_GAP / FEELER_LEAF_STEP) * FEELER_LEAF_STEP, 2)
# Main's U28 corollary (2026-09-23): the rig is accepted within 0.2 of the
# feeler either way at both stations.
TIP_GAP_ACCEPT_BAND = 0.2
TIP_GAP_ACCEPT = (
    round(TIP_GAP_FEELER - TIP_GAP_ACCEPT_BAND, 2),
    round(TIP_GAP_FEELER + TIP_GAP_ACCEPT_BAND, 2),
)


def leaf_stack(setting: float) -> tuple[float, ...]:
    """The gage leaves that make up ``setting``, thickest first: as many of the
    thickest leaf as fit, then the one leaf for the remainder."""
    thickest = FEELER_GAGE_LEAVES_MM[-1]
    steps, per_leaf = round(setting / FEELER_LEAF_STEP), round(thickest / FEELER_LEAF_STEP)
    count, remainder = divmod(steps, per_leaf)
    leaves = (thickest,) * count
    if remainder:
        leaves += (FEELER_GAGE_LEAVES_MM[remainder - 1],)
    return leaves


TIP_GAP_LEAVES = leaf_stack(TIP_GAP_FEELER)
TIP_GAP_LEAVES_TEXT = " + ".join(f"{leaf:.2f}" for leaf in TIP_GAP_LEAVES)
TIP_GAP_FEELER_TEXT = (
    f"{TIP_GAP_FEELER:.2f} FEELER ({TIP_GAP_LEAVES_TEXT} {FEELER_GAGE_NAME} LEAVES)"
)
TIP_GAP_ACCEPT_TEXT = f"ACCEPT {TIP_GAP_ACCEPT[0]:.2f}-{TIP_GAP_ACCEPT[1]:.2f}"

__all__ = [
    "MODEL_TIP_GAP",
    "REST_TIP_GAP",
    "TIP_GAP_ACCEPT",
    "TIP_GAP_ACCEPT_BAND",
    "TIP_GAP_ACCEPT_TEXT",
    "TIP_GAP_FEELER",
    "TIP_GAP_FEELER_TEXT",
    "TIP_GAP_LEAVES",
    "leaf_stack",
]
