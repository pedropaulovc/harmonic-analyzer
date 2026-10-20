"""Pure McMaster 99607A213 dimensions shared by recipe and assembly placement.

Separate from the COM recipe and part-save wrapper to limit cache blast radius.
"""

from __future__ import annotations

TS_MAJOR_R = 2.8448 / 2.0
TS_PITCH = 0.635
TS_LEN = 15.875
TS_SH_R = 5.953125 / 2.0
TS_SH_H = 3.175
TS_HEAD_R = 7.540625 / 2.0
TS_HEAD_H = 3.175


HEAD_DIA = 2.0 * TS_HEAD_R
HEAD_H = TS_HEAD_H
HEAD_STACK_LEN = TS_SH_H + TS_HEAD_H
SHANK_DIA = 2.0 * TS_MAJOR_R
SHANK_LEN = TS_LEN
TIP_CHAMFER = TS_PITCH * 0.75

# Supplier engineering drawing inspected 2026-10-19. Its rounded 0.297 in
# and 0.234 in diameters do not replace the exact 19/64 and 15/64 in model.
SUPPLIER_DRAWING_URL = (
    "https://www.mcmaster.com/mvC/Library/CAD2/20260110/B4224D5E/"
    "99607A213_Stainless%20Steel%20Flared-Collar%20Knurled-Head%20Thumb%20ScrewX.GIF"
)
# Production rotates the axis to X and places the head top at X=0.
# Route collar/thread witnesses away from the larger head.
SUPPLIER_REFERENCE_SIDES = {
    "SupplierHeadDiameter": "left",
    "SupplierCollarDiameter": "right",
    "SupplierThreadDiameter": "right",
}
SUPPLIER_REFERENCE_DIMENSIONS = (
    ("SupplierLength", TS_LEN, "horizontal"),
    ("SupplierHeadHeight", TS_HEAD_H, "horizontal"),
    ("SupplierCollarHeight", TS_SH_H, "horizontal"),
    ("SupplierHeadDiameter", HEAD_DIA, "vertical"),
    ("SupplierCollarDiameter", 2.0 * TS_SH_R, "vertical"),
    ("SupplierThreadDiameter", SHANK_DIA, "vertical"),
)
SUPPLIER_REFERENCE_STARTS = {
    "SupplierLength": (HEAD_STACK_LEN, 0.0),
    "SupplierCollarHeight": (TS_HEAD_H, 0.0),
    "SupplierHeadDiameter": (TS_HEAD_H / 2.0, -TS_HEAD_R),
    "SupplierCollarDiameter": (HEAD_STACK_LEN, -TS_SH_R),
    "SupplierThreadDiameter": (HEAD_STACK_LEN + TS_LEN / 2.0, -TS_MAJOR_R),
}
SUPPLIER_REFERENCE_PLANES = {}
SUPPLIER_REFERENCE_FORMATS = {
    "SupplierLength": (3, "length", None, None),
    "SupplierHeadHeight": (3, "length", None, None),
    "SupplierCollarHeight": (3, "length", None, None),
    "SupplierHeadDiameter": (3, "diameter", None, None),
    "SupplierCollarDiameter": (3, "diameter", None, None),
    "SupplierThreadDiameter": (3, "diameter", None, "4-40"),
}
