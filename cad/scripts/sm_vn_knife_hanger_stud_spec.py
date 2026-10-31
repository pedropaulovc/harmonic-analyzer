"""MHA-SM-VN-52 knife-hanger bolt: 92314A253 stock, cut to length.

Catalogue checked 2026-10-13: https://www.mcmaster.com/92314A253/.
18-8 stainless plain external hex, #10-24 UNC-2A, fully threaded, flat tip,
2 in under head, 5/16 in AF, 1/8 in head height, 80 ksi. The SKU omits a
specification standard and head/length tolerances. Published UNC-2A thread
major limits are separate from those unspecified supplier tolerances.

The thread-tail MIN below is MODIFIED-PART acceptance, not a supplier
tolerance; the cut-end chamfer takes the title block's band. Retain a
continuous usable tail through at least .418 in (10.6172 mm) from the
finished tip, with at most one pitch of
incomplete thread at that tip. Gauge the rest of that tail to the stock's
UNC-2A class; the print states only #10-24 UNC because the title block's
thread row already gives class 2A.
The native model depicts catalogue fully-threaded geometry; inspection,
not that depiction, certifies the tail used by the worst-case reach stack.

Title-block MATERIAL is the purchased 18-8 family as supplied: nothing in
this static clamp needs one 18-8 grade. ``_fastener_catalog`` keeps AISI 304
only as the SOLIDWORKS library stand-in for rendering and mass; it is not a
supplier grade.

Part frame: finished tip Y=0, axis +Y, bearing face Y=46.70 (nominal: the
length is cut at MHA-SM-00 assembly to the stack measured at its hole).
"""

import math

import _config
from _package_units import drawing_unit

from _mcmaster_92314a253 import (
    CATALOG_CHECKED_DATE as CATALOG_CHECKED_DATE,
    CATALOG_DIMENSIONAL_TOLERANCES as CATALOG_DIMENSIONAL_TOLERANCES,
    CATALOG_STANDARD as CATALOG_STANDARD,
    CATALOG_URL as CATALOG_URL,
    DIMS,
    THREAD_MAJOR_MAX,
    THREAD_MAJOR_MIN,
)
from _printed_tolerance import angular_band_deg, printed_band_mm

# #290: the registry row's drawing_unit (in) is this sheet's unit; the
# acceptance values below are authored on its grid.
UNIT = drawing_unit("parts/sm-vn-knife-hanger-stud", _config.parts("sm-vn-knife-hanger-stud"))

SKU = DIMS.part_no
THREAD = "#10-24"
THREAD_FIT = "UNC-2A"
SHANK_DIA = DIMS.major_dia
SHANK_DIA_MIN = THREAD_MAJOR_MIN
SHANK_DIA_MAX = THREAD_MAJOR_MAX
PITCH = DIMS.pitch
CATALOG_LENGTH = DIMS.length
# Nominal under-head length that holds the modelled tip at assembly Y
# 990.7827: the MHA-FR-02 grip 36.50 (finished underside to the faced top
# the washer bears on), plus the 96659A104 nominal thickness 1.2827, plus the
# 8.9173 nominal reach into the MHA-SM-02 tap. A literal, so this
# purchased-part spec stays free of the frame spec that imports it. The
# length carries no band of its own: MHA-SM-00 cuts each bolt to its
# measured stack plus the fit-up reach (sm_summing_assembly_spec
# HANGER_FIT_REACH), and build_sm_summing_assembly asserts that reach.
# The sheet prints it as the bracketed reference (1.84); the model keeps
# 46.70 (1.8386 in), the stack's nominal, which the crossbar and knife-mount
# reach stacks read.
LENGTH = 46.70
UNDERHEAD_LEN = LENGTH
HEAD_AF = DIMS.head_af
HEAD_H = DIMS.head_h
THREAD_LENGTH = LENGTH  # Nominal catalogue fully-threaded depiction.
# Tail measured from the finished tip, printed .418 MIN: 10.6172 less one
# incomplete pitch still spans the longest reach (build_sm_summing_assembly
# HANGER_THREAD_SPARE).
THREAD_LENGTH_MIN = 10.6172  # .418
INCOMPLETE_TIP_LEN_MAX = PITCH
FULL_FORM_TAIL_MIN = THREAD_LENGTH_MIN - INCOMPLETE_TIP_LEN_MAX
# The drawing-guidelines.md rule 18 (thread engagement) thread engagement floor.
ENGAGEMENT_MIN_D = 1.5
TIP_Y = 0.0
HEAD_UNDERFACE_Y = UNDERHEAD_LEN
HEAD_TOP_Y = HEAD_UNDERFACE_Y + HEAD_H
# Radial leg from the native ChamferWidth, measured on the tip face: .03
# under the title block's two-place row (.02-.04), no band of its own.
# Every leg in that band brings the cut thread start inside the MHA-SM-02
# #25 tap drill even on the largest 2A major (SHANK_DIA_MAX, .1890), so no
# feather edge is left on the crest, and keeps the chamfer's axial run
# inside the one incomplete pitch the thread tail's acceptance allows.
CHAMFER_WIDTH = 0.762  # .03
CHAMFER_WIDTH_TOLERANCE = printed_band_mm(2, unit=UNIT)  # +/-.01
CHAMFER_WIDTH_MIN = CHAMFER_WIDTH - CHAMFER_WIDTH_TOLERANCE
CHAMFER_WIDTH_MAX = CHAMFER_WIDTH + CHAMFER_WIDTH_TOLERANCE
CHAMFER_ANGLE = 45.0  # Native driving angle between tip face and chamfer.
# Printed natively without a band: the title block's angular row governs it.
CHAMFER_ANGLE_TOLERANCE = angular_band_deg(unit=UNIT)
# Worst axial tip loss: the widest radial leg at the steepest title-block
# angle. It must stay inside the one incomplete pitch that the thread tail's
# acceptance allows and the worst-case engagement (reach MIN less one pitch
# >= 1.5D) charges.
CHAMFER_AXIAL_MAX = CHAMFER_WIDTH_MAX * math.tan(
    math.radians(CHAMFER_ANGLE + CHAMFER_ANGLE_TOLERANCE)
)
if not 0.0 < CHAMFER_AXIAL_MAX <= INCOMPLETE_TIP_LEN_MAX:
    raise AssertionError("cut-end chamfer exceeds the charged incomplete pitch")

