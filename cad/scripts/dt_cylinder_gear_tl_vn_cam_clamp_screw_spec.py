r"""MHA-DT-12-TL-VN-52 cam fixture clamp screw: McMaster 91251A337.

PURE DATA, no SolidWorks/COM calls and no ``build_*`` module in its import
closure. Shop fixture hardware (cad/docs/subsystem-identities.md), modelled
so the MHA-DT-12-TL-00 kit can place it: the 10-32 x 5/16 SHCS that threads
into the -VN-50 stub's tap and, through the -VN-53 washer on the cam face,
clamps each cylinder gear to the MHA-DT-12-TL-01 body. Its worst-case
engagement and the tool-sweep clearance of its head are the fixture's
(``dt_cylinder_gear_tl_cam_fixture_spec``).

Catalogue (``_mcmaster_91251a337``, read live 2026-11-12): 10-32 UNF class
3A, 5/16 under the head, head Ø5/16 x .19, 5/32 hex, $22.41 per 50. The
socket depth is the standard's minimum key engagement. The geometry is the
91251A family's catalogue recipe (``diag_mcmaster_socket_head``), NOT
replica-gated; the recipe is ``diagnostics/diag_build_91251A337.py``.

Part frame: screw axis local +Y through the origin, published as
``ScrewAxis`` (Front ∩ Right); the bearing face (head underside) at y = 0
(the Top Plane), the tip at y = -length.
"""

from __future__ import annotations

import _config
from _mcmaster_91251a337 import (
    DIMS,
    LENGTH_SHORT as LENGTH_SHORT,
    LENGTH_TEXT as LENGTH_TEXT,
    PACK_QUANTITY as PACK_QUANTITY,
    PART_NO,
    THREAD as THREAD,
)
from _package_units import drawing_unit

PART_NAME = "dt-cylinder-gear-tl-vn-cam-clamp-screw"
UNIT = drawing_unit(
    "parts/dt-cylinder-gear-tl-vn-cam-clamp-screw",
    _config.parts("dt-cylinder-gear-tl-vn-cam-clamp-screw"),
)
SKU = PART_NO
QUANTITY = 1
if int(_config.parts("dt-cylinder-gear-tl-vn-cam-clamp-screw")["quantity"]) != QUANTITY:
    raise AssertionError(f"{SKU}: one clamp screw per fixture")
CALLOUT = "10-32 X 5/16 SHCS"

# Hidden nominal source references (the catalogue's sizes), not
# physical-edge or replica assertions.
SUPPLIER_PRODUCT_URL = "https://www.mcmaster.com/91251A337/"
SUPPLIER_REFERENCE_DIMENSIONS = (
    ("SupplierLength", -DIMS.length, "vertical"),
    ("SupplierHeadDiameter", DIMS.head_dia, "horizontal"),
    ("SupplierHeadHeight", DIMS.head_h, "vertical"),
    ("SupplierThreadDiameter", DIMS.major_dia, "horizontal"),
    ("SupplierDriveWidth", DIMS.socket_af, "horizontal"),
)
SUPPLIER_REFERENCE_STARTS = {
    "SupplierLength": (DIMS.major_dia / 2.0, 0.0),
    "SupplierHeadDiameter": (-DIMS.head_dia / 2.0, 0.0),
    "SupplierHeadHeight": (DIMS.head_dia / 2.0, 0.0),
    "SupplierThreadDiameter": (-DIMS.major_dia / 2.0, 0.0),
    "SupplierDriveWidth": (-DIMS.socket_af / 2.0, 0.0),
}
SUPPLIER_REFERENCE_PLANES = {
    "SupplierHeadDiameter": "Top",
    "SupplierDriveWidth": "Top",
}
SUPPLIER_REFERENCE_SIDES = {
    "SupplierLength": "right",
    "SupplierHeadDiameter": "top",
    "SupplierHeadHeight": "left",
    "SupplierThreadDiameter": "bottom",
    "SupplierDriveWidth": "bottom",
}
SUPPLIER_REFERENCE_FORMATS = {
    "SupplierLength": (4, "length", None, None),
    "SupplierHeadDiameter": (4, "diameter", None, None),
    "SupplierHeadHeight": (2, "length", None, None),
    "SupplierThreadDiameter": (3, "diameter", None, "10-32"),
    # Decimal, one line: the stacked 5/32 fraction ran its own dimension line
    # through its text (run 20261112T203156536Z layout audit).
    "SupplierDriveWidth": (3, "length", None, None),
}
