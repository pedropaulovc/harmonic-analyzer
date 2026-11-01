r"""MHA-CH-06-TL-VN-53 oblique-trammel CL locator dowel: McMaster 98381A542.

PURE DATA, no SolidWorks/COM calls and no ``build_*`` module in its import
closure.  Shop fixture (cad/docs/subsystem-identities.md): one 1/4 x 1 in
alloy-steel dowel, bought as a pack of 25.  Once the carrier's CL spot is
finished in place to .2490-.2495 on the running jig (``carrier.CL_HOLE_BAND``,
the owned .2490 reamer), press chamfered end first with the actual riser
installed. Set its round tip ``TIP_SET_MIN``–``TIP_SET_MAX`` above the actual
riser top. Check that the strap seats flat, locates and slips on/off without
the pin standing above it.  The 1 in pin passes through the carrier and its
chamfered end stands below the carrier's underside.

Sources:

* SOURCED, McMaster 98381A542 (live category table
  https://www.mcmaster.com/products/dowel-pins/diameter~1-4/length~1/, read
  2026-10-31; the detail page is login-walled): alloy steel, 1/4 in diameter
  +.0001/+.0003 (.2501-.2503), 1 in long (length tolerance not stated),
  Rockwell C47 min, ASME B18.8.2, end shape "Round x Chamfer".
* FROM THE CARRIER SPEC (imported): ``CL_DOWEL_DIA`` (.250), ``CL_DOWEL_BAND``,
  ``CL_HOLE_BAND``, ``CL_DOWEL_INTERFERENCE`` (.0006-.0013 diametral);
  finished plate thicknesses come from ``carrier`` and ``riser``, and the strap
  thickness band comes from ``rocker``.
* VENDOR MODEL: the end forms (a 16 deg x .0262 chamfer to a flat Ø.235 face,
  an R.031 round to a flat Ø.188 face) are read off McMaster's STEP
  (``_mcmaster_98381a542``); the recipe is ``diagnostics/diag_build_98381A542.py``,
  the shared ``diag_mcmaster_dowel`` section.  The STEP is read for
  dimensions only and NOT replica-gated; the recipe's standalone run is
  catalog-only.

Model diameter: nominal Ø.250, the vendor's.  The carrier models CL as its
Ø.12 x 90 deg centre-drill spot only (finished in place, like HUB), so the
assembly's press-fit allowance for this pair is the dowel's own volume in the
plate, as ``_interference_contracts.JIG_HUB_PIN_SEAT`` bounds the HUB pin:
``PRESS_ALLOWANCE_MM3`` below (1.10 x a Ø.250 x .47 carrier cylinder), which
the modelled overlap (only pin metal inside the carrier, less its centre spot)
stays under.

Part frame: pin axis local +Y through the origin, published as ``ScrewAxis``
(Front ∩ Right); the chamfered end's face at y = 0 (the Top Plane), the round
end's face at y = LENGTH. Mate the Top Plane at ``TIP_BASE_Z``, not flush.
"""

from __future__ import annotations

import math

import _config
import ch_rocker_arm_spec as rocker
import ch_rocker_arm_tl_oblique_carrier_spec as carrier
import ch_rocker_arm_tl_oblique_pivot_block_spec as pivot_block
import ch_rocker_arm_tl_oblique_riser_spec as riser
import ch_rocker_arm_tl_oblique_trammel_spec as trammel
from _mcmaster_98381a542 import DOWEL_SIZE, ENDS
from _package_units import drawing_unit

UNIT = drawing_unit(
    "parts/ch-rocker-arm-tl-vn-oblique-cl-dowel",
    _config.parts("ch-rocker-arm-tl-vn-oblique-cl-dowel"),
)

SKU = "98381A542"
QUANTITY = 1
PACK_QUANTITY = 25  # McMaster sells 98381A542 in packs of 25

DIA, LENGTH = DOWEL_SIZE
if DIA != carrier.CL_DOWEL_DIA:
    raise AssertionError("the CL dowel and the carrier's CL fit disagree on size")
DIA_BAND = carrier.CL_DOWEL_BAND  # (upper, lower): +.0003/+.0001
HOLE_BAND = carrier.CL_HOLE_BAND
INTERFERENCE = carrier.CL_DOWEL_INTERFERENCE  # diametral (min, max)
DIA_MAX = DIA + max(DIA_BAND)  # .2503
DIA_MIN = DIA + min(DIA_BAND)  # .2501

