"""MHA-VN-060 purchased #10 SAE flat washer, bottom Y=0, axis +Y.

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


def washer_volume() -> float:
    """Nominal annulus volume, mm^3."""
    return math.pi / 4 * (OD**2 - ID**2) * THICKNESS
