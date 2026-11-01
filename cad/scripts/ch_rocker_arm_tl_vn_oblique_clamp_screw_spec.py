r"""MHA-CH-06-TL-VN-68 oblique-trammel clamp screw: McMaster 91251A541.

PURE DATA, no SolidWorks/COM calls and no ``build_*`` module in its import
closure.  Shop fixture hardware (cad/docs/subsystem-identities.md), modelled
so the jig assembly can mate it and run native interference: the
``1/4-20 X 7/8 SHCS`` that is the CR clamp: it clamps the rocker-arm strap
and the riser down on the TL-21 carrier, tapped THRU; the head seats on the
rocker-arm strap.  It is the C4 fastener table's ``CR_CLAMP`` row.  It is its
own row on the jig's BOM; the shop inventory carries no screw stock (no
``INVENTORY_ID``), and the assembly steps cite it by item and callout
(``fasteners.callout``).

Used as bought, full length: the tip runs through TL-21's THRU tap and stands
below the carrier's underside (``STAND_OUT_MAX`` worst case).  That is
functional: over both passes' whole sweep the tip stays on the machine's +X
(rail 2) side, away from the leadscrew feed on rail 1 (``TIP_MACHINE_X_MIN``),
and in plan clear of both pivot blocks (``TIP_PLAN_CLEARANCE``), so below the
carrier it passes over rail 2 (``trammel.CARRIER_TO_RAIL_GAP``).  No fit-up
trim.

Sources:

* SOURCED, https://www.mcmaster.com/91251A541/ read live 2026-10-19:
  1/4"-20 UNRC class 3A right hand, 7/8 in under the head, fully threaded,
  head Ø3/8 x 1/4 in, 3/16 in hex, Rockwell C37, 170,000 psi, ASTM A574,
  tip type flat, $13.42 per pack of 50.
* FROM THE FASTENER TABLE (imported): thread, printed length, head, count,
  grip and the joint (``fasteners.CR_CLAMP``); the catalogue's thread and
  length must equal the row's (checked at import).
* STANDARD: the page gives no socket depth, so it is the standard's
  minimum key engagement (``_mcmaster_91251a541``; the 91251A108 convention).
* The geometry is the 91251A family's catalogue recipe
  (``diag_mcmaster_socket_head.build_socket_head``: plain cylindrical head,
  0.75P tip chamfer, 45 deg thread neck); no vendor model was read for this
  size and none is replica-gated (user ruling 2026-10-17).  The recipe is
  ``diagnostics/diag_build_91251A541.py``; its standalone run is
  catalog-only.

Part frame: screw axis local +Y through the origin, published as
``ScrewAxis`` (Front ∩ Right); the bearing face (head underside) at y = 0
(the Top Plane), the tip at y = -LENGTH.  Mate the Top Plane to the head's
seat, the rocker-arm strap.
"""

from __future__ import annotations

import math

import _config
import ch_rocker_arm_spec as rocker
import ch_rocker_arm_tl_oblique_carrier_spec as carrier
import ch_rocker_arm_tl_oblique_fasteners_spec as fasteners
import ch_rocker_arm_tl_oblique_pivot_block_spec as pivot_block
import ch_rocker_arm_tl_oblique_riser_spec as riser
import ch_rocker_arm_tl_oblique_trammel_spec as trammel
from _mcmaster_91251a541 import DIMS, LENGTH_TEXT, PART_NO, THREAD
from _package_units import drawing_unit

UNIT = drawing_unit(
    "parts/ch-rocker-arm-tl-vn-oblique-clamp-screw",
    _config.parts("ch-rocker-arm-tl-vn-oblique-clamp-screw"),
)
SKU = PART_NO
ROW = fasteners.CR_CLAMP
QUANTITY = ROW.count
PACK_QUANTITY = 50  # McMaster sells 91251A541 in packs of 50
CALLOUT = fasteners.callout(ROW)  # "1/4-20 X 7/8 SHCS"
LENGTH = DIMS.length  # 7/8 in, modelled as bought

if (THREAD, LENGTH_TEXT, fasteners.SHCS) != (ROW.thread, ROW.length, ROW.head):
    raise AssertionError(f"{SKU} is not the screw of {ROW.joint}")
