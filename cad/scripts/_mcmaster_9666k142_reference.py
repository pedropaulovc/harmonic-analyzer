"""Supplier nominal cross-section, separate from both installed wire members.

The catalogue prints the wire diameter 0.008 in; the sheet prints .008. Its
stock circle is .2032 mm. Coil package length is ordering metadata, never
either member's developed cut length.
"""

SUPPLIER_DIAMETER_PRECISION = 3
# The REF carries no band of its own; the catalogue (+/-.001) governs it. The
# sheet's purchased-wire note names McMaster-Carr 9666K142 once.
SUPPLIER_DIAMETER_CALLOUT = "PER SUPPLIER"
SUPPLIER_REFERENCE_CONFIGURATION = "SUPPLIER_REFERENCE"
SUPPLIER_REFERENCE_FEATURE = "SupplierStockCrossSection"
SUPPLIER_REFERENCE_DIMENSION = "SupplierStockDia"
SUPPLIER_REFERENCE_DIMENSIONS = {
    SUPPLIER_REFERENCE_FEATURE: {SUPPLIER_REFERENCE_DIMENSION},
}
