r"""MHA-CH-06-TL-VN-86 oblique-trammel left clamp screw: McMaster 92220A165.

PURE DATA, no SolidWorks/COM calls and no ``build_*`` module in its import
closure.  Shop fixture hardware (cad/docs/subsystem-identities.md), modelled
so the jig assembly can mate it and run native interference: the
``#10-24 X 3/4 LOW-HEAD SHCS`` that holds the MHA-CH-13 strap blank's
outboard left tail down through the TL-24 riser into TL-21's flat-bottom
blind tap; the low head seats directly on the strap.  It is the C4 fastener
table's ``LEFT_CLAMP`` row.  It is its own row on the jig's BOM; the shop
inventory carries no screw stock (no ``INVENTORY_ID``), and the assembly
steps cite it by item and callout (``fasteners.callout``).

Cut to fit: the carrier's receiver is blind (owner requirement), so each
screw is cut at assembly to the actual riser-plus-strap grip plus the
``fasteners.LEFT_CLAMP_INSERTION`` reach below the carrier top, and its cut
tip is chamfered 45 deg, ``fasteners.LEFT_CLAMP_TIP_CHAMFER`` long along the
axis.  Both are controlled because the receiver's full thread is guaranteed
only to its .310 MIN: the screw's full-form thread ends where the chamfer
starts, so the deepest insertion with the SHORTEST chamfer bounds the runout
and the shallowest insertion with the LONGEST chamfer bounds the engagement.

The chamfer is a model-owned manufacturing control, not catalogue data: the
builder cuts it natively (``TipChamferProfile``: a driving axial
``ChamferLength`` at the band's .035 maximum with its -.005 band, and a
driving 45 deg ``ChamferAngle`` on the title block's angular row), and the
sheet imports both associatively.  The cut length stays a fit-up reference
(rule 19): the solid is the screw as installed at the nominal grip and the
insertion window's middle, ``CUT_LENGTH`` under the head; the as-supplied
3/4 in is a separate stock witness beside the solid (the TL-VN-64 idiom).

Sources:

* SOURCED, https://www.mcmaster.com/92220A165/ read live 2026-11-06:
  #10-24 UNC class 3A right hand, 3/4 in under the head, fully threaded,
  low head Ø5/16 x 3/32 in, 3/32 in hex, 140,000 psi, Rockwell C39,
  ASME B18.3, flat tip, black oxide, $11.38 per pack of 50.
* FROM THE FASTENER TABLE (imported): thread, printed length, head, count,
  grip, cut length and the joint (``fasteners.LEFT_CLAMP``); the catalogue's
  thread and length must equal the row's (checked at import).
* STANDARD: the page gives no socket depth, so it is ASME B18.3's minimum
  key engagement for the #10 low head (``_mcmaster_92220a165``).
* The geometry is the 91251A family's catalogue recipe
  (``diag_mcmaster_socket_head.build_socket_head``); no vendor model was read
  and none is replica-gated (user ruling 2026-10-17).  The recipe is
  ``diagnostics/diag_build_92220A165.py``; its standalone run is
  catalog-only.

Part frame: screw axis local +Y through the origin, published as
``ScrewAxis`` (Front ∩ Right); the bearing face (head underside) at y = 0
(the Top Plane), the cut tip at y = -CUT_LENGTH.  Mate the Top Plane to the
head's seat, the strap's top face.
"""

from __future__ import annotations

import math

import _config
import ch_rocker_arm_tl_oblique_carrier_spec as carrier
import ch_rocker_arm_tl_oblique_fasteners_spec as fasteners
from _mcmaster_92220a165 import DIMS, LENGTH_TEXT, PART_NO, THREAD
from _package_units import drawing_unit
from _printed_tolerance import angular_band_deg, printed_band_mm

STEM = "ch-rocker-arm-tl-vn-oblique-left-clamp-screw"
UNIT = drawing_unit(f"parts/{STEM}", _config.parts("ch-rocker-arm-tl-vn-oblique-left-clamp-screw"))

