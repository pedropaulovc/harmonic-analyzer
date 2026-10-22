r"""MHA-MG-VN-54 wheel-axle-back-washer: McMaster 92916A480 brass #10 washer.

PURE DATA, no SolidWorks/COM calls and no ``build_*`` module in its import
closure.  One per wheel, on the 3/16 mg-wheel-axle between the mg-wheel-bar's
front face and the magnifying wheel's hub back face: the hub runs on it
(``mg_wheel_group``).

Catalogue (mcmaster.com/92916A480, checked live 2026-10-10 for the rev 10
design): brass washer for #10 screw, ID 0.200 in, OD 0.438 in, thickness
0.029-0.043 in.

Part frame: washer axis local +Z; the washer runs z 0..MODEL_THICKNESS.
"""

from __future__ import annotations

import math

MM_PER_IN = 25.4

SKU = "92916A480"
COUNT = 1
ID = 0.200 * MM_PER_IN  # 5.08
OD = 0.438 * MM_PER_IN  # 11.1252
THICKNESS_MIN = 0.029 * MM_PER_IN  # 0.7366
THICKNESS_MAX = 0.043 * MM_PER_IN  # 1.0922
MODEL_THICKNESS = 0.91  # the catalogue range's nominal, 0.036 in, to 0.01

if not THICKNESS_MIN < MODEL_THICKNESS < THICKNESS_MAX:
    raise AssertionError("92916A480 modelled thickness is outside the catalogue range")

# Engineering drawing inspected 2026-10-19. Its thickness is a limit stack;
# deviations around MODEL_THICKNESS print those limits without changing the solid.
SUPPLIER_DRAWING_URL = (
    "https://www.mcmaster.com/mvC/Library/CAD2/20260702/8C5AC0BA/"
    "92916A480_Brass%20WasherX.GIF"
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
SUPPLIER_BORE_CALLOUT = "FOR No. 10 SCREW SIZE"

REFERENCE_SKETCHES = ("SupplierWasherThicknessReference",)
DRAWING_PRECISION = {
    "SupplierWasherThicknessReference": {
        "SupplierThickness": DRAWING_REFERENCE_PRECISION["supplier thickness"],
    },
}


def washer_volume() -> float:
    """The modelled solid, mm^3."""
    return math.pi / 4.0 * (OD**2 - ID**2) * MODEL_THICKNESS
