"""Pure 91794A112 fillister dimensions; isolate each SKU's cache inputs."""

# 18-8 stainless fillister, the same 0.183 x 0.107 #4-40 head (McMaster
# 91794A product table, read 2026-09-25).
FILLISTER_SIZE = (2.8448, 15.875, 2.7178, 4.6482, 0.635)

THREAD = "#4-40"
SKU = "91794A112"
SHANK_DIA, SHANK_LEN, HEAD_H, HEAD_DIA, _PITCH = FILLISTER_SIZE

# McMaster engineering drawing inspected 2026-10-19; supplier inches/precision.
SUPPLIER_DRAWING_URL = (
    "https://www.mcmaster.com/mvC/Library/CAD2/20260108/E0CAAC5F/"
    "91794A112_18-8%20Stainless%20Steel%20Fillister%20Head%20Slotted%20ScrewX.GIF"
)
SUPPLIER_REFERENCE_DIMENSIONS = (
    ("SupplierLength", -SHANK_LEN, "vertical"),
    ("SupplierHeadHeight", HEAD_H, "vertical"),
    ("SupplierHeadDiameter", HEAD_DIA, "horizontal"),
    ("SupplierThreadDiameter", SHANK_DIA, "horizontal"),
)
# The shown construction lines print grey over model edges but under dimension
# extension lines of the same width, so each lies under one of this sheet's
# own extension lines (FRONT 1:1; gap ~0.76 mm):
# - the thread chord on the head underside edge (y=0), under the length's
#   upper extension line, which runs left from x=+SHANK_DIA/2;
# - the length on the right crest line, under the thread diameter's right
#   extension line, which runs down from y=0 to the bottom lane.
# Bare: the chord's right ~0.76 mm (inside the head underside edge), the
# length's top ~0.76 mm, and the head height on the head's right silhouette
# (no extension line covers it; above the cylinder band it is beside the dome).
SUPPLIER_REFERENCE_STARTS = {
    "SupplierLength": (SHANK_DIA / 2.0, 0.0),
    "SupplierHeadHeight": (HEAD_DIA / 2.0, 0.0),
    "SupplierHeadDiameter": (-HEAD_DIA / 2.0, 0.0),
    "SupplierThreadDiameter": (-SHANK_DIA / 2.0, 0.0),
}
SUPPLIER_REFERENCE_PLANES = {"SupplierHeadDiameter": "Top"}
SUPPLIER_REFERENCE_SIDES = {
    "SupplierLength": "left",
    "SupplierHeadHeight": "right",
    "SupplierHeadDiameter": "top",
    "SupplierThreadDiameter": "bottom",
}
SUPPLIER_REFERENCE_FORMATS = {
    "SupplierLength": (3, "length", None, None),
    "SupplierHeadHeight": (3, "length", None, None),
    "SupplierHeadDiameter": (3, "diameter", None, None),
    "SupplierThreadDiameter": (3, "diameter", None, "4-40"),
}