SKU = PART_NO
ROW = fasteners.LEFT_CLAMP
QUANTITY = ROW.count
PACK_QUANTITY = 50  # McMaster sells 92220A165 in packs of 50
CALLOUT = fasteners.callout(ROW)  # "#10-24 X 3/4 LOW-HEAD SHCS"

if (THREAD, LENGTH_TEXT, fasteners.LOW_HEAD) != (ROW.thread, ROW.length, ROW.head):
    raise AssertionError(f"{SKU} is not the screw of {ROW.joint}")
if abs(DIMS.length - ROW.length_mm) > 1e-9:
    raise AssertionError(f"{SKU}: {DIMS.length} long, the row prints {ROW.length_mm}")
if abs(DIMS.major_dia - ROW.major_mm) > 1e-3:
    raise AssertionError(
        f"{SKU}: major {DIMS.major_dia}, the row's thread is {ROW.major_mm}"
    )
CUT_LENGTH = ROW.cut_length_mm  # nominal grip + the insertion window's middle
CUT_INSERTION = fasteners.LEFT_CLAMP_INSERTION  # tip reach below TL-21's top
if not 0.0 < CUT_LENGTH < DIMS.length:
    raise AssertionError(f"{SKU}: a {CUT_LENGTH} mm cut is not inside the bought screw")

# --- The restored tip: model-owned controls ------------------------------------
# The recipe (diag_mcmaster_socket_head) builds the screw at CUT_LENGTH with
# its own 0.75P 45 deg tip chamfer; the builder's native TipChamfer cut then
# re-cuts the tip to ChamferLength, which must contain the recipe's chamfer so
# the native dimension, not the recipe, defines the finished tip.
TIP_CHAMFER = fasteners.LEFT_CLAMP_TIP_CHAMFER  # (min, max) axial length
TIP_CHAMFER_LENGTH = TIP_CHAMFER[1]  # the modelled nominal: the band's .035 max
TIP_CHAMFER_BAND = (0.0, TIP_CHAMFER[0] - TIP_CHAMFER[1])  # upper, lower: .030-.035
TIP_CHAMFER_ANGLE = 45.0  # driving, between the cut end face and the chamfer
TIP_CHAMFER_ANGLE_TOLERANCE = angular_band_deg(unit=UNIT)  # title-block row
TIP_CHAMFER_FEATURE = "TipChamferProfile"
if not DIMS.tip_chamfer <= TIP_CHAMFER_LENGTH:
    raise AssertionError(f"{SKU}: the native tip chamfer must contain the recipe's")
# The chamfer's radial leg at the steepest permitted angle still leaves a flat
# cut end, and at the shallowest it passes under the tap drill (so the crest
# is gone well before the chamfer's end).
_ANGLE_MIN = math.radians(TIP_CHAMFER_ANGLE - TIP_CHAMFER_ANGLE_TOLERANCE)
_ANGLE_MAX = math.radians(TIP_CHAMFER_ANGLE + TIP_CHAMFER_ANGLE_TOLERANCE)
if not TIP_CHAMFER[1] / math.tan(_ANGLE_MIN) < DIMS.major_dia / 2.0:
    raise AssertionError(f"{SKU}: the tip chamfer consumes the whole cut end")
if not DIMS.major_dia / 2.0 - TIP_CHAMFER[0] / math.tan(_ANGLE_MAX) < (
    carrier.LEFT_CLAMP_TAP_DRILL / 2.0
):
    raise AssertionError(f"{SKU}: the tip chamfer does not pass under the tap drill")

