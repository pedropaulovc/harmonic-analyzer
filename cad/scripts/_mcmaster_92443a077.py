"""Pure 92443A077 slotted binding-head dimensions; isolate this SKU's cache inputs.

McMaster "Brass Binding Head Slotted Screws, 2-56 Thread Size, 1/4" Long",
read live from the product page and its 2-D drawing on 2026-11-08: screw size
decimal 0.086 in, 1/4 in under the head, fully threaded, flat tip, UNC class
2A, slotted binding head Ø0.181 in x 0.05 in high, brass, Rockwell B40,
50,000 psi, ASME B18.6.3.  McMaster's no-threads STEP (SHA-256
b199cfaad793fda844fc6b655b831ad9dc959ba0ec486c426e737949263592a8) measures the
head Ø0.1797 x 0.0493 and the shank Ø0.086.  The page states no head band, so
the STEP's head diameter is the least head the clamp stacks read.
"""

PART_NO = "92443A077"
IN = 25.4

THREAD = "#2-56"
MAJOR_DIA = 0.086 * IN
LENGTH = 0.25 * IN
HEAD_H = 0.05 * IN
HEAD_DIA = 0.181 * IN
# The reference STEP's head, under the listed 0.181 (no band is published).
HEAD_DIA_MIN = 0.1797 * IN
PITCH = IN / 56.0

# (major dia, length, head height, head dia, pitch): the slotted-head
# recipe's size row (diagnostics.diag_mcmaster_fillister.build_fillister).
BINDING_HEAD_SIZE = (MAJOR_DIA, LENGTH, HEAD_H, HEAD_DIA, PITCH)

# No SUPPLIER_DRAWING_URL: the 2-D drawing was saved from the product page on
# 2026-11-08 (GIF SHA-256 a56c54cb...8acaab), but its CAD2 address could not
# be read back (cad/references/mcmaster/README.md, 92443A077).
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
# The thread's label reads as the footer's ITEM line does ("2-56" on the
# view, "#2-56" in the ITEM row), as on the 92446A077 sheet.
SUPPLIER_REFERENCE_FORMATS = {
    "SupplierLength": (2, "length", None, None),
    "SupplierHeadHeight": (3, "length", None, None),
    "SupplierHeadDiameter": (3, "diameter", None, None),
    "SupplierThreadDiameter": (3, "diameter", None, THREAD),
}
