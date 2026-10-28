r"""MHA-CH-06-TL-VN-53 oblique-trammel CL locator dowel: McMaster 91595A452.

PURE DATA, no SolidWorks/COM calls and no ``build_*`` module in its import
closure.  Shop fixture (cad/docs/subsystem-identities.md): one 6 x 20 m6
dowel, inventory ``fixtures.trammel-cl-dowel``, bought as a pack of 25.  Once
the carrier's CL spot is finished in place to Ø6 N7 on the running jig
(``carrier.CL_HOLE_BAND``), press chamfered end first with the actual riser
installed. Set its round tip ``TIP_SET_MIN``–``TIP_SET_MAX`` above the actual
riser top. Check that the strap seats flat, locates and slips on/off without
the pin standing above it; do not set the pin flush underneath the carrier.

Sources:

* SOURCED, https://www.mcmaster.com/91595A452/ read live 2026-10-17
  (inventory note): 52100 alloy steel, Ø6 +0.004/+0.012 (DIN 6325-m6 /
  ISO 8734), 20 long (length tolerance not stated), Rockwell C52 min, end
  shape "Round x Chamfer/Round".
* FROM THE CARRIER SPEC (imported): ``CL_DOWEL_DIA`` (6), ``CL_DOWEL_BAND``
  (m6), ``CL_HOLE_BAND`` (N7), ``CL_DOWEL_INTERFERENCE`` (0.008-0.028
  diametral); finished plate thicknesses come from ``carrier`` and ``riser``,
  and the strap thickness band comes from ``rocker``.
* VENDOR MODEL: the end forms (15 deg x 1.17 chamfer with an R5.016 crown,
  R5.45 dome) are read off McMaster's STEP (``_mcmaster_91595a452``); the
  recipe is ``diagnostics/diag_build_91595A452.py``.  The vendor SLDPRT/STEP
  (downloaded 2026-10-17) is read for dimensions only and NOT replica-gated
  (user ruling 2026-10-17); the recipe's standalone run is catalog-only.

Model diameter: nominal Ø6.000, the vendor's.  The carrier models CL as its
Ø3 x 90 deg centre-drill spot only (finished in place, like HUB), so the
assembly's press-fit allowance for this pair is the dowel's own volume in the
plate, as ``_interference_contracts.JIG_HUB_PIN_SEAT`` bounds the HUB pin:
``PRESS_ALLOWANCE_MM3`` below (1.10 x a Ø6 x 12 carrier cylinder), which the
modelled overlap (only pin metal inside the carrier, less its centre spot)
stays under. The small lower crown outside the carrier is excluded.

Part frame: pin axis local +Y through the origin, published as ``ScrewAxis``
(Front ∩ Right); the chamfered end's tip at y = 0 (the Top Plane), the round
end's tip at y = LENGTH. Mate the Top Plane at ``TIP_BASE_Z``, not flush.
"""

from __future__ import annotations

import math

import ch_rocker_arm_spec as rocker
import ch_rocker_arm_tl_oblique_carrier_spec as carrier
import ch_rocker_arm_tl_oblique_pivot_block_spec as pivot_block
import ch_rocker_arm_tl_oblique_riser_spec as riser
import ch_rocker_arm_tl_oblique_trammel_spec as trammel
from _mcmaster_91595a452 import (
    CHAMFER_LEN,
    CROWN_H,
    DIA,
    DOME_H,
    LENGTH,
    chamfer_rim_radius,
    crown_radius,
)

SKU = "91595A452"
INVENTORY_ID = "fixtures.trammel-cl-dowel"
QUANTITY = 1
PACK_QUANTITY = 25  # McMaster sells 91595A452 in packs of 25

DIA_BAND = carrier.CL_DOWEL_BAND  # m6, (upper, lower)
HOLE_BAND = carrier.CL_HOLE_BAND  # N7
INTERFERENCE = carrier.CL_DOWEL_INTERFERENCE  # diametral (min, max)
DIA_MAX = DIA + max(DIA_BAND)  # 6.012
DIA_MIN = DIA + min(DIA_BAND)  # 6.004

