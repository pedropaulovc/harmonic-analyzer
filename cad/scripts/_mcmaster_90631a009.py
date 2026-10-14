"""Pure McMaster 90631A009 catalogue dimensions for its recipe and assemblies.

McMaster 90631A009 product page read live on 2026-10-14:
https://www.mcmaster.com/90631A009/. Low-strength steel nylon-insert
locknut, zinc-plated, standard hex profile, 8-32 UNC, Class 2B, 11/32 in
wide, 15/64 in high.  The page gives no thread length past the insert; the
pen assembly holds at least two full pitches of the screw's thread, its tip
chamfer excluded, standing past the nut's insert face
(``THREAD_PAST_MIN_PITCHES``).  Only the catalogue fields are recorded; no
vendor solid was harvested.

The thread and the nylon insert are not modelled: the hex runs the full
height and the bore is the #8-32 basic major diameter, line-to-line with the
mating screw's modelled thread (the 92671A115 recipe's convention).
"""

from __future__ import annotations

import math

from _hole_spec import THREAD_MAJOR_MM

MM_PER_IN = 25.4
STEEL_G_PER_MM3 = 7.8e-3  # SOLIDWORKS "Plain Carbon Steel"

SKU = "90631A009"
THREAD = "#8-32"
ACROSS_FLATS = 11.0 / 32.0 * MM_PER_IN  # 8.73125
THICKNESS = 15.0 / 64.0 * MM_PER_IN  # 5.953125
BORE_DIA = THREAD_MAJOR_MM[THREAD]  # 4.166
ACROSS_CORNERS = ACROSS_FLATS / math.cos(math.radians(30.0))  # 10.082
THREAD_PAST_MIN_PITCHES = 2


def nut_volume() -> float:
    """The modelled solid, mm^3: hexagonal prism less the bore."""
    hexagon = math.sqrt(3.0) / 2.0 * ACROSS_FLATS**2
    return (hexagon - math.pi / 4.0 * BORE_DIA**2) * THICKNESS


MASS_G = nut_volume() * STEEL_G_PER_MM3