# --- Rule 18 and the blind receiver: full-form thread, from the geometry -------
# External: the recipe sweeps one uniform groove from the tip up to the neck,
# so above the chamfer every crest stands at the major (full form) and inside
# it each crest is truncated to the 45 deg cone.  The full-form thread
# therefore ends exactly ChamferLength above the cut end.  Under the head the
# 45 deg neck cone (``DIMS.neck_h``) is the run-up; it lies inside the grip.
# Internal: full form is guaranteed from TL-21's top to
# LEFT_CLAMP_THREAD_DEPTH (.310 MIN), less the mouth's TAP_MOUTH_BREAK; past
# it the bottoming tap's chamfered lead (STANDARD, ASME B94.9: a bottoming
# chamfer spans 1 to 2 threads; the carrier reserves at least one pitch for
# it) cuts an incomplete thread whose root falls from the major to the tap
# drill no faster than over one pitch.
# No interference past the internal full form: where the screw's full form
# ends at or above the internal's, the screw crest falls from the major at the
# chamfer's radial slope (at least 1/tan(45 deg + band)) while the internal
# root falls at the lead's (at most (major - drill) / 2 per pitch), so the
# crest stays inside the incomplete root all the way to the floor.  Nothing
# here waives incomplete thread: engagement counts only the full form above.
CHAMFER_RADIAL_SLOPE_MIN = 1.0 / math.tan(_ANGLE_MAX)
LEAD_ROOT_SLOPE_MAX = (DIMS.major_dia - carrier.LEFT_CLAMP_TAP_DRILL) / 2.0 / DIMS.pitch
if not LEAD_ROOT_SLOPE_MAX < CHAMFER_RADIAL_SLOPE_MIN:
    raise AssertionError(f"{SKU}: the tip chamfer is shallower than the tap's lead")
# Runout: the deepest insertion with the shortest chamfer.
FULL_THREAD_END_MAX = CUT_INSERTION[1] - TIP_CHAMFER[0]
if FULL_THREAD_END_MAX > carrier.LEFT_CLAMP_THREAD_DEPTH:
    raise AssertionError(f"{SKU}: the screw's full thread runs past TL-21's full thread")
# Engagement: the shallowest insertion with the longest chamfer, less the
# mouth break; the neck cone lies inside the grip, clear of the receiver.
SCREW_FULL_THREAD_MIN = CUT_INSERTION[0] - TIP_CHAMFER[1] - carrier.TAP_MOUTH_BREAK
ENGAGEMENT_MIN = min(SCREW_FULL_THREAD_MIN, carrier.LEFT_CLAMP_FULL_THREAD_MIN)
if ENGAGEMENT_MIN < ROW.min_engagement_d * DIMS.major_dia:
    raise AssertionError(
        f"{SKU}: {ENGAGEMENT_MIN:.3f} full thread in TL-21, under rule 18's 1.5D"
    )
if DIMS.neck_h >= ROW.grip_mm:
    raise AssertionError(f"{SKU}: the thread run-up under the head reaches TL-21")
# The model's own full thread (nominal grip, window middle, native chamfer).
MODEL_FULL_THREAD_END = CUT_LENGTH - ROW.grip_mm - TIP_CHAMFER_LENGTH
_MODEL_FULL_THREAD_MIN = SCREW_FULL_THREAD_MIN + carrier.TAP_MOUTH_BREAK
if not _MODEL_FULL_THREAD_MIN <= MODEL_FULL_THREAD_END <= FULL_THREAD_END_MAX:
    raise AssertionError(f"{SKU}: the installed model's thread end is outside the bounds")
# The pilot's depth carries the .XX band; the tip stays above its shallowest.
PILOT_DEPTH_MIN = carrier.LEFT_CLAMP_DRILL_DEPTH - printed_band_mm(2, unit=carrier.UNIT)
if not CUT_INSERTION[1] < PILOT_DEPTH_MIN:
    raise AssertionError(f"{SKU}: the cut tip reaches TL-21's flat pilot floor")

