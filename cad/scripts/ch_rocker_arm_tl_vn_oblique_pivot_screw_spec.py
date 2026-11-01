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
chamfer the end ``CUT_CHAMFER`` x 45 deg, to the thread's minor diameter. The
model is the screw as installed, after that cut and chamfer.
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
# .570 +/-.005, not .57 +/-.01: TL-22's tip clearance (.011 min) holds only
# with the three-place band (pivot block spec, PIVOT_TIP_CLEARANCE_MIN).
CUT_THREAD_PLACES = 3
CUT_CHAMFER = 0.762  # .03 x 45 deg: 5/16-18 major .3125 to minor ~.252
THREAD_LENGTH = CUT_THREAD_LENGTH  # as installed
HEAD_DIA = 14.2748  # .562
HEAD_HEIGHT = 6.35  # .250
HEX = 4.7625  # 3/16
LENGTH = SHOULDER_LENGTH + HEAD_HEIGHT
assert CUT_THREAD_LENGTH < SUPPLIED_THREAD_LENGTH

# The sheet dimensions the screw on its RIGHT view, axis horizontal as it lies
# in the lathe. The diameters and the shoulder length are construction lines
# in a Right-plane sketch, imported there; each line lies on a Right-view
# edge, so it prints under the outline: the shoulder Ø on the shoulder's
# thread-end step (z = 0), the shoulder length on the shoulder's upper
# silhouette, the head Ø on the head's end face (z = LENGTH). Right sketch x is
# model -z, y is model y. The head and thread sizes are stated in SUPPLIER_DATA.
REFERENCE_FEATURE = "SupplierRightReference"
REFERENCE_DIMENSIONS = (
    ("SupplierShoulderDiameter", SHOULDER_DIA, "vertical"),
    ("SupplierShoulderLength", SHOULDER_LENGTH, "horizontal"),
    ("SupplierHeadDiameter", HEAD_DIA, "vertical"),
)
REFERENCE_STARTS = {
    "SupplierShoulderDiameter": (0.0, -SHOULDER_DIA / 2.0),
    "SupplierShoulderLength": (-SHOULDER_LENGTH, SHOULDER_DIA / 2.0),
    "SupplierHeadDiameter": (-LENGTH, -HEAD_DIA / 2.0),
}
REFERENCE_FORMATS = {
    "SupplierShoulderDiameter": (4, "diameter", None, "SHOULDER"),
    "SupplierShoulderLength": (3, "length", None, "SHOULDER LENGTH"),
    "SupplierHeadDiameter": (3, "diameter", None, "HEAD"),
}
REFERENCE_TOLERANCES_MM = {
    "SupplierShoulderDiameter": deviations(SHOULDER_DIA_BAND),
}
# The shop cut: the thread envelope extrusion's own depth, printed plain at
# three places on the Right view (not a parenthesised supplier reference).
CUT_FEATURE = "ThreadEnvelope"
CUT_DIMENSION = "CutThreadLength"
_CHAMFER_IN = f"{CUT_CHAMFER / INCH:.2f}".removeprefix("0")
CUT_CALLOUT = (
    "CUT THREAD FROM SHOULDER\n"
    f"CHAMFER END {_CHAMFER_IN} X 45°\n"
    "TIP STAYS .011 MIN INSIDE TL-22"
)
THREAD_NOTE = f"{THREAD} UNC-2A\n(AS SUPPLIED)"
SUPPLIER_DATA = (
    "HEAD Ø.562 X .250; 3/16 HEX KEY.",
    "5/16-18 UNC-2A, 1.000 THREAD AS SUPPLIED.",
)
