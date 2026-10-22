"""Pure McMaster 90114A124 catalogue dimensions for its recipe and assemblies.

McMaster 90114A124 product table and 2-D drawing read live on 2026-10-09:
https://www.mcmaster.com/90114A124/. The smallest brass fillister in that
series is #2-56, close to M2. Head +Y, shank -Y, bearing plane Y=0.
No vendor solid was harvested; secondary head/thread details use the existing
catalogue-only fillister-family recipe, not a claimed vendor replica.
"""

from __future__ import annotations

SKU = "90114A124"
THREAD = "#2-56"
MAJOR_DIA = 0.086 * 25.4
LENGTH = 0.25 * 25.4
HEAD_H = 0.083 * 25.4
HEAD_DIA = 0.14 * 25.4
PITCH = 25.4 / 56.0

FILLISTER_SIZE = (MAJOR_DIA, LENGTH, HEAD_H, HEAD_DIA, PITCH)

# Actual supplier engineering drawing inspected 2026-10-19.
SUPPLIER_DRAWING_URL = (
    "https://www.mcmaster.com/mvC/Library/CAD2/20260619/961C5808/"
    "90114A124_Brass%20Fillister%20Head%20Slotted%20ScrewsX.GIF"
)
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
SUPPLIER_REFERENCE_PLANES = {"SupplierHeadDiameter": "Top"}
SUPPLIER_REFERENCE_FORMATS = {
    "SupplierLength": (2, "length", None, None),
    "SupplierHeadHeight": (3, "length", None, None),
    "SupplierHeadDiameter": (2, "diameter", None, None),
    "SupplierThreadDiameter": (3, "diameter", None, "2-56"),
}
