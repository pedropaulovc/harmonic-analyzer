"""Pure drawing/reference metadata, separate from wire mechanism inputs.

The engineering drawing was inspected on 2026-10-19. Its nominal diameter
is printed to four inch decimals; the straight length is representative,
not either finished wire's developed cut length. Keep presentation edits
out of ``_mcmaster_9666k56`` so they do not re-key unrelated mechanisms.
"""

SUPPLIER_DRAWING_URL = (
    "https://www.mcmaster.com/mvC/Library/CAD2/20260111/6A9AB2E8/"
    "9666K56_Lubricated%201080%20Spring%20Steel%20WireX.GIF"
)
SUPPLIER_DIAMETER_PRECISION = 4
SUPPLIER_REFERENCE_CONFIGURATION = "SupplierNominalStock"
SUPPLIER_REFERENCE_FEATURE = "SupplierStockCrossSection"
SUPPLIER_REFERENCE_DIMENSION = "SupplierStockDia"
SUPPLIER_REFERENCE_DIMENSIONS = {
    SUPPLIER_REFERENCE_FEATURE: {SUPPLIER_REFERENCE_DIMENSION},
}
