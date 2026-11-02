r"""MHA-CH-06-TL-VN-69 oblique-trammel feed lever screw: McMaster 91251A583.

PURE DATA, no SolidWorks/COM calls and no ``build_*`` module in its import
closure.  Shop fixture hardware (cad/docs/subsystem-identities.md), modelled
so the jig assembly can mate it and run native interference: the
``5/16-18 X 1 SHCS`` that holds the TL-26 feed lever to the TL-21 carrier,
tapped THRU; the head seats on the TL-VN-71 wedge-lock pair on the feed lever.
It is the C4 fastener table's ``LEVER_TO_CARRIER`` row.  It is its own row on
the jig's BOM; the shop inventory carries no screw stock (no
``INVENTORY_ID``), and the assembly steps cite it by item and callout
(``fasteners.callout``).

Sources:

* SOURCED, the McMaster 5/16-18 x 1 in socket head screw listing row read
  live 2026-10-17 (``_mcmaster_91251a583``): 5/16-18 UNC, 1 in under the
  head, fully threaded, head Ø15/32 x 5/16 in, 170,000 psi, $15.30 per pack
  of 50; the family's 1/4 in hex, Rockwell C37 and ASTM A574 from the 7/8 in
  sibling's page.
* FROM THE FASTENER TABLE (imported): thread, printed length, head, count,
  grip and the joint (``fasteners.LEVER_TO_CARRIER``); the catalogue's thread and
  length must equal the row's (checked at import).
* STANDARD: the listing gives no socket depth, so it is the standard's
  minimum key engagement (``_mcmaster_91251a583``; the 91251A108 convention);
  the length tolerance is ASME B18.3's -0.03 in (``LENGTH_MIN``), which the
  TL-VN-71 spec's worst-case engagement takes.
* The geometry is the 91251A family's catalogue recipe
  (``diag_mcmaster_socket_head.build_socket_head``: plain cylindrical head,
  0.75P tip chamfer, 45 deg thread neck), NOT replica-gated (user ruling
  2026-10-17).  The recipe is ``diagnostics/diag_build_91251A583.py``; its
  standalone run is catalog-only.

Part frame: screw axis local +Y through the origin, published as
``ScrewAxis`` (Front ∩ Right); the bearing face (head underside) at y = 0 (the Top Plane), the tip at
y = -length.  Mate the Top Plane to the head's seat, the TL-VN-71 pair's top.
"""

from __future__ import annotations

import _config
import ch_rocker_arm_tl_oblique_fasteners_spec as fasteners
from _mcmaster_91251a583 import (
    DIMS,
    LENGTH_MIN as LENGTH_MIN,
    LENGTH_TEXT,
    PACK_QUANTITY as _PACK_QUANTITY,
    PART_NO,
    THREAD,
)
from _package_units import drawing_unit

UNIT = drawing_unit(
    "parts/ch-rocker-arm-tl-vn-oblique-lever-screw",
    _config.parts("ch-rocker-arm-tl-vn-oblique-lever-screw"),
)
SKU = PART_NO
ROW = fasteners.LEVER_TO_CARRIER
QUANTITY = ROW.count
PACK_QUANTITY = _PACK_QUANTITY  # McMaster sells 91251A583 in packs of 50
CALLOUT = fasteners.callout(ROW)  # "5/16-18 X 1 SHCS"

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
# The table's exact head Ø15/32 and height5/16 remain .46875/.3125 in
# natively; only the engineering drawing's ink rounds them to .469/.313.
# Length/head Ø/head height/major Ø have three places; drive is 1/4.
# Standard-only socket depth/length tolerances are not supplier references.
SUPPLIER_PRODUCT_URL = "https://www.mcmaster.com/91251A583/"
SUPPLIER_DRAWING_URL = (
    "https://www.mcmaster.com/mvC/Library/CAD2/20260108/14BDCFCB/"
    "91251A583_Black-Oxide%20Alloy%20Steel%20Socket%20Head%20ScrewX.GIF"
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
    "SupplierThreadDiameter": (3, "diameter", None, '5/16"-18'),
    "SupplierDriveWidth": (0, "length", 4, None),
}