# The pressed end's lead-in that grips nothing: the chamfer.
LEAD_IN = ENDS.chamfer_len(DIA)  # .0262

# The supplier table's nominal 1/4 and 1 print as untoleranced references;
# the table's diameter band is quoted on the sheet's supplier line. Both
# carriers lie on Front-view edges, so their construction lines print under
# the outline: the diameter on the chamfer's edge with the cylinder (y =
# LEAD_IN), the length on the left silhouette. The Top (end) view shows no
# chord across the pin.
SUPPLIER_REFERENCE_DIMENSIONS = (
    ("SupplierDowelDiameter", DIA, "horizontal"),
    ("SupplierDowelLength", LENGTH, "vertical"),
)
SUPPLIER_REFERENCE_STARTS = {
    "SupplierDowelDiameter": (-DIA / 2.0, LEAD_IN),
    "SupplierDowelLength": (-DIA / 2.0, 0.0),
}
SUPPLIER_REFERENCE_PLANES = {
    "SupplierDowelDiameter": "Front",
    "SupplierDowelLength": "Front",
}
SUPPLIER_REFERENCE_SIDES = {
    "SupplierDowelDiameter": "bottom",
    "SupplierDowelLength": "left",
}
SUPPLIER_REFERENCE_FORMATS = {
    "SupplierDowelDiameter": (0, "diameter", 4, "NOMINAL PIN DIAMETER"),
    "SupplierDowelLength": (0, "length", None, "NOMINAL LENGTH"),
}
SUPPLIER_REFERENCE_UNITS = {
    "SupplierDowelDiameter": "in",
    "SupplierDowelLength": "in",
}
SUPPLIER_REFERENCE_TOLERANCES_MM: dict[str, tuple[float, float]] = {}
SUPPLIER_DATA = (
    "DIAMETER +.0001/+.0003 OVER NOMINAL; ROUND / CHAMFER ENDS.",
    "SUPPLIER LENGTH TOLERANCE NOT STATED.",
)
# The round end's corner: the cylinder stops ROUND_H short of the far face.
ROUND_H = ENDS.crown_r  # .031

# Owner-approved assembly fit-up (#1619): use the purchased pin, not a new
# shop-made locator. These are functional set-height limits, not tighter
# manufacturing bands on either plate. Native reference geometry shows the
# midpoint; the actual riser is the installation datum. Inside the strap's
# thinnest, with the full cylinder (past the round end's corner) in its hole.
TIP_SET_MIN = 1.524  # .060
TIP_SET_MAX = 1.7272  # .068
TIP_HEIGHT = (TIP_SET_MIN + TIP_SET_MAX) / 2.0  # .064
PROUD = riser.THICKNESS + TIP_HEIGHT
PRESS_DEPTH = LENGTH - PROUD
TIP_BASE_Z = trammel.CARRIER_TOP_Z - PRESS_DEPTH
PRESS_ENGAGEMENT_MIN_D = 1.5


def press_contact(carrier_thick: float, riser_thick: float, tip_set: float) -> float:
    """Full-diameter pin cylinder inside the carrier's hole, between its two
    mouths' title-block edge breaks, for one finished stack (catalogue nominal
    pin and end forms; no supplier length band is stated)."""
    bottom = carrier_thick + riser_thick + tip_set - LENGTH  # from the underside
    cylinder = (bottom + LEAD_IN, bottom + LENGTH - ROUND_H)
    hole = (carrier.TAP_MOUTH_BREAK, carrier_thick - carrier.TAP_MOUTH_BREAK)
    return min(cylinder[1], hole[1]) - max(cylinder[0], hole[0])


