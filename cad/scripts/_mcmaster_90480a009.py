"""Pure McMaster 90480A009 catalogue dimensions for its recipe and assemblies.

McMaster hex-nut listing read live on 2026-10-14
(https://www.mcmaster.com/products/hex-nuts/thread-size~8-32/hex-nuts-3~~/,
the product page itself needs a login): low-strength zinc-plated steel hex
nut, standard profile, ASME B18.2.2, 8-32 UNC, 11/32 in wide, 1/8 in high.
Only the catalogue fields are recorded; no vendor solid was harvested.

The thread is not modelled: the hex runs the full height and the bore is the
#8-32 basic major diameter, line-to-line with the mating screw's modelled
thread (the 92671A115 recipe's convention).
"""

from __future__ import annotations

import math

from _hole_spec import THREAD_MAJOR_MM

MM_PER_IN = 25.4
STEEL_G_PER_MM3 = 7.8e-3  # SOLIDWORKS "Plain Carbon Steel"

SKU = "90480A009"
THREAD = "#8-32"
ACROSS_FLATS = 11.0 / 32.0 * MM_PER_IN  # 8.73125
THICKNESS = 1.0 / 8.0 * MM_PER_IN  # 3.175
BORE_DIA = THREAD_MAJOR_MM[THREAD]  # 4.166
ACROSS_CORNERS = ACROSS_FLATS / math.cos(math.radians(30.0))  # 10.082


def nut_volume() -> float:
    """The modelled solid, mm^3: hexagonal prism less the bore."""
    hexagon = math.sqrt(3.0) / 2.0 * ACROSS_FLATS**2
    return (hexagon - math.pi / 4.0 * BORE_DIA**2) * THICKNESS


MASS_G = nut_volume() * STEEL_G_PER_MM3
