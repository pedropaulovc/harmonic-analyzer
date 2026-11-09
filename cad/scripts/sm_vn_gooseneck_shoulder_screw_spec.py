"""MHA-SM-VN-56: purchased gooseneck counter-spring shoulder screw.

Owner ruling 2026-11-08 (Pedro), #2144 item 11.4: option A, a purchased
shoulder screw, the counter spring's upper eye riding free on its shoulder
under a thin washer (MHA-SM-VN-57), the shoulder end seated on the MHA-SM-01
end face and the thread in that end piece's plain blind tap.  This supersedes
#1951's clamped eye and retires the made MHA-SM-04.  The ruling named
91259A576 (5/16 shoulder); its Ø7.94 shoulder drops the arm 0.79 mm against
the plumb spring and the leading half-turn then meets the tube, so the 1/4
shoulder keeps the retired screw's Ø6.35 support.  Owner ruling 2026-11-08
(Pedro, #2144 item 11.4): keep the slotted design; slotted McMaster 91829A566
found by vendor search, pending owner confirmation (it replaces the socket
91259A535 drafted before that direction).

Source: https://www.mcmaster.com/91829A566/, read live 2026-11-08; page-stated
fields only: slotted 18-8 stainless steel precision shoulder screw,
passivated, smooth head, tensile strength 70,000 psi, Rockwell B55, shear
not rated; precise shoulder fit, shoulder Ø1/4 (-.001 to 0), shoulder length
3/8 (0 to +.002); 10-24 UNC, Class 2A, thread length 3/8; head Ø3/8 x 3/16
high; $4.22 each (1-4).  The page cites no standard.

Its 2-D drawing (the page's CAD2 ...ScrewX.GIF, read 2026-11-08) dimensions
only those sizes; it shows a thread undercut and no under-head neck or
fillet.  The slot and the thread's full-thread start come from the same
family's harvested vendor model (``_mcmaster_91829a560``: identical 3/8 x
3/16 head and 10-24 thread; slot .060 wide x .075 deep, undercut span
2.3368), which the 2-D drawing scaled to its .375 head confirms (slot about
.060 x .075, undercut about .05 wide to Ø.132).  The under-head neck, fillet
and least head Ø the drawing does not state are charged at ASME B18.3's 1/4
row as a conservative allowance (as tabulated in
https://www.nutty.com/content/product-pdfs/socket_shoulder_bolt.pdf, read
2026-11-08): shoulder neck Ø .227 MIN x .093 MAX wide, head fillet
transition Ø .276 MAX, head Ø .357 MIN.

Model: the nominal supplied envelope, datasheet-built (no vendor STEP): the
shoulder, the head and the thread as plain cylinders at the page's sizes and
the straight driver slot across the head; the undercut and chamfers are not
invented.  Bands are (upper, lower) deviations, mm.  Frame: axis +Z; origin
at the shoulder end face, +Z toward the head; the thread extends -Z.

Pure data: no registry read, so the joint module and the native counter-seat
certificate that import it do not re-key on the part's registry row; the
drawing test proves ``UNIT`` against that row's drawing_unit.
"""

from __future__ import annotations

PART_NAME = "sm-vn-gooseneck-shoulder-screw"
UNIT = "in"
INCH = 25.4

SKU = "91829A566"
CATALOG_URL = "https://www.mcmaster.com/91829A566/"
CATALOG_CHECKED_DATE = "2026-11-08"
QUANTITY = 1
AXIS_NAME = "ScrewAxis"

SHOULDER_DIA = 0.250 * INCH  # 1/4 basic
SHOULDER_DIA_BAND = (0.0, -0.001 * INCH)
SHOULDER_LENGTH = 0.375 * INCH  # 3/8
SHOULDER_LENGTH_BAND = (0.002 * INCH, 0.0)
THREAD = "#10-24"  # the _hole_spec key; the page and sheets print 10-24
THREAD_SIZE = THREAD  # the receiver's HoleSpec size
THREAD_CLASS = "2A"
MAJOR_DIA = 0.190 * INCH
PITCH = INCH / 24.0
THREAD_LENGTH = 0.375 * INCH  # 3/8, from the shoulder end face to the tip
HEAD_DIA = 0.375 * INCH  # 3/8
HEAD_HEIGHT = 3.0 / 16.0 * INCH
LENGTH = SHOULDER_LENGTH + HEAD_HEIGHT
# The page's strength rating: 18-8, passivated, Rockwell B55.
TENSILE_STRENGTH_MPA = 70_000.0 * 0.00689476

# The straight driver slot across the head (module docstring: the family's
# harvested vendor model, 2-D drawing cross-check).
SLOT_WIDTH = 1.524  # .060
SLOT_DEPTH = 1.905  # .075

# The thread's full form starts past the vendor undercut (module docstring);
# its relief land Ø is the thread's least section next to the shoulder.
THREAD_NECK_WIDTH_MAX = 2.3368
THREAD_NECK_DIA_MIN = 3.3528
# ASME B18.3 1/4 row, a conservative allowance (module docstring).
SHOULDER_NECK_DIA_MIN = 0.227 * INCH
SHOULDER_NECK_WIDTH_MAX = 0.093 * INCH
HEAD_FILLET_TRANSITION_DIA_MAX = 0.276 * INCH
HEAD_DIA_MIN = 0.357 * INCH

if not HEAD_DIA > SHOULDER_DIA > MAJOR_DIA:
    raise AssertionError("91829A566 is not stepped head > shoulder > thread")
if not SLOT_DEPTH < HEAD_HEIGHT:
    raise AssertionError("91829A566 slot runs through its head")

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
    "SHOULDER Ø.2490-.2500 X .375-.377; HEAD Ø.375 X .188; SLOTTED.",
    "10-24 UNC-2A, 3/8 THREAD; 18-8 STAINLESS, PASSIVATED, 70 KSI.",
)
