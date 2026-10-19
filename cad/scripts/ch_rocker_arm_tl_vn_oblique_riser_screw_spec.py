r"""MHA-CH-06-TL-VN-67 oblique-trammel riser screw: McMaster 91771A110.

PURE DATA, no SolidWorks/COM calls and no ``build_*`` module in its import
closure.  Shop fixture hardware (cad/docs/subsystem-identities.md), modelled
so the jig assembly can mate it and run native interference: the
``#4-40 X 1/2 FLAT HEAD`` that holds the TL-24 riser to the TL-21 carrier, tapped THRU; the head seats on the riser's 82 deg countersink, the head's flat top flush with the riser's top face.
It is the C4 fastener table's ``RISER_TO_CARRIER`` row.  It is its own row on the
jig's BOM; the shop inventory carries no screw stock (no ``INVENTORY_ID``),
and the assembly steps cite it by item and callout (``fasteners.callout``).

Sources:

* SOURCED, https://www.mcmaster.com/91771A110/ read live 2026-10-17:
  18-8 stainless steel, passivated, Phillips No. 1 drive, standard 82 deg flat head Ø0.212 x 0.067 in, #4-40 UNC class 2A, 1/2 in overall (McMaster measures a flat head from its top), fully threaded, flat tip, Rockwell B80, 80,000 psi, ASME B18.6.3, $6.63 per pack of 100.
* FROM THE FASTENER TABLE (imported): thread, printed length, head, count,
  grip and the joint (``fasteners.RISER_TO_CARRIER``); the catalogue's thread and
  length must equal the row's (checked at import).
* FROM THE CALCULATOR (imported): ``trammel.RISER_SCREW_HEAD_DIA``, the
  B18.6.3 #4 flat head's max sharp Ø0.225 in the riser's countersink is
  sized for; the catalogue head (Ø0.212 in) must not exceed it (checked
  at import).
* VENDOR MODEL, only where the catalogue is silent (Phillips recess form,
  tip chamfer): read off McMaster's STEP (``_mcmaster_91771a110``, which
  labels each such value; SLDPRT and STEP downloaded 2026-10-17, their
  SHA-256 there), for dimensions only: NOT replica-gated (user ruling
  2026-10-17).  The recipe is ``diagnostics/diag_build_91771A110.py``; its
  standalone run is catalog-only.

Part frame: screw axis local +Y through the origin, published as
``ScrewAxis`` (Front ∩ Right); the flat top (flush in the countersink) at y = 0 (the Top Plane), the tip
at y = -length (McMaster's flat head length is overall).  Mate the Top
Plane to the riser's top face (the head sits flush in its countersink).
"""

from __future__ import annotations

import ch_rocker_arm_tl_oblique_fasteners_spec as fasteners
import ch_rocker_arm_tl_oblique_trammel_spec as trammel
from _mcmaster_91771a110 import DIMS, LENGTH_TEXT, PART_NO, THREAD

SKU = PART_NO
ROW = fasteners.RISER_TO_CARRIER
QUANTITY = ROW.count
PACK_QUANTITY = 100  # McMaster sells 91771A110 in packs of 100
CALLOUT = fasteners.callout(ROW)  # "#4-40 X 1/2 FLAT HEAD"

if (THREAD, LENGTH_TEXT, fasteners.FLAT_HEAD) != (ROW.thread, ROW.length, ROW.head):
    raise AssertionError(f"{SKU} is not the screw of {ROW.joint}")
if abs(DIMS.length - ROW.length_mm) > 1e-9:
    raise AssertionError(f"{SKU}: {DIMS.length} long, the row prints {ROW.length_mm}")
if abs(DIMS.major_dia - ROW.major_mm) > 1e-3:
    raise AssertionError(
        f"{SKU}: major {DIMS.major_dia}, the row's thread is {ROW.major_mm}"
    )
# The head sinks into the countersunk part: its cone must end inside the
# grip, or the head would reach the receiving thread.
if DIMS.junction_depth >= ROW.grip_mm:
    raise AssertionError(f"{SKU}: the head is deeper than the countersunk part")
# The riser's countersink is sized for the calculator's B18.6.3 head (max
# sharp Ø); the catalogue head must not exceed it.
if DIMS.head_dia > trammel.RISER_SCREW_HEAD_DIA:
    raise AssertionError(
        f"{SKU}: head Ø{DIMS.head_dia} over the riser countersink's "
        f"Ø{trammel.RISER_SCREW_HEAD_DIA}"
    )
