r"""MHA-DT-12-TL-VN-53 cam fixture clamp washer: McMaster 92141A011.

PURE DATA, no SolidWorks/COM calls and no ``build_*`` module in its import
closure. Shop fixture hardware (cad/docs/subsystem-identities.md), modelled
so the MHA-DT-12-TL-00 kit can place it: the #10 washer under the -VN-52
clamp screw's head, bearing on each cylinder gear's cam face inside the cam
circle. Its bearing ring and tool-sweep clearance are the fixture's
(``dt_cylinder_gear_tl_cam_fixture_spec``).

Catalogue (``_mcmaster_92141a011``, read live 2026-11-12): 18-8 stainless,
No. 10, ID .203, OD .438, thickness .017 to .047, $3.79 per 100. No vendor
model; the recipe is ``diagnostics/diag_build_92141A011.py`` (catalog-only),
modelled at the thickness range's mid value.

Part frame: axis local +Y through the origin, published as ``ScrewAxis``
(Front ∩ Right); the bottom face (on the cam face) at y = 0 (the Top Plane),
the top face (under the screw head) at y = THICKNESS.
"""

from __future__ import annotations

import math

import _config
from _mcmaster_91251a337 import DIMS as SCREW
from _mcmaster_92141a011 import (
    ID,
    MODEL_THICKNESS,
    OD,
    PACK_QUANTITY as PACK_QUANTITY,
    PART_NO,
    THICKNESS_MAX as THICKNESS_MAX,
    THICKNESS_MIN as THICKNESS_MIN,
)
from _package_units import drawing_unit

PART_NAME = "dt-cylinder-gear-tl-vn-cam-clamp-washer"
UNIT = drawing_unit(
    "parts/dt-cylinder-gear-tl-vn-cam-clamp-washer",
    _config.parts("dt-cylinder-gear-tl-vn-cam-clamp-washer"),
)
SKU = PART_NO
QUANTITY = 1
if (
    int(_config.parts("dt-cylinder-gear-tl-vn-cam-clamp-washer")["quantity"])
    != QUANTITY
):
    raise AssertionError(f"{SKU}: one washer under the clamp screw")
THICKNESS = MODEL_THICKNESS
BOTTOM_Y = 0.0
TOP_Y = THICKNESS

SUPPLIER_UNITS = "in"
DRAWING_REFERENCE_PRECISION = {
    "supplier outer diameter": 3,
    "supplier bore diameter": 3,
    "supplier thickness": 3,
}
SUPPLIER_MODEL_REFERENCES = ("supplier thickness",)
SUPPLIER_BORE_CALLOUT = None
SUPPLIER_DATA = ("REFERENCE THICKNESS IS THE CATALOGUE RANGE'S MID VALUE.",)
REFERENCE_SKETCHES = ("SupplierWasherThicknessReference",)
DRAWING_PRECISION = {
    "SupplierWasherThicknessReference": {
        "SupplierThickness": DRAWING_REFERENCE_PRECISION["supplier thickness"],
    },
}

if not THICKNESS_MIN < THICKNESS < THICKNESS_MAX:
    raise AssertionError(f"{SKU}: the modelled thickness is outside the catalogue's")
if ID <= SCREW.major_dia:
    raise AssertionError(f"{SKU}: ID does not pass the 10-32 major")
if not ID < SCREW.head_dia < OD:
    raise AssertionError(f"{SKU}: the 5/16 head does not bear on the washer")


def washer_volume() -> float:
    """Nominal annulus volume of the modelled washer, in mm^3 (model units)."""
    return math.pi / 4 * (OD**2 - ID**2) * THICKNESS
