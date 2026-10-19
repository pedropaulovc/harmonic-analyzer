"""Exact 91375A106 geometry and supplier-reference display contract."""

IN = 25.4
MAJOR_DIA = 0.112 * IN
PITCH = IN / 40.0
LENGTH = 0.25 * IN
HEX_AF = 0.050 * IN

# McMaster engineering drawing inspected 2026-10-19 (not catalogue shorthand).
SUPPLIER_DRAWING_URL = (
    "https://www.mcmaster.com/mvC/Library/CAD2/20260925/2DE2B046/"
    "91375A106_Alloy%20Steel%20Cup-Tip%20Set%20ScrewX.GIF"
)
SUPPLIER_REFERENCE_DIMENSIONS = (
    ("SupplierLength", LENGTH, "vertical"),
    ("SupplierThreadDiameter", MAJOR_DIA, "horizontal"),
    ("SupplierDriveWidth", HEX_AF, "horizontal"),
)
SUPPLIER_REFERENCE_STARTS = {
    "SupplierLength": (MAJOR_DIA / 2.0, 0.0),
    "SupplierThreadDiameter": (-MAJOR_DIA / 2.0, 0.0),
    "SupplierDriveWidth": (-HEX_AF / 2.0, 0.0),
}
SUPPLIER_REFERENCE_PLANES = {
    "SupplierThreadDiameter": "Top",
    "SupplierDriveWidth": "Top",
}
SUPPLIER_REFERENCE_FORMATS = {
    "SupplierLength": (2, "length", None, None),
    "SupplierThreadDiameter": (3, "diameter", None, "4-40"),
    "SupplierDriveWidth": (2, "length", None, None),
}
