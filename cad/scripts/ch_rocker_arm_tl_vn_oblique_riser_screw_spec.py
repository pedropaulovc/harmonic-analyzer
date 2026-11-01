r"""MHA-CH-06-TL-VN-67 oblique-trammel riser screw: McMaster 91771A112.

PURE DATA, no SolidWorks/COM calls and no ``build_*`` module in its import
closure.  Shop fixture hardware (cad/docs/subsystem-identities.md), modelled
so the jig assembly can mate it and run native interference: the
``#4-40 X 5/8 FLAT HEAD`` that holds the TL-24 riser to the TL-21 carrier,
tapped THRU; the head seats on the riser's 82 deg countersink.  It is the C4
fastener table's ``RISER_TO_CARRIER`` row.  It is its own row on the jig's
BOM; the shop inventory carries no screw stock (no ``INVENTORY_ID``), and the
assembly steps cite it by item and callout (``fasteners.callout``).

Sources:

* SOURCED, https://www.mcmaster.com/91771A112/ read live 2026-10-19:
  18-8 stainless steel, passivated, Phillips No. 1 drive, standard 82 deg
  flat head Ø0.212 x 0.067 in, #4-40 UNC class 2A, 5/8 in long ("Length is
  measured from the top of the head"), fully threaded, flat tip, Rockwell
  B80, 80,000 psi, ASME B18.6.3, $7.44 per pack of 100.  The page states no
  head-angle or head-diameter tolerance.
* FROM THE FASTENER TABLE (imported): thread, printed length, head, count,
  grip and the joint (``fasteners.RISER_TO_CARRIER``); the catalogue's thread
  and length must equal the row's, and the row's grip must be the nominal
  seat below (checked at import).
* FROM THE CALCULATOR (imported): ``trammel.RISER_SCREW_HEAD_DIA``, the
  B18.6.3 #4 flat head's max sharp Ø0.225 in the riser's countersink is
  sized for; the catalogue head (Ø0.212 in) must not exceed it (checked
  at import).
* ASME B18.6.3 (cited, not re-read here): overall length +0/-0.03 in through
  1 in (``build_pd_platen_clip`` precedent) and a 2P maximum point chamfer,
  §§3.2–3.7 (the sourced ``vn_transgear_arm_plate_screw_spec`` precedent).
* VENDOR MODEL, only where the catalogue is silent (Phillips recess form,
  tip chamfer): the same-family reading of the 1/2 in 91771A110 model
  (``_mcmaster_91771a112`` labels each value and carries its SHA-256); the
  91771A112 model was not measured.  For dimensions only: NOT replica-gated
  (user ruling 2026-10-17).  The recipe is
  ``diagnostics/diag_build_91771A112.py``; its standalone run is
  catalog-only.

Part frame: screw axis local +Y through the origin, published as
``ScrewAxis`` (Front ∩ Right); the flat top at y = 0 (the Top Plane), the tip
at y = -length (McMaster's flat head length is overall).  The assembly sets
the Top Plane ``HEAD_TOP_BELOW_RISER_TOP`` below the riser's top face: the
head's nominal seat in the countersink.  The model is the screw as bought.
"""

from __future__ import annotations

import math

import _config
import ch_rocker_arm_tl_oblique_carrier_spec as carrier
import ch_rocker_arm_tl_oblique_fasteners_spec as fasteners
import ch_rocker_arm_tl_oblique_pivot_block_spec as pivot_block
import ch_rocker_arm_tl_oblique_riser_spec as riser
import ch_rocker_arm_tl_oblique_trammel_spec as trammel
from _mcmaster_91771a112 import DIMS, LENGTH_TEXT, PART_NO, THREAD
from _package_units import drawing_unit

UNIT = drawing_unit(
    "parts/ch-rocker-arm-tl-vn-oblique-riser-screw",
    _config.parts("ch-rocker-arm-tl-vn-oblique-riser-screw"),
)
SKU = PART_NO
ROW = fasteners.RISER_TO_CARRIER
QUANTITY = ROW.count
PACK_QUANTITY = 100  # McMaster sells 91771A112 in packs of 100
CALLOUT = fasteners.callout(ROW)  # "#4-40 X 5/8 B18.6.3 FLAT HEAD"

