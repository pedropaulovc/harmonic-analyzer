r"""Pure-data contract of the latch-hook bracket screws (MHA-VN-043).

PURE DATA, no SolidWorks/COM imports.  Two McMaster 90280A108 #4-40 x 3/8
slotted narrow-fillister screws (the foot-screw SKU, contract ruling 2) pass
the latch hook's (MHA-PD-014) 0.8 spring-steel base into the support bar's
#4-40 THROUGH taps (contract §4.3, §7).

Frame (the fillister family's): screw axis +Y, head UP, the under-head
junction at y = 0, the thread running to y = -LENGTH.  The axis is published
as ``ScrewAxis`` (Front ∩ Right).

The bar's thickness, tap drill and tap countersinks belong to the support
bar's slice; ``engagement_worst`` and ``tip_short_worst`` take them as
arguments, so this module never retypes them.  The base sheet under the
head and its stock band are the hook's (``pd_latch_hook_geometry``).
"""

from __future__ import annotations

from vn_swing_stop_screw_spec import FILLISTER_SIZE
from pd_latch_hook_geometry import SHEET_T, SHEET_T_MINUS, SHEET_T_PLUS

SKU = "90280A108"
MAJOR_DIA, LENGTH, HEAD_H, HEAD_DIA, _SLOT_W = FILLISTER_SIZE
# #4-40 UNC-2A major limits, ASME B1.1: 0.1112 / 0.1061 in.
MAJOR_DIA_MIN = 0.1061 * 25.4
PITCH = 25.4 / 40.0  # #4-40 UNC
ENGAGEMENT_FLOOR_D = 1.5  # contract §7 pass line, full thread at the worst case

ENGAGEMENT_NOMINAL = LENGTH - SHEET_T


def _csk_loss(csk_dia_max: float, tap_drill_dia: float) -> float:
    """Thread one tap countersink removes (contract §7): full thread starts
    where its 45° leg meets the tap drill, not the major (R9-63)."""
    return max(0.0, (csk_dia_max - tap_drill_dia) / 2.0)


def engagement_worst(
    csk_dia_max: float, tap_drill_dia: float, exits_through: bool = True
) -> float:
    """Full-thread engagement in the bar tap at the worst case: nominal less
    the thickest sheet, one pitch of incomplete first thread, and the entry
    countersink (and the exit countersink when the tip reaches it)."""
    loss = SHEET_T_PLUS + PITCH + _csk_loss(csk_dia_max, tap_drill_dia)
    if exits_through:
        loss += _csk_loss(csk_dia_max, tap_drill_dia)
    return ENGAGEMENT_NOMINAL - loss


def tip_short_worst(bar_t: float, bar_t_minus: float) -> float:
    """Least distance the tip stays inside the bar's front face: the thinnest
    bar with the thinnest sheet under the head."""
    return (bar_t - bar_t_minus) - (LENGTH - (SHEET_T - SHEET_T_MINUS))


def checked_engagement(
    csk_dia_max: float, tap_drill_dia: float, bar_t: float, bar_t_minus: float
) -> float:
    """Worst engagement in D; raises if it misses 1.5 D or the tip can stand
    proud of the bar's front face (under the platen)."""
    worst_d = engagement_worst(csk_dia_max, tap_drill_dia) / MAJOR_DIA
    if worst_d < ENGAGEMENT_FLOOR_D:
        raise AssertionError(f"bracket screw engagement {worst_d:.2f} D under 1.5 D")
    if tip_short_worst(bar_t, bar_t_minus) <= 0.0:
        raise AssertionError("the bracket screw tip can stand proud of the bar")
    return worst_d
