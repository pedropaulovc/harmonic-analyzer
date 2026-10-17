"""Pure McMaster 90760A140 catalogue dimensions for its recipe and assemblies.

McMaster narrow-profile hex-nut listing read live on 2026-10-16
(https://www.mcmaster.com/products/hex-nuts/thread-size~10-24/narrow-profile-hex-nuts-1~~/,
the product page itself needs a login): zinc-plated steel narrow-profile
hex nut, 10-24 UNC class 2B, right-hand, 5/16 in wide, 7/64 in high, with a
material certificate.  Only the catalogue fields are recorded; no vendor
solid was harvested.

The thread is not modelled: the hex runs the full height and the bore is the
#10-24 basic major diameter, line-to-line with the mating screw's modelled
thread (the 92671A115 recipe's convention).
"""

from __future__ import annotations

import math

from _hole_spec import THREAD_MAJOR_MM

MM_PER_IN = 25.4
STEEL_G_PER_MM3 = 7.8e-3  # SOLIDWORKS "Plain Carbon Steel"

SKU = "90760A140"
THREAD = "#10-24"
ACROSS_FLATS = 5.0 / 16.0 * MM_PER_IN  # 7.9375
THICKNESS = 7.0 / 64.0 * MM_PER_IN  # 2.778125
BORE_DIA = THREAD_MAJOR_MM[THREAD]  # 4.826
ACROSS_CORNERS = ACROSS_FLATS / math.cos(math.radians(30.0))  # 9.165


def nut_volume() -> float:
    """The modelled solid, mm^3: hexagonal prism less the bore."""
    hexagon = math.sqrt(3.0) / 2.0 * ACROSS_FLATS**2
    return (hexagon - math.pi / 4.0 * BORE_DIA**2) * THICKNESS


MASS_G = nut_volume() * STEEL_G_PER_MM3
