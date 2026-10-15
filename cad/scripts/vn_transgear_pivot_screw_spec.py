r"""MHA-VN-041 transgear pivot screw: McMaster 90325A174, faced to fit.

The catalogue inputs live in ``_mcmaster_90325a174`` (the stock recipe reads
only those).  This module adds the modified part.

The user's 2026-10-15 rulings: the screw seats shoulder-hard in the MHA-PD-007
bar's THROUGH #8-32 tap, its thread tip is faced at fit-up to stand
TIP_RECESS below the bar's FRONT face (never proud: the platen slides across
that face) and the tip is staked at the tap's front mouth (drawing-guidelines
rule 23, staked end).  The length is a rule-19 fit-up: the tip is faced to the
actual bar, so the sheet prints the thread length as a REFERENCE nominal (the
nominal bar less the recess window's middle) and the recess as the matched
fit.  Threadlocker is optional.

Facing to fit leaves at most one pitch of incomplete thread at the new tip
(the repo's precedent charge, ``vn_knife_hanger_stud_spec``), and the thread
tail from the tip must stay full form for THREAD_LENGTH_MIN; the joint's
worst engagement is judged in ``transgear_hanger_joints``.

Frame (the stock recipe's): axis +Y, head up, the under-head shoulder face at
y = 0 (Top Plane); the shoulder runs down to y = -SHOULDER_LEN, the faced tip
stands FITTED_THREAD_LEN below it.
"""

from __future__ import annotations

import math

from _mcmaster_90325a174 import (
    ASME_NECK_WIDTH_MAX as ASME_NECK_WIDTH_MAX,
    CATALOG_CHECKED_DATE as CATALOG_CHECKED_DATE,
    CATALOG_URL as CATALOG_URL,
    FULL_THREAD_START as FULL_THREAD_START,
    HEAD_CHAMFER as HEAD_CHAMFER,
    HEAD_DIA as HEAD_DIA,
    HEAD_H as HEAD_H,
    NECK_DIA as NECK_DIA,
    PITCH as PITCH,
    SHOULDER_DIA as SHOULDER_DIA,
    SHOULDER_DIA_LIMITS as SHOULDER_DIA_LIMITS,
    SHOULDER_LEN as SHOULDER_LEN,
    SHOULDER_LEN_LIMITS as SHOULDER_LEN_LIMITS,
    SKU as SKU,
    SOCKET_AF as SOCKET_AF,
    SOCKET_DEPTH as SOCKET_DEPTH,
    STOCK_THREAD_LEN_MIN as STOCK_THREAD_LEN_MIN,
    THREAD as THREAD,
    THREAD_CLASS as THREAD_CLASS,
    THREAD_LEN as THREAD_LEN,
    THREAD_LEN_LIMITS as THREAD_LEN_LIMITS,
    THREAD_MAJOR as THREAD_MAJOR,
)
from _printed_tolerance import angular_band_deg

