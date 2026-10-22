"""Pure McMaster 91375A105 catalogue dimensions for its recipe and assemblies.

McMaster 91375A105 product page read live on 2026-10-13:
https://www.mcmaster.com/91375A105/. Alloy steel cup-tip set screw, black
oxide, 4-40 UNC Class 3A, 3/16 in long, 0.050 in hex drive, Rockwell C45,
ASME B18.3 / ASTM F912. Only a 2-D PDF is offered; no vendor solid was
harvested. It is the 1/4 in long 91375A106 (MHA-CH-VN-53, vendor-verified
replica) cut 1/16 in shorter, so the recipe takes that replica's laws.

Frame of the recipe: axis +Y, origin mid-length; the stock part lifts the
cup end onto y = 0 with the socket face at y = +LENGTH.
"""

from __future__ import annotations

import math

MM_PER_IN = 25.4
ALLOY_STEEL_G_PER_MM3 = 7.7e-3  # SOLIDWORKS "Alloy Steel"

SKU = "91375A105"
THREAD = "#4-40"
MAJOR_DIA = 0.112 * MM_PER_IN  # 2.8448, "Screw Size Decimal Equivalent"
PITCH = MM_PER_IN / 40.0
LENGTH = 3.0 / 16.0 * MM_PER_IN  # 4.7625, cup end to socket face
HEX_AF = 0.050 * MM_PER_IN
# The 91375A106 cup-end law: 45 deg x one pitch down to the cup diameter.
POINT_LENGTH = PITCH
CUP_DIA = MAJOR_DIA - 2.0 * POINT_LENGTH  # 1.5748

# Mass estimate: the 91375A106 vendor solid (25.8601 mm^3 at 1/4 in) less
# 1/16 in of threaded shank at the UN pitch-diameter section.
_PITCH_DIA = MAJOR_DIA - 0.649519 * PITCH
_VOLUME_MM3 = 25.8601 - (0.25 * MM_PER_IN - LENGTH) * math.pi / 4.0 * _PITCH_DIA**2
MASS_G = _VOLUME_MM3 * ALLOY_STEEL_G_PER_MM3

if POINT_LENGTH >= LENGTH:
    raise AssertionError("set-screw point overruns its length")

# Actual supplier engineering drawing inspected 2026-10-19: length 0.188 in,
# drive 0.05 in, major 0.112 in, 4-40. Keep exact 3/16 in model length.
SUPPLIER_DRAWING_URL = (
    "https://www.mcmaster.com/mvC/Library/CAD2/20260925/7C42F185/"
    "91375A105_Alloy%20Steel%20Cup-Tip%20Set%20ScrewX.GIF"
)
SUPPLIER_REFERENCE_SIDES = {}
SUPPLIER_REFERENCE_DIMENSIONS = (
    ("SupplierLength", LENGTH, "vertical"),
    ("SupplierThreadDiameter", MAJOR_DIA, "horizontal"),
    ("SupplierDriveWidth", HEX_AF, "horizontal"),
)
SUPPLIER_REFERENCE_STARTS = {
    "SupplierThreadDiameter": (-MAJOR_DIA / 2.0, LENGTH / 2.0),
    "SupplierDriveWidth": (-HEX_AF / 2.0, 0.0),
}
SUPPLIER_REFERENCE_PLANES = {"SupplierDriveWidth": "Top"}
SUPPLIER_REFERENCE_FORMATS = {
    "SupplierLength": (3, "length", None, None),
    "SupplierThreadDiameter": (3, "diameter", None, "4-40"),
    "SupplierDriveWidth": (2, "length", None, None),
}
