"""Pure McMaster 95462A505 catalogue dimensions for its recipe and assemblies.

McMaster product page read live on 2026-11-12 (https://www.mcmaster.com/95462A505/,
via GearKit2356.BuyResearch): medium-strength zinc-plated steel hex nut, SAE
grade 5, ASME B18.2.2, 1/4-28 class 2B, 7/16 in wide, 7/32 in high; $8.00 per
pack of 100. Only the catalogue fields are recorded; no vendor solid was
harvested.

The thread is not modelled: the hex runs the full height and the bore is the
1/4-28 basic major diameter, line-to-line with the mating arbor's schematic
thread (the 90480A009 recipe's convention).
"""

from __future__ import annotations

import math

from _hole_spec import THREAD_MAJOR_MM

MM_PER_IN = 25.4
STEEL_G_PER_MM3 = 7.8e-3  # SOLIDWORKS "Plain Carbon Steel"

SKU = "95462A505"
THREAD = "1/4-28"
ACROSS_FLATS = 7.0 / 16.0 * MM_PER_IN  # 11.1125
THICKNESS = 7.0 / 32.0 * MM_PER_IN  # 5.55625
BORE_DIA = THREAD_MAJOR_MM[THREAD]  # 6.350
ACROSS_CORNERS = ACROSS_FLATS / math.cos(math.radians(30.0))  # 12.832


def nut_volume() -> float:
    """The modelled solid, mm^3: hexagonal prism less the bore."""
    hexagon = math.sqrt(3.0) / 2.0 * ACROSS_FLATS**2
    return (hexagon - math.pi / 4.0 * BORE_DIA**2) * THICKNESS


MASS_G = nut_volume() * STEEL_G_PER_MM3
