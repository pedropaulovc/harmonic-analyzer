"""MHA-CH-06-TL-VN-77: purchased oblique-trammel pivot screw.

Source: https://www.mcmaster.com/90323A492/
Read live 2026-10-23; page-stated dimensions only (mm).
Supplier material is 18-8 stainless, not a certified AISI 304 grade.
Registry/native AISI 304 is an engineering CAD-library surrogate only,
used for appearance and approximate mass; procurement is 18-8, HRB95.
Bands are (upper, lower) deviations. No supplier length band is inferred.
Model: nominal supplied envelope; unstated edge forms are not invented.
Frame: axis +Z; origin at the shoulder end face, +Z toward the head; thread extends -Z.
Supplied component is installed without shop modification.
"""

from __future__ import annotations

from _fit_deviations import deviations

SKU = "90323A492"
QUANTITY = 2
AXIS_NAME = "PivotAxis"
SHOULDER_DIA = 10.0
SHOULDER_DIA_BAND = (0.0, -0.025)  # upper, lower deviations, mm
SHOULDER_LENGTH = 35.0
SHOULDER_LENGTH_BAND = (0.05, 0.0)
THREAD = "M8x1.25"
THREAD_DIA = 8.0
THREAD_PITCH = 1.25
THREAD_LENGTH = 13.0
HEAD_DIA = 16.0
HEAD_HEIGHT = 4.5
HEX = 5.0
LENGTH = SHOULDER_LENGTH + HEAD_HEIGHT

# The head-height and thread-length sizes are stated in SUPPLIER_DATA, not as
# more chords on the small screw. Banded references print as stacked limits.
SUPPLIER_REFERENCE_DIMENSIONS = (('SupplierShoulderDiameter', 10.0, 'horizontal'), ('SupplierShoulderLength', 35.0, 'vertical'), ('SupplierHeadDiameter', 16.0, 'horizontal'))
SUPPLIER_REFERENCE_STARTS = {'SupplierShoulderDiameter': (-5.0, 0.0), 'SupplierShoulderLength': (0.0, -35.0), 'SupplierHeadDiameter': (-8.0, 0.0)}
SUPPLIER_REFERENCE_PLANES = {'SupplierShoulderDiameter': 'Front', 'SupplierShoulderLength': 'Top', 'SupplierHeadDiameter': 'Front'}
SUPPLIER_REFERENCE_FORMATS = {'SupplierShoulderDiameter': (3, 'diameter', None, 'SHOULDER'), 'SupplierShoulderLength': (2, 'length', None, 'SHOULDER LENGTH'), 'SupplierHeadDiameter': (0, 'diameter', None, 'HEAD')}
# The two Front diameters take opposite lanes so their shelved texts never meet.
SUPPLIER_REFERENCE_SIDES = {'SupplierShoulderDiameter': 'top', 'SupplierShoulderLength': 'right', 'SupplierHeadDiameter': 'bottom'}
SUPPLIER_REFERENCE_UNITS = {'SupplierShoulderDiameter': 'mm', 'SupplierShoulderLength': 'mm', 'SupplierHeadDiameter': 'mm'}
SUPPLIER_REFERENCE_TOLERANCES_MM = {
    'SupplierShoulderDiameter': deviations(SHOULDER_DIA_BAND),
    'SupplierShoulderLength': deviations(SHOULDER_LENGTH_BAND),
}
SUPPLIER_DATA = ('HEAD Ø16 X 4.5; THREAD M8 X 1.25 X 13 LONG; 5 mm HEX KEY.',)
