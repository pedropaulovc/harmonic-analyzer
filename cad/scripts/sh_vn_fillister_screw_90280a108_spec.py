"""Pure dimensions for shared McMaster 90280A108 (MHA-SH-VN-52)."""

# part:        (major dia, length, head height, head dia, pitch)
FILLISTER_SIZE = (2.8448, 9.525, 2.7178, 4.6482, 0.635)

THREAD = "#4-40"
SHANK_DIA, SHANK_LEN, HEAD_H, HEAD_DIA, THREAD_PITCH = FILLISTER_SIZE
HEAD_T = HEAD_H

SUPPLIER_DRAWING_URL = (
    "https://www.mcmaster.com/mvC/Library/CAD2/20260612/BCD32C7D/"
    "90280A108_Steel%20Narrow%20Fillister%20Head%20Slotted%20ScrewsX.GIF"
)
# Unshifted stock frame: under-head junction Y=0, head +Y, shank -Y.
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
SUPPLIER_REFERENCE_PLANES = {"SupplierHeadDiameter": "Top"}
SUPPLIER_REFERENCE_SIDES = {"SupplierThreadDiameter": "bottom"}
SUPPLIER_REFERENCE_FORMATS = {
    "SupplierLength": (3, "length", None, None),
    "SupplierHeadHeight": (3, "length", None, None),
    "SupplierHeadDiameter": (3, "diameter", None, None),
    "SupplierThreadDiameter": (3, "diameter", None, "4-40"),
}
