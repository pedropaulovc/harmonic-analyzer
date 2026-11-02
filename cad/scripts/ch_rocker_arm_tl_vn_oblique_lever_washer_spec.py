r"""MHA-CH-06-TL-VN-71 oblique-trammel feed lever screw lock washer: McMaster 91812A230.

PURE DATA, no SolidWorks/COM calls and no ``build_*`` module in its import
closure.  Shop fixture hardware (cad/docs/subsystem-identities.md), modelled
so the jig assembly can mate it and run native interference: the wedge-lock
washer pair under the head of each of the two ``5/16-18 X 1 SHCS`` (TL-VN-69)
that hold the TL-26 feed lever to the TL-21 carrier.  The operator pushes
and pulls the lever both ways through every pass, so those screws carry a
reversing load and rule 23 wants a mechanical lock
(cad/docs/drawing-guidelines.md).  It is the C4 fastener table's
``LEVER_LOCK_WASHER`` row and its own row on the jig's BOM; the shop
inventory carries no washer stock (no ``INVENTORY_ID``).

Sources:

* SOURCED, https://www.mcmaster.com/products/washers/washer-type~wedge/ read
  live 2026-10-17 and 2026-11-01 (the detail page is login-walled): two-piece
  wedge-lock washer, reusable up to 15 times, comparable to NORD-LOCK; 316
  stainless steel, Rockwell C51, case hardened; for 5/16" / M8; ID 0.340 in,
  OD 0.530 in, thickness 0.070 to 0.090 in; package quantity 5.
* EXACT-CURRENT PRIMARY, https://www.mcmaster.com/91812A230/ read 2026-10-21:
  the product table repeats those dimensions. Its engineering drawing
  (``SUPPLIER_DRAWING_URL``) spans the depicted two-piece stack, not an
  individual half. References below describe only the unchanged plain
  envelope; they do not assert that the model contains a physical pair.
* PAIR AND PACKAGE (2026-11-01, ``_mcmaster_91812a230``): one catalogue item
  is the two-piece washer, so a package of 5 is five pairs, and the drawing's
  thickness is the pair's stack.  The model keeps the stack at its 0.090 in
  maximum, the worst case for the screw's engagement and its head's height;
  the C4 fastener table carries the same stack as a literal
  (``fasteners.LEVER_LOCK_STACK``), pinned here.
* Catalogue-only: no vendor model was downloaded, so there is no replica
  gate.  The geometry is the plain annulus of the pair's envelope (the cam
  faces, serrations and the split between the halves are not modelled); the
  recipe is ``diagnostics/diag_build_91812A230.py``.

The pair's stack took the screw from 7/8 in to the next stock length, 1 in
(TL-VN-69, 91251A583); the TL-21 taps stay THRU.  Engagement in TL-21
(AGENTS.md: worst case, not nominal): ENGAGEMENT is 1 in less the lever and
the modelled pair, above the 7/8 in screw's without the pair; ENGAGEMENT_MIN
is the shorter of the shortest screw (ASME B18.3, -0.03 in) through the
thickest lever and the thickest pair, and the carrier's worst-case full
thread (``carrier.ENGAGEMENT_MM``, the RV-01 shortfall), above the 7/8 in
screw's at the same corners.  STAND_OUT_MAX is how far the longest screw
(nominal, never long) through the thinnest lever and the thinnest pair
reaches past the thinnest plate's underside (negative: the tip stays inside
the plate).  It must stay inside the gap from the carrier's underside to the
pivot blocks' tops (``trammel.PIVOT_SUPPORT_HEIGHT``), the highest parts that
pass beneath it.

Fit (checked at import): the ID passes the 5/16 major, the screw head bears
on the pair, and the two pairs clear each other at the worst carrier tap
pitch with each pair floated on its screw (PAIR_GAP_MIN).  The inner pair
sits just inside the lever's inner end nominally; at the worst corner (the
.XX hole station, the screw floated in the drilled clearance hole and the
pair on the screw) it overhangs the end by INNER_END_OVERHANG_MAX and keeps
BEARING_FRACTION_MIN (at least 90%) of its bearing ring on the lever.

Part frame: axis local +Y through the origin, published as ``ScrewAxis``
(Front ∩ Right); the bottom face (on the lever's top face) at y = 0 (the
Top Plane), the top face (under the screw head) at y = THICKNESS.
"""

