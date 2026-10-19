r"""MHA-CH-06-TL-VN-65 oblique-trammel pillow block screw: McMaster 91251A150.

PURE DATA, no SolidWorks/COM calls and no ``build_*`` module in its import
closure.  Shop fixture hardware (cad/docs/subsystem-identities.md), modelled
so the jig assembly can mate it and run native interference: the
``#6-32 X 5/8 SHCS`` that holds a KP08 pillow block to its TL-28 end bracket, tapped THRU; the head seats on the KP08's foot (its thickness is UNVERIFIED in the fastener table).
It is the C4 fastener table's ``KP08_TO_BRACKET`` row.  It is its own row on the
jig's BOM; the shop inventory carries no screw stock (no ``INVENTORY_ID``),
and the assembly steps cite it by item and callout (``fasteners.callout``).

Sources:

* SOURCED, the #6-32 x 5/8 in black-oxide listing row read live 2026-10-19
  (https://www.mcmaster.com/products/socket-head-screws/steel-socket-head-screws~~/thread-size~6-32/finish~black-oxide/length~5-8-1/; the product page is login-walled):
  #6-32 UNC, 5/8 in under the head, fully threaded, head Ø0.226 x 0.138 in, 170,000 psi, US origin, $12.27 per pack of 100.
* FROM THE FASTENER TABLE (imported): thread, printed length, head, count,
  grip and the joint (``fasteners.KP08_TO_BRACKET``); the catalogue's thread and
  length must equal the row's (checked at import).
* STANDARD: the row gives no drive or socket depth, so it is the family's #6
  hex and the standard's minimum key engagement (``_mcmaster_91251a150``).
* The geometry is the 91251A family's catalogue recipe
  (``diag_mcmaster_socket_head.build_socket_head``: plain cylindrical head,
  0.75P tip chamfer, 45 deg thread neck); no vendor model was downloaded
  (login-walled), so it is NOT replica-gated.  The recipe is
  ``diagnostics/diag_build_91251A150.py``; its standalone run is catalog-only.

Part frame: screw axis local +Y through the origin, published as
``ScrewAxis`` (Front ∩ Right); the bearing face (head underside) at y = 0 (the Top Plane), the tip at
y = -length.  Mate the Top Plane to the head's seat, the KP08's foot (its thickness is UNVERIFIED in the fastener table).
"""

from __future__ import annotations

import ch_rocker_arm_tl_oblique_fasteners_spec as fasteners
from _mcmaster_91251a150 import DIMS, LENGTH_TEXT, PART_NO, THREAD

SKU = PART_NO
ROW = fasteners.KP08_TO_BRACKET
QUANTITY = ROW.count
PACK_QUANTITY = 100  # McMaster sells 91251A150 in packs of 100
CALLOUT = fasteners.callout(ROW)  # "#6-32 X 5/8 SHCS"

if (THREAD, LENGTH_TEXT, fasteners.SHCS) != (ROW.thread, ROW.length, ROW.head):
    raise AssertionError(f"{SKU} is not the screw of {ROW.joint}")
if abs(DIMS.length - ROW.length_mm) > 1e-9:
    raise AssertionError(f"{SKU}: {DIMS.length} long, the row prints {ROW.length_mm}")
if abs(DIMS.major_dia - ROW.major_mm) > 1e-3:
    raise AssertionError(
        f"{SKU}: major {DIMS.major_dia}, the row's thread is {ROW.major_mm}"
    )
