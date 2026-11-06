r"""MHA-CH-06-TL-VN-86 oblique-trammel left clamp screw: McMaster 92220A165.

PURE DATA, no SolidWorks/COM calls and no ``build_*`` module in its import
closure.  Shop fixture hardware (cad/docs/subsystem-identities.md), modelled
so the jig assembly can mate it and run native interference: the
``#10-24 X 3/4 LOW-HEAD SHCS`` that holds the MHA-CH-13 strap blank's
outboard left tail down through the TL-24 riser into TL-21's flat-bottom
blind tap; the low head seats directly on the strap.  It is the C4 fastener
table's ``LEFT_CLAMP`` row.  It is its own row on the jig's BOM; the shop
inventory carries no screw stock (no ``INVENTORY_ID``), and the assembly
steps cite it by item and callout (``fasteners.callout``).

Cut to fit: the carrier's receiver is blind (owner requirement), so each
screw is cut at assembly to the actual riser-plus-strap grip plus the
``fasteners.LEFT_CLAMP_INSERTION`` reach below the carrier top, its tip
restored to at most one incomplete pitch.  The part is modelled as
installed, ``CUT_LENGTH`` under the head at the nominal grip
(``build_92220A165(cut_length=...)``).  The sheet prints that length as a
reference, cut to fit, and the as-supplied 3/4 in as a separate stock
witness beside the solid (the TL-VN-64 idiom).

Sources:

* SOURCED, https://www.mcmaster.com/92220A165/ read live 2026-11-06:
  #10-24 UNC class 3A right hand, 3/4 in under the head, fully threaded,
  low head Ø5/16 x 3/32 in, 3/32 in hex, 140,000 psi, Rockwell C39,
  ASME B18.3, flat tip, black oxide, $11.38 per pack of 50.
* FROM THE FASTENER TABLE (imported): thread, printed length, head, count,
  grip, cut length and the joint (``fasteners.LEFT_CLAMP``); the catalogue's
  thread and length must equal the row's (checked at import).
* STANDARD: the page gives no socket depth, so it is ASME B18.3's minimum
  key engagement for the #10 low head (``_mcmaster_92220a165``).
* The geometry is the 91251A family's catalogue recipe
  (``diag_mcmaster_socket_head.build_socket_head``); no vendor model was read
  and none is replica-gated (user ruling 2026-10-17).  The recipe is
  ``diagnostics/diag_build_92220A165.py``; its standalone run is
  catalog-only.

Part frame: screw axis local +Y through the origin, published as
``ScrewAxis`` (Front ∩ Right); the bearing face (head underside) at y = 0
(the Top Plane), the cut tip at y = -CUT_LENGTH.  Mate the Top Plane to the
head's seat, the strap's top face.
"""

from __future__ import annotations

import ch_rocker_arm_tl_oblique_carrier_spec as carrier
import ch_rocker_arm_tl_oblique_fasteners_spec as fasteners
from _mcmaster_92220a165 import DIMS, LENGTH_TEXT, PART_NO, THREAD
from _printed_tolerance import printed_band_mm

SKU = PART_NO
ROW = fasteners.LEFT_CLAMP
QUANTITY = ROW.count
PACK_QUANTITY = 50  # McMaster sells 92220A165 in packs of 50
CALLOUT = fasteners.callout(ROW)  # "#10-24 X 3/4 LOW-HEAD SHCS"

if (THREAD, LENGTH_TEXT, fasteners.LOW_HEAD) != (ROW.thread, ROW.length, ROW.head):
    raise AssertionError(f"{SKU} is not the screw of {ROW.joint}")
if abs(DIMS.length - ROW.length_mm) > 1e-9:
    raise AssertionError(f"{SKU}: {DIMS.length} long, the row prints {ROW.length_mm}")
if abs(DIMS.major_dia - ROW.major_mm) > 1e-3:
    raise AssertionError(
        f"{SKU}: major {DIMS.major_dia}, the row's thread is {ROW.major_mm}"
    )
CUT_LENGTH = ROW.cut_length_mm  # nominal grip + the insertion window's middle
CUT_INSERTION = fasteners.LEFT_CLAMP_INSERTION  # tip reach below TL-21's top
if not 0.0 < CUT_LENGTH < DIMS.length:
    raise AssertionError(f"{SKU}: a {CUT_LENGTH} mm cut is not inside the bought screw")

# --- Rule 18 and the blind receiver -------------------------------------------
# The restored tip leaves at most one incomplete pitch; the tap's mouth takes
# the title block's edge break.  Its full thread ends above the receiver's
# guaranteed full thread, and the tip stops short of the flat pilot floor.
TIP_INCOMPLETE_LENGTH = DIMS.pitch
SCREW_FULL_THREAD_MIN = CUT_INSERTION[0] - TIP_INCOMPLETE_LENGTH - carrier.TAP_MOUTH_BREAK
ENGAGEMENT_MIN = min(SCREW_FULL_THREAD_MIN, carrier.LEFT_CLAMP_FULL_THREAD_MIN)
if ENGAGEMENT_MIN < ROW.min_engagement_d * DIMS.major_dia:
    raise AssertionError(
        f"{SKU}: {ENGAGEMENT_MIN:.3f} full thread in TL-21, under rule 18's 1.5D"
    )
if CUT_INSERTION[1] - TIP_INCOMPLETE_LENGTH > carrier.LEFT_CLAMP_THREAD_DEPTH:
    raise AssertionError(f"{SKU}: the screw's full thread runs past TL-21's full thread")
# The pilot's depth carries the .XX band; the tip stays above its shallowest.
PILOT_DEPTH_MIN = carrier.LEFT_CLAMP_DRILL_DEPTH - printed_band_mm(2, unit=carrier.UNIT)
if not CUT_INSERTION[1] < PILOT_DEPTH_MIN:
    raise AssertionError(f"{SKU}: the cut tip reaches TL-21's flat pilot floor")

# Exact-current product table and engineering drawing read 2026-11-06.
# Hidden nominal source references, not physical-edge/replica assertions.
# The installed screw is cut to fit: its length on the solid prints as a
# reference (CutLength), and the as-supplied 3/4 in is a SEPARATE stock
# witness left of the solid, labelled as stock.  The thread Ø's chord lies on
# the cut end, not across the shank.  The standard-only socket depth is
# omitted.
SUPPLIER_PRODUCT_URL = "https://www.mcmaster.com/92220A165/"
SUPPLIER_DRAWING_URL = (
    "https://www.mcmaster.com/mvC/Library/CAD2/20260806/77F91D12/"
    "92220A165_Alloy%20Steel%20Low-Profile%20Socket%20Head%20ScrewX.GIF"
)
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
    "SupplierLength": (0, "length", 4, "AS-SUPPLIED STOCK LENGTH"),
    "SupplierHeadDiameter": (0, "diameter", 16, None),
    "SupplierHeadHeight": (0, "length", 32, None),
    "SupplierThreadDiameter": (3, "diameter", None, "#10-24"),
    "SupplierDriveWidth": (0, "length", 32, None),
}
