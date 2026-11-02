"""Pure 90280A203 fillister dimensions; isolate each SKU's cache inputs."""

# Live product page read 2026-10-08: #8-32 x 1-1/2, ASME B18.6.3, fully
# threaded zinc-plated steel, flat tip; length measured under the head.
SHANK_DIA = 4.1656
SHANK_LEN = 38.1
HEAD_DIA = 6.858
HEAD_H = 3.9624
PITCH = 0.79375

# part:        (major dia, length, head height, head dia, pitch)
FILLISTER_SIZE = (SHANK_DIA, SHANK_LEN, HEAD_H, HEAD_DIA, PITCH)

# Actual supplier engineering drawing inspected 2026-10-19.
SUPPLIER_DRAWING_URL = (
    "https://www.mcmaster.com/mvC/Library/CAD2/20260612/379AD1A2/"
    "90280A203_Steel%20Narrow%20Fillister%20Head%20Slotted%20ScrewsX.GIF"
)
SUPPLIER_REFERENCE_SIDES = {"SupplierThreadDiameter": "bottom"}
SUPPLIER_REFERENCE_DIMENSIONS = (
    ("SupplierLength", -SHANK_LEN, "vertical"),
    ("SupplierHeadHeight", HEAD_H, "vertical"),
    ("SupplierHeadDiameter", HEAD_DIA, "horizontal"),
    ("SupplierThreadDiameter", SHANK_DIA, "horizontal"),
)
SUPPLIER_REFERENCE_STARTS = {
    "SupplierHeadDiameter": (-HEAD_DIA / 2.0, 0.0),
    "SupplierThreadDiameter": (-SHANK_DIA / 2.0, -SHANK_LEN / 2.0),
}
SUPPLIER_REFERENCE_PLANES = {"SupplierHeadDiameter": "Top"}
SUPPLIER_REFERENCE_FORMATS = {
    "SupplierLength": (1, "length", None, None),
    "SupplierHeadHeight": (3, "length", None, None),
    "SupplierHeadDiameter": (2, "diameter", None, None),
    "SupplierThreadDiameter": (3, "diameter", None, "#8-32"),
}
