"""Pure supplier print data, kept separate from exact purchased-pin geometry."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


MATING_HOLE_FEATURE = "SupplierMatingHoleReference"
MATING_HOLE_DIMENSION = "SupplierMatingHoleDia"
WALL_FEATURE = "SupplierPinWallReference"
WALL_DIMENSION = "SupplierPinWall"
REFERENCE_DIMENSIONS = {
    MATING_HOLE_FEATURE: {MATING_HOLE_DIMENSION},
    WALL_FEATURE: {WALL_DIMENSION},
}


@dataclass(frozen=True)
class SupplierPinReference:
    """Source nominal/band use supplier units; model sizes stay exact mm.

    ``diameter_band`` is (lower, upper), not an incoming inspection control.
    A source nominal different from the model is presented by equivalent
    native limits, never by changing geometry or replacing numeric text.
    """

    sku: str
    units: Literal["in", "mm"]
    diameter_mm: float
    length_mm: float
    diameter_nominal: float
    diameter_precision: int
    length_precision: int
    diameter_band: tuple[float, float] | None = None
    wall_mm: float | None = None
    wall_precision: int | None = None
    application_hole_limits: tuple[float, float] | None = None
    application_hole_precision: int | None = None

    @property
    def unit_mm(self) -> float:
        return 25.4 if self.units == "in" else 1.0

    @property
    def application_hole_center(self) -> tuple[float, float]:
        """Right-plane sketch coordinates, separate from the pin end profile.

        This offset is diagram placement only. The circle is a supplier
        application reference, not another body or a hole cut in the pin.
        """
        return (3.0 * self.diameter_mm, 0.0)
