r"""MHA-DT-VN-69 locating-pin: McMaster 98381A417 stock dowel.

PURE DATA, no SolidWorks/COM calls and no ``build_*`` module in its import
closure.  Rule-23 retention, owner ruling 2026-11-07 (MHA-DT-00 rubric
sample, PR #2248).  One is installed in MHA-DT-00: the tip-block locating
dowel, which locates the MHA-DT-21 cone tip block on the MHA-DT-20 cone
swing platform beside its single hold-down screw, so the block cannot turn
on it.  It is pressed to the floor of the MHA-DT-21 foot's blind .0620 ream
and is a slip fit in the MHA-DT-20 plate's .0630 thru ream, the two
match-drilled at MHA-DT-00 step 2.

Both holes are made at assembly; each host owns its hole's station and
callout, and the foot's press ream reads the press-hole contract below.

Catalogue (https://www.mcmaster.com/98381A417/, read live 2026-11-07):
1/16 x 3/8 alloy-steel dowel, Round x Chamfer ends, Tolerance Rating
Standard, diameter +0.0001 to +0.0003 in over nominal (``DIA_BAND_IN``, the
98381A family's), Rockwell C47 minimum, ASME B18.8.2, 750 lbf double shear,
package of 50.  No recommended hole size is stated.

Part frame: axis local +Y through the origin; the pressed (chamfered) end
face at y = 0, the rounded lead end at y = LENGTH.
"""

from __future__ import annotations

import _config
from _fit_ream_h7 import REAM_H7
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
    "PRESS_HOLE_BAND",
    "PRESS_HOLE_DIA",
    "PRESS_INTERFERENCE_MM",
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
# Rule-23 retention, owner ruling 2026-11-07 (MHA-DT-00 rubric sample, PR
# #2248): the foot reams for a light press of the hardened 1/16
# dowel, .0620 REAM_H7 (.0620/.0625) -- the 3/32 dowel's convention
# (``_sprocket_seat_geometry.DRIVE_PIN_HOLE_DIA/BAND``, .0930 REAM_H7).
PRESS_HOLE_DIA = 0.0620 * MM_PER_IN  # 1.5748
PRESS_HOLE_BAND = REAM_H7  # +.0005/-.0000

# Diametral interference (min, max): the smallest pin in the largest hole and
# the largest pin in the smallest hole.  Both must grip.
PRESS_INTERFERENCE_MM = (
    DIA + DIA_BAND_IN[0] * MM_PER_IN - (PRESS_HOLE_DIA + PRESS_HOLE_BAND[0]),
    DIA + DIA_BAND_IN[1] * MM_PER_IN - (PRESS_HOLE_DIA + PRESS_HOLE_BAND[1]),
)  # (.0001, .0008) in
if min(PRESS_INTERFERENCE_MM) <= 0.0:
    raise AssertionError(f"{SKU} loses its press in the .0620 REAM_H7 hole")

# Catalogue sizes print as untoleranced REF (#2147): the catalogue tolerance
# governs; DIA_BAND_IN and the press window above stay the fit controls.
SUPPLIER_REFERENCE = SupplierPinReference(
    sku=SKU,
    units="in",
    diameter_mm=DIA,
    length_mm=LENGTH,
    diameter_precision=4,
    length_precision=3,
    sheet_unit=UNIT,
)
