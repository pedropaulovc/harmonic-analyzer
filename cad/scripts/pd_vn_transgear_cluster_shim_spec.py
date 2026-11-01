r"""MHA-PD-VN-68 transgear cluster shim: McMaster 94773A606 stainless shim.

PURE DATA, no SolidWorks/COM imports.  Owner ruling 2026-11-01 (#2124): the
disc cluster's end float on the MHA-PD-23 pin is set at assembly with as many
of these shims as it takes, stacked on the MHA-PD-18 arm's front face under
the MHA-PD-24 rear bushing.  The fit-up, its window and the shim count live
in ``transgear_cluster_fit``.

Catalogue (``_mcmaster_94773a606``): 18-8 stainless, 1/8 ID (0/+.012 in) x
1/4 OD (-.005/+.002 in) x .005 (+/-.0005 in).

Part frame: axis +Y, the face on the arm at y = 0, the face under the rear
bushing at y = THICKNESS (the catalogue nominal).
"""

import math

from _mcmaster_94773a606 import (
    CATALOG_CHECKED_DATE as CATALOG_CHECKED_DATE,
    CATALOG_MATERIAL as CATALOG_MATERIAL,
    CATALOG_URL as CATALOG_URL,
    DIMS,
    FAMILY_TABLE_URL as FAMILY_TABLE_URL,
    THICKNESS_NOMINAL,
)

SKU = DIMS.part_no
ID = DIMS.id
OD = DIMS.od
ID_MIN = DIMS.id_min
ID_MAX = DIMS.id_max
OD_MIN = DIMS.od_min
OD_MAX = DIMS.od_max
THICKNESS = THICKNESS_NOMINAL
THICKNESS_MIN = DIMS.thickness_min
THICKNESS_MAX = DIMS.thickness_max
BOTTOM_Y = 0.0
TOP_Y = THICKNESS

# The catalogue's limits print as supplier references; the solid is the
# bore band's middle at the nominal thickness.
SUPPLIER_UNITS = "in"
DRAWING_REFERENCE_PRECISION = {
    "supplier outer diameter": 3,
    "supplier bore diameter": 3,
    "supplier thickness": 4,
}
SUPPLIER_TOLERANCES = {
    "supplier outer diameter": (OD_MIN, OD_MAX, "limits"),
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


def shim_volume() -> float:
    """The modelled annulus of one shim, mm^3."""
    return math.pi / 4.0 * (OD**2 - ID**2) * THICKNESS
