"""Pure McMaster 91255A267 catalogue dimensions for its recipe and assemblies.

McMaster product page read live on 2026-11-23 (https://www.mcmaster.com/91255A267/):
Black-Oxide Button Head Hex-Drive Screw, alloy steel, 10-32 UNF, class 3A,
right hand, 5/8" long (measured from under the head), fully threaded, flat
tip; button head, standard profile, 0.361" diameter x 0.101" high; 1/8"
hex drive; 120,000 psi, Rockwell C39; ASME B18.3, ASTM F835; $13.21 per
pack of 50. Those head sizes are ASME B18.3-2012's maxima for a No. 10
button head (diameter .361 max, .347 min; height .101 max, .091 min).

Head form from McMaster's own model (``91255A267_Button Head Hex Drive
Screw.STEP``, downloaded from the product page 2026-11-23, SHA-256
c8bab71d...6e41ddf6, probed headless with FreeCAD 1.1; not tracked): a
spherical dome R 5.26903 whose centre stands 2.21196 below the bearing
face, cut flat at the head height; socket floor 1.411 below the head top;
a 45 deg tip chamfer from the major to Ø.143. Its solid is 340.153 mm^3
with the thread.

The model keeps the catalogue head diameter as a plain cylinder up to the
dome (the vendor's 10 deg side and .005 edge rounds are not modelled), the
shank a plain cylinder at the 10-32 basic major (the thread is not
modelled), the socket flat-floored without its entry countersink.

``MAJOR_DIA_MIN`` is the class 3A major diameter's minimum (ASME B1.1:
10-32 UNF-3A major .1900 max, .1840 min), the screw a washer's bore has the
most play on.
"""

from __future__ import annotations

import math

MM_PER_IN = 25.4

SKU = "91255A267"
THREAD = "#10-32"
HEAD_DIA = 0.361 * MM_PER_IN  # 9.1694
HEAD_DIA_MIN = 0.347 * MM_PER_IN  # 8.8138 (ASME B18.3)
HEAD_HEIGHT = 0.101 * MM_PER_IN  # 2.5654
LENGTH = 0.625 * MM_PER_IN  # 15.875, under the head
MAJOR_DIA = 0.190 * MM_PER_IN  # 4.826
MAJOR_DIA_MIN = 0.184 * MM_PER_IN  # 4.6736 (ASME B1.1, class 3A)
SOCKET_AF = 1.0 / 8.0 * MM_PER_IN  # 3.175
SOCKET_DEPTH = 1.411
DOME_R = 5.26903
DOME_CENTER_Y = -2.21196  # below the bearing face
TIP_CHAMFER = 0.5953
STEP_VOLUME = 340.1527

# Where the dome meets the head's side, and the head top's flat radius.
SIDE_TOP_Y = DOME_CENTER_Y + math.sqrt(DOME_R**2 - (HEAD_DIA / 2.0) ** 2)
TOP_FLAT_R = math.sqrt(DOME_R**2 - (HEAD_HEIGHT - DOME_CENTER_Y) ** 2)
if not 0.0 < SIDE_TOP_Y < HEAD_HEIGHT or not 0.0 < TOP_FLAT_R < HEAD_DIA / 2.0:
    raise AssertionError("the 91255A267 dome does not meet its head")


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