if (THREAD, LENGTH_TEXT, fasteners.FLAT_HEAD) != (ROW.thread, ROW.length, ROW.head):
    raise AssertionError(f"{SKU} is not the screw of {ROW.joint}")
if abs(DIMS.length - ROW.length_mm) > 1e-9:
    raise AssertionError(f"{SKU}: {DIMS.length} long, the row prints {ROW.length_mm}")
if abs(DIMS.major_dia - ROW.major_mm) > 1e-3:
    raise AssertionError(
        f"{SKU}: major {DIMS.major_dia}, the row's thread is {ROW.major_mm}"
    )
# The head sinks into the countersunk part: its cone must end inside the
# grip, or the head would reach the receiving thread.
if DIMS.junction_depth >= ROW.grip_mm:
    raise AssertionError(f"{SKU}: the head is deeper than the countersunk part")
# The riser's countersink is sized for the calculator's B18.6.3 head (max
# sharp Ø); the catalogue head must not exceed it.
if DIMS.head_dia > trammel.RISER_SCREW_HEAD_DIA:
    raise AssertionError(
        f"{SKU}: head Ø{DIMS.head_dia} over the riser countersink's "
        f"Ø{trammel.RISER_SCREW_HEAD_DIA}"
    )

# --- Nominal seat (the model and the assembly) ------------------------------------
# The catalogue head's 82 deg cone on the riser's 82 deg countersink: the flat
# top (Ø.212 in) sits where the countersink narrows to it,
# (riser.CSK_DIA - Ø.212) / (2 tan 41°) below the riser top.  Nominal geometry
# only: the catalogue gives no head-angle tolerance and none is assumed, so this
# is the modelled seat, not a worst-case bound.  The fastener table's grip is the
# riser less this seat.
HEAD_RECESS_NOMINAL = DIMS.seated_recess(riser.CSK_DIA, riser.CSK_ANGLE)
# The assembly's placement datum: the Top Plane this far below the riser top.
HEAD_TOP_BELOW_RISER_TOP = HEAD_RECESS_NOMINAL
if abs(ROW.grip_mm - (riser.THICKNESS - HEAD_RECESS_NOMINAL)) > 1e-9:
    raise AssertionError(f"{ROW.joint}: the grip is not the head's nominal seat")
TIP_BELOW_RISER_TOP_NOMINAL = HEAD_TOP_BELOW_RISER_TOP + DIMS.length
# Nominal faced parts clear the bought tip: it stops inside the carrier.
TIP_ABOVE_CARRIER_UNDERSIDE_NOMINAL = (
    riser.THICKNESS + carrier.THICKNESS - TIP_BELOW_RISER_TOP_NOMINAL
)
if TIP_ABOVE_CARRIER_UNDERSIDE_NOMINAL <= 0.0:
    raise AssertionError(f"{SKU} stands out of the nominal carrier's underside")

# --- Full-thread engagement, rule 18 (finished .X plate bands, #1619) -----------
# Screw side: the shortest catalogue screw seated no deeper than flush (no
# recess credit) in the thickest riser, less the carrier tap's mouth break
# and the B18.6.3 2P maximum point.
# Receiver side: the thinnest carrier's full thread (carrier.ENGAGEMENT_MM,
# its own mouth and lead losses).  Engagement is the smaller of the two;
# the screw's point and the receiver's losses are separate, not summed.
LENGTH_MIN = DIMS.length - 0.03 * trammel.INCH
POINT_CHAMFER_LENGTH_MAX = 2.0 * DIMS.pitch
ENGAGEMENT_REQUIRED = 1.5 * ROW.major_mm
RECEIVER_FULL_THREAD_MIN = carrier.ENGAGEMENT_MM[carrier.RISER_THREAD]
SCREW_FULL_THREAD_REACH_MIN = (
    LENGTH_MIN
    - (riser.THICKNESS + riser.THICKNESS_BAND)
    - carrier.TAP_MOUTH_BREAK
    - POINT_CHAMFER_LENGTH_MAX
)
ENGAGEMENT_MIN = min(SCREW_FULL_THREAD_REACH_MIN, RECEIVER_FULL_THREAD_MIN)
if ENGAGEMENT_MIN < ENGAGEMENT_REQUIRED:
    raise AssertionError(f"{SKU}: {ENGAGEMENT_MIN:.3f} full thread is under 1.5D")

