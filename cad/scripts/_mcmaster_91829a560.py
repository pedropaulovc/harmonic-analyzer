"""Pure 91829A560 vendor dimensions; keep mechanical specs off recipe closures."""

import math

# --- vendor dims (all mm/deg, straight from the harvest) -------------------
HEAD_DIA = 9.525  # Head Diameter@Sketch1
HEAD_T = 4.7625  # Head Height@Sketch1
SHOULDER_DIA = 6.35  # Shoulder Diameter@Sketch1
SHOULDER_LEN = 6.35  # Shoulder Length@Sketch1
THREAD_MAJOR = 4.826  # Screw Size Decimal Equivalent@Sketch1
THREAD_LEN = 9.525  # Thread Length@Sketch1
UNDERHEAD_LEN = SHOULDER_LEN + THREAD_LEN  # 15.875
SLOT_W = 1.524  # D1@Sketch8
SLOT_D = 1.905  # D1@Cut-Extrude2
HEAD_CHAMFER = 0.309563  # D1@Chamfer1 (45 deg)
TIP_CHAMFER = 0.43434  # D1@Chamfer2 (45 deg)
UC_LAND_DIA = 3.3528  # CADA@Sketch5 (diametric)
UC_W = 1.6002  # CADB@Sketch5 (fillet + land; also the split-plane offset)
PITCH = 1.058333  # Pitch@Helix/Spiral2 (#10-24: 25.4/24)
REVS = 9.0  # 9000@Helix/Spiral2

# Undercut (vendor Sketch5): R-UC_FILLET quarter-round upper boundary tangent
# to the land, then the land, then the 45-deg lower flank up to the major.
UC_LAND_R = UC_LAND_DIA / 2.0  # 1.6764
UC_FILLET = THREAD_MAJOR / 2.0 - UC_LAND_R  # 0.7366 (fillet R == flank rise)
UC_LAND = UC_W - UC_FILLET  # 0.8636
UC_SPAN = UC_LAND + 2.0 * UC_FILLET  # 2.3368 (junction -> flank@major)

# Thread cutter (vendor Sketch10): UN form.  H is the sharp-V height; the
# groove is the V truncated to a P/8 flat at the root and capped at a 15P/16
# top width (the vendor's D1 = P dims the CONSTRUCTION sharp-V only).
H_SHARP = PITCH * math.sqrt(3.0) / 2.0
ROOT_R = THREAD_MAJOR / 2.0 - 0.75 * H_SHARP  # 1.725585 (vendor: 1.7256)
ROOT_FLAT = PITCH / 8.0  # 0.132292 == vendor D2@Sketch10
CUT_TOP_W = 15.0 * PITCH / 16.0  # 0.992187 (vendor: 0.9922)
CUT_TOP_R = ROOT_R + (CUT_TOP_W - ROOT_FLAT) / 2.0 * math.sqrt(3.0)  # 2.470292
CUT_CENTRE_Y = -UNDERHEAD_LEN - 7.0 * PITCH / 16.0  # -16.338 (vendor, in air)

# McMaster engineering drawing inspected 2026-10-19. Exact 3/16-in head
# height remains 4.7625 mm; only its supplier display rounds to 0.188 in.
SUPPLIER_DRAWING_URL = (
    "https://www.mcmaster.com/mvC/Library/CAD2/20260602/EA381BF9/"
    "91829A560_Slotted%2018-8%20Stainless%20Steel%20Precision%20Shoulder%20ScrewX.GIF"
)
SUPPLIER_REFERENCE_DIMENSIONS = (
    ("SupplierHeadHeight", HEAD_T, "vertical"),
    ("SupplierHeadDiameter", HEAD_DIA, "horizontal"),
    ("SupplierShoulderLength", -SHOULDER_LEN, "vertical"),
    ("SupplierShoulderDiameter", SHOULDER_DIA, "horizontal"),
    ("SupplierThreadLength", -THREAD_LEN, "vertical"),
    ("SupplierThreadDiameter", THREAD_MAJOR, "horizontal"),
)
# The shown construction lines print grey OVER model edges but UNDER dimension
# extension lines of the same width (FRONT 1:1, run 20261101T085308503Z), so
# none may cross a face or air uncovered. Each lies under one of this sheet's
# own extension lines:
# - both chords at y=0 (the head/shoulder junction edge), under the y=0 lines
#   of HeadHeight (from -HEAD_DIA/2 rightward) and ShoulderLength (leftward);
# - the thread chord on the shoulder end edge (y=-SHOULDER_LEN), under
#   ShoulderLength's far line, which reaches x=+THREAD_MAJOR/2;
# - HeadHeight on the head silhouette, under the head diameter's left line;
#   ShoulderLength on the shoulder silhouette and ThreadLength below it, under
#   the shoulder diameter's right line.
# Only HeadHeight's and ShoulderLength's ~0.76 mm extension-line gap next to
# y=0 stays bare, inside their silhouette edges. The sides pin every cover.
SUPPLIER_REFERENCE_STARTS = {
    "SupplierHeadHeight": (-HEAD_DIA / 2.0, 0.0),
    "SupplierHeadDiameter": (-HEAD_DIA / 2.0, 0.0),
    "SupplierShoulderLength": (SHOULDER_DIA / 2.0, 0.0),
    "SupplierShoulderDiameter": (-SHOULDER_DIA / 2.0, 0.0),
    "SupplierThreadLength": (SHOULDER_DIA / 2.0, -SHOULDER_LEN),
    "SupplierThreadDiameter": (-THREAD_MAJOR / 2.0, -SHOULDER_LEN),
}
SUPPLIER_REFERENCE_PLANES = {}
SUPPLIER_REFERENCE_SIDES = {
    "SupplierHeadHeight": "right",
    "SupplierHeadDiameter": "top",
    "SupplierShoulderLength": "left",
    "SupplierShoulderDiameter": "bottom",
    "SupplierThreadLength": "right",
    "SupplierThreadDiameter": "bottom",
}
SUPPLIER_REFERENCE_FORMATS = {
    "SupplierHeadHeight": (3, "length", None, None),
    "SupplierHeadDiameter": (3, "diameter", None, None),
    "SupplierShoulderLength": (3, "length", None, None),
    "SupplierShoulderDiameter": (3, "diameter", None, None),
    "SupplierThreadLength": (3, "length", None, None),
    "SupplierThreadDiameter": (3, "diameter", None, "10-24"),
}
# Signed lower/upper supplier deviations, inches. These are reference source
# information, not project fabrication controls.
SUPPLIER_REFERENCE_TOLERANCES_IN = {
    "SupplierShoulderLength": (0.0, 0.002),
    "SupplierShoulderDiameter": (-0.001, 0.0),
}
