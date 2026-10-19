"""Pure 93075A199 catalogue dimensions; keep mechanical specs off recipe closures.

McMaster 93075A199 product page read live on 2026-10-14
(https://www.mcmaster.com/93075A199/): low-strength zinc-plated steel hex
head screw, 8-32 UNC Class 2A, 1 in long (measured from under the head),
fully threaded, flat tip, ASME B18.6.3; head 1/4 in wide, 7/64 in high.  The
head height is the 93075A* vendor-model value (93075A194's 2.794), which the
family laws in ``diagnostics/diag_mcmaster_hex_head.py`` read.
"""

HX_MAJOR_R = 4.1656 / 2.0
HX_LEN = 25.4
HX_HW = 6.35  # across flats
HX_HH = 2.794
HX_PITCH = 0.79375
HX_UNDERSIDE = (HX_LEN - HX_HH) / 2.0  # vendor origin sits mid-overall
HX_TIP_CHAMFER = HX_PITCH * 0.851  # the family's 45 deg x P*0.851 tip chamfer

# Engineering drawing inspected 2026-10-19: AF is fractional; the supplier
# rounds the existing 0.110 in native head height to 0.11 in, not 7/64 in.
SUPPLIER_DRAWING_URL = (
    "https://www.mcmaster.com/mvC/Library/CAD2/20260107/D2669D01/"
    "93075A199_Low-Strength%20Zinc-Plated%20Steel%20Hex%20Head%20ScrewsX.GIF"
)
# Production frame: head +Z, shank -Z, bearing face Z=0.
# Route the thread witness away from the larger head.
SUPPLIER_REFERENCE_SIDES = {"SupplierThreadDiameter": "top"}
SUPPLIER_REFERENCE_DIMENSIONS = (
    ("SupplierLength", HX_LEN, "vertical"),
    ("SupplierHeadHeight", -HX_HH, "vertical"),
    ("SupplierHeadWidth", HX_HW, "horizontal"),
    ("SupplierThreadDiameter", 2.0 * HX_MAJOR_R, "horizontal"),
)
SUPPLIER_REFERENCE_STARTS = {
    "SupplierHeadWidth": (-HX_HW / 2.0, 0.0),
    "SupplierThreadDiameter": (-HX_MAJOR_R, HX_LEN / 2.0),
}
SUPPLIER_REFERENCE_PLANES = {
    "SupplierLength": "Top",
    "SupplierHeadHeight": "Top",
    "SupplierThreadDiameter": "Top",
}
SUPPLIER_REFERENCE_FORMATS = {
    "SupplierLength": (0, "length", None, None),
    "SupplierHeadHeight": (2, "length", None, None),
    "SupplierHeadWidth": (0, "length", 4, None),
    "SupplierThreadDiameter": (3, "diameter", None, "8-32"),
}
