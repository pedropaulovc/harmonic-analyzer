r"""MHA-CH-06-TL-VN-65 oblique-trammel pillow block screw: McMaster 91255A150.

PURE DATA, no SolidWorks/COM calls and no ``build_*`` module in its import
closure.  Shop fixture hardware (cad/docs/subsystem-identities.md), modelled
so the jig assembly can mate it and run native interference: the
``#6-32 X 5/8 BHCS`` that holds a KP08 pillow block to its TL-28 end bracket,
tapped THRU; the head seats on the KP08's foot (its thickness is UNVERIFIED
in the fastener table).  It is the C4 fastener table's ``KP08_TO_BRACKET``
row.  It is its own row on the jig's BOM; the shop inventory carries no screw
stock (no ``INVENTORY_ID``), and the assembly steps cite it by item and
callout (``fasteners.callout``).

Why a button head (owner ruling 2026-11-04, option b): the uxcell KP08's
foot hole is the listing's Ø5, and the KP08 floats on its screws by
``HOLE_FLOAT`` (0.75) while F1B aligns it.  The former #6-32 SHCS head
(Ø.226) covered the hole by only 0.37 mm radially; the button head's Ø.262
covers it by ``HEAD_OVER_HOLE`` (0.83), so it still bears on the foot at
full float.

Sources:

* SOURCED, https://www.mcmaster.com/91255A150/ read live 2026-11-04:
  "Black-Oxide Button Head Hex-Drive Screw, Alloy Steel, 6-32 Thread Size,
  5/8" Long"; head Ø0.262 x 0.073 in, 5/64 in hex drive, fully threaded,
  140,000 psi, Rockwell C39, class 3A, ASME B18.3 / ASTM F835, $18.56 per
  pack of 100 (``_mcmaster_91255a150``).
* FROM THE FASTENER TABLE (imported): thread, printed length, head, count,
  grip and the joint (``fasteners.KP08_TO_BRACKET``); the catalogue's thread and
  length must equal the row's (checked at import).
* The geometry is the button-head law of 91255A148, the 1/2 in length of the
  same series, replica-gated against its vendor model
  (``_button_head_dimensions``); the recipe is
  ``diagnostics/diag_build_91255A150.py``, and its standalone run is
  catalog-only (no 91255A150 vendor model was downloaded).

Part frame: screw axis local +Y through the origin, published as
``ScrewAxis`` (Front ∩ Right); the bearing face (head underside) at y = 0 (the
Top Plane), the tip at y = -length.  Mate the Top Plane to the head's seat,
the KP08's foot.
"""

from __future__ import annotations

import _config
import ch_rocker_arm_tl_oblique_fasteners_spec as fasteners
import ch_rocker_arm_tl_vn_oblique_leadscrew_spec as leadscrew
from _mcmaster_91255a150 import DIMS, LENGTH_TEXT, PACK_QUANTITY, PART_NO, TENSILE_PSI, THREAD
from _package_units import drawing_unit

UNIT = drawing_unit(
    "parts/ch-rocker-arm-tl-vn-oblique-kp08-screw",
    _config.parts("ch-rocker-arm-tl-vn-oblique-kp08-screw"),
)
SKU = PART_NO
ROW = fasteners.KP08_TO_BRACKET
QUANTITY = ROW.count
CALLOUT = fasteners.callout(ROW)  # "#6-32 X 5/8 BHCS"

if (THREAD, LENGTH_TEXT, fasteners.BHCS) != (ROW.thread, ROW.length, ROW.head):
    raise AssertionError(f"{SKU} is not the screw of {ROW.joint}")
if abs(DIMS.length - ROW.length_mm) > 1e-9:
    raise AssertionError(f"{SKU}: {DIMS.length} long, the row prints {ROW.length_mm}")
if abs(DIMS.major_dia - ROW.major_mm) > 1e-3:
    raise AssertionError(
        f"{SKU}: major {DIMS.major_dia}, the row's thread is {ROW.major_mm}"
    )

# --- The head on the KP08 foot at full float -----------------------------------
# The KP08 floats on its screws by the hole's radial clearance while F1B
# aligns it; the head's OD still covers the hole at that float. Its flat
# bearing annulus (``DIMS.bearing_edge_r``, inside the band and its fillet)
# reaches the hole's far edge at that float less HEAD_LAND_AT_FULL_FLOAT,
# which may be negative: the head then bears on the rest of its annulus
# (the assembly spec's foot-bearing budget counts only that).
HOLE_FLOAT = (leadscrew.KP08_HOLE_DIA - DIMS.major_dia) / 2.0  # 0.747
HEAD_OVER_HOLE = (DIMS.head_dia - leadscrew.KP08_HOLE_DIA) / 2.0  # 0.827
HEAD_LAND_AT_FULL_FLOAT = DIMS.bearing_edge_r - leadscrew.KP08_HOLE_DIA / 2.0 - HOLE_FLOAT
if not HEAD_OVER_HOLE > HOLE_FLOAT:
    raise AssertionError(f"{SKU}: the head falls into the KP08 hole at full float")

# Exact-current product page read 2026-11-04.
# Hidden nominal source references, not physical-edge/replica assertions.
# Only the sizes needed to buy a replacement: length (under the head), head
# diameter, thread and drive. Drawing precision: length/head Ø/major Ø .XXX,
# the drive an exact 5/64 fraction.
SUPPLIER_PRODUCT_URL = "https://www.mcmaster.com/91255A150/"
SUPPLIER_REFERENCE_DIMENSIONS = (
    ("SupplierLength", -DIMS.length, "vertical"),
    ("SupplierHeadDiameter", DIMS.head_dia, "horizontal"),
    ("SupplierThreadDiameter", DIMS.major_dia, "horizontal"),
    ("SupplierDriveWidth", DIMS.hex_af, "horizontal"),
)
SUPPLIER_REFERENCE_STARTS = {
    "SupplierLength": (DIMS.major_dia / 2.0, 0.0),
    "SupplierHeadDiameter": (-DIMS.head_dia / 2.0, 0.0),
    "SupplierThreadDiameter": (-DIMS.major_dia / 2.0, 0.0),  # on the bearing-face edge
    "SupplierDriveWidth": (-DIMS.hex_af / 2.0, 0.0),
}
SUPPLIER_REFERENCE_PLANES = {
    "SupplierHeadDiameter": "Top",
    "SupplierDriveWidth": "Top",
}
SUPPLIER_REFERENCE_SIDES = {
    "SupplierLength": "right",
    "SupplierHeadDiameter": "top",
    "SupplierThreadDiameter": "bottom",
    "SupplierDriveWidth": "bottom",
}
SUPPLIER_REFERENCE_FORMATS = {
    "SupplierLength": (3, "length", None, None),
    "SupplierHeadDiameter": (3, "diameter", None, None),
    "SupplierThreadDiameter": (3, "diameter", None, "#6-32"),
    "SupplierDriveWidth": (0, "length", 64, None),
}
