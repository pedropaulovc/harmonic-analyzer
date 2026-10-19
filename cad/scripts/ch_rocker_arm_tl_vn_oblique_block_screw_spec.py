r"""MHA-CH-06-TL-VN-63 oblique-trammel nut bracket screw: McMaster 91251A188.

PURE DATA, no SolidWorks/COM calls and no ``build_*`` module in its import
closure.  Shop fixture hardware (cad/docs/subsystem-identities.md), modelled
so the jig assembly can mate it and run native interference: the
``#8-32 X 1-7/8 SHCS`` that holds the TL-29 nut bracket to TL-22 pivot block 1, into a blind tap; the head seats on a TL-VN-70 wedge-lock pair on the floor of TL-22's counterbore.
It is the C4 fastener table's ``NUT_BRACKET_TO_BLOCK`` row.  It is its own row on the
jig's BOM; the shop inventory carries no screw stock (no ``INVENTORY_ID``),
and the assembly steps cite it by item and callout (``fasteners.callout``).

Sources:

* SOURCED, https://www.mcmaster.com/91251A188/ read live 2026-10-17 from
  the #8-32 black-oxide listing: #8-32 coarse, 1-7/8 in under the head,
  partly threaded (7/8 in thread), head Ø0.27 x 0.164 in, 9/64 in hex drive,
  170,000 psi, US origin, $11.00 per pack of 10.  It replaced the 1-3/4 in
  91251A screw (Codex review: with the TL-VN-70 pair under the head, the 1-3/4 in
  screw engaged 5.67 in TL-29 at the worst case, under 1.5 D).
* FROM THE FASTENER TABLE (imported): thread, printed length, head, count,
  grip and the joint (``fasteners.NUT_BRACKET_TO_BLOCK``); the catalogue's thread and
  length must equal the row's (checked at import).
* STANDARD: the page gives no socket depth, so it is the standard's
  minimum key engagement (``_mcmaster_91251a188``; the 91251A108 convention);
  the length tolerance is ASME B18.3's -0.04 in (``LENGTH_MIN``), which the
  TL-VN-70 spec's worst-case engagement reads.
* The geometry is the 91251A family's catalogue recipe
  (``diag_mcmaster_socket_head.build_socket_head``: plain cylindrical head,
  0.75P tip chamfer, 45 deg thread neck).  No vendor model was downloaded
  (login-walled), so it is NOT replica-gated.  The recipe is
  ``diagnostics/diag_build_91251A188.py``; its standalone run is catalog-only.

Part frame: screw axis local +Y through the origin, published as
``ScrewAxis`` (Front ∩ Right); the bearing face (head underside) at y = 0 (the Top Plane), the tip at
y = -length.  Mate the Top Plane to the head's seat, the top of the TL-VN-70 pair.
"""

from __future__ import annotations

import ch_rocker_arm_tl_oblique_fasteners_spec as fasteners
from _mcmaster_91251a188 import (
    DIMS,
    LENGTH_MIN as LENGTH_MIN,
    LENGTH_TEXT,
    PACK_QUANTITY as PACK_QUANTITY,
    PART_NO,
    THREAD,
)

SKU = PART_NO
ROW = fasteners.NUT_BRACKET_TO_BLOCK
QUANTITY = ROW.count
CALLOUT = fasteners.callout(ROW)  # "#8-32 X 1-7/8 SHCS"

if (THREAD, LENGTH_TEXT, fasteners.SHCS) != (ROW.thread, ROW.length, ROW.head):
    raise AssertionError(f"{SKU} is not the screw of {ROW.joint}")
if abs(DIMS.length - ROW.length_mm) > 1e-9:
    raise AssertionError(f"{SKU}: {DIMS.length} long, the row prints {ROW.length_mm}")
if abs(DIMS.major_dia - ROW.major_mm) > 1e-3:
    raise AssertionError(
        f"{SKU}: major {DIMS.major_dia}, the row's thread is {ROW.major_mm}"
    )
# Partly threaded: the receiving tap must engage thread, not the plain
# shank, so the engagement (length - grip) stays inside the thread.
if DIMS.threaded_length < ROW.engagement_mm:
    raise AssertionError(f"{SKU}: the engagement reaches the plain shank")
