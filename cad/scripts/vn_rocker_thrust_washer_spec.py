r"""MHA-VN-070 rocker thrust washer: McMaster 3088A429 carbon-steel ring shim.

PURE DATA, no SolidWorks/COM imports.  Two ride the Ø6.35 MHA-CH-005 pivot
shaft, one at each end of the rocker bank (``rocker_bank_layout``): the north
one between hub 19 and the north MHA-CH-008 ear's inner face (the bank's
datum; the fitter mics it and offsets the ear's DRO target), the south one
between hub 0 and the MHA-VN-053 wave spring.  It replaced the retired custom
MHA-CH-009 washer (owner ruling, 2026-10-15: every washer is a purchased
part); the 0.031 in stock thickness keeps the bank's stand-offs.

Catalogue (``_mcmaster_3088a429``): carbon steel, 1/4 ID (0/+0.011 in) x 3/8
OD (+/-0.002 in) x 0.031 (+/-0.002 in).

Part frame: axis +Z, one face on z = 0 (the Front Plane) and the other at
z = THICKNESS (the catalogue nominal).
"""

import math

from _mcmaster_3088a429 import (
    CATALOG_CHECKED_DATE as CATALOG_CHECKED_DATE,
    CATALOG_MATERIAL as CATALOG_MATERIAL,
    CATALOG_URL as CATALOG_URL,
    DIMS,
    FAMILY_TABLE_URL as FAMILY_TABLE_URL,
    THICKNESS_NOMINAL,
)

SKU = DIMS.part_no
COUNT = 2
ID = DIMS.id
OD = DIMS.od
ID_MIN = DIMS.id_min
ID_MAX = DIMS.id_max
OD_MIN = DIMS.od_min
OD_MAX = DIMS.od_max
THICKNESS = THICKNESS_NOMINAL
THICKNESS_MIN = DIMS.thickness_min
THICKNESS_MAX = DIMS.thickness_max
BOTTOM_Z = 0.0
TOP_Z = THICKNESS

# The engineering drawing uses .250 +.011/-.000 for the bore. The solid
# deliberately represents its midpoint; native equivalent limits retain the
# exact supplier acceptance without rounding or changing that geometry.
SUPPLIER_DRAWING_URL = (
    "https://www.mcmaster.com/mvC/Library/CAD2/20260108/095CF7B5/"
    "3088A429_Carbon%20Steel%20ShimX.GIF"
)
SUPPLIER_UNITS = "in"
DRAWING_REFERENCE_PRECISION = {
    "supplier outer diameter": 3,
    "supplier bore diameter": 3,
    "supplier thickness": 3,
}
SUPPLIER_TOLERANCES = {
    "supplier outer diameter": (OD_MIN, OD_MAX, "symmetric"),
    "supplier bore diameter": (ID_MIN, ID_MAX, "limits"),
    "supplier thickness": (THICKNESS_MIN, THICKNESS_MAX, "symmetric"),
}

REFERENCE_SKETCHES = (
    "SupplierWasherFaceReference",
    "SupplierWasherThicknessReference",
)
DRAWING_PRECISION = {
    "SupplierWasherFaceReference": {
        "SupplierOuterDiameter": DRAWING_REFERENCE_PRECISION["supplier outer diameter"],
        "SupplierBoreDiameter": DRAWING_REFERENCE_PRECISION["supplier bore diameter"],
    },
    "SupplierWasherThicknessReference": {
        "SupplierThickness": DRAWING_REFERENCE_PRECISION["supplier thickness"],
    },
}


def washer_volume() -> float:
    """The modelled annulus, mm^3."""
    return math.pi / 4.0 * (OD**2 - ID**2) * THICKNESS
