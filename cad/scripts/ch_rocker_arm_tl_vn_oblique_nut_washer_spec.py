r"""MHA-CH-06-TL-VN-72 oblique-trammel leadscrew nut screw washer: McMaster 90945A710.

PURE DATA, no SolidWorks/COM calls and no ``build_*`` module in its import
closure.  Shop fixture hardware (cad/docs/subsystem-identities.md), modelled
so the jig assembly can mate it and run native interference: the plain #4
flat washer under the head of each of the four ``#4-40 X 1/2 SHCS`` (TL-VN-66)
that hold the Tr8 flanged nut to the TL-29 nut bracket.  It spreads the
head's clamp on the nut's brass flange: the ring under a bare head (its
least diameter over the flange's Ø3.5 hole) is too small to carry the
preload that holds the nut from slipping (the jig spec's nut torque block).
It is the C4 fastener table's ``NUT_WASHER`` row and its own row on the jig's
BOM; the shop inventory carries no washer stock (no ``INVENTORY_ID``).

Sources:

* SOURCED, the No. 4 Mil. Spec. washer listing's 18-8 stainless steel row
  read live 2026-10-19 (``_mcmaster_90945a710``; the detail page is
  login-walled): NAS620C4L, ID 0.115 in, OD 0.209 in, thickness 0.015 to
  0.018 in, 500 per package, $21.94.  It is the smallest-OD steel No. 4
  washer McMaster lists.
* The model is the nominal annulus at the thickness band's maximum
  (``THICKNESS``), the worst case for the screw's engagement; the C4 fastener
  table's grip takes the same thickness (``leadscrew.NUT_WASHER_THICK``),
  pinned here.
* Catalogue-only: no vendor model was downloaded, so there is no replica
  gate; the recipe is ``diagnostics/diag_build_90945A710.py``.

Fit (checked at import): the ID passes the #4 major, the screw head's least
diameter bears on the washer, and the washer clears the nut's Ø10.2 body:
nominally by BODY_GAP (0.25), and by BODY_GAP_MIN (0.02) with the screw at
the nut bracket's ``POSITION_RADIUS`` from its nominal and the washer floated
on it toward the body (the nut centred). The nut floats on its spigot
(``SPIGOT_FLOAT``) and the screws in its holes (``NUT_SCREW_FLOAT``), so no
registration sets it: with the nut within NUT_CENTRING_ROOM (0.10) of the
seat's axis each washer has a flat seat on the flange, beside the body on
its screw's float where it would otherwise touch. Further off-centre a
washer will not go on beside the body. Nothing centres the nut by itself; it
is loose until a screw snugs, and step 7A fits all four screws on their
washers before snugging, so it lies where all four seat: never an empty
set, the centred nut being in it. The nut's own hole pattern and body are
taken at nominal: the vendor gives them no band (UNVERIFIED).

Part frame: axis local +Y through the origin, published as ``ScrewAxis``
(Front ∩ Right); the bottom face (on the nut's flange) at y = 0 (the Top
Plane), the top face (under the screw head) at y = THICKNESS.
"""

from __future__ import annotations

import math

import ch_rocker_arm_tl_oblique_fasteners_spec as fasteners
import ch_rocker_arm_tl_vn_oblique_leadscrew_nut_spec as leadscrew_nut
import ch_rocker_arm_tl_vn_oblique_leadscrew_spec as leadscrew
import ch_rocker_arm_tl_oblique_nut_bracket_spec as nut_bracket
import ch_rocker_arm_tl_vn_oblique_nut_screw_spec as nut_screw
from _mcmaster_90945a710 import (
    CATALOG_CHECKED_DATE as CATALOG_CHECKED_DATE,
    CATALOG_MATERIAL as CATALOG_MATERIAL,
    CATALOG_URL as CATALOG_URL,
    ID,
    MIL_SPEC as MIL_SPEC,
    OD,
    PACKAGE_QTY,
    PART_NO,
    SCREW_SIZE,
    THICKNESS_MAX,
    THICKNESS_MIN as THICKNESS_MIN,
)

SKU = PART_NO
ROW = fasteners.NUT_WASHER
SCREW_ROW = fasteners.NUT_TO_NUT_BRACKET
QUANTITY = ROW.count  # one under each nut screw head
PACK_QUANTITY = PACKAGE_QTY
THICKNESS = THICKNESS_MAX  # 0.457
BOTTOM_Y = 0.0
TOP_Y = THICKNESS

# --- Fit on the nut's flange ----------------------------------------------------
_MAJOR = SCREW_ROW.major_mm
_WASHER_FLOAT = (ID - _MAJOR) / 2.0  # the washer on its screw: 0.038
BODY_GAP = (
    leadscrew_nut.HOLE_PCD / 2.0 - OD / 2.0 - leadscrew_nut.BODY_DIA / 2.0
)  # 0.246
BODY_GAP_MIN = BODY_GAP - nut_bracket.POSITION_RADIUS - _WASHER_FLOAT  # 0.024
NUT_CENTRING_ROOM = BODY_GAP + _WASHER_FLOAT - nut_bracket.POSITION_RADIUS  # 0.10

if (SCREW_SIZE, ROW.joint) != (ROW.size, SCREW_ROW.joint):
    raise AssertionError(f"{SKU} is not the washer of {SCREW_ROW.joint}")
if QUANTITY != SCREW_ROW.count:
    raise AssertionError(f"{SKU}: one washer under each of {SCREW_ROW.count} heads")
if abs(THICKNESS - leadscrew.NUT_WASHER_THICK) > 1e-9:
    raise AssertionError(f"{SKU}: the grip's washer is not this washer")
if abs(THICKNESS - ROW.thickness_mm) > 1e-9:
    raise AssertionError(f"{SKU}: the fastener table's row is not the washer's")
if ID <= _MAJOR:
    raise AssertionError(f"{SKU}: ID {ID} does not pass the #4 major")
if not ID < nut_screw.HEAD_DIA_MIN < OD:
    raise AssertionError(f"{SKU}: the #4 head does not bear on the washer")
if not ID < leadscrew_nut.HOLE_DIA:
    raise AssertionError(f"{SKU}: the washer does not bridge the flange's hole")
if BODY_GAP_MIN <= 0.0 or NUT_CENTRING_ROOM <= 0.0:
    raise AssertionError(f"{SKU}: the washer reaches the nut's body")


def washer_volume() -> float:
    """Nominal annulus volume of the modelled washer, mm^3."""
    return math.pi / 4 * (OD**2 - ID**2) * THICKNESS
