"""Intended-fit interference contracts for the drive-train assembly.

Read by ``build_drive_train_assembly`` directly, so only that assembly's recipe
carries the geometry these limits are computed from; ``verify.py`` reaches the
same table through ``_interference_contracts.allowed_interference_pairs``.
"""

from __future__ import annotations

import math
from collections.abc import Mapping

from _interference_contracts import smooth_annulus_limit_mm3
from _hole_spec import blind_cut_dia_mm
from crank_arm_spec import (
    ARM_WIDTH as _ARM_W,
    PIN_HOLE_SPEC as _ARM_PILOT_SPEC,
    SHAFT_BORE_DIA as _ARM_BORE,
)
from crank_pin_spec import (
    BIG_END_DIA as _PIN_D0,
    PIN_LENGTH as _PIN_L,
    SMALL_END_DIA as _PIN_D1,
)
from crankshaft_spec import SHAFT_DIA as _CS_DIA


# Crank taper pin in its PILOT holes (ch11 p.14, 2026-09-02): the released
# drawings drill the arm #14 (4.623) and the shaft #9 (4.978) and taper-ream
# them together at assembly, so the nominal 1:48 pin overlaps both pilots.
# Bound each overlap at 1.10 x the analytic frustum-minus-cylinder volume
# over the span the pin crosses (arm hub minus its shaft bore; shaft diameter).

_CS_PILOT = 4.978  # #9 drill (build_crankshaft's wizard cross-hole)
_PIN_PROUD = 3.85  # build_drive_train_assembly.PIN_PROUD (kept in step by test)


def _pin_overlap(s0: float, s1: float, hole_dia: float) -> float:
    """Volume of the taper pin between axial stations s0..s1 (from the big end)
    that lies OUTSIDE a straight hole of ``hole_dia`` on the same axis."""
    n = 200
    total = 0.0
    for i in range(n):
        s = s0 + (s1 - s0) * (i + 0.5) / n
        d = _PIN_D0 - (_PIN_D0 - _PIN_D1) * s / _PIN_L
        total += max(0.0, math.pi / 4.0 * (d * d - hole_dia * hole_dia)) * (s1 - s0) / n
    return total


_ARM_PILOT = blind_cut_dia_mm(_ARM_PILOT_SPEC)

# hub -X face at s = PIN_PROUD; the shaft bore occupies the middle ARM_BORE of the hub
_ARM_S0, _ARM_S1 = _PIN_PROUD, _PIN_PROUD + _ARM_W
_BORE_S0 = _PIN_PROUD + (_ARM_W - _ARM_BORE) / 2.0
_BORE_S1 = _BORE_S0 + _ARM_BORE
_CS_S0 = _PIN_PROUD + (_ARM_W - _CS_DIA) / 2.0
_CS_S1 = _CS_S0 + _CS_DIA
_CRANK_PIN_ARM_MM3 = _pin_overlap(_ARM_S0, _BORE_S0, _ARM_PILOT) + _pin_overlap(
    _BORE_S1, _ARM_S1, _ARM_PILOT
)
_CRANK_PIN_SHAFT_MM3 = _pin_overlap(_CS_S0, _CS_S1, _CS_PILOT)

# Independent SolidWorks-kernel observations for the exact stock bodies in
# their production receivers.  The 90280A108's modeled helical thread and
# under-head runout overlapped the native #4-40 far jaw by 6.47 mm3 over its
# 2.625 of far-jaw engagement; the cup-tip adjuster makes its intended thrust
# contact with the shaft end at 0.13 mm3.  That is the 45 deg cup's analytic
# (2/3)*pi*r^3 for the 0.79 stub (0.131); rule-12 E11's 94025A164 cup is also
# 45 deg (vendor Sketch2).  The 1/16 in tip land doubles the stub radius, so
# the contact scales by r^3: 0.13 * 8 = 1.04 (analytic 1.047) until the next
# drive-train build re-observes it.  Rule-12 E1 lengthened the pinch
# screw to the 12.7 90280A110 (5.80 in the far jaw), so its limit scales that
# observation by engagement -- an over-estimate, since the runout share does
# not grow -- until the next drive-train build re-observes it.  Ten-percent
# bounded headroom still fails any materially deeper insertion.
# 6.47 * 5.80 / 2.625 = 14.296, rounded up.
_TIP_PINCH_OBSERVED_MM3 = 14.30
_TIP_PINCH_GATE_LIMIT_MM3 = _TIP_PINCH_OBSERVED_MM3 * 1.10
_ADJUSTER_THRUST_GATE_LIMIT_MM3 = 0.13 * 8.0 * 1.10

ALLOWED_PAIRS: Mapping[frozenset[str], float] = {
    frozenset(("crank-pin-1", "crank-arm-1")): 1.10 * _CRANK_PIN_ARM_MM3,
    frozenset(("crank-pin-1", "crankshaft-1")): 1.10 * _CRANK_PIN_SHAFT_MM3,
    # Stock 6.35 shank minus the 1.0 eye wire and 0.02 face clearance.
    frozenset(("fillister-screw-1", "crank-arm-1")): smooth_annulus_limit_mm3(
        2.8448, 2.261, 5.33
    ),
    # Rule-12 E11: #10-32 94025A164 (major 4.826) in the #21 (4.0386) tap
    # drill, ADJUSTER_EMBED 9.5 deep.
    frozenset(("cone-tip-adjuster-1", "cone-tip-block-1")): smooth_annulus_limit_mm3(
        4.826, 4.0386, 9.5
    ),
    frozenset(
        ("cone-tip-pinch-screw-1", "cone-tip-block-1")
    ): _TIP_PINCH_GATE_LIMIT_MM3,
    frozenset(
        ("cone-tip-adjuster-1", "cone-gear-shaft-1")
    ): _ADJUSTER_THRUST_GATE_LIMIT_MM3,
}