_STACKS = tuple(
    (
        carrier.THICKNESS + c * carrier.THICKNESS_BAND,
        riser.THICKNESS + r * riser.THICKNESS_BAND,
        tip,
    )
    for c in (-1.0, 1.0)
    for r in (-1.0, 1.0)
    for tip in (TIP_SET_MIN, TIP_SET_MAX)
)
PRESS_ENGAGEMENT_D = (
    press_contact(carrier.THICKNESS, riser.THICKNESS, TIP_HEIGHT) / DIA_MAX
)
# Design accounting across both finished-plate bands and the set band, not a
# receipt-inspection protocol. Normal assembly verifies set height and strap fit.
PRESS_ENGAGEMENT_MIN = min(press_contact(*stack) for stack in _STACKS)
CYLINDER_ENGAGEMENT_MIN = TIP_SET_MIN - ROUND_H
STRAP_TOP_CLEARANCE_MIN = (
    rocker.ARM_THICKNESS + min(rocker.ARM_THICKNESS_BAND) - TIP_SET_MAX
)
# The chamfered end below the carrier's underside, at the catalogue pin length
# and finished-plate limits. The pivot-block top plane is a conservative
# ceiling for the feed hardware and the allowed studs below the carrier; the
# pin/block envelope is also excluded in plan at either pair of pin holes.
BOTTOM_PROJECTION_MAX = max(
    0.0,
    -min(c + r + tip - LENGTH for c, r, tip in _STACKS),
)
_PIVOT_BLOCK_PLAN_RADIUS = math.hypot(
    max(
        abs(pivot_block.BLOCK_X0 - pivot_block.BORE_X),
        abs(pivot_block.BLOCK_X1 - pivot_block.BORE_X),
    ),
    pivot_block.BLOCK_WIDTH / 2.0,
)
PIN_PLAN_CLEARANCE = (
    min(math.dist(trammel.CL, point) for point in trammel.PIN_HOLES.values())
    - _PIVOT_BLOCK_PLAN_RADIUS
    - DIA_MAX / 2.0
)
if BOTTOM_PROJECTION_MAX >= trammel.PIVOT_SUPPORT_HEIGHT:
    raise AssertionError("the CL lower end reaches the below-carrier top envelope")
if PIN_PLAN_CLEARANCE <= 0.0:
    raise AssertionError("the CL lower end can meet a pivot pin or block in plan")
if PRESS_ENGAGEMENT_MIN < PRESS_ENGAGEMENT_MIN_D * DIA_MAX:
    raise AssertionError("the CL fit-up leaves under 1.5D full-diameter press")
if CYLINDER_ENGAGEMENT_MIN <= 0.0 or STRAP_TOP_CLEARANCE_MIN <= 0.0:
    raise AssertionError("the CL fit-up misses the strap cylinder or stands proud")
if riser.CLAMP_DIA <= DIA_MAX:
    raise AssertionError("the riser's clamp hole does not clear the CL dowel")


def _press_overlap_mm3() -> float:
    """Only the nominal installed pin metal inside the carrier slab.

    The chamfered end may stand below the underside and the round end always
    stands above the riser, so the slab clips the chamfer frustum and the
    cylinder; the carrier's native centre-drill spot is subtracted too.
    """
    radius, point_r = DIA / 2.0, ENDS.point_dia / 2.0
    bottom = -PRESS_DEPTH + carrier.THICKNESS  # the pin's chamfered face
    if bottom + LENGTH - ROUND_H <= carrier.THICKNESS:
        raise AssertionError("the CL round end reaches into the carrier")

    def radius_at(z: float) -> float:
        return point_r + (radius - point_r) * (z - bottom) / LEAD_IN

    lo, hi = max(0.0, bottom), min(carrier.THICKNESS, bottom + LEAD_IN)
    chamfer = 0.0
    if hi > lo:
        r_lo, r_hi = radius_at(lo), radius_at(hi)
        chamfer = math.pi / 3.0 * (hi - lo) * (r_lo**2 + r_lo * r_hi + r_hi**2)
    cylinder = math.pi * radius**2 * (carrier.THICKNESS - max(0.0, bottom + LEAD_IN))
    spot_r = carrier.SPOT_DIA / 2.0
    spot_depth = spot_r * math.tan(math.radians(carrier.SPOT_FLANK_ANGLE))
    spot = math.pi * spot_r**2 * spot_depth / 3.0
    return chamfer + cylinder - spot


PRESS_OVERLAP_MM3 = _press_overlap_mm3()
PRESS_ALLOWANCE_MM3 = 1.10 * math.pi * DIA**2 * carrier.THICKNESS / 4.0
if PRESS_OVERLAP_MM3 >= PRESS_ALLOWANCE_MM3:
    raise AssertionError("the CL dowel's modelled press exceeds its allowance")
