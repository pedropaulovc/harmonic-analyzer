"""Pure 93585A190 vendor dimensions; keep mechanical specs off recipe closures."""

import math

# --- Sketch1 driving dimensions (mm) -----------------------------------------
MAJOR_R = 3.175  # Thread Size 6.35 / 2
PITCH = 1.27
LENGTH = 19.05  # stud under the head
HEAD_R = 7.9375  # Head Diameter 15.875 / 2, over the knurl crests
HEAD_H = 12.7
RIM_CHAMFER = 0.79375  # Sketch37 45-deg rim triangle leg

# --- vendor equations ---------------------------------------------------------
TIP_CHAMFER = PITCH * 0.75  # D1@Chamfer2
CORE_R = HEAD_R * 0.98  # D1@Sketch21 = HD * .98
BAND_H = HEAD_H * 0.05  # D4@Sketch1 = HH * .05 (bands, Chamfer3/4)
KNURL_COUNT = 131  # D1@CirPattern1 = HD[in] * 3.14 / .015
KNURL_CREST_W = 0.127  # D3@Sketch26
KNURL_FLANK_DEG = 20.0  # D1@Sketch26 = D2@Sketch26
RUNOUT_DEPTH = 2.54  # Boss-Extrude7 dir1
RUNOUT_DRAFT_DEG = 45.0

H_SHARP = PITCH * math.sqrt(3.0) / 2.0
ROOT_R = MAJOR_R - 0.75 * H_SHARP  # 2.350111

# McMaster engineering drawing inspected 2026-10-19; sizes over knurl crests.
SUPPLIER_DRAWING_URL = (
    "https://www.mcmaster.com/mvC/Library/CAD2/20260702/07425126/"
    "93585A190_Stainless%20Steel%20High-Profile%20Knurled-Head%20Thumb%20ScrewX.GIF"
)
SUPPLIER_REFERENCE_DIMENSIONS = (
    ("SupplierLength", -LENGTH, "vertical"),
    ("SupplierHeadHeight", HEAD_H, "vertical"),
    ("SupplierHeadDiameter", 2.0 * HEAD_R, "horizontal"),
    ("SupplierThreadDiameter", 2.0 * MAJOR_R, "horizontal"),
)
SUPPLIER_REFERENCE_STARTS = {
    "SupplierLength": (MAJOR_R, 0.0),
    "SupplierHeadHeight": (-HEAD_R, 0.0),
    "SupplierHeadDiameter": (-HEAD_R, 0.0),
    "SupplierThreadDiameter": (-MAJOR_R, -LENGTH / 2.0),
}
SUPPLIER_REFERENCE_PLANES = {"SupplierHeadDiameter": "Top"}
SUPPLIER_REFERENCE_SIDES = {"SupplierThreadDiameter": "bottom"}
SUPPLIER_REFERENCE_FORMATS = {
    "SupplierLength": (2, "length", None, None),
    "SupplierHeadHeight": (1, "length", None, None),
    "SupplierHeadDiameter": (3, "diameter", None, None),
    "SupplierThreadDiameter": (2, "diameter", None, '1/4"-20'),
}
