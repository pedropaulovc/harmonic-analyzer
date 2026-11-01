"""MHA-CH-06-TL-VN-79: purchased oblique-trammel pivot shim.

Sources: https://www.huyett.com/shim-0375-004, https://www.huyett.com/shim-0375-008,
https://www.huyett.com/shim-0375-020, read live 2026-10-31; page-stated
dimensions only: full-hard low-carbon steel, plain, lightly oiled; ID .376-.386,
OD .615-.635; thickness .0035-.0045 / .0073-.0088 / .019-.021.
Bands are (upper, lower) deviations, in mm. Fitting stock is keyed by its
nominal thickness in thousandths of an inch.
Model: nominal supplied envelope; unstated edge forms are not invented.
Frame: axis +Z; origin at the bottom face.
Supplied component is installed without shop modification.
"""

from __future__ import annotations

import _config
from _fit_deviations import deviations
from _package_units import drawing_unit

PART_NAME = "ch-rocker-arm-tl-vn-oblique-pivot-shim"
UNIT = drawing_unit(
    "parts/ch-rocker-arm-tl-vn-oblique-pivot-shim",
    _config.parts("ch-rocker-arm-tl-vn-oblique-pivot-shim"),
)
SKU = "SHIM-0375-008"
PER_SUPPORT = 5  # the nominal .040 pack under each of the two spacers
QUANTITY = 2 * PER_SUPPORT
ID = 9.5504  # .376
ID_BAND = (0.254, 0.0)  # .376-.386
OD = 15.875  # .625
OD_BAND = (0.254, -0.254)  # .615-.635
THICKNESS_THOU = 8
THICKNESS = 0.2032  # .008
THICKNESS_BAND = (0.02032, -0.01778)  # .0073-.0088
FIT_SKUS = {4: "SHIM-0375-004", 8: SKU, 20: "SHIM-0375-020"}
FIT_THICKNESS_BANDS = {4: (0.0127, -0.0127), 8: THICKNESS_BAND, 20: (0.0254, -0.0254)}
LENGTH = THICKNESS

# Every carrier lies on a Top-view edge, so its construction line prints under
# the outline: the bore on the z = 0 face (the view's upper edge), the OD on
# the z = THICKNESS face (its lower edge), the thickness on the OD silhouette.
# The Front (bore) view shows no chord across the rings.
SUPPLIER_REFERENCE_DIMENSIONS = (('SupplierBoreDiameter', ID, 'horizontal'), ('SupplierOuterDiameter', OD, 'horizontal'), ('SupplierThickness', THICKNESS, 'vertical'))
SUPPLIER_REFERENCE_STARTS = {'SupplierBoreDiameter': (-ID / 2.0, 0.0), 'SupplierOuterDiameter': (-OD / 2.0, -THICKNESS), 'SupplierThickness': (OD / 2.0, -THICKNESS)}
SUPPLIER_REFERENCE_PLANES = {'SupplierBoreDiameter': 'Top', 'SupplierOuterDiameter': 'Top', 'SupplierThickness': 'Top'}
# Bands print as stacked limits (max over min) inside one parenthesis.
SUPPLIER_REFERENCE_FORMATS = {'SupplierBoreDiameter': (3, 'diameter', None, 'BORE'), 'SupplierOuterDiameter': (3, 'diameter', None, 'OUTSIDE'), 'SupplierThickness': (4, 'length', None, 'THICKNESS')}
# The bore takes the top lane, the OD the bottom: each shelved text stays clear
# of the other's witnesses. The thickness sits right of the Top view.
SUPPLIER_REFERENCE_SIDES = {'SupplierBoreDiameter': 'top', 'SupplierOuterDiameter': 'bottom', 'SupplierThickness': 'right'}
SUPPLIER_REFERENCE_UNITS = {'SupplierBoreDiameter': 'in', 'SupplierOuterDiameter': 'in', 'SupplierThickness': 'in'}
SUPPLIER_REFERENCE_TOLERANCES_MM = {
    'SupplierBoreDiameter': deviations(ID_BAND),
    'SupplierOuterDiameter': deviations(OD_BAND),
    'SupplierThickness': deviations(THICKNESS_BAND),
}
SUPPLIER_DATA = ('MODEL: FIVE .008 SHIMS PER PIVOT, NOMINAL.', 'FITTING STOCK: SHIM-0375-004 (.004), SHIM-0375-020 (.020).', 'SELECT AT ASSEMBLY TO THE JIG RUNNING-GAP REQUIREMENT.')
