r"""Live-sourced McMaster 91790A199 dimensions in mm, without native execution.

MHA-PD-VN-56 (quantity 2): standard OVAL slotted 18-8, #8-32 UNC-2A,
fully threaded 1 in stock, nominal 82 degree, ASME B18.6.3, flat tip.
Populated primary page observed 2026-10-09T07:17:13.553Z:
https://www.mcmaster.com/91790A199/ . Length is from BEVEL TOP,
not crown or underhead. Catalog head diameter .312 in, total head .152 in,
crown .052 in are nominal, not supplier tolerance bands. The derived
82 degree cone/spherical crown recipe is not a vendor 3D model or a
profile guarantee. The installed oval/slotted head look is unchanged.

Stock is bench-fitted and cut OFF MECHANISM before the guide-lock sweep.
The installed cut length and deburr follow the actual arm/plate stack.
Commodity hardware is used to its published catalogue/standard dimensions;
there is no incoming screw-profile, crown or thread-loss inspection plan.

Reference frame: axis+Y, bevel top y=0, crown above it; installed shank
ends y=-CUT_LENGTH. Nominal native builds do not invent actual receipts.
"""

from __future__ import annotations

import math

import _config
import pd_transgear_arm_geometry as ARM
import pd_transgear_arm_plate_geometry as PLATE
from _package_units import drawing_unit

IN = 25.4
# #290: the purchased reference sheet prints decimal inch.
UNIT = drawing_unit(
    "parts/pd-vn-transgear-arm-plate-screw", _config.parts("pd-vn-transgear-arm-plate-screw")
)

SKU = "91790A199"  # verified1in OVAL; cut to the unchanged installed fit
THREAD = "#8-32"
THREAD_CLASS = "2A"
ASSEMBLY_QUANTITY = 2
THREAD_MAJOR = 0.164 * IN
THREAD_MAJOR_MIN = 0.1571 * IN  # UNC-2A minimum major (ASME B1.1)
THREAD_MAJOR_MAX_MM = 0.1631 * IN  # UNC-2A maximum; GO gage mouth datum
# ASME B1.1 UNC-2A, Machining Doctor thread table tid 15. Internal 2B
# counterpart lives with the actual ARM tap; pitch clearance is NOT zero.
THREAD_PITCH_DIA_LIMITS_MM = tuple(value * IN for value in (0.1399, 0.1428))
PITCH = IN / 32.0
HEAD_DIA = 0.312 * IN  # at the top of the bevel
HEAD_H = 0.152 * IN  # total, crown included
CROWN_H = 0.052 * IN
BEVEL_H = HEAD_H - CROWN_H
HEAD_ANGLE_DEG = 82.0
# ASME B18.6.3-2013 Table 7 (printed p. 19), §§2.1.5, 2.1.6, 3.2–3.7:
# https://www.finesz.com/pic/ASMEB18.6.3-2013.pdf
# H=.100, C=.052 and total O=.152 are REF, not dimensional maxima.
# The mandatory protrusion F above standard gaging diameter G IS limited.
HEAD_DIA_MAX_MM = 0.312 * IN
HEAD_PROTRUSION_MAX_MM = 0.091 * IN
HEAD_PROTRUSION_GAGE_DIA_MM = 0.267 * IN
HEAD_BEARING_HALF_ANGLE_MIN_RAD = math.radians(80.0 / 2.0)
HEAD_AXIS_ECCENTRICITY_MAX_MM = 0.03 * HEAD_DIA_MAX_MM
HEAD_RADIUS_FROM_SHANK_AXIS_MAX_MM = HEAD_DIA_MAX_MM / 2.0 + HEAD_AXIS_ECCENTRICITY_MAX_MM
UNDER_HEAD_FILLET_RADIUS_MAX_MM = 0.15 * THREAD_MAJOR
UNTHREADED_UNDER_HEAD_MAX_MM = 2.0 * PITCH
POINT_CHAMFER_LENGTH_MAX_MM = 2.0 * PITCH
# §3.5 permits the non-thread body down to the Class 2A minimum pitch OD.
# Bound ALL crown/cone/fillet metal; no REF crown or side-height cap.
HEAD_WHOLE_METAL_HEIGHT_MAX_MM = (
    HEAD_PROTRUSION_MAX_MM
    + (HEAD_PROTRUSION_GAGE_DIA_MM - THREAD_PITCH_DIA_LIMITS_MM[0]) / 2.0
    / math.tan(HEAD_BEARING_HALF_ANGLE_MIN_RAD)
    + UNDER_HEAD_FILLET_RADIUS_MAX_MM
)
# §3.2 uses a GO thread ring countersunk to maximum thread-major diameter.
# This is its bearing datum, NOT the bottom of the entire head/fillet.
# A swelling fillet stops that ring earlier; do not charge it twice.
HEAD_TOP_TO_THREAD_GAGE_MAX_MM = (
    HEAD_PROTRUSION_MAX_MM
    + (HEAD_PROTRUSION_GAGE_DIA_MM - THREAD_MAJOR_MAX_MM) / 2.0
    / math.tan(HEAD_BEARING_HALF_ANGLE_MIN_RAD)
)
STOCK_LENGTH = 1.0 * IN  # primary nominal FROM BEVEL TOP
# §3.4 applies -.03 in to oval overall Lo. No positive .052 REF crown credit.
STOCK_OVERALL_LENGTH_MIN_MM = STOCK_LENGTH - 0.03 * IN
# §3.7: .006 in/in straightness. Whole-metal height bounds the uncredited
# crown in the maximum stock lever; no nominal crown tolerance is assumed.
STOCK_BODY_STRAIGHTNESS_MAX_MM = 0.006 * (STOCK_LENGTH + HEAD_WHOLE_METAL_HEIGHT_MAX_MM)
HEAD_RADIUS_FROM_THREAD_AXIS_MAX_MM = (
    HEAD_RADIUS_FROM_SHANK_AXIS_MAX_MM + STOCK_BODY_STRAIGHTNESS_MAX_MM
)

