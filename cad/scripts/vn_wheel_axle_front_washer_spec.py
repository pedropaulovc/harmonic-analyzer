r"""MHA-VN-058 wheel-axle-front-washer: McMaster 92916A250 brass #4 washer.

PURE DATA, no SolidWorks/COM calls and no ``build_*`` module in its import
closure.  One per wheel, on the mg-wheel-axle's #4-40 end between the
magnifying wheel's spigot face and the wheel-axle nut (``mg_wheel_group``).

Catalogue (mcmaster.com/92916A250, checked live 2026-10-10 for the rev 10
design): brass washer for #4 screw, ID 0.120 in, OD 0.281 in, thickness
0.018-0.032 in.

Part frame: washer axis local +Z; the washer runs z 0..MODEL_THICKNESS.
"""

from __future__ import annotations

import math

MM_PER_IN = 25.4

SKU = "92916A250"
COUNT = 1
ID = 0.120 * MM_PER_IN  # 3.048
OD = 0.281 * MM_PER_IN  # 7.1374
THICKNESS_MIN = 0.018 * MM_PER_IN  # 0.4572
THICKNESS_MAX = 0.032 * MM_PER_IN  # 0.8128
MODEL_THICKNESS = 0.64  # the catalogue range's nominal, 0.025 in, to 0.01

if not THICKNESS_MIN < MODEL_THICKNESS < THICKNESS_MAX:
    raise AssertionError("92916A250 modelled thickness is outside the catalogue range")

# Engineering drawing inspected 2026-10-19. Its thickness is a limit stack;
# deviations around MODEL_THICKNESS print those limits without changing the solid.
SUPPLIER_DRAWING_URL = (
    "https://www.mcmaster.com/mvC/Library/CAD2/20260702/F5440C8D/"
    "92916A250_Brass%20WasherX.GIF"
)
SUPPLIER_UNITS = "in"
DRAWING_REFERENCE_PRECISION = {
    "supplier outer diameter": 3,
    "supplier bore diameter": 3,
    "supplier thickness": 3,
}
SUPPLIER_TOLERANCES = {
    "supplier thickness": (THICKNESS_MIN, THICKNESS_MAX, "limits"),
}
SUPPLIER_BORE_CALLOUT = "FOR No. 4 SCREW SIZE"

REFERENCE_SKETCHES = ("SupplierWasherThicknessReference",)
DRAWING_PRECISION = {
    "SupplierWasherThicknessReference": {
        "SupplierThickness": DRAWING_REFERENCE_PRECISION["supplier thickness"],
    },
}


def washer_volume() -> float:
    """The modelled solid, mm^3."""
    return math.pi / 4.0 * (OD**2 - ID**2) * MODEL_THICKNESS
