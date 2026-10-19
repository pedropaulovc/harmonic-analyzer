r"""MHA-CH-06-TL-VN-70 oblique-trammel block screw lock washer: McMaster 91812A215.

PURE DATA, no SolidWorks/COM calls and no ``build_*`` module in its import
closure.  Shop fixture hardware (cad/docs/subsystem-identities.md), modelled
so the jig assembly can mate it and run native interference: the wedge-lock
washer pair under the head of each of the two ``#8-32 X 1-7/8 SHCS`` (TL-VN-63)
that hold the TL-29 nut bracket to TL-22 pivot block 1.  Those screws carry
the leadscrew's reversing feed thrust, so rule 23 wants a mechanical lock
(cad/docs/drawing-guidelines.md).  It is the C4 fastener table's
``BLOCK_LOCK_WASHER`` row and its own row on the jig's BOM; the shop
inventory carries no washer stock (no ``INVENTORY_ID``).

Sources:

* SOURCED, https://www.mcmaster.com/91812A215/ read live 2026-10-17 from the
  No. 8 listing (the detail page is login-walled): two-piece wedge-lock
  washer, reusable up to 15 times, comparable to NORD-LOCK; 316 stainless
  steel, Rockwell C51, case hardened; for No. 8 / M4; ID 0.170 in, OD
  0.300 in, thickness 0.080 to 0.100 in; 5 per package, $11.71.
* UNVERIFIED: the listing does not say whether the thickness is the pair's
  stack or one washer's, nor whether a package is 5 pairs.  The model takes
  it as the pair's stack at its 0.100 in maximum (``_mcmaster_91812a215``),
  the worst case for the screw's engagement and its head's stand-out; the
  C4 calculator carries the same stack as a literal
  (``leadscrew.BLOCK_SCREW_LOCK_STACK``), pinned here.  Verify on receipt.
* Catalogue-only: no vendor model was downloaded, so there is no replica
  gate.  The geometry is the plain annulus of the pair's envelope (the cam
  faces, serrations and the split between the halves are not modelled); the
  recipe is ``diagnostics/diag_build_91812A215.py``.

Fit (checked at import): the OD clears the smallest Ø7.94 counterbore, the
ID clears the #8 major, and the pair bears on the ring outside the largest
drilled hole.  Engagement in TL-29 (AGENTS.md: worst case, not nominal):
ENGAGEMENT (9.49) is 1-7/8 in less 35.6 of TL-22 and the modelled pair;
ENGAGEMENT_MIN (7.83) is the shortest screw (ASME B18.3, -0.04 in) through
the widest block, the shallowest counterbore and the thickest pair, at least
1.5 D; ENGAGEMENT_MAX (10.63) is the nominal screw (never long) through the
narrowest block, the deepest counterbore and the thinnest pair, inside
TL-29's 12 full thread (the screw never bottoms) and inside the screw's
7/8 in thread (it clamps, never jams on the plain shank).
The head stands HEAD_PROUD (2.31) proud of TL-22's +Y face.

Part frame: axis local +Y through the origin, published as ``ScrewAxis``
(Front ∩ Right); the bottom face (on the counterbore floor) at y = 0 (the
Top Plane), the top face (under the screw head) at y = THICKNESS.
"""

from __future__ import annotations

import math

import ch_rocker_arm_tl_vn_oblique_block_screw_spec as block_screw
import ch_rocker_arm_tl_oblique_fasteners_spec as fasteners
import ch_rocker_arm_tl_vn_oblique_leadscrew_spec as leadscrew
import ch_rocker_arm_tl_oblique_nut_bracket_spec as nut_bracket
import ch_rocker_arm_tl_oblique_pivot_block_spec as pivot_block
from _mcmaster_91812a215 import (
    CATALOG_CHECKED_DATE as CATALOG_CHECKED_DATE,
    CATALOG_MATERIAL as CATALOG_MATERIAL,
    CATALOG_URL as CATALOG_URL,
    ID,
    OD,
    PACKAGE_QTY,
    PAIR_THICKNESS,
    PART_NO,
    SCREW_SIZE,
    THICKNESS_MAX as THICKNESS_MAX,
    THICKNESS_MIN as THICKNESS_MIN,
)
from _printed_tolerance import printed_band_mm

