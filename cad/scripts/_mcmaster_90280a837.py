"""Pure 90280A837 fillister dimensions; isolate each SKU's cache inputs."""

THREAD = "#10-32"
THREAD_CLASS = "2A"
SHANK_DIA = 4.826
SHANK_LEN = 44.45
HEAD_DIA = 7.9502
HEAD_H = 4.572
PITCH = 0.79375


FILLISTER_SIZE = (SHANK_DIA, SHANK_LEN, HEAD_H, HEAD_DIA, PITCH)

# McMaster engineering drawing inspected 2026-10-19; supplier inches/precision.
SUPPLIER_DRAWING_URL = (
    "https://www.mcmaster.com/mvC/Library/CAD2/20260612/74B244C7/"
    "90280A837_Steel%20Narrow%20Fillister%20Head%20Slotted%20ScrewsX.GIF"
)
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
    "SupplierLength": (2, "length", None, None),
    "SupplierHeadHeight": (2, "length", None, None),
    "SupplierHeadDiameter": (3, "diameter", None, None),
    "SupplierThreadDiameter": (2, "diameter", None, "10-32"),
}
