"""Pure 91794A055 fillister dimensions; isolate each SKU's cache inputs."""

IN = 25.4

SKU = "91794A055"
THREAD = "#0-80"
THREAD_CLASS = "2A"

# --- catalogue (Sketch1's named driving dimensions agree) -------------------
SHANK_DIA = 0.060 * IN  # "Screw Size Decimal Equivalent@Sketch1" 1.524
SHANK_LEN = 0.25 * IN  # "Length@Sketch1" 6.35, under the head
HEAD_DIA = 0.096 * IN  # "Head Diameter@Sketch1" 2.4384
HEAD_H = 0.055 * IN  # "Head Height@Sketch1" 1.397
PITCH = IN / 80.0  # "Pitch@Sketch1" 0.3175

# 18-8 stainless fillister, 0-80 x 1/4, high narrow head 0.096 x 0.055,
# fully threaded (McMaster 91794A055 product page, read 2026-09-30).
# Sizes only: its vendor model is a different tree (drafted head, neck,
# tip-seeded thread), so diag_build_91794A055 builds it, not
# build_fillister.
FILLISTER_SIZE = (1.524, 6.35, 1.397, 2.4384, 25.4 / 80.0)

# Supplier engineering drawing inspected 2026-10-19. Production is cut at
# assembly, so its 1/4 in stock-length witness is a SEPARATE construction
# line to the left of the installed solid, explicitly labelled as stock.
SUPPLIER_DRAWING_URL = (
    "https://www.mcmaster.com/mvC/Library/CAD2/20260108/1437E659/"
    "91794A055_18-8%20Stainless%20Steel%20Fillister%20Head%20Slotted%20ScrewX.GIF"
)
# Route the thread witness away from the larger head.
SUPPLIER_REFERENCE_SIDES = {"SupplierThreadDiameter": "bottom"}
SUPPLIER_REFERENCE_DIMENSIONS = (
    ("SupplierStockLength", -SHANK_LEN, "vertical"),
    ("SupplierHeadHeight", HEAD_H, "vertical"),
    ("SupplierHeadDiameter", HEAD_DIA, "horizontal"),
    ("SupplierThreadDiameter", SHANK_DIA, "horizontal"),
)
SUPPLIER_REFERENCE_STARTS = {
    "SupplierStockLength": (-HEAD_DIA, 0.0),
    "SupplierHeadDiameter": (-HEAD_DIA / 2.0, 0.0),
    "SupplierThreadDiameter": (-SHANK_DIA / 2.0, -SHANK_LEN / 2.0),
}
SUPPLIER_REFERENCE_PLANES = {"SupplierHeadDiameter": "Top"}
SUPPLIER_REFERENCE_FORMATS = {
    "SupplierStockLength": (2, "length", None, "AS-SUPPLIED STOCK LENGTH"),
    "SupplierHeadHeight": (3, "length", None, None),
    "SupplierHeadDiameter": (3, "diameter", None, None),
    "SupplierThreadDiameter": (2, "diameter", None, "0-80"),
}
