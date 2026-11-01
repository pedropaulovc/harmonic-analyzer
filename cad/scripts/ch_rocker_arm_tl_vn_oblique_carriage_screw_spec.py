r"""MHA-CH-06-TL-VN-64 oblique-trammel carriage screw: McMaster 91290A168.

PURE DATA, no SolidWorks/COM calls and no ``build_*`` module in its import
closure.  Shop fixture hardware (cad/docs/subsystem-identities.md), modelled
so the jig assembly can mate it and run native interference: the
``M4 X 20 SHCS`` that holds a TL-22 pivot block to its HGH15CA carriage (the carriage's M4 x 5 holes); the head seats on the floor of TL-22's counterbore.
It is the C4 fastener table's ``BLOCK_TO_CARRIAGE`` row.  It is its own row on the
jig's BOM; the shop inventory carries no screw stock (no ``INVENTORY_ID``),
and the assembly steps cite it by item and callout (``fasteners.callout``).

Sources:

* SOURCED, https://www.mcmaster.com/91290A168/ read live 2026-10-17:
  M4 x 0.7 mm class 5g6g, 20 mm under the head, fully threaded, head Ø7 x 4 mm, 3 mm hex, class 12.9, Rockwell C41, DIN 912 / ISO 4762, $14.47 per pack of 100.
* FROM THE FASTENER TABLE (imported): thread, printed length, head, count,
  grip and the joint (``fasteners.BLOCK_TO_CARRIAGE``); the catalogue's thread and
  length must equal the row's (checked at import).
* STANDARD: the page gives no socket depth, so it is the standard's
  minimum key engagement (``_mcmaster_91290a168``; the 91251A108 convention).
* The geometry is the 91251A family's catalogue recipe
  (``diag_mcmaster_socket_head.build_socket_head``: plain cylindrical head,
  0.75P tip chamfer, 45 deg thread neck); the vendor model (downloaded
  2026-10-17) is a reading note only, NOT replica-gated (user ruling
  2026-10-17).  The recipe is ``diagnostics/diag_build_91290A168.py``; its
  standalone run is catalog-only.

Cut to fit (owner ruling 2026-11-01, option A): each screw is cut at assembly
to its own counterbore floor (MHA-CH-06-TL-00 step 5; the pivot block spec's
``SCREW_REACH``), so the part is modelled as installed, ``CUT_LENGTH`` under
the head at the nominal .570 floor (``build_91290A168(cut_length=...)``). The
sheet prints that length as a reference, cut to fit, and the as-supplied 20 mm
as a separate stock witness beside the solid.

Part frame: screw axis local +Y through the origin, published as
``ScrewAxis`` (Front ∩ Right); the bearing face (head underside) at y = 0 (the Top Plane), the tip at
y = -CUT_LENGTH.  Mate the Top Plane to the head's seat, the floor of TL-22's counterbore.
"""

from __future__ import annotations

import ch_rocker_arm_tl_oblique_fasteners_spec as fasteners
from _mcmaster_91290a168 import DIMS, LENGTH_TEXT, PART_NO, THREAD

SKU = PART_NO
ROW = fasteners.BLOCK_TO_CARRIAGE
QUANTITY = ROW.count
PACK_QUANTITY = 100  # McMaster sells 91290A168 in packs of 100
CALLOUT = fasteners.callout(ROW)  # "M4 X 20 SHCS"

if (THREAD, LENGTH_TEXT, fasteners.SHCS) != (ROW.thread, ROW.length, ROW.head):
    raise AssertionError(f"{SKU} is not the screw of {ROW.joint}")
if abs(DIMS.length - ROW.length_mm) > 1e-9:
    raise AssertionError(f"{SKU}: {DIMS.length} long, the row prints {ROW.length_mm}")
if abs(DIMS.major_dia - ROW.major_mm) > 1e-3:
    raise AssertionError(
        f"{SKU}: major {DIMS.major_dia}, the row's thread is {ROW.major_mm}"
    )
CUT_LENGTH = ROW.cut_length_mm  # 19.28, .570 floor + .189 reach
if not 0.0 < CUT_LENGTH < DIMS.length:
    raise AssertionError(f"{SKU}: a {CUT_LENGTH} mm cut is not inside the bought screw")

# Exact-current product table and engineering drawing read 2026-10-21.
# Hidden nominal source references, not physical-edge/replica assertions.
# The drawing uses whole millimetres for every size and M4 x 0.7 metadata.
# Socket depth is a standard-only model choice and is intentionally omitted.
SUPPLIER_PRODUCT_URL = "https://www.mcmaster.com/91290A168/"
SUPPLIER_DRAWING_URL = (
    "https://www.mcmaster.com/mvC/Library/CAD2/20260302/12D8C87B/"
    "91290A168_Black-Oxide%20Alloy%20Steel%20Socket%20Head%20ScrewX.GIF"
)
# The installed screw is cut to fit: its length on the solid prints as a
# reference (CutLength), and the as-supplied 20 mm is a SEPARATE stock witness
# left of the solid, labelled as stock (the 91794A055 cut-to-fit idiom). Its
# construction chord runs down the shank's own left edge and on through the
# uncut tip the drawing outlines in phantom, so its witnesses land on drawn
# geometry; the thread Ø's chord lies on the cut end, not across the shank.
SUPPLIER_REFERENCE_DIMENSIONS = (
    ("CutLength", -CUT_LENGTH, "vertical"),
    ("SupplierLength", -DIMS.length, "vertical"),
    ("SupplierHeadDiameter", DIMS.head_dia, "horizontal"),
    ("SupplierHeadHeight", DIMS.head_h, "vertical"),
    ("SupplierThreadDiameter", DIMS.major_dia, "horizontal"),
    ("SupplierDriveWidth", DIMS.socket_af, "horizontal"),
)
SUPPLIER_REFERENCE_STARTS = {
    "CutLength": (DIMS.major_dia / 2.0, 0.0),
    "SupplierLength": (-DIMS.major_dia / 2.0, 0.0),
    "SupplierHeadDiameter": (-DIMS.head_dia / 2.0, 0.0),
    "SupplierHeadHeight": (DIMS.head_dia / 2.0, 0.0),
    "SupplierThreadDiameter": (-DIMS.major_dia / 2.0, -CUT_LENGTH),
    "SupplierDriveWidth": (-DIMS.socket_af / 2.0, 0.0),
}
SUPPLIER_REFERENCE_PLANES = {
    "SupplierHeadDiameter": "Top",
    "SupplierDriveWidth": "Top",
}
SUPPLIER_REFERENCE_SIDES = {
    "CutLength": "right",
    "SupplierLength": "left",
    "SupplierHeadDiameter": "top",
    "SupplierHeadHeight": "left",
    "SupplierThreadDiameter": "bottom",
    "SupplierDriveWidth": "bottom",
}
SUPPLIER_REFERENCE_FORMATS = {
    "CutLength": (2, "length", None, "CUT TO FIT"),
    "SupplierLength": (0, "length", None, "AS-SUPPLIED STOCK LENGTH"),
    "SupplierHeadDiameter": (0, "diameter", None, None),
    "SupplierHeadHeight": (0, "length", None, None),
    "SupplierThreadDiameter": (0, "diameter", None, "M4 x 0.7"),
    "SupplierDriveWidth": (0, "length", None, None),
}
SUPPLIER_REFERENCE_UNITS = {
    name: "mm" for name, _value, _orientation in SUPPLIER_REFERENCE_DIMENSIONS
}
