r"""MHA-CH-06-TL-VN-85 oblique-trammel hub screw: McMaster 92220A163.

PURE DATA, no SolidWorks/COM calls and no ``build_*`` module in its import
closure.  Shop fixture hardware (cad/docs/subsystem-identities.md), modelled
so the jig assembly can mate it and run native interference: the
``#10-24 X 1/2 LOW-HEAD SHCS`` that clamps the MHA-CH-13 strap down on the
TL-34 sleeve through the TL-35 brass washer, into the TL-33 hub stud's blind
nose tap.  It is the C4 fastener table's ``HUB_CLAMP`` row.  It is its own row
on the jig's BOM; the shop inventory carries no screw stock (no
``INVENTORY_ID``), and the assembly steps cite it by item and callout
(``fasteners.callout``).  The low head keeps the hub clamp under the CR
clamp's head, the jig's tallest (``ch_rocker_arm_tl_oblique_holding_spec``).

Used as bought, full length: the tip stops inside the stud's full thread at
every printed limit (``INSERTION_MAX``), so it never bottoms.

Sources:

* SOURCED, https://www.mcmaster.com/92220A163/ read live 2026-11-06:
  #10-24 UNC class 3A right hand, 1/2 in under the head, fully threaded,
  low head Ø5/16 x 3/32 in, 3/32 in hex, 140,000 psi, Rockwell C39,
  ASME B18.3, flat tip, black oxide, $11.80 per pack of 50.
* FROM THE FASTENER TABLE (imported): thread, printed length, head, count,
  grip and the joint (``fasteners.HUB_CLAMP``); the catalogue's thread and
  length must equal the row's (checked at import).
* STANDARD: the page gives no socket depth, so it is ASME B18.3's minimum
  key engagement for the #10 low head (``_mcmaster_92220a163``).
* The geometry is the 91251A family's catalogue recipe
  (``diag_mcmaster_socket_head.build_socket_head``: plain cylindrical head,
  0.75P tip chamfer, 45 deg thread neck); no vendor model was read and none
  is replica-gated (user ruling 2026-10-17).  The recipe is
  ``diagnostics/diag_build_92220A163.py``; its standalone run is
  catalog-only.

Part frame: screw axis local +Y through the origin, published as
``ScrewAxis`` (Front ∩ Right); the bearing face (head underside) at y = 0
(the Top Plane), the tip at y = -LENGTH.  Mate the Top Plane to the head's
seat, the TL-35 washer's top face.
"""

from __future__ import annotations

import ch_rocker_arm_spec as rocker
import ch_rocker_arm_tl_oblique_fasteners_spec as fasteners
import ch_rocker_arm_tl_oblique_hub_stud_spec as stud
import ch_rocker_arm_tl_oblique_hub_washer_spec as washer
import ch_rocker_arm_tl_oblique_trammel_spec as trammel
from _mcmaster_92220a163 import DIMS, LENGTH_TEXT, PART_NO, THREAD
from _printed_tolerance import edge_break_chamfer_mm, printed_band_mm

SKU = PART_NO
ROW = fasteners.HUB_CLAMP
QUANTITY = ROW.count
PACK_QUANTITY = 50  # McMaster sells 92220A163 in packs of 50
CALLOUT = fasteners.callout(ROW)  # "#10-24 X 1/2 LOW-HEAD SHCS"
LENGTH = DIMS.length  # 1/2 in, modelled as bought

if (THREAD, LENGTH_TEXT, fasteners.LOW_HEAD) != (ROW.thread, ROW.length, ROW.head):
    raise AssertionError(f"{SKU} is not the screw of {ROW.joint}")
if abs(LENGTH - ROW.length_mm) > 1e-9:
    raise AssertionError(f"{SKU}: {LENGTH} long, the row prints {ROW.length_mm}")
if abs(DIMS.major_dia - ROW.major_mm) > 1e-3:
    raise AssertionError(
        f"{SKU}: major {DIMS.major_dia}, the row's thread is {ROW.major_mm}"
    )

# --- Grip: washer + strap above the stud's nose top ---------------------------
_WASHER_BAND = printed_band_mm(washer.THICK_PLACES, unit=washer.UNIT)
GRIP_MAX = (
    washer.THICK
    + _WASHER_BAND
    + rocker.ARM_THICKNESS
    + rocker.ARM_THICKNESS_BAND[0]
    - (stud.TIP_SET - stud.TIP_SET_BAND)
)
GRIP_MIN = (
    washer.THICK
    - _WASHER_BAND
    + rocker.ARM_THICKNESS
    + rocker.ARM_THICKNESS_BAND[1]
    - (stud.TIP_SET + stud.TIP_SET_BAND)
)
if abs(ROW.grip_mm - (washer.THICK + trammel.STRAP_THICK - stud.TIP_SET)) > 1e-9:
    raise AssertionError(f"{SKU}: the fastener table's grip is not washer + strap - proud")

# --- Rule 18: full thread in the stud's nose tap -----------------------------
# ASME B18.3, through 1 in long: +0/-0.03 in (the 91251A583 precedent).  Rule
# 18 permits one to one-and-a-half incomplete threads: charge 1.5P at the
# screw's tip.  The receiver's mouth takes the title block's edge break.
LENGTH_MIN = LENGTH - 0.03 * trammel.INCH
TIP_INCOMPLETE_LENGTH = 1.5 * DIMS.pitch
TAP_MOUTH_BREAK = edge_break_chamfer_mm(unit=stud.UNIT)
SCREW_FULL_THREAD_MIN = LENGTH_MIN - GRIP_MAX - TAP_MOUTH_BREAK - TIP_INCOMPLETE_LENGTH
RECEIVER_FULL_THREAD = stud.TAP_FULL_DEPTH_MIN - TAP_MOUTH_BREAK
ENGAGEMENT_MIN = min(SCREW_FULL_THREAD_MIN, RECEIVER_FULL_THREAD)
if ENGAGEMENT_MIN < ROW.min_engagement_d * DIMS.major_dia:
    raise AssertionError(
        f"{SKU}: {ENGAGEMENT_MIN:.3f} full thread in TL-33, under rule 18's 1.5D"
    )
# The longest screw through the thinnest grip stops inside the full thread.
INSERTION_MAX = LENGTH - GRIP_MIN
if not INSERTION_MAX < stud.TAP_FULL_DEPTH_MIN:
    raise AssertionError(f"{SKU}: the tip reaches past TL-33's full thread")

# Exact-current product table and engineering drawing read 2026-11-06.
# Hidden nominal source references, not physical-edge/replica assertions.
# Drawing precision: length .XXX; head Ø, head height and drive the page's
# exact fractions.  The standard-only socket depth is omitted.
SUPPLIER_PRODUCT_URL = "https://www.mcmaster.com/92220A163/"
SUPPLIER_DRAWING_URL = (
    "https://www.mcmaster.com/mvC/Library/CAD2/20260806/95CA9037/"
    "92220A163_Alloy%20Steel%20Low-Profile%20Socket%20Head%20ScrewX.GIF"
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
    "SupplierHeadDiameter": (0, "diameter", 16, None),
    "SupplierHeadHeight": (0, "length", 32, None),
    "SupplierThreadDiameter": (3, "diameter", None, "#10-24"),
    "SupplierDriveWidth": (0, "length", 32, None),
}