# Exact-current product table and engineering image inspected 2026-10-21.
# The print shows 6.000 mm +0.012/+0.004 and 20 mm tip-to-tip; it supplies
# no length tolerance. These are nominal purchasing references, independent
# of the unchanged installation/press controls below and model end forms.
# In particular, DIA_BAND above is (upper, lower); the source native
# tolerance tuple below is deliberately (lower, upper), both positive.
SUPPLIER_DRAWING_URL = (
    "https://www.mcmaster.com/mvC/Library/CAD2/20260107/03FA1557/"
    "91595A452_Dowel%20PinX.GIF"
)
SUPPLIER_REFERENCE_DIMENSIONS = (
    ("SupplierDowelDiameter", DIA, "horizontal"),
    ("SupplierDowelLength", LENGTH, "vertical"),
)
SUPPLIER_REFERENCE_STARTS = {
    "SupplierDowelDiameter": (-DIA / 2.0, 0.0),
    "SupplierDowelLength": (0.0, 0.0),
}
SUPPLIER_REFERENCE_PLANES = {
    "SupplierDowelDiameter": "Top",
    "SupplierDowelLength": "Front",
}
SUPPLIER_REFERENCE_SIDES = {
    "SupplierDowelDiameter": "bottom",
    "SupplierDowelLength": "left",
}
SUPPLIER_REFERENCE_FORMATS = {
    "SupplierDowelDiameter": (3, "diameter", None, "NOMINAL PIN DIAMETER"),
    "SupplierDowelLength": (0, "length", None, "NOMINAL TIP-TO-TIP"),
}
SUPPLIER_REFERENCE_UNITS = {
    "SupplierDowelDiameter": "mm",
    "SupplierDowelLength": "mm",
}
SUPPLIER_REFERENCE_TOLERANCES_MM = {
    "SupplierDowelDiameter": (0.004, 0.012),
}
SUPPLIER_DATA = (
    "NOMINAL SUPPLIER REFERENCES; ROUND / CHAMFER-ROUND ENDS.",
    "LENGTH IS TIP-TO-TIP; SUPPLIER LENGTH TOLERANCE NOT STATED.",
)
# The lead-in that grips nothing: the crown and the chamfer.
LEAD_IN = CROWN_H + CHAMFER_LEN  # 1.95

# Owner-approved assembly fit-up (#1619): use the existing purchased pin,
# not a new shop-made locator. These are functional set-height limits, not
# tighter manufacturing bands on either plate. Native reference geometry
# shows the midpoint; the actual riser is the installation datum.
TIP_SET_MIN = 1.50
TIP_SET_MAX = 1.70
TIP_HEIGHT = (TIP_SET_MIN + TIP_SET_MAX) / 2.0
PROUD = riser.THICKNESS + TIP_HEIGHT
PRESS_DEPTH = LENGTH - PROUD
TIP_BASE_Z = trammel.CARRIER_TOP_Z - PRESS_DEPTH
PRESS_ENGAGEMENT_MIN_D = 1.5