# The faced tip's recess below the bar's front face, as fitted (user ruling
# 2026-10-15): never proud of the platen's slide face, close enough for the
# stake at the tap's mouth to close the thread over the tip.
TIP_RECESS = (0.20, 0.50)
# The printed REFERENCE thread length: the nominal 9.5 bar less the recess
# window's middle (transgear_hanger_joints asserts the link).
FITTED_THREAD_LEN = 9.15
SHOULDER_END_Y = -SHOULDER_LEN
TIP_Y = SHOULDER_END_Y - FITTED_THREAD_LEN
INCOMPLETE_TIP_LEN_MAX = PITCH
# The drawing-guidelines.md rule 18 (thread engagement) floor.
ENGAGEMENT_MIN_D = 1.5
# Continuous tail from the faced tip that must be gauged full form beyond the
# incomplete pitch: the 1.5D engagement plus that pitch, rounded up.
THREAD_LENGTH_MIN = math.ceil((ENGAGEMENT_MIN_D * THREAD_MAJOR + PITCH) * 20.0) / 20.0
FULL_FORM_TAIL_MIN = THREAD_LENGTH_MIN - INCOMPLETE_TIP_LEN_MAX
# The 2A minor diameter's MAX (ASME B1.1 #8-32 UNC-2A, 0.1302 in): the cut-end
# chamfer's least leg must reach under it so no feather edge is left.
THREAD_MINOR_MAX = 0.1302 * 25.4
# Radial leg from the native ChamferWidth, measured on the tip face.
CHAMFER_WIDTH = 0.50
CHAMFER_WIDTH_TOLERANCE = 0.05
CHAMFER_WIDTH_MIN = CHAMFER_WIDTH - CHAMFER_WIDTH_TOLERANCE
CHAMFER_WIDTH_MAX = CHAMFER_WIDTH + CHAMFER_WIDTH_TOLERANCE
CHAMFER_ANGLE = 45.0  # Native driving angle between tip face and chamfer.
# Printed natively without a band: the title block's angular row governs it.
CHAMFER_ANGLE_TOLERANCE = angular_band_deg()
# Worst axial tip loss: the widest radial leg at the steepest title-block
# angle. It must stay inside the one incomplete pitch the engagement charges.
CHAMFER_AXIAL_MAX = CHAMFER_WIDTH_MAX * math.tan(
    math.radians(CHAMFER_ANGLE + CHAMFER_ANGLE_TOLERANCE)
)
if not 0.0 < CHAMFER_AXIAL_MAX <= INCOMPLETE_TIP_LEN_MAX:
    raise AssertionError("cut-end chamfer exceeds the charged incomplete pitch")
if not THREAD_MAJOR / 2.0 - CHAMFER_WIDTH_MIN < THREAD_MINOR_MAX / 2.0:
    raise AssertionError("the least cut-end chamfer leaves a feather edge")
# The faced length is shorter than every catalogue stock length's nominal and
# its full thread clears the neck.
if not FULL_THREAD_START + THREAD_LENGTH_MIN < FITTED_THREAD_LEN < THREAD_LEN:
    raise AssertionError("the fitted thread length leaves the stock")

DRAWING_DIMENSIONS = {
    "StockTrimProfile": {"CutLength"},
    "StockDeburrProfile": {"ChamferWidth", "ChamferAngle"},
    "ThreadTailAcceptance": {"ThreadLengthMin"},
}
DRAWING_PRECISION = {
    "StockTrimProfile": {"CutLength": 2},
    "StockDeburrProfile": {"ChamferWidth": 2, "ChamferAngle": 0},
    "ThreadTailAcceptance": {"ThreadLengthMin": 2},
}
DIMENSION_PRECISION = {
    name: digits
    for dimensions in DRAWING_PRECISION.values()
    for name, digits in dimensions.items()
}
# CutLength is a REFERENCE (swTolNONE, "(9.15)"): the fit-up sets the length.
REFERENCE_DIMENSIONS = (("StockTrimProfile", "CutLength"),)
DIMENSION_TOLERANCE_TYPES = {
    "CutLength": 0,
    "ChamferWidth": 4,
    "ChamferAngle": 11,  # swTolGeneral: native band, title-block print.
    "ThreadLengthMin": 5,
}
PRINTED_THREAD = f"{THREAD} UNC"  # Class 2A comes from the title block.
DIMENSION_CALLOUTS = {
    "CutLength": (
        "SHOULDER END TO FACED TIP\n"
        f"TIP {TIP_RECESS[0]:.2f}-{TIP_RECESS[1]:.2f} BELOW MHA-PD-007\n"
        "FRONT FACE AS FITTED"
    ),
    # The band on the leg is the engagement reason; the native ChamferAngle
    # prints its own 45 degrees.
    "ChamferWidth": "CUT-END CHAMFER\nSETS FULL-THREAD ENGAGEMENT\nIN MHA-PD-007 BAR",
    "ThreadLengthMin": (
        f"{PRINTED_THREAD} CONTINUOUS TAIL FROM TIP\n"
        "INCOMPLETE CUT-END THREAD 1 PITCH MAX\n"
        "ALL REMAINING TAIL FULL FORM"
    ),
}
