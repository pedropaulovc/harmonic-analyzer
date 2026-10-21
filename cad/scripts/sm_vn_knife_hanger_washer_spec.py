"""MHA-SM-VN-54 purchased #10 SAE flat washer, bottom Y=0, axis +Y.

Catalogue checked 2026-10-13: https://www.mcmaster.com/96659A104/.
18-8 stainless, ASME B18.21.1. Supplier diameter tolerance rows are omitted;
conformity supports the separate Table 11 bounds in the pure supplier module.
The midpoint thickness depicts the catalogue range; no exact stock thickness
or zero eccentricity is assumed by the assembly stack.
"""

import math

from _mcmaster_96659a104 import (
    BOUND_SOURCE as BOUND_SOURCE,
    BOUND_SOURCE_URL as BOUND_SOURCE_URL,
    CATALOG_CHECKED_DATE as CATALOG_CHECKED_DATE,
    CATALOG_DIAMETER_TOLERANCES as CATALOG_DIAMETER_TOLERANCES,
    CATALOG_STANDARD as CATALOG_STANDARD,
    CATALOG_URL as CATALOG_URL,
    DIMS,
)

SKU = DIMS.part_no
COUNT = 2
ID = DIMS.id
OD = DIMS.od
ID_MIN = DIMS.id_min
ID_MAX = DIMS.id_max
OD_MIN = DIMS.od_min
OD_MAX = DIMS.od_max
THICKNESS_MIN = DIMS.thickness_min
THICKNESS_MAX = DIMS.thickness_max
THICKNESS = DIMS.thickness
OD_ID_RUNOUT_MAX = DIMS.od_id_runout_max
BOTTOM_Y = 0.0
TOP_Y = THICKNESS

# Supplier engineering drawing inspected 2026-10-19. Display precision is
# independent of the unchanged representative thickness and exact diameters.
SUPPLIER_DRAWING_URL = (
    "https://www.mcmaster.com/mvC/Library/CAD2/20260630/7FA79105/"
    "96659A104_18-8%20Stainless%20Steel%20SAE%20WasherX.GIF"
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
    """Nominal annulus volume, mm^3."""
    return math.pi / 4 * (OD**2 - ID**2) * THICKNESS
