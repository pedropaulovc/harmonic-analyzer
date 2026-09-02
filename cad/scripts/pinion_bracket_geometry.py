r"""Geometry-only contract for the pinion swing bracket.

This module contains the nominal inputs consumed by both the part and the
drive-train assembly.  It deliberately owns no drawing notes or annotation
metadata: importing it from ``build_drive_train_assembly`` therefore makes a
real geometry edit a full assembly-recipe change without treating drawing-only
wording as assembly build logic.
"""

from __future__ import annotations

import math

from pinion_cam_geometry import CAM_OD, ECC

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
THICKNESS = 5.0
PIVOT_BORE = 6.35
ARBOR_BORE = 8.0
PIN_BORE = 4.0
PIN_DROP = -6.0  # NEGATIVE: the stud seat is 6 ABOVE the pivot bore (on the
# straight flank), where the collar under it can clear the base top
PIN_SEAT = 4.0

R_END = WIDTH / 2.0
HALF_WIDTH = R_END
OVERALL_LENGTH = C2C + 2.0 * R_END

# The v2-reclosed eccentric collar crosses the pivot cap's outer quadrant in
# the strap plane. Two R6.90 open scallops cover the collar's complete
# ECC+OD/2 swept envelope, plus 0.25 air, at both the parked and engaged strap
# orientations. Their overlap also covers the intervening 7.298-deg arc. The
# coordinates are part-local and are asserted from the live linkage transform
# in build_drive_train_assembly, so a future axis/angle change fails loud.
CAM_RELIEF_CLEARANCE = 0.25
CAM_RELIEF_RADIUS = 6.90
CAM_RELIEF_PARK_CENTER = (-12.6368839229725, 0.06789999999999563)
CAM_RELIEF_ENGAGED_CENTER = (-12.567707922051557, -1.3221812578778047)
CAM_RELIEF_ENVELOPE_RADIUS = ECC + CAM_OD / 2.0 + CAM_RELIEF_CLEARANCE
CAM_RELIEF_MIN_PIVOT_LIGAMENT = min(
    math.hypot(*CAM_RELIEF_PARK_CENTER),
    math.hypot(*CAM_RELIEF_ENGAGED_CENTER),
) - CAM_RELIEF_RADIUS - PIVOT_BORE / 2.0
if CAM_RELIEF_MIN_PIVOT_LIGAMENT < 2.5:
    raise AssertionError("cam scallop leaves less than 2.5 mm at the pivot bore")
