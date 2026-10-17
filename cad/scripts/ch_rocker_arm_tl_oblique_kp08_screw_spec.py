r"""MHA-CH-006-TL-45 oblique-trammel pillow block screw: McMaster 91290A148.

PURE DATA, no SolidWorks/COM calls and no ``build_*`` module in its import
closure.  Shop fixture hardware (cad/docs/subsystem-identities.md), modelled
so the jig assembly can mate it and run native interference: the
``M4 X 12 SHCS`` that holds a KP08 pillow block to its TL-28 end bracket, tapped THRU; the head seats on the KP08's foot (its thickness is UNVERIFIED in the fastener table).
It is the C4 fastener table's ``KP08_TO_BRACKET`` row.  It is its own row on the
jig's BOM; the shop inventory carries no screw stock (no ``INVENTORY_ID``),
and the assembly steps cite it by item and callout (``fasteners.callout``).

Sources:

* SOURCED, https://www.mcmaster.com/91290A148/ read live 2026-10-17:
  M4 x 0.7 mm class 5g6g, 12 mm under the head, fully threaded, head Ø7 x 4 mm, 3 mm hex, class 12.9, Rockwell C41, DIN 912 / ISO 4762, $12.30 per pack of 100.
* FROM THE FASTENER TABLE (imported): thread, printed length, head, count,
  grip and the joint (``fasteners.KP08_TO_BRACKET``); the catalogue's thread and
  length must equal the row's (checked at import).
* STANDARD: the page gives no socket depth, so it is the standard's
  minimum key engagement (``_mcmaster_91290a148``; the 91251A108 convention).
* The geometry is the 91251A family's catalogue recipe
  (``diag_mcmaster_socket_head.build_socket_head``: plain cylindrical head,
  0.75P tip chamfer, 45 deg thread neck); the vendor model (downloaded
  2026-10-17) is a reading note only, NOT replica-gated (user ruling
  2026-10-17).  The recipe is ``diagnostics/diag_build_91290A148.py``; its
  standalone run is catalog-only.

Part frame: screw axis local +Y through the origin, published as
``ScrewAxis`` (Front ∩ Right); the bearing face (head underside) at y = 0 (the Top Plane), the tip at
y = -length.  Mate the Top Plane to the head's seat, the KP08's foot (its thickness is UNVERIFIED in the fastener table).
"""

from __future__ import annotations

import ch_rocker_arm_tl_oblique_fasteners_spec as fasteners
from _mcmaster_91290a148 import DIMS, LENGTH_TEXT, PART_NO, THREAD

SKU = PART_NO
ROW = fasteners.KP08_TO_BRACKET
QUANTITY = ROW.count
PACK_QUANTITY = 100  # McMaster sells 91290A148 in packs of 100
CALLOUT = fasteners.callout(ROW)  # "M4 X 12 SHCS"

if (THREAD, LENGTH_TEXT, fasteners.SHCS) != (ROW.thread, ROW.length, ROW.head):
    raise AssertionError(f"{SKU} is not the screw of {ROW.joint}")
if abs(DIMS.length - ROW.length_mm) > 1e-9:
    raise AssertionError(f"{SKU}: {DIMS.length} long, the row prints {ROW.length_mm}")
if abs(DIMS.major_dia - ROW.major_mm) > 1e-3:
    raise AssertionError(
        f"{SKU}: major {DIMS.major_dia}, the row's thread is {ROW.major_mm}"
    )
