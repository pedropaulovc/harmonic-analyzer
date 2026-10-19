"""Pure McMaster 91410A540 dimensions shared by recipe and assembly placement.

Separate from the COM recipe and part-save wrapper to limit cache blast radius.
The live catalogue row (2026-10-12) differs from 91410A538 only in length
(3/4 in): head width 1/4 in, head height 3/16 in, 1/4-20 UNC-2A, cup point.
No vendor model is harvested, so the cup rim and chamfer are 91410A538's
solved values (cad/references/mcmaster/README.md).
"""

from __future__ import annotations

SQ_MAJOR_R = 6.35 / 2.0
SQ_LEN = 19.05  # catalogue length 3/4 in
SQ_HH = 4.7625  # catalogue head height 3/16 in
SQ_PITCH = 1.27
SQ_CUP_RIM_R = 1.739789  # 91410A538 Sketch2 solved rim; 45/59 deg
SQ_CHAMFER_DEG = 75.0  # 91410A538 head chamfer cones (Sketch3 D1/D2)


HEAD_AF = 2.0 * SQ_MAJOR_R  # catalogue head width 1/4 in
HEAD_H = SQ_HH
SHANK_DIA = 2.0 * SQ_MAJOR_R
SHANK_LEN = SQ_LEN

SQUARE_SET_SCREW_SIZE = (
    SQ_MAJOR_R,
    SQ_LEN,
    SQ_HH,
    SQ_PITCH,
    SQ_CUP_RIM_R,
    SQ_CHAMFER_DEG,
)

# McMaster engineering drawing inspected 2026-10-19; head widths/heights
# print fractional inches and the shank sizes decimal inches.
SUPPLIER_DRAWING_URL = (
    "https://www.mcmaster.com/mvC/Library/CAD2/20260108/9342C49D/"
    "91410A540_Steel%20Square-Head%20Cup-Point%20Set%20ScrewX.GIF"
)
SUPPLIER_REFERENCE_DIMENSIONS = (
    ("SupplierLength", -SHANK_LEN, "vertical"),
    ("SupplierHeadHeight", HEAD_H, "vertical"),
    ("SupplierHeadWidth", HEAD_AF, "horizontal"),
    ("SupplierThreadDiameter", SHANK_DIA, "horizontal"),
)
SUPPLIER_REFERENCE_STARTS = {
    "SupplierLength": (SHANK_DIA / 2.0, 0.0),
    "SupplierHeadHeight": (-HEAD_AF / 2.0, 0.0),
    "SupplierHeadWidth": (-HEAD_AF / 2.0, 0.0),
    "SupplierThreadDiameter": (-SHANK_DIA / 2.0, -SHANK_LEN / 2.0),
}
SUPPLIER_REFERENCE_PLANES = {"SupplierHeadWidth": "Top"}
SUPPLIER_REFERENCE_FORMATS = {
    "SupplierLength": (2, "length", None, None),
    "SupplierHeadHeight": (0, "length", 16, None),
    "SupplierHeadWidth": (0, "length", 4, None),
    "SupplierThreadDiameter": (2, "diameter", None, '1/4"-20'),
}
