"""Pure 92446A077 slotted pan-head dimensions; isolate this SKU's cache inputs.

McMaster "Brass Pan Head Slotted Screws, 2-56 Thread Size, 1/4" Long", read
live from the product page and its technical drawing on 2026-10-15: screw size
decimal 0.086 in, 1/4 in under the head, fully threaded, flat tip, UNC class
2A, slotted pan head Ø0.167 in x 0.053 in high, brass, Rockwell B40, 50,000
psi, ASME B18.6.3.  The page states no head band; Olander's 2C25SPMBP
(cross-referenced to 92446A077, read 2026-10-15) gives the B18.6.3 head
diameter band, Ø0.167 in max, 0.155 in min.
"""

PART_NO = "92446A077"
IN = 25.4

THREAD = "#2-56"
MAJOR_DIA = 0.086 * IN
LENGTH = 0.25 * IN
HEAD_H = 0.053 * IN
HEAD_DIA = 0.167 * IN
# ASME B18.6.3 #2 slotted pan head table, head diameter min (Olander
# 2C25SPMBP, cross-referenced to 92446A077, read 2026-10-15).
HEAD_DIA_MIN = 0.155 * IN
PITCH = IN / 56.0

# (major dia, length, head height, head dia, pitch): the slotted-head
# recipe's size row (diagnostics.diag_mcmaster_fillister.build_fillister).
PAN_HEAD_SIZE = (MAJOR_DIA, LENGTH, HEAD_H, HEAD_DIA, PITCH)

# Actual supplier engineering drawing inspected 2026-10-19.
SUPPLIER_DRAWING_URL = (
    "https://www.mcmaster.com/mvC/Library/CAD2/20260610/72386355/"
    "92446A077_Brass%20Pan%20Head%20Slotted%20ScrewsX.GIF"
)
# Production axis is Z, head -Z: Top sketch Y is model -Z.
SUPPLIER_REFERENCE_SIDES = {"SupplierThreadDiameter": "bottom"}
SUPPLIER_REFERENCE_DIMENSIONS = (
    ("SupplierLength", -LENGTH, "vertical"),
    ("SupplierHeadHeight", HEAD_H, "vertical"),
    ("SupplierHeadDiameter", HEAD_DIA, "horizontal"),
    ("SupplierThreadDiameter", MAJOR_DIA, "horizontal"),
)
SUPPLIER_REFERENCE_STARTS = {
    "SupplierHeadDiameter": (-HEAD_DIA / 2.0, 0.0),
    "SupplierThreadDiameter": (-MAJOR_DIA / 2.0, -LENGTH / 2.0),
}
SUPPLIER_REFERENCE_PLANES = {
    "SupplierLength": "Top",
    "SupplierHeadHeight": "Top",
    "SupplierThreadDiameter": "Top",
}
# The thread's label reads as the footer's ITEM line does (machinist review
# round 2: "2-56" on the view, "#2-56" in the ITEM row).
SUPPLIER_REFERENCE_FORMATS = {
    "SupplierLength": (2, "length", None, None),
    "SupplierHeadHeight": (3, "length", None, None),
    "SupplierHeadDiameter": (3, "diameter", None, None),
    "SupplierThreadDiameter": (3, "diameter", None, THREAD),
}
