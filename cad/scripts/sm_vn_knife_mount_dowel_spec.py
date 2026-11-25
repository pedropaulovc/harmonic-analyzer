r"""MHA-SM-VN-53 knife-mount-dowel: McMaster 98381A473 stock dowel.

PURE DATA, no SolidWorks/COM calls and no ``build_*`` module in its import
closure.  Two are used, one per knife mount: each is pressed chamfer end
first into a blind ream in the underside of the MHA-FR-02 crossbar, drilled
and reamed to a drill point, until it stands PROUD of the underside (set at
MHA-SM-00 step 1, never by bottoming: owner decision 2026-11-19, #3124
item 3), a knockout drilled up from the point through the faced top on the
ream's drawn axis, and slips, at assembly, into the MHA-SM-02 knife
mount's round hole (datum B) in its top seat (owner ruling 2026-10-24,
T+H3: the press and its way out live in the soft casting, the hardened
block carries only slip bands).  Owner ruling 2026-11-08 (Pedro), #2144
item 11.3 (scheme S1): one dowel and the #10-24 knife-hanger hex bolt
(MHA-SM-VN-52) hang each block; the bolt clamps the seat to the casting
underside, the pin locates it, and the block's yaw about the pin is set at
MHA-SM-00: the front block's by a (Ø.49) gauge bar slid through both
mounts' bores while its bolt is tightened (step 5), the rear block's by the
rock gauge (6G) before its bolt is tightened (6H).

Catalogue: 1/8 x 3/4 alloy-steel dowel, Round x Chamfer ends, diameter
+0.0001/+0.0003 in, Rockwell C47 min, ASME B18.8.2; the size row, the end
forms (read off the vendor model ``cad/references/mcmaster/98381A473.SLDPRT``)
and the diameter band are ``_mcmaster_98381a473``'s.  No
recommended hole size is stated; this module owns both holes' sizes.

This module owns the pin's interface between the two parts it joins: the
station of its axis from the screw axis, the press ream, its depth, the
proud the pin is pressed to and the knife mount's slip hole and depth, as
``dt_vn_crank_seat_drive_pin_spec`` owns its press depth for
``dt_crankshaft_spec``.

Part frame: axis local +Y through the origin; the pressed (chamfered) end
face at y = 0, the rounded lead end at y = LENGTH.  The Front and Right
Planes contain the axis, published as ``ScrewAxis`` (Front x Right); the Top
Plane is the pressed end face, so an assembly places the pin by that plane
INSERTION above the crossbar underside.
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
from _fit_ream_h7 import REAM_H7
from _hole_spec import DRILL_POINT_H
from _printed_tolerance import drilled_oversize_mm, printed_band_mm
from _supplier_pin_data import SupplierPinReference

# The knife mount's slip hole and its depth print on its sheet, in
# its unit (#290); the press ream's on MHA-FR-02's.
_MOUNT_UNIT = drawing_unit("parts/sm-knife-mount", _config.parts("sm-knife-mount"))
# The press ream's size, depth and stations print on MHA-FR-02, in its unit,
# read off its row (fr_top_frame_spec imports this module).
_FRAME_UNIT = drawing_unit("parts/fr-top-frame", _config.parts("fr-top-frame"))

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
# The pressed end's flat face, where the knockout's punch drives it: ASME
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

# General tolerance the crossbar ream's station's printed places claim
# (title block).
_XXX = printed_band_mm(3, unit=_FRAME_UNIT)

# One pin per knife mount, its axis HANGER_OFFSET along machine +X from the
# knife-hanger screw axis in BOTH parts (block local X is machine X: the
# mounts are placed unrotated).  Owner ruling 2026-10-24 (T+H3, machinist
# ENFORCE review of MHA-SM-02, rule 16): the pin presses into the MHA-FR-02
# crossbar, into a blind ream drilled from the underside, a knockout
# drilled up from its drill point through the top, located by the drawn
# common axis only (+/-.005 implied, owner ruling 2026-10-27 (c)), and slips
# into the hardened knife mount's round hole (datum B).  The crossbar prints
# the ream's station .XXX from its screw axis (HANGER_OFFSET_TOL).  Owner
# ruling 2026-11-08 (Pedro), #2144 item 11.3 (scheme S1): the -X pin, its
# crossbar ream and the block's slot (datum C) are deleted; the block turns
# about its one pin until its yaw is set at MHA-SM-00: the front block's by
# the gauge bar slid through both mounts' bores (step 5), the rear block's
# by the rock gauge (6G) (``build_sm_summing_assembly``).
PER_MOUNT = 1
MOUNTS = 2
QUANTITY = PER_MOUNT * MOUNTS
# 7.632 for the #10-24 hex bolt that replaced the #6-32 screw (the user's
# knife-hanger regression fix): the crossbar's then Ø6.045 #10 loose clearance
# hole (later a C drill Ø6.147, owner ruling 2026-11-06; an E drill Ø6.350
# since owner ruling 2026-11-24, fit audit OQ19), drilled from the
# underside under a then shallow top spotface, and its then
# slot, shortened to 3.95, each kept 2.0 of wall at the print-worst plus
# drill drift, inside to the hole and outside to the 25 crossbar's face.
# History: 7.100, not the original 1/4 in, because at 6.350 the crossbar's
# blind slot left under 2.0 of wall to the then #6 clearance hole at the
# print-worst plus drill drift (codex machinist review of fr_top_frame
# 4d11a94e); Q7 option C, approved as built by the user 2026-10-13 (#1348).
HANGER_OFFSET = 7.62  # .300 (#290: was 7.632, off the inch grid)
HANGER_OFFSET_PLACES = 3
HANGER_OFFSET_TOL = _XXX  # 0.127

# --- The press: the crossbar's blind reams (owner ruling 2026-10-24, T+H3) --
# Owner decision 2026-11-19 (#3124, item 3: the simplest manufacture,
# re-keys accepted): drilled and reamed from the faced underside to a drill
# point, the full-diameter depth printed as a MIN (single limit, open
# above).  The pin is pressed to its proud (below), never to the floor, so
# nothing bears on the point and the floor needs no flat or corner limit.
# A THRU ream, which would have dropped the separate knockout, is not clean:
# at its .300 station its Ø.1245 exit on the faced top already lies under
# the MHA-SM-VN-54 washer's rim at nominal (build_fr_top_frame's washer
# ring), so the knockout stays.
PRESS_DEPTH = 12.7  # .50 MIN, full diameter
PRESS_DEPTH_PLACES = 2
# The ream prints the owned .1240 chucking reamer's size (cad/process/shop/
# inventory.toml) at four places and no band (drawing-guidelines rule 4,
# form 3: the bought pin is the gauge; the MHA-PD-18 latch-pin precedent,
# fit audit question 9).  PRESS_HOLE_DIA_BAND is the analysis band, what
# that reamer cuts (REAM_H7), which the press and the frame's walls consume;
# never a printed limit.
PRESS_HOLE_DIA = 3.1496  # .1240
PRESS_HOLE_DIA_BAND = REAM_H7  # (upper, lower): +.0005/0
PRESS_HOLE_DIA_PLACES = 4
# The 118° drill point past the full-diameter depth, modelled on the ream
# size (_hole_spec's tip-height ratio, which every drill point shares).
PRESS_POINT_H = PRESS_HOLE_DIA / 2.0 * DRILL_POINT_H
# (loosest, tightest) press from the ream band and the catalogue band:
# 0.01524..0.03302, printed rounded outward to four places.
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
if PRESS_INTERFERENCE_PRINTED != (0.0152, 0.0331):
    raise AssertionError(f"knife-mount dowel press prints {PRESS_INTERFERENCE_PRINTED}")

# --- The proud: set at assembly (owner decision 2026-11-19, #3124 item 3) ---
# MHA-SM-00 step 1 presses each pin until it stands PROUD below the crossbar
# underside: an associative setting dimension on that sheet (two places, the
# title block's .XX; ``sm_summing_assembly_spec`` asserts the band it prints
# is PROUD_TOL).  The proud so no longer stacks the ream depth and the pin's
# length grade: the grade moves the pressed end inside the ream instead.
PROUD = 7.112  # .28
PROUD_PLACES = 2
PROUD_TOL = printed_band_mm(PROUD_PLACES, unit=_FRAME_UNIT)  # 0.254
PROUD_MIN = PROUD - PROUD_TOL  # 6.858
PROUD_MAX = PROUD + PROUD_TOL  # 7.366
# The pressed end's height above the underside: 11.938 nominal,
# 11.430..12.446 over the length grade and the proud's band.
INSERTION = LENGTH - PROUD
INSERTION_MIN = LENGTH - LENGTH_GRADE - PROUD_MAX
INSERTION_MAX = LENGTH + LENGTH_GRADE - PROUD_MIN
# The deepest pressed end stays in the full-diameter ream, short of the
# drill point: 12.700 - 12.446 = 0.254.  So the pin's chamfer cone never
# meets the point, and the whole pressed length grips reamed wall.
PRESS_POINT_CLEARANCE_MIN = PRESS_DEPTH - INSERTION_MAX
if PRESS_POINT_CLEARANCE_MIN <= 0.0:
    raise AssertionError(
        f"the deepest pressed knife-mount dowel ({INSERTION_MAX:.3f}) reaches the"
        f" crossbar ream's drill point ({PRESS_DEPTH:.3f} full diameter)"
    )

# --- The slip: the knife mount's round hole (datum B) -----------------------
# Owner ruling 2026-11-24, fit audit OQ19 (APPROVED as recommended, option
# A): the hole is a #30 drill (.1285 = 3.2639) at the title block's DRILLED
# HOLES row (+.004/0), no reamer: .0032-.0074 in (0.0812-0.1880) on the
# pin's catalogue diameter.  The former 0.02-0.10 window was the pinion
# cam's slip band copied over; nothing in this joint reads it.  What the
# slip must do: its minimum lets the pin enter the hole (> 0) and is the
# tilt proof's angular room (``build_sm_summing_assembly``
# KNIFE_DOWEL_TILT_ALLOWED_DEG); its maximum is the block's shift on the
# pin, charged where it binds -- the hanger bolt's float and the rear
# mount's yaw range (``build_sm_summing_assembly`` HANGER_SCREW_FLOAT_SPARE,
# KNIFE_REAR_YAW_RANGE_DEG) and the washer's bearing width
# (``build_fr_top_frame``) -- each with its own guard.
SLIP_HOLE_DRILL = "#30"
SLIP_HOLE_DIA = 3.2639  # .1285
SLIP_HOLE_DIA_BAND = (drilled_oversize_mm(unit=_MOUNT_UNIT), 0.0)  # title block
SLIP_HOLE_DIA_PLACES = 4
SLIP_CLEARANCE_MIN = round(SLIP_HOLE_DIA + SLIP_HOLE_DIA_BAND[1] - DIA_MAX, 6)
SLIP_CLEARANCE_MAX = round(SLIP_HOLE_DIA + SLIP_HOLE_DIA_BAND[0] - DIA_MIN, 6)
if SLIP_CLEARANCE_MIN <= 0.0:
    raise AssertionError(
        f"the {SLIP_HOLE_DRILL} hole ({SLIP_HOLE_DIA:.4f}) does not clear"
        f" MHA-SM-VN-53's largest diameter ({DIA_MAX:.4f})"
    )
# The block's round hole, blind from its top seat to a drill point (owner
# decision 2026-11-19, #3124 item 4), its full-diameter depth printed .XX:
# the floor-clearance and tilt stacks read the depth's band.
SLIP_DEPTH = 9.398  # .37
SLIP_DEPTH_PLACES = 2
SLIP_DEPTH_TOL = printed_band_mm(2, unit=_MOUNT_UNIT)  # 0.254
# A press-fit dowel grips at least 1.5 D (the drawing-guidelines.md rule 18 (thread engagement) engagement floor,
# applied to the press as ``pd_vn_transgear_latch_pin_spec`` does), counted over
# the full diameter only: the chamfer inside the hole carries no interference.
PRESS_ENGAGEMENT_MIN_D = 1.5
# The seat is clamped to the casting underside (no gap), so the pin's proud
# length goes straight down the knife mount's hole.  The shallowest hole's
# full diameter still takes the longest proud pin, or the pin would reach
# the drill point and hold the seat off the casting: 9.144 - 7.366 = 1.778.
SLIP_DEPTH_CLEARANCE_MIN = SLIP_DEPTH - SLIP_DEPTH_TOL - PROUD_MAX
if SLIP_DEPTH_CLEARANCE_MIN <= 0.0:
    raise AssertionError(
        f"the longest proud knife-mount dowel ({PROUD_MAX:.3f}) bottoms in the"
        f" shallowest knife-mount hole ({SLIP_DEPTH - SLIP_DEPTH_TOL:.3f})"
    )
# The shortest pressed length, less its chamfer: (11.430 - 0.443) / 3.175 =
# 3.46 D in the crossbar.
PRESS_ENGAGEMENT_D_MIN = (INSERTION_MIN - CHAMFER_LEN) / DIA
if PRESS_ENGAGEMENT_D_MIN < PRESS_ENGAGEMENT_MIN_D:
    raise AssertionError(
        f"knife-mount dowel grips {PRESS_ENGAGEMENT_D_MIN:.2f} D in the crossbar,"
        f" under {PRESS_ENGAGEMENT_MIN_D} D"
    )
# The shortest proud pin, less its free (round) end's crown, keys the block
# over at least 1.5 D of full diameter: (6.858 - 0.406) / 3.175 = 2.03 D.
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
    diameter_precision=4,
    length_precision=2,
    sheet_unit=SHEET_UNIT,
)
