"""Pure 90114A511 vendor dimensions; keep mechanical specs off recipe closures."""

BF_MAJOR_R = 2.8448 / 2.0
BF_LEN = 6.35
BF_HH = 2.7178
BF_HEAD_R = 4.6482 / 2.0
BF_PITCH = 0.635
BF_SLOT_W = 0.9906  # Slot Width@Sketch1
BF_SLOT_D = 1.2192  # Slot Depth@Sketch1

# Final VN axis -Z; the supplier sizes are identification references only.
# McMaster engineering drawing inspected 2026-10-19.
SUPPLIER_DRAWING_URL = (
    "https://www.mcmaster.com/mvC/Library/CAD2/20260619/A4C749C6/"
    "90114A511_Brass%20Fillister%20Head%20Slotted%20ScrewsX.GIF"
)
SUPPLIER_REFERENCE_DIMENSIONS = (
    ("SupplierLength", -BF_LEN, "vertical"),
    ("SupplierHeadHeight", BF_HH, "vertical"),
    ("SupplierHeadDiameter", 2.0 * BF_HEAD_R, "horizontal"),
    ("SupplierThreadDiameter", 2.0 * BF_MAJOR_R, "horizontal"),
)
SUPPLIER_REFERENCE_STARTS = {
    "SupplierLength": (BF_MAJOR_R, 0.0),
    "SupplierHeadHeight": (-BF_HEAD_R, 0.0),
    "SupplierHeadDiameter": (-BF_HEAD_R, 0.0),
    "SupplierThreadDiameter": (-BF_MAJOR_R, -BF_LEN / 2.0),
}
SUPPLIER_REFERENCE_PLANES = {
    "SupplierLength": "Top",
    "SupplierHeadHeight": "Top",
    "SupplierThreadDiameter": "Top",
}
SUPPLIER_REFERENCE_FORMATS = {
    "SupplierLength": (2, "length", None, None),
    "SupplierHeadHeight": (3, "length", None, None),
    "SupplierHeadDiameter": (3, "diameter", None, None),
    "SupplierThreadDiameter": (3, "diameter", None, "4-40"),
}
