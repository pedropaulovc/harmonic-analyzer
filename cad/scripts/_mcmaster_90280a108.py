"""Pure 90280A108 fillister dimensions; isolate each SKU's cache inputs."""

# part:        (major dia, length, head height, head dia, pitch)
FILLISTER_SIZE = (2.8448, 9.525, 2.7178, 4.6482, 0.635)

# McMaster engineering drawing inspected 2026-10-19; supplier inches/precision.
SUPPLIER_DRAWING_URL = (
    "https://www.mcmaster.com/mvC/Library/CAD2/20260612/BCD32C7D/"
    "90280A108_Steel%20Narrow%20Fillister%20Head%20Slotted%20ScrewsX.GIF"
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
SUPPLIER_REFERENCE_SIDES = {"SupplierThreadDiameter": "bottom"}
SUPPLIER_REFERENCE_FORMATS = {
    "SupplierLength": (3, "length", None, None),
    "SupplierHeadHeight": (3, "length", None, None),
    "SupplierHeadDiameter": (3, "diameter", None, None),
    "SupplierThreadDiameter": (3, "diameter", None, "4-40"),
}
