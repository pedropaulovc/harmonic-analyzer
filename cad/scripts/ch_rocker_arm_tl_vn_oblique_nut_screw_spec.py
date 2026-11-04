r"""MHA-CH-06-TL-VN-66 oblique-trammel feed nut screw: McMaster 91355A581.

PURE DATA, no SolidWorks/COM calls and no ``build_*`` module in its import
closure.  Shop fixture hardware (cad/docs/subsystem-identities.md), modelled
so the jig assembly can mate it and run native interference: the
``#4-40 X 3/4 FLANGED BHCS`` that holds the shop-made TL-27 feed nut to the
TL-32 integral feed-block lug, through the nut's Ø.170 clearance hole into
the lug's #4-40 tap, tapped THRU (owner ruling 2026-11-01, item 4, C1); the
flange bears directly on the brass nut. It is the fastener table's
``NUT_TO_FEED_BLOCK`` row. It is its own row on the jig's BOM; the shop
inventory carries no screw stock (no ``INVENTORY_ID``), and the assembly
steps cite it by item and callout (``fasteners.callout``).

Why a flanged button head (Codjiflo P1 on #2112): at the fit-up's
eccentricity (each lug tap spotted through its nut hole,
``feed_block.FIT_UP_RESIDUAL``) a #4 SHCS's Ø.141 underhead fillet needs a
Ø.170 hole mouth, and its Ø.176 head can then no longer bear outside that
hole. No McMaster #4 flat washer clears the fillet (every #4 washer's ID is
.117-.125), so a washer would seat on the fillet too. The flange's Ø.222
flat bearing face covers the Ø.174 largest hole at that eccentricity
(``feed_block``'s ``HEAD_BEARING_LAND_MIN``).

Sources:

* SOURCED, the product page read live 2026-11-02 (``_mcmaster_91355a581``):
  #4-40 UNC 3A, 3/4 in under the head, fully threaded, button head Ø0.193 x
  0.059 in, flange Ø0.234, 1/16 in hex, 120,000 psi, Rockwell C39,
  ASTM F835, $15.93 per pack of 100.
* MEASURED from the vendor STEP (not committed): the flange's 0.024 in
  thickness and its Ø0.222 flat bearing face (``BEARING_DIA_MIN``).
* STANDARD: ASME B18.3's length band; the underhead fillet bound
  (``FILLET_DIA_MAX``) is the #4 socket head cap screw's [ASSUMPTION].
* FROM THE FASTENER TABLE (imported): thread, printed length, head, count,
  grip and the joint (``fasteners.NUT_TO_FEED_BLOCK``); the catalogue's
  thread and length must equal the row's (checked at import).
* The geometry is the button head family's catalogue recipe, flanged
  (``diag_mcmaster_button_head.build_button_head``); NOT replica-gated.  The
  recipe is ``diagnostics/diag_build_91355A581.py``; its standalone run is
  catalog-only.

Part frame: screw axis local +Y through the origin, published as
``ScrewAxis`` (Front ∩ Right); the bearing face (flange underside) at y = 0
(the Top Plane), the tip at y = -length.  Mate the Top Plane to the head's
seat, the feed nut's -X face.
"""

from __future__ import annotations

import _config
import _mcmaster_91355a581 as _catalogue
import ch_rocker_arm_tl_oblique_fasteners_spec as fasteners
from _mcmaster_91355a581 import DIMS, LENGTH_TEXT, PART_NO, THREAD
from _package_units import drawing_unit

UNIT = drawing_unit(
    "parts/ch-rocker-arm-tl-vn-oblique-nut-screw",
    _config.parts("ch-rocker-arm-tl-vn-oblique-nut-screw"),
)
SKU = PART_NO
ROW = fasteners.NUT_TO_FEED_BLOCK
QUANTITY = ROW.count
PACK_QUANTITY = _catalogue.PACK_QUANTITY
BEARING_DIA_MIN = (
    _catalogue.BEARING_DIA_MIN
)  # the flange's flat face: the bearing bound
FILLET_DIA_MAX = _catalogue.FILLET_DIA_MAX
CALLOUT = fasteners.callout(ROW)  # "#4-40 X 3/4 FLANGED BHCS"

if (THREAD, LENGTH_TEXT, fasteners.FLANGED_BHCS) != (ROW.thread, ROW.length, ROW.head):
    raise AssertionError(f"{SKU} is not the screw of {ROW.joint}")
if abs(DIMS.length - ROW.length_mm) > 1e-9:
    raise AssertionError(f"{SKU}: {DIMS.length} long, the row prints {ROW.length_mm}")
if abs(DIMS.major_dia - ROW.major_mm) > 1e-3:
    raise AssertionError(
        f"{SKU}: major {DIMS.major_dia}, the row's thread is {ROW.major_mm}"
    )

# Hidden nominal source references (the live page's values), not
# physical-edge/replica assertions: length/flange Ø/head Ø/head height/major
# Ø .XXX, the drive an exact 1/16 fraction. The STEP-only flange thickness
# is omitted.
SUPPLIER_PRODUCT_URL = "https://www.mcmaster.com/91355A581/"
SUPPLIER_REFERENCE_DIMENSIONS = (
    ("SupplierLength", -DIMS.length, "vertical"),
    ("SupplierFlangeDiameter", DIMS.flange_dia, "horizontal"),
    ("SupplierHeadDiameter", DIMS.head_dia, "horizontal"),
    ("SupplierHeadHeight", DIMS.head_h, "vertical"),
    ("SupplierThreadDiameter", DIMS.major_dia, "horizontal"),
    ("SupplierDriveWidth", DIMS.hex_af, "horizontal"),
)
SUPPLIER_REFERENCE_STARTS = {
    "SupplierLength": (DIMS.major_dia / 2.0, 0.0),
    "SupplierFlangeDiameter": (-DIMS.flange_dia / 2.0, 0.0),
    "SupplierHeadDiameter": (-DIMS.head_dia / 2.0, 0.0),
    "SupplierHeadHeight": (DIMS.flange_dia / 2.0, 0.0),
    "SupplierThreadDiameter": (-DIMS.major_dia / 2.0, 0.0),  # on the bearing-face edge
    "SupplierDriveWidth": (-DIMS.hex_af / 2.0, 0.0),
}
SUPPLIER_REFERENCE_PLANES = {
    "SupplierFlangeDiameter": "Top",
    "SupplierHeadDiameter": "Top",
    "SupplierDriveWidth": "Top",
}
SUPPLIER_REFERENCE_SIDES = {
    "SupplierLength": "right",
    "SupplierFlangeDiameter": "top",
    "SupplierHeadDiameter": "top",
    "SupplierHeadHeight": "left",
    "SupplierThreadDiameter": "bottom",
    "SupplierDriveWidth": "bottom",
}
SUPPLIER_REFERENCE_FORMATS = {
    "SupplierLength": (3, "length", None, None),
    "SupplierFlangeDiameter": (3, "diameter", None, None),
    "SupplierHeadDiameter": (3, "diameter", None, None),
    "SupplierHeadHeight": (3, "length", None, None),
    "SupplierThreadDiameter": (3, "diameter", None, "#4-40"),
    "SupplierDriveWidth": (0, "length", 16, None),
}
