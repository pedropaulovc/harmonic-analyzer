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
# the west (-X) edge.
WIDTH = 18.0
C2C = 43.0
THICKNESS = 5.0
PIVOT_BORE = 6.35
ARBOR_BORE = 8.0
PIN_BORE = 4.0
PIN_DROP = 2.0
PIN_SEAT = 4.0

R_END = WIDTH / 2.0
HALF_WIDTH = R_END
OVERALL_LENGTH = C2C + 2.0 * R_END

# The drum-side support's eccentric collar crosses the pivot cap's outer
# quadrant in the strap plane. Two R6.90 open scallops cover the collar's
# complete ECC+OD/2 swept envelope, plus 0.25 air, at both the parked and
# engaged strap orientations. The
# coordinates are part-local and are asserted from the live linkage transform
# in build_drive_train_assembly, so a future axis/angle change fails loud.
CAM_RELIEF_CLEARANCE = 0.25
CAM_RELIEF_RADIUS = 6.90
CAM_RELIEF_PARK_CENTER = (-12.014136997215108, 6.2204465116279115)
CAM_RELIEF_ENGAGED_CENTER = (-12.611076880581468, 4.898385703876358)
CAM_RELIEF_ENVELOPE_RADIUS = ECC + CAM_OD / 2.0 + CAM_RELIEF_CLEARANCE
CAM_RELIEF_MIN_PIVOT_LIGAMENT = min(
    math.hypot(*CAM_RELIEF_PARK_CENTER),
    math.hypot(*CAM_RELIEF_ENGAGED_CENTER),
) - CAM_RELIEF_RADIUS - PIVOT_BORE / 2.0
if CAM_RELIEF_MIN_PIVOT_LIGAMENT < 2.5:
    raise AssertionError("cam scallop leaves less than 2.5 mm at the pivot bore")
