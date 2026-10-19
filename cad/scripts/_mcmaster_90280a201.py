"""Pure 90280A201 fillister dimensions; isolate each SKU's cache inputs."""

FILLISTER_SIZE = (4.1656, 31.75, 3.9624, 6.858, 0.79375)

# Final VN frame: screw axis -Z, seen lengthwise in Top and end-on in Front.
# McMaster engineering drawing inspected 2026-10-19; exact geometry unchanged.
SUPPLIER_DRAWING_URL = (
    "https://www.mcmaster.com/mvC/Library/CAD2/20260612/4E8F8FED/"
    "90280A201_Steel%20Narrow%20Fillister%20Head%20Slotted%20ScrewsX.GIF"
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
