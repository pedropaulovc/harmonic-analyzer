"""Pure 91794A080 fillister dimensions; isolate each SKU's cache inputs."""

# 18-8 stainless #2-56 x 7/16, the same head and thread (live public
# #2-56 fillister family table, read 2026-10-10); catalogue only.
FILLISTER_SIZE = (2.1844, 11.1125, 2.1082, 3.556, 25.4 / 56.0)

# McMaster engineering drawing inspected 2026-10-19. The model remains 7/16 in;
# its supplier display rounds only the native reference to 0.438 in.
SUPPLIER_DRAWING_URL = (
    "https://www.mcmaster.com/mvC/Library/CAD2/20260108/FAEE6E4F/"
    "91794A080_18-8%20Stainless%20Steel%20Fillister%20Head%20Slotted%20ScrewX.GIF"
)
SUPPLIER_REFERENCE_DIMENSIONS = (
    ("SupplierLength", -FILLISTER_SIZE[1], "vertical"),
    ("SupplierHeadHeight", FILLISTER_SIZE[2], "vertical"),
    ("SupplierHeadDiameter", FILLISTER_SIZE[3], "horizontal"),
    ("SupplierThreadDiameter", FILLISTER_SIZE[0], "horizontal"),
)
SUPPLIER_REFERENCE_STARTS = {
    "SupplierLength": (FILLISTER_SIZE[0] / 2.0, 0.0),
    "SupplierHeadHeight": (-FILLISTER_SIZE[3] / 2.0, 0.0),
    "SupplierHeadDiameter": (-FILLISTER_SIZE[3] / 2.0, 0.0),
    "SupplierThreadDiameter": (-FILLISTER_SIZE[0] / 2.0, -FILLISTER_SIZE[1] / 2.0),
}
SUPPLIER_REFERENCE_PLANES = {"SupplierHeadDiameter": "Top"}
SUPPLIER_REFERENCE_FORMATS = {
    "SupplierLength": (3, "length", None, None),
    "SupplierHeadHeight": (3, "length", None, None),
    "SupplierHeadDiameter": (2, "diameter", None, None),
    "SupplierThreadDiameter": (3, "diameter", None, "2-56"),
}
