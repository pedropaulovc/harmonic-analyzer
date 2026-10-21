r"""MHA-MG-VN-52 wheel-axle-nut: McMaster 92671A005 brass #4-40 hex nut.

PURE DATA, no SolidWorks/COM calls and no ``build_*`` module in its import
closure.  Two per wheel on the mg-wheel-axle's #4-40 end: the first is run
down until the wheel turns free without rattle (0.05-0.15 endshake), the
second jams it (``mg_wheel_group``).

Catalogue (mcmaster.com/92671A005, checked live 2026-10-10 for the rev 10
design): brass hex nut, ASME B18.2.2, #4-40, 1/4 in across flats, 3/32 in
thick.

Part frame: thread axis local +Z; the nut runs z 0..THICKNESS. The thread
is not modelled: the bore retains the rounded #4-40 major envelope,
line-to-line with the pin's modelled thread.
"""

from __future__ import annotations

import math

from _hole_spec import THREAD_MAJOR_MM

MM_PER_IN = 25.4

SKU = "92671A005"
COUNT = 2  # nut + locknut
THREAD = "#4-40"
ACROSS_FLATS = 0.25 * MM_PER_IN  # 6.35
THICKNESS = 3.0 / 32.0 * MM_PER_IN  # 2.38125, modelled
# The stack proofs take the ASME B18.6.3 #4 hex machine-screw nut band.
THICKNESS_MIN = 0.087 * MM_PER_IN  # 2.2098
THICKNESS_MAX = 0.098 * MM_PER_IN  # 2.4892
BORE_DIA = THREAD_MAJOR_MM[THREAD]  # 2.845
ACROSS_CORNERS = ACROSS_FLATS / math.cos(math.radians(30.0))  # 7.332

# Source drawing: 1/4 in AF and 0.094 in height; exact 3/32 in stays native.
# The existing 2.845 mm bore is rounded; do not label it as exact .112 in.
DRAWING_REFERENCE_PRECISION = {"AcrossFlats": 0, "Height": 3, "ThreadNominalMajor": 3}
SUPPLIER_FRACTION_DENOMINATOR = 4
SUPPLIER_NOMINAL_MAJOR_MM = 0.112 * MM_PER_IN
SUPPLIER_REFERENCE_DIMENSIONS = (
    ("ThreadNominalMajor", SUPPLIER_NOMINAL_MAJOR_MM, "horizontal"),
)
SUPPLIER_REFERENCE_STARTS = {
    "ThreadNominalMajor": (-SUPPLIER_NOMINAL_MAJOR_MM / 2.0, 0.0),
}


def nut_volume() -> float:
    """The modelled solid, mm^3: hexagonal prism less the bore."""
    hexagon = math.sqrt(3.0) / 2.0 * ACROSS_FLATS**2
    return (hexagon - math.pi / 4.0 * BORE_DIA**2) * THICKNESS
