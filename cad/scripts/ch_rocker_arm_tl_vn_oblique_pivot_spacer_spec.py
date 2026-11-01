"""MHA-CH-06-TL-VN-78: purchased oblique-trammel pivot spacer.

Source: https://www.aluminumspacers.com/as62-18-40 (AS62-18-40), read live
2026-10-31; page-stated dimensions only: 6061 aluminum, ID .382 +/-.003,
OD .625 +/-.005, length .625 +/-.005.
Main approved this spacer (option A, 2026-10-31). An aluminium spacer under the
aluminium carrier is accepted at this duty: the carrier swings +/-6 degrees, a
few cycles a job, on greased faces.
Bands are (upper, lower) deviations, in mm.
Model: nominal supplied envelope; unstated edge forms are not invented.
Frame: axis +Z; origin at the bottom face.
Supplied component is installed without shop modification.
"""

from __future__ import annotations

import _config
from _fit_deviations import deviations
from _package_units import drawing_unit

PART_NAME = "ch-rocker-arm-tl-vn-oblique-pivot-spacer"
UNIT = drawing_unit(
    "parts/ch-rocker-arm-tl-vn-oblique-pivot-spacer",
    _config.parts("ch-rocker-arm-tl-vn-oblique-pivot-spacer"),
)
SKU = "AS62-18-40"
QUANTITY = 2
ID = 9.7028  # .382
ID_BAND = (0.0762, -0.0762)  # +/-.003
OD = 15.875  # .625
OD_BAND = (0.127, -0.127)  # +/-.005
LENGTH = 15.875  # .625
LENGTH_BAND = (0.127, -0.127)  # +/-.005

SUPPLIER_REFERENCE_DIMENSIONS = (('SupplierBoreDiameter', ID, 'horizontal'), ('SupplierOuterDiameter', OD, 'horizontal'), ('SupplierLength', LENGTH, 'vertical'))
SUPPLIER_REFERENCE_STARTS = {'SupplierBoreDiameter': (-ID / 2.0, 0.0), 'SupplierOuterDiameter': (-OD / 2.0, 0.0), 'SupplierLength': (0.0, -LENGTH)}
SUPPLIER_REFERENCE_PLANES = {'SupplierBoreDiameter': 'Front', 'SupplierOuterDiameter': 'Front', 'SupplierLength': 'Top'}
# Bands print as stacked limits (max over min) inside one parenthesis.
SUPPLIER_REFERENCE_FORMATS = {'SupplierBoreDiameter': (3, 'diameter', None, 'BORE'), 'SupplierOuterDiameter': (3, 'diameter', None, 'OUTSIDE'), 'SupplierLength': (3, 'length', None, 'LENGTH')}
# The bore takes the top lane, the OD the bottom: each shelved text stays clear
# of the other's witnesses. The length sits right of the Top view.
SUPPLIER_REFERENCE_SIDES = {'SupplierBoreDiameter': 'top', 'SupplierOuterDiameter': 'bottom', 'SupplierLength': 'right'}
SUPPLIER_REFERENCE_UNITS = {'SupplierBoreDiameter': 'in', 'SupplierOuterDiameter': 'in', 'SupplierLength': 'in'}
SUPPLIER_REFERENCE_TOLERANCES_MM = {
    'SupplierBoreDiameter': deviations(ID_BAND),
    'SupplierOuterDiameter': deviations(OD_BAND),
    'SupplierLength': deviations(LENGTH_BAND),
}
