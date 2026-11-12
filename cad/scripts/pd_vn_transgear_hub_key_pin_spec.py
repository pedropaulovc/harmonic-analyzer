r"""MHA-PD-VN-69 transgear hub key pin: McMaster 98381A416 stock dowel.

PURE DATA, no SolidWorks/COM calls and no ``build_*`` module in its import
closure.  One lies on a chord of the MHA-PD-17 disc hub's body, parallel to
its local X on the -Y side, pressed from +X into the chord's .0615 ream until
it bottoms on the ream's stop; its side lies along the MHA-PD-10 sleeve's
D-flat across the D-gap and keys the hub to the flat (#2409;
``pd_transgear_disc_hub_spec`` owns the hole, its location and every stack).

Catalogue (https://www.mcmaster.com/98381A416/, read live 2026-11-11 by
DBore2409): 1/16 x 5/16 alloy-steel dowel, ASME B18.8.2, min hardness Rockwell
C47, double shear 750 lbf, ends round x chamfer, diameter +0.0001 to +0.0003
in over nominal (``DIA_BAND_IN``, the 98381A family's).  No vendor model is
tracked, so the recipe is the nominal cylinder.

Part frame: axis local +Y through the origin; the lead end face, the one
that bottoms on the hub's stop, at y = 0, the outer end at y = LENGTH.
"""

from __future__ import annotations

import _config
from _fit_ream_h7 import REAM_H7
from _mcmaster_98381a416 import DIA_BAND_IN, DOWEL_SIZE, MM_PER_IN
from _package_units import drawing_unit
from _sprocket_seat_geometry import DRIVE_PIN_LENGTH_GRADE
from _supplier_pin_data import SupplierPinReference

__all__ = [
    "DIA",
    "DIA_BAND_IN",
    "DIA_LIMITS_MM",
    "LENGTH",
    "LENGTH_GRADE",
    "LENGTH_LIMITS_MM",
    "PRESS_HOLE_BAND",
    "PRESS_HOLE_DIA",
    "PRESS_INTERFERENCE_MM",
    "SKU",
    "SUPPLIER_REFERENCE",
    "UNIT",
]

# #290: the registry row's drawing_unit (in) is this sheet's unit; it drops
# the supplier REFs' inch suffix.
UNIT = drawing_unit(
    "parts/pd-vn-transgear-hub-key-pin", _config.parts("pd-vn-transgear-hub-key-pin")
)

SKU = "98381A416"
DIA, LENGTH = DOWEL_SIZE  # 1.5875 x 7.9375
DIA_LIMITS_MM = tuple(DIA + band * MM_PER_IN for band in DIA_BAND_IN)  # .0626/.0628
# The 98381A stock dowel family's +/-.010 in length grade (symmetric half-band).
LENGTH_GRADE = DRIVE_PIN_LENGTH_GRADE  # 0.254
LENGTH_LIMITS_MM = (LENGTH - LENGTH_GRADE, LENGTH + LENGTH_GRADE)  # .3025/.3225
# The hub reams the press hole with the shop's .0615 reamer (the MHA-DT-38
# press bore's), .0615 REAM_H7 (.0615/.0620).
PRESS_HOLE_DIA = 0.0615 * MM_PER_IN  # 1.5621
PRESS_HOLE_BAND = REAM_H7  # +.0005/-.0000

# Diametral interference (min, max): the smallest pin in the largest hole and
# the largest pin in the smallest hole.  Both must grip.
PRESS_INTERFERENCE_MM = (
    min(DIA_LIMITS_MM) - (PRESS_HOLE_DIA + max(PRESS_HOLE_BAND)),
    max(DIA_LIMITS_MM) - (PRESS_HOLE_DIA + min(PRESS_HOLE_BAND)),
)  # (.0006, .0013) in
if min(PRESS_INTERFERENCE_MM) <= 0.0:
    raise AssertionError(f"{SKU} loses its press in the .0615 REAM_H7 hole")

# Catalogue sizes print as untoleranced REF (#2147): the catalogue tolerance
# governs; DIA_BAND_IN and the press window above stay the fit controls.
SUPPLIER_REFERENCE = SupplierPinReference(
    sku=SKU,
    units="in",
    diameter_mm=DIA,
    length_mm=LENGTH,
    diameter_precision=4,
    length_precision=4,
    sheet_unit=UNIT,
)
