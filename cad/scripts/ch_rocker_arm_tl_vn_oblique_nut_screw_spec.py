r"""MHA-CH-06-TL-VN-66 oblique-trammel leadscrew nut screw: Olander 4C50BHCA.

PURE DATA, no SolidWorks/COM calls and no ``build_*`` module in its import
closure.  Shop fixture hardware (cad/docs/subsystem-identities.md), modelled
so the jig assembly can mate it and run native interference: the
``#4-40 X 1/2 BHCS`` that holds the Tr8 flanged leadscrew nut to the TL-32
integral feed-block lug, into a blind tap; the button head bears directly
on the brass flange (owner ruling 2026-10-20: button heads, no washers).
It is the fastener table's ``NUT_TO_FEED_BLOCK`` row. It is its own row
on the jig's BOM; the shop inventory carries no screw stock (no
``INVENTORY_ID``), and the assembly steps cite it by item and callout
(``fasteners.callout``).

Sources:

* SOURCED, the Olander 4C50BHCA listing read live 2026-10-20
  (``_olander_4c50bhca``): #4-40 x 1/2 in alloy steel button head socket cap
  screw, ASME B18.3, plain finish, head Ø0.213 / 0.201 x 0.059 / 0.051 in,
  0.063 in hex.  Olander lists McMaster-Carr 91255A110 as an alternate code
  (``MCMASTER_XREF``), a cross-reference only.
* STANDARD: ASME B18.3 Table 11, the head's least diameter, its runout and
  the underhead fillet's F max (``HEAD_DIA_MIN``, ``HEAD_RUNOUT_FIM``,
  ``FILLET_DIA_MAX``).
* FROM THE FASTENER TABLE (imported): thread, printed length, head, count,
  grip and the joint (``fasteners.NUT_TO_FEED_BLOCK``); the catalogue's
  thread and length must equal the row's (checked at import).
* The geometry is the shared button-head recipe plus a nominal underhead
  fillet (``diagnostics/diag_build_4C50BHCA.py``); no vendor model was
  downloaded, so it is NOT replica-gated.  Its standalone run is
  catalog-only.

Part frame: screw axis local +Y through the origin, published as
``ScrewAxis`` (Front ∩ Right); the bearing face (head underside) at y = 0
(the Top Plane), the tip at y = -length.  Mate the Top Plane to the head's
seat, the nut flange's -X face.
"""

from __future__ import annotations

import _olander_4c50bhca as _catalogue
import ch_rocker_arm_tl_oblique_fasteners_spec as fasteners
from _olander_4c50bhca import DIMS, LENGTH_TEXT, PART_NO, THREAD

SKU = PART_NO
MCMASTER_XREF = _catalogue.MCMASTER_XREF
ROW = fasteners.NUT_TO_FEED_BLOCK
QUANTITY = ROW.count
HEAD_DIA_MIN = _catalogue.HEAD_DIA_MIN  # ASME B18.3 A min: the bearing bound
HEAD_RUNOUT_FIM = _catalogue.HEAD_RUNOUT_FIM
FILLET_DIA_MAX = _catalogue.FILLET_DIA_MAX
CALLOUT = fasteners.callout(ROW)  # "#4-40 X 1/2 BHCS"

if (THREAD, LENGTH_TEXT, fasteners.BHCS) != (ROW.thread, ROW.length, ROW.head):
    raise AssertionError(f"{SKU} is not the screw of {ROW.joint}")
if abs(DIMS.length - ROW.length_mm) > 1e-9:
    raise AssertionError(f"{SKU}: {DIMS.length} long, the row prints {ROW.length_mm}")
if abs(DIMS.major_dia - ROW.major_mm) > 1e-3:
    raise AssertionError(
        f"{SKU}: major {DIMS.major_dia}, the row's thread is {ROW.major_mm}"
    )

# Exact-current Olander product table read 2026-10-21; not its McMaster xref.
# Hidden nominal source references, not physical-edge/replica assertions.
# Head bands are supplied three-place limits, owned by new model carriers.
# The .063 hex table entry is rounded ink for the unchanged native 1/16;
# neither the solid nor the carrier is changed to a fictitious .063 hex.
# No numeric major diameter or socket depth is given by this source.
SUPPLIER_PRODUCT_URL = "https://www.olander.com/items/4C50BHCA"
SUPPLIER_REFERENCE_DIMENSIONS = (
    ("SupplierLength", -DIMS.length, "vertical"),
    ("SupplierHeadDiameter", DIMS.head_dia, "horizontal"),
    ("SupplierHeadHeight", DIMS.head_h, "vertical"),
    ("SupplierDriveWidth", DIMS.hex_af, "horizontal"),
)
SUPPLIER_REFERENCE_STARTS = {
    "SupplierLength": (DIMS.major_dia / 2.0, 0.0),
    "SupplierHeadDiameter": (-DIMS.head_dia / 2.0, 0.0),
    "SupplierHeadHeight": (DIMS.head_dia / 2.0, 0.0),
    "SupplierDriveWidth": (-DIMS.hex_af / 2.0, 0.0),
}
SUPPLIER_REFERENCE_PLANES = {
    "SupplierHeadDiameter": "Top",
    "SupplierDriveWidth": "Top",
}
SUPPLIER_REFERENCE_SIDES = {
    "SupplierLength": "right",
    "SupplierHeadDiameter": "top",
    "SupplierHeadHeight": "left",
    "SupplierDriveWidth": "bottom",
}
SUPPLIER_REFERENCE_FORMATS = {
    "SupplierLength": (0, "length", 2, "4-40"),
    "SupplierHeadDiameter": (3, "diameter", None, None),
    "SupplierHeadHeight": (3, "length", None, None),
    "SupplierDriveWidth": (3, "length", None, None),
}
# Absolute source limits in inches, not stock-recipe tolerances or fit bands.
SUPPLIER_REFERENCE_LIMITS_IN = {
    "SupplierHeadDiameter": (0.201, 0.213),
    "SupplierHeadHeight": (0.051, 0.059),
}
