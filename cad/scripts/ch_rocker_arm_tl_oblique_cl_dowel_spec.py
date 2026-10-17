r"""MHA-CH-006-TL-33 oblique-trammel CL locator dowel: McMaster 91595A452.

PURE DATA, no SolidWorks/COM calls and no ``build_*`` module in its import
closure.  Shop fixture (cad/docs/subsystem-identities.md): one 6 x 20 m6
dowel, inventory ``fixtures.trammel-cl-dowel``, bought as a pack of 25.  Once
the carrier's CL spot is finished in place to Ø6 N7 on the running jig
(``carrier.CL_HOLE_BAND``), the dowel is pressed, chamfered end first, until
that end is flush with the carrier's underside; its proud length passes the
riser's Ø7 clamp hole (``riser.CLAMP_DIA``) and enters the rocker strap
blank's CL hole in the end waste.

Sources:

* SOURCED, https://www.mcmaster.com/91595A452/ read live 2026-10-17
  (inventory note): 52100 alloy steel, Ø6 +0.004/+0.012 (DIN 6325-m6 /
  ISO 8734), 20 long (length tolerance not stated), Rockwell C52 min, end
  shape "Round x Chamfer/Round".
* FROM THE CARRIER SPEC (imported): ``CL_DOWEL_DIA`` (6), ``CL_DOWEL_BAND``
  (m6), ``CL_HOLE_BAND`` (N7), ``CL_DOWEL_INTERFERENCE`` (0.008-0.028
  diametral) and the plate ``THICKNESS``; the stack above it from
  ``trammel`` (``RISER_THICK``, ``STRAP_THICK``).
* VENDOR MODEL: the end forms (15 deg x 1.17 chamfer with an R5.016 crown,
  R5.45 dome) are read off McMaster's STEP (``_mcmaster_91595a452``); the
  recipe is ``diagnostics/diag_build_91595A452.py``.  The vendor SLDPRT/STEP
  (downloaded 2026-10-17) is read for dimensions only and NOT replica-gated
  (user ruling 2026-10-17); the recipe's standalone run is catalog-only.

Model diameter: nominal Ø6.000, the vendor's.  The carrier models CL as its
Ø3 x 90 deg centre-drill spot only (finished in place, like HUB), so the
assembly's press-fit allowance for this pair is the dowel's own volume in the
plate, as ``_interference_contracts.JIG_HUB_PIN_SEAT`` bounds the HUB pin:
``PRESS_ALLOWANCE_MM3`` below (1.10 x a Ø6 x 12 cylinder), which the modelled
overlap (``PRESS_OVERLAP_MM3``: the pin inside the plate less the spot cone)
stays under.

Part frame: pin axis local +Y through the origin, published as ``ScrewAxis``
(Front ∩ Right); the chamfered end's tip at y = 0 (the Top Plane), the round
end's tip at y = LENGTH.  Mate the Top Plane to the carrier's underside.
"""

from __future__ import annotations

import math

import ch_rocker_arm_tl_oblique_carrier_spec as carrier
import ch_rocker_arm_tl_oblique_riser_spec as riser
import ch_rocker_arm_tl_oblique_trammel_spec as trammel
from _mcmaster_91595a452 import (
    CHAMFER_LEN,
    CROWN_H,
    DIA,
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
# The lead-in that grips nothing: the crown and the chamfer.
LEAD_IN = CROWN_H + CHAMFER_LEN  # 1.95

# Pressed flush with the carrier's underside: the whole plate is the press.
PRESS_DEPTH = carrier.THICKNESS  # 12
PROUD = LENGTH - PRESS_DEPTH  # 8, up through the riser into the strap
# A press-fit dowel grips at least 1.5 D over its full diameter
# (drawing-guidelines.md rule 18 applied to the press, as
# vn_knife_mount_dowel_spec does): (12 - 1.95) / 6 = 1.675 D.
PRESS_ENGAGEMENT_MIN_D = 1.5
PRESS_ENGAGEMENT_D = (PRESS_DEPTH - LEAD_IN) / DIA
if PRESS_ENGAGEMENT_D < PRESS_ENGAGEMENT_MIN_D:
    raise AssertionError(
        f"the CL dowel grips {PRESS_ENGAGEMENT_D:.2f} D in the carrier,"
        f" under {PRESS_ENGAGEMENT_MIN_D} D"
    )
# The proud length clears the riser and locates the strap without standing
# above it: 8 - 6 = 2.0 into the 2.5 strap.
STRAP_ENGAGEMENT = PROUD - trammel.RISER_THICK
if not 0.0 < STRAP_ENGAGEMENT <= trammel.STRAP_THICK:
    raise AssertionError(
        f"the CL dowel enters the strap {STRAP_ENGAGEMENT:.2f},"
        f" outside 0..{trammel.STRAP_THICK}"
    )
if riser.CLAMP_DIA <= DIA_MAX:
    raise AssertionError("the riser's clamp hole does not clear the CL dowel")


def _press_overlap_mm3() -> float:
    """The modelled pin's volume inside the 12 plate (crown cap, chamfer
    frustum, cylinder to the top face) less the carrier's Ø3 x 90 deg spot
    cone at the top face, which the pin's axis passes through."""
    radius, rim = DIA / 2.0, chamfer_rim_radius()
    crown = math.pi * CROWN_H**2 * (3.0 * crown_radius() - CROWN_H) / 3.0
    chamfer = math.pi / 3.0 * CHAMFER_LEN * (radius**2 + radius * rim + rim**2)
    cylinder = math.pi * radius**2 * (PRESS_DEPTH - LEAD_IN)
    spot_r = carrier.SPOT_DIA / 2.0
    spot_depth = spot_r * math.tan(math.radians(carrier.SPOT_FLANK_ANGLE))
    spot = math.pi * spot_r**2 * spot_depth / 3.0
    return crown + chamfer + cylinder - spot


PRESS_OVERLAP_MM3 = _press_overlap_mm3()  # ~319.5
PRESS_ALLOWANCE_MM3 = 1.10 * math.pi * DIA**2 * PRESS_DEPTH / 4.0  # ~373.2
if PRESS_OVERLAP_MM3 >= PRESS_ALLOWANCE_MM3:
    raise AssertionError("the CL dowel's modelled press exceeds its allowance")