if abs(LENGTH - ROW.length_mm) > 1e-9:
    raise AssertionError(f"{SKU}: {LENGTH} long, the row prints {ROW.length_mm}")
if abs(DIMS.major_dia - ROW.major_mm) > 1e-3:
    raise AssertionError(
        f"{SKU}: major {DIMS.major_dia}, the row's thread is {ROW.major_mm}"
    )

# --- Plate bands (upper, lower) ----------------------------------------------
GRIP_MAX = (riser.THICKNESS + riser.THICKNESS_BAND) + (
    rocker.ARM_THICKNESS + rocker.ARM_THICKNESS_BAND[0]
)
GRIP_MIN = (riser.THICKNESS - riser.THICKNESS_BAND) + (
    rocker.ARM_THICKNESS + rocker.ARM_THICKNESS_BAND[1]
)
CARRIER_MIN = carrier.THICKNESS - carrier.THICKNESS_BAND

# --- Rule 18: full thread in TL-21's tap -------------------------------------
# Design math on the family's catalogue limits only.  ASME B18.3, through
# 1 in long: +0/-0.03 in (the 91251A583 precedent).  Rule 18 permits one to
# one-and-a-half incomplete threads: charge 1.5P at the screw's tip.  This is
# the policy convention, not a sourced B18.3 point-length maximum.  The
# screw's reach is the shortest screw through the thickest grip, less the
# tap's mouth break and the incomplete tip; the receiver's own full thread
# (mouth break and 1P exit) is a separate cap.  The two bottom losses sit in
# different places only when the tip is above the exit, so the min takes the
# governing one instead of summing them.
LENGTH_MIN = LENGTH - 0.03 * trammel.INCH
TIP_INCOMPLETE_LENGTH = 1.5 * DIMS.pitch
SCREW_FULL_THREAD_MIN = (
    LENGTH_MIN - GRIP_MAX - carrier.TAP_MOUTH_BREAK - TIP_INCOMPLETE_LENGTH
)
RECEIVER_FULL_THREAD = carrier.ENGAGEMENT_MM[carrier.CR_THREAD]
ENGAGEMENT_MIN = min(SCREW_FULL_THREAD_MIN, RECEIVER_FULL_THREAD)
if ENGAGEMENT_MIN < 1.5 * DIMS.major_dia:
    raise AssertionError(
        f"{SKU}: {ENGAGEMENT_MIN:.3f} full thread in TL-21, under rule 18's 1.5D"
    )

# --- The tip below the carrier ------------------------------------------------
# Nominal and worst-case (longest screw, thinnest grip and carrier) stand-out
# below the carrier's underside.
STAND_OUT_NOMINAL = LENGTH - ROW.grip_mm - carrier.THICKNESS
STAND_OUT_MAX = LENGTH - GRIP_MIN - CARRIER_MIN
# In plan: a circle about each pin hole bounds its pivot block at any yaw
# (the block's farthest corner from its bore); the CR axis's nearest pin hole
# keeps the whole tip outside every such circle.
BLOCK_PLAN_RADIUS = math.hypot(
    max(
        abs(pivot_block.BLOCK_X0 - pivot_block.BORE_X),
        abs(pivot_block.BLOCK_X1 - pivot_block.BORE_X),
    ),
    pivot_block.BLOCK_WIDTH / 2.0,
)
CR_TO_PIN_MIN = min(math.dist(trammel.CR, hole) for hole in trammel.PIN_HOLES.values())
TIP_PLAN_CLEARANCE = CR_TO_PIN_MIN - BLOCK_PLAN_RADIUS - DIMS.major_dia / 2.0
if not TIP_PLAN_CLEARANCE > 0.0:
    raise AssertionError(f"{SKU}: the tip reaches over a pivot block")
