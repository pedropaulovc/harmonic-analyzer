"""Pure 91794A078 fillister dimensions; isolate each SKU's cache inputs."""

# 18-8 stainless #2-56 x 5/16, the same head and thread as the #2-56 family
# (live product page read 2026-10-16: head 0.14 x 0.083 in, fully threaded).
# Derived family details are not vendor-verified.
FILLISTER_SIZE = (2.1844, 7.9375, 2.1082, 3.556, 25.4 / 56.0)

# Supplier engineering drawing inspected 2026-10-19. Exact 5/16 in stays
# 7.9375 mm even though the drawing spells its length 0.313 in.
SUPPLIER_DRAWING_URL = (
    "https://www.mcmaster.com/mvC/Library/CAD2/20260108/67729C16/"
    "91794A078_18-8%20Stainless%20Steel%20Fillister%20Head%20Slotted%20ScrewX.GIF"
)
# Route the thread witness away from the larger head.
SUPPLIER_REFERENCE_SIDES = {"SupplierThreadDiameter": "bottom"}
SUPPLIER_REFERENCE_DIMENSIONS = (
    ("SupplierLength", -FILLISTER_SIZE[1], "vertical"),
    ("SupplierHeadHeight", FILLISTER_SIZE[2], "vertical"),
    ("SupplierHeadDiameter", FILLISTER_SIZE[3], "horizontal"),
    ("SupplierThreadDiameter", FILLISTER_SIZE[0], "horizontal"),
)
SUPPLIER_REFERENCE_STARTS = {
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