from __future__ import annotations

import math

import _config
import ch_rocker_arm_tl_oblique_carrier_spec as carrier
import ch_rocker_arm_tl_oblique_fasteners_spec as fasteners
import ch_rocker_arm_tl_oblique_feed_lever_spec as feed_lever
import ch_rocker_arm_tl_vn_oblique_lever_screw_spec as lever_screw
import ch_rocker_arm_tl_oblique_trammel_spec as trammel
from _mcmaster_91812a230 import (
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
from _package_units import drawing_unit
from _printed_tolerance import printed_band_mm

SKU = PART_NO
ROW = fasteners.LEVER_LOCK_WASHER
SCREW_ROW = fasteners.LEVER_TO_CARRIER
QUANTITY = ROW.count  # pairs, one under each lever screw head
PACK_QUANTITY = PACKAGE_QTY  # pairs per package
UNIT = drawing_unit(
    "parts/ch-rocker-arm-tl-vn-oblique-lever-washer",
    _config.parts("ch-rocker-arm-tl-vn-oblique-lever-washer"),
)
THICKNESS = PAIR_THICKNESS  # the modelled pair's stack, .090 in
BOTTOM_Y = 0.0
TOP_Y = THICKNESS

# Exact-current engineering image inspected 2026-10-21. Use its two-place
# inch precision (.34 ID, .53 OD, .07-.09 stack), not the product table's
# three-place typography (.340, .530, .070-.090); the values agree exactly.
# No diameter band is supplied. Keep the maximum-stack envelope; neither the
# pair split nor its locking faces are added.
SUPPLIER_DRAWING_URL = (
    "https://www.mcmaster.com/mvC/Library/CAD2/20260617/385104C2/"
    "91812A230_Extreme-Vibration-Resistant%20Wedge%20Lock%20WasherX.GIF"
)
SUPPLIER_UNITS = "in"
DRAWING_REFERENCE_PRECISION = {
    "supplier outer diameter": 2,
    "supplier bore diameter": 2,
    "supplier thickness": 2,
}
SUPPLIER_TOLERANCES = {
    "supplier thickness": (THICKNESS_MIN, THICKNESS_MAX, "limits"),
}
SUPPLIER_BORE_CALLOUT = "FOR 5/16 SCREW SIZE"
SUPPLIER_DATA = (
    "SOLD AS TWO-PIECE WEDGE-LOCK PAIRS, 5 PAIRS PER PACKAGE.",
    "REFERENCE THICKNESS IS THE TWO-PIECE PAIR STACK.",
)
REFERENCE_SKETCHES = ("SupplierWasherThicknessReference",)
DRAWING_PRECISION = {
    "SupplierWasherThicknessReference": {
        "SupplierThickness": DRAWING_REFERENCE_PRECISION["supplier thickness"],
    },
}

# --- Engagement and stand-out in TL-21, worst case ------------------------------
_THICK_BAND = printed_band_mm(feed_lever.THICK_PLACES, unit=feed_lever.UNIT)
ENGAGEMENT = SCREW_ROW.engagement_mm  # nominal
ENGAGEMENT_MIN = min(
    lever_screw.LENGTH_MIN - (feed_lever.LEVER_THICK + _THICK_BAND + THICKNESS_MAX),
    carrier.ENGAGEMENT_MM[carrier.LEVER_THREAD],
)
STAND_OUT_MAX = (
    lever_screw.DIMS.length
    - (feed_lever.LEVER_THICK - _THICK_BAND + THICKNESS_MIN)
    - (carrier.THICKNESS - carrier.THICKNESS_BAND)
)

# --- Fit on the lever -----------------------------------------------------------
_MAJOR = SCREW_ROW.major_mm
_WASHER_FLOAT = (ID - _MAJOR) / 2.0  # the pair on its screw
_SCREW_FLOAT = (feed_lever.HOLE_DIA + feed_lever.DRILLED_BAND[0] - _MAJOR) / 2.0
_STATION_BAND = printed_band_mm(
    carrier.DRAWING_PRECISION_BY_NAME["LeverY1"], unit=carrier.UNIT
)
_TAP_PITCH = abs(carrier.LEVER_HOLES[1][1] - carrier.LEVER_HOLES[0][1])
PAIR_GAP_MIN = _TAP_PITCH - 2.0 * _STATION_BAND - 2.0 * _WASHER_FLOAT - OD
_HOLE_X_BAND = printed_band_mm(feed_lever.HOLE_X_PLACES, unit=feed_lever.UNIT)
_INNER_EDGE_MIN = feed_lever.HOLE_X[0] - _HOLE_X_BAND - _SCREW_FLOAT - _WASHER_FLOAT
INNER_END_OVERHANG_MAX = OD / 2.0 - _INNER_EDGE_MIN
# The lever face under the pair: the ring outside the largest drilled hole,
# less the circular segment that overhangs the inner end at the worst corner.
_R = OD / 2.0
BEARING_AREA = (
    math.pi / 4.0 * (OD**2 - (feed_lever.HOLE_DIA + feed_lever.DRILLED_BAND[0]) ** 2)
)
_SEGMENT = _R**2 * math.acos(_INNER_EDGE_MIN / _R) - _INNER_EDGE_MIN * math.sqrt(
    _R**2 - _INNER_EDGE_MIN**2
)
BEARING_AREA_MIN = BEARING_AREA - _SEGMENT
BEARING_FRACTION_MIN = BEARING_AREA_MIN / BEARING_AREA

if (SCREW_SIZE, ROW.joint) != (ROW.size, SCREW_ROW.joint):
    raise AssertionError(f"{SKU} is not the washer of {SCREW_ROW.joint}")
if QUANTITY != SCREW_ROW.count:
    raise AssertionError(f"{SKU}: one pair under each of {SCREW_ROW.count} heads")
if abs(THICKNESS - fasteners.LEVER_LOCK_STACK) > 1e-9:
    raise AssertionError(f"{SKU}: the fastener table's stack is not the pair's")
if abs(THICKNESS - ROW.thickness_mm) > 1e-9:
    raise AssertionError(f"{SKU}: the fastener table's row is not the pair's")
if ID <= _MAJOR:
    raise AssertionError(f"{SKU}: ID {ID} does not pass the 5/16 major")
if lever_screw.DIMS.head_dia > OD or lever_screw.DIMS.head_dia <= ID:
    raise AssertionError(f"{SKU}: the 5/16 head does not bear on the pair")
if PAIR_GAP_MIN <= 0.0:
    raise AssertionError(f"{SKU}: the two pairs touch at the worst tap pitch")
if BEARING_FRACTION_MIN < 0.90:
    raise AssertionError(f"{SKU}: the inner pair overhangs the lever's inner end")
if ENGAGEMENT < carrier.ENGAGEMENT_MM[carrier.LEVER_THREAD]:
    raise AssertionError(f"{SKU}: the lever screw stops short of TL-21's full thread")
if STAND_OUT_MAX >= trammel.PIVOT_SUPPORT_HEIGHT:
    raise AssertionError(f"{SKU}: the lever screw tip reaches the pivot blocks")


def washer_volume() -> float:
    """Nominal annulus volume of the modelled pair, in mm^3 (model units)."""
    return math.pi / 4 * (OD**2 - ID**2) * THICKNESS
