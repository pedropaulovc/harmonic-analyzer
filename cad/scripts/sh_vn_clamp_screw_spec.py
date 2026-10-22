"""Pure dimensions for shared McMaster 90280A201 (MHA-SH-VN-53).

MG and PD use the same purchased native part. Mechanical specs, layouts and
assemblies read this SKU's unchanged dimensions without importing CAD.
"""

FILLISTER_SIZE = (4.1656, 31.75, 3.9624, 6.858, 0.79375)

SHANK_DIA, SHANK_LEN, HEAD_H, HEAD_DIA, _PITCH = FILLISTER_SIZE

# Engineering drawing inspected directly; exact replica sizes remain above.
SUPPLIER_DRAWING_URL = (
    "https://www.mcmaster.com/mvC/Library/CAD2/20260612/4E8F8FED/"
    "90280A201_Steel%20Narrow%20Fillister%20Head%20Slotted%20ScrewsX.GIF"
)
# Final frame: head at -Z, shank at +Z. Top sketch Y is model -Z.
SUPPLIER_REFERENCE_DIMENSIONS = (
    ("SupplierLength", -SHANK_LEN, "vertical"),
    ("SupplierHeadHeight", HEAD_H, "vertical"),
    ("SupplierHeadDiameter", HEAD_DIA, "horizontal"),
    ("SupplierThreadDiameter", SHANK_DIA, "horizontal"),
)
SUPPLIER_REFERENCE_STARTS = {
    "SupplierLength": (SHANK_DIA / 2.0, 0.0),
    "SupplierHeadHeight": (-HEAD_DIA / 2.0, 0.0),
    "SupplierHeadDiameter": (-HEAD_DIA / 2.0, 0.0),
    "SupplierThreadDiameter": (-SHANK_DIA / 2.0, -SHANK_LEN / 2.0),
}
SUPPLIER_REFERENCE_PLANES = {
    "SupplierLength": "Top",
    "SupplierHeadHeight": "Top",
    "SupplierThreadDiameter": "Top",
}
SUPPLIER_REFERENCE_SIDES = {"SupplierThreadDiameter": "bottom"}
SUPPLIER_REFERENCE_FORMATS = {
    "SupplierLength": (2, "length", None, None),
    "SupplierHeadHeight": (3, "length", None, None),
    "SupplierHeadDiameter": (2, "diameter", None, None),
    "SupplierThreadDiameter": (3, "diameter", None, "8-32"),
}
