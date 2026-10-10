"""Cylinder face selector and matching behavior.

Separate from other selectors to keep edits local to specs that construct this type.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from _gtol_face import SURFACE_CYLINDER, FaceGeometry


@dataclass(frozen=True)
class CylinderFace:
    """The unique cylindrical face of ``diameter_mm`` (optionally disambiguated
    by a point its axis span must contain, in part coordinates, mm).

    The three station coordinates are independent and AND together, which is
    what it takes to name ONE bore of a symmetric family: the harmonic base's
    four column sockets share their diameter, depth and height and differ only
    in X and Z, so a diameter (or a diameter and an X) matches two or four
    faces and resolves none of them.
    """

    diameter_mm: float
    contains_x_mm: float | None = None
    contains_y_mm: float | None = None
    contains_z_mm: float | None = None
    tolerance_mm: float = 0.05

    def __post_init__(self) -> None:
        if self.diameter_mm <= 0.0:
            raise ValueError("cylinder diameter must be positive")
        if self.tolerance_mm <= 0.0:
            raise ValueError("cylinder match tolerance must be positive")

    surface_identity: ClassVar[int] = SURFACE_CYLINDER

    def matches(self, geometry: FaceGeometry) -> bool:
        tolerance_m = self.tolerance_mm / 1000.0
        if geometry.identity != SURFACE_CYLINDER:
            return False
        # CylinderParams: origin xyz, axis xyz, radius — meters.  The spec's
        # tolerance is a DIAMETER tolerance, so compare diameter to diameter.
        diameter_m = 2.0 * geometry.parameters[6]
        if abs(diameter_m - self.diameter_mm / 1000.0) > tolerance_m:
            return False
        stations = (self.contains_x_mm, self.contains_y_mm, self.contains_z_mm)
        if all(station is None for station in stations):
            return True
        if len(geometry.box) != 6:
            return False
        for axis, station in enumerate(stations):
            if station is None:
                continue
            value = station / 1000.0
            low = geometry.box[axis] - tolerance_m
            high = geometry.box[axis + 3] + tolerance_m
            if not low <= value <= high:
                return False
        return True
