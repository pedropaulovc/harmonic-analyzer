r"""MHA-CH-06-TL-VN-85: oblique-trammel hub clamp washer, McMaster 90231A116.

PURE DATA, no SolidWorks/COM imports.  Owner ruling 2026-11-13 (#2448): the
HUB clamp bears on a bought brass #8 SAE flat washer, used as supplied, in
place of the turned top-hat washer MHA-CH-06-TL-52 (retired, never reissued).
Brass, softer than the strap's steel, keeps the strap unmarked.  The washer
seats flat on the strap over its reamed hub hole under the head of the
common #8-32 x 3/4 SHCS (McMaster 91251A197); the screw, not a spigot,
centres it, so the holding proof charges the bore's float on the screw and
the supplier's OD-to-ID runout (``ch_rocker_arm_tl_oblique_holding_spec``).

Catalogue and bounds: ``_mcmaster_90231a116`` (read live 2026-11-13).

Part frame: washer axis +Z (``ScrewAxis``, Top Plane x Right Plane); the
strap-side face on the Front Plane (z = 0), the head-side face at
z = THICKNESS.
"""

from __future__ import annotations

import math

from _mcmaster_90231a116 import (
    BOUND_SOURCE as BOUND_SOURCE,
    BOUND_SOURCE_URL as BOUND_SOURCE_URL,
    CATALOG_CHECKED_DATE as CATALOG_CHECKED_DATE,
    CATALOG_DIAMETER_TOLERANCES as CATALOG_DIAMETER_TOLERANCES,
    CATALOG_PRICE as CATALOG_PRICE,
    CATALOG_STANDARD as CATALOG_STANDARD,
    CATALOG_URL as CATALOG_URL,
    DIMS,
    MM_PER_IN,
)

SKU = DIMS.part_no
QUANTITY = 1
SCREW_SIZE = "#8"
ID = DIMS.id
OD = DIMS.od
ID_MIN = DIMS.id_min
ID_MAX = DIMS.id_max
OD_MIN = DIMS.od_min
OD_MAX = DIMS.od_max
THICKNESS_MIN = DIMS.thickness_min
THICKNESS_MAX = DIMS.thickness_max
OD_ID_RUNOUT_MAX = DIMS.od_id_runout_max
# The model depicts Table 11's basic .049 thickness; every stack charges the
# supplier range (THICKNESS_MIN, THICKNESS_MAX), never this value alone.
THICKNESS = 0.049 * MM_PER_IN  # 1.2446
if not THICKNESS_MIN < THICKNESS < THICKNESS_MAX:
    raise AssertionError("90231A116 modelled thickness is outside the catalogue range")
BOTTOM_Z = 0.0
TOP_Z = THICKNESS

# Supplier engineering drawing inspected 2026-11-13 (ID .188, OD .438,
# thickness range .036-.065 in).  The sheet prints the model's sizes as
# untoleranced REF; the catalogue governs.
SUPPLIER_DRAWING_URL = (
    "https://www.mcmaster.com/mvC/Library/CAD2/20260110/866A632C/"
    "90231A116_Brass%20SAE%20WasherX.GIF"
)
SUPPLIER_UNITS = "in"
DRAWING_REFERENCE_PRECISION = {
    "supplier outer diameter": 3,
    "supplier bore diameter": 3,
    "supplier thickness": 3,
}
# Supplier sizes the part witnesses natively; all print untoleranced REF.
SUPPLIER_MODEL_REFERENCES = ("supplier thickness",)
# The bore prints bare: the ITEM line already names the #8 screw size.
SUPPLIER_BORE_CALLOUT = None
# The modelled (.049) is one point of the supplier's range.
SUPPLIER_DATA = ("THICKNESS .036-.065 AS SUPPLIED.",)

REFERENCE_SKETCHES = ("SupplierWasherThicknessReference",)
DRAWING_PRECISION = {
    "SupplierWasherThicknessReference": {
        "SupplierThickness": DRAWING_REFERENCE_PRECISION["supplier thickness"],
    },
}


def washer_volume() -> float:
    """The modelled annulus, mm^3."""
    return math.pi / 4.0 * (OD**2 - ID**2) * THICKNESS
