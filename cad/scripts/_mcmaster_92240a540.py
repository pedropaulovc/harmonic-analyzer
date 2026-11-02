"""Pure 92240A540 hex-screw dimensions; isolate this SKU's cache inputs."""

# Catalog dimensions, millimetres.  Keep the diameter as a public constant;
# the radius is derived so the catalog law has one source of truth.
MAJOR_DIAMETER_MM = 6.35
LENGTH_MM = 19.05
HEX_WIDTH_MM = 11.1125
HEX_HEIGHT_MM = 3.96875
PITCH_MM = 1.27
WASHER_DEPTH_MM = HEX_WIDTH_MM * 0.025

# Vendor axial placement, expressed in the adapter's model-Y build frame.
UNDERSIDE_MM = 0.0
HEAD_TOP_MM = UNDERSIDE_MM + HEX_HEIGHT_MM

HEX_SCREW_SIZE = (
    MAJOR_DIAMETER_MM,
    LENGTH_MM,
    HEX_WIDTH_MM,
    HEX_HEIGHT_MM,
    PITCH_MM,
    WASHER_DEPTH_MM,
    UNDERSIDE_MM,
)

# Supplier engineering drawing inspected 2026-10-19, not catalogue shorthand.
SUPPLIER_DRAWING_URL = (
    "https://www.mcmaster.com/mvC/Library/CAD2/20260107/676C0839/"
    "92240A540_18-8%20Stainless%20Steel%20Hex%20Head%20Screw%20Made%20Outside%20The%20U.S.X.GIF"
)
SUPPLIER_REFERENCE_SIDES = {"SupplierThreadDiameter": "bottom"}
SUPPLIER_REFERENCE_DIMENSIONS = (
    ("SupplierLength", -LENGTH_MM, "vertical"),
    ("SupplierHeadHeight", HEX_HEIGHT_MM, "vertical"),
    ("SupplierHeadWidth", HEX_WIDTH_MM, "horizontal"),
    ("SupplierThreadDiameter", MAJOR_DIAMETER_MM, "horizontal"),
)
SUPPLIER_REFERENCE_STARTS = {
    "SupplierHeadWidth": (-HEX_WIDTH_MM / 2.0, 0.0),
    "SupplierThreadDiameter": (-MAJOR_DIAMETER_MM / 2.0, -LENGTH_MM / 2.0),
}
SUPPLIER_REFERENCE_PLANES = {"SupplierHeadWidth": "Top"}
# Four-place decimals: 5/32 prints .1563 (half away) and 7/16 .4375 (exact).
# A native inch fraction prints its own inch mark before the " in" suffix.
SUPPLIER_REFERENCE_FORMATS = {
    "SupplierLength": (2, "length", None, None),
    "SupplierHeadHeight": (4, "length", None, None),
    "SupplierHeadWidth": (4, "length", None, None),
    "SupplierThreadDiameter": (2, "diameter", None, '1/4"-20'),
}
