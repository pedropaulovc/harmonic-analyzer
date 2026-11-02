"""Supplier nominal cross-section, separate from both installed wire members.

The supplier engineering drawing prints .0310 inches; the sheet prints .031. Its stock circle is
.7874 mm, not the accepted installed .8-mm clearance envelope. Coil package
length is ordering metadata, never either member's developed cut length.
"""

SUPPLIER_DRAWING_URL = (
    "https://www.mcmaster.com/mvC/Library/CAD2/20260111/6A9AB2E8/"
    "9666K56_Lubricated%201080%20Spring%20Steel%20WireX.GIF"
)
SUPPLIER_DIAMETER_PRECISION = 3
# The REF carries no band of its own; the catalogue (+/-.001) governs it. The
# sheet's purchased-wire note names McMaster-Carr 9666K56 once.
SUPPLIER_DIAMETER_CALLOUT = "PER SUPPLIER"
SUPPLIER_REFERENCE_CONFIGURATION = "SUPPLIER_REFERENCE"
SUPPLIER_REFERENCE_FEATURE = "SupplierStockCrossSection"
SUPPLIER_REFERENCE_DIMENSION = "SupplierStockDia"
SUPPLIER_REFERENCE_DIMENSIONS = {
    SUPPLIER_REFERENCE_FEATURE: {SUPPLIER_REFERENCE_DIMENSION},
}
