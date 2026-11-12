r"""MHA-PD-VN-70 transgear-collar-flat-pin: McMaster 90145A414 stock dowel.

PURE DATA, no SolidWorks/COM calls and no ``build_*`` module in its import
closure.  One is pressed parallel to the axis into the blind ream on local -Y
of the brass knob drive collar (MHA-PD-22), to the ream's floor; its crest,
the surface nearest the collar's axis, stands inside the round bore and is
the collar's drive flat on the MHA-PD-08 knob shaft's D-flat
(``pd_transgear_drive_collar_spec`` owns the hole, its station and every
stack).  The pin is unhardened, so where its rear end stands past the
collar's fitted rear face it is faced flush with that face at assembly, and
the collar's rear 45° bore break then cuts its crest corner with the brass.

Catalogue (https://www.mcmaster.com/90145A414/, read live 2026-11-11):
18-8 stainless steel dowel pin, 1/16 x 3/16, diameter 0 to +.0002 in over
nominal (``DIA_BAND_IN``), hardness not rated, Chamfer ends, standard
tolerance rating.  The chamfer size is not stated and no vendor model is
tracked, so the recipe is the nominal cylinder.

Part frame: axis local +Y through the origin; the end pressed to the floor
at y = 0, the other end at y = LENGTH as supplied.  The model's default
configuration is the pin faced flush with the MHA-PD-22 model's rear face
(``pd_transgear_drive_collar_spec.FLAT_PIN_LENGTH``) with its crest corner
broken, the one the assembly places; ``SUPPLIER_STOCK_CONFIGURATION``
suppresses both cuts and is the catalogue pin the purchased sheet documents.
"""

from __future__ import annotations

import _config
from _fit_ream_h7 import REAM_H7
from _mcmaster_90145a414 import DIA_BAND_IN, DOWEL_SIZE, MM_PER_IN
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
    "SUPPLIER_STOCK_CONFIGURATION",
    "SUPPLIER_STOCK_SUPPRESSED_FEATURES",
    "UNIT",
]

# #290: the registry row's drawing_unit (in) is this sheet's unit; it drops
# the supplier REFs' inch suffix.
UNIT = drawing_unit(
    "parts/pd-vn-transgear-collar-flat-pin",
    _config.parts("pd-vn-transgear-collar-flat-pin"),
)

SKU = "90145A414"
DIA, LENGTH = DOWEL_SIZE  # 1.5875 x 4.7625
DIA_LIMITS_MM = tuple(DIA + band * MM_PER_IN for band in DIA_BAND_IN)  # .0625/.0627
# The catalogue states no length tolerance; the stacks charge the 98381A
# stock dowels' +/-.010 in grade (a conservative standard-rating allowance).
LENGTH_GRADE = DRIVE_PIN_LENGTH_GRADE  # 0.254
LENGTH_LIMITS_MM = (LENGTH - LENGTH_GRADE, LENGTH + LENGTH_GRADE)  # .1775/.1975
# The collar reams the press hole with the shop's .0615 reamer (the MHA-DT-38
# press bore's), .0615 REAM_H7 (.0615/.0620).
PRESS_HOLE_DIA = 0.0615 * MM_PER_IN  # 1.5621
PRESS_HOLE_BAND = REAM_H7  # +.0005/-.0000

# Diametral interference (min, max): the smallest pin in the largest hole and
# the largest pin in the smallest hole.  Both must grip.
PRESS_INTERFERENCE_MM = (
    min(DIA_LIMITS_MM) - (PRESS_HOLE_DIA + max(PRESS_HOLE_BAND)),
    max(DIA_LIMITS_MM) - (PRESS_HOLE_DIA + min(PRESS_HOLE_BAND)),
)  # (.0005, .0012) in
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
    length_precision=3,
    sheet_unit=UNIT,
)

# The as-supplied catalogue pin: the facing and the crest break suppressed
# (the pd-vn-transgear-pivot-screw precedent).
SUPPLIER_STOCK_CONFIGURATION = "AS SUPPLIED STOCK"
SUPPLIER_STOCK_SUPPRESSED_FEATURES = ("StockFacing", "CrestBreak")
