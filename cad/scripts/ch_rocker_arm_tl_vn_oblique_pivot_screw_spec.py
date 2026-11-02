"""MHA-CH-06-TL-VN-77: purchased oblique-trammel pivot screw.

Source: https://www.huyett.com/blts40-0375-1500188p (Huyett BLTS40-0375-1500188P,
the AMPG STR60138C24-EXT extended-thread precision shoulder screw), read live
2026-10-31; page-stated dimensions only. Special order.
Supplier material is 18-8 stainless, plain. Registry/native AISI 304 is an
engineering CAD-library surrogate only, used for appearance and approximate mass.
Bands are (upper, lower) deviations. The page states no shoulder-length band:
the sheet prints 1.500 as an untoleranced reference, and the stack math uses a
+/-.005 envelope (``SHOULDER_LENGTH_BAND``), not a supplier claim.
Shop modification, the sheet's one shop dimension (as the hub pin's cut): cut the
1.000 supplied thread to ``CUT_THREAD_LENGTH`` from the shoulder face, then
chamfer the end. The model is the screw as installed, after that cut.
Frame: axis +Z; origin at the shoulder end face, +Z toward the head; thread extends -Z.
"""

from __future__ import annotations

import _config
from _fit_deviations import deviations
from _package_units import drawing_unit

PART_NAME = "ch-rocker-arm-tl-vn-oblique-pivot-screw"
UNIT = drawing_unit(
    "parts/ch-rocker-arm-tl-vn-oblique-pivot-screw",
    _config.parts("ch-rocker-arm-tl-vn-oblique-pivot-screw"),
)
INCH = 25.4

SKU = "BLTS40-0375-1500188P"
MANUFACTURER_PART = "AMPG STR60138C24-EXT"
QUANTITY = 2
AXIS_NAME = "PivotAxis"
SHOULDER_DIA = 9.525  # .375
SHOULDER_DIA_BAND = (0.0, -0.0254)  # +0/-.001
SHOULDER_LENGTH = 38.1  # 1.500
SHOULDER_LENGTH_BAND = (0.127, -0.127)  # stack envelope +/-.005; the page states none
THREAD = "5/16-18"
THREAD_DIA = 7.9375  # 5/16 UNC-2A major
THREAD_PITCH = INCH / 18.0
SUPPLIED_THREAD_LENGTH = 25.4  # 1.000 as supplied
CUT_THREAD_LENGTH = 14.478  # .570, the shop cut from the shoulder face
CUT_THREAD_PLACES = 3  # .570 +/-.005 under the title block's .XXX
THREAD_LENGTH = CUT_THREAD_LENGTH  # as installed
HEAD_DIA = 14.2748  # .562
HEAD_HEIGHT = 6.35  # .250
HEX = 4.7625  # 3/16
LENGTH = SHOULDER_LENGTH + HEAD_HEIGHT
assert CUT_THREAD_LENGTH < SUPPLIED_THREAD_LENGTH

# The head and thread sizes are stated in SUPPLIER_DATA, not as more chords on
# the small screw. The banded shoulder prints as stacked limits. Every carrier
# lies on a Top-profile edge, so its construction line prints under the
# outline: the shoulder Ø on the shoulder's thread-end step (z = 0), its
# witnesses rising clear past the narrower 5/16 thread to the top lane; the
# shoulder length on the shoulder's silhouette; the head Ø on the head's end
# face (z = LENGTH), its witnesses dropping to the bottom lane. The head-end
# Front view shows no chord across the head.
SUPPLIER_REFERENCE_DIMENSIONS = (
    ("SupplierShoulderDiameter", SHOULDER_DIA, "horizontal"),
    ("SupplierShoulderLength", SHOULDER_LENGTH, "vertical"),
    ("SupplierHeadDiameter", HEAD_DIA, "horizontal"),
)
SUPPLIER_REFERENCE_STARTS = {
    "SupplierShoulderDiameter": (-SHOULDER_DIA / 2.0, 0.0),
    "SupplierShoulderLength": (SHOULDER_DIA / 2.0, -SHOULDER_LENGTH),
    "SupplierHeadDiameter": (-HEAD_DIA / 2.0, -LENGTH),
}
SUPPLIER_REFERENCE_PLANES = {
    "SupplierShoulderDiameter": "Top", "SupplierShoulderLength": "Top",
    "SupplierHeadDiameter": "Top",
}
SUPPLIER_REFERENCE_FORMATS = {
    "SupplierShoulderDiameter": (4, "diameter", None, "SHOULDER"),
    "SupplierShoulderLength": (3, "length", None, "SHOULDER LENGTH"),
    "SupplierHeadDiameter": (3, "diameter", None, "HEAD"),
}
SUPPLIER_REFERENCE_SIDES = {
    "SupplierShoulderDiameter": "top", "SupplierShoulderLength": "right",
    "SupplierHeadDiameter": "bottom",
}
SUPPLIER_REFERENCE_UNITS = {name: "in" for name, _, _ in SUPPLIER_REFERENCE_DIMENSIONS}
SUPPLIER_REFERENCE_TOLERANCES_MM = {
    "SupplierShoulderDiameter": deviations(SHOULDER_DIA_BAND),
}
# The shop cut: the thread envelope extrusion's own depth, printed plain at
# three places in the Top view (not a parenthesised supplier reference).
CUT_FEATURE = "ThreadEnvelope"
CUT_DIMENSION = "CutThreadLength"
CUT_CALLOUT = "CUT THREAD; CHAMFER END"
SUPPLIER_DATA = (
    "HEAD Ø.562 X .250; 3/16 HEX KEY.",
    "5/16-18 UNC-2A, 1.000 THREAD AS SUPPLIED.",
)
