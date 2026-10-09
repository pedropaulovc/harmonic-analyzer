r"""Live-sourced McMaster91790A199 dimensions in mm, without native execution.

MHA-VN-040 (quantity2): standard OVAL slotted18-8, #8-32 UNC-2A,
fully threaded1in stock, nominal82degree, ASME B18.6.3, flat tip.
Populated primary page observed2026-10-09T07:17:13.553Z:
https://www.mcmaster.com/91790A199/ . Length is from BEVEL TOP,
not crown or underhead. Catalog head diameter.312in, total head.152in,
crown.052in are nominal, not supplier tolerance bands. The derived
82degree cone/spherical crown recipe is not a vendor3D model or a
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
# ASME B1.1 UNC-2A, Machining Doctor thread table tid15. Internal 2B
# counterpart lives with the actual ARM tap; pitch clearance is NOT zero.
THREAD_PITCH_DIA_LIMITS_MM = tuple(value * IN for value in (0.1399, 0.1428))
PITCH = IN / 32.0
HEAD_DIA = 0.312 * IN  # at the top of the bevel
HEAD_H = 0.152 * IN  # total, crown included
CROWN_H = 0.052 * IN
BEVEL_H = HEAD_H - CROWN_H
HEAD_ANGLE_DEG = 82.0
# ASME B18.6.3-2013 Table7 (printed p19), §§2.1.5,2.1.6,3.2–3.7:
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
# §3.5 permits the non-thread body down to the Class2A minimum pitch OD.
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
# §3.4 applies -.03in to oval overall Lo. No positive .052 REF crown credit.
STOCK_OVERALL_LENGTH_MIN_MM = STOCK_LENGTH - 0.03 * IN
# §3.7: .006in/in straightness. Whole-metal height bounds the uncredited
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
# The cut end's 45 deg deburr, its radial leg; a single MAX limit, as MHA-VN-031's
# CUT_END_BREAK_MAX_MM.  The model carries the maximum.  The part sheet's
# installation note (the registry's ``installation_notes``) prints it.
CUT_END_BREAK_MAX = 0.1
# What the A06 cut step prints for it.
CUT_END_BREAK_TEXT = f"{CUT_END_BREAK_MAX:g} MAX"

PURCHASED_STOCK_NOTE = "\n".join((
    f"McMASTER {SKU} / OVAL SLOTTED {THREAD} UNC-{THREAD_CLASS}",
    f"1 IN ({STOCK_LENGTH:.2f}) STOCK, FROM BEVEL TOP; CUT TO FIT",
    "CUT OFF MECHANISM BEFORE GUIDE-LOCK SWEEP",
    f"TRIM FLUSH OR PROUD 0.2 MAX; CUT-END BREAK {CUT_END_BREAK_TEXT}",
))


