"""Pure McMaster 91255A539 catalogue dimensions for its recipe and assemblies.

McMaster product page read live on 2026-11-17 (https://www.mcmaster.com/91255A539/):
Black-Oxide Button Head Hex-Drive Screw, alloy steel, 1/4"-20 UNC, class 3A,
right hand, 5/8" long (measured from under the head), fully threaded, flat
tip; button head, standard profile, 0.437" diameter x 0.132" high; 5/32"
hex drive; 140,000 psi, Rockwell C39; ASME B18.3, ASTM F835; $11.55 per
pack of 50.

Head form from McMaster's own model (``91255A539_Button Head Hex Drive
Screw.STEP``, downloaded from the product page 2026-11-17, SHA-256
e5ad67ac...25d7667, probed headless with FreeCAD 1.1; not tracked): a
spherical dome R 6.13936 whose centre stands 2.12203 below the bearing
face, cut flat at the head height; socket floor 1.844 below the head top;
a 45 deg tip chamfer from the major to Ø.175. Its solid is 592.448 mm^3
with the thread.

The model keeps the catalogue head diameter as a plain cylinder up to the
dome (the vendor's 10 deg side and .007 edge rounds are not modelled), the
shank a plain cylinder at the 1/4-20 basic major (the thread is not
modelled), the socket flat-floored without its entry countersink.
"""

from __future__ import annotations

import math

MM_PER_IN = 25.4

SKU = "91255A539"
THREAD = "1/4-20"
HEAD_DIA = 0.437 * MM_PER_IN  # 11.0998
HEAD_HEIGHT = 0.132 * MM_PER_IN  # 3.3528
LENGTH = 0.625 * MM_PER_IN  # 15.875, under the head
MAJOR_DIA = 0.250 * MM_PER_IN  # 6.350
SOCKET_AF = 5.0 / 32.0 * MM_PER_IN  # 3.96875
SOCKET_DEPTH = 1.844
DOME_R = 6.13936
DOME_CENTER_Y = -2.12203  # below the bearing face
TIP_CHAMFER = 0.9525
STEP_VOLUME = 592.4479

# Where the dome meets the head's side, and the head top's flat radius.
SIDE_TOP_Y = DOME_CENTER_Y + math.sqrt(DOME_R**2 - (HEAD_DIA / 2.0) ** 2)
TOP_FLAT_R = math.sqrt(DOME_R**2 - (HEAD_HEIGHT - DOME_CENTER_Y) ** 2)
if not 0.0 < SIDE_TOP_Y < HEAD_HEIGHT or not 0.0 < TOP_FLAT_R < HEAD_DIA / 2.0:
    raise AssertionError("the 91255A539 dome does not meet its head")


def _dome_slab(y0: float, y1: float) -> float:
    """Volume of the dome sphere between heights y0 and y1."""

    def primitive(y: float) -> float:
        t = y - DOME_CENTER_Y
        return DOME_R**2 * t - t**3 / 3.0

    return math.pi * (primitive(y1) - primitive(y0))


def revolved_volume() -> float:
    rm = MAJOR_DIA / 2.0
    head = math.pi * (HEAD_DIA / 2.0) ** 2 * SIDE_TOP_Y + _dome_slab(
        SIDE_TOP_Y, HEAD_HEIGHT
    )
    tip = rm - TIP_CHAMFER
    shank = (
        math.pi * rm**2 * (LENGTH - TIP_CHAMFER)
        + math.pi * TIP_CHAMFER * (rm * rm + rm * tip + tip * tip) / 3.0
    )
    return head + shank


def socket_volume() -> float:
    return math.sqrt(3.0) / 2.0 * SOCKET_AF**2 * SOCKET_DEPTH


def screw_volume() -> float:
    """The modelled solid, mm^3."""
    return revolved_volume() - socket_volume()
