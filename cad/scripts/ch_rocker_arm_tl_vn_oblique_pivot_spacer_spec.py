"""MHA-CH-06-TL-VN-78: purchased oblique-trammel pivot spacer.

Source: https://www.mcmaster.com/92871A359/
Read live 2026-10-23; page-stated dimensions only (mm).
Supplier material is 18-8 stainless, ASTM A582; no specific grade is stated.
Registry/native AISI 304 is an engineering CAD-library surrogate only,
used for appearance and approximate mass, not a supplier-grade claim.
Bands are (upper, lower) deviations. No supplier length band is inferred.
Model: nominal supplied envelope; unstated edge forms are not invented.
Frame: axis +Z; origin at the bottom face.
Supplied component is installed without shop modification.
"""

from __future__ import annotations

from _fit_deviations import deviations

SKU = "92871A359"
QUANTITY = 2
ID = 10.0
ID_BAND = (0.3, 0.0)  # upper, lower deviations, mm
OD = 16.0
OD_BAND = (0.13, -0.13)
LENGTH = 15.0
LENGTH_BAND = (0.13, -0.13)

SUPPLIER_REFERENCE_DIMENSIONS = (('SupplierBoreDiameter', 10.0, 'horizontal'), ('SupplierOuterDiameter', 16.0, 'horizontal'), ('SupplierLength', 15.0, 'vertical'))
SUPPLIER_REFERENCE_STARTS = {'SupplierBoreDiameter': (-5.0, 0.0), 'SupplierOuterDiameter': (-8.0, 0.0), 'SupplierLength': (0.0, -15.0)}
SUPPLIER_REFERENCE_PLANES = {'SupplierBoreDiameter': 'Front', 'SupplierOuterDiameter': 'Front', 'SupplierLength': 'Top'}
SUPPLIER_REFERENCE_FORMATS = {'SupplierBoreDiameter': (2, 'diameter', None, 'NOMINAL BORE DIAMETER'), 'SupplierOuterDiameter': (2, 'diameter', None, 'NOMINAL OUTER DIAMETER'), 'SupplierLength': (2, 'length', None, 'NOMINAL LENGTH')}
SUPPLIER_REFERENCE_SIDES = {'SupplierBoreDiameter': 'bottom', 'SupplierOuterDiameter': 'bottom', 'SupplierLength': 'left'}
SUPPLIER_REFERENCE_UNITS = {'SupplierBoreDiameter': 'mm', 'SupplierOuterDiameter': 'mm', 'SupplierLength': 'mm'}
SUPPLIER_REFERENCE_TOLERANCES_MM = {
    'SupplierBoreDiameter': deviations(ID_BAND),
    'SupplierOuterDiameter': deviations(OD_BAND),
    'SupplierLength': deviations(LENGTH_BAND),
}
SUPPLIER_DATA = ('SUPPLIED SPACER; NO SHOP MACHINING.', 'LOOSE BORE IS NOT A LOCATING BUSHING.')
