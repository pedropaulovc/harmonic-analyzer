"""Torus face selector and matching behavior.

Separate from other selectors to keep edits local to specs that construct this type.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from _gtol_face import SURFACE_TORUS, FaceGeometry


@dataclass(frozen=True)
class TorusFace:
    """The unique toroidal face with the specified generating radii."""

    major_radius_mm: float
    minor_radius_mm: float
    center_mm: tuple[float, float, float] | None = None
    tolerance_mm: float = 0.05

    def __post_init__(self) -> None:
        # SolidWorks permits negative major radii for lemon tori, so only the
        # physically positive minor radius is constrained here.
        if self.minor_radius_mm <= 0.0:
            raise ValueError("torus minor radius must be positive")
        if self.center_mm is not None and len(self.center_mm) != 3:
            raise ValueError("torus center must be a 3-vector")
        if self.tolerance_mm <= 0.0:
            raise ValueError("torus match tolerance must be positive")

    surface_identity: ClassVar[int] = SURFACE_TORUS

    def matches(self, geometry: FaceGeometry) -> bool:
        tolerance_m = self.tolerance_mm / 1000.0
        if geometry.identity != SURFACE_TORUS:
            return False
        center = geometry.parameters[0:3]
        major_radius = geometry.parameters[6]
        minor_radius = geometry.parameters[7]
        if abs(major_radius - self.major_radius_mm / 1000.0) > tolerance_m:
            return False
        if abs(minor_radius - self.minor_radius_mm / 1000.0) > tolerance_m:
            return False
        if self.center_mm is None:
            return True
        return all(
            abs(actual - expected / 1000.0) <= tolerance_m
            for actual, expected in zip(center, self.center_mm)
        )
