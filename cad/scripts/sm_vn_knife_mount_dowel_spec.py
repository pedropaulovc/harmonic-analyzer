r"""MHA-SM-VN-53 knife-mount-dowel: McMaster 98381A473 stock dowel.

PURE DATA, no SolidWorks/COM calls and no ``build_*`` module in its import
closure.  Four are used, two per knife mount: each is pressed chamfer end
first to the flat floor of a blind ream in the underside of the MHA-FR-02
crossbar, a knockout drilled through from the crossbar's faced top to that
floor, and slips, at assembly, into the MHA-SM-02 knife mount's top seat,
one into a round hole, the other into a slot open to the block's -X face
(owner ruling 2026-10-24, T+H3: the press and its way out live in the soft
casting, the hardened block carries only slip bands).  The pair keys the
block against turning about its #10-24 knife-hanger hex bolt (MHA-SM-VN-52):
the bolt clamps the seat to the casting underside, the pins react the torque
and hold the block's yaw.

Catalogue: 1/8 x 3/4 alloy-steel dowel, Round x Chamfer ends, diameter
+0.0001/+0.0003 in, Rockwell C47 min, ASME B18.8.2; the size row, the end
forms (read off the vendor model ``cad/references/mcmaster/98381A473.SLDPRT``)
and the diameter band are ``_mcmaster_98381a473``'s.  No
recommended hole size is stated; this module owns both holes' sizes.

This module owns the pin's interface between the two parts it joins: the
station of its axis from the screw axis, the press ream, its depth and the
knife mount's slip hole and depth, as ``dt_vn_crank_seat_drive_pin_spec``
owns its press depth for ``dt_crankshaft_spec``.

Part frame: axis local +Y through the origin; the pressed (chamfered) end
face at y = 0, the rounded lead end at y = LENGTH.  The Front and Right
Planes contain the axis, published as ``ScrewAxis`` (Front x Right); the Top
Plane is the pressed end face, so an assembly places the pin by that plane
on the crossbar ream's floor.
"""

from __future__ import annotations

import math

import _config
from _mcmaster_98381a473 import (
    DIA_BAND_IN,
    ENDS,
    DOWEL_SIZE,
    MM_PER_IN,
)
from _supplier_pin_data import SupplierPinReference

SKU = "98381A473"
DIA, LENGTH = DOWEL_SIZE  # 3.175 x 19.05
# Catalogue diameter band over nominal, mm, as (upper, lower) deviations:
# +0.00762 / +0.00254 (the catalogue row lists it low-first).
DIA_BAND = tuple(band * MM_PER_IN for band in reversed(DIA_BAND_IN))
DIA_MAX = DIA + max(DIA_BAND)  # 3.18262
DIA_MIN = DIA + min(DIA_BAND)  # 3.17754
# The pressed end's chamfer: the length of it that grips nothing.
CHAMFER_LEN = ENDS.chamfer_len(DIA)  # 0.443
# The family's length grade, +/-0.010 in (``_sprocket_seat_geometry``'s
# DRIVE_PIN_LENGTH_GRADE for the same 98381A family).
LENGTH_GRADE = 0.010 * MM_PER_IN  # 0.254

# General tolerances the two holes' printed places claim (title block).
_X = float(str(_config.title_block("linear_1pl")["display"]).lstrip("\u00b1"))
_XXX = float(str(_config.title_block("linear_3pl")["display"]).lstrip("\u00b1"))

