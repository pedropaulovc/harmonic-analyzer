"""MHA-SM-VN-57: purchased washer under the MHA-SM-VN-56 shoulder screw's head.

Owner ruling 2026-11-08 (Pedro), #2144 item 11.4: a thin washer under the
shoulder screw's head, on its 1/4 shoulder, keeps the counter spring's upper
eye (Ø.374 ID) from passing the Ø3/8 head.  Owner ruling 2026-11-08 (Pedro,
#2144 item 11.4): keep the slotted design; slotted McMaster 91829A566 found
by vendor search, pending owner confirmation, and this washer found for its
shoulder.

Source: https://www.mcmaster.com/93475A250/, read live 2026-11-08; page-stated
fields only: 18-8 stainless steel general purpose washer for M6, DIN 125; ID
6.4 mm, OD 12.0 mm, thickness 1.4 to 1.8 mm; $6.19 per pack of 100.  The page
states no ID or OD tolerance: DIN 125-1 / ISO 7089 (product grade A) gives
M6 ID 6.40-6.62 and OD 11.57-12.00 (the standard's table as listed at
https://www.aspenfasteners.com/m6-din-125-type-a-iso-7089-7090-metric-standard-flat-washers-a4-stainless-steel/,
read 2026-11-08).

Selected on the same date for the window the joint needs: the bore must
pass the Ø.248 MAX shoulder and stay under the head (B18.3 Ø.357 MIN), and
the OD must keep 1.0 of the eye (OD MIN .453) yet stay clear of the counter
spring's leading half-turn (OD MAX about .476).  DIN 125 M6's 11.57-12.00
(.4555-.4724) sits inside that window, its bore over the shoulder; the
98126A907 ring shim first drafted (OD .498 MIN) meets the half-turn.
The fit and retention arithmetic is ``sm_gooseneck_spring_joint``'s.

Model: the nominal supplied annulus, datasheet-built (no vendor STEP).  Bands
are (upper, lower) deviations, mm.  Frame: axis +Z; origin at the bottom
face.  Installed without shop modification.  Pure data (no registry read), as
the screw's spec; the drawing test proves ``UNIT`` against the row.
"""

from __future__ import annotations

PART_NAME = "sm-vn-gooseneck-shoulder-washer"
UNIT = "mm"

SKU = "93475A250"
CATALOG_URL = "https://www.mcmaster.com/93475A250/"
CATALOG_CHECKED_DATE = "2026-11-08"
QUANTITY = 1
AXIS_NAME = "ScrewAxis"

ID = 6.4
ID_BAND = (0.22, 0.0)  # ISO 7089 grade A, M6: 6.40-6.62
OD = 12.0
OD_BAND = (0.0, -0.43)  # ISO 7089 grade A, M6: 11.57-12.00
THICKNESS = 1.6
THICKNESS_BAND = (0.2, -0.2)  # the page's 1.4 to 1.8 mm
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
    "SupplierOuterDiameter": (1, "diameter", None, "OUTSIDE"),
    "SupplierThickness": (1, "length", None, "THICKNESS"),
}
SUPPLIER_REFERENCE_SIDES = {"SupplierOuterDiameter": "bottom", "SupplierThickness": "right"}
SUPPLIER_REFERENCE_UNITS = {"SupplierOuterDiameter": "mm", "SupplierThickness": "mm"}
# The bore is the ring profile's own bore-circle diameter, printed on the
# Front (end) view's visible bore circle: the edge-on Top view shows no bore.
BORE_FEATURE = "RingProfile"
BORE_DIMENSION = "SupplierBoreDiameter"
BORE_FORMAT = (1, "diameter", None, "BORE")
SUPPLIER_DATA = (
    "18-8 STAINLESS FLAT WASHER FOR M6, DIN 125.",
    "ID 6.40-6.62, OD 11.57-12.00, THICKNESS 1.4-1.8 (ISO 7089 GRADE A).",
)
