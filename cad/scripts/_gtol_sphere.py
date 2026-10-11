"""Sphere face selector and matching behavior.

Separate from other selectors to keep edits local to specs that construct this type.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from _gtol_face import SURFACE_SPHERE, FaceGeometry


@dataclass(frozen=True)
class SphereFace:
    """The unique spherical face of ``diameter_mm`` and optional centre."""

    diameter_mm: float
    center_mm: tuple[float, float, float] | None = None
    tolerance_mm: float = 0.05

    def __post_init__(self) -> None:
        if self.diameter_mm <= 0.0:
            raise ValueError("sphere diameter must be positive")
        if self.center_mm is not None and len(self.center_mm) != 3:
            raise ValueError("sphere center must be a 3-vector")
        if self.tolerance_mm <= 0.0:
            raise ValueError("sphere match tolerance must be positive")

    surface_identity: ClassVar[int] = SURFACE_SPHERE

    def matches(self, geometry: FaceGeometry) -> bool:
        tolerance_m = self.tolerance_mm / 1000.0
        if geometry.identity != SURFACE_SPHERE:
            return False
        center = geometry.parameters[0:3]
        radius = geometry.parameters[3]
        if abs(2.0 * radius - self.diameter_mm / 1000.0) > tolerance_m:
            return False
        if self.center_mm is None:
            return True
        return all(
            abs(actual - expected / 1000.0) <= tolerance_m
            for actual, expected in zip(center, self.center_mm)
        )