# --- Below the carrier: the factory tip is never trimmed ------------------------
# The longest screw at the nominal seat in the thinnest plates may reach just
# past the carrier underside; on nominal plates it stops short of it
# (TIP_ABOVE_CARRIER_UNDERSIDE_NOMINAL). No tip is shortened. The checks below
# cover the pivot-block footprints; they are not a whole-fixture clearance
# proof. The retention caps sit above the block tops, and the assembly's
# complete material envelopes and installed tooling acceptance remain
# authoritative.
STAND_OUT_MAX_NOMINAL_SEAT = (
    DIMS.length
    + HEAD_RECESS_NOMINAL
    - (riser.THICKNESS - riser.THICKNESS_BAND)
    - (carrier.THICKNESS - carrier.THICKNESS_BAND)
)
# A block's plan corner farthest from its bore (the pin axis).
PIVOT_BLOCK_PLAN_RADIUS = max(
    math.hypot(x - pivot_block.BORE_X, pivot_block.BLOCK_WIDTH / 2.0)
    for x in (pivot_block.BLOCK_X0, pivot_block.BLOCK_X1)
)
PIVOT_BLOCK_PLAN_CLEARANCE = (
    min(
        math.dist(axis, pin)
        for axis in trammel.RISER_SCREWS
        for pin in trammel.PIN_HOLES.values()
    )
    - PIVOT_BLOCK_PLAN_RADIUS
    - DIMS.major_dia / 2.0
)
if PIVOT_BLOCK_PLAN_CLEARANCE <= 0.0:
    raise AssertionError(f"{SKU}: a riser screw tip lies over a pivot block")
if STAND_OUT_MAX_NOMINAL_SEAT >= trammel.CARRIER_TO_RAIL_GAP:
    raise AssertionError(f"{SKU}: a riser screw tip reaches the rails")
if STAND_OUT_MAX_NOMINAL_SEAT >= trammel.PIVOT_SUPPORT_HEIGHT:
    raise AssertionError(f"{SKU}: a riser screw tip reaches the pivot block tops")

# Exact-current product table and engineering drawing read 2026-10-21.
# Hidden nominal source references, not physical-edge/replica assertions.
# Only the sizes needed to buy a replacement: length (OVERALL, from head top
# Y=0 to the factory tip), head diameter (the riser countersink's fit) and
# thread. The 82 deg head angle and head height follow from the B18.6.3 flat
# head in the callout; they are not authored, because the drawing view shows
# every reference line it dimensions from, printed or not.
# Source decimals have three places. Phillips No. 1 is nonnumeric metadata;
# no recess size/depth is invented.
SUPPLIER_PRODUCT_URL = "https://www.mcmaster.com/91771A112/"
SUPPLIER_DRAWING_URL = (
    "https://www.mcmaster.com/mvC/Library/CAD2/20260324/D7F7176D/"
    "91771A112_Passivated%2018-8%20Stainless%20Steel%20Phillips%20Flat%20Head%20ScrewX.GIF"
)
SUPPLIER_REFERENCE_DIMENSIONS = (
    ("SupplierLength", -DIMS.length, "vertical"),
    ("SupplierHeadDiameter", DIMS.head_dia, "horizontal"),
    ("SupplierThreadDiameter", DIMS.major_dia, "horizontal"),
)
SUPPLIER_REFERENCE_STARTS = {
    "SupplierLength": (DIMS.major_dia / 2.0, 0.0),
    "SupplierHeadDiameter": (-DIMS.head_dia / 2.0, 0.0),
    "SupplierThreadDiameter": (-DIMS.major_dia / 2.0, -DIMS.length / 2.0),
}
SUPPLIER_REFERENCE_PLANES = {"SupplierHeadDiameter": "Top"}
SUPPLIER_REFERENCE_SIDES = {
    "SupplierLength": "right",
    "SupplierHeadDiameter": "top",
    "SupplierThreadDiameter": "bottom",
}
SUPPLIER_REFERENCE_FORMATS = {
    "SupplierLength": (3, "length", None, None),
    "SupplierHeadDiameter": (3, "diameter", None, "PHILLIPS NO. 1"),
    "SupplierThreadDiameter": (3, "diameter", None, "#4-40"),
}
