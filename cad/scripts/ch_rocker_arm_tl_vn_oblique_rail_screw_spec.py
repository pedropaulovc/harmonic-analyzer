r"""MHA-CH-06-TL-VN-61 oblique-trammel rail screw: McMaster 91251A197.

PURE DATA, no SolidWorks/COM calls and no ``build_*`` module in its import
closure.  Shop fixture hardware (cad/docs/subsystem-identities.md), modelled
so the jig assembly can mate it and run native interference: the
``#8-32 X 3/4 SHCS`` that holds an HGR15R rail to its TL-20 base bar, tapped THRU; the head seats on the rail's counterbore floor.
It is the C4 fastener table's ``RAIL_TO_BAR`` row.  It is its own row on the
jig's BOM; the shop inventory carries no screw stock (no ``INVENTORY_ID``),
and the assembly steps cite it by item and callout (``fasteners.callout``).

Sources:

* SOURCED, https://www.mcmaster.com/91251A197/ read live 2026-10-17:
  #8-32 UNC class 3A, 3/4 in under the head, fully threaded, head Ø0.27 x 0.164 in, 9/64 in hex, Rockwell C37, ASTM A574, $18.68 per pack of 100.
* FROM THE FASTENER TABLE (imported): thread, printed length, head, count,
  grip and the joint (``fasteners.RAIL_TO_BAR``); the catalogue's thread and
  length must equal the row's (checked at import).
* STANDARD: the page gives no socket depth, so it is the standard's
  minimum key engagement (``_mcmaster_91251a197``; the 91251A108 convention).
* The geometry is the 91251A family's catalogue recipe
  (``diag_mcmaster_socket_head.build_socket_head``: plain cylindrical head,
  0.75P tip chamfer, 45 deg thread neck); the vendor model (downloaded
  2026-10-17) is a reading note only, NOT replica-gated (user ruling
  2026-10-17).  The recipe is ``diagnostics/diag_build_91251A197.py``; its
  standalone run is catalog-only.

Part frame: screw axis local +Y through the origin, published as
``ScrewAxis`` (Front ∩ Right); the bearing face (head underside) at y = 0 (the Top Plane), the tip at
y = -length.  Mate the Top Plane to the head's seat, the rail's counterbore floor.
"""

from __future__ import annotations

import _config
import ch_rocker_arm_tl_oblique_fasteners_spec as fasteners
from _mcmaster_91251a197 import DIMS, LENGTH_TEXT, PART_NO, THREAD
from _package_units import drawing_unit

UNIT = drawing_unit(
    "parts/ch-rocker-arm-tl-vn-oblique-rail-screw",
    _config.parts("ch-rocker-arm-tl-vn-oblique-rail-screw"),
)
SKU = PART_NO
ROW = fasteners.RAIL_TO_BAR
QUANTITY = ROW.count
PACK_QUANTITY = 100  # McMaster sells 91251A197 in packs of 100
CALLOUT = fasteners.callout(ROW)  # "#8-32 X 3/4 SHCS"

if (THREAD, LENGTH_TEXT, fasteners.SHCS) != (ROW.thread, ROW.length, ROW.head):
    raise AssertionError(f"{SKU} is not the screw of {ROW.joint}")
if abs(DIMS.length - ROW.length_mm) > 1e-9:
    raise AssertionError(f"{SKU}: {DIMS.length} long, the row prints {ROW.length_mm}")
if abs(DIMS.major_dia - ROW.major_mm) > 1e-3:
    raise AssertionError(
        f"{SKU}: major {DIMS.major_dia}, the row's thread is {ROW.major_mm}"
    )

# Exact-current product table and engineering drawing read 2026-10-21.
# Hidden nominal source references, not physical-edge/replica assertions.
# Drawing precision: length/head Ø/head height/major Ø .XXX,
# drive an exact 9/64 fraction. The standard-only socket depth is omitted.
SUPPLIER_PRODUCT_URL = "https://www.mcmaster.com/91251A197/"
SUPPLIER_DRAWING_URL = (
    "https://www.mcmaster.com/mvC/Library/CAD2/20260108/291FC233/"
    "91251A197_Black-Oxide%20Alloy%20Steel%20Socket%20Head%20ScrewX.GIF"
)
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
    "SupplierThreadDiameter": (-DIMS.major_dia / 2.0, 0.0),  # on the bearing-face edge
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
    "SupplierLength": (3, "length", None, None),
    "SupplierHeadDiameter": (3, "diameter", None, None),
    "SupplierHeadHeight": (3, "length", None, None),
    "SupplierThreadDiameter": (3, "diameter", None, "#8-32"),
    "SupplierDriveWidth": (0, "length", 64, None),
}
