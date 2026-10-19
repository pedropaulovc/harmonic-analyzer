"""Exact 91375A942 geometry and supplier-reference display contract."""

IN = 25.4
MAJOR_DIA = 0.073 * IN
PITCH = IN / 72.0
LENGTH = 5.0 / 32.0 * IN  # The drawing prints 0.156, not the model value.
HEX_AF = 0.035 * IN

# McMaster engineering drawing inspected 2026-10-19 (not catalogue shorthand).
SUPPLIER_DRAWING_URL = (
    "https://www.mcmaster.com/mvC/Library/CAD2/20260925/B58B1B28/"
    "91375A942_Alloy%20Steel%20Cup-Tip%20Set%20ScrewX.GIF"
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
SUPPLIER_REFERENCE_SIDES = {}
SUPPLIER_REFERENCE_FORMATS = {
    "SupplierLength": (3, "length", None, None),
    "SupplierThreadDiameter": (3, "diameter", None, "1-72"),
    "SupplierDriveWidth": (3, "length", None, None),
}
