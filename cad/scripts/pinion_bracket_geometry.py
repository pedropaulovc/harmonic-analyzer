r"""Geometry-only contract for the pinion swing bracket.

This module contains the nominal inputs consumed by both the part and the
drive-train assembly.  It deliberately owns no drawing notes or annotation
metadata: importing it from ``build_drive_train_assembly`` therefore makes a
real geometry edit a full assembly-recipe change without treating drawing-only
wording as assembly build logic.
"""

from __future__ import annotations


# cad/config/dimensions.yaml "Chapter 25", photo-scaled.  The pivot bore is at
# the origin, the arbor bore at (0, C2C), and the blind follower-pin seat enters
# the -X edge (machine EAST after the assembly's Ry(180)), ABOVE the pivot.
# 2026-09 photo re-derive (ch25 page002_img01 at ~10 px/mm on the O22.4 drum,
# page001_img02): the strap is SHORT and near-vertical -- ~28 pivot-to-arbor,
# ~15 wide, the pivot block sitting right under the drum -- not the 43 x 18
# 50-deg-leaning link of the first pass. The follower stud sits ~6 above the
# pivot on the lift-rod side, resting on the cam collar (the p.68 arrow).
WIDTH = 15.0
C2C = 28.0
# THICKNESS re-derived 2026-10 from ch25 page001_img01, which frames BOTH straps
# (the follower stud pokes out of the front strap, lower right).  The O22.433
# pinion drum spans 174 px there, so the photo runs 7.76 px/mm.  Each strap shows
# a foreshortened broad face plus its edge: front 61 + 62 px, back 86 + 40 px.
# Solving 15*cos(t) + T*sin(t) = (face + edge)/7.76 for each end's own view angle
# (cos t = face/(15*7.76)) gives T = 9.4 front, 7.6 back.  U28 (user, 2026-09-23)
# sets 9.0, inside that photo band: it leaves (9 - 4)/2 = 2.5 mm of web each side
# of the O4 blind follower-stud seat.  Rule 12 (audit W23) found 1.18 at the
# worst case when the seat was printed from one face (Depth .X, PinSeatCz .XX);
# it is now printed CENTRED on the thickness, which leaves 2.04 at the worst
# case (pinion_bracket_spec.PIN_SEAT_WEB_WORST) with no exception needed.
THICKNESS = 9.0
PIVOT_BORE = 6.35
ARBOR_BORE = 8.0
PIN_BORE = 4.0
PIN_DROP = -7.0  # NEGATIVE: the stud seat is 7 ABOVE the pivot bore (on the
# straight flank).  U28 raised it from 6: the O4 seat keeps a 2.4 mm worst-case
# web to the O6.35 pivot bore, and the higher pin lets the lift cam carry a
# 2.1 mm thin-side wall at the same park gap.
PIN_SEAT = 4.0

R_END = WIDTH / 2.0
HALF_WIDTH = R_END
OVERALL_LENGTH = C2C + 2.0 * R_END

