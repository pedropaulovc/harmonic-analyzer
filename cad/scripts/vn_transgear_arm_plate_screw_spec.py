r"""Live-sourced McMaster 91790A199 dimensions in mm, without native execution.

MHA-VN-040 (quantity 2): standard OVAL slotted 18-8, #8-32 UNC-2A,
fully threaded 1 in stock, nominal 82 degree, ASME B18.6.3, flat tip.
Populated primary page observed 2026-10-09T07:17:13.553Z:
https://www.mcmaster.com/91790A199/ . Length is from BEVEL TOP,
not crown or underhead. Catalog head diameter .312 in, total head .152 in,
crown .052 in are nominal, not supplier tolerance bands. The 82 degree
cone/spherical crown follow those catalogue sizes; the underhead neck,
fillet and thread start are the supplier STEP's (``SOURCE_STEP_SHA256``,
inspected out of tree, not committed). The installed oval/slotted head look
is unchanged.

Stock is bench-fitted and cut OFF MECHANISM before the guide-lock sweep.
The installed cut length and deburr follow the actual arm/plate stack.
Commodity hardware is used to its published catalogue/standard dimensions;
there is no incoming screw-profile, crown or thread-loss inspection plan.

Reference frame: axis+Y, bevel top y=0, crown above it; the installed
(default) shank ends y=-CUT_LENGTH, the SupplierStock configuration's factory
tip y=-STOCK_LENGTH. Nominal native builds do not invent actual receipts.
"""

from __future__ import annotations

import math

import pd_transgear_arm_geometry as ARM
import pd_transgear_arm_plate_geometry as PLATE

IN = 25.4

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

# --- Underhead transition: the supplier's own STEP -------------------------------
# McMaster's CAD-chooser STEP for this SKU (1 solid, 77 faces), inspected with
# headless FreeCAD on 2026-10-19 and kept out of tree. Its axis is +X with the
# bevel top at x = -12.7; the depths below are measured from the bevel top.
SOURCE_STEP_URL = (
    "https://www.mcmaster.com/mvC/Library/CAD2/20260108/53AE5A4D/"
    "91790A199_18-8%20Stainless%20Steel%20Slotted%20Oval%20Head%20Screws.STEP"
)
SOURCE_STEP_SHA256 = "8dce92581429d3c3fcf5e4d8b5a3588ce990af21ad99cd5d00051ff7653c71bb"
SUPPLIER_DRAWING_URL = (
    "https://www.mcmaster.com/mvC/Library/CAD2/20260108/172E7CCB/"
    "91790A199_18-8%20Stainless%20Steel%20Slotted%20Oval%20Head%20ScrewsX.GIF"
)
# Where the 82 deg bevel cone, run on, meets the thread major (the fillet's
# theoretical sharp corner): STEP cone faces 1/71 hold r = THREAD_MAJOR / 2 there.
BEVEL_CONE_DEPTH = (
    (HEAD_DIA - THREAD_MAJOR) / 2.0 / math.tan(math.radians(HEAD_ANGLE_DEG / 2.0))
)
# The full-major neck (STEP face 64) ends and the thread starts at H = .100 in
# (total .152 less crown .052): STEP x = -10.16, where the annular step
# (face 69, major -> THREAD_START_STEP_R) and the thread-start cone (face 68)
# begin and the groove flanks (faces 66/67) end. The .152 in head height is
# therefore crown apex to thread start, a real model station.
THREAD_START_DEPTH = BEVEL_H
# The STEP's torus (faces 0/70) rounds the cone/neck corner with exactly the
# neck's own length as its radius; its centre sits at depth
# BEVEL_CONE_DEPTH + R * tan(20.5 deg) = 2.303474, so its tangents fall at
# depths 2.05564 (cone) and 2.30347 (neck), not at the thread start.
UNDER_HEAD_FILLET_R = THREAD_START_DEPTH - BEVEL_CONE_DEPTH
# Thread start: an annular step from the major down to r = .077 in, then a
# 60 deg half-angle cone (from the axis) down to the groove root.
THREAD_START_STEP_R = 0.077 * IN
THREAD_START_CONE_HALF_ANGLE_DEG = 60.0
# The STEP's own readings, kept so the formulas above are checked against it.
SOURCE_THREAD_START_DEPTH = -10.16 - -12.7
SOURCE_UNDER_HEAD_FILLET_R = 0.377767541787383
SOURCE_UNDER_HEAD_FILLET_CENTRE_DEPTH = -10.396526045506446 - -12.7
SOURCE_THREAD_START_STEP_R = 1.9558000000000013
SOURCE_THREAD_START_CONE_HALF_ANGLE_RAD = 1.0471975511966
for _formula, _source, _tol in (
    (THREAD_START_DEPTH, SOURCE_THREAD_START_DEPTH, 1e-9),
    (UNDER_HEAD_FILLET_R, SOURCE_UNDER_HEAD_FILLET_R, 1e-9),
    (
        BEVEL_CONE_DEPTH
        + UNDER_HEAD_FILLET_R * math.tan(math.radians(HEAD_ANGLE_DEG / 4.0)),
        SOURCE_UNDER_HEAD_FILLET_CENTRE_DEPTH,
        1e-9,
    ),
    (THREAD_START_STEP_R, SOURCE_THREAD_START_STEP_R, 1e-9),
    (
        math.radians(THREAD_START_CONE_HALF_ANGLE_DEG),
        SOURCE_THREAD_START_CONE_HALF_ANGLE_RAD,
        1e-12,
    ),
):
    if abs(_formula - _source) > _tol:
        raise ValueError(f"underhead transition {_formula!r} departs from the STEP's {_source!r}")

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
# The default (installed) configuration is the installed screw: placement,
# interference and the joint stack read LENGTH as its length.
LENGTH = CUT_LENGTH
# The cut end's 45 deg deburr, its radial leg; a single MAX limit, as MHA-VN-031's
# CUT_END_BREAK_MAX_MM.  The model carries the maximum.  The part sheet's
# installation note (the registry's ``installation_notes``) prints it.
CUT_END_BREAK_MAX = 0.1
# What the A06 cut step prints for it.
CUT_END_BREAK_TEXT = f"{CUT_END_BREAK_MAX:g} MAX"