# Two pins per knife mount, their axes HANGER_OFFSET either side of the
# knife-hanger screw axis along machine X in BOTH parts (block local X is
# machine X: the mounts are placed unrotated).  Owner ruling 2026-10-24
# (T+H3, machinist ENFORCE review of MHA-SM-02, rule 16): the pins press
# into the MHA-FR-02 crossbar, each to the floor of a blind ream drilled from
# the underside with a knockout drilled through from the faced top, and slip
# into the hardened knife mount, one into its round hole (datum B) and the
# other into its slot (datum C), open to the block's -X face.  The crossbar
# prints each ream's station .XXX from its screw axis (HANGER_OFFSET_TOL),
# so a mount fitted turned end for end, its round hole on the -X pin, keeps
# the same float; the block's slot takes up the spacing, the crossbar's #10
# clearance hole the rest (``fr_top_frame_spec``, ``sm_knife_mount_spec``,
# ``build_sm_summing_assembly``).
PER_MOUNT = 2
MOUNTS = 2
QUANTITY = PER_MOUNT * MOUNTS
# 7.632 for the #10-24 hex bolt that replaced the #6-32 screw (the user's
# knife-hanger regression fix): the crossbar's Ø6.045 #10 loose clearance
# hole, drilled from the underside under a shallow top spotface, and its then
# slot, shortened to 3.95, each kept 2.0 of wall at the print-worst plus
# drill drift, inside to the hole and outside to the 25 crossbar's face; the
# block widened to 25.4 so its then pressed -X dowel kept 2.0 to the far
# face round the 15.264 BASIC span.  T+H3 moves the slot to the block and
# the press to the crossbar's reams (``build_fr_top_frame``'s ream walls,
# ``sm_knife_mount_spec``'s slot webs).  History: 7.100, not the
# original 1/4 in, because at 6.350 the crossbar's blind slot left under 2.0
# of wall to the then #6 clearance hole at the print-worst plus drill drift
# (codex machinist review of fr_top_frame 4d11a94e); Q7 option C, approved as
# built by the user 2026-10-13 (#1348): 14.200 BASIC span, 24 crossbar, 25
# block, Ø4.699 #6 hole drilled from the underside.
HANGER_OFFSET = 7.632
HANGER_OFFSET_PLACES = 3
HANGER_OFFSET_TOL = _XXX  # 0.13
# The pair's centre-to-centre span along the dowel line: each crossbar ream
# stands .XXX from its screw axis, so the span spreads by both bands; the
# knife mount's slot takes that variation as travel.
SPAN = 2.0 * HANGER_OFFSET  # 15.264
SPAN_TOL = 2.0 * HANGER_OFFSET_TOL  # 0.26

# --- The press: the crossbar's blind reams (owner ruling 2026-10-24, T+H3) --
# Reamed from the faced underside to a flat floor, printed .X, the pin
# pressed chamfer end first onto it.
PRESS_DEPTH = 12.0
PRESS_DEPTH_PLACES = 1
PRESS_DEPTH_TOL = _X  # 0.8
# The ream's explicit band, printed at three places: its mate and press are
# the callout's (rule 4), the MHA-PD-18 latch-pin precedent.
PRESS_HOLE_DIA = DIA  # 3.175
PRESS_HOLE_DIA_BAND = (0.0, -0.010)  # (upper, lower)
PRESS_HOLE_DIA_PLACES = 3
# (loosest, tightest) press from the ream band and the catalogue band:
# 0.00254..0.01762, printed rounded outward to four places.
PRESS_INTERFERENCE = (
    round(DIA_MIN - (PRESS_HOLE_DIA + max(PRESS_HOLE_DIA_BAND)), 6),
    round(DIA_MAX - (PRESS_HOLE_DIA + min(PRESS_HOLE_DIA_BAND)), 6),
)
if PRESS_INTERFERENCE[0] <= 0.0:
    raise AssertionError("the crossbar dowel ream loses MHA-SM-VN-53's press")
PRESS_INTERFERENCE_PRINTED = (
    math.floor(PRESS_INTERFERENCE[0] * 1e4) / 1e4,
    math.ceil(PRESS_INTERFERENCE[1] * 1e4) / 1e4,
)
if PRESS_INTERFERENCE_PRINTED != (0.0025, 0.0177):
    raise AssertionError(f"knife-mount dowel press prints {PRESS_INTERFERENCE_PRINTED}")

# --- The slip: the knife mount's round hole and open slot -------------------
# A slip on the pin's catalogue diameter at 0.02..0.10 diametral clearance
# (the dt_pinion_cam_spec slip band), reamed (the round hole) or milled (the
# slot's width) to an explicit +/-0.03 band printed .XXX: 0.0274..0.0925.
# Cut soft in the O1 block: hardening's growth (<= 0.003 on this size,
# owner ruling 2026-10-24, H3) stays well inside the band.
SLIP_HOLE_DIA = 3.24
SLIP_HOLE_DIA_BAND = (0.03, -0.03)
SLIP_HOLE_DIA_PLACES = 3
SLIP_CLEARANCE_MIN = round(SLIP_HOLE_DIA + SLIP_HOLE_DIA_BAND[1] - DIA_MAX, 6)
SLIP_CLEARANCE_MAX = round(SLIP_HOLE_DIA + SLIP_HOLE_DIA_BAND[0] - DIA_MIN, 6)
if SLIP_CLEARANCE_MIN < 0.02 or SLIP_CLEARANCE_MAX > 0.10:
    raise AssertionError(
        f"knife-mount dowel slip clearance {SLIP_CLEARANCE_MIN}-"
        f"{SLIP_CLEARANCE_MAX} is outside 0.02-0.10"
    )
