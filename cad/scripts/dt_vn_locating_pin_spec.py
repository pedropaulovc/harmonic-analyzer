r"""MHA-DT-VN-69 locating-pin: McMaster 98381A417 stock dowel.

PURE DATA, no SolidWorks/COM calls and no ``build_*`` module in its import
closure.  Rule-23 retention, owner ruling 2026-11-07 (MHA-DT-00 rubric
sample, PR #2248).  One is installed in MHA-DT-00: the tip-block locating
dowel, which locates the MHA-DT-21 cone tip block on the MHA-DT-20 cone
swing platform beside its single hold-down screw, so the block cannot turn
on it.  It is bonded (LOCTITE 638) to the floor of the MHA-DT-21 foot's
blind 1/16 drilled hole and is a slip fit in the MHA-DT-20 plate's #52 thru
hole, the two drilled at MHA-DT-00 step 2 (owner ruling 2026-11-24, fit
audit question 11; was a press in a .0620 ream and a slip in a .0630 ream).

Both holes are made at assembly; each host owns its hole's station,
callout and fit (dt_cone_tip_block_spec.DOWEL_BOND_CLEARANCE_MM,
dt_cone_swing_platform_spec.TIP_DOWEL_SLIP_CLEARANCE_MM).

Catalogue (https://www.mcmaster.com/98381A417/, read live 2026-11-07):
1/16 x 3/8 alloy-steel dowel, Round x Chamfer ends, Tolerance Rating
Standard, diameter +0.0001 to +0.0003 in over nominal (``DIA_BAND_IN``, the
98381A family's), Rockwell C47 minimum, ASME B18.8.2, 750 lbf double shear,
package of 50.  No recommended hole size is stated.

Part frame: axis local +Y through the origin; the chamfered end face at
y = 0, the rounded lead end at y = LENGTH.
"""

from __future__ import annotations

import _config
from _mcmaster_98381a417 import DIA_BAND_IN, DOWEL_SIZE, MM_PER_IN
from _package_units import drawing_unit
from _sprocket_seat_geometry import DRIVE_PIN_LENGTH_GRADE
from _supplier_pin_data import SupplierPinReference

__all__ = [
    "DIA",
    "DIA_BAND_IN",
    "LENGTH",
    "LENGTH_GRADE",
    "LENGTH_LIMITS_MM",
    "MM_PER_IN",
    "SKU",
    "SUPPLIER_REFERENCE",
    "UNIT",
]

# #290: the registry row's drawing_unit (in) is this sheet's unit; it drops
# the supplier REFs' inch suffix.
UNIT = drawing_unit("parts/dt-vn-locating-pin", _config.parts("dt-vn-locating-pin"))

SKU = "98381A417"
DIA, LENGTH = DOWEL_SIZE  # 1.5875 x 9.525
# The 98381A stock dowel family's +/-.010 in length grade (symmetric half-band).
LENGTH_GRADE = DRIVE_PIN_LENGTH_GRADE  # 0.254
LENGTH_LIMITS_MM = (LENGTH - LENGTH_GRADE, LENGTH + LENGTH_GRADE)  # .365/.385

# Catalogue sizes print as untoleranced REF (#2147): the catalogue tolerance
# governs; DIA_BAND_IN stays the fit control its hosts read.
SUPPLIER_REFERENCE = SupplierPinReference(
    sku=SKU,
    units="in",
    diameter_mm=DIA,
    length_mm=LENGTH,
    diameter_precision=4,
    length_precision=3,
    sheet_unit=UNIT,
)
