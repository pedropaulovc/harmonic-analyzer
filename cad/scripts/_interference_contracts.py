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

_DRIVE_TRAIN_ALLOWED_PAIRS = {
    frozenset(("pinion-bracket-1", "pinion-cam-pin-1")):
        _CAM_PIN_GATE_LIMIT_MM3,
    frozenset(("pinion-bracket-2", "pinion-cam-pin-2")):
        _CAM_PIN_GATE_LIMIT_MM3,
}

_BY_ASSEMBLY: dict[str, Mapping[frozenset[str], float]] = {
    "drive-train": _DRIVE_TRAIN_ALLOWED_PAIRS,
}


def allowed_interference_pairs(name: str) -> Mapping[frozenset[str], float]:
    """Return exact intended-fit pairs and maximum overlap volumes for *name*."""
    return _BY_ASSEMBLY.get(name, {})
