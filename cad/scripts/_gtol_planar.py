"""Planar face selector and matching behavior.

Separate from other selectors to keep edits local to specs that construct this type.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from _gtol_face import SURFACE_PLANE, FaceGeometry, unit_vector


@dataclass(frozen=True)
class PlanarFace:
    """The unique planar face whose outward normal ≈ ``normal`` and whose plane
    sits at ``offset_mm`` along that normal (part coordinates, mm).

    ``contains_x_mm`` and ``contains_z_mm`` AND together like the cylinder
    stations above: the top frame's four cap-recess floors are COPLANAR (one Y
    offset, one annulus area each), so naming one takes both plan stations.
    """

    normal: tuple[float, float, float]
    offset_mm: float
    contains_z_mm: float | None = None
    contains_x_mm: float | None = None
    tolerance_mm: float = 0.05

    def __post_init__(self) -> None:
        if len(self.normal) != 3 or not any(float(value) for value in self.normal):
            raise ValueError("plane normal must be a non-zero 3-vector")
        if self.tolerance_mm <= 0.0:
            raise ValueError("plane match tolerance must be positive")

    surface_identity: ClassVar[int] = SURFACE_PLANE

    def matches(self, geometry: FaceGeometry) -> bool:
        tolerance_m = self.tolerance_mm / 1000.0
        if geometry.identity != SURFACE_PLANE or geometry.outward_normal is None:
            return False
        want = unit_vector(self.normal)
        if sum(a * b for a, b in zip(geometry.outward_normal, want)) < 0.999:
            return False
        offset = sum(
            point * normal
            for point, normal in zip(geometry.parameters[3:6], geometry.outward_normal)
        )
        if abs(offset - self.offset_mm / 1000.0) > tolerance_m:
            return False
        if self.contains_x_mm is None and self.contains_z_mm is None:
            return True
        if len(geometry.box) != 6:
            return False
        for axis, station in ((0, self.contains_x_mm), (2, self.contains_z_mm)):
            if station is None:
                continue
            value = station / 1000.0
            low = geometry.box[axis] - tolerance_m
            high = geometry.box[axis + 3] + tolerance_m
            if not low <= value <= high:
                return False
        return True
