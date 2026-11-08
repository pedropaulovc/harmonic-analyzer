"""MHA-SM-VN-56: purchased gooseneck counter-spring shoulder screw.

Owner ruling 2026-11-08 (Pedro), #2144 item 11.4: option A, McMaster
91259A576, the counter spring's upper eye riding free on its 5/16 shoulder
under a thin washer (MHA-SM-VN-57), the shoulder end seated on the MHA-SM-01
end face and the 1/4-20 thread in that end piece's plain blind tap.  This
supersedes #1951's clamped eye and retires the made MHA-SM-04.

Source: https://www.mcmaster.com/91259A576/, read live 2026-11-08; page-stated
fields only: alloy steel shoulder screw, black oxide, Rockwell C32, ASME
B18.3, standard shoulder fit; shoulder Ø5/16 (-.004 to -.002), shoulder length
3/8 (-.005 to +.005); 1/4-20 UNC, Class 3A, thread length 7/16; head Ø7/16 x
7/32 high, knurled; 5/32 hex drive; $3.65 each.

The page states no thread-neck or under-head forms.  The joint budgets
(``sm_gooseneck_spring_joint``) take them from the ASME B18.3 socket head
shoulder screw table the page cites (5/16 nominal row, as tabulated in
https://www.nutty.com/content/product-pdfs/socket_shoulder_bolt.pdf, read
2026-11-08): thread neck width .100, shoulder (under-head) neck Ø .289 MIN x
.093 MAX wide, head fillet transition Ø .345 MAX, head Ø .419 MIN.

Model: the nominal supplied envelope, datasheet-built (no vendor STEP): the
shoulder, the head and the thread as plain cylinders at the page's sizes; the
hex socket, knurl, necks and chamfers are not invented.  Bands are (upper,
lower) deviations, mm.  Frame: axis +Z; origin at the shoulder end face, +Z
toward the head; the thread extends -Z.

Pure data: no registry read, so the joint module and the native counter-seat
certificate that import it do not re-key on the part's registry row; the
drawing test proves ``UNIT`` against that row's drawing_unit.
"""

from __future__ import annotations

PART_NAME = "sm-vn-gooseneck-shoulder-screw"
UNIT = "in"
INCH = 25.4

SKU = "91259A576"
CATALOG_URL = "https://www.mcmaster.com/91259A576/"
CATALOG_CHECKED_DATE = "2026-11-08"
QUANTITY = 1
AXIS_NAME = "ScrewAxis"

SHOULDER_DIA = 5.0 / 16.0 * INCH  # 5/16 basic
SHOULDER_DIA_BAND = (-0.002 * INCH, -0.004 * INCH)
SHOULDER_LENGTH = 0.375 * INCH  # 3/8
SHOULDER_LENGTH_BAND = (0.005 * INCH, -0.005 * INCH)
THREAD = "1/4-20"
THREAD_SIZE = THREAD  # the receiver's HoleSpec size
THREAD_CLASS = "3A"
MAJOR_DIA = 0.250 * INCH
PITCH = INCH / 20.0
THREAD_LENGTH = 7.0 / 16.0 * INCH  # from the shoulder end face to the tip
HEAD_DIA = 7.0 / 16.0 * INCH
HEAD_HEIGHT = 7.0 / 32.0 * INCH
HEX = 5.0 / 32.0 * INCH
LENGTH = SHOULDER_LENGTH + HEAD_HEIGHT

# ASME B18.3 (5/16 nominal row), the standard the page cites; module docstring.
THREAD_NECK_WIDTH_MAX = 0.100 * INCH
SHOULDER_NECK_DIA_MIN = 0.289 * INCH
SHOULDER_NECK_WIDTH_MAX = 0.093 * INCH
HEAD_FILLET_TRANSITION_DIA_MAX = 0.345 * INCH
HEAD_DIA_MIN = 0.419 * INCH

if not HEAD_DIA > SHOULDER_DIA > MAJOR_DIA:
    raise AssertionError("91259A576 is not stepped head > shoulder > thread")

# The sheet dimensions the screw on its RIGHT view, axis horizontal as it lies
# in the lathe (as MHA-CH-06-TL-VN-77's).  The diameters and the shoulder
# length are construction lines in a Right-plane sketch, each on a Right-view
# edge: the shoulder Ø on the shoulder's thread-end step (z = 0), the shoulder
# length on the shoulder's upper silhouette, the head Ø on the head's end face
# (z = LENGTH).  Right sketch x is model -z, y is model y.  The thread and
# drive are stated in SUPPLIER_DATA.
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
# (places, presentation, denominator, callout below)
REFERENCE_FORMATS = {
    "SupplierShoulderDiameter": (4, "diameter", None, "SHOULDER"),
    "SupplierShoulderLength": (3, "length", None, None),
    "SupplierHeadDiameter": (3, "diameter", None, "HEAD"),
}
THREAD_NOTE = f"{THREAD} UNC-{THREAD_CLASS}\n(AS SUPPLIED)"
SUPPLIER_DATA = (
    "SHOULDER Ø.3085-.3105 X .370-.380; HEAD Ø.438 X .219; 5/32 HEX KEY.",
    "1/4-20 UNC-3A, 7/16 THREAD; ALLOY STEEL, BLACK OXIDE, RC 32.",
)
