"""Pure supplier print data, kept separate from exact purchased-pin geometry."""

from __future__ import annotations

import math
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
    # The package's sheet unit (its drawing_unit). An inch sheet already reads
    # UNIT: IN, so an inch source drops its " in" there. The drawing refuses a
    # sheet whose unit differs; a mm part's own document unit is its
    # template's, which differs between farm seats.
    sheet_unit: Literal["in", "mm"] = "mm"

    @property
    def unit_mm(self) -> float:
        return 25.4 if self.units == "in" else 1.0

    @property
    def diameter_uses_limits(self) -> bool:
        """Present a discrepant print nominal as limits on the exact carrier."""
        return self.diameter_band is not None and not math.isclose(
            self.diameter_nominal * self.unit_mm, self.diameter_mm,
            rel_tol=0.0, abs_tol=1e-8,
        )

    @property
    def diameter_deviations_mm(self) -> tuple[float, float]:
        """Signed drawing-source interval relative to the unchanged model OD."""
        if self.diameter_band is None:
            raise ValueError(f"{self.sku}: supplier diameter has no source band")
        lower, upper = self.diameter_band
        return (
            (self.diameter_nominal + lower) * self.unit_mm - self.diameter_mm,
            (self.diameter_nominal + upper) * self.unit_mm - self.diameter_mm,
        )

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