r"""MHA-CH-06-TL-VN-66 oblique-trammel leadscrew nut screw: McMaster 91251A110.

PURE DATA, no SolidWorks/COM calls and no ``build_*`` module in its import
closure.  Shop fixture hardware (cad/docs/subsystem-identities.md), modelled
so the jig assembly can mate it and run native interference: the
``#4-40 X 1/2 SHCS`` that holds the Tr8 flanged leadscrew nut to the TL-29 nut bracket, into a blind tap; the head seats on a TL-VN-72 flat washer on the nut's flange.
It is the C4 fastener table's ``NUT_TO_NUT_BRACKET`` row.  It is its own row on the
jig's BOM; the shop inventory carries no screw stock (no ``INVENTORY_ID``),
and the assembly steps cite it by item and callout (``fasteners.callout``).

Sources:

* SOURCED, the #4-40 x 1/2 in black-oxide listing row read live 2026-10-19
  (https://www.mcmaster.com/products/socket-head-screws/steel-socket-head-screws~~/thread-size~4-40/finish~black-oxide/length~1-2-2/; the product page is login-walled):
  #4-40, 1/2 in under the head, fully threaded, head Ø0.183 x 0.112 in, 170,000 psi, $12.26 per pack of 100.
* FROM THE FASTENER TABLE (imported): thread, printed length, head, count,
  grip and the joint (``fasteners.NUT_TO_NUT_BRACKET``); the catalogue's thread and
  length must equal the row's (checked at import).
* STANDARD: the row gives no drive or socket depth, so it is the family's #4
  hex and the standard's minimum key engagement (``_mcmaster_91251a110``),
  and the head's least diameter is ASME B18.3's (``HEAD_DIA_MIN``).
* The geometry is the 91251A family's catalogue recipe
  (``diag_mcmaster_socket_head.build_socket_head``: plain cylindrical head,
  0.75P tip chamfer, 45 deg thread neck); no vendor model was downloaded
  (login-walled), so it is NOT replica-gated.  The recipe is
  ``diagnostics/diag_build_91251A110.py``; its standalone run is catalog-only.

Part frame: screw axis local +Y through the origin, published as
``ScrewAxis`` (Front ∩ Right); the bearing face (head underside) at y = 0 (the Top Plane), the tip at
y = -length.  Mate the Top Plane to the head's seat, the TL-VN-72 washer's top face.
"""

from __future__ import annotations

import _mcmaster_91251a110 as _catalogue
import ch_rocker_arm_tl_oblique_fasteners_spec as fasteners
from _mcmaster_91251a110 import DIMS, LENGTH_TEXT, PART_NO, THREAD

SKU = PART_NO
ROW = fasteners.NUT_TO_NUT_BRACKET
QUANTITY = ROW.count
PACK_QUANTITY = _catalogue.PACK_QUANTITY  # 100
HEAD_DIA_MIN = _catalogue.HEAD_DIA_MIN  # ASME B18.3: the head's bearing bound
CALLOUT = fasteners.callout(ROW)  # "#4-40 X 1/2 SHCS"

if (THREAD, LENGTH_TEXT, fasteners.SHCS) != (ROW.thread, ROW.length, ROW.head):
    raise AssertionError(f"{SKU} is not the screw of {ROW.joint}")
if abs(DIMS.length - ROW.length_mm) > 1e-9:
    raise AssertionError(f"{SKU}: {DIMS.length} long, the row prints {ROW.length_mm}")
if abs(DIMS.major_dia - ROW.major_mm) > 1e-3:
    raise AssertionError(
        f"{SKU}: major {DIMS.major_dia}, the row's thread is {ROW.major_mm}"
    )
