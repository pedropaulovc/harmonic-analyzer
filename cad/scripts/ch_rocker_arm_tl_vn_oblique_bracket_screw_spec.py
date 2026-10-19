r"""MHA-CH-06-TL-VN-62 oblique-trammel end bracket screw: McMaster 91251A196.

PURE DATA, no SolidWorks/COM calls and no ``build_*`` module in its import
closure.  Shop fixture hardware (cad/docs/subsystem-identities.md), modelled
so the jig assembly can mate it and run native interference: the
``#8-32 X 5/8 SHCS`` that holds a TL-28 end bracket to the TL-20 base bar, up from the bar's underside into the bracket, tapped THRU; the head seats on the floor of TL-20's counterbore.
It is the C4 fastener table's ``BRACKET_TO_BAR`` row.  It is its own row on the
jig's BOM; the shop inventory carries no screw stock (no ``INVENTORY_ID``),
and the assembly steps cite it by item and callout (``fasteners.callout``).

Sources:

* SOURCED, https://www.mcmaster.com/91251A196/ read live 2026-10-17:
  #8-32 UNC class 3A, 5/8 in under the head, fully threaded, head Ø0.27 x 0.164 in, 9/64 in hex, Rockwell C37, ASTM A574, $15.24 per pack of 100.
* FROM THE FASTENER TABLE (imported): thread, printed length, head, count,
  grip and the joint (``fasteners.BRACKET_TO_BAR``); the catalogue's thread and
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
y = -length.  Mate the Top Plane to the head's seat, the floor of TL-20's counterbore.
"""

from __future__ import annotations

import ch_rocker_arm_tl_oblique_fasteners_spec as fasteners
from _mcmaster_91251a196 import DIMS, LENGTH_TEXT, PART_NO, THREAD

SKU = PART_NO
ROW = fasteners.BRACKET_TO_BAR
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
