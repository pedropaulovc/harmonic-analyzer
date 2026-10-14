"""Pure McMaster 90760A009 catalogue dimensions for its recipe and assemblies.

McMaster narrow-profile hex-nut listing read live on 2026-10-14
(https://www.mcmaster.com/products/hex-nuts/thread-size~8-32/narrow-profile-hex-nuts-1~~/,
the product page itself needs a login): zinc-plated steel narrow-profile
(small-pattern) hex nut, 8-32 UNC, right-hand, 1/4 in wide, 3/32 in high.
McMaster's only 8-32 thin-profile hex nuts are left-hand thread, so this
small-pattern nut is the thin right-hand nut.  Only the catalogue fields are
recorded; no vendor solid was harvested.

The thread is not modelled: the hex runs the full height and the bore is the
#8-32 basic major diameter, line-to-line with the mating screw's modelled
thread (the 92671A115 recipe's convention).
"""

from __future__ import annotations

import math

from _hole_spec import THREAD_MAJOR_MM

MM_PER_IN = 25.4
STEEL_G_PER_MM3 = 7.8e-3  # SOLIDWORKS "Plain Carbon Steel"

SKU = "90760A009"
THREAD = "#8-32"
ACROSS_FLATS = 1.0 / 4.0 * MM_PER_IN  # 6.35
THICKNESS = 3.0 / 32.0 * MM_PER_IN  # 2.38125
BORE_DIA = THREAD_MAJOR_MM[THREAD]  # 4.166
ACROSS_CORNERS = ACROSS_FLATS / math.cos(math.radians(30.0))  # 7.332


def nut_volume() -> float:
    """The modelled solid, mm^3: hexagonal prism less the bore."""
    hexagon = math.sqrt(3.0) / 2.0 * ACROSS_FLATS**2
    return (hexagon - math.pi / 4.0 * BORE_DIA**2) * THICKNESS


MASS_G = nut_volume() * STEEL_G_PER_MM3
