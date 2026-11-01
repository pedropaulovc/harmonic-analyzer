r"""Geometry-only contract for the pinion swing bracket.

This module contains the nominal inputs consumed by both the part and the
drive-train assembly.  It deliberately owns no drawing notes or annotation
metadata: importing it from ``build_drive_train_assembly`` therefore makes a
real geometry edit a full assembly-recipe change without treating drawing-only
wording as assembly build logic.
"""

from __future__ import annotations

import _config
from _package_units import drawing_unit
from _printed_tolerance import printed_band_mm

# #290: the registry row's drawing_unit (in) is this sheet's unit; every band
# and place below is authored for it, and the drive train, the rig layout and
# the set-pin webs read the printed rows through it.
UNIT = drawing_unit("parts/dt-pinion-bracket", _config.parts("dt-pinion-bracket"))


# cad/config/dimensions.yaml "Chapter 25", photo-scaled.  The pivot bore is at
# the origin, the arbor bore at (0, C2C), and the blind follower-pin seat enters
# the -X edge (machine EAST after the assembly's Ry(180)), ABOVE the pivot.
# 2026-09 photo re-derive (ch25 page002_img01 at ~10 px/mm on the O22.4 drum,
# page001_img02): the strap is SHORT and near-vertical -- ~28 pivot-to-arbor,
# ~15 wide, the pivot block sitting right under the drum -- not the 43 x 18
# 50-deg-leaning link of the first pass. The follower stud sits ~6 above the
# pivot on the lift-rod side, resting on the cam collar (the p.68 arrow).
# #290: WIDTH, C2C and PIN_DROP are kinematic closures (the strap's swing into
# mesh, the follower's park gap, the spring blade's flank), so they keep their
# millimetre nominals and print rounded in inches; every reader judges them at
# the PRINTED limits.
WIDTH = 15.0
C2C = 28.0
# THICKNESS re-derived 2026-10 from ch25 page001_img01, which frames BOTH straps
# (the follower stud pokes out of the front strap, lower right).  The O22.433
# pinion drum spans 174 px there, so the photo runs 7.76 px/mm.  Each strap shows
# a foreshortened broad face plus its edge: front 61 + 62 px, back 86 + 40 px.
# Solving 15*cos(t) + T*sin(t) = (face + edge)/7.76 for each end's own view angle
# (cos t = face/(15*7.76)) gives T = 9.4 front, 7.6 back.  U28 (user, 2026-09-23)
# set 9.0, inside that photo band; #290 snaps it to .354 at .XXX, the row the
# rig's span stack, the follower-seat web and the cross-hole web all read.  The
# seat and the cross hole are printed CENTRED on the thickness, which leaves
# the far-face webs over the .080 target (dt_pinion_bracket_spec.PIN_SEAT_WEB_WORST,
# dt_vn_pinion_strap_pin_spec.STRAP_FACE_WEB_WORST).
THICKNESS = 8.9916  # .354
THICKNESS_PLACES = 3  # Depth prints .XXX (dt_pinion_bracket_spec.DRAWING_PRECISION)
THICKNESS_BAND = printed_band_mm(THICKNESS_PLACES, unit=UNIT)  # .005; the rig's stack reads it
PIVOT_BORE = 6.35  # .2500, REAM_SLIDE on the MHA-DT-19 shaft
ARBOR_BORE = 7.9375  # 5/16 in, REAM_SLIDE on the MHA-DT-22 arbor
# #290: the MHA-DT-25 stud is 5/32 drill rod, bonded in a seat cut by the
# purchased .1570 chucking reamer (REAM_H7).
PIN_BORE = 3.9878  # .157
PIN_DROP = -7.0  # NEGATIVE: the stud seat is 7 ABOVE the pivot bore (on the
# straight flank).  U28 raised it from 6: the seat keeps a 2.4 mm worst-case
# web to the O6.35 pivot bore, and the higher pin lets the lift cam carry a
# 2.1 mm thin-side wall at the same park gap.
PIN_SEAT = 4.064  # .16
# Option E-a: the 1/16 cross hole runs along local X on the strap mid-plane,
# this far from the part origin face (build_dt_pinion_bracket drives it, the
# drive train reads it to place the MHA-DT-VN-63 pins).
CROSS_HOLE_CZ = THICKNESS / 2.0

R_END = WIDTH / 2.0
HALF_WIDTH = R_END
OVERALL_LENGTH = C2C + 2.0 * R_END

# Printed places of the dimensions whose bands the E-a cross-hole webs read
# (dt_vn_pinion_strap_pin_spec).  dt_pinion_bracket_spec.DRAWING_PRECISION states them
# natively from these, so a precision change reaches the web gates by itself
# (restricted review, ruling 3).
# The end radii are the unmated outline: .XX (R.30), whose band still buries
# the longest set pin in the narrowest foot (PIN_BURIED_MARGIN).
END_RADIUS_PLACES = 2  # BottomCapRadius / TopCapRadius
# CrossHoleCz, from broad face A: half the thickness, at .XX (.18); the far-face
# web clears the .080 target at that row.  The hole's height prints no offset:
# its centre sits on the pivot-axis line the flank view draws, an implied zero
# the webs charge (dt_vn_pinion_strap_pin_spec).
CROSS_HOLE_CZ_PLACES = 2

