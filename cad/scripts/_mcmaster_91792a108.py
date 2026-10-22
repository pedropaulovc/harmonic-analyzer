"""Pure 91792A108 slotted pan-head dimensions; isolate this SKU's cache inputs."""

PART_NO = "91792A108"
IN = 25.4

# McMaster "Stainless Steel Pan Head Slotted Screws" family table, 18-8 rows,
# read live in a headless browser on 2026-10-11 (Rounded Head Screws, 4-40,
# Slotted; the product detail page needs a login): #4-40 x 3/8 in under the
# head, head Ø0.219 in x 0.068 in high, fully threaded, 100,000 psi; family
# facets UNC class 2A, flat tip, ASME B18.6.3. The screw size decimal 0.112 in
# is the #4 basic major.
# (major dia, length, head height, head dia, pitch): the slotted-head
# recipe's size row (diagnostics.diag_mcmaster_fillister.build_fillister).
PAN_HEAD_SIZE = (0.112 * IN, 0.375 * IN, 0.068 * IN, 0.219 * IN, IN / 40.0)

# Actual supplier engineering drawing inspected 2026-10-19. The 3/8 in
# geometry stays exact; supplier decimal spelling is independent metadata.
SUPPLIER_DRAWING_URL = (
    "https://www.mcmaster.com/mvC/Library/CAD2/20260610/3DCADCB9/"
    "91792A108_18-8%20Stainless%20Steel%20Pan%20Head%20Slotted%20ScrewsX.GIF"
)
# Production rotates the screw onto Z: Top sketch Y is model -Z.
SUPPLIER_REFERENCE_SIDES = {"SupplierThreadDiameter": "bottom"}
SUPPLIER_REFERENCE_DIMENSIONS = (
    ("SupplierLength", -PAN_HEAD_SIZE[1], "vertical"),
    ("SupplierHeadHeight", PAN_HEAD_SIZE[2], "vertical"),
    ("SupplierHeadDiameter", PAN_HEAD_SIZE[3], "horizontal"),
    ("SupplierThreadDiameter", PAN_HEAD_SIZE[0], "horizontal"),
)
SUPPLIER_REFERENCE_STARTS = {
    "SupplierHeadDiameter": (-PAN_HEAD_SIZE[3] / 2.0, 0.0),
    "SupplierThreadDiameter": (-PAN_HEAD_SIZE[0] / 2.0, -PAN_HEAD_SIZE[1] / 2.0),
}
SUPPLIER_REFERENCE_PLANES = {
    "SupplierLength": "Top",
    "SupplierHeadHeight": "Top",
    "SupplierThreadDiameter": "Top",
}
SUPPLIER_REFERENCE_FORMATS = {
    "SupplierLength": (3, "length", None, None),
    "SupplierHeadHeight": (3, "length", None, None),
    "SupplierHeadDiameter": (3, "diameter", None, None),
    "SupplierThreadDiameter": (3, "diameter", None, "4-40"),
}
