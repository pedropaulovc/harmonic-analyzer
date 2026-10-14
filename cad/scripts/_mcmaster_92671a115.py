"""Pure McMaster 92671A115 catalogue dimensions for its recipe and assemblies.

McMaster 92671A115 product page read live on 2026-10-13:
https://www.mcmaster.com/92671A115/. Brass hex nut, standard profile, 0-80
UNF, Class 2B, 5/32 in wide, 3/64 in high. Only a 2-D PDF is offered; no
vendor solid was harvested. The narrow-profile brass 0-80 (92736A001,
3/32 in wide) was not chosen.

The thread is not modelled: the bore is the #0-80 basic major diameter,
line-to-line with the mating stud's modelled thread (the 92671A005 recipe's
convention).
"""

from __future__ import annotations

import math

from _hole_spec import THREAD_MAJOR_MM

MM_PER_IN = 25.4
BRASS_G_PER_MM3 = 8.5e-3

SKU = "92671A115"
THREAD = "#0-80"
ACROSS_FLATS = 5.0 / 32.0 * MM_PER_IN  # 3.96875
THICKNESS = 3.0 / 64.0 * MM_PER_IN  # 1.190625
BORE_DIA = THREAD_MAJOR_MM[THREAD]  # 1.524
ACROSS_CORNERS = ACROSS_FLATS / math.cos(math.radians(30.0))


def nut_volume() -> float:
    """The modelled solid, mm^3: hexagonal prism less the bore."""
    hexagon = math.sqrt(3.0) / 2.0 * ACROSS_FLATS**2
    return (hexagon - math.pi / 4.0 * BORE_DIA**2) * THICKNESS


MASS_G = nut_volume() * BRASS_G_PER_MM3
