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

# The OD and length carriers lie on Top-view edges, so their construction lines
# print under the outline: the OD on the z = LENGTH face (the view's lower
# edge), the length on the OD silhouette.
SUPPLIER_REFERENCE_DIMENSIONS = (('SupplierOuterDiameter', OD, 'horizontal'), ('SupplierLength', LENGTH, 'vertical'))
SUPPLIER_REFERENCE_STARTS = {'SupplierOuterDiameter': (-OD / 2.0, -LENGTH), 'SupplierLength': (OD / 2.0, -LENGTH)}
SUPPLIER_REFERENCE_PLANES = {'SupplierOuterDiameter': 'Top', 'SupplierLength': 'Top'}
# Bands print as stacked limits (max over min) inside one parenthesis.
SUPPLIER_REFERENCE_FORMATS = {'SupplierOuterDiameter': (3, 'diameter', None, 'OUTSIDE'), 'SupplierLength': (3, 'length', None, 'LENGTH')}
# The OD takes the bottom lane; the length sits right of the Top view.
SUPPLIER_REFERENCE_SIDES = {'SupplierOuterDiameter': 'bottom', 'SupplierLength': 'right'}
SUPPLIER_REFERENCE_UNITS = {'SupplierOuterDiameter': 'in', 'SupplierLength': 'in'}
SUPPLIER_REFERENCE_TOLERANCES_MM = {
    'SupplierOuterDiameter': deviations(OD_BAND),
    'SupplierLength': deviations(LENGTH_BAND),
}
# The bore is the ring profile's own bore-circle diameter, printed on the
# Front (end) view's visible bore circle: the edge-on Top view shows no bore.
BORE_FEATURE = "RingProfile"
BORE_DIMENSION = "SupplierBoreDiameter"
BORE_FORMAT = (3, "diameter", None, "BORE")
BORE_TOLERANCE_MM = deviations(ID_BAND)
