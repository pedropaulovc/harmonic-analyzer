"""Pure supplier print data, kept separate from exact purchased-pin geometry."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


DIAMETER_FEATURE = "SupplierPinDiameterReference"
DIAMETER_DIMENSION = "SupplierPinDiameter"
MATING_HOLE_FEATURE = "SupplierMatingHoleReference"
MATING_HOLE_DIMENSION = "SupplierMatingHoleDia"
WALL_FEATURE = "SupplierPinWallReference"
WALL_DIMENSION = "SupplierPinWall"
REFERENCE_DIMENSIONS = {
    DIAMETER_FEATURE: {DIAMETER_DIMENSION},
    MATING_HOLE_FEATURE: {MATING_HOLE_DIMENSION},
    WALL_FEATURE: {WALL_DIMENSION},
}


@dataclass(frozen=True)
class SupplierPinReference:
    """Source sizes use supplier units; model sizes stay exact mm.

    Supplier sizes print as untoleranced REF: the catalogue tolerance governs
    (drawing-guidelines), so no supplier band reaches the print.
    """

    sku: str
    units: Literal["in", "mm"]
    diameter_mm: float
    length_mm: float
    diameter_precision: int
    length_precision: int
    wall_mm: float | None = None
    wall_precision: int | None = None
    application_hole_limits: tuple[float, float] | None = None
    application_hole_precision: int | None = None
    # The package's sheet unit (its drawing_unit). An inch sheet already reads
    # UNIT: IN, so an inch source drops its " in" there. The drawing refuses a
    # sheet whose unit differs; a mm part's own document unit is its
    # template's, which differs between farm seats.
    sheet_unit: Literal["in", "mm"] = "mm"

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


def declares_application_hole(source: SupplierPinReference) -> bool:
    """Whether a spring pin carries the supplier application (mating) hole.

    Both application fields or neither: a pin whose mating parts' own sheets
    specify its holes omits the circle, which reads as a second pin feature.
    """
    limits, precision = source.application_hole_limits, source.application_hole_precision
    if (limits is None) != (precision is None):
        raise ValueError(f"{source.sku}: incomplete supplier mating-hole reference")
    return limits is not None