PURCHASED_STOCK_NOTE = "\n".join((
    f"1 IN ({STOCK_LENGTH:.2f}) STOCK. CUT LENGTH AT ASSEMBLY (MHA-PD-000, BEFORE THE",
    "GUIDE-LOCK SWEEP): TIP FLUSH OR PROUD 0.2 MAX OF THE MHA-PD-018 ARM",
    f"FRONT FACE; CUT-END BREAK {CUT_END_BREAK_TEXT}.",
))

# --- Supplier engineering drawing references -------------------------------------
# The part's native SupplierStock configuration suppresses only the CutToFit
# trim, so it is the full 1 in stock with its factory tip; the reference sheet
# shows that configuration, which makes these supplier sizes the solid's own
# spans. Every value is the exact catalogue constant that drives the solid.
# The supplier drawing (SUPPLIER_DRAWING_URL) labels the thread "8-32" and
# prints no thread-major size, so none is added; the thread size rides the
# stock-length callout instead.
SUPPLIER_STOCK_CONFIGURATION = "SupplierStock"
# Existing witness sides already clear the larger head.
SUPPLIER_REFERENCE_SIDES = {}
SUPPLIER_REFERENCE_DIMENSIONS = (
    ("SupplierStockLength", -STOCK_LENGTH, "vertical"),  # bevel top -> tip
    ("SupplierHeadHeight", -HEAD_H, "vertical"),  # crown apex -> thread start
    ("SupplierCrownHeight", CROWN_H, "vertical"),  # bevel top -> crown apex
    ("SupplierHeadAngle", HEAD_ANGLE_DEG, "angle"),
    ("SupplierHeadDiameter", HEAD_DIA, "horizontal"),  # rim at the bevel top
)
SUPPLIER_REFERENCE_STARTS = {
    "SupplierStockLength": (HEAD_DIA / 2.0, 0.0),
    "SupplierHeadHeight": (-HEAD_DIA / 2.0, CROWN_H),
    "SupplierCrownHeight": (HEAD_DIA / 2.0, 0.0),
    "SupplierHeadAngle": (-HEAD_DIA / 2.0, 0.0),
    "SupplierHeadDiameter": (-HEAD_DIA / 2.0, 0.0),
}
SUPPLIER_REFERENCE_PLANES = {"SupplierHeadDiameter": "Top"}
SUPPLIER_REFERENCE_FORMATS = {
    "SupplierStockLength": (0, "length", None, "8-32"),
    "SupplierHeadHeight": (3, "length", None, None),
    "SupplierCrownHeight": (3, "length", None, None),
    "SupplierHeadAngle": (0, "angle", None, None),
    "SupplierHeadDiameter": (3, "diameter", None, None),
}
