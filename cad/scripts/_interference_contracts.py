"""Explicit, volume-bounded interference-fit contracts for assembly gates.

Most nominal CAD solids must never overlap. A small set of manufactured
interference fits intentionally do; keeping those exceptions here lets both
the assembly build and the reopened soundness gate apply the same exact pair
and maximum-volume contract.
"""

from __future__ import annotations

import math
from collections.abc import Mapping

from pinion_bracket_geometry import PIN_BORE, PIN_SEAT
from pinion_cam_pin_geometry import PIN_DIA

_CAM_PIN_OVERLAP_MM3 = math.pi * (PIN_DIA**2 - PIN_BORE**2) * PIN_SEAT / 4.0
_CAM_PIN_GATE_LIMIT_MM3 = 1.10 * _CAM_PIN_OVERLAP_MM3

# Crank taper pin in its PILOT holes (ch11 p.14, 2026-09-02): the released
# drawings drill the arm #14 (4.623) and the shaft #9 (4.978) and taper-ream
# them together at assembly, so the nominal 1:48 pin overlaps both pilots.
# Bound each overlap at 1.10 x the analytic frustum-minus-cylinder volume
# over the span the pin crosses (arm hub minus its shaft bore; shaft diameter).
from crank_arm_spec import ARM_WIDTH as _ARM_W, PIN_HOLE_DIA as _ARM_PILOT, SHAFT_BORE_DIA as _ARM_BORE  # noqa: E402
from crank_pin_spec import BIG_END_DIA as _PIN_D0, PIN_LENGTH as _PIN_L, SMALL_END_DIA as _PIN_D1  # noqa: E402
from crankshaft_spec import SHAFT_DIA as _CS_DIA  # noqa: E402

_CS_PILOT = 4.978  # #9 drill (build_crankshaft's wizard cross-hole)
_PIN_PROUD = 3.0  # build_drive_train_assembly.PIN_PROUD (kept in step by test)


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


# hub -X face at s = PIN_PROUD; the shaft bore occupies the middle ARM_BORE of the hub
_ARM_S0, _ARM_S1 = _PIN_PROUD, _PIN_PROUD + _ARM_W
_BORE_S0 = _PIN_PROUD + (_ARM_W - _ARM_BORE) / 2.0
_BORE_S1 = _BORE_S0 + _ARM_BORE
_CS_S0 = _PIN_PROUD + (_ARM_W - _CS_DIA) / 2.0
_CS_S1 = _CS_S0 + _CS_DIA
_CRANK_PIN_ARM_MM3 = _pin_overlap(_ARM_S0, _BORE_S0, _ARM_PILOT) + _pin_overlap(_BORE_S1, _ARM_S1, _ARM_PILOT)
_CRANK_PIN_SHAFT_MM3 = _pin_overlap(_CS_S0, _CS_S1, _CS_PILOT)

_DRIVE_TRAIN_ALLOWED_PAIRS = {
    frozenset(("crank-pin-1", "crank-arm-1")): 1.10 * _CRANK_PIN_ARM_MM3,
    frozenset(("crank-pin-1", "crankshaft-1")): 1.10 * _CRANK_PIN_SHAFT_MM3,
    frozenset(("pinion-bracket-1", "pinion-cam-pin-1")):
        _CAM_PIN_GATE_LIMIT_MM3,
    frozenset(("pinion-bracket-2", "pinion-cam-pin-2")):
        _CAM_PIN_GATE_LIMIT_MM3,
}

# The cone-platform pivot screw's modeled thread envelope intentionally equals
# the harmonic-base tap-drill cylinder. SolidWorks reports a 0.06 mm^3 overlap
# at that coincident threaded-seat boundary; keep the exact nested pair bounded
# so any deeper engagement or neighboring clash still fails the gate.
_HARMONIC_ANALYZER_ALLOWED_PAIRS = {
    frozenset((
        "frame-1/harmonic-base-1",
        "drive-train-1/cone-pivot-screw-1",
    )): 0.10,
}

_BY_ASSEMBLY: dict[str, Mapping[frozenset[str], float]] = {
    "drive-train": _DRIVE_TRAIN_ALLOWED_PAIRS,
    "harmonic-analyzer": _HARMONIC_ANALYZER_ALLOWED_PAIRS,
}


def allowed_interference_pairs(name: str) -> Mapping[frozenset[str], float]:
    """Return exact intended-fit pairs and maximum overlap volumes for *name*."""
    return _BY_ASSEMBLY.get(name, {})
