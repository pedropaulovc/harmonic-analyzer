r"""MHA-SM-VN-53 knife-mount-dowel: McMaster 98381A473 stock dowel.

PURE DATA, no SolidWorks/COM calls and no ``build_*`` module in its import
closure.  Four are used, two per knife mount: each is pressed chamfer end
first to the flat floor of a blind ream in the underside of the MHA-FR-02
crossbar, a knockout drilled up from that floor through the faced top on
the ream's drawn axis, and slips, at assembly, into the MHA-SM-02 knife mount's top seat,
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
from _package_units import drawing_unit
from _printed_tolerance import printed_band_mm
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
# The free end, the one that enters the knife mount's hole, is the round
# end: its crown radius, tangent to the diameter, is the length of it that
# keys nothing (codjiflo round 5: not the pressed end's chamfer).
FREE_END_LEN = ENDS.crown_r  # 0.4064
# The pressed end's flat face, the pin's bearing on the ream floor: ASME
# B18.8.2's point diameter for the 1/8 in pin, 0.110-0.120 in (Engineers
# Edge, ASME B18.8.2 machine dowel pin table:
# https://www.engineersedge.com/hardware/machine_dowel_pins_chart_ansi_asme__13076.htm).
# The vendor model's 0.115 in (ENDS.point_dia) is that band's middle.
POINT_DIA_MIN = 0.110 * MM_PER_IN  # 2.794
POINT_DIA_MAX = 0.120 * MM_PER_IN  # 3.048
if not POINT_DIA_MIN <= ENDS.point_dia <= POINT_DIA_MAX:
    raise AssertionError("the vendor model's end flat is outside ASME B18.8.2's band")
# The family's length grade, +/-0.010 in (``_sprocket_seat_geometry``'s
# DRIVE_PIN_LENGTH_GRADE for the same 98381A family).
LENGTH_GRADE = 0.010 * MM_PER_IN  # 0.254

# General tolerances the two holes' printed places claim (title block).
_X = printed_band_mm(1)
_XXX = printed_band_mm(3)

# Two pins per knife mount, their axes HANGER_OFFSET either side of the
# knife-hanger screw axis along machine X in BOTH parts (block local X is
# machine X: the mounts are placed unrotated).  Owner ruling 2026-10-24
# (T+H3, machinist ENFORCE review of MHA-SM-02, rule 16): the pins press
# into the MHA-FR-02 crossbar, each to the floor of a blind ream drilled from
# the underside, a knockout drilled up from its floor through the top, located
# by the drawn common axis only (+/-0.13 implied, owner ruling 2026-10-27
# (c)), and slip
# into the hardened knife mount, one into its round hole (datum B) and the
# other into its slot (datum C), open to the block's -X face.  The crossbar
# prints each +X ream's station .XXX from its screw axis (HANGER_OFFSET_TOL)
# and each -X ream BASIC SPAN from its +X ream under a ⌖Ø0.05 frame (fr-top-
# frame ENFORCE review, farm run 20261027T030041319Z: a frame needs BASIC
# locations), so a mount fitted turned end for end, its round hole on the
# -X pin, still floats inside the crossbar's #10 clearance hole; the block's
# slot takes up the spacing (``fr_top_frame_spec``, ``sm_knife_mount_spec``,
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
# The pair's centre-to-centre span along the dowel line: BASIC on the
# crossbar, within the -X ream's Ø0.05 position zone radius
# (``fr_top_frame_spec.HANGER_PRESS_HOLE_POSITION_TOL``, which asserts it);
# the knife mount's slot takes that variation as travel.
SPAN = 2.0 * HANGER_OFFSET  # 15.264
SPAN_TOL = 0.025

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
# The ream's flat floor ends in a corner radius the depth's callout limits
# (the title block's inside-corner radius would leave the end flat on a
# fillet).  B18.8.2's largest point (1.524 radius) still overhangs the
# floor's flat at the smallest ream and largest corner (1.4825), so its
# edge stands on the fillet and holds the pin that far off the floor,
# longer proud below the underside (PROUD_MAX).
PRESS_FLOOR_CORNER_R_MAX = 0.1


def floor_fillet_seating_lift(flat_r: float, wall_r: float, corner_r: float) -> float:
    """How far a floor's corner fillet holds the pressed end off the floor.

    The end is its flat out to ``flat_r``, then the chamfer cone at
    ``ENDS.chamfer_deg`` to the axis; the floor is flat out to
    ``wall_r - corner_r``, then a ``corner_r`` fillet up to the wall.  The
    lift is the fillet's greatest height over the end's surface."""
    centre = wall_r - corner_r
    rise = 1.0 / math.tan(math.radians(ENDS.chamfer_deg))  # axial per radial
    lift = 0.0
    steps = 4000
    for index in range(steps + 1):
        r = centre + corner_r * index / steps
        fillet = corner_r - math.sqrt(max(corner_r**2 - (r - centre) ** 2, 0.0))
        lift = max(lift, fillet - max(r - flat_r, 0.0) * rise)
    return lift


PRESS_FLOOR_LIFT_MAX = floor_fillet_seating_lift(
    POINT_DIA_MAX / 2.0,
    (PRESS_HOLE_DIA + min(PRESS_HOLE_DIA_BAND)) / 2.0,
    PRESS_FLOOR_CORNER_R_MAX,
)  # 0.0090
if PRESS_FLOOR_LIFT_MAX > 0.02 * PRESS_DEPTH_TOL:
    raise AssertionError(
        f"the ream floor's corner holds the dowel {PRESS_FLOOR_LIFT_MAX:.4f} off its floor"
    )

# --- The slip: the knife mount's round hole and open slot -------------------
# A slip on the pin's catalogue diameter at 0.02..0.10 diametral clearance
# (the dt_pinion_cam_spec slip band), reamed (the round hole, a stock Ø3.25
# metric reamer) or milled (the slot's width) to an explicit +/-0.02 band
# printed .XXX: 0.0474..0.0925.  The band's maximum stays 3.270, so the
# loosest slip (and the rock, bolt-float, web and slot-margin stacks it
# feeds) is unchanged; the tightest slip opens from 0.027 to 0.047 to give
# the pin-to-hole tilt proof real angular margin (codjiflo round 6).
# Cut soft in the O1 block: hardening's growth (<= 0.003 on this size,
# owner ruling 2026-10-24, H3) stays inside the band.
SLIP_HOLE_DIA = 3.25
SLIP_HOLE_DIA_BAND = (0.02, -0.02)
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
# 5.996..8.113, the longest standing on the floor's corner fillet
# (PRESS_FLOOR_LIFT_MAX, codjiflo round 5).
PROUD = proud_length(PRESS_DEPTH)
PROUD_MIN = proud_length(PRESS_DEPTH + PRESS_DEPTH_TOL, -LENGTH_GRADE)
PROUD_MAX = (
    proud_length(PRESS_DEPTH - PRESS_DEPTH_TOL, LENGTH_GRADE) + PRESS_FLOOR_LIFT_MAX
)
# The shallowest knife-mount hole still takes the longest proud pin, or the
# pin would bottom and hold the seat off the casting: 8.7 - 8.113 = 0.587.
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
# The shortest proud pin, less its free (round) end's crown, keys the block
# over at least 1.5 D of full diameter: (5.996 - 0.406) / 3.175 = 1.76 D.
SLIP_ENGAGEMENT_D_MIN = (PROUD_MIN - FREE_END_LEN) / DIA
if SLIP_ENGAGEMENT_D_MIN < PRESS_ENGAGEMENT_MIN_D:
    raise AssertionError(
        f"knife-mount dowel keys the block over {SLIP_ENGAGEMENT_D_MIN:.2f} D"
    )
# Angular fit: these checks treat the pressed pin and the block's hole as
# parallel.  Their relative tilt is bounded by the crossbar ream's and the
# block hole's perpendicularity controls (owner ruling 2026-10-27, #2016
# option A) and proved against the tightest slip in
# ``build_sm_summing_assembly`` (KNIFE_DOWEL_TILT_CHARGED_DEG <
# KNIFE_DOWEL_TILT_ALLOWED_DEG).

# The pin's own sheet unit (#290 drawing_unit): an inch sheet's UNIT: IN
# names the supplier REFs' unit, so they close without the inch suffix.
SHEET_UNIT = drawing_unit("parts/sm-vn-knife-mount-dowel", _config.parts("sm-vn-knife-mount-dowel"))

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
    sheet_unit=SHEET_UNIT,
)
