"""Pure 91794A079 fillister dimensions; isolate each SKU's cache inputs."""

# 18-8 stainless #2-56 x 3/8, the same head and thread as the #2-56 family
# (live product page read 2026-11-20, https://www.mcmaster.com/91794A079/:
# 2-56 UNC 2A, fully threaded, flat tip, head 0.14 x 0.083 in, ASME B18.6.3).
# Only the length differs from the 91794A078/91794A080 rows; derived family
# details are not vendor-verified, and no supplier drawing was read.
FILLISTER_SIZE = (2.1844, 9.525, 2.1082, 3.556, 25.4 / 56.0)

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
