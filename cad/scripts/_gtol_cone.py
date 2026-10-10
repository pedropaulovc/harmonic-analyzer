"""Cone face selector and matching behavior.

Separate from other selectors to keep edits local to specs that construct this type.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import ClassVar

from _gtol_face import SURFACE_CONE, FaceGeometry


@dataclass(frozen=True)
class ConeFace:
    """The unique conical face with the specified half-angle.

    ``contains_x_mm`` optionally requires the face bounding box to cross a
    part-coordinate X station. This distinguishes coaxial conical patches
    without depending on volatile face enumeration order.
    """

    half_angle_degrees: float
    contains_x_mm: float | None = None
    tolerance_degrees: float = 0.01
    tolerance_mm: float = 0.05

    def __post_init__(self) -> None:
        if not 0.0 < self.half_angle_degrees < 90.0:
            raise ValueError("cone half-angle must be between 0 and 90 degrees")
        if self.tolerance_degrees <= 0.0:
            raise ValueError("cone angle tolerance must be positive")
        if self.tolerance_mm <= 0.0:
            raise ValueError("cone match tolerance must be positive")

    surface_identity: ClassVar[int] = SURFACE_CONE

    def matches(self, geometry: FaceGeometry) -> bool:
        tolerance_m = self.tolerance_mm / 1000.0
        if geometry.identity != SURFACE_CONE:
            return False
        # ConeParams2: origin xyz, axis xyz, reference radius, half-angle,
        # reference direction xyz. The angle is radians.
        if abs(math.degrees(geometry.parameters[7]) - self.half_angle_degrees) > (
            self.tolerance_degrees
        ):
            return False
        if self.contains_x_mm is None:
            return True
        if len(geometry.box) != 6:
            return False
        x = self.contains_x_mm / 1000.0
        return geometry.box[0] - tolerance_m <= x <= geometry.box[3] + tolerance_m