# --- The cut end's native manufacturing controls (sheet 1, *Front) -------------
# Marked, toleranced and printed from the part: ChamferLength's bilateral
# -.005/0 at .035 (swTolBILAT) and the driving 45 deg on the title block's
# angular row (swTolGeneral keeps the band natively, prints none).
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    TIP_CHAMFER_FEATURE: {"ChamferLength", "ChamferAngle"},
}
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    TIP_CHAMFER_FEATURE: {"ChamferLength": 3, "ChamferAngle": 0},
}
DIMENSION_PRECISION: dict[str, int] = DRAWING_PRECISION[TIP_CHAMFER_FEATURE]
DIMENSION_TOLERANCE_TYPES: dict[str, int] = {
    "ChamferLength": 2,  # swTolBILAT
    "ChamferAngle": 11,  # swTolGeneral
}
CARRIER_NUMBER = _config.parts("ch-rocker-arm-tl-oblique-carrier")["number"]
# Rule 4 and rule 12: the band names its mate and both of its reasons, in
# rows no wider than the stock length's qualifier.
DIMENSION_CALLOUTS: dict[str, str] = {
    "ChamferLength": (
        "AXIAL CUT-END CHAMFER\n"
        "MIN: FULL THREAD ENDS\n"
        f"IN {CARRIER_NUMBER} TAP\n"
        "MAX: 1.5D FULL THREAD"
    ),
}

# Exact-current product table and engineering drawing read 2026-11-06.
# Hidden nominal source references, not physical-edge/replica assertions.
# The installed screw is cut to fit: its length on the solid prints as a
# reference (CutLength), and the as-supplied 3/4 in is a SEPARATE stock
# witness left of the solid, labelled as stock.  The thread Ø's chord lies on
# the cut end, not across the shank.  The standard-only socket depth is
# omitted.
SUPPLIER_PRODUCT_URL = "https://www.mcmaster.com/92220A165/"
SUPPLIER_DRAWING_URL = (
    "https://www.mcmaster.com/mvC/Library/CAD2/20260806/77F91D12/"
    "92220A165_Alloy%20Steel%20Low-Profile%20Socket%20Head%20ScrewX.GIF"
)
SUPPLIER_REFERENCE_DIMENSIONS = (
    ("CutLength", -CUT_LENGTH, "vertical"),
    ("SupplierLength", -DIMS.length, "vertical"),
    ("SupplierHeadDiameter", DIMS.head_dia, "horizontal"),
    ("SupplierHeadHeight", DIMS.head_h, "vertical"),
    ("SupplierThreadDiameter", DIMS.major_dia, "horizontal"),
    ("SupplierDriveWidth", DIMS.socket_af, "horizontal"),
)
SUPPLIER_REFERENCE_STARTS = {
    "CutLength": (DIMS.major_dia / 2.0, 0.0),
    "SupplierLength": (-DIMS.major_dia / 2.0, 0.0),
    "SupplierHeadDiameter": (-DIMS.head_dia / 2.0, 0.0),
    "SupplierHeadHeight": (DIMS.head_dia / 2.0, 0.0),
    "SupplierThreadDiameter": (-DIMS.major_dia / 2.0, -CUT_LENGTH),
    "SupplierDriveWidth": (-DIMS.socket_af / 2.0, 0.0),
}
SUPPLIER_REFERENCE_PLANES = {
    "SupplierHeadDiameter": "Top",
    "SupplierDriveWidth": "Top",
}
SUPPLIER_REFERENCE_SIDES = {
    "CutLength": "right",
    "SupplierLength": "left",
    "SupplierHeadDiameter": "top",
    "SupplierHeadHeight": "left",
    "SupplierThreadDiameter": "bottom",
    "SupplierDriveWidth": "bottom",
}
SUPPLIER_REFERENCE_FORMATS = {
    "CutLength": (2, "length", None, "CUT TO FIT"),
    "SupplierLength": (0, "length", 4, "AS-SUPPLIED STOCK LENGTH"),
    "SupplierHeadDiameter": (0, "diameter", 16, None),
    "SupplierHeadHeight": (0, "length", 32, None),
    "SupplierThreadDiameter": (3, "diameter", None, "#10-24"),
    "SupplierDriveWidth": (0, "length", 32, None),
}