# Swept, closed form.  ``trammel.carrier_pose`` turns the carrier by
# phi = theta/2 about the spindle at (R sin theta, R cos theta - H1), so the
# CR axis lands at machine X = a cos(phi) - k sin(phi) = rho cos(phi + beta),
# with (a, b) = CR, k = b + H1 + R, beta = atan2(k, a).  Over a pass,
# phi + beta stays inside (0, pi), where cos falls monotonically: the least X
# is at phi = +SWEEP/2, on the pass with the larger k (the outer).
_CR_X, _CR_Y = trammel.CR
_TIP_X_MIN = []
for _name, _sweep in trammel.SWEEP.items():
    _k = _CR_Y + trammel.H1 + trammel.PASS_RADIUS[_name]
    _beta = math.atan2(_k, _CR_X)
    if not (0.0 < _beta - _sweep / 2.0 and _beta + _sweep / 2.0 < math.pi):
        raise AssertionError(f"{SKU}: the CR sweep is not monotone in machine X")
    _TIP_X_MIN.append(_CR_X * math.cos(_sweep / 2.0) - _k * math.sin(_sweep / 2.0))
TIP_MACHINE_X_MIN = min(_TIP_X_MIN) - DIMS.major_dia / 2.0
# The tip's whole sweep stays at machine +X, rail 2's side; the leadscrew
# feed stands on rail 1 at -X.  Beneath the tip stand only rail 2's parts:
# pivot block 2 (clear above), carriage 2 under it, rail 2's studs (out of
# the tip's path) and rail 2.
if not TIP_MACHINE_X_MIN > 0.0:
    raise AssertionError(f"{SKU}: the tip's sweep crosses to rail 1's side")
if not STAND_OUT_MAX < trammel.CARRIER_TO_RAIL_GAP:
    raise AssertionError(f"{SKU}: the tip reaches rail 2")
if ROW.tip_clearance_mm != trammel.CARRIER_TO_RAIL_GAP:
    raise AssertionError(f"{SKU}: the fastener table's tip clearance is not the rails'")

# Exact-current product table and engineering drawing read 2026-10-21.
# Hidden nominal source references, not physical-edge/replica assertions.
# Drawing precision: length/head Ø/head height/major Ø .XXX,
# drive an exact 3/16 fraction. The standard-only socket depth is omitted.
SUPPLIER_PRODUCT_URL = "https://www.mcmaster.com/91251A541/"
SUPPLIER_DRAWING_URL = (
    "https://www.mcmaster.com/mvC/Library/CAD2/20260108/B9FA8D18/"
    "91251A541_Black-Oxide%20Alloy%20Steel%20Socket%20Head%20ScrewX.GIF"
)
SUPPLIER_REFERENCE_DIMENSIONS = (
    ("SupplierLength", -DIMS.length, "vertical"),
    ("SupplierHeadDiameter", DIMS.head_dia, "horizontal"),
    ("SupplierHeadHeight", DIMS.head_h, "vertical"),
    ("SupplierThreadDiameter", DIMS.major_dia, "horizontal"),
    ("SupplierDriveWidth", DIMS.socket_af, "horizontal"),
)
SUPPLIER_REFERENCE_STARTS = {
    "SupplierLength": (DIMS.major_dia / 2.0, 0.0),
    "SupplierHeadDiameter": (-DIMS.head_dia / 2.0, 0.0),
    "SupplierHeadHeight": (DIMS.head_dia / 2.0, 0.0),
    "SupplierThreadDiameter": (-DIMS.major_dia / 2.0, 0.0),  # on the bearing-face edge
    "SupplierDriveWidth": (-DIMS.socket_af / 2.0, 0.0),
}
SUPPLIER_REFERENCE_PLANES = {
    "SupplierHeadDiameter": "Top",
    "SupplierDriveWidth": "Top",
}
SUPPLIER_REFERENCE_SIDES = {
    "SupplierLength": "right",
    "SupplierHeadDiameter": "top",
    "SupplierHeadHeight": "left",
    "SupplierThreadDiameter": "bottom",
    "SupplierDriveWidth": "bottom",
}
SUPPLIER_REFERENCE_FORMATS = {
    "SupplierLength": (3, "length", None, None),
    "SupplierHeadDiameter": (3, "diameter", None, None),
    "SupplierHeadHeight": (3, "length", None, None),
    "SupplierThreadDiameter": (3, "diameter", None, '1/4"-20'),
    "SupplierDriveWidth": (0, "length", 16, None),
}
