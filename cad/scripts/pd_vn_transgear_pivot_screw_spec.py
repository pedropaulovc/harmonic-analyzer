r"""MHA-PD-VN-57 transgear pivot screw: McMaster 90325A174, faced to fit.

The catalogue inputs live in ``_mcmaster_90325a174`` (the stock recipe reads
only those).  This module adds the modified part.

The user's 2026-10-15 rulings: the screw seats shoulder-hard in the MHA-PD-07
bar's THROUGH #8-32 tap, its thread tip is faced at fit-up to stand
TIP_RECESS below the bar's FRONT face (never proud: the platen slides across
that face) and the tip is staked at the tap's front mouth (drawing-guidelines
rule 23, staked end).  The length is a rule-19 fit-up: the tip is faced to the
actual bar, so the sheet prints the thread length as a REFERENCE nominal (the
nominal bar less the recess window's middle) and the recess as the matched
fit.  Threadlocker is optional.

Facing to fit leaves at most one pitch of incomplete thread at the new tip
(the repo's precedent charge, ``sm_vn_knife_hanger_stud_spec``), and the thread
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
import _config
from _package_units import drawing_unit
from _printed_tolerance import angular_band_deg

UNIT = drawing_unit(
    "parts/pd-vn-transgear-pivot-screw", _config.parts("pd-vn-transgear-pivot-screw")
)

# The faced tip's recess below the bar's front face, as fitted (user ruling
# 2026-10-15): never proud of the platen's slide face, close enough for the
# stake at the tap's mouth to close the thread over the tip.  .008-.020 (#290).
TIP_RECESS = (0.2032, 0.508)
# The printed REFERENCE thread length: the nominal 9.5 bar less the recess
# window's middle (transgear_hanger_joints asserts the link), (.360).
FITTED_THREAD_LEN = 9.1444
SHOULDER_END_Y = -SHOULDER_LEN
TIP_Y = SHOULDER_END_Y - FITTED_THREAD_LEN
INCOMPLETE_TIP_LEN_MAX = PITCH
# The drawing-guidelines.md rule 18 (thread engagement) floor.
ENGAGEMENT_MIN_D = 1.5
# Continuous tail from the faced tip that must be gauged full form beyond the
# incomplete pitch: the 1.5D engagement plus that pitch, rounded up to .001 in.
THREAD_LENGTH_MIN = (
    math.ceil((ENGAGEMENT_MIN_D * THREAD_MAJOR + PITCH) / 25.4 * 1000.0) / 1000.0 * 25.4
)
FULL_FORM_TAIL_MIN = THREAD_LENGTH_MIN - INCOMPLETE_TIP_LEN_MAX
# #8-32 UNC-2A external minor diameter, from the UNC class 2A/2B tables in
# Kennametal's "Thread data - American UN" (read 2026-10-15,
# https://kthreadmilling.kennametal.com/KThreadmillingWeb/help/UN%20standard.htm).
# The previous 0.1302 in sits in the 2B INTERNAL minor band (0.130-0.139 in),
# not on the screw's root.
# The table publishes only the UNR reference MAXIMUM: the 2A major max
# 0.1631 in (0.164 basic less the 0.0009 allowance) less 1.226869 P is
# 0.1248 in = 3.170.  DERIVED ESTIMATE of the minimum, the repo's deepest-root
# construction (sm_gooseneck_spring_screw_geom, dt_crank_handle_pivot_screw_spec):
# a full basic half-depth 0.649519 P below the 2A pitch-diameter minimum
# 0.1399 in is 0.1196 in = 3.038 (the UNR 0.108 P least root radius gives the
# same 0.1196 in).
THREAD_MINOR_UNR_2A_MAX = (0.1631 - 1.226869 / 32.0) * 25.4
THREAD_PD_2A_MIN_IN = 0.1399
THREAD_MINOR_2A_MIN_EST = (THREAD_PD_2A_MIN_IN - 0.649519 / 32.0) * 25.4
# Radial leg from the native ChamferWidth, measured on the tip face: a MAX
# (swTolMAX prints the nominal and "max."), so the model stands at the printed
# maximum. Its callout asks for the chamfer past the thread root, which leaves
# no feather edge; the thread tail's 1-pitch note bounds the rest.
CHAMFER_WIDTH = 0.6096  # .024
CHAMFER_WIDTH_MAX = CHAMFER_WIDTH
CHAMFER_ANGLE = 45.0  # Native driving angle between tip face and chamfer.
# Printed natively without a band: the title block's angular row governs it.
CHAMFER_ANGLE_TOLERANCE = angular_band_deg(unit=UNIT)
# Worst axial tip loss: the widest radial leg at the steepest title-block
# angle. It must stay inside the one incomplete pitch the engagement charges.
CHAMFER_AXIAL_MAX = CHAMFER_WIDTH_MAX * math.tan(
    math.radians(CHAMFER_ANGLE + CHAMFER_ANGLE_TOLERANCE)
)
if not 0.0 < CHAMFER_AXIAL_MAX <= INCOMPLETE_TIP_LEN_MAX:
    raise AssertionError("cut-end chamfer exceeds the charged incomplete pitch")


def require_chamfer_past_root(chamfer_width_max: float) -> None:
    """Refuse a cut-end chamfer band whose largest leg cannot reach under the
    root of every conforming screw.

    "Past the thread root" must be achievable for the worst screw: the largest
    tip face (the basic major, at or above the 2A major max) against the
    deepest root (the estimated 2A minor minimum).  A shallower root only makes
    it easier, so checking the minor MAXIMUM would pass bands that leave a
    feather edge on a deep-rooted screw.
    """
    if not THREAD_MAJOR - 2.0 * chamfer_width_max < THREAD_MINOR_2A_MIN_EST:
        raise AssertionError("a chamfer past the thread root exceeds its maximum")


require_chamfer_past_root(CHAMFER_WIDTH_MAX)
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
    "StockTrimProfile": {"CutLength": 3},
    "StockDeburrProfile": {"ChamferWidth": 3, "ChamferAngle": 0},
    "ThreadTailAcceptance": {"ThreadLengthMin": 3},
}
DIMENSION_PRECISION = {
    name: digits
    for dimensions in DRAWING_PRECISION.values()
    for name, digits in dimensions.items()
}
# CutLength is a REFERENCE (swTolNONE, "(.360)"): the fit-up sets the length.
REFERENCE_DIMENSIONS = (("StockTrimProfile", "CutLength"),)
DIMENSION_TOLERANCE_TYPES = {
    "CutLength": 0,
    "ChamferWidth": 6,  # swTolMAX
    "ChamferAngle": 11,  # swTolGeneral: native band, title-block print.
    "ThreadLengthMin": 5,
}
PRINTED_THREAD = f"{THREAD} UNC"  # Class 2A comes from the title block.
DIMENSION_CALLOUTS = {
    "CutLength": (
        "SHOULDER END TO FACED TIP\n"
        f"TIP {TIP_RECESS[0] / 25.4:.3f}-{TIP_RECESS[1] / 25.4:.3f}".replace("0.", ".")
        + " BELOW MHA-PD-07\nFRONT FACE AS FITTED"
    ),
    # The native ChamferAngle prints its own 45 degrees.
    "ChamferWidth": "CUT-END CHAMFER\nPAST THE THREAD ROOT",
    "ThreadLengthMin": (
        f"{PRINTED_THREAD} CONTINUOUS TAIL FROM TIP\n"
        "INCOMPLETE CUT-END THREAD 1 PITCH MAX\n"
        "ALL REMAINING TAIL FULL FORM"
    ),
}

# Supplier engineering drawing inspected 2026-10-19. Its .313/.156/.188
# spellings do not replace the exact 5/16, 5/32 and 3/16 inch native geometry.
SUPPLIER_DRAWING_URL = (
    "https://www.mcmaster.com/mvC/Library/CAD2/20260701/7DFBF7EB/"
    "90325A174_18-8%20Stainless%20Steel%20Precision%20Shoulder%20ScrewX.GIF"
)
SUPPLIER_REFERENCE_DIMENSIONS = {
    "SupplierHeadDiameter": {
        "units": "in",
        "precision": 3,
        "expected_mm": HEAD_DIA,
        "presentation": "diameter",
        "callout": "HEAD",
    },
    "SupplierHeadHeight": {
        "units": "in",
        "precision": 3,
        "expected_mm": HEAD_H,
        "callout": "HEAD HEIGHT",
    },
    "SupplierSocketAF": {
        "units": "in",
        "precision": 0,
        "fraction_denominator": 32,
        "expected_mm": SOCKET_AF,
        "callout": "HEX SOCKET AF",
    },
    "SupplierShoulderDiameter": {
        "units": "in",
        "precision": 3,
        "expected_mm": SHOULDER_DIA,
        "presentation": "diameter",
        "callout": "AS-SUPPLIED SHOULDER",
    },
    "SupplierShoulderLength": {
        "units": "in",
        "precision": 3,
        "expected_mm": SHOULDER_LEN,
        "callout": "AS-SUPPLIED SHOULDER",
    },
    "SupplierThreadMajor": {
        "units": "in",
        "precision": 3,
        "expected_mm": THREAD_MAJOR,
        "presentation": "diameter",
        "callout": f"{PRINTED_THREAD}\nTHREAD MAJOR NOMINAL",
    },
    "SupplierStockThreadLength": {
        "units": "in",
        "precision": 3,
        "expected_mm": THREAD_LEN,
        "callout": "AS SUPPLIED\nSTOCK THREAD",
    },
}
# Native source-band carriers do not retolerance solid-driving dimensions or
# the existing faced-tip manufacturing acceptance controls.
SUPPLIER_REFERENCE_BANDS = {
    "SupplierShoulderDiameter": SHOULDER_DIA_LIMITS,
    "SupplierShoulderLength": SHOULDER_LEN_LIMITS,
}
SUPPLIER_REFERENCE_SKETCH = (
    ("SupplierThreadMajor", THREAD_MAJOR, "horizontal"),
    ("SupplierShoulderDiameter", SHOULDER_DIA, "horizontal"),
    ("SupplierShoulderLength", SHOULDER_LEN, "vertical"),
)
SUPPLIER_REFERENCE_STARTS = {
    "SupplierThreadMajor": (
        -THREAD_MAJOR / 2,
        SHOULDER_END_Y - (FULL_THREAD_START + FITTED_THREAD_LEN) / 2,
    ),
    # On the head's bearing face (y 0), whose outline edge spans the shoulder:
    # the drawing draws this line and the length's (on the shoulder's flank)
    # in the outline's black, so neither prints as a stray centreline
    # (machinist review r2, minor, all runs).
    "SupplierShoulderDiameter": (-SHOULDER_DIA / 2, 0.0),
    "SupplierShoulderLength": (SHOULDER_DIA / 2, SHOULDER_END_Y),
}
SUPPLIER_DRAWING_DIMENSIONS = {
    "SupplierReference": {name for name, _value, _orientation in SUPPLIER_REFERENCE_SKETCH},
}
# The source-stock sheet restores the actual original solid, not a witness
# length on the faced geometry. Factory thread/chamfer remain intact.
SUPPLIER_STOCK_CONFIGURATION = "AS SUPPLIED STOCK"
SUPPLIER_STOCK_SUPPRESSED_FEATURES = ("StockDeburr", "StockTrim")
SUPPLIER_STOCK_TITLE = "\n".join((
    f"McMASTER {SKU} SHOULDER SCREW",
    "AS SUPPLIED STOCK - SUPPLIER REFERENCE ONLY",
    "FACED LENGTH AND END CONTROLS: SHEET 1",
))