PRESS_ENGAGEMENT_D = (
    min(
        carrier.THICKNESS - carrier.TAP_MOUTH_BREAK,
        LENGTH - riser.THICKNESS - TIP_HEIGHT - LEAD_IN - carrier.TAP_MOUTH_BREAK,
    )
    / DIA_MAX
)
# Catalogue nominal pin/end forms across both finished-plate bands. This is
# design accounting, not a new receipt-inspection protocol or supplier
# length tolerance. Normal assembly verifies the set height and strap fit.
PRESS_ENGAGEMENT_MIN = min(
    carrier.THICKNESS - carrier.THICKNESS_BAND - carrier.TAP_MOUTH_BREAK,
    LENGTH
    - (riser.THICKNESS + riser.THICKNESS_BAND)
    - TIP_SET_MAX
    - LEAD_IN
    - carrier.TAP_MOUTH_BREAK,
)
CYLINDER_ENGAGEMENT_MIN = TIP_SET_MIN - DOME_H
STRAP_TOP_CLEARANCE_MIN = (
    rocker.ARM_THICKNESS + rocker.ARM_THICKNESS_BAND[1] - TIP_SET_MAX
)
# Lower-end projection at the catalogue pin length and finished-plate limits.
# The pivot-block top plane is a conservative ceiling for the feed hardware
# and the allowed studs below the carrier. Pin collars reach higher, so also
# exclude the entire pin/block envelope in plan at either pair of pin holes.
BOTTOM_PROJECTION_MAX = max(
    0.0,
    LENGTH
    - (carrier.THICKNESS - carrier.THICKNESS_BAND)
    - (riser.THICKNESS - riser.THICKNESS_BAND)
    - TIP_SET_MIN,
)
_PIVOT_BLOCK_PLAN_RADIUS = math.hypot(
    max(
        abs(pivot_block.BLOCK_X0 - pivot_block.BORE_X),
        abs(pivot_block.BLOCK_X1 - pivot_block.BORE_X),
    ),
    pivot_block.BLOCK_WIDTH / 2.0,
)
_PIN_PLAN_CLEARANCE = (
    min(math.dist(trammel.CL, point) for point in trammel.PIN_HOLES.values())
    - _PIVOT_BLOCK_PLAN_RADIUS
    - DIA_MAX / 2.0
)
if BOTTOM_PROJECTION_MAX >= trammel.PIVOT_SUPPORT_HEIGHT:
    raise AssertionError("the CL lower end reaches the below-carrier top envelope")
if _PIN_PLAN_CLEARANCE <= 0.0:
    raise AssertionError("the CL lower end can meet a pivot pin or block in plan")
if PRESS_ENGAGEMENT_MIN < PRESS_ENGAGEMENT_MIN_D * DIA_MAX:
    raise AssertionError("the CL fit-up leaves under 1.5D full-diameter press")
if CYLINDER_ENGAGEMENT_MIN <= 0.0 or STRAP_TOP_CLEARANCE_MIN <= 0.0:
    raise AssertionError("the CL fit-up misses the strap cylinder or stands proud")
if riser.CLAMP_DIA <= DIA_MAX:
    raise AssertionError("the riser's clamp hole does not clear the CL dowel")


def _press_overlap_mm3() -> float:
    """Only the nominal installed pin metal inside the carrier.

    The lower crown projects slightly beneath the carrier; subtract that
    spherical cap, as well as the carrier's native centre-drill spot.
    """
    radius, rim = DIA / 2.0, chamfer_rim_radius()
    crown = math.pi * CROWN_H**2 * (3.0 * crown_radius() - CROWN_H) / 3.0
    chamfer = math.pi / 3.0 * CHAMFER_LEN * (radius**2 + radius * rim + rim**2)
    outside = max(0.0, PRESS_DEPTH - carrier.THICKNESS)
    if outside > CROWN_H:
        raise AssertionError("the CL overlap integral must also trim its chamfer")
    outside_cap = math.pi * outside**2 * (3.0 * crown_radius() - outside) / 3.0
    cylinder = math.pi * radius**2 * (PRESS_DEPTH - LEAD_IN)
    spot_r = carrier.SPOT_DIA / 2.0
    spot_depth = spot_r * math.tan(math.radians(carrier.SPOT_FLANK_ANGLE))
    spot = math.pi * spot_r**2 * spot_depth / 3.0
    return crown + chamfer + cylinder - outside_cap - spot


PRESS_OVERLAP_MM3 = _press_overlap_mm3()
PRESS_ALLOWANCE_MM3 = 1.10 * math.pi * DIA**2 * carrier.THICKNESS / 4.0
if PRESS_OVERLAP_MM3 >= PRESS_ALLOWANCE_MM3:
    raise AssertionError("the CL dowel's modelled press exceeds its allowance")
