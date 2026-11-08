"""MHA-SM-VN-57: purchased washer under the MHA-SM-VN-56 shoulder screw's head.

Owner ruling 2026-11-08 (Pedro), #2144 item 11.4: a thin washer under the
91259A576 head, on its 5/16 shoulder, keeps the counter spring's upper eye
(Ø.374 ID) from passing the Ø7/16 head.

Source: https://www.mcmaster.com/98126A907/, read live 2026-11-08; page-stated
fields only: 18-8 stainless steel ring shim, ASTM A240, round, for round
shafts, unpassivated, Rockwell B70 min; ID 5/16 (0 to +.011), OD 1/2
(-.002 to +.002), thickness .030 (-.002 to +.002); $8.48 per pack of 10.

Selected on the same date over the same 5/16 x 1/2 family's 99040A616 (.016,
OD +/-.005, so .505 MAX over the end piece's Ø.50) and 98126A906 (.020): the
.030 ring is the stiffest of the thin rows with the tighter OD band; and over
94773A686/94773A743 (shoulder-screw shims, OD 7/16), whose .432 MIN OD keeps
only .74 of the eye.  The fit and retention arithmetic is
``sm_gooseneck_spring_joint``'s.

Model: the nominal supplied annulus, datasheet-built (no vendor STEP).  Bands
are (upper, lower) deviations, mm.  Frame: axis +Z; origin at the bottom
face.  Installed without shop modification.  Pure data (no registry read), as
the screw's spec; the drawing test proves ``UNIT`` against the row.
"""

from __future__ import annotations

PART_NAME = "sm-vn-gooseneck-shoulder-washer"
UNIT = "in"
INCH = 25.4

SKU = "98126A907"
CATALOG_URL = "https://www.mcmaster.com/98126A907/"
CATALOG_CHECKED_DATE = "2026-11-08"
QUANTITY = 1
AXIS_NAME = "ScrewAxis"

ID = 5.0 / 16.0 * INCH
ID_BAND = (0.011 * INCH, 0.0)
OD = 0.500 * INCH
OD_BAND = (0.002 * INCH, -0.002 * INCH)
THICKNESS = 0.030 * INCH
THICKNESS_BAND = (0.002 * INCH, -0.002 * INCH)
LENGTH = THICKNESS

ID_MIN = ID + ID_BAND[1]
ID_MAX = ID + ID_BAND[0]
OD_MIN = OD + OD_BAND[1]
OD_MAX = OD + OD_BAND[0]
THICKNESS_MIN = THICKNESS + THICKNESS_BAND[1]
THICKNESS_MAX = THICKNESS + THICKNESS_BAND[0]

# The OD and thickness carriers lie on Top-view edges, so their construction
# lines print under the outline: the OD on the z = THICKNESS face (the view's
# lower edge), the thickness on the OD silhouette (as MHA-CH-06-TL-VN-79's).
SUPPLIER_REFERENCE_DIMENSIONS = (
    ("SupplierOuterDiameter", OD, "horizontal"),
    ("SupplierThickness", THICKNESS, "vertical"),
)
SUPPLIER_REFERENCE_STARTS = {
    "SupplierOuterDiameter": (-OD / 2.0, -THICKNESS),
    "SupplierThickness": (OD / 2.0, -THICKNESS),
}
SUPPLIER_REFERENCE_PLANES = {"SupplierOuterDiameter": "Top", "SupplierThickness": "Top"}
# Supplier sizes print as untoleranced REF; the catalogue band governs.
SUPPLIER_REFERENCE_FORMATS = {
    "SupplierOuterDiameter": (3, "diameter", None, "OUTSIDE"),
    "SupplierThickness": (3, "length", None, "THICKNESS"),
}
SUPPLIER_REFERENCE_SIDES = {"SupplierOuterDiameter": "bottom", "SupplierThickness": "right"}
SUPPLIER_REFERENCE_UNITS = {"SupplierOuterDiameter": "in", "SupplierThickness": "in"}
# The bore is the ring profile's own bore-circle diameter, printed on the
# Front (end) view's visible bore circle: the edge-on Top view shows no bore.
BORE_FEATURE = "RingProfile"
BORE_DIMENSION = "SupplierBoreDiameter"
BORE_FORMAT = (3, "diameter", None, "BORE")
SUPPLIER_DATA = (
    "18-8 STAINLESS RING SHIM, ASTM A240.",
    "ID .3125-.3235, OD .498-.502, THICKNESS .028-.032.",
)
