r"""Geometry-only contract for the pinion swing bracket.

This module contains the nominal inputs consumed by both the part and the
drive-train assembly.  It deliberately owns no drawing notes or annotation
metadata: importing it from ``build_drive_train_assembly`` therefore makes a
real geometry edit a full assembly-recipe change without treating drawing-only
wording as assembly build logic.
"""

from __future__ import annotations

from _inch import inch
from _printed_tolerance import printed_band_mm


# cad/config/dimensions.yaml "Chapter 25", photo-scaled.  The pivot bore is at
# the origin, the arbor bore at (0, C2C), and the blind follower-pin seat enters
# the -X edge (machine EAST after the assembly's Ry(180)), ABOVE the pivot.
# 2026-09 photo re-derive (ch25 page002_img01 at ~10 px/mm on the O22.4 drum,
# page001_img02): the strap is SHORT and near-vertical -- ~28 pivot-to-arbor,
# ~15 wide, the pivot block sitting right under the drum -- not the 43 x 18
# 50-deg-leaning link of the first pass. The follower stud sits ~6 above the
# pivot on the lift-rod side, resting on the cam collar (the p.68 arrow).
# All-inch experiment: 19/32 wide (the nearest 9/16 leaves the longest 1/2 in
# MHA-VN-033 pin proud of the narrowest .X strap foot, vn_pinion_strap_pin_spec
# PIN_BURIED_MARGIN), 1-1/8 bore to bore (the nearest 1/16).  The 21/32 pivot
# bore puts the drum axis exactly 1-3/32 above it, so the parked strap leans
# 13.54 deg (it was 8.14; 1-3/32 would stand it dead vertical).
WIDTH = inch(19, 32)
C2C = inch(9, 8)
# THICKNESS re-derived 2026-10 from ch25 page001_img01, which frames BOTH straps
# (the follower stud pokes out of the front strap, lower right).  The O22.433
# pinion drum spans 174 px there, so the photo runs 7.76 px/mm.  Each strap shows
# a foreshortened broad face plus its edge: front 61 + 62 px, back 86 + 40 px.
# Solving 15*cos(t) + T*sin(t) = (face + edge)/7.76 for each end's own view angle
# (cos t = face/(15*7.76)) gives T = 9.4 front, 7.6 back.  U28 (user, 2026-09-23)
# sets 9.0, inside that photo band: it leaves (9 - 4)/2 = 2.5 mm of web each side
# of the O4 blind follower-stud seat.  drawing-guidelines.md rule 17 (walls and webs) (audit W23) found 1.18 at the
# worst case when the seat was printed from one face (Depth .X, PinSeatCz .XX);
# it is now printed CENTRED on the thickness, which leaves 2.04 at the worst
# case (dt_pinion_bracket_spec.PIN_SEAT_WEB_WORST) with no exception needed.
THICKNESS = inch(3, 8)  # 3/8 in plate
THICKNESS_PLACES = 1  # Depth prints .X (dt_pinion_bracket_spec.DRAWING_PRECISION)
THICKNESS_BAND = printed_band_mm(THICKNESS_PLACES)  # 0.8; the rig's stack reads it
PIVOT_BORE = 6.35
ARBOR_BORE = inch(5, 16)  # follows the Ø5/16 MHA-DT-022 arbor (REAM_SLIDE)
# Ø5/32 drill-rod MHA-DT-025 stud (REAM_H7).  1/32: the nearest 3/16 leaves the
# far-face follower-seat web 1.43 at the worst case, under the 1.5 floor
# (dt_pinion_bracket_spec.PIN_SEAT_WEB_WORST).
PIN_BORE = inch(5, 32)
# NEGATIVE: the stud seat is 7/32 in ABOVE the pivot bore (on the straight
# flank).  U28 raised it from 6: the seat keeps its web to the Ø6.35 pivot
# bore, and the higher pin lets the lift cam carry its thin-side wall at the
# 0.10..0.25 park gap.  1/32: with the nearest 1/4 the Ø9/16 x 1/16 cam parks
# 0.91 under the stud; 7/32 parks it 0.115 under (build_dt_drive_train_assembly).
PIN_DROP = -inch(7, 32)
PIN_SEAT = inch(3, 16)
# Option E-a: the 1/16 cross hole runs along local X on the strap mid-plane,
# this far from the part origin face (build_dt_pinion_bracket drives it, the
# drive train reads it to place the MHA-VN-033 pins).
CROSS_HOLE_CZ = THICKNESS / 2.0

R_END = WIDTH / 2.0
HALF_WIDTH = R_END
OVERALL_LENGTH = C2C + 2.0 * R_END

# Printed places of the dimensions whose bands the E-a cross-hole webs read
# (vn_pinion_strap_pin_spec).  dt_pinion_bracket_spec.DRAWING_PRECISION states them
# natively from these, so a precision change reaches the web gates by itself
# (restricted review, ruling 3).
END_RADIUS_PLACES = 1  # BottomCapRadius / TopCapRadius
CROSS_HOLE_CZ_PLACES = 2  # CrossHoleCz, from broad face A
CROSS_HOLE_FROM_BORE_WALL_PLACES = 2  # CrossHoleFromBoreWall