# The block's round hole and slot, blind from its top seat, printed .X.
SLIP_DEPTH = 9.5
SLIP_DEPTH_PLACES = 1
SLIP_DEPTH_TOL = _X  # 0.8
# A press-fit dowel grips at least 1.5 D (the drawing-guidelines.md rule 18 (thread engagement) engagement floor,
# applied to the press as ``pd_vn_transgear_latch_pin_spec`` does), counted over
# the full diameter only: the chamfer inside the hole carries no interference.
PRESS_ENGAGEMENT_MIN_D = 1.5


def proud_length(hole_depth: float, length_dev: float = 0.0) -> float:
    """The pin's length out of the crossbar's underside when it is pressed
    to the floor of a blind ream ``hole_depth`` deep, the pin ``length_dev``
    off its nominal length."""
    return LENGTH + length_dev - hole_depth


def press_engagement_d(hole_depth: float) -> float:
    """Full-diameter press engagement, in D, of the pin bottomed in a blind
    hole ``hole_depth`` deep."""
    return (hole_depth - CHAMFER_LEN) / DIA


# The seat is clamped to the casting underside (no gap), so the pin's proud
# length goes straight down the knife mount's hole: 7.05 nominal,
# 5.996..8.104.
PROUD = proud_length(PRESS_DEPTH)
PROUD_MIN = proud_length(PRESS_DEPTH + PRESS_DEPTH_TOL, -LENGTH_GRADE)
PROUD_MAX = proud_length(PRESS_DEPTH - PRESS_DEPTH_TOL, LENGTH_GRADE)
# The shallowest knife-mount hole still takes the longest proud pin, or the
# pin would bottom and hold the seat off the casting: 8.7 - 8.104 = 0.596.
SLIP_DEPTH_CLEARANCE_MIN = SLIP_DEPTH - SLIP_DEPTH_TOL - PROUD_MAX
if SLIP_DEPTH_CLEARANCE_MIN <= 0.0:
    raise AssertionError(
        f"the longest proud knife-mount dowel ({PROUD_MAX:.3f}) bottoms in the"
        f" shallowest knife-mount hole ({SLIP_DEPTH - SLIP_DEPTH_TOL:.3f})"
    )
# (11.2 - 0.443) / 3.175 = 3.39 D at the shallowest printed press depth.
PRESS_ENGAGEMENT_D_MIN = press_engagement_d(PRESS_DEPTH - PRESS_DEPTH_TOL)
if PRESS_ENGAGEMENT_D_MIN < PRESS_ENGAGEMENT_MIN_D:
    raise AssertionError(
        f"knife-mount dowel grips {PRESS_ENGAGEMENT_D_MIN:.2f} D in the crossbar,"
        f" under {PRESS_ENGAGEMENT_MIN_D} D"
    )
# The shortest proud pin, less its free end's chamfer, keys the block over
# at least 1.5 D of full diameter: (5.996 - 0.443) / 3.175 = 1.75 D.
SLIP_ENGAGEMENT_D_MIN = (PROUD_MIN - CHAMFER_LEN) / DIA
if SLIP_ENGAGEMENT_D_MIN < PRESS_ENGAGEMENT_MIN_D:
    raise AssertionError(
        f"knife-mount dowel keys the block over {SLIP_ENGAGEMENT_D_MIN:.2f} D"
    )

# McMaster engineering drawing inspected 2026-10-19; supplier information
# only. Installation/finished controls above are intentionally unchanged.
SUPPLIER_REFERENCE = SupplierPinReference(
    sku=SKU,
    units="in",
    diameter_mm=DIA,
    length_mm=LENGTH,
    diameter_nominal=0.1250,
    diameter_precision=4,
    length_precision=2,
    diameter_band=(0.0001, 0.0003),
)