# --- As installed: cut to fit ----------------------------------------------------
# The bevel top sits flush with the plate's rear face, so the tip is flush
# with the arm's front face at the plate's over-arm section plus the arm.
CUT_LENGTH = PLATE.THICKNESS_OVER_ARM + ARM.THICKNESS
# The modelled screw is the installed one: placement, interference and the
# joint stack read LENGTH as its length.
LENGTH = CUT_LENGTH
# The cut end's 45 deg deburr, its radial leg; a single MAX limit, as MHA-DT-VN-61's
# CUT_END_BREAK_MAX_MM.  The model carries the maximum.  Tighter than the
# title block's .010 edge break on purpose: at .010 the break would take the
# arm tap's last thread and the joint's worst engagement falls to 1.47D, under
# the 1.5D ``transgear_hanger_joints`` requires.  The MHA-PD-00 cut step,
# which does the cut, prints this limit and the tip's proud limit; the part
# sheet's note only says what the cut is for.
CUT_END_BREAK_MAX = 0.1016  # .004
# The cut tip may stand this far proud of the arm's front face (the joint
# stack's ``transgear_hanger_joints.PLATE_SCREW_CUT_PROUD_MAX``).
CUT_PROUD_MAX = 0.2032  # .008

# The views show the screw as cut, shorter than the ITEM row's 1 in stock
# (machinist review round 3); its length is the MHA-PD-00 cut step's.  Three
# lines: no more fit beside the purchased sheet's general line (rule 7).
PURCHASED_STOCK_NOTE = "\n".join((
    "CUT TO LENGTH AND BREAK THE CUT END AT ASSEMBLY (MHA-PD-00 CUT STEP,",
    "BEFORE THE GUIDE-LOCK SWEEP), SO THE TIP CLEARS THE SWEEP AND THE",
    "THREAD STAYS FULLY ENGAGED IN THE MHA-PD-18 ARM. VIEWS SHOW IT AS CUT.",
))


# --- Supplier engineering drawing references -----------------------------------
# Drawing/source evidence is retained out of tree under SupplierScrewsB.
SUPPLIER_DRAWING_URL = (
    "https://www.mcmaster.com/mvC/Library/CAD2/20260108/172E7CCB/"
    "91790A199_18-8%20Stainless%20Steel%20Slotted%20Oval%20Head%20ScrewsX.GIF"
)
# The current solid has no physical station matching the supplier's HEAD_H:
# its cone meets the major at depth (HEAD_DIA-THREAD_MAJOR)/2/tan(41 deg),
# whereas the source STEP's neck/thread-start station is BEVEL_H below the
# bevel top. Do not dimension that source head height onto the current solid.
# The source STEP also has a different underhead fillet; this port changes
# neither transition nor any other solid/installed geometry.
# Stock length is an isolated construction witness, not the installed span.
# The supplier prints only the 8-32 designation, not a numeric major diameter.
# This extra carrier is explicitly the current model's basic nominal thread
# size, not a supplier-printed dimension or a helical-surface measurement.
SUPPLIER_REFERENCE_SIDES = {
    "SupplierStockLength": "left",
    "SupplierCrownHeight": "right",
    "SupplierNominalThreadMajor": "bottom",
}
SUPPLIER_REFERENCE_DIMENSIONS = (
    ("SupplierStockLength", -STOCK_LENGTH, "vertical"),
    ("SupplierCrownHeight", CROWN_H, "vertical"),
    ("SupplierHeadAngle", HEAD_ANGLE_DEG, "angle"),
    ("SupplierHeadDiameter", HEAD_DIA, "horizontal"),
    ("SupplierNominalThreadMajor", THREAD_MAJOR, "horizontal"),
)
SUPPLIER_REFERENCE_STARTS = {
    "SupplierStockLength": (-HEAD_DIA, 0.0),
    "SupplierCrownHeight": (HEAD_DIA / 2.0, 0.0),
    "SupplierHeadAngle": (-HEAD_DIA / 2.0, 0.0),
    "SupplierHeadDiameter": (-HEAD_DIA / 2.0, 0.0),
    "SupplierNominalThreadMajor": (-THREAD_MAJOR / 2.0, -CUT_LENGTH / 2.0),
}
SUPPLIER_REFERENCE_PLANES = {"SupplierHeadDiameter": "Top"}
SUPPLIER_REFERENCE_FORMATS = {
    "SupplierStockLength": (0, "length", None, "AS-SUPPLIED STOCK LENGTH"),
    "SupplierCrownHeight": (3, "length", None, None),
    "SupplierHeadAngle": (0, "angle", None, None),
    "SupplierHeadDiameter": (3, "diameter", None, None),
    "SupplierNominalThreadMajor": (
        3, "diameter", None, "8-32\nNOMINAL THREAD SIZE"
    ),
}
