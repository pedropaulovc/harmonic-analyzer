"""MHA-CH-06-TL-VN-79: purchased oblique-trammel pivot shim.

Source: https://www.mcmaster.com/98055A118/
Read live 2026-10-23; page-stated dimensions only (mm).
Bands are (upper, lower) deviations. No supplier length band is inferred.
Model: nominal supplied envelope; unstated edge forms are not invented.
Frame: axis +Z; origin at the bottom face.
Supplied component is installed without shop modification.
"""

from __future__ import annotations

from _fit_deviations import deviations

SKU = "98055A118"
QUANTITY = 2
ID = 10.0
ID_BAND = (0.4, 0.03)  # upper, lower deviations, mm
OD = 16.0
OD_BAND = (-0.04, -0.47)
THICKNESS = 0.2
THICKNESS_BAND = (0.0, -0.04)
FIT_SKUS = {0.1: "98055A117", 0.2: "98055A118", 0.5: "98055A121"}
FIT_THICKNESS_BANDS = {0.1: (0.0, -0.03), 0.2: THICKNESS_BAND, 0.5: (0.0, -0.05)}
LENGTH = THICKNESS

SUPPLIER_REFERENCE_DIMENSIONS = (('SupplierBoreDiameter', 10.0, 'horizontal'), ('SupplierOuterDiameter', 16.0, 'horizontal'), ('SupplierThickness', 0.2, 'vertical'))
SUPPLIER_REFERENCE_STARTS = {'SupplierBoreDiameter': (-5.0, 0.0), 'SupplierOuterDiameter': (-8.0, 0.0), 'SupplierThickness': (0.0, -0.2)}
SUPPLIER_REFERENCE_PLANES = {'SupplierBoreDiameter': 'Front', 'SupplierOuterDiameter': 'Front', 'SupplierThickness': 'Top'}
SUPPLIER_REFERENCE_FORMATS = {'SupplierBoreDiameter': (2, 'diameter', None, 'NOMINAL BORE DIAMETER'), 'SupplierOuterDiameter': (2, 'diameter', None, 'NOMINAL OUTER DIAMETER'), 'SupplierThickness': (2, 'length', None, 'NOMINAL THICKNESS')}
SUPPLIER_REFERENCE_SIDES = {'SupplierBoreDiameter': 'bottom', 'SupplierOuterDiameter': 'bottom', 'SupplierThickness': 'left'}
SUPPLIER_REFERENCE_UNITS = {'SupplierBoreDiameter': 'mm', 'SupplierOuterDiameter': 'mm', 'SupplierThickness': 'mm'}
SUPPLIER_REFERENCE_TOLERANCES_MM = {
    'SupplierBoreDiameter': deviations(ID_BAND),
    'SupplierOuterDiameter': deviations(OD_BAND),
    'SupplierThickness': deviations(THICKNESS_BAND),
}
SUPPLIER_DATA = ('MODEL: ONE 0.2 mm SHIM PER PIVOT.', 'FITTING STOCK: 98055A117 (0.1 mm), 98055A121 (0.5 mm).', 'SELECT AT ASSEMBLY TO THE JIG RUNNING-GAP REQUIREMENT.')
