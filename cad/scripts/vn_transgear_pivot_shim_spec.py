"""MHA-VN-069 transgear pivot shim: McMaster 98055A098 DIN 988 shim ring.

PURE DATA, no SolidWorks/COM imports.  One shim sits on the MHA-VN-041 pivot
screw's shoulder between the underside of its head and the MHA-VN-049 disc
spring: the 9.5 support bar grew 0.5 rearward under the hanger (user ruling
2026-10-15) and the MHA-PD-020 spacer gave that up, which lifted the screw
head 0.5 off the spring; the shim takes it back, so the spring room stays
0.80 nominal (transgear_hanger_joints).

Catalogue (``_mcmaster_98055a098``): spring steel, 5 ID x 10 OD x 0.5,
thickness -0.05/0, ID +0.03/+0.4, OD -0.47/-0.04.

Part frame: axis +Y, the face on the spring at y = 0, the face under the
screw head at y = THICKNESS (the catalogue nominal).
"""

import math

from _mcmaster_98055a098 import (
    CATALOG_CHECKED_DATE as CATALOG_CHECKED_DATE,
    CATALOG_MATERIAL as CATALOG_MATERIAL,
    CATALOG_STANDARD as CATALOG_STANDARD,
    CATALOG_URL as CATALOG_URL,
    DIMS,
    THICKNESS_NOMINAL,
)

SKU = DIMS.part_no
COUNT = 1
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

# Supplier nominal design dimensions may lie outside their unilateral stock
# bands: these are reference annotations, not measured-specimen assertions.
SUPPLIER_DRAWING_URL = (
    "https://www.mcmaster.com/mvC/Library/CAD2/20260108/1F378AF1/"
    "98055A098_Spring%20Steel%20ShimX.GIF"
)
SUPPLIER_UNITS = "mm"
DRAWING_REFERENCE_PRECISION = {
    "supplier outer diameter": 2,
    "supplier bore diameter": 2,
    "supplier thickness": 2,
}
SUPPLIER_TOLERANCES = {
    "supplier outer diameter": (OD_MIN, OD_MAX, "bilateral"),
    "supplier bore diameter": (ID_MIN, ID_MAX, "bilateral"),
    "supplier thickness": (THICKNESS_MIN, THICKNESS_MAX, "bilateral"),
}


def shim_volume() -> float:
    """Nominal annulus volume, mm^3."""
    return math.pi / 4 * (OD**2 - ID**2) * THICKNESS
