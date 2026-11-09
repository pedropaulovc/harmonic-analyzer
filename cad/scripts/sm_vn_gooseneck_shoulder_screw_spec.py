"""MHA-SM-VN-56: purchased gooseneck counter-spring shoulder screw.

Owner ruling 2026-11-08 (Pedro), #2144 item 11.4: option A, a purchased
shoulder screw, the counter spring's upper eye riding free on its shoulder
under a thin washer (MHA-SM-VN-57), the shoulder end seated on the MHA-SM-01
end face and the thread in that end piece's plain blind tap.  This supersedes
#1951's clamped eye and retires the made MHA-SM-04.  The ruling named
91259A576 (5/16 shoulder); its Ø7.94 shoulder drops the arm 0.79 mm against
the plumb spring and the leading half-turn then meets the tube.  SKU
91259A535 (1/4 shoulder, the retired screw's Ø6.35 support) was
auto-selected after the owner's ask timed out, pending owner confirmation.

Source: https://www.mcmaster.com/91259A535/, read live 2026-11-08; page-stated
fields only: alloy steel shoulder screw, black oxide, Rockwell C32, ASME
B18.3, standard shoulder fit; shoulder Ø1/4 (-.004 to -.002), shoulder length
3/8 (-.005 to +.005); 10-24 UNC, Class 3A, thread length 3/8; head Ø3/8 x
3/16 high, knurled; 1/8 hex drive; $3.48 each.

The page states no thread-neck or under-head forms.  The joint budgets
(``sm_gooseneck_spring_joint``) take them from the ASME B18.3 socket head
shoulder screw table the page cites (1/4 nominal row, as tabulated in
https://www.nutty.com/content/product-pdfs/socket_shoulder_bolt.pdf, read
2026-11-08): thread neck width .083, shoulder (under-head) neck Ø .227 MIN x
.093 MAX wide, head fillet transition Ø .276 MAX, head Ø .357 MIN.

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

SKU = "91259A535"
CATALOG_URL = "https://www.mcmaster.com/91259A535/"
CATALOG_CHECKED_DATE = "2026-11-08"
QUANTITY = 1
AXIS_NAME = "ScrewAxis"

SHOULDER_DIA = 0.250 * INCH  # 1/4 basic
SHOULDER_DIA_BAND = (-0.002 * INCH, -0.004 * INCH)
SHOULDER_LENGTH = 0.375 * INCH  # 3/8
SHOULDER_LENGTH_BAND = (0.005 * INCH, -0.005 * INCH)
THREAD = "#10-24"  # the _hole_spec key; the page and sheets print 10-24
THREAD_SIZE = THREAD  # the receiver's HoleSpec size
THREAD_CLASS = "3A"
MAJOR_DIA = 0.190 * INCH
PITCH = INCH / 24.0
THREAD_LENGTH = 0.375 * INCH  # 3/8, from the shoulder end face to the tip
HEAD_DIA = 0.375 * INCH  # 3/8
HEAD_HEIGHT = 3.0 / 16.0 * INCH
HEX = 0.125 * INCH  # 1/8
LENGTH = SHOULDER_LENGTH + HEAD_HEIGHT

# ASME B18.3 (1/4 nominal row), the standard the page cites; module docstring.
THREAD_NECK_WIDTH_MAX = 0.083 * INCH
SHOULDER_NECK_DIA_MIN = 0.227 * INCH
SHOULDER_NECK_WIDTH_MAX = 0.093 * INCH
HEAD_FILLET_TRANSITION_DIA_MAX = 0.276 * INCH
HEAD_DIA_MIN = 0.357 * INCH

if not HEAD_DIA > SHOULDER_DIA > MAJOR_DIA:
    raise AssertionError("91259A535 is not stepped head > shoulder > thread")

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
THREAD_NOTE = f"{THREAD.lstrip('#')} UNC-{THREAD_CLASS}\n(AS SUPPLIED)"
SUPPLIER_DATA = (
    "SHOULDER Ø.2460-.2480 X .370-.380; HEAD Ø.375 X .188; 1/8 HEX KEY.",
    "10-24 UNC-3A, 3/8 THREAD; ALLOY STEEL, BLACK OXIDE, RC 32.",
)
