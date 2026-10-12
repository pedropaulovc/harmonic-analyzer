"""The two chain-wrapped removables' authored mounts, for the interference gate.

Only the assemblies that carry the roller chain import this and pass
``mounted_wheels()`` to ``_assembly.check_no_interference``. Keeping it out of
``_assembly`` keeps the cone line and channel table off every other assembly's
recipe, and out of ``_chain`` keeps the leaf chain-link parts' recipes as they
are.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import _chain
import pd_transgear_removable_spec as removable


@dataclass(frozen=True)
class WheelMounts:
    """Mounted crank and knob wheels: machine-xy centre (pre-mirror) and the
    selected configuration of each, plus the shared axial band."""

    roles: tuple[tuple[tuple[float, float], str], ...]
    band_front_z: float
    seat_face_z: float
    plate: float
    configuration_teeth: Callable[[str], int]


def mounted_wheels() -> WheelMounts:
    """Read the authorities at call time, so the gate sees current values."""
    return WheelMounts(
        roles=(
            (_chain.CRANK_CENTRE, removable.CRANK_CONFIG),
            (_chain.KNOB_CENTRE, removable.KNOB_CONFIG),
        ),
        band_front_z=removable.BAND_FRONT_Z,
        seat_face_z=removable.SEAT_FACE_Z,
        plate=removable.PLATE,
        configuration_teeth=removable.configuration_teeth,
    )