SKU = PART_NO
ROW = fasteners.BLOCK_LOCK_WASHER
SCREW_ROW = fasteners.NUT_BRACKET_TO_BLOCK
QUANTITY = ROW.count  # pairs, one under each block screw head
PACK_QUANTITY = PACKAGE_QTY  # UNVERIFIED: pairs or single washers
THICKNESS = PAIR_THICKNESS  # the modelled pair's stack, 2.54
BOTTOM_Y = 0.0
TOP_Y = THICKNESS

_CBORE_BAND = printed_band_mm(pivot_block.SIDE_CBORE_PLACES)
# Diametral clearance in the smallest counterbore: 7.81 - 7.62.
CBORE_CLEARANCE = pivot_block.SIDE_CBORE_DIA - _CBORE_BAND - OD
# The pair bears on the counterbore floor outside the largest drilled hole.
FLOOR_BEARING = (OD - pivot_block.SIDE_HOLE_DIA - pivot_block.DRILLED_BAND[0]) / 2.0
_WIDTH_BAND = printed_band_mm(pivot_block.DRAWING_PRECISION_BY_NAME["BlockWidth"])
ENGAGEMENT = SCREW_ROW.engagement_mm  # nominal, 9.49 in TL-29
# TL-22 under the pair, at its bands: 35.6 +/- (0.51 + 0.13).
_UNDER_PAIR_MAX = (
    pivot_block.BLOCK_WIDTH + _WIDTH_BAND - pivot_block.SIDE_CBORE_DEPTH + _CBORE_BAND
)
_UNDER_PAIR_MIN = (
    pivot_block.BLOCK_WIDTH - _WIDTH_BAND - pivot_block.SIDE_CBORE_DEPTH - _CBORE_BAND
)
ENGAGEMENT_MIN = block_screw.LENGTH_MIN - (_UNDER_PAIR_MAX + THICKNESS_MAX)  # 7.83
ENGAGEMENT_MAX = block_screw.DIMS.length - (_UNDER_PAIR_MIN + THICKNESS_MIN)  # 10.63
HEAD_PROUD = block_screw.DIMS.head_h + THICKNESS - pivot_block.SIDE_CBORE_DEPTH

if (SCREW_SIZE, ROW.joint) != (ROW.size, SCREW_ROW.joint):
    raise AssertionError(f"{SKU} is not the washer of {SCREW_ROW.joint}")
if QUANTITY != SCREW_ROW.count:
    raise AssertionError(f"{SKU}: one pair under each of {SCREW_ROW.count} heads")
if abs(THICKNESS - leadscrew.BLOCK_SCREW_LOCK_STACK) > 1e-9:
    raise AssertionError(f"{SKU}: the leadscrew spec's lock stack is not the pair's")
if abs(THICKNESS - ROW.thickness_mm) > 1e-9:
    raise AssertionError(f"{SKU}: the fastener table's stack is not the pair's")
if CBORE_CLEARANCE < 0.19 - 1e-9:
    raise AssertionError(f"{SKU}: OD {OD} does not clear TL-22's counterbore")
if ID <= SCREW_ROW.major_mm:
    raise AssertionError(f"{SKU}: ID {ID} does not pass the #8 major")
if FLOOR_BEARING < 0.5:
    raise AssertionError(f"{SKU}: the pair bears on too thin a counterbore ring")
if block_screw.DIMS.head_dia > OD or block_screw.DIMS.head_dia <= ID:
    raise AssertionError(f"{SKU}: the #8 head does not bear on the pair")
if ENGAGEMENT_MIN < 1.5 * SCREW_ROW.major_mm:
    raise AssertionError(f"{SKU}: the block screw engages under 1.5 D (rule 18)")
if ENGAGEMENT_MAX > nut_bracket.BLOCK_TAP_THREAD_DEPTH:
    raise AssertionError(f"{SKU}: the block screw bottoms in TL-29's thread")
if block_screw.DIMS.threaded_length <= ENGAGEMENT_MAX:
    raise AssertionError(f"{SKU}: the block screw's plain shank reaches TL-29")


def washer_volume() -> float:
    """Nominal annulus volume of the modelled pair, mm^3."""
    return math.pi / 4 * (OD**2 - ID**2) * THICKNESS
