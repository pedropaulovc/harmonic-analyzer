r"""MHA-CH-06-TL-VN-62 oblique-trammel KP08 screw: McMaster 91251A196.

PURE DATA, no SolidWorks/COM calls and no ``build_*`` module in its import
closure.  Shop fixture hardware (cad/docs/subsystem-identities.md), modelled
so the jig assembly can mate it and run native interference: the
``#8-32 X 5/8 SHCS`` that holds a KP08 pillow block to its TL-28 end bracket,
down through the block's Ø5 foot hole into the bracket's KP08-face thread
(.436 deep, ``end_bracket.KP08_THREAD_DEPTH``); the head seats on the KP08's
foot (its thickness is UNVERIFIED, #2184).  It is the C4 fastener table's
``KP08_TO_BRACKET`` row, four in the jig.  It is its own row on the jig's
BOM; the shop inventory carries no screw stock (no ``INVENTORY_ID``), and the
assembly steps cite it by item and callout (``fasteners.callout``).

Oblique simplification PR2 (owner ruling 2026-11-06, Main, option B): TL-28
has two holes, each tapped from both faces; the bar screws below are the
jig's common #8-32 x 3/4 (TL-VN-61), and this 5/8 is the owner-approved
second length (the 3/4 from the top would meet the bar screw's tip). The
same SKU held TL-28 to TL-20 before PR2; it replaces the #6-32 button heads
(91255A150, TL-VN-65, retired).

The head on the KP08 foot (``HEAD_OVER_HOLE``): the #8's float in the Ø5
hole at its minimum major (``leadscrew.KP08_SCREW_FLOAT_MAX``) is under the
head's least flat-bearing radius over the hole, so the head bears on the
foot at full float.

Sources:

* SOURCED, https://www.mcmaster.com/91251A196/ read live 2026-10-17:
  #8-32 UNC class 3A, 5/8 in under the head, fully threaded, head Ø0.27 x 0.164 in, 9/64 in hex, Rockwell C37, ASTM A574, 170,000 psi, $15.24 per pack of 100.
* STANDARD: ASME B18.3-2012 Table 1 (hexagon socket head cap screws), #8
  row: head diameter A 0.257 in minimum (``HEAD_DIA_MIN``) and head edge
  break K 0.008 in maximum (``HEAD_EDGE_BREAK_MAX``); note (12) lets the
  edge between bearing surface and head side be broken by up to K measured
  along the bearing surface, so the least flat bearing is A min - 2K =
  0.241 in (``HEAD_BEARING_DIA_MIN``), the one taken on the KP08 foot.
  https://www.finesz.com/pic/ASME%20B18.3.pdf (0.262 in is the LOW HEAD
  socket cap screw's A min, Table 12, not this screw's).
* FROM THE FASTENER TABLE (imported): thread, printed length, head, count,
  grip and the joint (``fasteners.KP08_TO_BRACKET``); the catalogue's thread and
  length must equal the row's (checked at import).
* STANDARD: the page gives no socket depth, so it is the standard's
  minimum key engagement (``_mcmaster_91251a196``; the 91251A108 convention).
* The geometry is the 91251A family's catalogue recipe
  (``diag_mcmaster_socket_head.build_socket_head``: plain cylindrical head,
  0.75P tip chamfer, 45 deg thread neck); the vendor model (downloaded
  2026-10-17) is a reading note only, NOT replica-gated (user ruling
  2026-10-17).  The recipe is ``diagnostics/diag_build_91251A196.py``; its
  standalone run is catalog-only.

Part frame: screw axis local +Y through the origin, published as
``ScrewAxis`` (Front ∩ Right); the bearing face (head underside) at y = 0 (the Top Plane), the tip at
y = -length.  Mate the Top Plane to the head's seat, the KP08's foot.
"""

from __future__ import annotations

import _config
import ch_rocker_arm_tl_oblique_fasteners_spec as fasteners
import ch_rocker_arm_tl_vn_oblique_leadscrew_spec as leadscrew
from _mcmaster_91251a196 import DIMS, LENGTH_TEXT, PART_NO, THREAD
from _package_units import drawing_unit

UNIT = drawing_unit(
    "parts/ch-rocker-arm-tl-vn-oblique-bracket-screw",
    _config.parts("ch-rocker-arm-tl-vn-oblique-bracket-screw"),
)
SKU = PART_NO
ROW = fasteners.KP08_TO_BRACKET
QUANTITY = ROW.count
PACK_QUANTITY = 100  # McMaster sells 91251A196 in packs of 100
CALLOUT = fasteners.callout(ROW)  # "#8-32 X 5/8 SHCS"

if (THREAD, LENGTH_TEXT, fasteners.SHCS) != (ROW.thread, ROW.length, ROW.head):
    raise AssertionError(f"{SKU} is not the screw of {ROW.joint}")
if abs(DIMS.length - ROW.length_mm) > 1e-9:
    raise AssertionError(f"{SKU}: {DIMS.length} long, the row prints {ROW.length_mm}")
if abs(DIMS.major_dia - ROW.major_mm) > 1e-3:
    raise AssertionError(
        f"{SKU}: major {DIMS.major_dia}, the row's thread is {ROW.major_mm}"
    )
# The catalogue's tensile strength (the jig assembly spec's screw-stress
# budget at its torque).
TENSILE_PSI = 170_000

# --- The head on the KP08 foot at full float -----------------------------------
# The KP08 floats on its screws by the hole's radial clearance (the #8 at its
# UNC-3A minimum major in the UNVERIFIED Ø5) while F1B aligns it; the head's
# least flat bearing (ASME B18.3 Table 1: A min less K on each edge, note
# (12)) still covers the hole at that float, and its annulus out to
# HEAD_BEARING_R is the foot-bearing budget's (jig assembly spec).
HEAD_DIA_MIN = 0.257 * 25.4  # ASME B18.3 Table 1 #8, A minimum
HEAD_EDGE_BREAK_MAX = 0.008 * 25.4  # ASME B18.3 Table 1 #8, K maximum
HEAD_BEARING_DIA_MIN = HEAD_DIA_MIN - 2.0 * HEAD_EDGE_BREAK_MAX  # .241, 6.121
HEAD_BEARING_R = HEAD_BEARING_DIA_MIN / 2.0  # 3.061
HOLE_FLOAT = leadscrew.KP08_SCREW_FLOAT_MAX  # 0.487
HEAD_OVER_HOLE = HEAD_BEARING_R - leadscrew.KP08_HOLE_DIA / 2.0  # 0.561
if not HEAD_OVER_HOLE > HOLE_FLOAT:  # 0.074 to spare
    raise AssertionError(f"{SKU}: the head falls into the KP08 hole at full float")

# Exact-current product table and engineering drawing read 2026-10-21.
# Hidden nominal source references, not physical-edge/replica assertions.
# Drawing precision: length/head Ø/head height/major Ø .XXX,
# drive an exact 9/64 fraction. The standard-only socket depth is omitted.
SUPPLIER_PRODUCT_URL = "https://www.mcmaster.com/91251A196/"
SUPPLIER_DRAWING_URL = (
    "https://www.mcmaster.com/mvC/Library/CAD2/20260108/58F0D646/"
    "91251A196_Black-Oxide%20Alloy%20Steel%20Socket%20Head%20ScrewX.GIF"
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
