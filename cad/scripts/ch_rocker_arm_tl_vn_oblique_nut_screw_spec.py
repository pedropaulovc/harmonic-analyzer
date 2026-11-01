r"""MHA-CH-06-TL-VN-66 oblique-trammel feed nut screw: McMaster 91251A113.

PURE DATA, no SolidWorks/COM calls and no ``build_*`` module in its import
closure.  Shop fixture hardware (cad/docs/subsystem-identities.md), modelled
so the jig assembly can mate it and run native interference: the
``#4-40 X 3/4 SHCS`` that holds the shop-made TL-27 feed nut to the TL-32
integral feed-block lug, through the nut's loose-clearance hole into the
lug's #4-40 tap, tapped THRU (owner ruling 2026-11-01, item 4, C1); the head
bears directly on the brass nut. It is the fastener table's
``NUT_TO_FEED_BLOCK`` row. It is its own row on the jig's BOM; the shop
inventory carries no screw stock (no ``INVENTORY_ID``), and the assembly
steps cite it by item and callout (``fasteners.callout``).

Sources:

* SOURCED, the #4-40 black-oxide listing row read live 2026-11-01
  (``_mcmaster_91251a113``): #4-40 UNC, 3/4 in under the head, fully
  threaded, head Ø0.183 x 0.112 in, 170,000 psi, US origin, $12.19 per pack
  of 100; the product page (HTTP 200, titled for the 4-40 x 3/4 in screw) is
  login-walled.
* STANDARD: ASME B18.3 Table 1, the head's least diameter and the underhead
  transition diameter (``HEAD_DIA_MIN``, ``FILLET_DIA_MAX``); the socket
  depth is the standard's minimum key engagement.
* FROM THE FASTENER TABLE (imported): thread, printed length, head, count,
  grip and the joint (``fasteners.NUT_TO_FEED_BLOCK``); the catalogue's
  thread and length must equal the row's (checked at import).
* The geometry is the 91251A family's catalogue recipe
  (``diag_mcmaster_socket_head.build_socket_head``: plain cylindrical head,
  0.75P tip chamfer, 45 deg thread neck); no vendor model was downloaded
  (login-walled), so it is NOT replica-gated.  The recipe is
  ``diagnostics/diag_build_91251A113.py``; its standalone run is catalog-only.

Part frame: screw axis local +Y through the origin, published as
``ScrewAxis`` (Front ∩ Right); the bearing face (head underside) at y = 0
(the Top Plane), the tip at y = -length.  Mate the Top Plane to the head's
seat, the feed nut's -X face.
"""

from __future__ import annotations

import _config
import _mcmaster_91251a113 as _catalogue
import ch_rocker_arm_tl_oblique_fasteners_spec as fasteners
from _mcmaster_91251a113 import DIMS, LENGTH_TEXT, PART_NO, THREAD
from _package_units import drawing_unit

UNIT = drawing_unit(
    "parts/ch-rocker-arm-tl-vn-oblique-nut-screw",
    _config.parts("ch-rocker-arm-tl-vn-oblique-nut-screw"),
)
SKU = PART_NO
ROW = fasteners.NUT_TO_FEED_BLOCK
QUANTITY = ROW.count
PACK_QUANTITY = _catalogue.PACK_QUANTITY
HEAD_DIA_MIN = _catalogue.HEAD_DIA_MIN  # ASME B18.3 A min: the bearing bound
FILLET_DIA_MAX = _catalogue.FILLET_DIA_MAX
CALLOUT = fasteners.callout(ROW)  # "#4-40 X 3/4 SHCS"

if (THREAD, LENGTH_TEXT, fasteners.SHCS) != (ROW.thread, ROW.length, ROW.head):
    raise AssertionError(f"{SKU} is not the screw of {ROW.joint}")
if abs(DIMS.length - ROW.length_mm) > 1e-9:
    raise AssertionError(f"{SKU}: {DIMS.length} long, the row prints {ROW.length_mm}")
if abs(DIMS.major_dia - ROW.major_mm) > 1e-3:
    raise AssertionError(
        f"{SKU}: major {DIMS.major_dia}, the row's thread is {ROW.major_mm}"
    )

# Hidden nominal source references (the live listing's values), not
# physical-edge/replica assertions: length/head Ø/head height/major Ø .XXX,
# the drive an exact 3/32 fraction. The standard-only socket depth is omitted.
SUPPLIER_PRODUCT_URL = "https://www.mcmaster.com/91251A113/"
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
    "SupplierThreadDiameter": (3, "diameter", None, "#4-40"),
    "SupplierDriveWidth": (0, "length", 32, None),
}