DRAWING_DIMENSIONS = {
    "StockTrimProfile": {"CutLength"},
    "StockDeburrProfile": {"ChamferWidth", "ChamferAngle"},
    "ThreadTailAcceptance": {"ThreadLengthMin"},
}
DRAWING_PRECISION = {
    "StockTrimProfile": {"CutLength": 2},
    "StockDeburrProfile": {"ChamferWidth": 2, "ChamferAngle": 0},
    "ThreadTailAcceptance": {"ThreadLengthMin": 3},
}
DIMENSION_PRECISION = {
    name: digits
    for dimensions in DRAWING_PRECISION.values()
    for name, digits in dimensions.items()
}
DIMENSION_TOLERANCE_TYPES = {
    "CutLength": 0,  # Reference: cut at MHA-SM-00 assembly.
    "ChamferWidth": 11,  # swTolGeneral: native band, title-block print.
    "ChamferAngle": 11,
    "ThreadLengthMin": 5,
}
PRINTED_THREAD = f"{THREAD} UNC"  # Class 2A comes from the title block.
DIMENSION_CALLOUTS = {
    "CutLength": ("UNDER HEAD TO FINISHED TIP\nCUT AT ASSEMBLY\nPER MHA-SM-00 STEP 4"),
    # The leg leads the cut end into the mount's tap; the native ChamferAngle
    # prints its own 45 degrees.
    "ChamferWidth": "CUT-END CHAMFER\nLEAD-IN TO MHA-SM-02 TAP",
    "ThreadLengthMin": (
        f"{PRINTED_THREAD} CONTINUOUS TAIL FROM TIP\n"
        "INCOMPLETE CUT-END THREAD 1 PITCH MAX\n"
        "ALL REMAINING TAIL FULL FORM"
    ),
}

# Supplier engineering drawing inspected 2026-10-19. Presentation is separate
# from the exact catalogue dimensions consumed by the stock solid recipe.
SUPPLIER_DRAWING_URL = (
    "https://www.mcmaster.com/mvC/Library/CAD2/20260107/BB28DFA4/"
    "92314A253_18-8%20Stainless%20Steel%20Hex%20Head%20ScrewsX.GIF"
)
SUPPLIER_REFERENCE_DIMENSIONS = {
    "SupplierHeadAF": {
        "units": "in",
        "precision": 0,
        "fraction_denominator": 16,
        "expected_mm": HEAD_AF,
        "callout": "HEAD AF",
    },
    "SupplierHeadHeight": {
        "units": "in",
        "precision": 3,
        "expected_mm": HEAD_H,
        "callout": "HEAD HEIGHT",
    },
    "SupplierThreadMajor": {
        "units": "in",
        "precision": 2,
        "expected_mm": SHANK_DIA,
        "presentation": "diameter",
        "callout": f"{PRINTED_THREAD}\nTHREAD MAJOR NOMINAL",
    },
    "SupplierStockLength": {
        "units": "in",
        "precision": 0,
        "expected_mm": CATALOG_LENGTH,
        "callout": "AS SUPPLIED\nSTOCK UNDER HEAD",
    },
}
# The helical groove need not leave diametrically opposed crests in one view.
# This construction-only chord preserves the same exact nominal as the solid.
SUPPLIER_REFERENCE_SKETCH = (("SupplierThreadMajor", SHANK_DIA, "horizontal"),)
SUPPLIER_REFERENCE_STARTS = {"SupplierThreadMajor": (-SHANK_DIA / 2, LENGTH / 2)}
SUPPLIER_DRAWING_DIMENSIONS = {"SupplierReference": {"SupplierThreadMajor"}}
# Only the finished cuts are suppressed in the drawing-only stock child.
# The factory thread and all finished/simplified configuration states remain.
SUPPLIER_STOCK_CONFIGURATION = "AS SUPPLIED STOCK"
SUPPLIER_STOCK_SUPPRESSED_FEATURES = ("StockDeburr", "StockTrim")
SUPPLIER_STOCK_TITLE = "\n".join((
    f"McMASTER {SKU} HEX HEAD SCREW",
    "AS SUPPLIED STOCK - SUPPLIER REFERENCE ONLY",
    "FITTED LENGTH AND END CONTROLS: SHEET 1",
))
