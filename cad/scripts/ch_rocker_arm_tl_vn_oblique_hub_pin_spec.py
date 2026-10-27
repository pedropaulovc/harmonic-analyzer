"""MHA-CH-06-TL-VN-80: purchased oblique-trammel hub pin.

Source: https://www.mcmaster.com/2281A11-6410N695/
Read live 2026-10-23; page-stated dimensions only (mm).
Bands are (upper, lower) deviations. No supplier length band is inferred.
Model: nominal supplied envelope; unstated edge forms are not invented.
Frame: axis +Z; origin at the bottom face.
The 20.0 mm abrasive cut and Loctite 638 assembly bond are owner requirements, not supplier claims.
"""

from __future__ import annotations

from _fit_deviations import deviations

SKU = "2281A11"
QUANTITY = 1
CONFIGURED_SKU = "2281A11-6410N695"
DIA = 10.2
DIA_BAND = (0.0, -0.00254)  # upper, lower deviations, mm
SUPPLY_LENGTH = 50.8  # page-stated 2 in
CUT_LENGTH = 20.0  # owner-approved shop cut, not a supplier length
LENGTH = CUT_LENGTH
BOND = "Loctite 638"
TIP_SET = 2.0
TIP_SET_BAND = 0.2

SUPPLIER_REFERENCE_DIMENSIONS = (('SupplierPinDiameter', 10.2, 'horizontal'), ('SupplierCutLength', 20.0, 'vertical'))
SUPPLIER_REFERENCE_STARTS = {'SupplierPinDiameter': (-5.1, 0.0), 'SupplierCutLength': (0.0, -20.0)}
SUPPLIER_REFERENCE_PLANES = {'SupplierPinDiameter': 'Front', 'SupplierCutLength': 'Top'}
SUPPLIER_REFERENCE_FORMATS = {'SupplierPinDiameter': (5, 'diameter', None, 'NOMINAL PIN DIAMETER'), 'SupplierCutLength': (1, 'length', None, 'ABRASIVE CUT LENGTH')}
SUPPLIER_REFERENCE_SIDES = {'SupplierPinDiameter': 'bottom', 'SupplierCutLength': 'left'}
SUPPLIER_REFERENCE_UNITS = {'SupplierPinDiameter': 'mm', 'SupplierCutLength': 'mm'}
SUPPLIER_REFERENCE_TOLERANCES_MM = {'SupplierPinDiameter': deviations(DIA_BAND)}
SUPPLIER_DATA = ('PURCHASE 2281A11, SIZE 10.2000 mm (2 in SUPPLY).', 'ABRASIVE CUT-OFF TO THE NATIVE CUT LENGTH; DEBURR CUT END.', 'CUT END DOWN; FACTORY END UP. NO OTHER PIN MODIFICATION.', 'BOND WITH LOCTITE 638; SET HEIGHT PER JIG ASSEMBLY.')
